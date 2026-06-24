"""Validate AI Berkshire exports against OpenClaw-facing profiles.

This module intentionally uses only the Python standard library.  It is a
contract helper for AI Berkshire artifacts; OpenClaw remains the authority for
runtime import, health checks, daily committee inclusion, and degraded state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping


VALID_STATUSES = {"healthy", "degraded", "critical"}
VALID_CONFIDENCE = {"low", "medium", "high"}

REQUIRED_EARNINGS_SECTIONS = {
    "今日财报主线",
    "最值得关注的公司",
    "继续观察的公司",
    "需要回避的公司",
    "1-4 周走势判断",
    "证据缺口",
}

LONGBRIDGE_SOURCE_TOKENS = (
    "longbridge",
    "longbridge_filing",
    "longbridge_financial_report",
    "longbridge_financial_report_latest",
    "longbridge_consensus",
    "longbridge_calendar",
)


@dataclass
class ValidationResult:
    """Profile validation result with downgrade semantics."""

    ok: bool
    status: str
    errors: List[str]
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _is_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def _nested(payload: Mapping[str, Any], dotted: str) -> Any:
    current: Any = payload
    for part in dotted.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _field_present(payload: Mapping[str, Any], dotted: str) -> bool:
    current: Any = payload
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False
        current = current[part]
    if current is None:
        return False
    if isinstance(current, str) and not current.strip():
        return False
    return True


def _require_fields(payload: Mapping[str, Any], fields: Iterable[str]) -> List[str]:
    missing = []
    for field in fields:
        if not _field_present(payload, field):
            missing.append(field)
    return missing


def _worst_status(*statuses: str) -> str:
    rank = {"healthy": 0, "degraded": 1, "critical": 2}
    clean = [status if status in rank else "degraded" for status in statuses if status]
    if not clean:
        return "healthy"
    return max(clean, key=lambda item: rank[item])


def _source_tokens_from_value(value: Any) -> List[str]:
    tokens: List[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if "source" in str(key).lower():
                tokens.append(str(child).lower())
            tokens.extend(_source_tokens_from_value(child))
    elif isinstance(value, list):
        for child in value:
            tokens.extend(_source_tokens_from_value(child))
    elif isinstance(value, str):
        lowered = value.lower()
        if "source" in lowered or "longbridge" in lowered or "yfinance" in lowered:
            tokens.append(lowered)
    return tokens


def has_longbridge_provenance(payload: Mapping[str, Any]) -> bool:
    """Return True when earnings targets preserve Longbridge provenance."""

    coverage = _as_dict(payload.get("coverage"))
    source_counts = _as_dict(coverage.get("source_counts"))
    for key, value in source_counts.items():
        if any(token in str(key).lower() for token in LONGBRIDGE_SOURCE_TOKENS) and int(value or 0) > 0:
            return True

    for row in _as_list(payload.get("analyzed_targets")):
        target = _as_dict(row)
        provenance = _as_list(target.get("evidence_provenance"))
        for token in _source_tokens_from_value(provenance):
            if any(source_token in token for source_token in LONGBRIDGE_SOURCE_TOKENS):
                return True
    return False


def validate_common_envelope(payload: Mapping[str, Any]) -> ValidationResult:
    """Validate the common AI Berkshire -> OpenClaw export envelope."""

    required = [
        "schema_version",
        "generated_at",
        "source_repo",
        "source_report",
        "artifact_type",
        "status",
        "confidence",
        "market_thesis",
    ]
    errors = [f"missing:{field}" for field in _require_fields(payload, required)]
    warnings: List[str] = []
    status = str(payload.get("status") or "").strip().lower()
    confidence = str(payload.get("confidence") or "").strip().lower()

    if status and status not in VALID_STATUSES:
        errors.append(f"invalid_status:{status}")
    if confidence and confidence not in VALID_CONFIDENCE:
        errors.append(f"invalid_confidence:{confidence}")
    if str(payload.get("source_repo") or "") != "ai-berkshire":
        errors.append("source_repo_must_be_ai-berkshire")
    if not _as_dict(payload.get("validation_summary")):
        warnings.append("validation_summary_empty")

    result_status = "critical" if errors else _worst_status(status or "degraded", "degraded" if warnings else "healthy")
    return ValidationResult(ok=not errors, status=result_status, errors=errors, warnings=warnings)


def validate_ai_bottleneck_research(payload: Mapping[str, Any]) -> ValidationResult:
    required = [
        "generated_at",
        "status",
        "coverage.symbols_total",
        "coverage.symbols_with_order_evidence",
        "coverage.symbols_with_margin_cashflow",
        "coverage.source_count",
        "market_thesis",
        "bottleneck_lanes",
        "top_targets",
        "watch_targets",
        "avoid_targets",
    ]
    errors = [f"missing:{field}" for field in _require_fields(payload, required)]
    warnings: List[str] = []
    coverage = _as_dict(payload.get("coverage"))
    top_targets = _as_list(payload.get("top_targets"))

    symbols_total = int(coverage.get("symbols_total") or 0)
    source_count = int(coverage.get("source_count") or 0)
    if symbols_total < 20:
        errors.append("coverage.symbols_total_lt_20")
    if source_count < 3:
        warnings.append("coverage.source_count_lt_3")
    if len(top_targets) < 3:
        warnings.append("top_targets_lt_3")

    missing_evidence = []
    for item in top_targets[:5]:
        row = _as_dict(item)
        evidence = _as_dict(row.get("evidence"))
        has_demand = bool(evidence.get("orders") or evidence.get("customers"))
        has_financial_quality = bool(evidence.get("margin") or evidence.get("cashflow"))
        if not (has_demand and has_financial_quality):
            missing_evidence.append(str(row.get("display_name") or row.get("symbol") or "unknown"))
    if missing_evidence:
        warnings.append("top_target_evidence_incomplete:" + ",".join(missing_evidence[:5]))

    status = "critical" if errors else ("degraded" if warnings else str(payload.get("status") or "healthy"))
    return ValidationResult(ok=not errors, status=_worst_status(status), errors=errors, warnings=warnings)


def validate_commodity_real_assets_research(payload: Mapping[str, Any]) -> ValidationResult:
    required = [
        "generated_at",
        "status",
        "coverage.tracked_symbols",
        "coverage.data_ok",
        "coverage.missing_symbols",
        "market_thesis",
        "macro_view",
        "asset_metrics",
        "focus_targets",
        "top_targets",
        "watch_targets",
    ]
    errors = [f"missing:{field}" for field in _require_fields(payload, required)]
    warnings: List[str] = []
    coverage = _as_dict(payload.get("coverage"))
    macro_view = _as_dict(payload.get("macro_view"))
    asset_metrics = _as_dict(payload.get("asset_metrics"))
    focus_targets = _as_list(payload.get("focus_targets"))

    if int(coverage.get("data_ok") or 0) < 8:
        errors.append("coverage.data_ok_lt_8")
    if _as_list(coverage.get("missing_symbols")):
        warnings.append("coverage.missing_symbols_nonempty")
    if not str(macro_view.get("regime") or "").strip():
        warnings.append("macro_view.regime_empty")
    if len(focus_targets) < 3:
        warnings.append("focus_targets_lt_3")

    thesis = str(payload.get("market_thesis") or "").lower()
    claims_copper = "铜" in thesis or "copper" in thesis
    if claims_copper and not any(symbol in asset_metrics for symbol in ("HG=F", "CPER")):
        warnings.append("copper_proxy_missing")

    status = "critical" if errors else ("degraded" if warnings else str(payload.get("status") or "healthy"))
    return ValidationResult(ok=not errors, status=_worst_status(status), errors=errors, warnings=warnings)


def validate_earnings_season_research(payload: Mapping[str, Any]) -> ValidationResult:
    required = [
        "generated_at",
        "status",
        "coverage.universe_size",
        "coverage.analyzed_count",
        "coverage.source_counts",
        "coverage.evidence_rows",
        "market_thesis",
        "selection_reason",
        "source_health",
        "analyzed_targets",
        "report_sections",
    ]
    errors = [f"missing:{field}" for field in _require_fields(payload, required)]
    warnings: List[str] = []
    coverage = _as_dict(payload.get("coverage"))
    report_sections = _as_dict(payload.get("report_sections"))
    source_health = _as_dict(payload.get("source_health"))

    if int(coverage.get("evidence_rows") or 0) < 4:
        errors.append("coverage.evidence_rows_lt_4")

    missing_sections = sorted(REQUIRED_EARNINGS_SECTIONS.difference(report_sections.keys()))
    if missing_sections:
        errors.append("report_sections_missing:" + ",".join(missing_sections))

    if str(source_health.get("status") or "").strip().lower() == "degraded":
        warnings.append("source_health_degraded")
    if not has_longbridge_provenance(payload):
        warnings.append("longbridge_provenance_missing")

    source_tokens = _source_tokens_from_value(payload)
    has_yfinance = any("yfinance" in token for token in source_tokens)
    if has_yfinance and not has_longbridge_provenance(payload):
        warnings.append("yfinance_only_or_primary")

    status = "critical" if errors else ("degraded" if warnings else str(payload.get("status") or "healthy"))
    return ValidationResult(ok=not errors, status=_worst_status(status), errors=errors, warnings=warnings)


PROFILE_VALIDATORS = {
    "ai_bottleneck_research": validate_ai_bottleneck_research,
    "commodity_real_assets_research": validate_commodity_real_assets_research,
    "earnings_season_research": validate_earnings_season_research,
}


def validate_profile(profile: str, payload: Mapping[str, Any]) -> ValidationResult:
    validator = PROFILE_VALIDATORS.get(profile)
    if validator is None:
        return ValidationResult(
            ok=False,
            status="critical",
            errors=[f"unknown_profile:{profile}"],
            warnings=[],
        )
    return validator(payload)


def apply_validation_status(payload: MutableMapping[str, Any], result: ValidationResult) -> None:
    payload["status"] = _worst_status(str(payload.get("status") or "healthy"), result.status)
    payload["profile_validation"] = result.to_dict()
    if result.errors or result.warnings:
        reasons = list(payload.get("degrade_reasons") or [])
        reasons.extend(result.errors)
        reasons.extend(result.warnings)
        payload["degrade_reasons"] = list(dict.fromkeys(str(item) for item in reasons if str(item).strip()))
