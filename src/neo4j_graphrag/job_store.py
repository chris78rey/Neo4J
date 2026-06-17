from __future__ import annotations

import json
from pathlib import Path
from threading import Lock


class JobStore:
    def get(self, job_id: str) -> dict[str, str] | None:
        raise NotImplementedError

    def set(self, job_id: str, payload: dict[str, str]) -> None:
        raise NotImplementedError

    def list(self) -> dict[str, dict[str, str]]:
        raise NotImplementedError

    def list_by_prefix(self, prefix: str) -> dict[str, dict[str, str]]:
        raise NotImplementedError

    def delete(self, job_id: str) -> None:
        raise NotImplementedError


class MemoryJobStore(JobStore):
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, str]] = {}

    def get(self, job_id: str) -> dict[str, str] | None:
        return self._jobs.get(job_id)

    def set(self, job_id: str, payload: dict[str, str]) -> None:
        self._jobs[job_id] = payload

    def list(self) -> dict[str, dict[str, str]]:
        return dict(self._jobs)

    def list_by_prefix(self, prefix: str) -> dict[str, dict[str, str]]:
        return {key: value for key, value in self._jobs.items() if key.startswith(prefix)}

    def delete(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)


class FileJobStore(JobStore):
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def _read(self) -> dict[str, dict[str, str]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write(self, payload: dict[str, dict[str, str]]) -> None:
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def get(self, job_id: str) -> dict[str, str] | None:
        with self._lock:
            return self._read().get(job_id)

    def set(self, job_id: str, payload: dict[str, str]) -> None:
        with self._lock:
            jobs = self._read()
            jobs[job_id] = payload
            self._write(jobs)

    def list(self) -> dict[str, dict[str, str]]:
        with self._lock:
            return self._read()

    def list_by_prefix(self, prefix: str) -> dict[str, dict[str, str]]:
        with self._lock:
            jobs = self._read()
            return {key: value for key, value in jobs.items() if key.startswith(prefix)}

    def delete(self, job_id: str) -> None:
        with self._lock:
            jobs = self._read()
            jobs.pop(job_id, None)
            self._write(jobs)


_JOB_STORE: JobStore | None = None


def get_job_store(path: str | None = None) -> JobStore:
    global _JOB_STORE
    if _JOB_STORE is not None:
        return _JOB_STORE
    if path:
        _JOB_STORE = FileJobStore(path)
    else:
        _JOB_STORE = MemoryJobStore()
    return _JOB_STORE
