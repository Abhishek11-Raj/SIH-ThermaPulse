"""Database init, seeding and persistence."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from app.core.database import init_db
from app.models.location import Location
from app.models.operations import ProviderStatus
from app.models.weather import WeatherObservation
from app.services.bootstrap import seed_locations
from app.services.ingest import ingest_weather
from app.utils.time import utcnow
from app.providers import registry
from app.providers.mock.providers import register_all_mock_providers

# Fixed past windows unique to these tests (never collide with API-window tests
# or with each other, so dedupe logic can be asserted deterministically).
_WINDOW_START = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
_WINDOW_END = _WINDOW_START + timedelta(hours=2)
_WINDOW_START_2 = _WINDOW_START + timedelta(days=1)
_WINDOW_END_2 = _WINDOW_START_2 + timedelta(hours=2)


def test_init_db_creates_tables(db):
    init_db()
    assert "locations" in Location.__table__.name


def test_seed_locations_matches_official_catalog(db):
    register_all_mock_providers()
    seed_locations(db, registry)
    rows = db.query(Location).all()
    assert len(rows) == 10
    ids = {r.location_id for r in rows}
    assert "DEMO-WARD-01" in ids
    assert "DEMO-WARD-03" in ids


def test_location_parent_hierarchy(db):
    register_all_mock_providers()
    seed_locations(db, registry)
    ward = db.query(Location).filter(Location.location_id == "DEMO-WARD-01").one()
    city = db.query(Location).filter(Location.location_id == "DEMO-CITY-1").one()
    assert ward.parent_location_id == "DEMO-CITY-1"
    assert city.parent_location_id == "DEMO-DIST-1"


def test_ingest_weather_persists_canonical_rows(db):
    register_all_mock_providers()
    seed_locations(db, registry)
    canonical, tracker = ingest_weather(db, "DEMO-WARD-01", _WINDOW_START, _WINDOW_END)
    assert tracker.accepted >= 1
    rows = db.query(WeatherObservation).all()
    matched = [r for r in rows if r.observed_at >= _WINDOW_START.replace(tzinfo=None)]
    assert len(matched) >= 1
    row = matched[0]
    assert row.location_id == "DEMO-WARD-01"
    assert row.source == canonical[0].source


def test_ingest_weather_deduplicates_by_identity(db):
    register_all_mock_providers()
    seed_locations(db, registry)
    first, tracker1 = ingest_weather(db, "DEMO-WARD-01", _WINDOW_START_2, _WINDOW_END_2)
    _, tracker2 = ingest_weather(db, "DEMO-WARD-01", _WINDOW_START_2, _WINDOW_END_2)
    assert tracker1.accepted >= 1
    assert tracker2.accepted == 0
    assert tracker2.duplicate == tracker1.accepted
    rows = db.query(WeatherObservation).filter(
        WeatherObservation.observed_at >= _WINDOW_START_2.replace(tzinfo=None),
        WeatherObservation.observed_at <= _WINDOW_END_2.replace(tzinfo=None),
    ).all()
    assert len(rows) == tracker1.accepted


def test_ingestion_logs_recorded(db):
    from app.models.operations import IngestionLog

    register_all_mock_providers()
    seed_locations(db, registry)
    ingest_weather(db, "DEMO-WARD-01", _WINDOW_START, _WINDOW_END)
    logs = db.query(IngestionLog).all()
    assert len(logs) >= 1
    assert logs[0].status in {"SUCCESS", "STARTED", "PARTIAL"}


def test_provider_status_seeded(db):
    register_all_mock_providers()
    from app.services.bootstrap import seed_provider_status

    seed_provider_status(db, registry)
    rows = db.query(ProviderStatus).all()
    assert len(rows) == 6


def test_utcnow_helper_returns_aware_utc():
    stamp = utcnow()
    assert stamp.tzinfo is not None
    assert stamp.utcoffset().total_seconds() == 0