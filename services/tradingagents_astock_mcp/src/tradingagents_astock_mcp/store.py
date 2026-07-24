from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

from .models import RunRecord

_RUN_ID = re.compile(r"^[0-9a-f]{32}$")


class RunStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def run_dir(self, run_id: str) -> Path:
        if not _RUN_ID.fullmatch(run_id):
            raise ValueError("invalid run_id")
        candidate = (self.root / run_id).resolve()
        if candidate.parent != self.root:
            raise ValueError("invalid run_id")
        return candidate

    def create(self, record: RunRecord) -> None:
        directory = self.run_dir(record.run_id)
        with self._lock:
            directory.mkdir(mode=0o700)
            self.save(record)

    def save(self, record: RunRecord) -> None:
        directory = self.run_dir(record.run_id)
        path = directory / "run.json"
        temporary = directory / ".run.json.tmp"
        payload = record.model_dump_json(indent=2)
        with self._lock:
            temporary.write_text(payload + "\n", encoding="utf-8")
            os.replace(temporary, path)

    def get(self, run_id: str) -> RunRecord:
        path = self.run_dir(run_id) / "run.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValueError(f"research run not found: {run_id}") from exc
        return RunRecord.model_validate(payload)

    def list(self, limit: int = 50) -> list[RunRecord]:
        records: list[RunRecord] = []
        with self._lock:
            for path in self.root.glob("*/run.json"):
                if not _RUN_ID.fullmatch(path.parent.name):
                    continue
                try:
                    records.append(RunRecord.model_validate_json(path.read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    continue
        records.sort(key=lambda item: item.created_at, reverse=True)
        return records[:limit]

    def recover_interrupted(self) -> int:
        recovered = 0
        for record in self.list(limit=100_000):
            if record.status in {"queued", "running"}:
                record.status = "failed"
                record.completed_at = record.completed_at or record.created_at
                record.error = {"code": "server_restarted", "message": "Run interrupted by server restart"}
                self.save(record)
                recovered += 1
        return recovered
