from portfolio_monitor.models import MarketRegime, SignalStatus
from portfolio_monitor.rules import RuleEngine

from conftest import snapshot, technology_indicators, weak_context


def regime(engine, context):
    return engine.classify_market(context)


def test_support_break_blocks_beta(config):
    engine = RuleEngine(config)
    indicators = technology_indicators(**{"159995.SZ": 1.14})
    signals = engine.beta_signals(snapshot(), indicators, weak_context(), regime(engine, weak_context()))
    assert signals[0].rule_id == "technology_support_break"
    assert signals[0].status == SignalStatus.BLOCKED
    assert all(item.status != SignalStatus.ELIGIBLE for item in signals)


def test_stage2_requires_three_of_seven_conditions(config):
    engine = RuleEngine(config)
    indicators = technology_indicators()
    context = weak_context(limit_down_count=50, advances_exceed_declines_two_days=True, median_positive_two_days=False)
    ok, evidence, blockers = engine._stage_eligibility(2, indicators, context, regime(engine, context), 25_000)
    assert ok is True
    assert len(evidence) >= 3  # limit-down + chip confirmation + communication confirmation
    assert blockers == []
    context = weak_context(limit_down_count=150, advances_exceed_declines_two_days=False)
    indicators = technology_indicators(**{"159995.SZ": 1.20, "515050.SH": 1.02})
    ok, _, blockers = engine._stage_eligibility(2, indicators, context, regime(engine, context), 25_000)
    assert ok is False
    assert "Stage 2" in blockers[0]


def test_beta_drawdown_ladders(config):
    engine = RuleEngine(config)
    indicators = technology_indicators()
    context = weak_context()
    stopped = engine.beta_signals(snapshot(technology_value=91_900, technology_cost=100_000), indicators, context, regime(engine, context))
    assert stopped[0].status == SignalStatus.BLOCKED
    assert stopped[0].rule_id == "technology_drawdown_stop_add"
    reduced = engine.beta_signals(snapshot(technology_value=87_900, technology_cost=100_000), indicators, context, regime(engine, context))
    assert reduced[0].status == SignalStatus.REDUCE
    assert "三分之一" in reduced[0].blocking_reasons[0]


def test_equipment_is_last_and_requires_all_confirmations(config):
    engine = RuleEngine(config)
    context = weak_context(limit_down_count=20, equipment_inflow_two_days=False, equipment_leaders_confirmed=1)
    signals = engine.beta_signals(snapshot(technology_value=115_000), technology_indicators(), context, regime(engine, context))
    equipment = next(item for item in signals if item.symbol == "159516.SZ")
    assert equipment.status == SignalStatus.BLOCKED
    assert "Stage 4" in equipment.blocking_reasons[0]


def test_portfolio_drawdown_16_percent_reduces_equity_cap(config):
    recommendation = RuleEngine(config).portfolio_risk(snapshot(drawdown=0.161))
    assert recommendation.status == SignalStatus.REDUCE
    assert "权益授权上限降至25%" in recommendation.blocking_reasons


def test_stale_data_blocks_action(config):
    engine = RuleEngine(config)
    indicators = technology_indicators()
    indicators["159995.SZ"] = indicators["159995.SZ"].model_copy(update={"stale": True, "data_quality": "stale"})
    context = weak_context()
    signals = engine.beta_signals(snapshot(), indicators, context, regime(engine, context))
    assert signals[0].rule_id == "technology_data_quality"
    assert signals[0].status == SignalStatus.BLOCKED
