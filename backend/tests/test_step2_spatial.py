"""Step 2 tests: spatial mapping and geometry normalization."""

from __future__ import annotations

import pytest

from app.services.spatial import (
    bbox_candidates,
    best_available_candidate,
    find_nearest_location,
    haversine_km,
    map_source_point,
    normalize_geometry,
    summarize_points_on_extent,
)

CATALOGUE = [
    {"location_id": "DEMO-WARD-01", "type": "ward", "latitude": 19.88, "longitude": 75.34, "area_sq_km": 3.2},
    {"location_id": "DEMO-STATION-A", "type": "point", "latitude": 19.8805, "longitude": 75.3405, "area_sq_km": None},
    {"location_id": "DEMO-WARD-02", "type": "ward", "latitude": 19.875, "longitude": 75.345, "area_sq_km": 2.5},
]


def test_haversine_zero_distance():
    assert haversine_km(19.88, 75.34, 19.88, 75.34) == pytest.approx(0.0, abs=1e-6)


def test_haversine_reflects_known_distance():
    d = haversine_km(0.0, 0.0, 0.0, 1.0)
    assert d == pytest.approx(111.19, abs=0.5)


def test_find_nearest_returns_closest():
    hit = find_nearest_location(19.88, 75.34, CATALOGUE)
    assert hit is not None
    distance, cand = hit
    assert cand["location_id"] == "DEMO-WARD-01"
    assert distance == pytest.approx(0.0, abs=1e-3)


def test_nearest_out_of_range_returns_none():
    hit = find_nearest_location(50.0, 10.0, CATALOGUE, max_distance_km=30.0)
    assert hit is None


def test_map_source_point_builds_provenance():
    m = map_source_point("src-1", 19.881, 75.341, CATALOGUE)
    assert m is not None
    assert m.target_location_id == "DEMO-STATION-A"
    assert m.source_type == "point"
    assert m.mapping_method == "nearest_point"
    assert m.quality_flag in ("VALID", "SUSPECT")
    assert m.provenance["source_geometry"] == "point"
    assert m.distance_km is not None and m.distance_km >= 0


def test_map_source_point_far_returns_none():
    m = map_source_point("src-2", 30.0, 70.0, CATALOGUE, max_distance_km=10.0)
    assert m is None


def test_geometry_normalization():
    assert normalize_geometry("g1", "raster")["source_type"] == "raster_cell"
    assert normalize_geometry("g2", "polygon")["precision_rank"] >= normalize_geometry("g3", "point")["precision_rank"]


def test_best_available_candidate_prefers_precision():
    best = best_available_candidate(CATALOGUE, preferred_types=("point", "ward"))
    assert best["location_id"] in ("DEMO-WARD-01", "DEMO-STATION-A")


def test_summarize_points_on_extent():
    points = [(19.87, 75.34), (19.88, 75.34), (19.87, 75.35), (19.88, 75.35)]
    summary = summarize_points_on_extent(points)
    assert summary["count"] == 4
    assert summary["extent_km2"] is not None and summary["extent_km2"] > 0


def test_summarize_points_empty():
    assert summarize_points_on_extent([])["count"] == 0


def test_bbox_candidates_filters_by_extent():
    bbox = (19.86, 75.33, 19.89, 75.36)  # min_lat, min_lon, max_lat, max_lon
    hits = [c for c in bbox_candidates(bbox, CATALOGUE)]
    assert len(hits) == 3