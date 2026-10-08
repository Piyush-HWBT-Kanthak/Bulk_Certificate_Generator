# Bulk Certificate Generator

A FastAPI-based web service for generating and managing bulk certificate requests. Submit many recipient names at once, track progress in real time, and download individual certificates on demand.

## Features

- **Bulk Processing**: Submit up to 1,000 recipient records in a single request
- **Background Job Processing**: Certificates are generated after the API accepts the request, without blocking the response
- **Robust Error Handling**: Invalid recipient data is skipped only for that person; valid recipients still get certificates
- **Progress Tracking**: Monitor job status and per-recipient results through the API
- **Per-Person Error Messages**: Understand exactly why a specific recipient was rejected
- **Isolated Failures**: One certificate generation failure does not stop the rest of the job

## Tech Stack

- **Framework**: FastAPI + Uvicorn
- **Database**: SQLAlchemy ORM with SQLite
- **Certificate Generation**: Pillow (PIL)
- **Validation**: Pydantic
- **Testing**: pytest + TestClient

## Project Structure

```text
Bulk_Certificate_Generator/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI routes and job creation logic
│   ├── models.py               # SQLAlchemy database models
│   ├── schemas.py              # Pydantic validation schemas
│   ├── database.py             # Database connection and session management
│   ├── generator.py            # Certificate image generation
│   └── worker.py               # Background certificate processing
├── tests/
│   └── test_app.py             # Comprehensive test suite
├── new_requirements.txt         # Python dependencies
├── pytest.ini                   # pytest configuration
├── .gitignore
├── README.md
└── README_print.md              # PDF-friendly version for export/printing
```

## Setup & Installation

### Prerequisites

- Python 3.8 or higher
- pip

### 1) Clone the Repository

```bash
git clone https://github.com/Piyush-HWBT-Kanthak/Bulk_Certificate_Generator.git
cd Bulk_Certificate_Generator
```

### 2) Create a Virtual Environment

```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3) Install Dependencies

```bash
pip install -r new_requirements.txt
```

Installed packages include:
- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `pydantic`
- `Pillow>=10.1`
- `pytest`
- `httpx`

### 4) Database Setup

The app creates its database automatically when it starts. By default it uses SQLite and stores the database in `app.db`.

To use a different database, set `DATABASE_URL` before running the server:

```bash
export DATABASE_URL="postgresql://username:password@localhost:5432/certificates"
```

## Running the Application

### Start the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at:
- http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Run on a Custom Port

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Verbose Output

```bash
pytest -v
```

### Specific File

```bash
pytest tests/test_app.py -v
```

### With Coverage

```bash
pip install pytest-cov
pytest --cov=app tests/
```

## How to Submit a Certificate Generation Request

### Endpoint

`POST /api/jobs`

### Request Body

```json
{
  "recipients": [
    {
      "name": "Alice Johnson",
      "email": "alice@example.com"
    },
    {
      "name": "Bob Smith",
      "email": "bob@example.com"
    },
    {
      "name": "Carol Lee",
      "email": "carol@example.com"
    }
  ]
}
```

### Example Response

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "message": "Job accepted. 3 recipient(s) are being processed in the background; 0 skipped because of invalid data."
}
```

### cURL Example

```bash
curl -X POST "http://localhost:8000/api/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "recipients": [
      {"name": "Alice Johnson", "email": "alice@example.com"},
      {"name": "Bob Smith", "email": "bob@example.com"}
    ]
  }'
```

### Python Example

```python
import requests

url = "http://localhost:8000/api/jobs"
payload = {
    "recipients": [
        {"name": "Alice Johnson", "email": "alice@example.com"},
        {"name": "Bob Smith", "email": "bob@example.com"}
    ]
}

response = requests.post(url, json=payload)
job_data = response.json()
print(job_data)
```

### Validation Rules

