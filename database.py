from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./goblin_assistant.db")

# Production PostgreSQL configuration
is_postgres = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith(
    "postgres"
)

# Connection pool settings (only for PostgreSQL)
pool_config = {}
if is_postgres:
    pool_config = {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),  # Base pool size
        "max_overflow": int(
            os.getenv("DB_MAX_OVERFLOW", "40")
        ),  # Max connections beyond pool_size
        "pool_timeout": int(
            os.getenv("DB_POOL_TIMEOUT", "30")
        ),  # Timeout for getting connection
        "pool_recycle": int(
            os.getenv("DB_POOL_RECYCLE", "3600")
        ),  # Recycle connections after 1 hour
        "pool_pre_ping": True,  # Test connections before use to catch stale connections
        "echo": False,  # Disable SQL logging in production
    }

    # PostgreSQL-specific connect args
    connect_args = {
        "connect_timeout": 10,  # Connection timeout in seconds
        "options": "-c statement_timeout=30000",  # 30s query timeout
    }

    # Add SSL certificate if using Supabase
    ssl_cert_path = os.getenv("DB_SSL_CERT_PATH")
    if ssl_cert_path and os.path.exists(ssl_cert_path):
        connect_args["sslmode"] = "verify-ca"
        connect_args["sslrootcert"] = ssl_cert_path
else:
    # SQLite-specific connect args
    connect_args = {"check_same_thread": False}

# Create engine with production-ready configuration
engine = create_engine(DATABASE_URL, connect_args=connect_args, **pool_config)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Session:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all tables"""
    Base.metadata.drop_all(bind=engine)
