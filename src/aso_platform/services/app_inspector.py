"""Evidence-backed single-app inspection service."""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import (
    AnalysisReport,
    AnalysisScore,
    AnalysisWarning,
    ConfidenceAssessment,
    SourceEvidence,
)
from ..providers import PlayStorePublicProvider
from ..registry import RegistryError, ensure_source_approved, get_source, load_source_registry


class AppInspectionService:
    """Orchestrates policy checks, provider calls, and normalized output."""

    def __init__(self, provider: PlayStorePublicProvider | None = None, registry=None):
        self.provider = provider or PlayStorePublicProvider()
        self.registry = registry or load_source_registry()

    def inspect(self, package_id: str, lang: str = "en", country: str = "us") -> AnalysisReport:
        requested_at = datetime.now(timezone.utc).isoformat()
        source = get_source(self.provider.source_id, self.registry)
        context = {
            "package_id": package_id,
            "lang": lang,
            "country": country,
            "requested_at": requested_at,
            "sources": [source.source_id],
        }

        try:
            ensure_source_approved(source)
        except RegistryError as exc:
            return self._build_blocked_report(context, package_id, source, exc)

        try:
            app = self.provider.fetch_app(package_id, lang=lang, country=country)
        except Exception as exc:
            return self._build_failure_report(context, package_id, source, exc)

        return self._build_success_report(context, app, source, requested_at, lang, country)

    def _build_blocked_report(self, context, package_id, source, exc):
        empty_app = self.provider.fetch_app(package_id, lang=context["lang"], country=context["country"]) if False else None
        # The service returns a safe empty payload rather than attempting a blocked fetch.
        return AnalysisReport(
            request_context=context,
            app=empty_app or self._empty_app(package_id),
            evidence=[],
            scores=[],
            insights=[],
            warnings=[
                AnalysisWarning(
                    code="SOURCE_DISABLED",
                    severity="error",
                    message=str(exc),
                    source_id=source.source_id,
                )
            ],
            confidence=ConfidenceAssessment(
                label="blocked",
                score=0,
                rationale="Inspection was blocked by source compliance policy.",
            ),
        )

    def _build_failure_report(self, context, package_id, source, exc):
        return AnalysisReport(
            request_context=context,
            app=self._empty_app(package_id),
            evidence=[],
            scores=[],
            insights=[],
            warnings=[
                AnalysisWarning(
                    code="PROVIDER_FAILURE",
                    severity="error",
                    message=f"App inspection failed: {exc}",
                    source_id=source.source_id,
                )
            ],
            confidence=ConfidenceAssessment(
                label="low",
                score=10,
                rationale="Public source request failed before a normalized app record could be built.",
            ),
        )

    @staticmethod
    def _collect_warnings(app, source) -> list[AnalysisWarning]:
        warnings: list[AnalysisWarning] = []
        if app.from_cache:
            warnings.append(
                AnalysisWarning(
                    code="CACHE_HIT",
                    severity="info",
                    message="Result was served from cache; confirm freshness for time-sensitive decisions.",
                    source_id=source.source_id,
                )
            )
        if not app.histogram:
            warnings.append(
                AnalysisWarning(
                    code="PARTIAL_DATA",
                    severity="warning",
                    message="Ratings histogram was unavailable from the source payload.",
                    source_id=source.source_id,
                )
            )
        return warnings

    def _build_success_report(self, context, app, source, requested_at, lang, country):
        warnings = self._collect_warnings(app, source)
        return AnalysisReport(
            request_context=context,
            app=app,
            evidence=[
                SourceEvidence(
                    source_id=source.source_id,
                    display_name=source.display_name,
                    source_type="public_store",
                    scope="single_app_inspection",
                    fetched_at=app.fetched_at or requested_at,
                    from_cache=app.from_cache,
                    locale=lang,
                    country=country,
                )
            ],
            scores=[
                AnalysisScore(
                    name="store_quality_score",
                    value=self._store_quality_score(app),
                    scale="0-100",
                    formula_version="1.0.0",
                    explanation="Combines public store rating and rating-volume signals for a quick inspection score.",
                )
            ],
            insights=self._build_insights(app),
            warnings=warnings,
            confidence=self._confidence_for(app, warnings),
        )

    @staticmethod
    def _empty_app(package_id: str):
        from ..models import AppDetails

        return AppDetails.from_mapping(
            {
                "package_id": package_id,
                "title": "",
                "summary": "",
                "description": "",
                "score": 0,
                "ratings": 0,
                "reviews": 0,
                "installs": "",
                "min_installs": 0,
                "category": "",
                "category_id": "",
                "developer": "",
                "developer_email": "",
                "price": 0,
                "free": True,
                "content_rating": "",
                "updated": "",
                "version": "",
                "android_version": "",
                "contains_ads": False,
                "released": "",
                "histogram": {},
                "_fetched_at": "",
                "_from_cache": False,
            }
        )

    @staticmethod
    def _store_quality_score(app) -> int:
        rating_component = max(0.0, min(app.score, 5.0)) / 5.0 * 70
        volume_component = min(app.ratings, 100000) / 100000 * 30
        return round(rating_component + volume_component)

    @staticmethod
    def _build_insights(app) -> list[str]:
        insights = [
            f"Title captured from public store listing: {app.title or 'unknown title'}."
        ]
        if app.score >= 4.5:
            insights.append("Public store rating is strong and supports credibility in acquisition funnels.")
        elif app.score <= 3.5:
            insights.append("Public store rating is weak enough to reduce conversion and should be investigated.")
        if app.from_cache:
            insights.append("Cached data was used; refresh before making time-sensitive publishing decisions.")
        return insights

    @staticmethod
    def _confidence_for(app, warnings: list[AnalysisWarning]) -> ConfidenceAssessment:
        score = 85
        rationale = "Single-source public metadata is available with clear provenance."
        if warnings:
            score -= min(len(warnings) * 10, 30)
            rationale = "Confidence reduced because warnings were emitted during inspection."
        if app.from_cache:
            score -= 5
        if app.reviews == 0 and app.ratings == 0:
            score -= 20
        label = "high" if score >= 80 else "medium" if score >= 60 else "low"
        return ConfidenceAssessment(label=label, score=max(score, 0), rationale=rationale)


def inspect_app(package_id: str, lang: str = "en", country: str = "us") -> dict:
    """Convenience API for external callers."""

    return AppInspectionService().inspect(package_id, lang=lang, country=country).to_dict()
