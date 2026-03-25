import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base
from config import DATABASE_URL


engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = scoped_session(sessionmaker(bind=engine))


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)
    print("✅ Tabelas do banco de dados criadas/verificadas.")


def get_session():
    """Get a new database session."""
    return SessionLocal()


def close_session(session):
    """Close a database session."""
    try:
        session.close()
    except Exception:
        pass
