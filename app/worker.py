from app.database import SessionLocal
from app.models import Job
from app.generator import generate_certificate


def process_certificate_job(job_id: str):
    """Processes recipients in the background with isolated error handling."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        job.status = "PROCESSING"
        db.commit()

        for recipient in job.recipients:
            # People rejected by validation were already saved as FAILED - skip them.
            if recipient.status != "PENDING":
                continue

            try:
                file_path = generate_certificate(
                    job_id=job.id,
                    recipient_id=recipient.id,
                    recipient_name=recipient.name
                )
                recipient.file_path = file_path
                recipient.status = "SUCCESS"
                job.success_count += 1
            except Exception as exc:
                # Isolate failure: update this recipient only, do not crash the loop
                recipient.status = "FAILED"
                recipient.error_message = f"Generation error: {exc}"
                job.failed_count += 1

            db.commit()  # commit after every person so progress is visible while we work

        # Final job status evaluation
        if job.success_count == 0:
            job.status = "FAILED"
        elif job.failed_count > 0:
            job.status = "COMPLETED_WITH_ERRORS"
        else:
            job.status = "COMPLETED"

        db.commit()
    except Exception:
        # Something bigger than one recipient broke
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "FAILED"
            db.commit()
    finally:
        db.close()
