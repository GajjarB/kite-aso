"""Keyword discovery service for category and free-form ASO research."""

from __future__ import annotations

from datetime import UTC, datetime

from core.keywords import (
    build_keyword_candidates,
    build_public_search_enrichment,
    get_category_seed_keywords,
    normalize_keyword_seed_input,
    score_keywords,
)

from ..models import AnalysisWarning, ConfidenceAssessment, KeywordDiscoveryReport, SourceEvidence
from ..registry import ensure_source_approved, get_source
from ..providers import PlayStoreSearchProvider


class KeywordDiscoveryService:
    """Generate keyword opportunities using only approved free/legal inputs."""

    def __init__(self, search_provider: PlayStoreSearchProvider | None = None, registry=None):
        self.search_provider = search_provider or PlayStoreSearchProvider()
        self.registry = registry

    def discover(
        self,
        seed_text: str = "",
        category: str = "",
        *,
        lang: str = "en",
        country: str = "us",
        limit: int = 40,
    ) -> KeywordDiscoveryReport:
        requested_at = datetime.now(UTC).isoformat()
        warnings: list[AnalysisWarning] = []
        evidence: list[SourceEvidence] = []
        public_search_used = False

        input_review = normalize_keyword_seed_input(seed_text) if seed_text else {
            "raw_input": "",
            "seeds": [],
            "corrections": [],
            "ignored_terms": [],
            "warnings": [],
            "quality_label": "not_used",
            "quality_score": 0,
        }
        category_review = get_category_seed_keywords(category) if category else {
            "raw_category": "",
            "category": "",
            "matched": False,
            "warnings": [],
            "seeds": [],
            "source": "none",
            "legal_notes": "",
        }

        combined_seeds, seed_sources, new_evidence, new_warnings = self._build_seeds_and_sources(
            category_review, input_review, requested_at, lang, country, category
        )
        evidence.extend(new_evidence)
        warnings.extend(new_warnings)

        public_search_enrichment, public_search_used, p_evidence, p_warnings = self._fetch_public_search_enrichment(
            combined_seeds, input_review, category_review, requested_at, lang, country
        )
        evidence.extend(p_evidence)
        warnings.extend(p_warnings)

        candidates = build_keyword_candidates(
            combined_seeds,
            suggestions=public_search_enrichment["suggestions"],
            max_keywords=max(24, limit * 3),
            seed_sources=seed_sources,
            live_support_map=public_search_enrichment["live_support_map"],
        )
        scored = score_keywords(candidates, {"data": {}})
        confidence = self._confidence(scored, category_review, input_review, public_search_used)

        return KeywordDiscoveryReport(
            request_context={
                "category": category,
                "seed_text": seed_text,
                "lang": lang,
                "country": country,
                "limit": limit,
                "requested_at": requested_at,
                "sources": sorted({"local_category_taxonomy", *seed_sources.values(), "local_variant", *({"google_play_public_search"} if public_search_used else set())}),
                "live_search_queries": public_search_enrichment["queries_used"],
                "live_suggestions": len(public_search_enrichment["suggestions"]),
            },
            input_review=input_review,
            category=category_review,
            seed_sources=seed_sources,
            keywords=scored[:limit],
            evidence=evidence,
            warnings=warnings,
            confidence=confidence,
        )

    def _build_seeds_and_sources(
        self,
        category_review: dict,
        input_review: dict,
        requested_at: str,
        lang: str,
        country: str,
        category: str,
    ) -> tuple[list[str], dict[str, str], list[SourceEvidence], list[AnalysisWarning]]:
        evidence: list[SourceEvidence] = []
        warnings: list[AnalysisWarning] = []
        seed_sources: dict[str, str] = {}
        combined_seeds: list[str] = []

        if category_review["seeds"]:
            source = get_source("local_category_taxonomy")
            ensure_source_approved(source)
            evidence.append(
                SourceEvidence(
                    source_id=source.source_id,
                    display_name=source.display_name,
                    source_type="local_taxonomy",
                    scope="keyword_category_discovery",
                    fetched_at=requested_at,
                    from_cache=False,
                    locale=lang,
                    country=country,
                )
            )
            for seed in category_review["seeds"]:
                if seed not in combined_seeds:
                    combined_seeds.append(seed)
                    seed_sources[seed] = "category_seed"

        for seed in input_review["seeds"]:
            if seed not in combined_seeds:
                combined_seeds.append(seed)
            seed_sources[seed] = "normalized_input"

        for message in category_review["warnings"] + input_review["warnings"]:
            warnings.append(
                AnalysisWarning(
                    code="keyword_input_notice",
                    severity="info",
                    message=message,
                    source_id="local_category_taxonomy" if category else "normalized_input",
                )
            )

        if not combined_seeds:
            warnings.append(
                AnalysisWarning(
                    code="no_keyword_seeds",
                    severity="warning",
                    message="No category or seed keywords could be used for discovery.",
                    source_id="local_category_taxonomy",
                )
            )

        return combined_seeds, seed_sources, evidence, warnings

    def _fetch_public_search_enrichment(
        self,
        combined_seeds: list[str],
        input_review: dict,
        category_review: dict,
        requested_at: str,
        lang: str,
        country: str,
    ) -> tuple[dict, bool, list[SourceEvidence], list[AnalysisWarning]]:
        evidence: list[SourceEvidence] = []
        warnings: list[AnalysisWarning] = []
        public_search_used = False
        public_search_enrichment = {
            "live_support_map": {},
            "suggestions": [],
            "warnings": [],
            "queries_used": [],
        }

        if combined_seeds:
            try:
                source = get_source("google_play_public_search", self.registry)
                ensure_source_approved(source)
                enrichment_queries = self._enrichment_queries(input_review["seeds"], category_review["seeds"])
                public_search_enrichment = build_public_search_enrichment(
                    enrichment_queries,
                    self.search_provider.search,
                    lang=lang,
                    country=country,
                )
                if public_search_enrichment["queries_used"]:
                    public_search_used = True
                    evidence.append(
                        SourceEvidence(
                            source_id=source.source_id,
                            display_name=source.display_name,
                            source_type="public_search",
                            scope="keyword_discovery_enrichment",
                            fetched_at=requested_at,
                            from_cache=False,
                            locale=lang,
                            country=country,
                        )
                    )
            except Exception as exc:
                warnings.append(
                    AnalysisWarning(
                        code="keyword_search_enrichment_unavailable",
                        severity="info",
                        message=f"Public search enrichment was unavailable: {exc}",
                        source_id="google_play_public_search",
                    )
                )

        for message in public_search_enrichment["warnings"]:
            warnings.append(
                AnalysisWarning(
                    code="keyword_search_enrichment_notice",
                    severity="info",
                    message=message,
                    source_id="google_play_public_search",
                )
            )

        return public_search_enrichment, public_search_used, evidence, warnings

    @staticmethod
    def _enrichment_queries(input_seeds: list[str], category_seeds: list[str], limit: int = 5) -> list[str]:
        queries: list[str] = []
        for seed in input_seeds + category_seeds:
            if seed and seed not in queries:
                queries.append(seed)
            if len(queries) >= limit:
                break
        return queries

    def _confidence(self, scored: list[dict], category_review: dict, input_review: dict, public_search_used: bool) -> ConfidenceAssessment:
        if not scored:
            return ConfidenceAssessment(
                label="low",
                score=0,
                rationale="No usable category or seed input was provided.",
            )
        if public_search_used and input_review.get("seeds"):
            return ConfidenceAssessment(
                label="high",
                score=82,
                rationale="User-provided seeds were expanded and cross-checked against approved public search results.",
            )
        if public_search_used and category_review.get("matched"):
            return ConfidenceAssessment(
                label="medium",
                score=74,
                rationale="Category taxonomy was enriched with approved public search evidence.",
            )
        if category_review.get("matched") and input_review.get("seeds"):
            return ConfidenceAssessment(
                label="medium",
                score=70,
                rationale="Category taxonomy and user-provided seeds agree on the discovery scope.",
            )
        if category_review.get("matched"):
            return ConfidenceAssessment(
                label="medium",
                score=62,
                rationale="Local category taxonomy produced deterministic keyword opportunities.",
            )
        return ConfidenceAssessment(
            label="medium",
            score=max(45, int(input_review.get("quality_score", 50))),
            rationale="User-provided seed input was normalized and expanded locally.",
        )
