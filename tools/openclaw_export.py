#!/usr/bin/env python3
"""Export AI Berkshire reports into OpenClaw-compatible artifact bundles."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from openclaw.profile_validators import (  # noqa: E402
    apply_validation_status,
    validate_common_envelope,
    validate_profile,
)

OPENCLAW_WORLD_MODEL = Path("/Users/bingzhang/clawd/myclaw-repo/data/world_model").resolve()
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "openclaw_exports"
SCHEMA_VERSION = "ai-berkshire-openclaw-export-v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _safe_slug(value: str) -> str:
    text = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "-", value.strip(), flags=re.UNICODE)
    return text.strip("-") or "openclaw-export"


def _resolve_report(path_text: str) -> Path:
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    path = path.resolve()
    if not path.exists():
        raise SystemExit(f"report not found: {path}")
    if not path.is_file():
        raise SystemExit(f"report is not a file: {path}")
    return path


def _ensure_safe_output_dir(path_text: str | None) -> Path:
    path = Path(path_text).expanduser() if path_text else DEFAULT_OUTPUT_DIR
    if not path.is_absolute():
        path = REPO_ROOT / path
    resolved = path.resolve()
    try:
        resolved.relative_to(OPENCLAW_WORLD_MODEL)
    except ValueError:
        return resolved
    raise SystemExit(
        "phase 1 exporter refuses to write under OpenClaw world_model: "
        f"{resolved}"
    )


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _section_text(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start < 0:
        return ""
    rest = text[start + len(marker):]
    next_match = re.search(r"\n##\s+", rest)
    if next_match:
        rest = rest[: next_match.start()]
    return rest.strip()


def _extract_bullets(section: str, limit: int = 6) -> List[str]:
    rows = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            rows.append(stripped[2:].strip())
        if len(rows) >= limit:
            break
    return rows


def _extract_report_summary(text: str) -> Dict[str, Any]:
    conclusion = _section_text(text, "一句话结论")
    data_section = _section_text(text, "关键数据与交叉验证记录")
    risks = _extract_bullets(_section_text(text, "风险") or _section_text(text, "风险与判断"), limit=8)
    unresolved = _extract_bullets(_section_text(text, "数据来源与未解决问题"), limit=8)
    return {
        "title": _first_heading(text),
        "conclusion": conclusion[:1200],
        "data_section_present": bool(data_section),
        "risk_bullets": risks,
        "unresolved_items": unresolved,
    }


def _base_status(summary: Dict[str, Any]) -> str:
    if not summary.get("data_section_present"):
        return "degraded"
    if summary.get("unresolved_items"):
        return "degraded"
    return "healthy"


def _confidence(status: str, summary: Dict[str, Any]) -> str:
    if status == "critical":
        return "low"
    if status == "degraded":
        return "medium" if summary.get("data_section_present") else "low"
    return "high"


def _build_company_payload(args: argparse.Namespace, report: Path, text: str) -> Dict[str, Any]:
    summary = _extract_report_summary(text)
    status = _base_status(summary)
    generated_at = _now_iso()
    target = {
        "symbol": args.symbol,
        "display_name": args.company_name or args.symbol,
        "market": args.market,
        "action": "跟踪",
        "why": summary["conclusion"][:300],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_repo": "ai-berkshire",
        "source_report": str(report),
        "report_path": str(report),
        "artifact_type": args.research_type,
        "skill": args.skill,
        "company_name": args.company_name,
        "symbol": args.symbol,
        "market": args.market,
        "topic": args.topic or args.company_name or args.symbol,
        "status": status,
        "confidence": _confidence(status, summary),
        "degrade_reasons": [] if status == "healthy" else ["report_has_unresolved_items_or_missing_data_section"],
        "source_health": {
            "status": status,
            "notes": summary.get("unresolved_items") or [],
        },
        "validation_summary": {
            "report_data_section_present": summary.get("data_section_present"),
            "report_audit_required": True,
            "tooling": ["tools/report_audit.py", "tools/financial_rigor.py"],
        },
        "thesis_verdict": "有条件通过" if "有条件通过" in text else "",
        "one_to_four_week_view": "",
        "market_thesis": summary["conclusion"] or summary["title"],
        "top_targets": [target],
        "watch_targets": [target],
        "avoid_targets": [],
        "evidence_gaps": summary.get("unresolved_items") or [],
        "report_sections": {
            "一句话结论": [summary["conclusion"]] if summary["conclusion"] else [],
            "风险提示": summary.get("risk_bullets") or [],
            "证据缺口": summary.get("unresolved_items") or [],
        },
        "coverage": {
            "universe_size": 1,
            "analyzed_count": 1,
            "source_counts": {},
            "evidence_rows": 1 if summary.get("data_section_present") else 0,
        },
        "openclaw_targets": [args.target_profile] if args.target_profile else ["company_research"],
    }


def export_report(args: argparse.Namespace) -> Dict[str, Any]:
    report = _resolve_report(args.report)
    output_dir = _ensure_safe_output_dir(args.output_dir)
    text = _read_text(report)
    payload = _build_company_payload(args, report, text)

    common = validate_common_envelope(payload)
    if common.errors:
        apply_validation_status(payload, common)
    else:
        payload["common_validation"] = common.to_dict()

    if args.target_profile:
        profile_result = validate_profile(args.target_profile, payload)
        apply_validation_status(payload, profile_result)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _safe_slug(f"{args.company_name or args.symbol}-{args.research_type}-{stamp}")
    json_path = output_dir / f"{slug}.json"
    latest_path = output_dir / f"{_safe_slug(args.research_type)}_latest.json"
    payload["json_path"] = str(json_path)
    payload["latest_path"] = str(latest_path)

    _write_json(json_path, payload)
    _write_json(latest_path, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export AI Berkshire report for OpenClaw phase 1 ingestion.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--market", required=True)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--research-type", required=True)
    parser.add_argument("--target-profile", choices=[
        "ai_bottleneck_research",
        "commodity_real_assets_research",
        "earnings_season_research",
    ])
    parser.add_argument("--topic", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = export_report(args)
    print(json.dumps({
        "ok": True,
        "status": payload.get("status"),
        "json_path": payload.get("json_path"),
        "latest_path": payload.get("latest_path"),
        "profile_validation": payload.get("profile_validation"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
