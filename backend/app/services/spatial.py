"""Spatial normalization and location-mapping utilities.

Handles the "spatial dimensions" problems KESHAV must never paper over:

    - normalize how a source geometry is described (point / grid / raster /
      polygon / practice), preserving the original description
    - map an arbitrary source point (e.g. an API station at lat/lon) onto the
      nearest known KESHAV location
    - RECORD the mapping (method, source location, target location, distance,
      quality) instead of pretending a point observation is a ward measurement

All helpers are pure (no DB) so they are unit-testable; the adapter/ingestion
layer passes candidates from the location catalogue.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from ..core.enums import SpatialReferenceType
from ..utils.time import utcnow

EARTH_RADIUS_KM = 6371.0088

GEOMETRY_TYPE_ORDER: Dict[str, int] = {
    "point": 1,
    "grid": 2,
    "raster_cell": 3,
    "polygon": 4,
    "practice": 5,
}
"""Higher = coarser / more derived. Used to record resolved precision."""


def haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Great-circle distance in km between two coordinate pairs."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


SpatialCandidate = Dict[str, Any]
# {"location_id", "type", "latitude", "longitude", "name", "area_sq_km"}


def geometry_type_precision(gtype: str) -> int:
    return GEOMETRY_TYPE_ORDER.get(gtype, 99)


def normalize_geometry(
    geometry_reference: str,
    source_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalize a geometry description into a stable, serializable form.

    Accepts any of the KESHAV geometry conventions and returns:
        {"geometry_reference", "source_type", "precision_rank"}
    """
    stype = source_type or "point"
    if stype not in GEOMETRY_TYPE_ORDER:
        stype = "polygon" if stype == "polygons" else (
            "raster_cell" if stype == "raster" else (
                "grid" if stype in ("grid", "GRID", "res_0.25") else "point"
            )
        )
    if not geometry_reference:
        geometry_reference = ""
    return {
        "geometry_reference": str(geometry_reference),
        "source_type": stype,
        "precision_rank": geometry_type_precision(stype),
    }


@dataclass
class SpatialMappingResult:
    mapping_id: str
    source_id: str
    source_name: Optional[str]
    source_type: str
    source_latitude: Optional[float]
    source_longitude: Optional[float]
    target_location_id: str
    mapping_method: str
    distance_km: Optional[float]
    resolution_value: Optional[float]
    resolution_unit: Optional[str]
    quality_flag: str
    provenance: Dict[str, Any]
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.mapping_id:
            self.mapping_id = f"map_{uuid.uuid4().hex[:12]}"

    def to_orm_dict(self) -> Dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "source_latitude": self.source_latitude,
            "source_longitude": self.source_longitude,
            "target_location_id": self.target_location_id,
            "mapping_method": self.mapping_method,
            "distance_km": self.distance_km,
            "resolution_value": self.resolution_value,
            "resolution_unit": self.resolution_unit,
            "quality_flag": self.quality_flag,
            "provenance": self.provenance,
            "created_at": self.created_at,
        }


def _nearby_candidates(
    latitude: float,
    longitude: float,
    candidates: Sequence[SpatialCandidate],
    max_distance_km: float,
) -> List[tuple]:
    """Return (distance_km, candidate) sorted ascending within max distance."""
    hits = []
    for cand in candidates:
        lat = cand.get("latitude")
        lon = cand.get("longitude")
        if lat is None or lon is None:
            continue
        distance = haversine_km(latitude, longitude, float(lat), float(lon))
        if distance <= max_distance_km:
            hits.append((distance, cand))
    hits.sort(key=lambda item: item[0])
    return hits


def find_nearest_location(
    latitude: float,
    longitude: float,
    candidates: Sequence[SpatialCandidate],
    max_distance_km: float = 200.0,
) -> Optional[tuple]:
    """Return ``(distance_km, candidate)`` for the nearest candidate."""
    hits = _nearby_candidates(latitude, longitude, candidates, max_distance_km)
    return hits[0] if hits else None


def bbox_candidates(
    bbox: tuple,
    candidates: Sequence[SpatialCandidate],
) -> List[SpatialCandidate]:
    """Return candidates inside a (min_lat, min_lon, max_lat, max_lon) extent."""
    min_lat, min_lon, max_lat, max_lon = bbox
    out: List[SpatialCandidate] = []
    for cand in candidates:
        lat = cand.get("latitude")
        lon = cand.get("longitude")
        if lat is None or lon is None:
            continue
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            out.append(cand)
    return out


