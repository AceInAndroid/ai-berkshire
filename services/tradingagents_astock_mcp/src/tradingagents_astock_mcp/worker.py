from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from .config import UPSTREAM_VERSION
from .models import ResearchRequest

_REPORT_FIELDS = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
    "policy": "policy_report",
    "hot_money": "hot_money_report",
    "lockup": "lockup_report",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def stable_projection(
    final_state: dict[str, Any],
    signal: Any,
    selected_analysts: list[str] | None = None,
) -> dict[str, Any]:
    """Project untrusted/upstream state onto the adapter's versioned public schema."""
    selected = selected_analysts or list(_REPORT_FIELDS)
    reports = {
        public_name: _text(final_state.get(upstream_name))
        for public_name, upstream_name in _REPORT_FIELDS.items()
        if public_name in selected
        and _text(final_state.get(upstream_name)).strip()
    }
    warnings = [
        f"Missing or empty report for selected analyst: {analyst}"
        for analyst in selected
        if analyst not in reports
    ]
    investment_debate = final_state.get("investment_debate_state")
    risk_debate = final_state.get("risk_debate_state")
    return {
        "schema_version": 1,
        "upstream_version": UPSTREAM_VERSION,
        "company_of_interest": _text(final_state.get("company_of_interest")),
        "trade_date": _text(final_state.get("trade_date")),
        "signal": _text(signal),
        "analyst_reports": reports,
        "data_quality_summary": _text(final_state.get("data_quality_summary")),
        "warnings": warnings,
        "investment_debate_judgment": _text(
            investment_debate.get("judge_decision") if isinstance(investment_debate, dict) else None
        ),
        "trader_investment_plan": _text(final_state.get("trader_investment_plan")),
        "risk_debate_judgment": _text(
            risk_debate.get("judge_decision") if isinstance(risk_debate, dict) else None
        ),
        "investment_plan": _text(final_state.get("investment_plan")),
        "final_trade_decision": _text(final_state.get("final_trade_decision")),
    }


def build_upstream_config(run_dir: Path, request: ResearchRequest) -> dict[str, Any]:
    """Build a per-run config. No user-supplied configuration is accepted."""
    from tradingagents.default_config import DEFAULT_CONFIG

    config = copy.deepcopy(DEFAULT_CONFIG)
    isolated = run_dir.resolve() / "upstream"
    config["results_dir"] = str(isolated / "results")
    config["data_cache_dir"] = str(isolated / "cache")
    config["memory_log_path"] = str(isolated / "memory" / "trading_memory.md")
    config["checkpoint_enabled"] = False
    config["max_debate_rounds"] = request.research_depth
    config["max_risk_discuss_rounds"] = request.research_depth
    config["data_vendors"] = {
        "core_stock_apis": "a_stock",
        "technical_indicators": "a_stock",
        "fundamental_data": "a_stock",
        "news_data": "a_stock",
        "signal_data": "a_stock",
    }

    env_overrides = {
        "llm_provider": os.getenv("TRADINGAGENTS_LLM_PROVIDER"),
        "deep_think_llm": os.getenv("TRADINGAGENTS_DEEP_MODEL"),
        "quick_think_llm": os.getenv("TRADINGAGENTS_QUICK_MODEL"),
        "backend_url": os.getenv("TRADINGAGENTS_BACKEND_URL"),
        "output_language": os.getenv("TRADINGAGENTS_OUTPUT_LANGUAGE"),
    }
    for key, value in env_overrides.items():
        if value is not None and value.strip():
            config[key] = value.strip()
    return config


def run_upstream(request: ResearchRequest, run_dir: Path) -> dict[str, Any]:
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    config = build_upstream_config(run_dir, request)
    graph = TradingAgentsGraph(
        selected_analysts=list(request.analysts),
        debug=False,
        config=config,
    )
    final_state, signal = graph.propagate(request.ticker, request.trade_date)
    return stable_projection(final_state, signal, list(request.analysts))


def execute_request_file(request_path: Path, result_path: Path) -> None:
    request = ResearchRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    result = run_upstream(request, request_path.resolve().parent)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