**Name rules**
- 1–50 characters
- Must start with a letter
- Allowed characters: letters, spaces, dots, apostrophes, and hyphens
- Examples: "Alice Johnson", "Mary-Jane O'Neil", "Dr. Kalam"

**Email rules**
- 3–100 characters
- Must match a standard email format like `name@example.com`
- No spaces allowed

**Limits**
- Minimum recipients per request: 1
- Maximum recipients per request: 1,000

### Error Behavior

- Invalid recipients are saved with a failure status and a reason message
- Valid recipients continue to be processed
- If every recipient is invalid, the job is marked as `FAILED`
- If some are valid and some are invalid, the job is marked as `COMPLETED_WITH_ERRORS`

## How to Retrieve Generated Certificates

### Check Job Status

`GET /api/jobs/{job_id}`

Example response:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "total_records": 3,
  "success_count": 3,
  "failed_count": 0,
  "progress_percent": 100.0,
  "created_at": "2024-01-15T10:30:45.123456+00:00",
  "recipients": [
    {
      "id": 1,
      "position": 0,
      "name": "Alice Johnson",
      "email": "alice@example.com",
      "status": "SUCCESS",
      "file_path": "media/550e8400-e29b-41d4-a716-446655440000/1.png",
      "error_message": null
    }
  ]
}
```

### Download a Certificate

`GET /api/jobs/{job_id}/certificates/{recipient_id}`

This returns a PNG file for a successful recipient.

### cURL Example

```bash
curl "http://localhost:8000/api/jobs/550e8400-e29b-41d4-a716-446655440000" \
  -o job_status.json

curl "http://localhost:8000/api/jobs/550e8400-e29b-41d4-a716-446655440000/certificates/1" \
  -o certificate_alice.png
```

### Job Status Lifecycle

1. `PENDING` — job accepted and waiting to start
2. `PROCESSING` — generating certificates
3. `COMPLETED` — all valid recipients succeeded
4. `COMPLETED_WITH_ERRORS` — some succeeded, some failed
5. `FAILED` — no certificate generation completed successfully

## Important Implementation & Design Choices

### 1. Background Task Execution

This project uses FastAPI's `BackgroundTasks` to trigger certificate generation after returning an HTTP 202 response. The worker continues in the same process and commits each recipient result to the database as it finishes.

### 2. Per-Recipient Error Isolation

Each recipient is validated independently. A bad name or email only affects that individual record; the rest of the batch continues normally.

### 3. Two-Stage Validation

- Request validation occurs during job creation
- Runtime generation errors are caught inside the worker so a single failure does not crash the whole job

### 4. SQLite Default

The app uses SQLite by default for simplicity and easy setup. A different database can be used by setting `DATABASE_URL`.

### 5. Template Auto-Generation

If the certificate template is missing, the app creates one automatically in the `assets` directory. This keeps the project runnable without any external font or asset files.

### 6. Dynamic Font Sizing

The generator reduces font size automatically so long names still fit within the certificate layout without breaking the image.

### 7. Database-Backed Job State

Job state and recipient results are saved in the database. This allows status checks and certificate downloads after the request completes.

### 8. File-Based Certificate Storage

Generated certificate files are stored under `media/{job_id}/` and their file paths are tracked in the database for retrieval.

### 9. Test Coverage

The project includes 19 focused tests covering:
- valid and invalid input handling
- job creation and progress tracking
- certificate generation
- failure isolation
- download behavior
- Swagger/OpenAPI availability

## Common Troubleshooting

### Module import errors

```bash
cd Bulk_Certificate_Generator
source venv/bin/activate
python -m uvicorn app.main:app --reload
```

### Database table errors

```bash
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### Blank certificate issues

```bash
python -c "from app.generator import ensure_template_exists; ensure_template_exists()"
```

## Environment Variables

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/certificates"
uvicorn app.main:app
```

## License

This project is open source and available under the MIT License.

## Support & Contributing

For issues or contributions, check the GitHub repository and create a new issue or pull request.

---

API docs are available at http://localhost:8000/docs when the app is running.
