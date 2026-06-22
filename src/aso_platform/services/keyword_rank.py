"""Keyword rank tracking with source-policy enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..models import (
    AnalysisWarning,
    ConfidenceAssessment,
    KeywordRankEntry,
    KeywordRankReport,
    SourceEvidence,
)
from ..providers import PlayStoreSearchProvider
from ..registry import RegistryError, ensure_source_approved, get_source, load_source_registry
from ..storage import HistoryStore


@dataclass(frozen=True)
class RankConfig:
    keyword: str
    target_package_id: str
    lang: str = "en"
    country: str = "us"
    limit: int = 20
    save_history: bool = True


class KeywordRankService:
    """Checks where a target app appears in public search results."""

    def __init__(self, provider: PlayStoreSearchProvider | None = None, registry=None, history: HistoryStore | None = None):
        self.provider = provider or PlayStoreSearchProvider()
        self.registry = registry or load_source_registry()
        self.history = history

    def rank_batch(
        self,
        keyword: str,
        target_package_ids: list[str],
        lang: str = "en",
        country: str = "us",
        limit: int = 20,
        save_history: bool = True,
    ) -> dict[str, KeywordRankReport]:
        keyword = keyword.strip()
        target_package_ids = [pid.strip() for pid in target_package_ids if pid.strip()]
        requested_at = datetime.now(timezone.utc).isoformat()
        source = get_source(self.provider.source_id, self.registry)

        base_context = {
            "keyword": keyword,
            "lang": lang,
            "country": country,
            "limit": limit,
            "requested_at": requested_at,
            "sources": [source.source_id],
        }

        reports = {}

        warnings: list[AnalysisWarning] = []
        is_blocked = False
        try:
            ensure_source_approved(source)
        except RegistryError as exc:
            is_blocked = True
            warnings.append(
                AnalysisWarning(
                    code="SOURCE_DISABLED",
                    severity="error",
                    message=str(exc),
                    source_id=source.source_id,
                )
            )

        if not keyword:
            warnings.append(
                AnalysisWarning(
                    code="EMPTY_KEYWORD",
                    severity="error",
                    message="Keyword is required for rank tracking.",
                    source_id=source.source_id,
                )
            )

        if not target_package_ids:
            warnings.append(
                AnalysisWarning(
                    code="EMPTY_PACKAGE_ID",
                    severity="error",
                    message="At least one target package id is required for rank tracking.",
                    source_id=source.source_id,
                )
            )

        # Early exit for validation failures
        if is_blocked or not keyword or not target_package_ids:
            confidence = ConfidenceAssessment(
                label="blocked" if is_blocked else "low",
                score=0,
                rationale="Rank check was blocked by source compliance policy." if is_blocked else "Rank check could not run because required input was missing.",
            )
            for target_id in target_package_ids:
                context = {**base_context, "target_package_id": target_id}
                reports[target_id] = KeywordRankReport(
                    request_context=context,
                    keyword=keyword,
                    target_package_id=target_id,
                    target_position=None,
                    warnings=list(warnings),
                    confidence=confidence,
                )
            return reports

        limit = max(1, min(int(limit), 50))
        raw_results = []
        try:
            raw_results = self.provider.search(keyword, n_hits=limit, lang=config.lang, country=config.country)
        except Exception as exc:
            warnings.append(
                AnalysisWarning(
                    code="PROVIDER_FAILURE",
                    severity="error",
                    message=f"Rank check failed: {exc}",
                    source_id=source.source_id,
                )
            )
            for target_id in target_package_ids:
                context = {**base_context, "target_package_id": target_id}
                reports[target_id] = self._empty_report(context, keyword, target_id, list(warnings))
            return reports

        if not raw_results:
            warnings.append(
                AnalysisWarning(
                    code="NO_SEARCH_RESULTS",
                    severity="warning",
                    message="Public search returned no results for this keyword.",
                    source_id=source.source_id,
                )
            )

        for target_id in target_package_ids:
            entries = [
                KeywordRankEntry(
                    position=index,
                    package_id=str(item.get("package_id", "")),
                    title=str(item.get("title", "")),
                    developer=str(item.get("developer", "")),
                    score=float(item.get("score", 0) or 0),
                    installs=str(item.get("installs", "")),
                    is_target=str(item.get("package_id", "")).lower() == target_id.lower(),
                )
                for index, item in enumerate(raw_results, 1)
            ]
            target_entry = next((entry for entry in entries if entry.is_target), None)

            target_warnings = list(warnings)
            if raw_results and target_entry is None:
                target_warnings.append(
                    AnalysisWarning(
                        code="TARGET_NOT_IN_TOP_RESULTS",
                        severity="info",
                        message=f"Target app was not found in the top {limit} public search results.",
                        source_id=source.source_id,
                    )
                )

            context = {**base_context, "target_package_id": target_id}
            report = KeywordRankReport(
                request_context=context,
                keyword=keyword,
                target_package_id=target_id,
                target_position=target_entry.position if target_entry else None,
                top_results=entries,
                evidence=[
                    SourceEvidence(
                        source_id=source.source_id,
                        display_name=source.display_name,
                        source_type="public_search",
                        scope="keyword_rank_tracking",
                        fetched_at=requested_at,
                        from_cache=False,
                        locale=lang,
                        country=country,
                    )
                ],
                warnings=target_warnings,
                confidence=self._confidence_for(entries, target_entry is not None, target_warnings),
            )

            if save_history:
                (self.history or HistoryStore()).append("keyword_rank", report.to_dict())
                from .local_store import LocalDataStore
                LocalDataStore().append_event("rank_history", report.to_dict())

            reports[target_id] = report

        return reports

    def rank(
        self,
        keyword: str,
        target_package_id: str,
        lang: str = "en",
        country: str = "us",
        limit: int = 20,
        save_history: bool = True,
    ) -> KeywordRankReport:
        target_package_id = target_package_id.strip()
        reports = self.rank_batch(
            keyword=keyword,
            target_package_ids=[target_package_id],
            lang=lang,
            country=country,
            limit=limit,
            save_history=save_history,
        )
        return reports.get(target_package_id) or self._empty_report(
            context={"keyword": keyword, "target_package_id": target_package_id, "lang": lang, "country": country, "limit": limit, "requested_at": "", "sources": []},
            keyword=keyword,
            target_package_id=target_package_id,
            warnings=[]
        )

    @staticmethod
    def _empty_report(context, keyword, target_package_id, warnings) -> KeywordRankReport:
        return KeywordRankReport(
            request_context=context,
            keyword=keyword,
            target_package_id=target_package_id,
            target_position=None,
            warnings=warnings,
            confidence=ConfidenceAssessment(
                label="low",
                score=0,
                rationale="Rank check could not run because required input was missing.",
            ),
        )

    @staticmethod
    def _confidence_for(entries: list[KeywordRankEntry], target_found: bool, warnings: list[AnalysisWarning]) -> ConfidenceAssessment:
        if not entries:
            return ConfidenceAssessment(label="low", score=20, rationale="No public search results were returned.")
        score = 80 if target_found else 65
        if warnings:
            score -= min(len(warnings) * 5, 20)
        label = "high" if score >= 80 else "medium" if score >= 55 else "low"
        rationale = "Public search snapshot captured with source provenance."
        if not target_found:
            rationale = "Target was not found in the checked result window; expand limit or track over time."
        return ConfidenceAssessment(label=label, score=max(score, 0), rationale=rationale)
