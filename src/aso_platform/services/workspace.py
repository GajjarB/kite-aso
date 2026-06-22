"""Workspace service for repeatable ASO product flows."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..models import WorkspaceBaselineReport, WorkspaceConfig
from .local_store import LocalDataStore
from .app_inspector import AppInspectionService
from .keyword_discovery import KeywordDiscoveryService
from .keyword_rank import KeywordRankService, RankConfig

DEFAULT_WORKSPACE_DIR = Path(__file__).resolve().parents[3] / "data" / "workspaces"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "workspace"


class WorkspaceService:
    """Persist workspace config and run a baseline product workflow."""

    def __init__(
        self,
        workspace_dir: Path | None = None,
        app_service: AppInspectionService | None = None,
        keyword_service: KeywordDiscoveryService | None = None,
        rank_service: KeywordRankService | None = None,
    ):
        self.workspace_dir = workspace_dir or DEFAULT_WORKSPACE_DIR
        self.app_service = app_service or AppInspectionService()
        self.keyword_service = keyword_service or KeywordDiscoveryService()
        self.rank_service = rank_service or KeywordRankService()
        self.store = LocalDataStore()

    def create(
        self,
        name: str,
        target_package_id: str,
        *,
        category: str = "",
        seed_text: str = "",
        lang: str = "en",
        country: str = "us",
        competitors: list[str] | None = None,
        notes: str = "",
        overwrite: bool = False,
    ) -> WorkspaceConfig:
        name = name.strip()
        target_package_id = target_package_id.strip()
        if not name:
            raise ValueError("Workspace name is required.")
        if not target_package_id:
            raise ValueError("Target package id is required.")

        now = datetime.now(UTC).isoformat()
        workspace_id = _slugify(name)
        path = self._path_for(workspace_id)
        if path.exists() and not overwrite:
            raise FileExistsError(f"Workspace '{workspace_id}' already exists.")

        config = WorkspaceConfig(
            workspace_id=workspace_id,
            name=name,
            target_package_id=target_package_id,
            category=category.strip(),
            seed_text=seed_text.strip(),
            lang=(lang or "en").strip().lower(),
            country=(country or "us").strip().lower(),
            competitors=[item.strip() for item in (competitors or []) if item.strip()],
            notes=notes.strip(),
            created_at=now,
            updated_at=now,
        )
        self._write(config)
        return config

    def get(self, workspace_ref: str) -> WorkspaceConfig:
        workspace_ref = workspace_ref.strip()
        if not workspace_ref:
            raise ValueError("Workspace id or name is required.")

        candidates = [
            self._path_for(workspace_ref),
            self._path_for(_slugify(workspace_ref)),
        ]
        for path in candidates:
            if path.exists():
                return WorkspaceConfig.from_mapping(json.loads(path.read_text(encoding="utf-8")))

        for path in sorted(self.workspace_dir.glob("*.json")):
            config = WorkspaceConfig.from_mapping(json.loads(path.read_text(encoding="utf-8")))
            if config.name.lower() == workspace_ref.lower():
                return config
        raise FileNotFoundError(f"Workspace '{workspace_ref}' was not found.")

    def list(self) -> list[WorkspaceConfig]:
        if not self.workspace_dir.exists():
            return []
        rows = [
            WorkspaceConfig.from_mapping(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self.workspace_dir.glob("*.json"))
        ]
        return sorted(rows, key=lambda item: (item.name.lower(), item.workspace_id))

    def update_competitors(self, workspace_ref: str, package_ids: list[str], mode: str = "add") -> WorkspaceConfig:
        config = self.get(workspace_ref)
        current = list(config.competitors)
        normalized = [item.strip() for item in package_ids if item.strip()]
        if mode == "remove":
            next_competitors = [item for item in current if item not in normalized]
        else:
            next_competitors = current[:]
            for item in normalized:
                if item not in next_competitors:
                    next_competitors.append(item)
        updated = replace(config, competitors=next_competitors, updated_at=datetime.now(UTC).isoformat())
        self._write(updated)
        return updated

    def baseline(
        self,
        workspace_ref: str,
        *,
        keyword_limit: int = 20,
        top_keywords: int = 5,
        rank_limit: int = 10,
        save_history: bool = False,
    ) -> WorkspaceBaselineReport:
        workspace = self.get(workspace_ref)
        generated_at = datetime.now(UTC).isoformat()

        app_report = self.app_service.inspect(
            workspace.target_package_id,
            lang=workspace.lang,
            country=workspace.country,
        ).to_dict()
        keyword_report = self.keyword_service.discover(
            seed_text=workspace.seed_text,
            category=workspace.category,
            lang=workspace.lang,
            country=workspace.country,
            limit=max(1, keyword_limit),
        ).to_dict()

        rank_checks: list[dict[str, Any]] = []
        for item in keyword_report.get("keywords", [])[: max(1, top_keywords)]:
            keyword = str(item.get("keyword", "")).strip()
            if not keyword:
                continue
            rank_checks.append(
                self.rank_service.rank(
                    RankConfig(
                        keyword=keyword,
                        target_package_id=workspace.target_package_id,
                        lang=workspace.lang,
                        country=workspace.country,
                        limit=rank_limit,
                        save_history=save_history,
                    )
                ).to_dict()
            )

        warnings = [
            *keyword_report.get("warnings", []),
            *app_report.get("warnings", []),
        ]
        warnings.extend(
            warning
            for report in rank_checks
            for warning in report.get("warnings", [])
        )

        found_ranks = [report["target_position"] for report in rank_checks if report.get("target_position")]
        summary = {
            "target_package_id": workspace.target_package_id,
            "country": workspace.country,
            "lang": workspace.lang,
            "keyword_count": len(keyword_report.get("keywords", [])),
            "rank_checks_run": len(rank_checks),
            "rank_hits": len(found_ranks),
            "best_rank": min(found_ranks) if found_ranks else None,
            "app_confidence": app_report.get("confidence", {}).get("label"),
            "keyword_confidence": keyword_report.get("confidence", {}).get("label"),
        }

        return WorkspaceBaselineReport(
            workspace=replace(workspace, updated_at=generated_at),
            generated_at=generated_at,
            app_report=app_report,
            keyword_report=keyword_report,
            rank_checks=rank_checks,
            warnings=warnings,
            summary=summary,
        )

    def _path_for(self, workspace_id: str) -> Path:
        return self.workspace_dir / f"{_slugify(workspace_id)}.json"

    def _write(self, config: WorkspaceConfig) -> Path:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(config.workspace_id)
        path.write_text(json.dumps(config.to_dict(), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        return path
