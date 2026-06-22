"""CLI for the enterprise ASO platform slice."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .capabilities import audit_capabilities
from .registry import load_source_registry
from .services.app_inspector import AppInspectionService
from .services.intelligence import (
    AlertService,
    CompetitorIntelligenceService,
    DatabaseBuildParams,
    IOSInspectionService,
    KeywordIntelligenceService,
    ShareOfVoiceOptions,
    LocalizationAuditService,
    MetadataAuditService,
    RankHistoryService,
    ReportExportService,
    ReviewIntelligenceService,
    SourceHealthService,
)
from .services.keyword_discovery import KeywordDiscoveryService
from .services.keyword_rank import KeywordRankService, RankConfig
from .services.workspace import WorkspaceService
from .saas_app import run as run_saas_app
from .ui.branding import APP_NAME, APP_TAGLINE, render_kite_logo
from core.keywords import available_keyword_categories, get_category_seed_keywords

VERSION = "0.2.0"

EXAMPLES = """examples:
  python -m src.aso_platform.cli doctor
  python -m src.aso_platform.cli workspace init "calc-lab" com.example.calc --category tools --seed "scientific calculator, bmi"
  python -m src.aso_platform.cli workspace show calc-lab
  python -m src.aso_platform.cli workspace baseline calc-lab --format json
  python -m src.aso_platform.cli categories
  python -m src.aso_platform.cli categories --category tools --format json
  python -m src.aso_platform.cli keywords --category tools --seed "bmi calculator"
  python -m src.aso_platform.cli keywords build --category tools --seed "bmi calculator"
  python -m src.aso_platform.cli keywords score "bmi calculator,loan calculator" --app-text "calculator finance tools"
  python -m src.aso_platform.cli inspect com.google.android.calculator --format json
  python -m src.aso_platform.cli rank "calculator" com.google.android.calculator --no-history
  python -m src.aso_platform.cli rank history "calculator" com.google.android.calculator --format json
  python -m src.aso_platform.cli competitors gap calc-lab --format json
  python -m src.aso_platform.cli audit metadata com.google.android.calculator --keywords "calculator,math"
  python -m src.aso_platform.cli reviews analyze com.google.android.calculator --count 50
  python -m src.aso_platform.cli localization audit com.google.android.calculator --markets "en-us,en-gb" --keywords "calculator"
  python -m src.aso_platform.cli ios inspect com.apple.Pages --country us
  python -m src.aso_platform.cli capabilities --status planned
  python -m src.aso_platform.cli saas --port 8787
