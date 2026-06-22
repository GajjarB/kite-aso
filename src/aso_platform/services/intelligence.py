"""Local-first ASO intelligence services."""

from __future__ import annotations

import concurrent.futures
import csv
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from dataclasses import dataclass
from statistics import mean
from dataclasses import dataclass
from typing import Any

from core.fetcher import fetch_reviews
from core.keywords import extract_keywords_from_text, mine_review_keywords

from ..providers import PlayStorePublicProvider, PlayStoreSearchProvider
from ..providers.apple_store import AppleLookupProvider
from ..registry import RegistryError, ensure_source_approved, get_source, load_source_registry
from .app_inspector import AppInspectionService
from .keyword_discovery import KeywordDiscoveryService
from .keyword_rank import KeywordRankService, RankConfig
from .local_store import LocalDataStore
from .workspace import WorkspaceService


@dataclass
class ShareOfVoiceOptions:
    lang: str = "en"
    country: str = "us"
    limit: int = 50


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _confidence(label: str, score: int, rationale: str) -> dict[str, Any]:
    return {"label": label, "score": max(0, min(100, int(score))), "rationale": rationale}


def _warning(code: str, message: str, severity: str = "warning", source_id: str = "local_modeled_estimates") -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message, "source_id": source_id}


def _evidence(source_id: str, source_type: str, scope: str, lang: str = "en", country: str = "us") -> dict[str, Any]:
    try:
        source = get_source(source_id)
        display_name = source.display_name
    except RegistryError:
        display_name = source_id
    return {
        "source_id": source_id,
        "display_name": display_name,
        "source_type": source_type,
        "scope": scope,
        "fetched_at": _now(),
        "from_cache": False,
        "locale": lang,
        "country": country,
    }


def _estimate(value: float | int, method: str, confidence: str, evidence_count: int) -> dict[str, Any]:
    return {
        "value": round(value, 2) if isinstance(value, float) else value,
        "method": method,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "is_estimate": True,
    }


def _tokens(text: str) -> set[str]:
    return {item for item in re.sub(r"[^a-z0-9\s]+", " ", (text or "").lower()).split() if len(item) > 2}


