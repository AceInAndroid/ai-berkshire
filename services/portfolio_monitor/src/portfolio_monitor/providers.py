from __future__ import annotations

import asyncio
import json
import os
import statistics
from abc import ABC, abstractmethod
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx

from .models import Bar, MarketContext, Quote


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class ProviderError(RuntimeError):
    pass


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        raise NotImplementedError

    @abstractmethod
    async def get_history(self, symbol: str, start: date, end: date) -> list[Bar]:
        raise NotImplementedError

    async def get_market_context(self) -> MarketContext | None:
        return None

    async def health(self) -> dict[str, Any]:
        return {"provider": self.name, "status": "unknown"}


class TencentProvider(MarketDataProvider):
    name = "tencent"

    def __init__(self, timeout: float = 15):
        self.timeout = timeout

    @staticmethod
    def _code(symbol: str) -> str:
        code, market = symbol.split(".", 1)
        return ("sh" if market == "SH" else "sz") + code

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        if not symbols:
            return {}
        codes = ",".join(self._code(symbol) for symbol in symbols)
        url = f"https://qt.gtimg.cn/q={codes}"
        fetched_at = datetime.now(UTC)
        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = await client.get(url)
            response.raise_for_status()
            raw = response.content.decode("gbk", errors="replace")
        result: dict[str, Quote] = {}
        code_map = {self._code(symbol): symbol for symbol in symbols}
        for line in raw.splitlines():
            if "=\"" not in line:
                continue
            prefix, payload = line.split("=\"", 1)
            qq_code = prefix.removeprefix("v_")
            symbol = code_map.get(qq_code)
            if not symbol:
                continue
            fields = payload.rsplit('"', 1)[0].split("~")
            if len(fields) < 35 or not fields[3]:
                continue
            market_time = fetched_at
            if len(fields) > 30 and fields[30]:
                try:
                    local = datetime.strptime(fields[30], "%Y%m%d%H%M%S").replace(tzinfo=SHANGHAI_TZ)
                    market_time = local.astimezone(UTC)
                except ValueError:
                    pass
            result[symbol] = Quote(
                symbol=symbol,
                price=float(fields[3]),
                previous_close=float(fields[4]) if fields[4] else None,
                open=float(fields[5]) if fields[5] else None,
                high=float(fields[33]) if len(fields) > 33 and fields[33] else None,
                low=float(fields[34]) if len(fields) > 34 and fields[34] else None,
                volume=float(fields[6]) * 100 if fields[6] else None,
                amount=float(fields[37]) * 10_000 if len(fields) > 37 and fields[37] else None,
                change_pct=float(fields[32]) if len(fields) > 32 and fields[32] else None,
                source=self.name,
                market_time=market_time,
                fetched_at=fetched_at,
                raw={"name": fields[1], "fields": fields},
            )
        return result

    async def get_history(self, symbol: str, start: date, end: date) -> list[Bar]:
        raise ProviderError("Tencent provider does not expose history in this adapter")


