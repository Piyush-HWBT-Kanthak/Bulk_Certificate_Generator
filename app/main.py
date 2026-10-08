import os
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.models import Job, Recipient
from app.schemas import (
    JobCreateRequest, JobCreateResponse, JobStatusResponse, RecipientInput,
)
from app.worker import process_certificate_job


# Auto-generate DB tables on startup
Base.metadata.create_all(bind=engine)

# Swagger UI is available at /docs  (and ReDoc at /redoc)
app = FastAPI(
    title="Bulk Certificate Generator API",
    description="Submit many recipients in ONE request, track progress, download certificates.",
)


def _as_text(value):
    """Whatever the client sent, as short text (or None if it was missing)."""
    return None if value is None else str(value)[:100]


def _describe(error: ValidationError) -> str:
    """One readable line, e.g. 'name: Field required; email: Field required'."""
    return "; ".join(
        f"{e['loc'][0] if e['loc'] else 'recipient'}: {e['msg']}" for e in error.errors()
    )


@app.post(
    "/api/jobs",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Jobs"],
    summary="Submit a bulk certificate request",
)
def create_generation_job(
    payload: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Submits a bulk certificate request and begins processing in background.

    Every recipient is validated separately. A recipient with a missing or invalid
    name/email is SKIPPED (saved as FAILED with the reason); everyone else still
    gets a certificate."""
    job = Job(total_records=len(payload.recipients), status="PENDING",
              success_count=0, failed_count=0)
    db.add(job)
    db.flush()  # gives the job its id

    valid_count = 0
    for position, raw in enumerate(payload.recipients):
        try:
            item = RecipientInput.model_validate(raw)
            db.add(Recipient(job_id=job.id, position=position, name=item.name,
                             email=item.email, status="PENDING"))
            valid_count += 1
        except ValidationError as exc:
            sent = raw if isinstance(raw, dict) else {}
            db.add(Recipient(job_id=job.id, position=position,
                             name=_as_text(sent.get("name")), email=_as_text(sent.get("email")),
                             status="FAILED", error_message=_describe(exc)))
            job.failed_count += 1

    skipped = job.failed_count
    if valid_count == 0:
        job.status = "FAILED"  # nobody valid, so there is nothing to generate
    db.commit()
    db.refresh(job)

    if valid_count > 0:
        # Queue background task
        background_tasks.add_task(process_certificate_job, job.id)

    return JobCreateResponse(
        job_id=job.id,
        status=job.status,
        message=(f"Job accepted. {valid_count} recipient(s) are being processed in the background; "
                 f"{skipped} skipped because of invalid data.")
    )


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse, tags=["Jobs"],
         summary="Job status, progress and per-recipient results")
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Fetches job status, metrics, and individual recipient outcomes."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    done = job.success_count + job.failed_count
    progress = round(100 * done / job.total_records, 1) if job.total_records else 100.0

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        total_records=job.total_records,
        success_count=job.success_count,
        failed_count=job.failed_count,
        progress_percent=progress,
        created_at=job.created_at,
        recipients=job.recipients
    )


@app.get("/api/jobs/{job_id}/certificates/{recipient_id}", tags=["Certificates"],
         summary="Download one certificate (PNG)")
def download_certificate(
    job_id: str,
    recipient_id: int,
    db: Session = Depends(get_db)
):
    """Streams the generated certificate file for a given recipient."""
    recipient = db.query(Recipient).filter(
        Recipient.id == recipient_id,
        Recipient.job_id == job_id
    ).first()

    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    if recipient.status != "SUCCESS" or not recipient.file_path:
        raise HTTPException(
            status_code=400,
            detail=f"Certificate unavailable. Status: {recipient.status}. Error: {recipient.error_message}"
        )

    if not os.path.exists(recipient.file_path):
        raise HTTPException(status_code=404, detail="Certificate file missing on disk")

    return FileResponse(
        recipient.file_path,
        media_type="image/png",
        filename=f"certificate_{recipient.id}.png"
    )
