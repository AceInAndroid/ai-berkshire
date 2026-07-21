from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Severity(StrEnum):
    INFO = "info"
    WATCH = "watch"
    ACTION = "action"
    RISK = "risk"
    EMERGENCY = "emergency"


class SignalStatus(StrEnum):
    WATCH = "watch"
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    REDUCE = "reduce"


class MarketRegime(StrEnum):
    DELEVERAGING = "DELEVERAGING"
    STABILIZING = "STABILIZING"
    RECOVERING = "RECOVERING"
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"


class TransactionType(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    DIVIDEND = "DIVIDEND"
    FEE = "FEE"


class InstrumentConfig(BaseModel):
    symbol: str
    name: str
    module: str
    target_amount_cny: float = 0
    role: str
    alternative_for: str | None = None
    anchors: dict[str, float] = Field(default_factory=dict)


class ModuleConfig(BaseModel):
    name: str
    target_weight: float
    target_amount_cny: float
    hard_cap_weight: float


class TechnologyStage(BaseModel):
    stage: int
    name: str
    cumulative_amount_cny: float
    allocations: dict[str, float]
    minimum_conditions: int | None = None


class RuntimeConfig(BaseModel):
    timezone: str = "Asia/Shanghai"
    stale_after_minutes: int = 10
    cross_source_max_deviation: float = 0.005
    alert_cooldown_minutes: int = 30
    http_host: str = "127.0.0.1"
    http_port: int = 8765
    streamable_http_path: str = "/mcp"


class CostConfig(BaseModel):
    commission_rate: float = 0.0003
    minimum_commission_cny: float = 5
    slippage_rate: float = 0.0005
    stamp_duty_rate: float = 0
    annual_cash_yield: float = 0.012


class PortfolioConfig(BaseModel):
    version: str
    name: str
    source_document: str
    initial_capital_cny: float
    base_currency: str
    equity_weight_cap: float
    technology_weight_cap: float
    shadow_mode_days: int = 5
    initial_authorization: dict[str, dict[str, Any]]
    runtime: RuntimeConfig
    costs: CostConfig
    modules: dict[str, ModuleConfig]
    instruments: list[InstrumentConfig]
    technology_stages: list[TechnologyStage]
    technology_risk: dict[str, float]
    portfolio_drawdown_ladder: list[dict[str, Any]]
    market_recovery_conditions: dict[str, Any]
    external_indicators: list[dict[str, str]]

    def instrument_map(self) -> dict[str, InstrumentConfig]:
        return {item.symbol: item for item in self.instruments}


class Quote(BaseModel):
    symbol: str
    price: float
    previous_close: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    amount: float | None = None
    change_pct: float | None = None
    source: str
    market_time: datetime
    fetched_at: datetime
    currency: str = "CNY"
    delayed: bool = False
    degraded: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class Bar(BaseModel):
    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float = 0
    amount: float = 0
    source: str


class IndicatorSnapshot(BaseModel):
    symbol: str
    data_as_of: datetime
    price: float
    change_pct: float | None = None
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    high20: float | None = None
    low20: float | None = None
    return5: float | None = None
    return20: float | None = None
    volume_ratio20: float | None = None
    volatility20: float | None = None
    volatility60: float | None = None
    trend: Literal["rising", "falling", "flat", "unknown"] = "unknown"
    stale: bool = False
    cross_source_deviation: float | None = None
    data_quality: Literal["verified", "single_source", "degraded", "stale", "conflict"] = "single_source"


class MarketContext(BaseModel):
    data_as_of: datetime
    shanghai_return: float = 0
    csi300_return: float = 0
    csi500_return: float = 0
    csi1000_return: float = 0
    chinext_return: float = 0
    star50_return: float = 0
    advances: int = 0
    declines: int = 0
    limit_down_count: int = 0
    median_return: float = 0
    semiconductor_median_return: float | None = None
    semiconductor_breadth: float | None = None
    turnover_cny: float | None = None
    margin_balance_change: float | None = None
    technology_etf_inflow_two_days: bool = False
    advances_exceed_declines_two_days: bool = False
    median_positive_two_days: bool = False
    csi1000_stops_new_low: bool = False
    growth_outperformance_days: int = 0
    technology_volume_healthy: bool = False
    margin_stabilized: bool = False
    equipment_leaders_confirmed: int = 0
    equipment_inflow_two_days: bool = False
    previous_regime: MarketRegime | None = None


class MarketRegimeResult(BaseModel):
    regime: MarketRegime
    score: int
    evidence: list[str]
    risk_evidence: list[str]
    data_as_of: datetime
    deleveraging_continues: bool = False


class Position(BaseModel):
    symbol: str
    quantity: float
    average_cost: float
    market_price: float = 0
    market_value: float = 0
    realized_pnl: float = 0
    unrealized_pnl: float = 0
    module: str | None = None


class PortfolioSnapshot(BaseModel):
    data_as_of: datetime
    total_assets: float
    cash: float
    positions_value: float
    realized_pnl: float
    unrealized_pnl: float
    total_return: float
    drawdown: float
    equity_weight: float
    technology_weight: float
    module_values: dict[str, float]
    module_weights: dict[str, float]
    positions: list[Position]


class Recommendation(BaseModel):
    status: SignalStatus
    severity: Severity
    module: str
    symbol: str | None = None
    rule_id: str
    max_amount_cny: float = 0
    evidence: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    invalidation: list[str] = Field(default_factory=list)
    data_as_of: datetime
    config_version: str


class TransactionInput(BaseModel):
    transaction_type: TransactionType
    symbol: str | None = None
    quantity: float = 0
    price: float = 0
    fees: float = 0
    traded_at: datetime
    idempotency_key: str
    notes: str | None = None


class AlertRecord(BaseModel):
    id: int | None = None
    dedup_key: str
    rule_id: str
    symbol: str | None = None
    module: str
    severity: Severity
    status: str = "open"
    message: str
    payload: dict[str, Any]
    first_triggered_at: datetime
    last_triggered_at: datetime
    acknowledged_at: datetime | None = None
    snoozed_until: datetime | None = None
    delivery_status: str = "pending"


class BacktestRequest(BaseModel):
    start_date: date
    end_date: date
    initial_capital_cny: float = 1_000_000
    use_index_proxies: bool = False


class BacktestResult(BaseModel):
    run_id: str
    status: str
    start_date: date
    end_date: date
    metrics: dict[str, float]
    comparisons: dict[str, dict[str, float]]
    trades: list[dict[str, Any]]
    stage_changes: list[dict[str, Any]]
    equity_curve: list[dict[str, Any]]
    warnings: list[str] = Field(default_factory=list)