class RankHistoryService:
    def __init__(self, store: LocalDataStore | None = None):
        self.store = store or LocalDataStore()

    def history(self, keyword: str = "", package_id: str = "") -> dict[str, Any]:
        rows = self._filtered(keyword, package_id)
        positions = [row["position"] for row in rows if row.get("position") is not None]
        summary = {
            "checks": len(rows),
            "hits": len(positions),
            "first_seen": rows[0]["recorded_at"] if rows else "",
            "last_seen": rows[-1]["recorded_at"] if rows else "",
            "best_position": min(positions) if positions else None,
            "worst_position": max(positions) if positions else None,
            "volatility": self._volatility(positions),
        }
        return {
            "request_context": {"keyword": keyword, "target_package_id": package_id, "requested_at": _now(), "sources": ["local_rank_history"]},
            "history": rows,
            "summary": summary,
            "evidence": [_evidence("local_modeled_estimates", "local_history", "keyword_rank_history")],
            "warnings": [] if rows else [_warning("NO_HISTORY", "No local rank history matched the request.", "info")],
            "confidence": _confidence("high" if rows else "low", 90 if rows else 20, "Computed from local rank snapshots."),
        }

    def delta(self, keyword: str, package_id: str) -> dict[str, Any]:
        rows = self._filtered(keyword, package_id)
        previous = rows[-2] if len(rows) >= 2 else None
        current = rows[-1] if rows else None
        previous_position = previous.get("position") if previous else None
        current_position = current.get("position") if current else None
        delta = None
        if previous_position is not None and current_position is not None:
            delta = previous_position - current_position
        movement = "new" if previous is None and current else "unchanged"
        if delta is not None:
            movement = "up" if delta > 0 else "down" if delta < 0 else "unchanged"
        return {
            "request_context": {"keyword": keyword, "target_package_id": package_id, "requested_at": _now(), "sources": ["local_rank_history"]},
            "delta": {
                "previous_position": previous_position,
                "current_position": current_position,
                "delta": delta,
                "movement": movement,
                "previous_recorded_at": previous.get("recorded_at") if previous else "",
                "current_recorded_at": current.get("recorded_at") if current else "",
            },
            "evidence": [_evidence("local_modeled_estimates", "local_history", "keyword_rank_delta")],
            "warnings": [] if len(rows) >= 2 else [_warning("INSUFFICIENT_HISTORY", "At least two matching rank snapshots are needed for a delta.", "info")],
            "confidence": _confidence("high" if len(rows) >= 2 else "low", 90 if len(rows) >= 2 else 30, "Computed from local rank snapshots."),
        }

    def _filtered(self, keyword: str, package_id: str) -> list[dict[str, Any]]:
        rows = []
        keyword = keyword.lower().strip()
        package_id = package_id.lower().strip()
        for record in self.store.read_events("rank_history"):
            payload = record.get("payload", {})
            row_keyword = str(payload.get("keyword", "")).lower()
            row_package = str(payload.get("target_package_id", "")).lower()
            if keyword and row_keyword != keyword:
                continue
            if package_id and row_package != package_id:
                continue
            rows.append(
                {
                    "recorded_at": record.get("recorded_at", ""),
                    "keyword": payload.get("keyword", ""),
                    "target_package_id": payload.get("target_package_id", ""),
                    "position": payload.get("target_position"),
                    "country": payload.get("request_context", {}).get("country", ""),
                    "lang": payload.get("request_context", {}).get("lang", ""),
                }
            )
        return sorted(rows, key=lambda item: item["recorded_at"])

    @staticmethod
    def _volatility(positions: list[int]) -> float:
        if len(positions) < 2:
            return 0.0
        return round(mean(abs(positions[index] - positions[index - 1]) for index in range(1, len(positions))), 2)


@dataclass(frozen=True)
class DatabaseBuildParams:
    category: str = ""
    seed_text: str = ""
    lang: str = "en"
    country: str = "us"
    limit: int = 40


