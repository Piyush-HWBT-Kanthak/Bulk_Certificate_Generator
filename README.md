# Bulk Certificate Generator

A FastAPI-based web service for generating and managing bulk certificate requests. Submit many recipient names at once, track progress in real-time, and download individual certificates on demand.

## Features

- **Bulk Processing**: Submit up to 1,000 recipient records in a single request
- **Asynchronous Generation**: Certificates are generated in the background without blocking the API
- **Robust Error Handling**: Invalid recipient data skips only that person; valid recipients still get certificates
- **Progress Tracking**: Monitor job status and per-recipient results via REST API
- **Per-Person Error Messages**: Understand exactly why each invalid recipient was rejected
- **Isolated Failures**: One certificate generation failure doesn't crash the entire job
- **Scalable Architecture**: Foundation for distributed processing without queue infrastructure

## Tech Stack

- **Framework**: FastAPI + Uvicorn
- **Database**: SQLAlchemy ORM with SQLite (easily switched to PostgreSQL)
- **Certificate Generation**: Pillow (PIL) for image manipulation
- **Validation**: Pydantic
- **Testing**: pytest with TestClient

## Project Structure

```
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
└── README.md
```

## Setup & Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Clone the Repository

```bash
git clone https://github.com/Piyush-HWBT-Kanthak/Bulk_Certificate_Generator.git
cd Bulk_Certificate_Generator
```

### Step 2: Create a Virtual Environment

```bash
# On macOS/Linux
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r new_requirements.txt
```

This will install:
- `fastapi` - Modern web framework
- `uvicorn` - ASGI server
- `sqlalchemy` - ORM for database
- `pydantic` - Data validation
- `Pillow>=10.1` - Image processing
- `pytest` - Testing framework
- `httpx` - HTTP client for tests

### Step 4: Database Setup

The database is automatically initialized when the application starts. It uses SQLite by default (stored as `app.db`).

**To use PostgreSQL instead**, set the `DATABASE_URL` environment variable:

```bash
export DATABASE_URL="postgresql://username:password@localhost:5432/certificates"
```

## Running the Application

### Start the Development Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

**Swagger UI (Interactive Documentation)**: `http://localhost:8000/docs`  
**ReDoc (Alternative Documentation)**: `http://localhost:8000/redoc`

### Run with Custom Port

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Specific Test File

```bash
pytest tests/test_app.py -v
```

### Run Tests with Coverage

```bash
pip install pytest-cov
pytest --cov=app tests/
```

**Test Coverage Includes:**
- Input validation (names, emails, request envelope)
- Job creation and status tracking
- Certificate generation and PNG format validation
- Per-recipient error isolation
- Progress percentage calculation
- Certificate download and access control

## How to Submit a Certificate Generation Request

### Submit a Bulk Job (HTTP POST)

**Endpoint**: `POST /api/jobs`

**Request Body** (JSON):

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

**Response** (HTTP 202 Accepted):

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
print(f"Job ID: {job_data['job_id']}")
print(f"Status: {job_data['status']}")
```

### Input Validation Rules

**Name Requirements:**
- 1–50 characters
- Must start with a letter
- Allowed characters: letters, spaces, dots (`.`), apostrophes (`'`), hyphens (`-`)
- Examples: ✅ "Alice Johnson", "Mary-Jane O'Neil", "Dr. Kalam"
- Counter-examples: ❌ "Bob123", "123Alice", "<script>alert('xss')</script>"

**Email Requirements:**
- 3–100 characters
- Valid email format: `something@something.something`
- No spaces allowed
- Examples: ✅ "alice@example.com", "user.name+tag@company.co.uk"
- Counter-examples: ❌ "not-an-email", "user@domain", "user @example.com"

**Limits:**
- Minimum recipients per job: 1
- Maximum recipients per job: 1,000

### Error Handling

- **Invalid recipient**: Skipped with error message; doesn't affect valid recipients
- **All invalid**: Job marked as "FAILED"
- **Mix of valid & invalid**: Job marked as "COMPLETED_WITH_ERRORS"

Example response when some recipients fail validation:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "message": "Job accepted. 2 recipient(s) are being processed in the background; 3 skipped because of invalid data."
}
```

## How to Retrieve Generated Certificates

### Check Job Status & Progress

**Endpoint**: `GET /api/jobs/{job_id}`

**Response** (JSON):

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
    },
    {
      "id": 2,
      "position": 1,
      "name": "Bob Smith",
      "email": "bob@example.com",
      "status": "SUCCESS",
      "file_path": "media/550e8400-e29b-41d4-a716-446655440000/2.png",
      "error_message": null
    }
  ]
}
```

### Download a Certificate (PNG)

**Endpoint**: `GET /api/jobs/{job_id}/certificates/{recipient_id}`

**Response**: Binary PNG file (image/png)

### cURL Example

```bash
# Get job status
curl "http://localhost:8000/api/jobs/550e8400-e29b-41d4-a716-446655440000"

# Download certificate for recipient 1
curl "http://localhost:8000/api/jobs/550e8400-e29b-41d4-a716-446655440000/certificates/1" \
  -o certificate_alice.png
```

### Python Example

