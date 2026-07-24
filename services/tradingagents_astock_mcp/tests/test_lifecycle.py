import asyncio
from pathlib import Path

import pytest

from tradingagents_astock_mcp.config import Settings
from tradingagents_astock_mcp.service import ResearchService


class BlockingFakeWorker:
    def __init__(self):
        self.active = 0
        self.max_active = 0

    async def run(self, request, run_dir: Path):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.02)
        self.active -= 1
        return {
            "schema_version": 1,
            "company_of_interest": request.ticker,
            "trade_date": request.trade_date,
            "signal": "Hold",
            "analyst_reports": {},
        }


class FailingFakeWorker:
    async def run(self, request, run_dir: Path):
        raise RuntimeError("synthetic worker failure")


async def wait_completed(service, run_id):
    for _ in range(100):
        status = service.status(run_id)
        if status["status"] in {"completed", "failed"}:
            return status
        await asyncio.sleep(0.01)
    raise AssertionError("run did not finish")


@pytest.mark.asyncio
async def test_persisted_lifecycle_and_concurrency_cap(tmp_path):
    worker = BlockingFakeWorker()
    service = ResearchService(Settings(data_dir=tmp_path, max_concurrent=1), worker=worker)
    first = await service.start("600519.SH", "2026-01-05", ["market"], 1)
    second = await service.start("000001", "2026-01-05", ["fundamentals"], 3)
    assert first["status"] == "queued"
    assert second["status"] == "queued"
    first_status, second_status = await asyncio.gather(
        wait_completed(service, first["run_id"]),
        wait_completed(service, second["run_id"]),
    )
    assert first_status["status"] == second_status["status"] == "completed"
    assert first_status["request"]["ticker"] == "600519"
    assert worker.max_active == 1
    assert service.result(first["run_id"])["result"]["company_of_interest"] == "600519"
    assert service.result(first["run_id"])["result"]["signal"] == "Hold"
    assert "result" not in service.list_runs()[0]

    restarted = ResearchService(Settings(data_dir=tmp_path), worker=worker)
    assert restarted.status(first["run_id"])["status"] == "completed"
    await service.close()
    await restarted.close()


@pytest.mark.asyncio
async def test_failed_worker_is_persisted_without_result(tmp_path):
    service = ResearchService(Settings(data_dir=tmp_path), worker=FailingFakeWorker())
    started = await service.start("600519", "2026-01-05", ["market"], 1)
    status = await wait_completed(service, started["run_id"])
    assert status["status"] == "failed"
    assert status["error"]["code"] == "worker_failed"
    with pytest.raises(ValueError, match="not completed"):
        service.result(started["run_id"])
    await service.close()
