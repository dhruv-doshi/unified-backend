import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from src.main import app
from src.core.dependencies import get_db
from src.infrastructure.models import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        # Exclude PostgreSQL-only tables (TSVECTOR, pgvector) — they cannot be
        # compiled against SQLite. Research integration tests require a real
        # Postgres instance and are not run in this suite.
        sqlite_tables = [t for t in Base.metadata.sorted_tables if t.name != "papers"]
        await conn.run_sync(Base.metadata.create_all, tables=sqlite_tables)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(engine):
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