class EastmoneyProvider(MarketDataProvider):
    name = "eastmoney"

    def __init__(self, timeout: float = 20):
        self.timeout = timeout

    @staticmethod
    def _secid(symbol: str) -> str:
        code, market = symbol.split(".", 1)
        return f"{1 if market == 'SH' else 0}.{code}"

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        # History endpoint also returns the latest daily close. It is deliberately
        # marked degraded because it is not a true intraday quote.
        result: dict[str, Quote] = {}
        today = datetime.now(SHANGHAI_TZ).date()
        for symbol in symbols:
            bars = await self.get_history(symbol, today - timedelta(days=10), today)
            if not bars:
                continue
            bar = bars[-1]
            market_time = datetime.combine(bar.trade_date, time(15, 0), SHANGHAI_TZ).astimezone(UTC)
            previous_close = bars[-2].close if len(bars) > 1 else None
            pct = ((bar.close / previous_close) - 1) * 100 if previous_close else None
            result[symbol] = Quote(
                symbol=symbol,
                price=bar.close,
                previous_close=previous_close,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                volume=bar.volume,
                amount=bar.amount,
                change_pct=pct,
                source=self.name,
                market_time=market_time,
                fetched_at=datetime.now(UTC),
                degraded=True,
            )
        return result

    async def get_history(self, symbol: str, start: date, end: date) -> list[Bar]:
        params = {
            "secid": self._secid(symbol),
            "klt": "101",
            "fqt": "1",
            "beg": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "lmt": "5000",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        }
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get?" + urlencode(params)
        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        klines = ((payload or {}).get("data") or {}).get("klines") or []
        bars: list[Bar] = []
        for row in klines:
            fields = row.split(",")
            if len(fields) < 7:
                continue
            bars.append(
                Bar(
                    symbol=symbol,
                    trade_date=date.fromisoformat(fields[0]),
                    open=float(fields[1]),
                    close=float(fields[2]),
                    high=float(fields[3]),
                    low=float(fields[4]),
                    volume=float(fields[5]),
                    amount=float(fields[6]),
                    source=self.name,
                )
            )
        return bars

    async def get_market_context(self) -> MarketContext | None:
        params = {
            "pn": "1",
            "pz": "6000",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": "f2,f3,f12,f14",
        }
        url = "https://push2.eastmoney.com/api/qt/clist/get?" + urlencode(params)
        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        rows = (((payload or {}).get("data") or {}).get("diff") or [])
        returns = [float(row["f3"]) for row in rows if row.get("f3") not in (None, "-")]
        if not returns:
            return None
        advances = sum(value > 0 for value in returns)
        declines = sum(value < 0 for value in returns)
        limit_down = sum(value <= -9.8 for value in returns)
        return MarketContext(
            data_as_of=datetime.now(UTC),
            advances=advances,
            declines=declines,
            limit_down_count=limit_down,
            median_return=statistics.median(returns),
        )


class YahooProvider(MarketDataProvider):
    name = "yahoo"

    def __init__(self, timeout: float = 20):
        self.timeout = timeout

    async def _chart(self, symbol: str, period1: int, period2: int) -> dict[str, Any]:
        encoded = httpx.URL(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}")
        params = {"period1": period1, "period2": period2, "interval": "1d", "events": "history"}
        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = await client.get(encoded, params=params)
            response.raise_for_status()
            payload = response.json()
        result = (payload.get("chart", {}).get("result") or [None])[0]
        if not result:
            raise ProviderError(f"Yahoo returned no data for {symbol}")
        return result

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        end = datetime.now(UTC)
        start = end - timedelta(days=10)
        result: dict[str, Quote] = {}
        for symbol in symbols:
            chart = await self._chart(symbol, int(start.timestamp()), int((end + timedelta(days=1)).timestamp()))
            timestamps = chart.get("timestamp") or []
            quote = (chart.get("indicators", {}).get("quote") or [{}])[0]
            closes = quote.get("close") or []
            valid = [(idx, close) for idx, close in enumerate(closes) if close is not None]
            if not valid:
                continue
            idx, close = valid[-1]
            prev = valid[-2][1] if len(valid) > 1 else None
            market_time = datetime.fromtimestamp(timestamps[idx], UTC) if timestamps else end
            result[symbol] = Quote(
                symbol=symbol,
                price=float(close),
                previous_close=float(prev) if prev is not None else None,
                open=float(quote["open"][idx]) if quote.get("open") and quote["open"][idx] is not None else None,
                high=float(quote["high"][idx]) if quote.get("high") and quote["high"][idx] is not None else None,
                low=float(quote["low"][idx]) if quote.get("low") and quote["low"][idx] is not None else None,
                volume=float(quote["volume"][idx]) if quote.get("volume") and quote["volume"][idx] is not None else None,
                change_pct=((float(close) / float(prev)) - 1) * 100 if prev else None,
                source=self.name,
                market_time=market_time,
                fetched_at=end,
                currency=(chart.get("meta") or {}).get("currency", "USD"),
                delayed=True,
            )
        return result

    async def get_history(self, symbol: str, start: date, end: date) -> list[Bar]:
        start_dt = datetime.combine(start, time.min, UTC)
        end_dt = datetime.combine(end + timedelta(days=1), time.min, UTC)
        chart = await self._chart(symbol, int(start_dt.timestamp()), int(end_dt.timestamp()))
        timestamps = chart.get("timestamp") or []
        quote = (chart.get("indicators", {}).get("quote") or [{}])[0]
        bars: list[Bar] = []
        for idx, timestamp in enumerate(timestamps):
            values = [quote.get(key, [None] * len(timestamps))[idx] for key in ("open", "high", "low", "close")]
            if any(value is None for value in values):
                continue
            bars.append(
                Bar(
                    symbol=symbol,
                    trade_date=datetime.fromtimestamp(timestamp, UTC).date(),
                    open=float(values[0]),
                    high=float(values[1]),
                    low=float(values[2]),
                    close=float(values[3]),
                    volume=float((quote.get("volume") or [0] * len(timestamps))[idx] or 0),
                    amount=0,
                    source=self.name,
                )
            )
        return bars


