import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

Base = declarative_base()

from sqlalchemy import text

# -------------------------------------------------
# Database initialization
# -------------------------------------------------
async def init_db() -> None:
    """
    Ensure pgvector extension exists and create all tables
    defined in the SQLAlchemy models.
    """
    # Import all models to ensure they register with Base.metadata
    import src.models.user  # noqa: F401
    import src.models.knowledge  # noqa: F401
    import src.models.ticket  # noqa: F401
    import src.models.chat  # noqa: F401

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
