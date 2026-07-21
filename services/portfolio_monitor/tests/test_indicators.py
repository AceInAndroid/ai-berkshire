from datetime import UTC, datetime, timedelta

from portfolio_monitor.indicators import calculate_indicator
from portfolio_monitor.models import Bar, Quote


def bars():
    return [Bar(symbol="159995.SZ", trade_date=f"2026-06-{i:02d}", open=1+i/100, high=1.02+i/100,
                low=.98+i/100, close=1+i/100, volume=1000+i, source="test") for i in range(1, 22)]


def test_stale_and_cross_source_conflict():
    now = datetime.now(UTC)
    quote = Quote(symbol="159995.SZ", price=1.3, source="a", market_time=now, fetched_at=now-timedelta(minutes=11))
    result = calculate_indicator("159995.SZ", bars(), quote, [quote], 10, .005, now=now)
    assert result.stale is True and result.data_quality == "stale"
    fresh = quote.model_copy(update={"fetched_at": now})
    other = fresh.model_copy(update={"source": "b", "price": 1.4})
    result = calculate_indicator("159995.SZ", bars(), fresh, [fresh, other], 10, .005, now=now)
    assert result.data_quality == "conflict"
