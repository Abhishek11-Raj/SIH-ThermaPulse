"""Provider response cache (DB-backed, TTL-based).

Purpose: survive short provider outages, avoid hammering rate-limited APIs and
keep the demo reliable. Cache entries carry their own metadata so we never
present stale data as fresh:

    cached_at          when cached
    source_timestamp   when the provider produced the data
    provider           which provider produced it
    domain             weather / forecast / air_quality / ...
    location_id        the spatial key
    expires_at         storage TTL (the hard cutoff)
    freshness          FRESH / AGING / STALE (computed on read)

Fallback semantics are explicit: reading from cache when a live provider failed
marks the returned data as ``fallback_source=cache`` and sets freshness by age —
we never silently dress cached data up as live.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from ..core.enums import FreshnessStatus
from ..models.step2 import ProviderCache as ProviderCacheModel

AGING_FACTOR = 0.5  # past half the TTL → AGING


@dataclass
class CacheEntry:
    """A cache entry with freshness metadata computed at read time."""

    value: Any
    cached_at: datetime
    source_timestamp: Optional[datetime]
    provider: str
    domain: str
    location_id: str
    expires_at: datetime
    freshness: FreshnessStatus

    def is_expired(self) -> bool:
        from ..utils.time import utcnow

        return utcnow() > self.expires_at


def cache_key(provider: str, domain: str, location_id: str, *parts: str) -> str:
    joined = "|".join([provider, domain, location_id, *parts])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _as_utc(value: datetime, default: Optional[datetime] = None) -> Optional[datetime]:
    """SQLite returns naive UTC datetimes; treat them as aware UTC."""
    if value is None:
        return default
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_cache_entry(
    db: Session,
    provider: str,
    domain: str,
    location_id: str,
    *parts: str,
) -> Optional[CacheEntry]:
    """Read a cache entry with freshness computed against provider TTL.

    Returns None if missing or past its storage TTL. ``stale_ttl_multiplier``
    is intentionally not applied here — the caller (fallback logic) decides
    whether to serve aging/stale data.
    """
    from ..utils.time import utcnow

    row = (
        db.query(ProviderCacheModel)
        .filter(ProviderCacheModel.cache_key == cache_key(provider, domain, location_id, *parts))
        .first()
    )
    if row is None:
        return None
    now = utcnow()
    expires_at = _as_utc(row.expires_at)
    source_ts = _as_utc(row.source_timestamp)
    cached_at = _as_utc(row.cached_at)
    if now > expires_at:
        return None
    ttl = max((expires_at - source_ts).total_seconds() if source_ts else 3600.0, 1.0)
    age = (now - _as_utc(cached_or_source(row))).total_seconds()
    if age <= ttl * AGING_FACTOR:
        freshness = FreshnessStatus.FRESH
    elif age <= ttl:
        freshness = FreshnessStatus.AGING
    else:  # beyond TTL but returned anyway by fallback policy → stale
        freshness = FreshnessStatus.STALE
    try:
        value = json.loads(row.payload) if isinstance(row.payload, str) else row.payload
    except (TypeError, json.JSONDecodeError):
        return None
    return CacheEntry(
        value=value,
        cached_at=cached_at,
        source_timestamp=source_ts,
        provider=row.provider,
        domain=row.domain,
        location_id=row.location_id,
        expires_at=expires_at,
        freshness=freshness,
    )


def cached_or_source(row) -> datetime:
    if row.source_timestamp is not None:
        return row.source_timestamp
    return row.cached_at


def store_cache_entry(
    db: Session,
    provider: str,
    domain: str,
    location_id: str,
    value: Any,
    ttl_seconds: float,
    source_timestamp: Optional[datetime] = None,
    *parts: str,
) -> ProviderCacheModel:
    """Upsert a cache entry. Commits the transaction."""
    from ..utils.time import utcnow

    now = utcnow()
    key = cache_key(provider, domain, location_id, *parts)
    expires = now + timedelta(seconds=max(ttl_seconds, 1.0))
    row = (
        db.query(ProviderCacheModel)
        .filter(ProviderCacheModel.cache_key == key)
        .first()
    )
    payload = json.dumps(value, default=str) if not isinstance(value, str) else value
    if row is None:
        row = ProviderCacheModel(
            cache_key=key,
            provider=provider,
            domain=domain,
            location_id=location_id,
            source_timestamp=source_timestamp,
            cached_at=now,
            expires_at=expires,
            payload=payload,
        )
        db.add(row)
    else:
        row.provider = provider
        row.domain = domain
        row.location_id = location_id
        row.source_timestamp = source_timestamp
        row.cached_at = now
        row.expires_at = expires
        row.payload = payload
    db.commit()
    return row


def list_cache_entries(db: Session, domain: Optional[str] = None) -> List[dict]:
    q = db.query(ProviderCacheModel)
    if domain:
        q = q.filter(ProviderCacheModel.domain == domain)
    rows = q.order_by(ProviderCacheModel.cached_at.desc()).limit(100).all()
    out = []
    for r in rows:
        out.append(
            {
                "cache_key": r.cache_key,
                "provider": r.provider,
                "domain": r.domain,
                "location_id": r.location_id,
                "source_timestamp": r.source_timestamp,
                "cached_at": r.cached_at,
                "expires_at": r.expires_at,
            }
        )
    return out


def clear_cache(db: Session, domain: Optional[str] = None) -> int:
    q = db.query(ProviderCacheModel)
    if domain:
        q = q.filter(ProviderCacheModel.domain == domain)
    count = q.delete()
    db.commit()
    return count