class LongbridgeReadOnlyProvider(MarketDataProvider):
    """Optional Longbridge MCP client. Only read-only tools are callable."""

    name = "longbridge"
    READ_ONLY_TOOLS = frozenset({"quote", "candlesticks", "intraday", "capital_flow", "market_temperature"})

    def __init__(self, endpoint: str | None = None, token: str | None = None):
        self.endpoint = endpoint or os.getenv("LONGBRIDGE_MCP_URL")
        self.token = token or os.getenv("LONGBRIDGE_MCP_TOKEN")

    async def _call(self, tool: str, arguments: dict[str, Any]) -> Any:
        if tool not in self.READ_ONLY_TOOLS:
            raise ProviderError(f"Longbridge tool {tool} is not allowed")
        if not self.endpoint:
            raise ProviderError("Longbridge MCP is not configured")
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        headers = {"Authorization": f"Bearer {self.token}"} if self.token else None
        async with streamablehttp_client(self.endpoint, headers=headers) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                response = await session.call_tool(tool, arguments)
        if response.isError:
            raise ProviderError(f"Longbridge {tool} failed")
        if getattr(response, "structuredContent", None) is not None:
            return response.structuredContent
        texts = [content.text for content in response.content if getattr(content, "type", None) == "text"]
        return json.loads(texts[0]) if texts else {}

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        payload = await self._call("quote", {"symbols": symbols})
        rows = payload.get("quotes") or payload.get("data") or payload if isinstance(payload, list) else []
        now = datetime.now(UTC)
        result: dict[str, Quote] = {}
        for row in rows:
            symbol = row.get("symbol")
            if not symbol:
                continue
            timestamp = row.get("timestamp") or row.get("trade_time")
            market_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if timestamp else now
            result[symbol] = Quote(
                symbol=symbol,
                price=float(row.get("last_done") or row.get("price")),
                previous_close=float(row["prev_close"]) if row.get("prev_close") else None,
                open=float(row["open"]) if row.get("open") else None,
                high=float(row["high"]) if row.get("high") else None,
                low=float(row["low"]) if row.get("low") else None,
                volume=float(row["volume"]) if row.get("volume") else None,
                amount=float(row["turnover"]) if row.get("turnover") else None,
                change_pct=float(row["change_rate"]) if row.get("change_rate") else None,
                source=self.name,
                market_time=market_time,
                fetched_at=now,
            )
        return result

    async def get_history(self, symbol: str, start: date, end: date) -> list[Bar]:
        payload = await self._call(
            "candlesticks", {"symbol": symbol, "period": "day", "count": 1000, "forward_adjust": True}
        )
        rows = payload.get("candlesticks") or payload.get("items") or payload.get("data") or []
        bars = []
        for row in rows:
            raw_time = row.get("timestamp") or row.get("time") or row.get("trade_date")
            trade_date = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00")).date()
            if not start <= trade_date <= end:
                continue
            bars.append(
                Bar(
                    symbol=symbol,
                    trade_date=trade_date,
                    open=float(row["open"]), high=float(row["high"]), low=float(row["low"]), close=float(row["close"]),
                    volume=float(row.get("volume") or 0), amount=float(row.get("turnover") or 0), source=self.name,
                )
            )
        return sorted(bars, key=lambda item: item.trade_date)

    async def health(self) -> dict[str, Any]:
        return {"provider": self.name, "status": "configured" if self.endpoint else "disabled", "read_only": True}


