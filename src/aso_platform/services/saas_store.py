"""SQLite store for the local SaaS MVP."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DATA_ROOT = Path(__file__).resolve().parents[3] / "data"
DEFAULT_DB_PATH = DATA_ROOT / "aso_saas.sqlite3"


@dataclass
class JobError:
    code: str
    message: str
    fix: str


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    clean = "-".join(part for part in clean.split("-") if part)
    return clean or "workspace"


class SaasStore:
    """Tiny multi-tenant store for accounts, projects, and analysis reports."""

    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    organization_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (organization_id) REFERENCES organizations(id)
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    package_id TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    seed_text TEXT NOT NULL DEFAULT '',
                    lang TEXT NOT NULL DEFAULT 'en',
                    country TEXT NOT NULL DEFAULT 'us',
                    competitors_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (organization_id) REFERENCES organizations(id)
                );
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL,
                    project_id INTEGER,
                    analysis_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    action_plan_json TEXT NOT NULL DEFAULT '[]',
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    confidence_json TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT,
                    completed_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (organization_id) REFERENCES organizations(id),
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    workspace_name TEXT NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS analysis_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL,
                    project_id INTEGER NOT NULL,
                    analysis_id INTEGER,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_code TEXT NOT NULL DEFAULT '',
                    error_message TEXT NOT NULL DEFAULT '',
                    error_fix TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (organization_id) REFERENCES organizations(id),
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
                );
                CREATE TABLE IF NOT EXISTS source_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER,
                    source_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    amount INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._ensure_columns(conn)

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        analysis_cols = {row["name"] for row in conn.execute("PRAGMA table_info(analyses)").fetchall()}
        additions = {
            "action_plan_json": "TEXT NOT NULL DEFAULT '[]'",
            "warnings_json": "TEXT NOT NULL DEFAULT '[]'",
            "confidence_json": "TEXT NOT NULL DEFAULT '{}'",
            "started_at": "TEXT",
            "completed_at": "TEXT",
        }
        allowed_columns = {"action_plan_json", "warnings_json", "confidence_json", "started_at", "completed_at"}
        for name, sql_type in additions.items():
            if name not in allowed_columns or not name.isidentifier():
                raise ValueError(f"Invalid column name: {name}")
            if name not in analysis_cols:
                conn.execute(f"ALTER TABLE analyses ADD COLUMN {name} {sql_type}")

    def signup(self, email: str, workspace_name: str) -> dict[str, Any]:
        email = email.strip().lower()
        workspace_name = workspace_name.strip() or email.split("@")[0] or "ASO Workspace"
        if not email or "@" not in email:
            raise ValueError("Valid email is required.")
        now = _now()
        with self._connection() as conn:
            return self._ensure_account(conn, email, workspace_name, now)

    def _ensure_account(self, conn: sqlite3.Connection, email: str, workspace_name: str, now: str) -> dict[str, Any]:
        existing = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            org = conn.execute("SELECT * FROM organizations WHERE id = ?", (existing["organization_id"],)).fetchone()
            return {"user": dict(existing), "organization": dict(org)}
        base_slug = _slug(workspace_name)
        slug = base_slug
        counter = 2
        while conn.execute("SELECT id FROM organizations WHERE slug = ?", (slug,)).fetchone():
            slug = f"{base_slug}-{counter}"
            counter += 1
        cursor = conn.execute(
            "INSERT INTO organizations (name, slug, created_at) VALUES (?, ?, ?)",
            (workspace_name, slug, now),
        )
        organization_id = int(cursor.lastrowid)
        conn.execute(
            "INSERT INTO users (email, organization_id, role, created_at) VALUES (?, ?, ?, ?)",
            (email, organization_id, "owner", now),
        )
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        org = conn.execute("SELECT * FROM organizations WHERE id = ?", (organization_id,)).fetchone()
        return {"user": dict(user), "organization": dict(org)}

    def create_auth_token(self, email: str, workspace_name: str = "", ttl_minutes: int = 15) -> dict[str, Any]:
        email = email.strip().lower()
        if not email or "@" not in email:
            raise ValueError("Valid email is required.")
        token = secrets.token_urlsafe(32)
        hashed_token = _hash_token(token)
        now = _now()
        expires_at = (datetime.now(UTC) + timedelta(minutes=ttl_minutes)).isoformat()
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO auth_tokens (email, workspace_name, token, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (email, workspace_name.strip(), hashed_token, expires_at, now),
            )
        return {"email": email, "token": token, "expires_at": expires_at, "magic_link": f"/api/auth/verify?token={token}"}

    def verify_auth_token(self, token: str, session_ttl_days: int = 30) -> dict[str, Any]:
        token = token.strip()
        hashed_token = _hash_token(token)
        now = _now()
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM auth_tokens WHERE token = ?", (hashed_token,)).fetchone()
            if not row:
                raise ValueError("Magic link is invalid.")
            if row["consumed_at"]:
                raise ValueError("Magic link was already used.")
            if row["expires_at"] < now:
                raise ValueError("Magic link expired. Request a new one.")
            account = self._ensure_account(conn, row["email"], row["workspace_name"], now)
            conn.execute("UPDATE auth_tokens SET consumed_at = ? WHERE id = ?", (now, row["id"]))
            session_token = secrets.token_urlsafe(40)
            hashed_session_token = _hash_token(session_token)
            expires_at = (datetime.now(UTC) + timedelta(days=session_ttl_days)).isoformat()
            conn.execute(
                "INSERT INTO sessions (user_id, token, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (account["user"]["id"], hashed_session_token, expires_at, now),
            )
            return {**account, "session": {"token": session_token, "expires_at": expires_at}}

    def account_for_session(self, session_token: str) -> dict[str, Any] | None:
        session_token = (session_token or "").strip()
        if not session_token:
            return None
        hashed_session_token = _hash_token(session_token)
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT sessions.*, users.email, users.organization_id, users.role, users.created_at AS user_created_at
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?
                """,
                (hashed_session_token,),
            ).fetchone()
            if not row or row["expires_at"] < _now():
                return None
            org = conn.execute("SELECT * FROM organizations WHERE id = ?", (row["organization_id"],)).fetchone()
            user = {
                "id": row["user_id"],
                "email": row["email"],
                "organization_id": row["organization_id"],
                "role": row["role"],
                "created_at": row["user_created_at"],
            }
            return {"user": user, "organization": dict(org)}

    def delete_session(self, session_token: str) -> None:
        session_token = (session_token or "").strip()
        if not session_token:
            return
        hashed_session_token = _hash_token(session_token)
        with self._connection() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (hashed_session_token,))

    def account_for_email(self, email: str) -> dict[str, Any] | None:
        email = email.strip().lower()
        with self._connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not user:
                return None
            org = conn.execute("SELECT * FROM organizations WHERE id = ?", (user["organization_id"],)).fetchone()
            return {"user": dict(user), "organization": dict(org)}

    def create_project(self, organization_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        package_id = str(payload.get("package_id") or "").strip()
        if not name:
            raise ValueError("Project name is required.")
        if not package_id:
            raise ValueError("Package id is required.")
        if len([item for item in str(payload.get("seed_text") or "").split(",") if item.strip()]) > 10:
            raise ValueError("Use 10 or fewer seed keywords for the first audit.")
        competitors = payload.get("competitors") or []
        if isinstance(competitors, str):
            competitors = [item.strip() for item in competitors.split(",") if item.strip()]
        now = _now()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO projects
                (organization_id, name, package_id, category, seed_text, lang, country, competitors_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    organization_id,
                    name,
                    package_id,
                    str(payload.get("category") or ""),
                    str(payload.get("seed_text") or ""),
                    str(payload.get("lang") or "en").lower(),
                    str(payload.get("country") or "us").lower(),
                    json.dumps(competitors, ensure_ascii=True),
                    now,
                    now,
                ),
            )
            project_id = int(cursor.lastrowid)
            row = conn.execute("SELECT * FROM projects WHERE id = ? AND organization_id = ?", (project_id, organization_id)).fetchone()
            if not row:
                raise KeyError("Project not found.")
            return self._project_dict(row)

    def list_projects(self, organization_id: int) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM projects WHERE organization_id = ? ORDER BY updated_at DESC", (organization_id,)).fetchall()
            return [self._project_dict(row) for row in rows]

    def get_project(self, organization_id: int, project_id: int) -> dict[str, Any]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ? AND organization_id = ?", (project_id, organization_id)).fetchone()
            if not row:
                raise KeyError("Project not found.")
            return self._project_dict(row)

    def record_analysis(self, organization_id: int, project_id: int | None, analysis_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        summary = self._summary_for(analysis_type, payload)
        warnings = payload.get("warnings", [])
        confidence = payload.get("confidence", {})
        action_plan = payload.get("action_plan", self.action_plan_for(payload))
        now = _now()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analyses
                (organization_id, project_id, analysis_type, status, summary, payload_json, action_plan_json, warnings_json, confidence_json, started_at, completed_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    organization_id,
                    project_id,
                    analysis_type,
                    "complete",
                    summary,
                    json.dumps(payload, ensure_ascii=True),
                    json.dumps(action_plan, ensure_ascii=True),
                    json.dumps(warnings, ensure_ascii=True),
                    json.dumps(confidence, ensure_ascii=True),
                    now,
                    now,
                    now,
                ),
            )
            analysis_id = int(cursor.lastrowid)
            row = conn.execute("SELECT * FROM analyses WHERE id = ? AND organization_id = ?", (analysis_id, organization_id)).fetchone()
            if not row:
                raise KeyError("Analysis not found.")
            return self._analysis_dict(row, include_payload=True)

    def list_analyses(self, organization_id: int, limit: int = 20) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM analyses WHERE organization_id = ? ORDER BY created_at DESC LIMIT ?",
                (organization_id, limit),
            ).fetchall()
            return [self._analysis_dict(row, include_payload=False) for row in rows]

    def get_analysis(self, organization_id: int, analysis_id: int) -> dict[str, Any]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM analyses WHERE id = ? AND organization_id = ?", (analysis_id, organization_id)).fetchone()
            if not row:
                raise KeyError("Analysis not found.")
            return self._analysis_dict(row, include_payload=True)

    def create_job(self, organization_id: int, project_id: int, job_type: str = "baseline") -> dict[str, Any]:
        now = _now()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analysis_jobs (organization_id, project_id, job_type, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (organization_id, project_id, job_type, "queued", now),
            )
            return self.get_job(organization_id, int(cursor.lastrowid), conn=conn)

    def start_job(self, organization_id: int, job_id: int) -> dict[str, Any]:
        now = _now()
        with self._connection() as conn:
            conn.execute("UPDATE analysis_jobs SET status = ?, started_at = ? WHERE id = ? AND organization_id = ?", ("running", now, job_id, organization_id))
            return self.get_job(organization_id, job_id, conn=conn)

    def complete_job(self, organization_id: int, job_id: int, analysis_id: int) -> dict[str, Any]:
        now = _now()
        with self._connection() as conn:
            conn.execute(
                "UPDATE analysis_jobs SET status = ?, analysis_id = ?, completed_at = ? WHERE id = ? AND organization_id = ?",
                ("succeeded", analysis_id, now, job_id, organization_id),
            )
            return self.get_job(organization_id, job_id, conn=conn)

    def fail_job(self, organization_id: int, job_id: int, error: JobError) -> dict[str, Any]:
        now = _now()
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE analysis_jobs
                SET status = ?, error_code = ?, error_message = ?, error_fix = ?, completed_at = ?
                WHERE id = ? AND organization_id = ?
                """,
                ("failed", error.code, error.message, error.fix, now, job_id, organization_id),
            )
            return self.get_job(organization_id, job_id, conn=conn)

    def get_job(self, organization_id: int, job_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        own_conn = conn is None
        conn = conn or self._connect()
        try:
            row = conn.execute("SELECT * FROM analysis_jobs WHERE id = ? AND organization_id = ?", (job_id, organization_id)).fetchone()
            if not row:
                raise KeyError("Job not found.")
            return dict(row)
        finally:
            if own_conn:
                conn.close()

    def count_projects(self, organization_id: int) -> int:
        with self._connection() as conn:
            return int(conn.execute("SELECT COUNT(*) AS count FROM projects WHERE organization_id = ?", (organization_id,)).fetchone()["count"])

    def count_analyses_today(self, organization_id: int) -> int:
        today = datetime.now(UTC).date().isoformat()
        with self._connection() as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) AS count FROM analyses WHERE organization_id = ? AND created_at >= ?",
                    (organization_id, today),
                ).fetchone()["count"]
            )

    def record_usage(self, organization_id: int, event_type: str, amount: int = 1) -> None:
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO usage_events (organization_id, event_type, amount, created_at) VALUES (?, ?, ?, ?)",
                (organization_id, event_type, amount, _now()),
            )

    def record_source_event(self, organization_id: int | None, source_id: str, status: str, message: str) -> None:
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO source_events (organization_id, source_id, status, message, created_at) VALUES (?, ?, ?, ?, ?)",
                (organization_id, source_id, status, message, _now()),
            )

    @staticmethod
    def _project_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["competitors"] = json.loads(data.pop("competitors_json") or "[]")
        return data

    @staticmethod
    def _analysis_dict(row: sqlite3.Row, *, include_payload: bool) -> dict[str, Any]:
        data = dict(row)
        payload = json.loads(data.pop("payload_json") or "{}")
        data["action_plan"] = json.loads(data.pop("action_plan_json", "[]") or "[]")
        data["warnings"] = json.loads(data.pop("warnings_json", "[]") or "[]")
        data["confidence"] = json.loads(data.pop("confidence_json", "{}") or "{}")
        if include_payload:
            data["payload"] = payload
        return data

    @staticmethod
    def _summary_for(analysis_type: str, payload: dict[str, Any]) -> str:
        if analysis_type == "baseline":
            summary = payload.get("summary", {})
            return f"{summary.get('keyword_count', 0)} keywords, best rank {summary.get('best_rank') or 'not found'}"
        if analysis_type == "metadata":
            audit = payload.get("metadata_audit", {})
            return f"title {audit.get('title_score', 0)}, short {audit.get('short_description_score', 0)}"
        if analysis_type == "keyword_score":
            return f"{len(payload.get('scores', []))} keyword estimates"
        return analysis_type.replace("_", " ").title()

    @staticmethod
    def action_plan_for(payload: dict[str, Any]) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        metadata = payload.get("metadata_audit", {})
        for recommendation in metadata.get("recommendations", [])[:4]:
            actions.append({"priority": "high", "area": "metadata", "title": recommendation, "why": "Public metadata affects conversion and keyword relevance."})
        keywords = payload.get("keyword_report", {}).get("keywords", []) or payload.get("keywords", [])
        for item in keywords[:5]:
            keyword = item.get("keyword", "")
            score = item.get("composite_score") or item.get("score") or 0
            actions.append({"priority": "medium", "area": "keyword", "title": f"Target '{keyword}'", "why": f"Opportunity score {score} from approved public/local signals."})
        for warning in payload.get("warnings", [])[:5]:
            actions.append({"priority": "low", "area": "trust", "title": warning.get("message", "Review source warning."), "why": "Warnings reduce confidence and should be checked before acting."})
        if not actions:
            actions.append({"priority": "medium", "area": "next_step", "title": "Run baseline audit again after metadata changes.", "why": "Tracking repeated runs builds rank and confidence history."})
        return actions[:8]
