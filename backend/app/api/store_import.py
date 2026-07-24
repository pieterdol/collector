"""Router factory for launcher-file imports (Epic, GOG).

Both stores expose the same three endpoints — upload, poll, confirm —
over the same reviewed-job machinery, differing only in their StoreSpec.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core import import_jobs
from app.core.library_import import StoreSpec, import_selected, parse_upload, prepare_review
from app.core.security import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.library_import import ConfirmIn, ImportJobOut, JobStartOut


def build_store_router(prefix: str, tag: str, spec: StoreSpec) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.post("/import", response_model=JobStartOut, status_code=202)
    async def start_import(
        background: BackgroundTasks,
        file: UploadFile = File(...),
        user: User = Depends(get_current_user),
    ) -> JobStartOut:
        """Upload a library file; the job pauses in review for confirmation."""
        entries = parse_upload(await file.read(), spec)  # 400s on a bad file
        job_id = import_jobs.create(owner_id=user.id)
        background.add_task(prepare_review, job_id, user.id, entries, spec)
        return JobStartOut(job_id=job_id)

    @router.get("/import/{job_id}", response_model=ImportJobOut)
    def import_status(
        job_id: str,
        user: User = Depends(get_current_user),
    ) -> ImportJobOut:
        job = _owned_job(job_id, user)
        return ImportJobOut(
            **{k: v for k, v in job.items() if not k.startswith("_") and k != "owner_id"}
        )

    @router.post("/import/{job_id}/confirm", response_model=JobStartOut, status_code=202)
    def confirm_import(
        job_id: str,
        body: ConfirmIn,
        background: BackgroundTasks,
        user: User = Depends(get_current_user),
        _db: Session = Depends(get_db),
    ) -> JobStartOut:
        """Create items for the selected title ids of a job in review."""
        job = _owned_job(job_id, user)
        if job["status"] != "review":
            raise HTTPException(status_code=409, detail="This import is not awaiting review")
        import_jobs.update(job_id, status="running", phase="Adding games")
        background.add_task(import_selected, job_id, user.id, body.title_ids, spec)
        return JobStartOut(job_id=job_id)

    return router


def _owned_job(job_id: str, user: User) -> dict:
    job = import_jobs.get(job_id)
    if job is None or job["owner_id"] != user.id:
        raise HTTPException(status_code=404, detail="Import job not found")
    return job


def owner_id_of(job_id: str) -> uuid.UUID | None:
    job = import_jobs.get(job_id)
    return job["owner_id"] if job else None
