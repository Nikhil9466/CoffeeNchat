import os
import logging
from pathlib import Path
from dotenv import load_dotenv

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("SQLALCHEMY_DATABASE_URL environment variable is not set!")

# Ensure the scheme uses the asyncpg driver
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# 1. Shared Base for SQLAlchemy models
Base = declarative_base()

# 2. Create Async Engine
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    hide_parameters=True,
    echo=False,
)

# 3. Export AsyncSessionLocal for routes and controllers
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# 4. Async Connection Verification
async def verify_db_connection():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            print("Database connected successfully! PostgreSQL server is online.")
    except Exception:
        logger.exception("Database connection failed during startup")
        raise


# 5. Async Database Initialization
async def init_db() -> None:
    # Startup verifies schema; only the explicit migration command changes it.
    async with engine.connect() as conn:
        revision = await conn.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "0003_integrity":
            raise RuntimeError(
                "Database migration required: run python manage.py migrate"
            )


# 6. Async DB Dependency for REST API Routes
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
