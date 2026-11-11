"""DB session / engine. Postgres when DATABASE_URL is set, SQLite fallback."""
from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from settings import settings
from database.models import Base

def _engine():
    url = settings.DATABASE_URL
    if url.startswith("postgres://"):
        # Render (and Heroku-style) Postgres URLs use postgres://;
        # SQLAlchemy requires the postgresql:// scheme.
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)

engine = _engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def init_db() -> None:
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
