from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

MAX_RECIPIENTS = 1000

# Name: letters, spaces, dots, apostrophes, hyphens. Must start with a letter.
#   OK: "Alice Johnson", "Mary-Jane O'Neil"      NOT OK: "Bob123", "", "<b>"
NAME_PATTERN = r"^[A-Za-z][A-Za-z .'\-]*$"
# Email: something@something.something with no spaces.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RecipientInput(BaseModel):
    """Rules for ONE person. name and email follow the same style: required,
    length limit, pattern. If either breaks a rule, only this person is skipped."""
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=50, pattern=NAME_PATTERN,
                      description="Recipient's full name (letters, spaces, . ' -)")
    email: str = Field(..., min_length=3, max_length=100, pattern=EMAIL_PATTERN,
                       description="Valid recipient email address")


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={  # pre-fills the Swagger "Try it out" box
            "example": {
                "recipients": [
                    {"name": "Alice Johnson", "email": "alice@example.com"},
                    {"name": "Bob Smith", "email": "bob@example.com"},
                    {"email": "no.name@example.com"},
                    {"name": "No Email"},
                    {"name": "Bad Email", "email": "not-an-email"},
                ]
            }
        }
    )

    # "Any" on purpose: each person is checked separately in main.py (RecipientInput),
    # so one bad person cannot reject the whole request.
    recipients: List[Any] = Field(
        ..., min_length=1, max_length=MAX_RECIPIENTS, description="Batch list of recipients"
    )


class RecipientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    name: Optional[str] = None
    email: Optional[str] = None
    status: str
    file_path: Optional[str] = None
    error_message: Optional[str] = None


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: str
    total_records: int
    success_count: int
    failed_count: int
    progress_percent: float
    created_at: datetime
    recipients: List[RecipientResponse]


class JobCreateResponse(BaseModel):
    job_id: str
    status: str
    message: str
