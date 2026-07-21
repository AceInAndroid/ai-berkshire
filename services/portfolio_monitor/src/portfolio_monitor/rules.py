from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from .models import (
    IndicatorSnapshot,
    MarketContext,
    MarketRegime,
    MarketRegimeResult,
    PortfolioConfig,
    PortfolioSnapshot,
    Recommendation,
    Severity,
    SignalStatus,
)


SEVERITY_ORDER = {Severity.INFO: 0, Severity.WATCH: 1, Severity.ACTION: 2, Severity.RISK: 3, Severity.EMERGENCY: 4}


class RuleEngine:
    def __init__(self, config: PortfolioConfig):
        self.config = config
        self.instruments = config.instrument_map()

    def classify_market(self, context: MarketContext) -> MarketRegimeResult:
        evidence: list[str] = []
        risk: list[str] = []
        conditions = [
            (context.limit_down_count < 100, f"跌停家数{context.limit_down_count}<100"),
            (context.advances_exceed_declines_two_days, "连续两日上涨家数多于下跌家数"),
            (context.median_positive_two_days, "市场中位数连续两日为正"),
            (context.csi1000_stops_new_low and context.csi1000_return > context.csi300_return, "中证1000止跌并跑赢沪深300"),
            (context.growth_outperformance_days >= 3, "成长指数五日内至少三日跑赢沪深300"),
            ((context.semiconductor_breadth or 0) >= 0.50, "半导体上涨家数占比超过50%"),
            (context.technology_volume_healthy, "科技上涨放量、回调缩量"),
            (context.margin_stabilized and context.technology_etf_inflow_two_days, "两融企稳且科技ETF连续流入"),
        ]
        for matched, text in conditions:
            if matched:
                evidence.append(text)
        if context.limit_down_count >= 200:
            risk.append(f"跌停家数{context.limit_down_count}>=200")
        if context.median_return < -1:
            risk.append(f"市场中位数{context.median_return:.2f}%显著为负")
        if context.declines > context.advances * 2 and context.advances > 0:
            risk.append("下跌家数超过上涨家数两倍")
        if context.csi1000_return < context.csi300_return - 1:
            risk.append("中证1000明显跑输沪深300")
        score = len(evidence)
        severe = len(risk) >= 2
        if context.previous_regime in (MarketRegime.RECOVERING, MarketRegime.RISK_ON) and severe:
            regime = MarketRegime.RISK_OFF
        elif score >= 7 and not severe:
            regime = MarketRegime.RISK_ON
        elif score >= int(self.config.market_recovery_conditions["required_for_recovering"]) and not severe:
            regime = MarketRegime.RECOVERING
        elif context.csi300_return > 0 and severe:
            regime = MarketRegime.STABILIZING
        elif severe:
            regime = MarketRegime.DELEVERAGING
        else:
            regime = MarketRegime.STABILIZING
        return MarketRegimeResult(
            regime=regime,
            score=score,
            evidence=evidence,
            risk_evidence=risk,
            data_as_of=context.data_as_of,
            deleveraging_continues=severe,
        )

    def portfolio_risk(self, snapshot: PortfolioSnapshot) -> Recommendation | None:
        active = None
        for rung in sorted(self.config.portfolio_drawdown_ladder, key=lambda item: item["threshold"]):
            if snapshot.drawdown >= float(rung["threshold"]):
                active = rung
        if not active:
            return None
        severity = Severity(active["severity"])
        blockers = [str(active["action"])]
        if active.get("equity_cap") is not None:
            blockers.append(f"权益授权上限降至{float(active['equity_cap']):.0%}")
        if active.get("minimum_cash_cny") is not None:
            blockers.append(f"最低现金提高至{float(active['minimum_cash_cny']):.0f}元")
        return Recommendation(
            status=SignalStatus.REDUCE if snapshot.drawdown >= 0.12 else SignalStatus.BLOCKED,
            severity=severity,
            module="portfolio",
            rule_id=f"portfolio_drawdown_{int(float(active['threshold']) * 100)}",
            max_amount_cny=0,
            evidence=[f"组合回撤{snapshot.drawdown:.2%}触发{float(active['threshold']):.0%}阶梯"],
            blocking_reasons=blockers,
            invalidation=["组合回撤重新下降且风险规则经收盘确认解除"],
            data_as_of=snapshot.data_as_of,
            config_version=self.config.version,
        )

    def buy_signals(
        self,
        snapshot: PortfolioSnapshot,
        indicators: dict[str, IndicatorSnapshot],
        context: MarketContext,
        regime: MarketRegimeResult,
    ) -> list[Recommendation]:
        signals: list[Recommendation] = []
        signals.extend(self._cash_signals(snapshot, indicators))
        signals.extend(self._fixed_income_signals(snapshot, indicators))
        signals.extend(self._gold_signals(snapshot, indicators))
        signals.extend(self._dividend_signals(snapshot, indicators))
        signals.extend(self._broad_signals(snapshot, indicators, context))
        signals.extend(self.beta_signals(snapshot, indicators, context, regime))
        risk = self.portfolio_risk(snapshot)
        if risk:
            signals.append(risk)
        if snapshot.cash < 200_000:
            signals.append(
                self._rec(
                    SignalStatus.BLOCKED, Severity.RISK, "portfolio", None, "cash_floor_200k", 0,
                    [f"现金仅{snapshot.cash:.0f}元"], ["现金低于20万元，暂停新增风险资产"],
                    ["现金恢复至20万元以上"], snapshot.data_as_of,
                )
            )
        return signals

    def beta_signals(
        self,
        snapshot: PortfolioSnapshot,
        indicators: dict[str, IndicatorSnapshot],
        context: MarketContext,
        regime: MarketRegimeResult,
    ) -> list[Recommendation]:
        technology_value = snapshot.module_values.get("technology", 0)
        technology_cost = sum(
            position.quantity * position.average_cost for position in snapshot.positions if position.module == "technology"
        )
        technology_pnl = sum(position.unrealized_pnl for position in snapshot.positions if position.module == "technology")
        technology_drawdown = abs(min(technology_pnl / technology_cost, 0)) if technology_cost else 0
        if technology_drawdown >= float(self.config.technology_risk["reduce_drawdown"]):
            breadth_weak = (
                context.limit_down_count >= 100
                or context.median_return < 0
                or (context.semiconductor_breadth is not None and context.semiconductor_breadth < 0.50)
                or regime.regime in (MarketRegime.DELEVERAGING, MarketRegime.STABILIZING, MarketRegime.RISK_OFF)
            )
            return [
                self._rec(
                    SignalStatus.REDUCE if breadth_weak else SignalStatus.BLOCKED,
                    Severity.RISK, "technology", None,
                    "technology_drawdown_reduce" if breadth_weak else "technology_drawdown_review", 0,
                    [f"科技仓浮亏{technology_drawdown:.2%}", *regime.risk_evidence],
                    ["科技仓达到12%且广度仍弱，建议减少约三分之一"] if breadth_weak
                    else ["科技仓达到12%，但广度未恶化，先执行风险复核并停止新增"],
                    ["行业广度与相对强弱恢复后重新评估"], snapshot.data_as_of,
                )
            ]
        if technology_drawdown >= float(self.config.technology_risk["stop_adding_drawdown"]):
            severity = Severity.RISK if technology_drawdown >= float(self.config.technology_risk["review_drawdown"]) else Severity.WATCH
            return [
                self._rec(
                    SignalStatus.BLOCKED, severity, "technology", None, "technology_drawdown_stop_add", 0,
                    [f"科技仓浮亏{technology_drawdown:.2%}"], ["科技仓达到停止加仓阈值"],
                    ["浮亏回到8%以内且市场广度改善"], snapshot.data_as_of,
                )
            ]
        quality_blocks = self._quality_blocks(indicators, ["159995.SZ", "515050.SH", "512480.SH", "159516.SZ"])
        if quality_blocks:
            return [
                self._rec(
                    SignalStatus.BLOCKED, Severity.RISK, "technology", None, "technology_data_quality", 0,
                    [], quality_blocks, ["行情恢复且多源价格偏差回到阈值内"], snapshot.data_as_of,
                )
            ]
        support_breaks = []
        for symbol in ("159995.SZ", "515050.SH", "512480.SH", "159516.SZ"):
            indicator = indicators.get(symbol)
            support = self.instruments[symbol].anchors.get("support")
            if indicator and support and indicator.price < support:
                support_breaks.append(f"{symbol}价格{indicator.price:.3f}跌破支撑{support:.3f}")
        if support_breaks:
            return [
                self._rec(
                    SignalStatus.BLOCKED, Severity.RISK, "technology", None, "technology_support_break", 0,
                    support_breaks, ["关键支撑失效，禁止进入下一阶段"],
                    ["收盘重新站回支撑并确认承接"], snapshot.data_as_of,
                )
            ]
        current_stage = self._current_stage(technology_value)
        next_stage = min(current_stage + 1, 4) if current_stage else 1
        eligible, evidence, blockers = self._stage_eligibility(next_stage, indicators, context, regime, technology_value)
        stage = next(item for item in self.config.technology_stages if item.stage == next_stage)
        positions_by_symbol = {position.symbol: position.market_value for position in snapshot.positions}
        recommendations = []
        for symbol, cumulative_target in stage.allocations.items():
            gap = max(float(cumulative_target) - positions_by_symbol.get(symbol, 0), 0)
            if gap <= 1:
                continue
            recommendations.append(
                self._rec(
                    SignalStatus.ELIGIBLE if eligible else SignalStatus.BLOCKED,
                    Severity.ACTION if eligible else Severity.WATCH,
                    "technology", symbol, f"technology_stage_{next_stage}_{symbol.split('.')[0]}", gap if eligible else 0,
                    evidence, blockers,
                    self._technology_invalidation(symbol), snapshot.data_as_of,
                )
            )
        if snapshot.technology_weight > float(self.config.technology_risk["rebalance_trigger_weight"]):
            recommendations.append(
                self._rec(
                    SignalStatus.REDUCE, Severity.ACTION, "technology", None, "technology_weight_rebalance", 0,
                    [f"科技仓权重{snapshot.technology_weight:.2%}>18%"], ["减回15%战略上限"],
                    ["科技仓权重回到15%附近"], snapshot.data_as_of,
                )
            )
        return recommendations

    def _current_stage(self, technology_value: float) -> int:
        current = 0
        for stage in sorted(self.config.technology_stages, key=lambda item: item.stage):
            if technology_value >= stage.cumulative_amount_cny * 0.95:
                current = stage.stage
        return current

    def _stage_eligibility(
        self,
        stage: int,
        indicators: dict[str, IndicatorSnapshot],
        context: MarketContext,
        regime: MarketRegimeResult,
        technology_value: float,
    ) -> tuple[bool, list[str], list[str]]:
        if stage == 1:
            return True, ["科技首阶段仅占组合2.5%，允许试错"], []
        previous_target = self.config.technology_stages[stage - 2].cumulative_amount_cny
        if technology_value < previous_target * 0.90:
            return False, [], [f"上一阶段尚未完成，当前科技仓{technology_value:.0f}元"]
        if stage == 2:
            chip = indicators.get("159995.SZ")
            comm = indicators.get("515050.SH")
            checks = [
                (context.limit_down_count < 100, f"跌停家数{context.limit_down_count}<100"),
                (context.advances_exceed_declines_two_days, "连续两日上涨家数多于下跌家数"),
                (context.median_positive_two_days, "市场中位数连续转正"),
                (context.csi1000_stops_new_low and context.csi1000_return > context.csi300_return, "中证1000止跌并跑赢沪深300"),
                (bool(chip and chip.price >= self.instruments["159995.SZ"].anchors["first_confirm"]), "芯片ETF站上1.271"),
                (bool(comm and comm.price >= self.instruments["515050.SH"].anchors["first_confirm"]), "通信ETF站上1.096"),
                (context.technology_etf_inflow_two_days, "科技ETF连续两日净流入"),
            ]
            evidence = [text for passed, text in checks if passed]
            required = next(item for item in self.config.technology_stages if item.stage == 2).minimum_conditions or 3
            return len(evidence) >= required, evidence, ([] if len(evidence) >= required else [f"Stage 2仅满足{len(evidence)}/{required}项"])
        if stage == 3:
            checks = [
                (context.growth_outperformance_days >= 3, "成长指数五日内至少三日跑赢沪深300"),
                (context.technology_volume_healthy, "科技上涨放量、回调缩量"),
                (context.limit_down_count < 50, f"跌停家数{context.limit_down_count}<50"),
                (regime.regime in (MarketRegime.RECOVERING, MarketRegime.RISK_ON), f"市场状态{regime.regime.value}"),
            ]
            evidence = [text for passed, text in checks if passed]
            return len(evidence) >= 3, evidence, ([] if len(evidence) >= 3 else [f"Stage 3仅满足{len(evidence)}/3项"])
        equipment = indicators.get("159516.SZ")
        checks = [
            (bool(equipment and equipment.price >= self.instruments["159516.SZ"].anchors["first_confirm"]), "设备ETF站上0.729"),
            (context.equipment_inflow_two_days, "设备ETF连续两日净流入"),
            (context.equipment_leaders_confirmed >= 2, "中微、北方华创、拓荆至少两只同步确认"),
            (bool(equipment and equipment.trend != "falling"), "设备ETF不再处于下降趋势"),
        ]
        evidence = [text for passed, text in checks if passed]
        return len(evidence) == 4, evidence, ([] if len(evidence) == 4 else [f"Stage 4仅满足{len(evidence)}/4项"])

    def _cash_signals(self, snapshot: PortfolioSnapshot, indicators: dict[str, IndicatorSnapshot]) -> list[Recommendation]:
        target = self.config.modules["cash"].target_amount_cny
        gap = max(target - snapshot.module_values.get("cash", 0), 0)
        if gap <= 1:
            return []
        quality = self._quality_blocks(indicators, ["511880.SH"])
        return [self._rec(
            SignalStatus.BLOCKED if quality else SignalStatus.ELIGIBLE,
            Severity.RISK if quality else Severity.INFO,
            "cash", "511880.SH", "cash_primary", 0 if quality else gap,
            ["现金管理模块可立即配置"] if not quality else [], quality,
            ["出现异常折溢价或买卖价差扩大"], snapshot.data_as_of,
        )]

    def _fixed_income_signals(self, snapshot: PortfolioSnapshot, indicators: dict[str, IndicatorSnapshot]) -> list[Recommendation]:
        current = snapshot.module_values.get("fixed_income", 0)
        first_target = 100_000
        max_add = max(first_target - current, 0) if current < first_target else max(self.config.modules["fixed_income"].target_amount_cny - current, 0)
        if max_add <= 1:
            return []
        quality = self._quality_blocks(indicators, ["511360.SH", "511010.SH"])
        return [self._rec(
            SignalStatus.BLOCKED if quality else SignalStatus.ELIGIBLE,
            Severity.RISK if quality else Severity.INFO,
            "fixed_income", None, "fixed_income_first_half", 0 if quality else max_add,
            ["短融与国债趋势稳定，首批最多配置10万元"] if not quality else [], quality,
            ["信用利差快速走阔或10年国债收益率快速上行"], snapshot.data_as_of,
        )]

    def _gold_signals(self, snapshot: PortfolioSnapshot, indicators: dict[str, IndicatorSnapshot]) -> list[Recommendation]:
        symbol = "518880.SH"
        indicator = indicators.get(symbol)
        if not indicator:
            return []
        quality = self._quality_blocks(indicators, [symbol])
        support = self.instruments[symbol].anchors["support"]
        high = self.instruments[symbol].anchors["first_zone_high"]
        current = snapshot.module_values.get("gold", 0)
        gap = max(min(20_000, self.config.modules["gold"].target_amount_cny - current), 0)
        if indicator.price < support:
            return [self._rec(SignalStatus.BLOCKED, Severity.RISK, "gold", symbol, "gold_support_break", 0,
                              [f"价格{indicator.price:.3f}<支撑{support:.3f}"], ["黄金支撑失效"],
                              ["重新站回8.22并确认止跌"], snapshot.data_as_of)]
        eligible = support <= indicator.price <= high and not quality and gap > 0
        return [self._rec(
            SignalStatus.ELIGIBLE if eligible else SignalStatus.WATCH,
            Severity.ACTION if eligible else Severity.WATCH,
            "gold", symbol, "gold_first_tranche", gap if eligible else 0,
            [f"价格位于{support:.3f}-{high:.3f}首笔区间"] if eligible else [],
            quality or (["尚未进入首笔区间"] if indicator.price > high else []),
            ["放量跌破8.22暂停机械摊低"], snapshot.data_as_of,
        )]

    def _dividend_signals(self, snapshot: PortfolioSnapshot, indicators: dict[str, IndicatorSnapshot]) -> list[Recommendation]:
        current = snapshot.module_values.get("dividend", 0)
        tranche = max(min(50_000, self.config.modules["dividend"].target_amount_cny - current), 0)
        results = []
        for symbol in ("512890.SH", "510880.SH"):
            indicator = indicators.get(symbol)
            if not indicator or tranche <= 0:
                continue
            anchors = self.instruments[symbol].anchors
            in_zone = anchors["first_zone_low"] <= indicator.price <= anchors["first_zone_high"]
            chasing = (indicator.change_pct or 0) >= 2
            quality = self._quality_blocks(indicators, [symbol])
            eligible = in_zone and not chasing and not quality
            results.append(self._rec(
                SignalStatus.ELIGIBLE if eligible else SignalStatus.WATCH,
                Severity.ACTION if eligible else Severity.WATCH,
                "dividend", symbol, f"dividend_pullback_{symbol.split('.')[0]}", tranche if eligible else 0,
                ["回踩首笔区间且未出现单日追高"] if eligible else [],
                quality + (["单日涨幅超过2%，不追价"] if chasing else []) + (["未进入MA5附近首笔区间"] if not in_zone else []),
                ["放量跌破MA20或核心成分股分红逻辑恶化"], snapshot.data_as_of,
            ))
        return results

    def _broad_signals(self, snapshot: PortfolioSnapshot, indicators: dict[str, IndicatorSnapshot], context: MarketContext) -> list[Recommendation]:
        current = snapshot.module_values.get("broad_market", 0)
        total_gap = max(self.config.modules["broad_market"].target_amount_cny - current, 0)
        results = []
        for symbol, first_amount in (("510300.SH", 30_000), ("563360.SH", 20_000)):
            indicator = indicators.get(symbol)
            if not indicator or total_gap <= 0:
                continue
            anchors = self.instruments[symbol].anchors
            in_zone = anchors["first_zone_low"] <= indicator.price <= anchors["first_zone_high"]
            quality = self._quality_blocks(indicators, [symbol])
            breadth_ok = symbol == "510300.SH" or context.limit_down_count < 100
            eligible = in_zone and breadth_ok and not quality
            amount = min(first_amount, total_gap) if eligible else 0
            results.append(self._rec(
                SignalStatus.ELIGIBLE if eligible else SignalStatus.WATCH,
                Severity.ACTION if eligible else Severity.WATCH,
                "broad_market", symbol, f"broad_first_{symbol.split('.')[0]}", amount,
                ["位于首笔区间", "沪深300优先" if symbol == "510300.SH" else "市场广度允许A500首笔"] if eligible else [],
                quality + (["跌停家数未降至100以下，A500暂缓"] if symbol == "563360.SH" and not breadth_ok else []) + (["未进入首笔区间"] if not in_zone else []),
                [f"放量跌破支撑{anchors['support']:.3f}"], snapshot.data_as_of,
            ))
        return results

    def _quality_blocks(self, indicators: dict[str, IndicatorSnapshot], symbols: Iterable[str]) -> list[str]:
        blocks = []
        for symbol in symbols:
            indicator = indicators.get(symbol)
            if not indicator:
                blocks.append(f"{symbol}缺少行情")
            elif indicator.stale or indicator.data_quality == "stale":
                blocks.append(f"{symbol}行情超过新鲜度阈值")
            elif indicator.data_quality == "conflict":
                blocks.append(f"{symbol}多源价格偏差超过阈值")
        return blocks

    def _technology_invalidation(self, symbol: str) -> list[str]:
        anchors = self.instruments[symbol].anchors
        return [f"放量跌破支撑{anchors['support']:.3f}", "科技仓浮亏达到8%", "组合现金低于20万元"]

    def _rec(
        self,
        status: SignalStatus,
        severity: Severity,
        module: str,
        symbol: str | None,
        rule_id: str,
        max_amount: float,
        evidence: list[str],
        blockers: list[str],
        invalidation: list[str],
        data_as_of: datetime,
    ) -> Recommendation:
        return Recommendation(
            status=status,
            severity=severity,
            module=module,
            symbol=symbol,
            rule_id=rule_id,
            max_amount_cny=max(max_amount, 0),
            evidence=evidence,
            blocking_reasons=blockers,
            invalidation=invalidation,
            data_as_of=data_as_of,
            config_version=self.config.version,
        )
