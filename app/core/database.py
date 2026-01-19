"""
Database configuration with Render PostgreSQL SSL support
Place this in: app/core/database.py
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os
import logging
import time

logger = logging.getLogger(__name__)

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Fix postgres:// to postgresql:// (Render sometimes uses old format)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    logger.info("Converted postgres:// to postgresql://")

# Add SSL mode if not present
if "sslmode" not in DATABASE_URL:
    separator = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = f"{DATABASE_URL}{separator}sslmode=require"
    logger.info("Added sslmode=require to connection string")

# Determine environment
is_production = os.getenv("ENVIRONMENT", "development") == "production"

# Connection arguments optimized for Render
connect_args = {
    "connect_timeout": 30,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
    "options": "-c statement_timeout=30000",  # 30 second statement timeout
}

# Engine configuration
engine_config = {
    "connect_args": connect_args,
    "pool_pre_ping": True,  # Verify connections before use
    "pool_size": int(os.getenv("DATABASE_POOL_SIZE", 5)),
    "max_overflow": int(os.getenv("DATABASE_MAX_OVERFLOW", 0)),
    "pool_recycle": 300,  # Recycle connections every 5 minutes
    "echo": os.getenv("DEBUG", "False").lower() == "true",
}

# Create engine
try:
    engine = create_engine(DATABASE_URL, **engine_config)
    logger.info("Database engine created successfully")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    raise

# Connection event listeners
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log successful connections"""
    logger.info("New database connection established")

@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Verify connection is alive before checkout"""
    try:
        cursor = dbapi_conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
    except Exception as e:
        logger.warning(f"Connection checkout failed, invalidating: {e}")
        raise

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def get_db():
    """
    Dependency for getting database session
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def test_connection(max_retries=3):
    """
    Test database connection with retries
    Call this on application startup
    """
    for attempt in range(max_retries):
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info("✅ Database connection test successful")
                return True
        except Exception as e:
            logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error("❌ All database connection attempts failed")
                raise

def init_db():
    """
    Initialize database (create tables)
    Import all models before calling this
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise
    