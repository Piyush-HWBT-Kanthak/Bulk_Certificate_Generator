
import os
import tempfile


os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db").replace("\\", "/")

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from app import generator, main, worker
from app.database import Base, SessionLocal, engine
from app.main import app
from app.schemas import RecipientInput

# TestClient acts as a fake web browser. It also runs background tasks BEFORE it returns
# the response, so right after POST the certificates already exist (no waiting needed).
client = TestClient(app)


@pytest.fixture(autouse=True)  # autouse = runs automatically before EVERY test
def clean_state(tmp_path, monkeypatch):
    """Empty database + empty certificate folders for every test,
    so tests can never disturb each other (or your real data)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(generator, "ASSETS_DIR", str(tmp_path / "assets"))
    monkeypatch.setattr(generator, "MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setattr(generator, "TEMPLATE_PATH", str(tmp_path / "assets" / "template.png"))


def make_payload(*names):
    """Helper (not a test): a valid request for the given names."""
    return {"recipients": [{"name": n, "email": f"{n.lower()}@example.com"} for n in names]}


def is_rejected(**data):
    """Helper: True if ONE recipient with this data fails validation."""
    try:
        RecipientInput(**data)
        return False
    except ValidationError:
        return True


# =========================================================== 1. CREATING A JOB
def test_create_job_returns_202_and_job_id():
    response = client.post("/api/jobs", json=make_payload("Alice", "Bob", "Carol"))
    assert response.status_code == 202
    assert response.json()["job_id"]
    assert "3 recipient(s)" in response.json()["message"]


def test_valid_recipients_all_get_certificates():
    job_id = client.post("/api/jobs", json=make_payload("Alice", "Bob")).json()["job_id"]
    data = client.get(f"/api/jobs/{job_id}").json()
    assert data["status"] == "COMPLETED"
    assert data["total_records"] == 2
    assert data["success_count"] == 2
    assert data["failed_count"] == 0


# =========================================================== 2. INPUT VALIDATION
def test_whole_request_is_rejected_when_envelope_is_wrong():
    assert client.post("/api/jobs", json={"recipients": []}).status_code == 422   # empty list
    assert client.post("/api/jobs", json={}).status_code == 422                   # no recipients key
    too_many = {"recipients": [{}] * 1001}
    assert client.post("/api/jobs", json=too_many).status_code == 422             # over the limit


def test_good_names_are_accepted():
    for name in ["Alice Johnson", "Mary-Jane O'Neil", "Dr. Kalam"]:
        assert not is_rejected(name=name, email="a@example.com")


def test_bad_names_are_rejected():
    for name in ["", "   ", "Bob123", "<script>", "X" * 51]:
        assert is_rejected(name=name, email="a@example.com"), name


def test_bad_emails_are_rejected():
    for email in ["", "not-an-email", "a@b", "a b@c.com"]:
        assert is_rejected(name="Alice", email=email), email


def test_missing_name_or_email_is_rejected():
    assert is_rejected(email="a@example.com")   # no name
    assert is_rejected(name="Alice")            # no email
    assert is_rejected()                        # neither


def test_bad_people_are_skipped_and_good_people_still_get_certificates():
    """The key requirement: invalid data skips ONLY that person. Nothing crashes."""
    payload = {
        "recipients": [
            {"name": "Good One", "email": "good@example.com"},    # 0 ok
            {"email": "noname@example.com"},                       # 1 name missing
            {"name": "No Email"},                                  # 2 email missing
            {},                                                    # 3 both missing
            {"name": "Bob123", "email": "bob@example.com"},        # 4 bad name
            {"name": "Bad Email", "email": "nope"},                # 5 bad email
            "just text",                                           # 6 not even an object
            {"name": "Also Good", "email": "also@example.com"},    # 7 ok
        ]
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 202          # accepted, nothing crashed

    data = client.get(f"/api/jobs/{response.json()['job_id']}").json()
    assert data["status"] == "COMPLETED_WITH_ERRORS"
    assert data["success_count"] == 2
    assert data["failed_count"] == 6

    people = data["recipients"]
    assert [p["status"] for p in people] == ["SUCCESS"] + ["FAILED"] * 6 + ["SUCCESS"]
    assert "name" in people[1]["error_message"]
    assert "email" in people[2]["error_message"]
    assert "name" in people[3]["error_message"] and "email" in people[3]["error_message"]


def test_job_where_everyone_is_invalid_is_marked_failed():
    response = client.post("/api/jobs", json={"recipients": [{}, {"name": ""}]})
    assert response.status_code == 202
    assert response.json()["status"] == "FAILED"
    data = client.get(f"/api/jobs/{response.json()['job_id']}").json()
    assert data["failed_count"] == 2


# =========================================================== 3. CERTIFICATE GENERATION
def test_generator_creates_a_png_certificate(tmp_path):
    path = generator.generate_certificate("job-1", 1, "Alice Johnson")
    assert os.path.exists(path)
    image = Image.open(path)
    assert image.format == "PNG"
    assert image.size == (800, 600)


def test_different_names_make_different_certificates():
    a = generator.generate_certificate("job-1", 1, "Alice")
    b = generator.generate_certificate("job-1", 2, "Bob")
    assert open(a, "rb").read() != open(b, "rb").read()


def test_very_long_name_does_not_crash():
    path = generator.generate_certificate("job-1", 1, "W" * 50)
    assert os.path.exists(path)


def test_certificate_files_are_saved_on_disk():
    job_id = client.post("/api/jobs", json=make_payload("Alice", "Bob")).json()["job_id"]
    files = os.listdir(os.path.join(generator.MEDIA_DIR, job_id))
    assert len(files) == 2


# =========================================================== 4. JOB STATUS / PROGRESS
def test_unknown_job_returns_404():
    assert client.get("/api/jobs/does-not-exist").status_code == 404


def test_progress_goes_from_0_to_100_percent(monkeypatch):
    # Stop the background task from running automatically, so we can look at the "before" state.
    monkeypatch.setattr(main, "process_certificate_job", lambda job_id: None)
    job_id = client.post("/api/jobs", json=make_payload("A", "B", "C", "D")).json()["job_id"]

    before = client.get(f"/api/jobs/{job_id}").json()
    assert before["status"] == "PENDING"
    assert before["progress_percent"] == 0

    worker.process_certificate_job(job_id)   # now run the worker ourselves

    after = client.get(f"/api/jobs/{job_id}").json()
    assert after["status"] == "COMPLETED"
    assert after["progress_percent"] == 100
    assert after["success_count"] == 4


# =========================================================== 5. ONE FAILURE DOESN'T STOP THE REST
def test_one_failing_certificate_does_not_stop_the_others(monkeypatch):
    real_function = worker.generate_certificate

    def sometimes_fails(job_id, recipient_id, recipient_name):
        if recipient_name == "Bob":
            raise ValueError("drawing exploded")
        return real_function(job_id, recipient_id, recipient_name)

    monkeypatch.setattr(worker, "generate_certificate", sometimes_fails)

    job_id = client.post("/api/jobs", json=make_payload("Alice", "Bob", "Carol")).json()["job_id"]
    data = client.get(f"/api/jobs/{job_id}").json()

    assert data["status"] == "COMPLETED_WITH_ERRORS"
    assert data["success_count"] == 2
    assert data["failed_count"] == 1

    people = {p["name"]: p for p in data["recipients"]}
    assert people["Alice"]["status"] == "SUCCESS"
    assert people["Carol"]["status"] == "SUCCESS"   # Carol comes AFTER Bob and still worked
    assert people["Bob"]["status"] == "FAILED"
    assert "drawing exploded" in people["Bob"]["error_message"]


def test_job_is_failed_when_every_certificate_fails(monkeypatch):
    def always_fails(job_id, recipient_id, recipient_name):
        raise ValueError("nope")

    monkeypatch.setattr(worker, "generate_certificate", always_fails)
    job_id = client.post("/api/jobs", json=make_payload("A", "B")).json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "FAILED"


# =========================================================== 6. RETRIEVING CERTIFICATES
def test_download_successful_certificate_returns_png():
    payload = {"recipients": [{"name": "Alice Valid", "email": "alice@example.com"}]}
    job_id = client.post("/api/jobs", json=payload).json()["job_id"]
    alice = client.get(f"/api/jobs/{job_id}").json()["recipients"][0]

    response = client.get(f"/api/jobs/{job_id}/certificates/{alice['id']}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")   # every PNG file starts with these bytes


def test_cannot_download_failed_or_unknown_certificate():
    payload = {"recipients": [{"name": "No Email"}, {"name": "Ok", "email": "o@e.co"}]}
    job_id = client.post("/api/jobs", json=payload).json()["job_id"]
    skipped = client.get(f"/api/jobs/{job_id}").json()["recipients"][0]

    assert client.get(f"/api/jobs/{job_id}/certificates/{skipped['id']}").status_code == 400
    assert client.get(f"/api/jobs/{job_id}/certificates/99999").status_code == 404
    assert client.get("/api/jobs/nope/certificates/1").status_code == 404


# =========================================================== 7. SWAGGER UI
def test_swagger_ui_is_available():
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
