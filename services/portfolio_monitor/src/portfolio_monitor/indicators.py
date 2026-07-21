from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from .models import Bar, IndicatorSnapshot, Quote


def calculate_indicator(
    symbol: str,
    bars: list[Bar],
    quote: Quote | None,
    quote_candidates: list[Quote] | None,
    stale_after_minutes: int,
    max_deviation: float,
    now: datetime | None = None,
) -> IndicatorSnapshot:
    now = now or datetime.now(UTC)
    if not bars and not quote:
        raise ValueError(f"no data for {symbol}")
    frame = pd.DataFrame(
        [
            {
                "date": bar.trade_date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ]
    ).sort_values("date")
    price = quote.price if quote else float(frame.iloc[-1]["close"])
    if not frame.empty:
        if frame.iloc[-1]["date"] != (quote.market_time.date() if quote else frame.iloc[-1]["date"]):
            synthetic = {
                "date": quote.market_time.date() if quote else frame.iloc[-1]["date"],
                "open": quote.open or price,
                "high": quote.high or price,
                "low": quote.low or price,
                "close": price,
                "volume": quote.volume or 0,
            }
            frame = pd.concat([frame, pd.DataFrame([synthetic])], ignore_index=True)
        elif quote:
            frame.loc[frame.index[-1], "close"] = price
            if quote.volume is not None:
                frame.loc[frame.index[-1], "volume"] = quote.volume
    closes = frame["close"].astype(float)
    volumes = frame["volume"].astype(float)

    def rolling_mean(window: int) -> float | None:
        return float(closes.tail(window).mean()) if len(closes) >= window else None

    ma5, ma10, ma20, ma60 = (rolling_mean(size) for size in (5, 10, 20, 60))
    high20 = float(frame["high"].tail(20).max()) if len(frame) >= 1 else None
    low20 = float(frame["low"].tail(20).min()) if len(frame) >= 1 else None
    return5 = ((price / float(closes.iloc[-6])) - 1) * 100 if len(closes) >= 6 else None
    return20 = ((price / float(closes.iloc[-21])) - 1) * 100 if len(closes) >= 21 else None
    avg_volume20 = volumes.tail(20).mean() if len(volumes) else 0
    volume_ratio = float(volumes.iloc[-1] / avg_volume20) if avg_volume20 and len(volumes) else None
    returns = closes.pct_change().dropna()
    vol20 = float(returns.tail(20).std(ddof=1) * np.sqrt(252)) if len(returns) >= 2 else None
    vol60 = float(returns.tail(60).std(ddof=1) * np.sqrt(252)) if len(returns) >= 2 else None
    if ma5 is None or ma20 is None:
        trend = "unknown"
    elif price > ma5 > ma20:
        trend = "rising"
    elif price < ma5 < ma20:
        trend = "falling"
    else:
        trend = "flat"

    stale = False
    if quote:
        stale = now - quote.fetched_at.astimezone(UTC) > timedelta(minutes=stale_after_minutes)
    candidates = quote_candidates or ([quote] if quote else [])
    prices = [candidate.price for candidate in candidates if candidate.price > 0]
    deviation = None
    if len(prices) >= 2:
        midpoint = float(np.median(prices))
        deviation = (max(prices) - min(prices)) / midpoint if midpoint else None
    if stale:
        quality = "stale"
    elif deviation is not None and deviation > max_deviation:
        quality = "conflict"
    elif quote and quote.degraded:
        quality = "degraded"
    elif len(prices) >= 2:
        quality = "verified"
    else:
        quality = "single_source"

    return IndicatorSnapshot(
        symbol=symbol,
        data_as_of=quote.market_time if quote else datetime.combine(frame.iloc[-1]["date"], datetime.min.time(), UTC),
        price=price,
        change_pct=quote.change_pct if quote else None,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        ma60=ma60,
        high20=high20,
        low20=low20,
        return5=return5,
        return20=return20,
        volume_ratio20=volume_ratio,
        volatility20=vol20,
        volatility60=vol60,
        trend=trend,
        stale=stale,
        cross_source_deviation=deviation,
        data_quality=quality,
    )


def max_drawdown(values: list[float]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1)
    return abs(worst)


def annualized_metrics(equity_curve: pd.Series, trading_days: int = 252) -> dict[str, float]:
    if len(equity_curve) < 2:
        return {"total_return": 0, "cagr": 0, "volatility": 0, "sharpe": 0, "sortino": 0, "max_drawdown": 0, "calmar": 0}
    returns = equity_curve.pct_change().dropna()
    years = max((equity_curve.index[-1] - equity_curve.index[0]).days / 365.25, 1 / 365.25)
    total_return = equity_curve.iloc[-1] / equity_curve.iloc[0] - 1
    cagr = (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1 / years) - 1
    volatility = float(returns.std(ddof=1) * np.sqrt(trading_days)) if len(returns) > 1 else 0
    sharpe = float(returns.mean() / returns.std(ddof=1) * np.sqrt(trading_days)) if len(returns) > 1 and returns.std(ddof=1) else 0
    downside = returns[returns < 0]
    sortino = float(returns.mean() / downside.std(ddof=1) * np.sqrt(trading_days)) if len(downside) > 1 and downside.std(ddof=1) else 0
    drawdown = max_drawdown(equity_curve.tolist())
    return {
        "total_return": float(total_return),
        "cagr": float(cagr),
        "volatility": volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": drawdown,
        "calmar": float(cagr / drawdown) if drawdown else 0,
    }
