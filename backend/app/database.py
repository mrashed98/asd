"""Database configuration and session management."""
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Create engine
sqlite_connect_args = {}
if "sqlite" in settings.database_url:
    # Allow cross-thread access and increase lock timeout for concurrent processes
    sqlite_connect_args = {
        "check_same_thread": False,
        "timeout": 30,  # seconds
    }

engine = create_engine(
    settings.database_url,
    connect_args=sqlite_connect_args,
    pool_pre_ping=True,
)

# Improve SQLite concurrency (WAL mode) when used by multiple processes (API + Celery)
if "sqlite" in settings.database_url:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")  # 30s
            cursor.close()
        except Exception:
            # Best-effort; ignore if PRAGMAs are unsupported
            pass

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

# Create base class for models
Base = declarative_base()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)

