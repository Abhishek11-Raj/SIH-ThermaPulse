"""Synthetic KESHAV location catalogue (clearly marked mock).

Names/identifiers use a ``DEMO`` prefix so no one mistakes this synthetic
catalogue for a real national location hierarchy. Real governments/municipal
GIS sources plug into the same schema through a future GeoSpatialProvider.
"""

from __future__ import annotations

from typing import List

from ...core.enums import LocationType

# (location_id, parent, name, type, lat, lon, population, area_sq_km)
LOCATION_ROWS: List[tuple] = [
    ("DEMO-IN", None, "DemoCountry", LocationType.COUNTRY, 22.0, 79.0, 1_400_000_000, 3_287_000.0),
    ("DEMO-IN-MH", "DEMO-IN", "DemoState", LocationType.STATE, 19.6, 75.3, 120_000_000, 307_713.0),
    ("DEMO-DIST-1", "DEMO-IN-MH", "DemoDistrict-1", LocationType.DISTRICT, 19.88, 75.34, 4_600_000, 10_100.0),
    ("DEMO-CITY-1", "DEMO-DIST-1", "DemoCity-1", LocationType.CITY, 19.8762, 75.3433, 1_200_000, 138.0),
    ("DEMO-WARD-01", "DEMO-CITY-1", "DemoCity-1 Ward 01", LocationType.WARD, 19.8800, 75.3400, 58_000, 3.2),
    ("DEMO-WARD-02", "DEMO-CITY-1", "DemoCity-1 Ward 02", LocationType.WARD, 19.8750, 75.3450, 44_000, 2.5),
    ("DEMO-WARD-03", "DEMO-CITY-1", "DemoCity-1 Ward 03 (data-poor demo)", LocationType.WARD, 19.8700, 75.3500, 62_000, 3.9),
    ("DEMO-ZONE-A", "DEMO-CITY-1", "DemoCity-1 Zone A", LocationType.ZONE, 19.8770, 75.3420, 210_000, 12.0),
    ("DEMO-STATION-A", "DEMO-WARD-01", "DemoStation-A (mock sensor)", LocationType.POINT, 19.8805, 75.3405, None, None),
    ("DEMO-STATION-B", "DEMO-WARD-02", "DemoStation-B (mock sensor)", LocationType.POINT, 19.8755, 75.3455, None, None),
]


def mock_location_rows() -> List[tuple]:
    return list(LOCATION_ROWS)


def data_poor_location_id() -> str:
    return "DEMO-WARD-03"