"""Concurrent /assess endpoint load tests.

Validates DB transaction isolation, parcel upsert races, and deadlock
resistance under parallel requests against a real PostgreSQL database.

Requires: running PostgreSQL at DATABASE_URL (defaults to cover_test).
"""

import asyncio
import os
import time

import httpx
import pytest
import pytest_asyncio

# Skip entire module unless explicitly opted in (requires running PostgreSQL)
pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_DB_TESTS"),
    reason="Requires running PostgreSQL (set RUN_DB_TESTS=1 and DATABASE_URL)",
)
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/cover_test",
)

from backend.app.api.endpoints import _parcel_service
from backend.app.db.models import Assessment, Base, Parcel, Zone
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.services.parcel_service import ParcelData, ParcelZoning
from backend.tests.conftest import make_la_parcel_geojson

# ---------------------------------------------------------------------------
# Test DB engine (separate from the app engine so we can query independently)
# ---------------------------------------------------------------------------

_TEST_DB_URL = os.environ["DATABASE_URL"]
_test_engine = create_async_engine(_TEST_DB_URL, pool_size=5, max_overflow=10)
_test_session_factory = async_sessionmaker(
    _test_engine, class_=AsyncSession, expire_on_commit=False
)


# ---------------------------------------------------------------------------
# DB session override
# ---------------------------------------------------------------------------

async def _override_get_db():
    """Yield a real AsyncSession per request, same commit/rollback semantics as production."""
    session = _test_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parcel_data(address: str, apn: str) -> ParcelData:
    """Return a deterministic ParcelData with R1-1 zoning."""
    return ParcelData(
        apn=apn,
        address=address,
        lat=34.0760,
        lng=-118.2920,
        geometry=make_la_parcel_geojson(),
        lot_area_sf=6000.0,
        year_built=1955,
        existing_units=1,
        existing_sqft=1200.0,
        zoning=ParcelZoning(
            zone_complete="R1-1",
            zone_class="R1",
            zone_code="R1",
            general_plan_land_use="Low Residential",
            land_use_category="Residential",
            specific_plan=None,
            hpoz=None,
        ),
    )


def _mock_parcel_service_with(lookup_fn):
    """Build a FastAPI dependency override that yields a mock ParcelService."""

    class _MockSvc:
        async def lookup_by_address(self, address: str) -> ParcelData:
            return await lookup_fn(address)

    async def _override():
        yield _MockSvc()

    return _override


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="module")
async def _setup_db():
    """Create tables before the module, drop after."""
    async with _test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(_setup_db):
    """Truncate test tables before each test."""
    async with _test_engine.begin() as conn:
        await conn.execute(delete(Assessment))
        await conn.execute(delete(Zone))
        await conn.execute(delete(Parcel))
    yield


@pytest_asyncio.fixture()
async def _seed_rules(_setup_db):
    """Seed rule fragments so the ConstraintResolver has data."""
    from backend.app.db.seed_data import seed_all

    async with _test_session_factory() as session:
        await seed_all(session)
        await session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_same_address_no_duplicate_parcels(_seed_rules):
    """10 concurrent /assess for the same address must produce exactly 1 parcel row."""
    test_apn = "9999-000-001"
    test_address = "123 Concurrency Test St"
    parcel_data = _make_parcel_data(test_address, test_apn)

    async def _lookup(_address: str) -> ParcelData:
        return parcel_data

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[_parcel_service] = _mock_parcel_service_with(_lookup)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            tasks = [
                client.post("/api/assess", json={"address": test_address})
                for _ in range(10)
            ]
            responses = await asyncio.gather(*tasks)

        status_codes = [r.status_code for r in responses]
        assert all(
            s == 200 for s in status_codes
        ), f"Expected all 200s, got: {status_codes}"

        async with _test_session_factory() as session:
            parcel_count = await session.scalar(
                select(func.count()).select_from(Parcel).where(Parcel.apn == test_apn)
            )
            assert parcel_count == 1, f"Expected 1 parcel row, got {parcel_count}"

            zone_count = await session.scalar(
                select(func.count()).select_from(Zone)
            )
            assert zone_count == 1, f"Expected 1 zone row, got {zone_count}"

            assessment_count = await session.scalar(
                select(func.count()).select_from(Assessment)
            )
            assert assessment_count == 10, f"Expected 10 assessments, got {assessment_count}"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_different_addresses_independent(_seed_rules):
    """10 concurrent /assess for different addresses must produce 10 distinct parcels."""

    async def _lookup(address: str) -> ParcelData:
        idx = address.split("#")[1].strip() if "#" in address else "0"
        return _make_parcel_data(address, f"9999-000-{idx.zfill(3)}")

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[_parcel_service] = _mock_parcel_service_with(_lookup)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            tasks = [
                client.post("/api/assess", json={"address": f"100 Test Ave #{i}"})
                for i in range(10)
            ]
            responses = await asyncio.gather(*tasks)

        status_codes = [r.status_code for r in responses]
        assert all(
            s == 200 for s in status_codes
        ), f"Expected all 200s, got: {status_codes}"

        for r in responses:
            body = r.json()
            assert "assessment_id" in body, f"Missing assessment_id in response: {body}"

        async with _test_session_factory() as session:
            parcel_count = await session.scalar(
                select(func.count()).select_from(Parcel)
            )
            assert parcel_count == 10, f"Expected 10 parcel rows, got {parcel_count}"

            distinct_apns = await session.scalar(
                select(func.count(func.distinct(Parcel.apn)))
            )
            assert distinct_apns == 10, f"Expected 10 distinct APNs, got {distinct_apns}"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_no_deadlocks_under_load(_seed_rules):
    """20 concurrent /assess (10 same address + 10 different) must all complete within 30s."""
    same_apn = "9999-DL-001"
    same_address = "200 Deadlock Blvd"
    same_parcel = _make_parcel_data(same_address, same_apn)

    async def _lookup(address: str) -> ParcelData:
        if address == same_address:
            return same_parcel
        idx = address.split("#")[1].strip() if "#" in address else "99"
        return _make_parcel_data(address, f"9999-DL-{idx.zfill(3)}")

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[_parcel_service] = _mock_parcel_service_with(_lookup)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            same_tasks = [
                client.post("/api/assess", json={"address": same_address})
                for _ in range(10)
            ]
            diff_tasks = [
                client.post("/api/assess", json={"address": f"300 Varied St #{i}"})
                for i in range(10)
            ]

            start = time.monotonic()
            responses = await asyncio.gather(*(same_tasks + diff_tasks))
            elapsed = time.monotonic() - start

        assert elapsed < 30, f"Requests took {elapsed:.1f}s (>30s deadlock threshold)"

        status_codes = [r.status_code for r in responses]
        failures = [s for s in status_codes if s >= 500]
        assert not failures, f"Got {len(failures)} server errors: {status_codes}"
    finally:
        app.dependency_overrides.clear()
