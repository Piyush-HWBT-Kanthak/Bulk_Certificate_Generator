import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# This will automatically create a local file named 'app.db' in  project root.
# (The DATABASE_URL environment variable lets the tests use a separate temporary database.)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# check_same_thread=False allows FastAPI background tasks to share the SQLite connection safely
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Provides a transactional database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