class FixtureProvider(MarketDataProvider):
    name = "fixture"

    def __init__(self, fixture_path: str | Path):
        self.path = Path(fixture_path)
        self.payload = json.loads(self.path.read_text(encoding="utf-8"))

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        result: dict[str, Quote] = {}
        refresh_fetched_at = bool(self.payload.get("refresh_fetched_at"))
        for symbol in symbols:
            raw = self.payload.get("quotes", {}).get(symbol)
            if not raw:
                continue
            quote = Quote.model_validate(raw)
            if refresh_fetched_at:
                quote = quote.model_copy(update={"fetched_at": datetime.now(UTC)})
            result[symbol] = quote
        return result

    async def get_history(self, symbol: str, start: date, end: date) -> list[Bar]:
        rows = self.payload.get("history", {}).get(symbol, [])
        bars = [Bar.model_validate(row) for row in rows]
        return [bar for bar in bars if start <= bar.trade_date <= end]

    async def get_market_context(self) -> MarketContext | None:
        raw = self.payload.get("market_context")
        return MarketContext.model_validate(raw) if raw else None

    async def health(self) -> dict[str, Any]:
        return {"provider": self.name, "status": "ok", "fixture": str(self.path)}


class ProviderRegistry:
    def __init__(self, primary: MarketDataProvider, fallbacks: list[MarketDataProvider] | None = None):
        self.primary = primary
        self.fallbacks = fallbacks or []

    @property
    def providers(self) -> list[MarketDataProvider]:
        return [self.primary, *self.fallbacks]

    async def quotes(self, symbols: list[str]) -> tuple[dict[str, Quote], dict[str, list[Quote]]]:
        all_quotes: dict[str, list[Quote]] = {symbol: [] for symbol in symbols}
        for provider in self.providers:
            try:
                provider_quotes = await provider.get_quotes(symbols)
            except Exception:
                continue
            for symbol, quote in provider_quotes.items():
                all_quotes.setdefault(symbol, []).append(quote)
        selected: dict[str, Quote] = {}
        for symbol, candidates in all_quotes.items():
            if candidates:
                selected[symbol] = candidates[0]
                if candidates[0].source != self.primary.name:
                    selected[symbol] = candidates[0].model_copy(update={"degraded": True})
        return selected, all_quotes

    async def history(self, symbol: str, start: date, end: date) -> list[Bar]:
        errors = []
        for provider in self.providers:
            try:
                bars = await provider.get_history(symbol, start, end)
                if bars:
                    return bars
            except Exception as error:
                errors.append(f"{provider.name}: {error}")
        raise ProviderError(f"all history providers failed for {symbol}: {'; '.join(errors)}")

    async def market_context(self) -> MarketContext | None:
        for provider in self.providers:
            try:
                context = await provider.get_market_context()
                if context:
                    return context
            except Exception:
                continue
        return None

    async def health(self) -> list[dict[str, Any]]:
        return await asyncio.gather(*(provider.health() for provider in self.providers))
