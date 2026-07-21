from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx

from .db import Database
from .models import AlertRecord, Recommendation, Severity, SignalStatus


HARD_RISK_PREFIXES = (
    "portfolio_drawdown_",
    "technology_drawdown_",
    "technology_support_break",
    "cash_floor_",
)


class Notifier(Protocol):
    async def send(self, alert_id: int, alert: AlertRecord) -> bool: ...


class OpenClawWebhookNotifier:
    def __init__(self, url: str | None = None, token: str | None = None, timeout: float = 10):
        self.url = url or os.getenv("OPENCLAW_WEBHOOK_URL")
        self.token = token or os.getenv("OPENCLAW_WEBHOOK_TOKEN")
        self.timeout = timeout

    async def send(self, alert_id: int, alert: AlertRecord) -> bool:
        if not self.url:
            return False
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        payload = {
            "event": "ai_berkshire.portfolio_alert",
            "alert_id": alert_id,
            "severity": alert.severity.value,
            "title": f"[{alert.severity.value.upper()}] {alert.module} {alert.rule_id}",
            "message": alert.message,
            "data": alert.payload,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.url, json=payload, headers=headers)
                response.raise_for_status()
            return True
        except Exception:
            return False


class AlertManager:
    def __init__(self, database: Database, notifier: Notifier | None = None):
        self.database = database
        self.notifier = notifier or OpenClawWebhookNotifier()

    async def process_recommendations(self, recommendations: list[Recommendation]) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        for recommendation in recommendations:
            if recommendation.status == SignalStatus.WATCH and recommendation.severity in (Severity.INFO, Severity.WATCH):
                continue
            alert = self._to_alert(recommendation)
            alert_id, is_new = self.database.upsert_alert(alert)
            delivered = False
            if is_new:
                delivered = await self.notifier.send(alert_id, alert)
                self.database.update_alert(alert_id, delivery_status="delivered" if delivered else "pending")
            created.append({"alert_id": alert_id, "new": is_new, "delivered": delivered, "rule_id": alert.rule_id})
        return created

    async def retry_pending(self) -> list[int]:
        delivered: list[int] = []
        for row in self.database.list_alerts(status="open"):
            if row["delivery_status"] != "pending":
                continue
            if row["snoozed_until"] and datetime.fromisoformat(row["snoozed_until"]) > datetime.now(UTC):
                continue
            alert = AlertRecord(
                id=row["id"],
                dedup_key=row["dedup_key"],
                rule_id=row["rule_id"],
                symbol=row["symbol"],
                module=row["module"],
                severity=Severity(row["severity"]),
                status=row["status"],
                message=row["message"],
                payload=row["payload"],
                first_triggered_at=datetime.fromisoformat(row["first_triggered_at"]),
                last_triggered_at=datetime.fromisoformat(row["last_triggered_at"]),
                acknowledged_at=datetime.fromisoformat(row["acknowledged_at"]) if row["acknowledged_at"] else None,
                snoozed_until=datetime.fromisoformat(row["snoozed_until"]) if row["snoozed_until"] else None,
                delivery_status=row["delivery_status"],
            )
            if await self.notifier.send(int(row["id"]), alert):
                self.database.update_alert(int(row["id"]), delivery_status="delivered")
                delivered.append(int(row["id"]))
        return delivered

    def acknowledge(self, alert_id: int) -> None:
        self.database.update_alert(alert_id, status="acknowledged", acknowledged_at=datetime.now(UTC))

    def snooze(self, alert_id: int, minutes: int) -> None:
        row = next((item for item in self.database.list_alerts() if int(item["id"]) == alert_id), None)
        if not row:
            raise ValueError(f"alert {alert_id} not found")
        if row["rule_id"].startswith(HARD_RISK_PREFIXES):
            raise ValueError("hard portfolio risk alerts cannot be snoozed")
        self.database.update_alert(alert_id, snoozed_until=datetime.now(UTC) + timedelta(minutes=minutes))

    @staticmethod
    def _to_alert(recommendation: Recommendation) -> AlertRecord:
        day = recommendation.data_as_of.date().isoformat()
        symbol = recommendation.symbol or "portfolio"
        # Severity is part of the key so escalation can create a new notification.
        dedup_key = f"{recommendation.rule_id}:{symbol}:{day}:{recommendation.severity.value}"
        message_parts = [
            f"状态={recommendation.status.value}",
            f"最大授权={recommendation.max_amount_cny:.0f}元",
        ]
        if recommendation.evidence:
            message_parts.append("证据=" + "；".join(recommendation.evidence))
        if recommendation.blocking_reasons:
            message_parts.append("阻断=" + "；".join(recommendation.blocking_reasons))
        now = datetime.now(UTC)
        return AlertRecord(
            dedup_key=dedup_key,
            rule_id=recommendation.rule_id,
            symbol=recommendation.symbol,
            module=recommendation.module,
            severity=recommendation.severity,
            message=" | ".join(message_parts),
            payload=recommendation.model_dump(mode="json"),
            first_triggered_at=now,
            last_triggered_at=now,
        )