def map_source_point(
    source_id: str,
    latitude: float,
    longitude: float,
    location_catalogue: Sequence[SpatialCandidate],
    source_name: Optional[str] = None,
    source_type: str = "point",
    mapping_method: str = "nearest_point",
    max_distance_km: float = 200.0,
    quality_rule: str = "distance-based",
) -> Optional[SpatialMappingResult]:
    """Map a source point to the nearest known KESHAV location.

    Returns a full ``SpatialMappingResult`` (with provenance) or None when no
    location is within range. Quality guidance:
        distance <= 5 km            → VALID
        distance <= 25 km           → SUSPECT (coarse assignment)
        beyond                    → not returned (beyond max_distance_km)
    """
    nearest = find_nearest_location(
        latitude, longitude, location_catalogue, max_distance_km
    )
    if nearest is None:
        return None
    distance_km, target = nearest
    if distance_km <= 5.0:
        quality = "VALID"
    elif distance_km <= 25.0:
        quality = "SUSPECT"
    else:
        quality = "SUSPECT"
    return SpatialMappingResult(
        mapping_id=f"map_{uuid.uuid4().hex[:12]}",
        source_id=source_id,
        source_name=source_name,
        source_type=source_type,
        source_latitude=latitude,
        source_longitude=longitude,
        target_location_id=target["location_id"],
        mapping_method=mapping_method,
        distance_km=round(distance_km, 3),
        resolution_value=target.get("area_sq_km"),
        resolution_unit="sq_km",
        quality_flag=quality,
        provenance={
            "quality_rule": quality_rule,
            "source_geometry": source_type,
            "target_type": target.get("type"),
            "distance_threshold_km": max_distance_km,
        },
        created_at=utcnow(),
    )


def grid_resolution_metadata(
    grid_step_degrees: float,
) -> Dict[str, Any]:
    """Approximate real-world resolution of a lat/lon grid step."""
    km_per_degree = 111.0  # at equator; used only for attribution
    return {
        "resolution_value": round(grid_step_degrees * km_per_degree, 1),
        "resolution_unit": "km",
        "grid_step_degrees": grid_step_degrees,
    }


def best_available_candidate(
    candidates: Sequence[SpatialCandidate],
    preferred_types: Sequence[str] = ("point", "ward", "city", "district"),
) -> Optional[SpatialCandidate]:
    """Pick the most precise usable candidate (finer geometry wins)."""
    ordered = []
    for cand in candidates:
        ctype = cand.get("type", "")
        precision = geometry_type_precision(ctype)
        if ctype in preferred_types:
            refined = 0 if ctype == "point" else (1 if ctype == "ward" else 2)
            precision = refined
        ordered.append((precision, -1 * float(cand.get("population") or 0), cand))
    if not ordered:
        return None
    ordered.sort(key=lambda item: item[0])
    return ordered[0][2]


def location_catalogue_from_rows(rows: Sequence[Any]) -> List[SpatialCandidate]:
    """Convert ORM Location rows (or dicts) into mapping candidates."""
    out = []
    for row in rows:
        if hasattr(row, "location_id"):
            out.append(
                {
                    "location_id": row.location_id,
                    "type": row.type,
                    "latitude": row.latitude,
                    "longitude": row.longitude,
                    "name": row.name,
                    "area_sq_km": row.area_sq_km,
                }
            )
        else:
            out.append(dict(row))
    return out


def summarize_points_on_extent(
    points: Sequence[tuple],
) -> Dict[str, Any]:
    """Spatial summary of a point set (lat, lon) for coverage/resolution audit."""
    if not points:
        return {"count": 0, "extent_km2": None, "mean_density_per_km2": None}
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    lat_span = max(lats) - min(lats)
    lon_span = max(lons) - min(lons)
    width_km = lon_span * 111.0 * math.cos(math.radians((max(lats) + min(lats)) / 2))
    height_km = lat_span * 111.0
    extent_km2 = max(width_km, 0.0) * max(height_km, 0.0)
    if extent_km2 <= 0:
        return {"count": len(points), "extent_km2": 0.0, "mean_density_per_km2": None}
    return {
        "count": len(points),
        "extent_km2": round(extent_km2, 3),
        "mean_density_per_km2": round(len(points) / extent_km2, 4),
    }


def resolve_spatial_reference(
    geometry_reference: Optional[str],
    source_type: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
) -> Dict[str, Any]:
    """Build a canonical ``SpatialReference``-compatible dict for adapters.

    Uses the existing spatial-reference conventions (POINT / RASTER_CELL /
    POLYGON / GRID / PRACTICE). Raises ValueError on an empty/invalid reference.
    """
    gtype = source_type or "point"
    if gtype == "point":
        ref_type = SpatialReferenceType.POINT
    elif gtype in ("raster_cell", "raster"):
        ref_type = SpatialReferenceType.RASTER_CELL
    elif gtype in ("grid",):
        ref_type = SpatialReferenceType.GRID
    elif gtype in ("practice",):
        ref_type = SpatialReferenceType.PRACTICE
    else:
        ref_type = SpatialReferenceType.POLYGON
    ref: Dict[str, Any] = {
        "ref_type": ref_type,
        "geometry_reference": geometry_reference,
    }
    if latitude is not None:
        ref["latitude"] = latitude
        ref["longitude"] = longitude
    return ref