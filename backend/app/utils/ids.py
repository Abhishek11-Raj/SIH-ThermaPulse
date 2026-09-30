"""Stable, readable identifier generation for canonical records."""
from __future__ import annotations

import uuid


def new_record_id(prefix: str) -> str:
    """Generate a record id like ``wxn-3f9a2c1b...`` (stable per call)."""
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def source_record_id(source: str, location_id: str, moment: str) -> str:
    """Deterministic source-side id, e.g. ``imd-LOC123-2026-06-01T12:00Z``."""
    return f"{source}:{location_id}:{moment}"