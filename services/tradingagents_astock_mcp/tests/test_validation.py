from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from tradingagents_astock_mcp.models import ResearchRequest
from tradingagents_astock_mcp.config import Settings
from tradingagents_astock_mcp.service import ResearchService
from tradingagents_astock_mcp.store import RunStore


@pytest.mark.parametrize(
    ("ticker", "normalized"),
    [
        ("600519", "600519"),
        ("600519.SH", "600519"),
        ("000001.SZ", "000001"),
        ("430047.BJ", "430047"),
        (" 600519.sh ", "600519"),
    ],
)
def test_canonical_astock_tickers_are_normalized(ticker, normalized):
    request = ResearchRequest(ticker=ticker, trade_date="2026-01-05")
    assert request.ticker == normalized


@pytest.mark.parametrize("ticker", ["../../etc", "600519/..", "SH600519", "60051", "6005190"])
def test_ticker_rejects_unsafe_or_non_astock_values(ticker):
    with pytest.raises(ValidationError):
        ResearchRequest(ticker=ticker, trade_date="2026-01-05")


@pytest.mark.parametrize("ticker", ["600519.SZ", "000001.SH", "300750.BJ", "430047.SH"])
def test_ticker_rejects_mismatched_exchange_suffix(ticker):
    with pytest.raises(ValidationError, match="does not match code family"):
        ResearchRequest(ticker=ticker, trade_date="2026-01-05")


def test_request_forbids_config_credentials_and_invalid_catalog():
    with pytest.raises(ValidationError):
        ResearchRequest.model_validate(
            {
                "ticker": "600519",
                "trade_date": "2026-01-05",
                "analysts": ["market", "hacker"],
                "research_depth": 2,
                "api_key": "secret",
                "base_url": "https://example.invalid",
            }
        )


def test_date_and_duplicate_analysts_are_rejected():
    future = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError):
        ResearchRequest(ticker="600519", trade_date=future)
    with pytest.raises(ValidationError):
        ResearchRequest(ticker="600519", trade_date="2026-01-05", analysts=["market", "market"])


def test_run_id_cannot_traverse_store(tmp_path):
    store = RunStore(tmp_path)
    with pytest.raises(ValueError, match="invalid run_id"):
        store.get("../../outside")


def test_codex_native_plan_needs_no_provider_and_discloses_execution_boundary(tmp_path):
    service = ResearchService(Settings(data_dir=tmp_path))
    plan = service.prepare_codex_native("600519.SH", "2026-01-05", ["market", "fundamentals"], 3)
    assert plan["execution_mode"] == "codex_native"
    assert plan["requires_external_llm_credentials"] is False
    assert plan["upstream_graph_executed"] is False
    assert plan["request"]["ticker"] == "600519"
    assert [role["name"] for role in plan["workflow"]["evidence_roles"]] == [
        "fundamentals",
        "market_flow",
        "news_policy_events",
    ]
    assert "original upstream TradingAgentsGraph is not executed" in plan["disclosure"]