class KeywordIntelligenceService:
    def __init__(self, store: LocalDataStore | None = None, discovery_service: KeywordDiscoveryService | None = None):
        self.store = store or LocalDataStore()
        self.discovery_service = discovery_service or KeywordDiscoveryService()

    def build_database(self, params: DatabaseBuildParams) -> dict[str, Any]:
        report = self.discovery_service.discover(seed_text=params.seed_text, category=params.category, lang=params.lang, country=params.country, limit=params.limit).to_dict()
        facts = []
        for item in report.get("keywords", []):
            fact = {
                "keyword": item["keyword"],
                "source": item.get("source", "unknown"),
                "country": params.country,
                "language": params.lang,
                "discovered_at": _now(),
                "topic": params.category or params.seed_text,
                "intent": item.get("type", "keyword"),
                "related_apps": [],
                "score": item.get("composite_score", 0),
            }
            self.store.append_event("keyword_facts", fact)
            facts.append(fact)
        return {
            "request_context": {"category": params.category, "seed_text": params.seed_text, "lang": params.lang, "country": params.country, "limit": params.limit, "requested_at": _now(), "sources": report["request_context"].get("sources", [])},
            "keywords": facts,
            "evidence": report.get("evidence", []),
            "warnings": report.get("warnings", []),
            "confidence": report.get("confidence", _confidence("medium", 60, "Keyword facts were generated locally.")),
        }

    def score(self, keywords: list[str], app_text: str = "", current_rank: int | None = None) -> dict[str, Any]:
        scored = []
        app_tokens = _tokens(app_text)
        for keyword in keywords:
            keyword_tokens = _tokens(keyword)
            evidence_count = len(keyword_tokens)
            volume = min(100, 20 + len(keyword) * 1.4 + len(keyword_tokens) * 8)
            difficulty = min(100, 25 + len(keyword_tokens) * 11 + (current_rank or 20) * 0.8)
            relevancy = 50
            if keyword_tokens:
                relevancy = round(len(keyword_tokens & app_tokens) / len(keyword_tokens) * 100) if app_tokens else 55
            opportunity = max(0, min(100, (volume * 0.45) + (relevancy * 0.35) + ((100 - difficulty) * 0.2)))
            scored.append(
                {
                    "keyword": keyword,
                    "volume_estimate": _estimate(volume, "local keyword length and phrase specificity proxy", "low", evidence_count),
                    "difficulty": _estimate(difficulty, "local competition proxy without paid volume data", "low", evidence_count),
                    "relevancy": _estimate(relevancy, "keyword token overlap against supplied app text", "medium" if app_text else "low", evidence_count),
                    "opportunity": _estimate(opportunity, "weighted volume, relevancy, and inverse difficulty", "low", evidence_count),
                }
            )
        return {
            "request_context": {"keywords": keywords, "requested_at": _now(), "sources": ["local_modeled_estimates"]},
            "scores": scored,
            "evidence": [_evidence("local_modeled_estimates", "local_model", "keyword_opportunity_score")],
            "warnings": [_warning("ESTIMATE_ONLY", "Keyword volume, difficulty, and opportunity are modeled estimates, not official store metrics.", "info")],
            "confidence": _confidence("medium" if app_text else "low", 62 if app_text else 45, "Scores use local transparent heuristics."),
        }

    def share_of_voice(self, keywords: list[str], target_package_id: str, competitors: list[str], options: ShareOfVoiceOptions | None = None) -> dict[str, Any]:
        options = options or ShareOfVoiceOptions()
        rank_service = KeywordRankService()
        rows = []
        warnings = []
        for keyword in keywords:
            batched_reports = rank_service.rank_batch(keyword, [target_package_id] + competitors, lang=lang, country=country, limit=limit, save_history=False)
            target = batched_reports[target_package_id].to_dict()
            competitor_rows = []
            for competitor in competitors:
                comp = batched_reports[competitor].to_dict()
                competitor_rows.append({"package_id": competitor, "position": comp.get("target_position")})
                warnings.extend(comp.get("warnings", []))
            target_visibility = self._visibility(target.get("target_position"), options.limit)
            competitor_visibility = sum(self._visibility(row.get("position"), options.limit) for row in competitor_rows)
            rows.append({"keyword": keyword, "target_position": target.get("target_position"), "target_visibility": target_visibility, "competitors": competitor_rows, "competitor_visibility": round(competitor_visibility, 2)})
            warnings.extend(target.get("warnings", []))
        return {
            "request_context": {"keywords": keywords, "target_package_id": target_package_id, "competitors": competitors, "lang": options.lang, "country": options.country, "requested_at": _now(), "sources": ["google_play_public_search", "local_modeled_estimates"]},
            "share_of_voice": rows,
            "evidence": [_evidence("google_play_public_search", "public_search", "share_of_voice", options.lang, options.country), _evidence("local_modeled_estimates", "local_model", "share_of_voice", options.lang, options.country)],
            "warnings": warnings,
            "confidence": _confidence("medium", 65, "Visibility is rank-weighted from public search snapshots."),
        }

    @staticmethod
    def _visibility(position: int | None, limit: int) -> float:
        if not position:
            return 0.0
        return round(max(0.0, (limit - position + 1) / limit), 2)


