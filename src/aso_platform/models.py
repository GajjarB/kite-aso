"""Typed models for the enterprise ASO platform slice."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ComplianceStatus(str, Enum):
    APPROVED = "approved"
    DISABLED = "disabled"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class FetchPolicy:
    rate_limit: str
    cache_ttl_minutes: int
    minimal_collection: str
    fallback_behavior: str


@dataclass(frozen=True)
class SourceDescriptor:
    source_id: str
    display_name: str
    purpose: str
    cost: str
    auth: str
    legal_notes: str
    compliance_status: ComplianceStatus
    enabled: bool
    policy: FetchPolicy


@dataclass(frozen=True)
class SourceEvidence:
    source_id: str
    display_name: str
    source_type: str
    scope: str
    fetched_at: str
    from_cache: bool
    locale: str
    country: str


@dataclass(frozen=True)
class AnalysisScore:
    name: str
    value: int
    scale: str
    formula_version: str
    explanation: str


@dataclass(frozen=True)
class AnalysisWarning:
    code: str
    severity: str
    message: str
    source_id: str


@dataclass(frozen=True)
class ConfidenceAssessment:
    label: str
    score: int
    rationale: str


@dataclass(frozen=True)
class AppDetails:
    package_id: str
    title: str
    summary: str
    description: str
    score: float
    ratings: int
    reviews: int
    installs: str
    min_installs: int
    category: str
    category_id: str
    developer: str
    developer_email: str
    price: float
    free: bool
    content_rating: str
    updated: str
    version: str
    android_version: str
    contains_ads: bool
    released: str
    histogram: dict[str, int]
    fetched_at: str
    from_cache: bool

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AppDetails":
        histogram_raw = raw.get("histogram") or {}
        histogram = {str(k): int(v or 0) for k, v in histogram_raw.items()}
        return cls(
            package_id=str(raw.get("package_id", "")),
            title=str(raw.get("title", "")),
            summary=str(raw.get("summary", "")),
            description=str(raw.get("description", "")),
            score=float(raw.get("score", 0) or 0),
            ratings=int(raw.get("ratings", 0) or 0),
            reviews=int(raw.get("reviews", 0) or 0),
            installs=str(raw.get("installs", "")),
            min_installs=int(raw.get("min_installs", 0) or 0),
            category=str(raw.get("category", "")),
            category_id=str(raw.get("category_id", "")),
            developer=str(raw.get("developer", "")),
            developer_email=str(raw.get("developer_email", "")),
            price=float(raw.get("price", 0) or 0),
            free=bool(raw.get("free", True)),
            content_rating=str(raw.get("content_rating", "")),
            updated=str(raw.get("updated", "")),
            version=str(raw.get("version", "")),
            android_version=str(raw.get("android_version", "")),
            contains_ads=bool(raw.get("contains_ads", False)),
            released=str(raw.get("released", "")),
            histogram=histogram,
            fetched_at=str(raw.get("_fetched_at", raw.get("fetched_at", ""))),
            from_cache=bool(raw.get("_from_cache", raw.get("from_cache", False))),
        )


@dataclass(frozen=True)
class AnalysisReport:
    request_context: dict[str, Any]
    app: AppDetails
    evidence: list[SourceEvidence] = field(default_factory=list)
    scores: list[AnalysisScore] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    warnings: list[AnalysisWarning] = field(default_factory=list)
    confidence: ConfidenceAssessment = field(
        default_factory=lambda: ConfidenceAssessment(
            label="low",
            score=0,
            rationale="No assessment available.",
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_context": self.request_context,
            "app": asdict(self.app),
            "evidence": [asdict(item) for item in self.evidence],
            "scores": [asdict(item) for item in self.scores],
            "insights": list(self.insights),
            "warnings": [asdict(item) for item in self.warnings],
            "confidence": asdict(self.confidence),
        }


@dataclass(frozen=True)
class KeywordRankEntry:
    position: int
    package_id: str
    title: str
    developer: str
    score: float
    installs: str
    is_target: bool


@dataclass(frozen=True)
class KeywordRankReport:
    request_context: dict[str, Any]
    keyword: str
    target_package_id: str
    target_position: int | None
    top_results: list[KeywordRankEntry] = field(default_factory=list)
    evidence: list[SourceEvidence] = field(default_factory=list)
    warnings: list[AnalysisWarning] = field(default_factory=list)
    confidence: ConfidenceAssessment = field(
        default_factory=lambda: ConfidenceAssessment(
            label="low",
            score=0,
            rationale="No assessment available.",
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_context": self.request_context,
            "keyword": self.keyword,
            "target_package_id": self.target_package_id,
            "target_position": self.target_position,
            "top_results": [asdict(item) for item in self.top_results],
            "evidence": [asdict(item) for item in self.evidence],
            "warnings": [asdict(item) for item in self.warnings],
            "confidence": asdict(self.confidence),
        }


@dataclass(frozen=True)
class KeywordDiscoveryReport:
    request_context: dict[str, Any]
    input_review: dict[str, Any]
    category: dict[str, Any]
    seed_sources: dict[str, str]
    keywords: list[dict[str, Any]]
    evidence: list[SourceEvidence] = field(default_factory=list)
    warnings: list[AnalysisWarning] = field(default_factory=list)
    confidence: ConfidenceAssessment = field(
        default_factory=lambda: ConfidenceAssessment(
            label="medium",
            score=60,
            rationale="Local deterministic keyword discovery without live demand data.",
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_context": self.request_context,
            "input_review": dict(self.input_review),
            "category": dict(self.category),
            "seed_sources": dict(self.seed_sources),
            "keywords": [dict(item) for item in self.keywords],
            "evidence": [asdict(item) for item in self.evidence],
            "warnings": [asdict(item) for item in self.warnings],
            "confidence": asdict(self.confidence),
        }


@dataclass(frozen=True)
class WorkspaceConfig:
    workspace_id: str
    name: str
    target_package_id: str
    category: str
    seed_text: str
    lang: str
    country: str
    competitors: list[str] = field(default_factory=list)
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "WorkspaceConfig":
        return cls(
            workspace_id=str(raw.get("workspace_id", "")),
            name=str(raw.get("name", "")),
            target_package_id=str(raw.get("target_package_id", "")),
            category=str(raw.get("category", "")),
            seed_text=str(raw.get("seed_text", "")),
            lang=str(raw.get("lang", "en") or "en"),
            country=str(raw.get("country", "us") or "us"),
            competitors=[str(item) for item in raw.get("competitors", []) if str(item).strip()],
            notes=str(raw.get("notes", "")),
            created_at=str(raw.get("created_at", "")),
            updated_at=str(raw.get("updated_at", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkspaceBaselineReport:
    workspace: WorkspaceConfig
    generated_at: str
    app_report: dict[str, Any]
    keyword_report: dict[str, Any]
    rank_checks: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace.to_dict(),
            "generated_at": self.generated_at,
            "app_report": dict(self.app_report),
            "keyword_report": dict(self.keyword_report),
            "rank_checks": [dict(item) for item in self.rank_checks],
            "warnings": [dict(item) for item in self.warnings],
            "summary": dict(self.summary),
        }
