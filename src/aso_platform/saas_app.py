"""FastAPI web app for the ASO PRO SaaS MVP."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import threading
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import APIRouter, Cookie, Depends, FastAPI, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .services.intelligence import KeywordIntelligenceService, MetadataAuditService, SourceHealthService
from .services.saas_store import DEFAULT_DB_PATH, JobError, SaasStore
from .services.workspace import WorkspaceService

WEB_ROOT = Path(__file__).resolve().parent / "web"
SESSION_COOKIE = "aso_session"


class AsoApiError(RuntimeError):
    def __init__(self, code: str, message: str, fix: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.fix = fix
        self.status_code = status_code


class AppConfig:
    def __init__(self):
        self.env = os.getenv("ASO_ENV", "development")
        secret_key = os.getenv("ASO_SECRET_KEY")
        if not secret_key:
            # Auto-generate a stable local key for development / single-user use.
            # Set ASO_SECRET_KEY in your environment for production deployments.
            import hashlib
            import platform
            seed = f"kite-aso-local-{platform.node()}"
            secret_key = hashlib.sha256(seed.encode()).hexdigest()
        self.secret_key = secret_key
        self.public_base_url = os.getenv("ASO_PUBLIC_BASE_URL", "http://127.0.0.1:8787")
        self.database_url = os.getenv("ASO_DATABASE_URL", str(DEFAULT_DB_PATH))
        self.project_limit = int(os.getenv("ASO_PROJECT_LIMIT", "3"))
        self.daily_analysis_limit = int(os.getenv("ASO_DAILY_ANALYSIS_LIMIT", "20"))
        self.rank_checks_per_analysis = int(os.getenv("ASO_RANK_CHECKS_PER_ANALYSIS", "3"))



class AuthStartRequest(BaseModel):
    email: str
    workspace_name: str = ""


class AuthVerifyRequest(BaseModel):
    token: str


class ProjectRequest(BaseModel):
    name: str
    package_id: str
    category: str = ""
    seed_text: str = ""
    lang: str = "en"
    country: str = "us"
    competitors: str | list[str] = ""
    auto_analyze: bool = True


class KeywordScoreRequest(BaseModel):
    keywords: str
    app_text: str = ""


class JobRunner:
    def __init__(self, store: SaasStore, config: AppConfig):
        self.store = store
        self.config = config

    def enqueue(self, organization_id: int, project_id: int, job_type: str = "baseline") -> dict[str, Any]:
        if self.store.count_analyses_today(organization_id) >= self.config.daily_analysis_limit:
            raise AsoApiError("quota_exceeded", "Daily analysis limit reached.", "Wait until tomorrow or raise ASO_DAILY_ANALYSIS_LIMIT.", 429)
        job = self.store.create_job(organization_id, project_id, job_type)
        thread = threading.Thread(target=self._run_job, args=(organization_id, project_id, job["id"], job_type), daemon=True)
        thread.start()
        return job

    def _run_job(self, organization_id: int, project_id: int, job_id: int, job_type: str) -> None:
        try:
            self.store.start_job(organization_id, job_id)
            project = self.store.get_project(organization_id, project_id)
            if job_type == "metadata":
                payload = self._metadata(project)
                analysis_type = "metadata"
            else:
                payload = self._baseline(project)
                analysis_type = "baseline"
            analysis = self.store.record_analysis(organization_id, project_id, analysis_type, payload)
            self.store.record_usage(organization_id, "analysis_run")
            self.store.complete_job(organization_id, job_id, analysis["id"])
        except Exception as exc:
            self.store.fail_job(
                organization_id,
                job_id,
                JobError(
                    code="analysis_failed",
                    message=str(exc),
                    fix="Check app package id, source health, and network access, then rerun analysis.",
                ),
            )

    def _baseline(self, project: dict[str, Any]) -> dict[str, Any]:
        workspace_service = WorkspaceService()
        temp_name = f"saas-{project['id']}"
        workspace_service.create(
            temp_name,
            project["package_id"],
            category=project["category"],
            seed_text=project["seed_text"],
            lang=project["lang"],
            country=project["country"],
            competitors=project["competitors"],
            overwrite=True,
        )
        payload = workspace_service.baseline(
            temp_name,
            keyword_limit=12,
            top_keywords=self.config.rank_checks_per_analysis,
            rank_limit=10,
            save_history=True,
        ).to_dict()
        payload["action_plan"] = self.store.action_plan_for(payload)
        return payload

    def _metadata(self, project: dict[str, Any]) -> dict[str, Any]:
        keywords = _csv(project.get("seed_text", ""))
        payload = MetadataAuditService().audit(project["package_id"], keywords, lang=project["lang"], country=project["country"])
        payload["action_plan"] = self.store.action_plan_for(payload)
        return payload



router = APIRouter()

def get_store(request: Request) -> SaasStore:
    return request.app.state.store

def get_config(request: Request) -> AppConfig:
    return request.app.state.config

def get_runner(request: Request) -> JobRunner:
    return request.app.state.runner

def current_account(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    store: SaasStore = Depends(get_store)
) -> dict[str, Any]:
    account = store.account_for_session(session or "")
    if not account:
        raise AsoApiError("auth_required", "Sign in required.", "Start with POST /api/auth/start, then verify the magic link.", 401)
    return account

@router.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(WEB_ROOT / "index.html")

@router.get("/health")
def health(config: AppConfig = Depends(get_config)):
    return {"status": "ok", "env": config.env, "database": "configured"}

@router.post("/api/auth/start")
def auth_start(payload: AuthStartRequest, store: SaasStore = Depends(get_store), config: AppConfig = Depends(get_config)):
    token = store.create_auth_token(payload.email, payload.workspace_name)
    return {
        "status": "magic_link_created",
        "email": token["email"],
        "expires_at": token["expires_at"],
        "dev_magic_link": token["magic_link"] if config.env != "production" else "",
        "dev_token": token["token"] if config.env != "production" else "",
    }

@router.post("/api/auth/verify")
def auth_verify(payload: AuthVerifyRequest, response: Response, store: SaasStore = Depends(get_store), config: AppConfig = Depends(get_config)):
    account = store.verify_auth_token(payload.token)
    response.set_cookie(
        SESSION_COOKIE,
        account["session"]["token"],
        httponly=True,
        samesite="lax",
        secure=config.env == "production",
        max_age=60 * 60 * 24 * 30,
    )
    return {"authenticated": True, "user": account["user"], "organization": account["organization"]}

@router.get("/api/auth/verify")
def auth_verify_get(token: str, response: Response, store: SaasStore = Depends(get_store), config: AppConfig = Depends(get_config)):
    return auth_verify(AuthVerifyRequest(token=token), response, store, config)

@router.post("/api/logout")
def logout(response: Response, session: str | None = Cookie(default=None, alias=SESSION_COOKIE), store: SaasStore = Depends(get_store)):
    store.delete_session(session or "")
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}

@router.get("/api/me")
def me(account: dict = Depends(current_account)):
    return account

@router.get("/api/bootstrap")
def bootstrap(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    store: SaasStore = Depends(get_store),
    config: AppConfig = Depends(get_config)
):
    account = store.account_for_session(session or "")
    source_health = SourceHealthService().health()
    if not account:
        return {"authenticated": False, "source_health": source_health, "projects": [], "analyses": [], "limits": limits_payload(config)}
    org_id = account["organization"]["id"]
    return {
        "authenticated": True,
        **account,
        "source_health": source_health,
        "projects": store.list_projects(org_id),
        "analyses": store.list_analyses(org_id),
        "limits": limits_payload(config, store, org_id),
    }

@router.get("/api/projects")
def list_projects(account: dict = Depends(current_account), store: SaasStore = Depends(get_store)):
    return {"projects": store.list_projects(account["organization"]["id"])}

@router.post("/api/projects", status_code=201)
def create_project(
    payload: ProjectRequest,
    account: dict = Depends(current_account),
    store: SaasStore = Depends(get_store),
    config: AppConfig = Depends(get_config),
    runner: JobRunner = Depends(get_runner)
):
    org_id = account["organization"]["id"]
    if store.count_projects(org_id) >= config.project_limit:
        raise AsoApiError("quota_exceeded", "Project limit reached.", "Delete a project later or increase ASO_PROJECT_LIMIT.", 429)
    project = store.create_project(org_id, payload.model_dump())
    job = runner.enqueue(org_id, project["id"], "baseline") if payload.auto_analyze else None
    return {"project": project, "job": job}

@router.get("/api/projects/{project_id}")
def get_project(project_id: int, account: dict = Depends(current_account), store: SaasStore = Depends(get_store)):
    return {"project": require_project(store, account["organization"]["id"], project_id)}

@router.post("/api/projects/{project_id}/analyses")
def run_analysis(
    project_id: int,
    analysis_type: str = "baseline",
    account: dict = Depends(current_account),
    store: SaasStore = Depends(get_store),
    runner: JobRunner = Depends(get_runner)
):
    org_id = account["organization"]["id"]
    require_project(store, org_id, project_id)
    job_type = "metadata" if analysis_type == "metadata" else "baseline"
    return {"job": runner.enqueue(org_id, project_id, job_type)}

@router.get("/api/analysis-jobs/{job_id}")
def get_job(job_id: int, account: dict = Depends(current_account), store: SaasStore = Depends(get_store)):
    return {"job": store.get_job(account["organization"]["id"], job_id)}

@router.get("/api/analyses")
def list_analyses(account: dict = Depends(current_account), store: SaasStore = Depends(get_store)):
    return {"analyses": store.list_analyses(account["organization"]["id"])}

@router.get("/api/analyses/{analysis_id}")
def get_analysis(analysis_id: int, account: dict = Depends(current_account), store: SaasStore = Depends(get_store)):
    return {"analysis": require_analysis(store, account["organization"]["id"], analysis_id)}

@router.post("/api/keywords/score")
def score_keywords(
    payload: KeywordScoreRequest,
    account: dict = Depends(current_account),
    store: SaasStore = Depends(get_store),
    config: AppConfig = Depends(get_config)
):
    org_id = account["organization"]["id"]
    if store.count_analyses_today(org_id) >= config.daily_analysis_limit:
        raise AsoApiError("quota_exceeded", "Daily analysis limit reached.", "Wait until tomorrow or raise ASO_DAILY_ANALYSIS_LIMIT.", 429)
    report = KeywordIntelligenceService().score(_csv(payload.keywords), app_text=payload.app_text)
    report["action_plan"] = store.action_plan_for(report)
    analysis = store.record_analysis(org_id, None, "keyword_score", report)
    store.record_usage(org_id, "keyword_score")
    return {"analysis": analysis}

@router.get("/api/source-health")
def source_health():
    return SourceHealthService().health()

@router.get("/api/reports/{analysis_id}.{fmt}")
def report_export(analysis_id: int, fmt: str, account: dict = Depends(current_account), store: SaasStore = Depends(get_store)):
    analysis = require_analysis(store, account["organization"]["id"], analysis_id)
    payload = analysis.get("payload", {})
    if fmt == "json":
        return JSONResponse(payload)
    if fmt == "md":
        return PlainTextResponse(markdown_report(analysis), media_type="text/markdown")
    if fmt == "csv":
        return PlainTextResponse(csv_report(payload), media_type="text/csv")
    raise AsoApiError("unsupported_report_format", "Unsupported report format.", "Use json, md, or csv.", 404)


def create_app(store: SaasStore | None = None, config: AppConfig | None = None) -> FastAPI:
    config = config or AppConfig()
    store = store or SaasStore(Path(config.database_url))
    runner = JobRunner(store, config)
    app = FastAPI(title="ASO PRO SaaS MVP", version="0.3.0")
    app.state.store = store
    app.state.config = config
    app.state.runner = runner
    app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")

    @app.exception_handler(AsoApiError)
    async def aso_error_handler(_: Request, exc: AsoApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "fix": exc.fix}},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(_: Request, exc: Exception):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "request_failed", "message": str(exc), "fix": "Review the request fields and try again."}},
        )

    app.include_router(router)
    return app


def limits_payload(config: AppConfig, store: SaasStore | None = None, organization_id: int | None = None) -> dict[str, Any]:
    used_projects = store.count_projects(organization_id) if store and organization_id else 0
    used_analyses = store.count_analyses_today(organization_id) if store and organization_id else 0
    return {
        "projects": {"used": used_projects, "limit": config.project_limit},
        "daily_analyses": {"used": used_analyses, "limit": config.daily_analysis_limit},
        "rank_checks_per_analysis": config.rank_checks_per_analysis,
    }


def require_project(store: SaasStore, organization_id: int, project_id: int) -> dict[str, Any]:
    try:
        return store.get_project(organization_id, project_id)
    except KeyError as exc:
        raise AsoApiError("not_found", "Project not found.", "Check the project id and signed-in organization.", 404) from exc


def require_analysis(store: SaasStore, organization_id: int, analysis_id: int) -> dict[str, Any]:
    try:
        return store.get_analysis(organization_id, analysis_id)
    except KeyError as exc:
        raise AsoApiError("not_found", "Analysis not found.", "Check the analysis id and signed-in organization.", 404) from exc


def markdown_report(analysis: dict[str, Any]) -> str:
    payload = analysis.get("payload", {})
    lines = [
        "# ASO PRO Report",
        "",
        f"Type: {analysis.get('analysis_type')}",
        f"Summary: {analysis.get('summary')}",
        f"Generated: {analysis.get('completed_at') or analysis.get('created_at')}",
        "",
        "## Action Plan",
    ]
    for item in analysis.get("action_plan", []):
        lines.append(f"- **{item.get('priority', 'medium').upper()}** {item.get('title')} - {item.get('why')}")
    lines.extend(["", "## Evidence", "```json", json.dumps(payload.get("evidence", []), indent=2), "```", "", "## Warnings"])
    for warning in analysis.get("warnings", []):
        lines.append(f"- {warning.get('code', 'warning')}: {warning.get('message')}")
    return "\n".join(lines) + "\n"


def csv_report(payload: dict[str, Any]) -> str:
    output = io.StringIO()
    rows = []
    rows.extend(payload.get("keyword_report", {}).get("keywords", []))
    rows.extend(payload.get("keywords", []))
    rows.extend(payload.get("scores", []))
    if not rows:
        rows = [{"summary": payload.get("summary", {})}]
    fieldnames = sorted({key for row in rows if isinstance(row, dict) for key in row.keys()}) or ["summary"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row if isinstance(row, dict) else {"summary": str(row)})
    return output.getvalue()


def _csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


# Module-level app instance (only used when running via `uvicorn saas_app:app` directly).
# The `run()` function creates its own instance to avoid double-init.
try:
    app = create_app()
except Exception:
    app = None  # type: ignore[assignment]


def run(host: str = "127.0.0.1", port: int = 8787) -> None:
    _app = create_app()
    uvicorn.run(_app, host=host, port=port, reload=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aso-saas")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args(argv)
    run(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