class CompetitorIntelligenceService:
    def __init__(self, workspace_service: WorkspaceService | None = None):
        self.workspace_service = workspace_service or WorkspaceService()

    def add(self, workspace_ref: str, package_ids: list[str]) -> dict[str, Any]:
        workspace = self.workspace_service.update_competitors(workspace_ref, package_ids, mode="add")
        return {"workspace": workspace.to_dict(), "competitors": workspace.competitors, "warnings": [], "confidence": _confidence("high", 95, "Competitor watchlist is local workspace configuration.")}

    def remove(self, workspace_ref: str, package_ids: list[str]) -> dict[str, Any]:
        workspace = self.workspace_service.update_competitors(workspace_ref, package_ids, mode="remove")
        return {"workspace": workspace.to_dict(), "competitors": workspace.competitors, "warnings": [], "confidence": _confidence("high", 95, "Competitor watchlist is local workspace configuration.")}

    def gap(self, workspace_ref: str, keywords: list[str] | None = None, limit: int = 20) -> dict[str, Any]:
        workspace = self.workspace_service.get(workspace_ref)
        keywords = keywords or [item.strip() for item in workspace.seed_text.split(",") if item.strip()]
        if not keywords and workspace.category:
            keywords = [item["keyword"] for item in KeywordDiscoveryService().discover(category=workspace.category, limit=8).to_dict().get("keywords", [])[:8]]
        rank_service = KeywordRankService()
        gaps = []
        warnings = []
        def get_rank(kw, pkg):
            return rank_service.rank(kw, pkg, lang=workspace.lang, country=workspace.country, limit=limit, save_history=False).to_dict()

        with ThreadPoolExecutor(max_workers=max(1, len(workspace.competitors) + 1)) as executor:
            for keyword in keywords:
                target_future = executor.submit(get_rank, keyword, workspace.target_package_id)
                comp_futures = {competitor: executor.submit(get_rank, keyword, competitor) for competitor in workspace.competitors}

                target = target_future.result()
                comp_positions = []
                for competitor, future in comp_futures.items():
                    comp = future.result()
                    comp_positions.append({"package_id": competitor, "position": comp.get("target_position")})
                    warnings.extend(comp.get("warnings", []))

                best_comp = min([row["position"] for row in comp_positions if row.get("position")] or [None])
                target_pos = target.get("target_position")
                gap_type = "missing_rank" if target_pos is None and best_comp else "competitor_wins" if target_pos and best_comp and best_comp < target_pos else "covered"
                priority = "HIGH" if gap_type == "missing_rank" else "MEDIUM" if gap_type == "competitor_wins" else "LOW"
                gaps.append({"keyword": keyword, "target_position": target_pos, "competitor_positions": comp_positions, "gap_type": gap_type, "priority": priority})
                warnings.extend(target.get("warnings", []))
        return {
            "request_context": {"workspace": workspace.workspace_id, "requested_at": _now(), "sources": ["google_play_public_search"]},
            "gaps": gaps,
            "evidence": [_evidence("google_play_public_search", "public_search", "ranking_based_keyword_gap", workspace.lang, workspace.country)],
            "warnings": warnings,
            "confidence": _confidence("medium", 65, "Gap analysis uses low-volume public rank checks."),
        }

    def timeline(self, workspace_ref: str) -> dict[str, Any]:
        workspace = self.workspace_service.get(workspace_ref)
        targets = [workspace.target_package_id, *workspace.competitors]
        inspector = AppInspectionService()
        changes = []
        warnings = []

        def process_target(package_id: str) -> dict[str, Any]:
            report = inspector.inspect(package_id, lang=workspace.lang, country=workspace.country).to_dict()
            app = report.get("app", {})
            key = f"metadata_snapshots/{package_id.replace('.', '_')}.json"
            previous = self.workspace_service.store.read_json(key, default={}) if hasattr(self.workspace_service, "store") else {}
            diff = {field: {"previous": previous.get(field), "current": app.get(field)} for field in ("title", "summary", "description", "version", "updated") if previous.get(field) != app.get(field)}
            self.workspace_service.store.write_json(key, app) if hasattr(self.workspace_service, "store") else None
            return {
                "package_id": package_id,
                "changed": bool(diff),
                "diff": diff,
                "warnings": report.get("warnings", []),
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(process_target, targets)

        for res in results:
            changes.append({"package_id": res["package_id"], "changed": res["changed"], "diff": res["diff"]})
            warnings.extend(res["warnings"])

        return {
            "request_context": {"workspace": workspace.workspace_id, "requested_at": _now(), "sources": ["google_play_public_store"]},
            "metadata_timeline": changes,
            "evidence": [_evidence("google_play_public_store", "public_store", "competitor_metadata_timeline", workspace.lang, workspace.country)],
            "warnings": warnings,
            "confidence": _confidence("medium", 70, "Metadata changes compare current public metadata with local snapshots."),
        }

    def creatives(self, workspace_ref: str) -> dict[str, Any]:
        timeline = self.timeline(workspace_ref)
        creatives = []
        for item in timeline.get("metadata_timeline", []):
            current = {field: values.get("current") for field, values in item.get("diff", {}).items()}
            asset_text = json.dumps(current, sort_keys=True)
            creatives.append({"package_id": item["package_id"], "asset_hash": hashlib.sha256(asset_text.encode("utf-8")).hexdigest()[:16], "references": current})
        return {**timeline, "creative_timeline": creatives}


class MetadataAuditService:
    def audit(self, package_id: str, keywords: list[str], lang: str = "en", country: str = "us") -> dict[str, Any]:
        report = AppInspectionService().inspect(package_id, lang=lang, country=country).to_dict()
        app = report.get("app", {})
        title = app.get("title", "")
        summary = app.get("summary", "")
        description = app.get("description", "")

        title_lower = title.lower()
        summary_lower = summary.lower()
        combined_lower = f"{title_lower} {summary_lower} {description.lower()}"
        lower_keywords = [keyword.lower() for keyword in keywords]

        keyword_hits = {keyword: lower_kw in combined_lower for keyword, lower_kw in zip(keywords, lower_keywords)}
        title_score = min(100, len(title) * 2 + sum(lower_kw in title_lower for lower_kw in lower_keywords) * 15)
        summary_score = min(100, len(summary) + sum(lower_kw in summary_lower for lower_kw in lower_keywords) * 12)
        long_score = min(100, len(description) / 40 + sum(keyword_hits.values()) * 10)
        recommendations = []
        if keywords and not any(keyword_hits.values()):
            recommendations.append("Add at least one target keyword naturally to public metadata.")
        if len(title) < 10:
            recommendations.append("Use a clearer title that communicates the main job-to-be-done.")
        if len(summary) < 40:
            recommendations.append("Strengthen the short description with a concise benefit and use case.")
        return {
            "request_context": {"package_id": package_id, "keywords": keywords, "lang": lang, "country": country, "requested_at": _now(), "sources": ["google_play_public_store", "local_modeled_estimates"]},
            "metadata_audit": {"title_score": round(title_score), "short_description_score": round(summary_score), "long_description_score": round(long_score), "keyword_coverage": keyword_hits, "field_limits": {"title": 30, "short_description": 80, "long_description": 4000}, "recommendations": recommendations},
            "evidence": report.get("evidence", []) + [_evidence("local_modeled_estimates", "local_rules", "metadata_audit_core", lang, country)],
            "warnings": report.get("warnings", []),
            "confidence": _confidence("medium", 72, "Audit uses public metadata and local store-field rules."),
        }


class ReviewIntelligenceService:
    def analyze(self, package_id: str, count: int = 100, lang: str = "en", country: str = "us") -> dict[str, Any]:
        source = get_source("google_play_reviews_public_store")
        warnings = []
        reviews: list[dict[str, Any]] = []
        try:
            ensure_source_approved(source)
            reviews = fetch_reviews(package_id, count=min(max(1, count), 200), lang=lang, country=country)
        except Exception as exc:
            warnings.append(_warning("REVIEWS_UNAVAILABLE", f"Review intelligence could not fetch public samples: {exc}", "warning", source.source_id))
        mined = mine_review_keywords(reviews) if reviews else {"positive_keywords": [], "negative_keywords": [], "all_keywords": [], "review_count": 0, "positive_count": 0, "negative_count": 0}
        scores = [int(item.get("score", 0) or 0) for item in reviews]
        sentiment = "positive" if scores and mean(scores) >= 4 else "negative" if scores and mean(scores) <= 2.5 else "mixed"
        return {
            "request_context": {"package_id": package_id, "count": count, "lang": lang, "country": country, "requested_at": _now(), "sources": ["google_play_reviews_public_store", "local_modeled_estimates"]},
            "review_intelligence": {"sentiment": sentiment, "average_rating_sample": round(mean(scores), 2) if scores else None, "topics": mined.get("all_keywords", [])[:20], "complaints": mined.get("negative_keywords", [])[:12], "praise": mined.get("positive_keywords", [])[:12], "feature_requests": [item for item in mined.get("all_keywords", []) if any(term in item.get("keyword", "") for term in ("feature", "add", "need", "please"))][:10], "rating_drivers": mined},
            "evidence": [_evidence("google_play_reviews_public_store", "public_reviews", "review_intelligence", lang, country)] if reviews else [],
            "warnings": warnings,
            "confidence": _confidence("medium" if reviews else "low", 68 if reviews else 20, "Review analysis uses limited public samples and local keyword extraction."),
        }


class LocalizationAuditService:
    def audit(self, package_id: str, markets: list[str], keywords: list[str]) -> dict[str, Any]:
        inspector = AppInspectionService()
        ranker = KeywordRankService()
        rows = []
        warnings = []
        for market in markets:
            lang, country = self._parse_market(market)
            app_report = inspector.inspect(package_id, lang=lang, country=country).to_dict()
            rank_rows = []

            rank_reports = ranker.rank_batch(
                keywords, package_id, lang=lang, country=country, limit=10, save_history=False
            )

            for keyword, report_obj in zip(keywords, rank_reports):
                rank_report = report_obj.to_dict()
                rank_rows.append({"keyword": keyword, "position": rank_report.get("target_position")})
                warnings.extend(rank_report.get("warnings", []))
            app = app_report.get("app", {})
            rows.append({"market": market, "lang": lang, "country": country, "metadata_available": bool(app.get("title")), "missing_fields": [field for field in ("title", "summary", "description") if not app.get(field)], "local_keyword_rank": rank_rows})
            warnings.extend(app_report.get("warnings", []))
        return {
            "request_context": {"package_id": package_id, "markets": markets, "keywords": keywords, "requested_at": _now(), "sources": ["google_play_public_store", "google_play_public_search"]},
            "localization_audit": rows,
            "evidence": [_evidence("google_play_public_store", "public_store", "localization_audit"), _evidence("google_play_public_search", "public_search", "localization_audit")],
            "warnings": warnings,
            "confidence": _confidence("medium", 65, "Localization audit uses per-market public metadata and rank snapshots."),
        }

    @staticmethod
    def _parse_market(market: str) -> tuple[str, str]:
        parts = re.split(r"[-_/]", market.lower())
        if len(parts) >= 2:
            return parts[0], parts[1]
        return "en", parts[0] if parts and parts[0] else "us"


class IOSInspectionService:
    def __init__(self, provider: AppleLookupProvider | None = None):
        self.provider = provider or AppleLookupProvider()

    def inspect(self, identifier: str, country: str = "us") -> dict[str, Any]:
        source = get_source(self.provider.source_id)
        warnings = []
        app = {}
        try:
            ensure_source_approved(source)
            app = self.provider.lookup(identifier, country=country)
            if not app:
                warnings.append(_warning("IOS_APP_NOT_FOUND", "Apple lookup returned no matching app.", "warning", source.source_id))
        except (RegistryError, Exception) as exc:
            warnings.append(_warning("IOS_LOOKUP_UNAVAILABLE", f"Apple lookup failed: {exc}", "error", source.source_id))
        normalized = {
            "bundle_id": app.get("bundleId", identifier),
            "track_id": app.get("trackId"),
            "title": app.get("trackName", ""),
            "subtitle": app.get("sellerName", ""),
            "description": app.get("description", ""),
            "rating": app.get("averageUserRating"),
            "screenshots": app.get("screenshotUrls", []),
            "genres": app.get("genres", []),
        }
        return {
            "request_context": {"identifier": identifier, "country": country, "requested_at": _now(), "sources": ["apple_itunes_lookup_api"]},
            "ios_app": normalized,
            "evidence": [_evidence("apple_itunes_lookup_api", "public_store", "ios_app_store_support", "en", country)] if app else [],
            "warnings": warnings,
            "confidence": _confidence("high" if app else "low", 82 if app else 20, "Uses Apple's public iTunes Lookup API."),
        }


class SourceHealthService:
    def health(self) -> dict[str, Any]:
        sources = load_source_registry()
        rows = []
        for source in sources.values():
            legal_ready = source.enabled and source.compliance_status.value == "approved" and source.cost == "free" and source.auth == "none"
            rows.append({"source_id": source.source_id, "display_name": source.display_name, "policy_status": source.compliance_status.value, "enabled": source.enabled, "legal_ready": legal_ready, "last_success": "", "last_failure": "", "failure_reason": "" if legal_ready else "Source is not runtime-approved."})
        warnings = [_warning("SOURCE_NOT_RUNTIME_READY", f"{row['source_id']} is not approved for automatic runtime use.", "info", row["source_id"]) for row in rows if not row["legal_ready"]]
        return {
            "request_context": {"requested_at": _now(), "sources": list(sources)},
            "source_health": rows,
            "evidence": [_evidence("local_modeled_estimates", "local_policy", "source_health_monitor")],
            "warnings": warnings,
            "confidence": _confidence("high", 90, "Health report reflects registry policy without probing disabled sources."),
        }


class AlertService:
    def __init__(self, history_service: RankHistoryService | None = None):
        self.history_service = history_service or RankHistoryService()

    def list(self) -> dict[str, Any]:
        return {"request_context": {"requested_at": _now(), "sources": ["local_rank_history"]}, "alerts": [], "evidence": [], "warnings": [_warning("NO_ALERT_RULES", "Local alert rules are evaluated on demand with alerts check.", "info")], "confidence": _confidence("medium", 60, "No persistent alert rules are configured yet.")}

    def check(self, keyword: str, package_id: str, drop_threshold: int = 3) -> dict[str, Any]:
        delta = self.history_service.delta(keyword, package_id)
        movement = delta.get("delta", {})
        alerts = []
        if movement.get("current_position") is None:
            alerts.append({"alert_type": "target_not_found", "severity": "warning", "triggered_at": _now(), "evidence": movement})
        elif movement.get("delta") is not None and movement.get("delta") <= -abs(drop_threshold):
            alerts.append({"alert_type": "rank_drop", "severity": "warning", "triggered_at": _now(), "evidence": movement})
        return {**delta, "alerts": alerts}


class ReportExportService:
    def export(self, payload: dict[str, Any], output: Path, fmt: str = "json") -> dict[str, Any]:
        output.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "json":
            output.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
        elif fmt == "csv":
            rows = self._flatten(payload)
            with output.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row}))
                writer.writeheader()
                writer.writerows(rows)
        else:
            output.write_text(self._markdown(payload), encoding="utf-8")
        return {"request_context": {"output": str(output), "format": fmt, "requested_at": _now(), "sources": ["local_modeled_estimates"]}, "export": {"path": str(output), "format": fmt}, "evidence": [_evidence("local_modeled_estimates", "local_export", "reporting_exports")], "warnings": [], "confidence": _confidence("high", 95, "Report was exported locally.")}

    @staticmethod
    def _flatten(payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for key, value in payload.items():
            if isinstance(value, list):
                for item in value:
                    rows.append(item if isinstance(item, dict) else {key: item})
            elif isinstance(value, dict):
                rows.append({f"{key}.{inner_key}": inner_value for inner_key, inner_value in value.items() if not isinstance(inner_value, (dict, list))})
        return rows or [{"payload": json.dumps(payload, sort_keys=True)}]

    @staticmethod
    def _markdown(payload: dict[str, Any]) -> str:
        lines = ["# ASO PRO Report", "", f"Generated: {_now()}", ""]
        for key, value in payload.items():
            lines.append(f"## {key.replace('_', ' ').title()}")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True))
            lines.append("```")
            lines.append("")
        return "\n".join(lines)

