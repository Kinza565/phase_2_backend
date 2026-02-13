from sqlmodel import SQLModel, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import contextmanager

from .config import DATABASE_URL

# Import all models to ensure they are registered with SQLModel metadata
from .models import Task, User  # noqa: F401

def _create_engine():
    if DATABASE_URL.startswith("sqlite"):
        return create_engine(
            DATABASE_URL,
            echo=False,
            connect_args={"check_same_thread": False},
        )

    # Neon/Postgres: disable pooling for serverless and enable pre-ping
    return create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        poolclass=NullPool,
    )

engine = _create_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_session():
    """Get a database session (context manager style).
    
    This is a convenience function for use outside of FastAPI dependencies.
    Usage:
        with get_session() as session:
            # do something with session
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def create_tables():
    """Create all database tables."""
    SQLModel.metadata.create_all(bind=engine)