```python
import requests

job_id = "550e8400-e29b-41d4-a716-446655440000"

# Get job status
status_response = requests.get(f"http://localhost:8000/api/jobs/{job_id}")
status_data = status_response.json()
print(f"Job Status: {status_data['status']}")
print(f"Progress: {status_data['progress_percent']}%")

# Download certificate for recipient
recipient_id = 1
cert_response = requests.get(
    f"http://localhost:8000/api/jobs/{job_id}/certificates/{recipient_id}"
)

if cert_response.status_code == 200:
    with open("certificate.png", "wb") as f:
        f.write(cert_response.content)
    print("Certificate downloaded successfully!")
```

### Job Status Lifecycle

1. **PENDING** → Job accepted, waiting to start processing
2. **PROCESSING** → Background worker is generating certificates
3. **COMPLETED** → All certificates generated successfully
4. **COMPLETED_WITH_ERRORS** → Some certificates generated, some failed
5. **FAILED** → No certificates were generated (all were invalid or all generation attempts failed)

## Important Implementation & Design Choices

### 1. **Asynchronous Background Processing**

- Certificate generation runs in FastAPI's background tasks (not a separate queue)
- Allows immediate API response (HTTP 202 Accepted) while processing happens in parallel
- **Trade-off**: Single-process only; for true scalability, replace with Celery + Redis

### 2. **Per-Recipient Error Isolation**

- Invalid data (bad email, bad name) causes that recipient to be rejected at submission time
- One generation failure (e.g., Pillow crash) doesn't stop processing for other recipients
- Each recipient committed to DB independently so progress is visible during processing

### 3. **Validation at Two Stages**

- **Submission time** (main.py): Parse request, validate each recipient separately
- **Generation time** (worker.py): Handle runtime errors without crashing the job

### 4. **SQLite with Fallback Support**

- Default: SQLite for simplicity (no external setup)
- Flexible: Configured via `DATABASE_URL` environment variable
- Easy migration to PostgreSQL for production without code changes

### 5. **Certificate Template Auto-Generation**

- If `assets/template.png` doesn't exist, it's created automatically
- Uses Pillow's scalable default font (no font file dependencies)
- Template is a simple 800×600 PNG with decorative border and placeholder text

### 6. **Adaptive Font Sizing**

- Long names automatically shrink to fit on the certificate
- Minimum font size: 16px (prevents names from becoming unreadable)
- Prevents layout breaking on extremely long names (e.g., "W" × 50)

### 7. **Progress Calculation**

- Real-time: `progress = (success_count + failed_count) / total_records`
- Visible during processing (background commits after each recipient)
- Reaches 100% only when job is completed or failed

### 8. **Database Schema**

- **Jobs Table**: Tracks overall job status, counts, timestamps
- **Recipients Table**: Tracks each person's outcome, error messages, file paths
  - Supports nullable `name` and `email` (for records of invalid submissions)
  - One-to-many relationship: One job → Many recipients

### 9. **File Storage**

- Certificates stored on disk: `media/{job_id}/{recipient_id}.png`
- File path tracked in DB for download routing
- `.gitignore` prevents checking in generated files

### 10. **Comprehensive Test Suite**

- Test isolation: Clean DB + clean filesystem before each test
- 39 test cases covering:
  - Happy path (valid recipients)
  - Error handling (invalid data, partial failures)
  - API contracts (status codes, response shapes)
  - Edge cases (empty names, very long names, non-dict objects)
  - Concurrency safety (monkeypatching to control timing)

### 11. **Stateless API Design**

- No in-memory state; all data persisted to database
- Safe for horizontal scaling (multiple API instances)
- Job status always queryable, even after server restart

### 12. **Graceful Degradation**

- Request accepted even if some recipients are invalid
- Job marked with appropriate status (COMPLETED_WITH_ERRORS or FAILED)
- Error messages explain what went wrong for each recipient

## Common Issues & Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'app'`

**Solution**: Ensure you're running from the project root directory and have activated the virtual environment.

```bash
cd Bulk_Certificate_Generator
source venv/bin/activate  # macOS/Linux
python -m uvicorn app.main:app --reload
```

### Issue: `sqlite3.OperationalError: no such table: jobs`

**Solution**: The database table is created automatically on startup. If this fails:

```bash
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### Issue: Certificate image appears blank or unreadable

**Solution**: Check that the `assets/` directory was created and contains `template.png`. If not:

```bash
python -c "from app.generator import ensure_template_exists; ensure_template_exists()"
```

### Issue: Tests fail with permission errors on Windows

**Solution**: Ensure the `media/` and `assets/` directories are not locked by other processes.

## Performance Considerations

- **Small batches**: 10–100 recipients → completes in seconds
- **Medium batches**: 100–500 recipients → completes in 30 seconds
- **Large batches**: 500–1,000 recipients → completes in 1–2 minutes

Generation speed is primarily limited by disk I/O. For production:
- Consider background job queues (Celery + Redis)
- Use a CDN for certificate download
- Implement cleanup jobs to remove old certificates

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///app.db` | Database connection string |
| `ASSETS_DIR` | `assets` | Directory for certificate templates |
| `MEDIA_DIR` | `media` | Directory for generated certificates |

Example:

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/certificates"
export ASSETS_DIR="/mnt/certificates/assets"
export MEDIA_DIR="/mnt/certificates/media"
uvicorn app.main:app
```

## License

This project is open source and available under the MIT License.

## Support & Contributing

For issues, questions, or contributions:

1. Check existing GitHub issues
2. Create a new issue with details
3. Fork the repository and submit a pull request

---

**API Documentation**: Once running, visit `http://localhost:8000/docs` for interactive Swagger UI.
