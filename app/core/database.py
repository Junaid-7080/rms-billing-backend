"""
Database configuration and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from typing import Generator

from app.core.config import settings

# Convert async URL to sync URL
database_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

# Create sync engine
engine = create_engine(
    database_url,
    echo=settings.DEBUG,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create declarative base for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session

    Usage:
        @app.get("/")
        def read_data(db: Session = Depends(get_db)):
            # Use db session here
    """
    db = SessionLocal()
    try:
        yield db
        # ❌ Remove automatic commit - let routes handle it
        # db.commit()
    except Exception as e:
        db.rollback()
        print(f"❌ Database Error in get_db: {e}")
        raise
    finally:
        db.close()


def init_db():
    """Initialize database tables (for development only)"""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        raise


def drop_db():
    """Drop all database tables (for testing only)"""
    try:
        Base.metadata.drop_all(bind=engine)
        print("✅ Database tables dropped successfully")
    except Exception as e:
        print(f"❌ Error dropping tables: {e}")
        raise