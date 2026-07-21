from datetime import UTC, datetime

import pytest

from portfolio_monitor.alerts import AlertManager
from portfolio_monitor.models import Recommendation, Severity, SignalStatus


class Notifier:
    def __init__(self): self.calls = 0
    async def send(self, alert_id, alert): self.calls += 1; return True


def recommendation(rule="technology_stage_1_159995"):
    return Recommendation(status=SignalStatus.ELIGIBLE, severity=Severity.ACTION, module="technology",
                          symbol="159995.SZ", rule_id=rule, max_amount_cny=15000, evidence=["x"],
                          data_as_of=datetime.now(UTC), config_version="2026-07-20")


@pytest.mark.asyncio
async def test_alert_dedup_and_hard_risk_snooze(database):
    notifier = Notifier(); manager = AlertManager(database, notifier)
    first = await manager.process_recommendations([recommendation()])
    second = await manager.process_recommendations([recommendation()])
    assert first[0]["new"] is True and second[0]["new"] is False
    assert notifier.calls == 1
    hard = recommendation("technology_support_break").model_copy(update={"status": SignalStatus.BLOCKED, "severity": Severity.RISK})
    row = (await manager.process_recommendations([hard]))[0]
    with pytest.raises(ValueError): manager.snooze(row["alert_id"], 30)
