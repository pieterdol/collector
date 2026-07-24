"""In-process progress registry for long-running library imports.

Collector runs as a single uvicorn worker, so a module-level dict is
enough. Jobs are ephemeral status records — a restart loses the status
display, never data. The registry keeps only the most recent jobs.
"""

import threading
import uuid

_MAX_JOBS = 50

_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def create(owner_id: uuid.UUID) -> str:
    job_id = uuid.uuid4().hex
    with _lock:
        while len(_jobs) >= _MAX_JOBS:
            _jobs.pop(next(iter(_jobs)))
        _jobs[job_id] = {
            "owner_id": owner_id,
            "status": "running",
            "phase": "Starting",
            "done": 0,
            "total": 0,
            "imported": None,
            "skipped": None,
            "detail": None,
        }
    return job_id


def update(job_id: str, **fields) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is not None:
            job.update(fields)


def finish(job_id: str, imported: int, skipped: int, total: int) -> None:
    update(
        job_id,
        status="done",
        phase="Done",
        imported=imported,
        skipped=skipped,
        total=total,
    )


def fail(job_id: str, detail: str) -> None:
    update(job_id, status="error", phase="Failed", detail=detail)


def get(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job is not None else None
