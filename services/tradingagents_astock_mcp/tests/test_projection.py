from tradingagents_astock_mcp.worker import stable_projection


def test_projection_keeps_only_stable_public_fields():
    raw = {
        "company_of_interest": "600519",
        "trade_date": "2026-01-05",
        "market_report": "market",
        "policy_report": "policy",
        "fundamentals_report": "   ",
        "data_quality_summary": "quality gate passed with caveats",
        "investment_debate_state": {"judge_decision": "judge", "history": "private debate"},
        "risk_debate_state": {"judge_decision": "risk", "history": "private risk debate"},
        "trader_investment_plan": "trader",
        "investment_plan": "plan",
        "final_trade_decision": "final",
        "messages": ["raw graph message"],
        "api_key": "must-not-leak",
        "backend_url": "must-not-leak",
    }
    projected = stable_projection(raw, "Hold", ["market", "policy", "fundamentals", "news"])
    assert projected == {
        "schema_version": 1,
        "upstream_version": "0.2.21",
        "company_of_interest": "600519",
        "trade_date": "2026-01-05",
        "signal": "Hold",
        "analyst_reports": {"market": "market", "policy": "policy"},
        "data_quality_summary": "quality gate passed with caveats",
        "warnings": [
            "Missing or empty report for selected analyst: fundamentals",
            "Missing or empty report for selected analyst: news",
        ],
        "investment_debate_judgment": "judge",
        "trader_investment_plan": "trader",
        "risk_debate_judgment": "risk",
        "investment_plan": "plan",
        "final_trade_decision": "final",
    }
    assert "must-not-leak" not in str(projected)
    assert "private debate" not in str(projected)
