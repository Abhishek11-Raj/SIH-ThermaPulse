"""Step 2 tests: DB-backed provider cache with explicit freshness."""

from __future__ import annotations

from datetime import timedelta

from app.core.enums import FreshnessStatus
from app.models.step2 import ProviderCache as ProviderCacheModel
from app.services.cache import (
    cache_key,
    clear_cache,
    get_cache_entry,
    list_cache_entries,
    store_cache_entry,
)
from app.utils.time import utcnow


def test_cache_roundtrip(db):
    store_cache_entry(
        db, "openmeteo_weather", "weather", "DEMO-WARD-01",
        {"temp": 25.0}, ttl_seconds=3600.0, source_timestamp=utcnow(),
    )
    entry = get_cache_entry(db, "openmeteo_weather", "weather", "DEMO-WARD-01")
    assert entry is not None
    assert entry.value == {"temp": 25.0}
    assert entry.freshness == FreshnessStatus.FRESH
    assert entry.provider == "openmeteo_weather"


def test_cache_miss_returns_none(db):
    assert get_cache_entry(db, "openmeteo_weather", "weather", "NOPE") is None


def test_cache_expired_returns_none(db):
    old = utcnow() - timedelta(hours=10)
    row = ProviderCacheModel(
        cache_key=cache_key("p", "d", "L"),
        provider="p",
        domain="d",
        location_id="L",
        source_timestamp=old,
        cached_at=old,
        expires_at=old + timedelta(minutes=1),  # already passed
        payload='{"temp": 1}',
    )
    db.add(row)
    db.commit()
    assert get_cache_entry(db, "p", "d", "L") is None


def test_cache_aging_when_past_half_ttl(db):
    from datetime import timedelta as td

    old = utcnow() - td(hours=2)  # 2 h age, but TTL 3 h → still cached but aging
    row = ProviderCacheModel(
        cache_key=cache_key("p2", "d", "L"),
        provider="p",
        domain="d",
        location_id="L",
        source_timestamp=old,
        cached_at=old,
        expires_at=old + td(hours=3),
        payload='{"temp": 1}',
    )
    db.add(row)
    db.commit()
    entry = get_cache_entry(db, "p2", "d", "L")
    assert entry is not None
    assert entry.freshness == FreshnessStatus.AGING


def test_cache_upsert_overwrites(db):
    store_cache_entry(db, "p1", "d1", "L1", {"v": 1}, 3600.0)
    store_cache_entry(db, "p1", "d1", "L1", {"v": 2}, 3600.0)
    assert get_cache_entry(db, "p1", "d1", "L1").value == {"v": 2}
    rows = db.query(ProviderCacheModel).filter(ProviderCacheModel.location_id == "L1").all()
    assert len(rows) == 1


def test_list_and_clear(db):
    store_cache_entry(db, "a", "d", "L1", [1], 3600.0)
    store_cache_entry(db, "b", "d", "L2", [2], 3600.0)
    assert len(list_cache_entries(db)) >= 2
    assert clear_cache(db, domain="d") >= 2
    assert list_cache_entries(db, domain="d") == []