"""


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _csv_items(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _add_format_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the full output payload. Parent directories are created.",
    )


def _emit(payload: dict, args: argparse.Namespace, text: str) -> None:
    rendered = json.dumps(payload, indent=2) if args.format == "json" else text
    if getattr(args, "output", None):
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def _warning_lines(warnings: list[dict]) -> list[str]:
    if not warnings:
        return []
    lines = ["Warnings:"]
    for warning in warnings:
        code = warning.get("code", "warning")
        message = warning.get("message", str(warning))
        lines.append(f"- {code}: {message}")
    return lines


def _simple_report_text(title: str, payload: dict) -> str:
    lines = [render_kite_logo().rstrip(), "", f"{APP_NAME} {title}"]
    confidence = payload.get("confidence")
    if confidence:
        lines.append(f"Confidence: {confidence.get('label')} ({confidence.get('score')})")
    for key, value in payload.items():
        if key in {"request_context", "evidence", "warnings", "confidence"}:
            continue
        lines.append("")
        lines.append(key.replace("_", " ").title() + ":")
        if isinstance(value, list):
            for item in value[:12]:
                lines.append(f"- {json.dumps(item, ensure_ascii=True, sort_keys=True)}")
        else:
            lines.append(json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True))
    lines.extend(_warning_lines(payload.get("warnings", [])))
    return "\n".join(lines)


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _handle_nested_legacy_commands(argv: list[str]) -> int | None:
    if len(argv) >= 2 and argv[0] == "keywords" and argv[1] in {"build", "score"}:
        parser = argparse.ArgumentParser(prog=f"kite keywords {argv[1]}")
        if argv[1] == "build":
            parser.add_argument("--category", default="")
            parser.add_argument("--seed", default="")
            parser.add_argument("--lang", default="en")
            parser.add_argument("--country", default="us")
            parser.add_argument("--limit", type=_positive_int, default=40)
            _add_format_args(parser)
            args = parser.parse_args(argv[2:])
            params = DatabaseBuildParams(
                category=args.category,
                seed_text=args.seed,
                lang=args.lang,
                country=args.country,
                limit=args.limit,
            )
            payload = KeywordIntelligenceService().build_database(params)
            _emit(payload, args, _simple_report_text("Keyword Database", payload))
            return 0
        parser.add_argument("keywords", help="Comma-separated keywords")
        parser.add_argument("--app-text", default="")
        parser.add_argument("--current-rank", type=int)
        _add_format_args(parser)
        args = parser.parse_args(argv[2:])
        payload = KeywordIntelligenceService().score(_parse_csv(args.keywords), app_text=args.app_text, current_rank=args.current_rank)
        _emit(payload, args, _simple_report_text("Keyword Score", payload))
        return 0

    if len(argv) >= 2 and argv[0] == "rank" and argv[1] in {"history", "delta"}:
        parser = argparse.ArgumentParser(prog=f"kite rank {argv[1]}")
        parser.add_argument("keyword")
        parser.add_argument("package_id")
        _add_format_args(parser)
        args = parser.parse_args(argv[2:])
        service = RankHistoryService()
        payload = service.history(args.keyword, args.package_id) if argv[1] == "history" else service.delta(args.keyword, args.package_id)
        _emit(payload, args, _simple_report_text("Rank " + argv[1].title(), payload))
        return 0

    return None



def _add_workspace_parser(subparsers) -> None:
    workspace_parser = subparsers.add_parser(
        "workspace",
        help="Manage ASO workspaces and run baseline product flows.",
    )
    workspace_subparsers = workspace_parser.add_subparsers(dest="workspace_command", required=True)

    workspace_init = workspace_subparsers.add_parser(
        "init",
        help="Create a workspace for one target app, market, and keyword scope.",
    )
    workspace_init.add_argument("name", help="Workspace name")
    workspace_init.add_argument("package_id", help="Target Android package identifier")
    workspace_init.add_argument("--category", default="", help="Optional category, for example tools")
    workspace_init.add_argument("--seed", default="", help="Optional comma-separated seed words or app topics")
    workspace_init.add_argument("--lang", default="en", help="Language code")
    workspace_init.add_argument("--country", default="us", help="Country code")
    workspace_init.add_argument("--competitors", default="", help="Optional comma-separated competitor package ids")
    workspace_init.add_argument("--notes", default="", help="Optional operator notes")
    workspace_init.add_argument("--overwrite", action="store_true", help="Overwrite an existing workspace with the same id")
    _add_format_args(workspace_init)

    workspace_show = workspace_subparsers.add_parser(
        "show",
        help="Show one saved workspace.",
    )
    workspace_show.add_argument("workspace", help="Workspace id or name")
    _add_format_args(workspace_show)

    workspace_list = workspace_subparsers.add_parser(
        "list",
        help="List saved workspaces.",
    )
    _add_format_args(workspace_list)

    workspace_baseline = workspace_subparsers.add_parser(
        "baseline",
        help="Run baseline app + keyword + rank workflow for one workspace.",
    )
    workspace_baseline.add_argument("workspace", help="Workspace id or name")
    workspace_baseline.add_argument("--keyword-limit", type=_positive_int, default=20, help="Maximum keyword opportunities to generate")
    workspace_baseline.add_argument("--top-keywords", type=_positive_int, default=5, help="How many top keywords to rank-check")
    workspace_baseline.add_argument("--rank-limit", type=_positive_int, default=10, help="Maximum public search results to inspect per rank check")
    workspace_baseline.add_argument("--save-history", action="store_true", help="Append rank checks to local history")
    _add_format_args(workspace_baseline)

def _add_categories_parser(subparsers) -> None:
    categories_parser = subparsers.add_parser(
        "categories",
        help="List supported local keyword categories or inspect one category.",
    )
    categories_parser.add_argument("--category", help="Optional category to inspect, for example tools")
    _add_format_args(categories_parser)

def _add_keywords_parser(subparsers) -> None:
    keywords_parser = subparsers.add_parser(
        "keywords",
        aliases=("discover-keywords", "discover"),
        help="Discover keyword opportunities from a category, seed words, or both.",
    )
    keywords_parser.add_argument("--category", default="", help="Optional category, for example tools or finance")
    keywords_parser.add_argument("--seed", default="", help="Optional seed words, app name, or comma-separated topics")
    keywords_parser.add_argument("--lang", default="en", help="Language code")
    keywords_parser.add_argument("--country", default="us", help="Country code")
    keywords_parser.add_argument("--limit", type=_positive_int, default=40, help="Maximum keyword opportunities to return")
    _add_format_args(keywords_parser)

def _add_inspect_parser(subparsers) -> None:
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect one Android app using policy-approved public sources.",
    )
    inspect_parser.add_argument("package_id", help="Android package identifier")
    inspect_parser.add_argument("--lang", default="en", help="Language code")
    inspect_parser.add_argument("--country", default="us", help="Country code")
    _add_format_args(inspect_parser)

def _add_rank_parser(subparsers) -> None:
    rank_parser = subparsers.add_parser(
        "rank",
        help="Check target app position for one keyword using approved public search.",
    )
    rank_parser.add_argument("keyword", help="Keyword/search query to check")
    rank_parser.add_argument("package_id", help="Target Android package identifier")
    rank_parser.add_argument("--lang", default="en", help="Language code")
    rank_parser.add_argument("--country", default="us", help="Country code")
    rank_parser.add_argument("--limit", type=_positive_int, default=20, help="Maximum public results to inspect")
    rank_parser.add_argument("--no-history", action="store_true", help="Do not append this check to local history")
    _add_format_args(rank_parser)

def _add_capabilities_parser(subparsers) -> None:
    capabilities_parser = subparsers.add_parser(
        "capabilities",
        help="List planned, active, and blocked ASO capabilities with legal-source status.",
    )
    capabilities_parser.add_argument("--area", help="Filter by capability area")
    capabilities_parser.add_argument("--status", choices=("active", "planned", "blocked"), help="Filter by build status")
    _add_format_args(capabilities_parser)

def _add_sov_parser(subparsers) -> None:
    sov_parser = subparsers.add_parser(
        "share-of-voice",
        help="Compare target and competitor visibility across public keyword ranks.",
    )
    sov_parser.add_argument("keywords", help="Comma-separated keywords")
    sov_parser.add_argument("package_id", help="Target Android package identifier")
    sov_parser.add_argument("--competitors", default="", help="Comma-separated competitor package ids")
    sov_parser.add_argument("--lang", default="en")
    sov_parser.add_argument("--country", default="us")
    sov_parser.add_argument("--limit", type=_positive_int, default=20)
    _add_format_args(sov_parser)

def _add_competitors_parser(subparsers) -> None:
    competitors_parser = subparsers.add_parser("competitors", help="Manage competitor watchlists and analysis.")
    competitors_subparsers = competitors_parser.add_subparsers(dest="competitors_command", required=True)
    for name in ("add", "remove"):
        sub = competitors_subparsers.add_parser(name, help=f"{name.title()} competitors for a workspace.")
        sub.add_argument("workspace")
        sub.add_argument("package_ids", help="Comma-separated package ids")
        _add_format_args(sub)
    competitors_list = competitors_subparsers.add_parser("list", help="List workspace competitors.")
    competitors_list.add_argument("workspace")
    _add_format_args(competitors_list)
    competitors_gap = competitors_subparsers.add_parser("gap", help="Find ranking-based keyword gaps.")
    competitors_gap.add_argument("workspace")
    competitors_gap.add_argument("--keywords", default="", help="Optional comma-separated keyword override")
    competitors_gap.add_argument("--limit", type=_positive_int, default=20)
    _add_format_args(competitors_gap)
    competitors_timeline = competitors_subparsers.add_parser("timeline", help="Capture competitor metadata changes.")
    competitors_timeline.add_argument("workspace")
    _add_format_args(competitors_timeline)
    competitors_creatives = competitors_subparsers.add_parser("creatives", help="Capture creative references and hashes.")
    competitors_creatives.add_argument("workspace")
    _add_format_args(competitors_creatives)

def _add_audit_parser(subparsers) -> None:
    audit_parser = subparsers.add_parser("audit", help="Run metadata and optimization audits.")
    audit_subparsers = audit_parser.add_subparsers(dest="audit_command", required=True)
    audit_metadata = audit_subparsers.add_parser("metadata", help="Audit public store metadata.")
    audit_metadata.add_argument("package_id")
    audit_metadata.add_argument("--keywords", default="")
    audit_metadata.add_argument("--lang", default="en")
    audit_metadata.add_argument("--country", default="us")
    _add_format_args(audit_metadata)

def _add_reviews_parser(subparsers) -> None:
    reviews_parser = subparsers.add_parser("reviews", help="Analyze public review samples.")
    reviews_subparsers = reviews_parser.add_subparsers(dest="reviews_command", required=True)
    reviews_analyze = reviews_subparsers.add_parser("analyze", help="Analyze review sentiment and topics.")
    reviews_analyze.add_argument("package_id")
    reviews_analyze.add_argument("--count", type=_positive_int, default=100)
    reviews_analyze.add_argument("--lang", default="en")
    reviews_analyze.add_argument("--country", default="us")
    _add_format_args(reviews_analyze)

def _add_localization_parser(subparsers) -> None:
    localization_parser = subparsers.add_parser("localization", help="Audit localized metadata and ranks.")
    localization_subparsers = localization_parser.add_subparsers(dest="localization_command", required=True)
    localization_audit = localization_subparsers.add_parser("audit", help="Audit locales such as en-us,en-gb.")
    localization_audit.add_argument("package_id")
    localization_audit.add_argument("--markets", default="en-us")
    localization_audit.add_argument("--keywords", default="")
    _add_format_args(localization_audit)

def _add_ios_parser(subparsers) -> None:
    ios_parser = subparsers.add_parser("ios", help="Inspect public Apple App Store metadata.")
    ios_subparsers = ios_parser.add_subparsers(dest="ios_command", required=True)
    ios_inspect = ios_subparsers.add_parser("inspect", help="Inspect an iOS app by bundle id or track id.")
    ios_inspect.add_argument("identifier")
    ios_inspect.add_argument("--country", default="us")
    _add_format_args(ios_inspect)

def _add_reports_parser(subparsers) -> None:
    reports_parser = subparsers.add_parser("reports", help="Export local ASO reports.")
    reports_subparsers = reports_parser.add_subparsers(dest="reports_command", required=True)
    reports_export = reports_subparsers.add_parser("export", help="Export a workspace baseline report.")
    reports_export.add_argument("workspace")
    reports_export.add_argument("--file", required=True, help="Destination report path")
    reports_export.add_argument("--export-format", choices=("json", "csv", "md"), default="json")
    reports_export.add_argument("--keyword-limit", type=_positive_int, default=20)
    reports_export.add_argument("--top-keywords", type=_positive_int, default=5)
    reports_export.add_argument("--rank-limit", type=_positive_int, default=10)
    _add_format_args(reports_export)

def _add_alerts_parser(subparsers) -> None:
    alerts_parser = subparsers.add_parser("alerts", help="List or check local alert conditions.")
    alerts_subparsers = alerts_parser.add_subparsers(dest="alerts_command", required=True)
    alerts_list = alerts_subparsers.add_parser("list", help="List local alert rules.")
    _add_format_args(alerts_list)
    alerts_check = alerts_subparsers.add_parser("check", help="Check rank-drop and not-found alerts.")
    alerts_check.add_argument("keyword")
    alerts_check.add_argument("package_id")
    alerts_check.add_argument("--drop-threshold", type=_positive_int, default=3)
    _add_format_args(alerts_check)

def _add_sources_parser(subparsers) -> None:
    sources_parser = subparsers.add_parser("sources", help="Inspect source governance and health.")
    sources_subparsers = sources_parser.add_subparsers(dest="sources_command", required=True)
    sources_health = sources_subparsers.add_parser("health", help="Show source policy readiness.")
    _add_format_args(sources_health)

def _add_saas_parser(subparsers) -> None:
    saas_parser = subparsers.add_parser("saas", help="Run the ASO PRO SaaS MVP web console.")
    saas_parser.add_argument("--host", default="127.0.0.1")
    saas_parser.add_argument("--port", type=int, default=8787)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kite",
        description=f"{render_kite_logo()}\n{APP_NAME}: {APP_TAGLINE}",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check local project health, source policy, and platform readiness.",
    )
    _add_format_args(doctor_parser)

    _add_workspace_parser(subparsers)
    _add_categories_parser(subparsers)
    _add_keywords_parser(subparsers)
    _add_inspect_parser(subparsers)
    _add_rank_parser(subparsers)
    _add_capabilities_parser(subparsers)
    _add_sov_parser(subparsers)
    _add_competitors_parser(subparsers)
    _add_audit_parser(subparsers)
    _add_reviews_parser(subparsers)
    _add_localization_parser(subparsers)
    _add_ios_parser(subparsers)
    _add_reports_parser(subparsers)
    _add_alerts_parser(subparsers)
    _add_sources_parser(subparsers)
    _add_saas_parser(subparsers)

    return parser


def _doctor_payload() -> dict:
    sources = load_source_registry()
    audit = audit_capabilities(registry=sources)
    root = Path(__file__).resolve().parents[2]
    checks = [
        {
            "name": "source_registry",
            "status": "ok",
            "details": f"{len(sources)} sources loaded",
        },
        {
            "name": "approved_runtime_sources",
            "status": "ok",
            "details": f"{sum(1 for source in sources.values() if source.enabled and source.compliance_status.value == 'approved')} approved/enabled sources",
        },
        {
            "name": "capability_catalog",
            "status": "ok" if audit["summary"]["missing_sources"] == 0 else "warning",
            "details": f"{audit['summary']['legal_ready']} legal-ready capabilities, {audit['summary']['missing_sources']} with missing sources",
        },
        {
            "name": "reports_directory",
            "status": "ok" if (root / "reports").exists() else "warning",
            "details": str(root / "reports"),
        },
        {
            "name": "cache_directory",
            "status": "ok" if (root / "cache").exists() else "warning",
            "details": str(root / "cache"),
        },
    ]
    status = "ok" if all(check["status"] == "ok" for check in checks) else "warning"
    return {
        "status": status,
        "version": VERSION,
        "checks": checks,
        "policy": {
            "free_legal_only": True,
            "runtime_rule": "sources must be free, auth=none, enabled=true, compliance_status=approved",
        },
    }


def _doctor_text(payload: dict) -> str:
    lines = [
        render_kite_logo().rstrip(),
        "",
        f"{APP_NAME} Doctor",
        f"Status: {payload['status']}",
        f"Version: {payload['version']}",
        "",
        "Checks:",
    ]
    for check in payload["checks"]:
        lines.append(f"- {check['status']}: {check['name']} - {check['details']}")
    lines.extend([
        "",
        "Policy:",
        f"- free/legal only: {payload['policy']['free_legal_only']}",
        f"- runtime rule: {payload['policy']['runtime_rule']}",
    ])
    return "\n".join(lines)


def _categories_payload(category: str | None = None) -> dict:
    if category:
        detail = get_category_seed_keywords(category)
        return {
            "categories": available_keyword_categories(),
            "selected": detail,
        }
    return {
        "categories": available_keyword_categories(),
        "selected": None,
    }


def _categories_text(payload: dict) -> str:
    if payload["selected"]:
        selected = payload["selected"]
        lines = [
            render_kite_logo().rstrip(),
            "",
            f"{APP_NAME} Categories",
            f"Selected: {selected['category'] or 'not matched'}",
            f"Matched: {selected['matched']}",
            "Seeds:",
        ]
        lines.extend(f"- {seed}" for seed in selected["seeds"])
        if selected["warnings"]:
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in selected["warnings"])
        return "\n".join(lines)
    return "\n".join([render_kite_logo().rstrip(), "", f"{APP_NAME} Categories", *[f"- {category}" for category in payload["categories"]]])


def _workspace_text(payload: dict) -> str:
    lines = [
        render_kite_logo().rstrip(),
        "",
        f"{APP_NAME} Workspace",
        f"Workspace: {payload['name']} ({payload['workspace_id']})",
        f"Target: {payload['target_package_id']}",
        f"Market: {payload['country']}/{payload['lang']}",
        f"Category: {payload['category'] or 'none'}",
        f"Seeds: {payload['seed_text'] or 'none'}",
        f"Competitors: {', '.join(payload['competitors']) if payload['competitors'] else 'none'}",
    ]
    if payload.get("notes"):
        lines.append(f"Notes: {payload['notes']}")
    return "\n".join(lines)


def _workspace_list_text(payload: dict) -> str:
    lines = [render_kite_logo().rstrip(), "", f"{APP_NAME} Workspaces", f"Count: {len(payload['workspaces'])}", "", "Saved workspaces:"]
    for row in payload["workspaces"]:
        lines.append(
            f"- {row['workspace_id']}: {row['target_package_id']} [{row['country']}/{row['lang']}] "
            f"category={row['category'] or 'none'}"
        )
    return "\n".join(lines)


def _workspace_baseline_text(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        render_kite_logo().rstrip(),
        "",
        f"{APP_NAME} Workspace Baseline",
        f"Workspace: {payload['workspace']['name']} ({payload['workspace']['workspace_id']})",
        f"Target: {summary['target_package_id']}",
        f"Market: {summary['country']}/{summary['lang']}",
        f"Keywords: {summary['keyword_count']}",
        f"Rank checks: {summary['rank_checks_run']}",
        f"Rank hits: {summary['rank_hits']}",
        f"Best rank: {summary['best_rank'] if summary['best_rank'] is not None else 'not found'}",
        f"App confidence: {summary['app_confidence']}",
        f"Keyword confidence: {summary['keyword_confidence']}",
        "",
        "Top opportunities:",
    ]
    for index, item in enumerate(payload["keyword_report"].get("keywords", [])[:5], 1):
        lines.append(f"{index:2}. {item['keyword']} [score={item['composite_score']}, priority={item['priority']}]")
    lines.extend(_warning_lines(payload.get("warnings", [])))
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    custom_exit = _handle_nested_legacy_commands(raw_argv)
    if custom_exit is not None:
        return custom_exit
    parser = build_parser()
    args = parser.parse_args(raw_argv)
    if args.command == "doctor":
        payload = _doctor_payload()
        _emit(payload, args, _doctor_text(payload))
        return 0
    if args.command == "workspace":
        service = WorkspaceService()
        if args.workspace_command == "init":
            payload = service.create(
                args.name,
                args.package_id,
                category=args.category,
                seed_text=args.seed,
                lang=args.lang,
                country=args.country,
                competitors=_csv_items(args.competitors),
                notes=args.notes,
                overwrite=args.overwrite,
            ).to_dict()
            _emit(payload, args, _workspace_text(payload))
            return 0
        if args.workspace_command == "show":
            payload = service.get(args.workspace).to_dict()
            _emit(payload, args, _workspace_text(payload))
            return 0
        if args.workspace_command == "list":
            payload = {"workspaces": [item.to_dict() for item in service.list()]}
            _emit(payload, args, _workspace_list_text(payload))
            return 0
        if args.workspace_command == "baseline":
            payload = service.baseline(
                args.workspace,
                keyword_limit=args.keyword_limit,
                top_keywords=args.top_keywords,
                rank_limit=args.rank_limit,
                save_history=args.save_history,
            ).to_dict()
            _emit(payload, args, _workspace_baseline_text(payload))
            return 0
        return 1
    if args.command == "categories":
        payload = _categories_payload(args.category)
        _emit(payload, args, _categories_text(payload))
        return 0
    if args.command in {"keywords", "discover-keywords", "discover"}:
        if not args.category and not args.seed:
            parser.error("keywords requires --category, --seed, or both")
        service = KeywordDiscoveryService()
        report = service.discover(
            seed_text=args.seed,
            category=args.category,
            lang=args.lang,
            country=args.country,
            limit=args.limit,
        ).to_dict()
        category = report["category"].get("category") or "none"
        lines = [
            render_kite_logo().rstrip(),
            "",
            f"{APP_NAME} Keyword Discovery",
            f"Category: {category}",
            f"Confidence: {report['confidence']['label']} ({report['confidence']['score']})",
            "",
            "Top keywords:",
        ]
        for index, item in enumerate(report["keywords"][: min(args.limit, 25)], 1):
            lines.append(
                f"{index:2}. {item['keyword']} "
                f"[{item['type']}, score={item['composite_score']}, priority={item['priority']}, confidence={item['confidence']}]"
            )
        lines.extend(_warning_lines(report["warnings"]))
        _emit(report, args, "\n".join(lines))
        return 0
    if args.command == "inspect":
        service = AppInspectionService()
        report = service.inspect(args.package_id, lang=args.lang, country=args.country).to_dict()
        lines = [
            render_kite_logo().rstrip(),
            "",
            f"{APP_NAME} App Inspect",
            f"Package: {report['app']['package_id']}",
            f"Title: {report['app']['title']}",
            f"Score: {report['scores'][0]['value'] if report['scores'] else 'n/a'}",
            f"Confidence: {report['confidence']['label']} ({report['confidence']['score']})",
        ]
        lines.extend(_warning_lines(report["warnings"]))
        _emit(report, args, "\n".join(lines))
        return 0
    if args.command == "rank":
        service = KeywordRankService()
        report = service.rank(
            RankConfig(
                keyword=args.keyword,
                target_package_id=args.package_id,
                lang=args.lang,
                country=args.country,
                limit=args.limit,
                save_history=not args.no_history,
            )
        ).to_dict()
        position = report["target_position"] if report["target_position"] is not None else "not found"
        lines = [
            render_kite_logo().rstrip(),
            "",
            f"{APP_NAME} Rank Check",
            f"Keyword: {report['keyword']}",
            f"Target: {report['target_package_id']}",
            f"Position: {position}",
            f"Confidence: {report['confidence']['label']} ({report['confidence']['score']})",
        ]
        lines.extend(_warning_lines(report["warnings"]))
        _emit(report, args, "\n".join(lines))
        return 0
    if args.command == "capabilities":
        audit = audit_capabilities()
        rows = audit["capabilities"]
        if args.area:
            rows = [row for row in rows if row["area"] == args.area]
        if args.status:
            rows = [row for row in rows if row["status"] == args.status]
        payload = {"summary": audit["summary"], "capabilities": rows}
        lines = [
            render_kite_logo().rstrip(),
            "",
            f"{APP_NAME} Capability Catalog",
            f"Total: {len(rows)}",
            f"Legal ready: {sum(1 for row in rows if row['legal_ready'])}",
            "",
            "Capabilities:",
        ]
        for row in rows:
            readiness = "ready" if row["legal_ready"] else "blocked"
            lines.append(f"- {row['priority']} {row['status']} {readiness}: {row['area']} / {row['name']}")
        _emit(payload, args, "\n".join(lines))
        return 0
    if args.command == "share-of-voice":
        options = ShareOfVoiceOptions(lang=args.lang, country=args.country, limit=args.limit)
        payload = KeywordIntelligenceService().share_of_voice(
            _parse_csv(args.keywords),
            args.package_id,
            _parse_csv(args.competitors),
            options=options,
        )
        _emit(payload, args, _simple_report_text("Share Of Voice", payload))
        return 0
    if args.command == "competitors":
        service = CompetitorIntelligenceService()
        if args.competitors_command == "add":
            payload = service.add(args.workspace, _parse_csv(args.package_ids))
        elif args.competitors_command == "remove":
            payload = service.remove(args.workspace, _parse_csv(args.package_ids))
        elif args.competitors_command == "list":
            workspace = WorkspaceService().get(args.workspace)
            payload = {
                "request_context": {"workspace": workspace.workspace_id, "sources": ["local_modeled_estimates"]},
                "competitors": workspace.competitors,
                "evidence": [],
                "warnings": [],
                "confidence": {"label": "high", "score": 95, "rationale": "Competitors are read from local workspace configuration."},
            }
        elif args.competitors_command == "gap":
            payload = service.gap(args.workspace, keywords=_parse_csv(args.keywords) or None, limit=args.limit)
        elif args.competitors_command == "timeline":
            payload = service.timeline(args.workspace)
        else:
            payload = service.creatives(args.workspace)
        _emit(payload, args, _simple_report_text("Competitors", payload))
        return 0
    if args.command == "audit" and args.audit_command == "metadata":
        payload = MetadataAuditService().audit(
            args.package_id,
            _parse_csv(args.keywords),
            lang=args.lang,
            country=args.country,
        )
        _emit(payload, args, _simple_report_text("Metadata Audit", payload))
        return 0
    if args.command == "reviews" and args.reviews_command == "analyze":
        payload = ReviewIntelligenceService().analyze(
            args.package_id,
            count=args.count,
            lang=args.lang,
            country=args.country,
        )
        _emit(payload, args, _simple_report_text("Review Intelligence", payload))
        return 0
    if args.workspace_command == "show":
        payload = service.get(args.workspace).to_dict()
        _emit(payload, args, _workspace_text(payload))
        return 0
    if args.workspace_command == "list":
        payload = {"workspaces": [item.to_dict() for item in service.list()]}
        _emit(payload, args, _workspace_list_text(payload))
        return 0
    if args.workspace_command == "baseline":
        payload = service.baseline(
            args.workspace,
            keyword_limit=args.keyword_limit,
            top_keywords=args.top_keywords,
            rank_limit=args.rank_limit,
            save_history=args.save_history,
        ).to_dict()
        _emit(payload, args, _workspace_baseline_text(payload))
        return 0
    return 1

def _handle_categories(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    payload = _categories_payload(args.category)
    _emit(payload, args, _categories_text(payload))
    return 0

def _handle_keywords(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.category and not args.seed:
        parser.error("keywords requires --category, --seed, or both")
    service = KeywordDiscoveryService()
    report = service.discover(
        seed_text=args.seed,
        category=args.category,
        lang=args.lang,
        country=args.country,
        limit=args.limit,
    ).to_dict()
    category = report["category"].get("category") or "none"
    lines = [
        render_kite_logo().rstrip(),
        "",
        f"{APP_NAME} Keyword Discovery",
        f"Category: {category}",
        f"Confidence: {report['confidence']['label']} ({report['confidence']['score']})",
        "",
        "Top keywords:",
    ]
    for index, item in enumerate(report["keywords"][: min(args.limit, 25)], 1):
        lines.append(
            f"{index:2}. {item['keyword']} "
            f"[{item['type']}, score={item['composite_score']}, priority={item['priority']}, confidence={item['confidence']}]"
        )
    lines.extend(_warning_lines(report["warnings"]))
    _emit(report, args, "\n".join(lines))
    return 0

def _handle_inspect(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    service = AppInspectionService()
    report = service.inspect(args.package_id, lang=args.lang, country=args.country).to_dict()
    lines = [
        render_kite_logo().rstrip(),
        "",
        f"{APP_NAME} App Inspect",
        f"Package: {report['app']['package_id']}",
        f"Title: {report['app']['title']}",
        f"Score: {report['scores'][0]['value'] if report['scores'] else 'n/a'}",
        f"Confidence: {report['confidence']['label']} ({report['confidence']['score']})",
    ]
    lines.extend(_warning_lines(report["warnings"]))
    _emit(report, args, "\n".join(lines))
    return 0

def _handle_rank(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    service = KeywordRankService()
    report = service.rank(
        args.keyword,
        args.package_id,
        lang=args.lang,
        country=args.country,
        limit=args.limit,
        save_history=not args.no_history,
    ).to_dict()
    position = report["target_position"] if report["target_position"] is not None else "not found"
    lines = [
        render_kite_logo().rstrip(),
        "",
        f"{APP_NAME} Rank Check",
        f"Keyword: {report['keyword']}",
        f"Target: {report['target_package_id']}",
        f"Position: {position}",
        f"Confidence: {report['confidence']['label']} ({report['confidence']['score']})",
    ]
    lines.extend(_warning_lines(report["warnings"]))
    _emit(report, args, "\n".join(lines))
    return 0

def _handle_capabilities(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    audit = audit_capabilities()
    rows = audit["capabilities"]
    if args.area:
        rows = [row for row in rows if row["area"] == args.area]
    if args.status:
        rows = [row for row in rows if row["status"] == args.status]
    payload = {"summary": audit["summary"], "capabilities": rows}
    lines = [
        render_kite_logo().rstrip(),
        "",
        f"{APP_NAME} Capability Catalog",
        f"Total: {len(rows)}",
        f"Legal ready: {sum(1 for row in rows if row['legal_ready'])}",
        "",
        "Capabilities:",
    ]
    for row in rows:
        readiness = "ready" if row["legal_ready"] else "blocked"
        lines.append(f"- {row['priority']} {row['status']} {readiness}: {row['area']} / {row['name']}")
    _emit(payload, args, "\n".join(lines))
    return 0

def _handle_share_of_voice(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    payload = KeywordIntelligenceService().share_of_voice(
        _parse_csv(args.keywords),
        args.package_id,
        _parse_csv(args.competitors),
        lang=args.lang,
        country=args.country,
        limit=args.limit,
    )
    _emit(payload, args, _simple_report_text("Share Of Voice", payload))
    return 0

def _handle_competitors(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    service = CompetitorIntelligenceService()
    if args.competitors_command == "add":
        payload = service.add(args.workspace, _parse_csv(args.package_ids))
    elif args.competitors_command == "remove":
        payload = service.remove(args.workspace, _parse_csv(args.package_ids))
    elif args.competitors_command == "list":
        workspace = WorkspaceService().get(args.workspace)
        payload = {
            "request_context": {"workspace": workspace.workspace_id, "sources": ["local_modeled_estimates"]},
            "competitors": workspace.competitors,
            "evidence": [],
            "warnings": [],
            "confidence": {"label": "high", "score": 95, "rationale": "Competitors are read from local workspace configuration."},
        }
    elif args.competitors_command == "gap":
        payload = service.gap(args.workspace, keywords=_parse_csv(args.keywords) or None, limit=args.limit)
    elif args.competitors_command == "timeline":
        payload = service.timeline(args.workspace)
    else:
        payload = service.creatives(args.workspace)
    _emit(payload, args, _simple_report_text("Competitors", payload))
    return 0

def _handle_audit(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.audit_command != "metadata":
        return 1
    payload = MetadataAuditService().audit(
        args.package_id,
        _parse_csv(args.keywords),
        lang=args.lang,
        country=args.country,
    )
    _emit(payload, args, _simple_report_text("Metadata Audit", payload))
    return 0

def _handle_reviews(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.reviews_command != "analyze":
        return 1
    payload = ReviewIntelligenceService().analyze(
        args.package_id,
        count=args.count,
        lang=args.lang,
        country=args.country,
    )
    _emit(payload, args, _simple_report_text("Review Intelligence", payload))
    return 0

def _handle_localization(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.localization_command != "audit":
        return 1
    payload = LocalizationAuditService().audit(
        args.package_id,
        _parse_csv(args.markets),
        _parse_csv(args.keywords),
    )
    _emit(payload, args, _simple_report_text("Localization Audit", payload))
    return 0

def _handle_ios(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.ios_command != "inspect":
        return 1
    payload = IOSInspectionService().inspect(args.identifier, country=args.country)
    _emit(payload, args, _simple_report_text("iOS Inspect", payload))
    return 0

def _handle_reports(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.reports_command != "export":
        return 1
    baseline = WorkspaceService().baseline(
        args.workspace,
        keyword_limit=args.keyword_limit,
        top_keywords=args.top_keywords,
        rank_limit=args.rank_limit,
        save_history=False,
    ).to_dict()
    payload = ReportExportService().export(baseline, Path(args.file), fmt=args.export_format)
    _emit(payload, args, _simple_report_text("Report Export", payload))
    return 0

def _handle_alerts(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    service = AlertService()
    if args.alerts_command not in {"list", "check"}:
        return 1
    payload = service.list() if args.alerts_command == "list" else service.check(args.keyword, args.package_id, drop_threshold=args.drop_threshold)
    _emit(payload, args, _simple_report_text("Alerts", payload))
    return 0

def _handle_sources(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.sources_command != "health":
        return 1
    payload = SourceHealthService().health()
    _emit(payload, args, _simple_report_text("Source Health", payload))
    return 0

def _handle_saas(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    run_saas_app(host=args.host, port=args.port)
    return 0

def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    custom_exit = _handle_nested_legacy_commands(raw_argv)
    if custom_exit is not None:
        return custom_exit
    parser = build_parser()
    args = parser.parse_args(raw_argv)

    handlers = {
        "doctor": _handle_doctor,
        "workspace": _handle_workspace,
        "categories": _handle_categories,
        "keywords": _handle_keywords,
        "discover-keywords": _handle_keywords,
        "discover": _handle_keywords,
        "inspect": _handle_inspect,
        "rank": _handle_rank,
        "capabilities": _handle_capabilities,
        "share-of-voice": _handle_share_of_voice,
        "competitors": _handle_competitors,
        "audit": _handle_audit,
        "reviews": _handle_reviews,
        "localization": _handle_localization,
        "ios": _handle_ios,
        "reports": _handle_reports,
        "alerts": _handle_alerts,
        "sources": _handle_sources,
        "saas": _handle_saas,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args, parser)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
