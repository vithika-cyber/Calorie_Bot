"""
Database Module - Database connection and session management
"""

import logging
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from ..config import get_settings
from .models import Base

logger = logging.getLogger(__name__)

# Global engine and session factory
engine = None
SessionLocal = None


def init_db() -> None:
    """
    Initialize the database engine and create all tables
    
    This function should be called once at application startup
    """
    global engine, SessionLocal
    
    settings = get_settings()
    
    # Create engine based on database URL
    if settings.database_url.startswith("sqlite"):
        # SQLite-specific configuration
        engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=settings.debug,
        )
        
        # Enable foreign keys for SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    else:
        # PostgreSQL or other databases
        engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            echo=settings.debug,
        )
    
    # Create session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create all tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("[OK] Database tables created successfully")
    except Exception as e:
        logger.error(f"[FAIL] Error creating database tables: {e}")
        raise


def get_db() -> Generator[Session, None, None]:
    """
    Get database session - use as a dependency
    
    Yields:
        Database session
        
    Example:
        with get_db() as db:
            users = db.query(User).all()
    """
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions
    
    Yields:
        Database session
        
    Example:
        with get_db_session() as db:
            user = db.query(User).first()
    """
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()


def reset_database() -> None:
    """
    Drop all tables and recreate them - USE WITH CAUTION
    
    This will delete all data in the database
    """
    global engine
    
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    logger.warning("⚠️  Resetting database - all data will be lost!")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("[OK] Database reset complete")


def check_db_connection() -> bool:
    """
    Check if database connection is working
    
    Returns:
        True if connection is successful, False otherwise
    """
    try:
        from sqlalchemy import text
        with get_db_session() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


if __name__ == "__main__":
    # Test database initialization
    print("Initializing database...")
    init_db()
    
    if check_db_connection():
        print("[OK] Database connection successful!")
    else:
        print("[FAIL] Database connection failed!")
