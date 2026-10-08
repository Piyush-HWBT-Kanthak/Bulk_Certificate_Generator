import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base

class Job(Base):
    """One bulk request."""
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # PENDING -> PROCESSING -> COMPLETED / COMPLETED_WITH_ERRORS / FAILED
    status = Column(String, default="PENDING")
    total_records = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    recipients = relationship("Recipient", back_populates="job", order_by="Recipient.id")


class Recipient(Base):
    """One person inside a bulk request (including people we had to skip)."""
    __tablename__ = "recipients"

    id = Column(Integer, primary_key=True)
    job_id = Column(String, ForeignKey("jobs.id"), index=True)
    position = Column(Integer)                      # place in the submitted list (0 = first)
    name = Column(String, nullable=True)            # nullable: a bad request may have no name
    email = Column(String, nullable=True)           # nullable: a bad request may have no email
    status = Column(String, default="PENDING")      # PENDING / SUCCESS / FAILED
    file_path = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    job = relationship("Job", back_populates="recipients")
