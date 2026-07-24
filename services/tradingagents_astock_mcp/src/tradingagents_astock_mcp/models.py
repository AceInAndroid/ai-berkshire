from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Analyst = Literal["market", "social", "news", "fundamentals", "policy", "hot_money", "lockup"]
RunStatus = Literal["queued", "running", "completed", "failed"]

DEFAULT_ANALYSTS: list[Analyst] = [
    "market",
    "social",
    "news",
    "fundamentals",
    "policy",
    "hot_money",
    "lockup",
]


class ResearchRequest(BaseModel):
    """The complete and deliberately small user-controlled input surface."""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    trade_date: str
    analysts: list[Analyst] = Field(default_factory=lambda: list(DEFAULT_ANALYSTS), min_length=1, max_length=7)
    research_depth: Literal[1, 3, 5] = 1

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("ticker must be a string")
        normalized = value.strip().upper()
        match = re.fullmatch(r"([0-9]{6})(?:\.(SH|SZ|BJ))?", normalized)
        if not match:
            raise ValueError("ticker must be six digits with optional .SH, .SZ, or .BJ suffix")
        code, suffix = match.groups()
        expected_exchange = None
        if code.startswith("6"):
            expected_exchange = "SH"
        elif code.startswith(("0", "3")):
            expected_exchange = "SZ"
        elif code.startswith(("4", "8", "92")):
            expected_exchange = "BJ"
        if suffix and suffix != expected_exchange:
            raise ValueError(f"ticker suffix .{suffix} does not match code family")
        return code

    @field_validator("trade_date")
    @classmethod
    def validate_trade_date(cls, value: str) -> str:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("trade_date must use YYYY-MM-DD") from exc
        if parsed > date.today():
            raise ValueError("trade_date cannot be in the future")
        return parsed.isoformat()

    @field_validator("analysts")
    @classmethod
    def analysts_must_be_unique(cls, value: list[Analyst]) -> list[Analyst]:
        if len(set(value)) != len(value):
            raise ValueError("analysts must not contain duplicates")
        return value


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    run_id: str
    status: RunStatus
    request: ResearchRequest
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: dict | None = None
    error: dict[str, str] | None = None
