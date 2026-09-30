"""Mock provider implementations (all deterministic).

These providers simulate external sources so the whole pipeline is demoable and
testable without any external API. They produce provider-native records which
must flow through adapters before anything downstream touches them.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ...core.enums import Scenario
from ...providers.base import (
    RawForecast,
    RawObservation,
    active_scenario,
    register_provider,
)
from ...utils.time import utcnow
from . import generator as gen
from . import locations as mock_locations
from .locations import data_poor_location_id

__all__ = [
    "MockWeatherObservationProvider",
    "MockWeatherForecastProvider",
    "MockAirQualityProvider",
    "MockGeoSpatialProvider",
    "MockVulnerabilityProvider",
    "MockHealthOutcomeProvider",
    "register_all_mock_providers",
]
# Keep scenario switch reachable from callers that import this module.
get_active_scenario = active_scenario


def _current_scenario(location_id: str) -> Scenario:
    sc = active_scenario()
    if sc == Scenario.DATA_POOR_AREA and location_id != data_poor_location_id():
        # DATA_POOR_AREA scenario applies to the designated demo ward only.
        return Scenario.NORMAL_DAY
    return sc


class MockWeatherObservationProvider:
    """Simulates an hourly weather-observation source (e.g. a station network)."""

    name = "mock_weather"
    domain = "weather"

    def fetch_observations(
        self,
        location_id: str,
        start: datetime,
        end: datetime,
        **options: Any,
    ) -> List[RawObservation]:
        scenario = _current_scenario(location_id)
        seed = options.get("seed", 2026)
        records: List[RawObservation] = []
        cursor = start
        step = timedelta(hours=1)
        while cursor <= end:
            gap_prob = gen.profile(scenario)["gap_prob"]
            if gen.should_record(seed, scenario, location_id, cursor, gap_prob):
                fields = gen.base_weather_fields(seed, scenario, location_id, cursor)
                if scenario == Scenario.DATA_POOR_AREA and cursor.hour == 6:
                    # Demonstrate explicit missing value (null, never 0).
                    fields["temp_c"] = None
                records.append(RawObservation(self.name, location_id, cursor, fields))
            cursor += step
        return records


class MockWeatherForecastProvider:
    """Simulates a forecast model issuing rolling 5-day forecasts."""

    name = "mock_forecast"
    domain = "weather_forecast"
    model_name = "mock-forecast-v1"
    model_version = "1.0.0"

    def fetch_forecast(
        self,
        location_id: str,
        issued_at: datetime,
        horizon_hours: int = 120,
        **options: Any,
    ) -> List[RawForecast]:
        scenario = _current_scenario(location_id)
        seed = options.get("seed", 2026)
        periods: List[tuple] = []
        start = issued_at.replace(minute=0, second=0, microsecond=0)
        for i in range(horizon_hours):
            cursor = start + timedelta(hours=i)
            fields = gen.base_weather_fields(seed, scenario, location_id, cursor)
            if i == 0:
                # First valid window includes everything from issue time.
                valid_from = issued_at
            else:
                valid_from = cursor
            periods.append((valid_from, cursor + timedelta(hours=1), fields))
        return [
            RawForecast(
                provider_name=self.name,
                location_id=location_id,
                issued_at=issued_at,
                periods=periods,
                model_name=self.model_name,
                model_version=self.model_version,
            )
        ]


class MockAirQualityProvider:
    """Simulates an hourly air-quality observation source."""

    name = "mock_air_quality"
    domain = "air_quality"

    def fetch_observations(
        self,
        location_id: str,
        start: datetime,
        end: datetime,
        **options: Any,
    ) -> List[RawObservation]:
        scenario = _current_scenario(location_id)
        seed = options.get("seed", 2026)
        records: List[RawObservation] = []
        cursor = start
        step = timedelta(hours=1)
        while cursor <= end:
            gap_prob = gen.profile(scenario)["gap_prob"]
            if gen.should_record(seed, scenario, location_id, cursor, gap_prob):
                records.append(
                    RawObservation(
                        self.name,
                        location_id,
                        cursor,
                        gen.air_quality_fields(seed, scenario, location_id, cursor),
                    )
                )
            cursor += step
        return records


class MockGeoSpatialProvider:
    """Simulates a GIS catalogue returning the mock location hierarchy."""

    name = "mock_gis"
    domain = "gis"

    def fetch_locations(self, **options: Any) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for loc_id, parent, name, ltype, lat, lon, pop, area in mock_locations.mock_location_rows():
            out.append(
                {
                    "loc_id": loc_id,
                    "parent": parent,
                    "name": name,
                    "type": ltype.value,
                    "lat": lat,
                    "lon": lon,
                    "pop": pop,
                    "area": area,
                }
            )
        return out


class MockVulnerabilityProvider:
    """Simulates a vulnerability/demographic source with nullable factors."""

    name = "mock_vulnerability"
    domain = "vulnerability"

    def fetch_vulnerability(
        self,
        location_id: str,
        reference_date: datetime,
        **options: Any,
    ) -> Dict[str, Any]:
        scenario = _current_scenario(location_id)
        seed = options.get("seed", 2026)
        ward_factors = {
            "DEMO-WARD-01": (0.24, 0.31, 0.12, 18125.0, 0.5, 0.42, 0.7, 0.85, 0.6, 0.4, 0.1),
            "DEMO-WARD-02": (0.18, 0.27, 0.2, 17600.0, 0.55, 0.5, 0.6, 0.8, 0.65, 0.45, 0.15),
            "DEMO-WARD-03": (0.3, 0.35, 0.3, 15897.0, 0.7, 0.25, 0.3, 0.5, 0.35, 0.7, 0.4),
            "DEMO-ZONE-A": (0.22, 0.3, 0.16, 17500.0, 0.52, 0.44, 0.65, 0.82, 0.62, 0.42, 0.12),
        }
        if location_id in ward_factors:
            (old, child, worker, dens, housing, cooling, elec, water,
             health, socio, informal) = ward_factors[location_id]
            factors: Dict[str, Optional[float]] = {
                "elderly_population_share": max(0.0, min(1.0, old)),
                "children_population_share": max(0.0, min(1.0, child)),
                "outdoor_worker_share": max(0.0, min(1.0, worker)),
                "population_density_per_km2": dens,
                "housing_vulnerability_index": housing,
                "cooling_access_share": cooling,
                "electricity_reliability_index": elec,
                "water_access_share": water,
                "healthcare_accessibility_index": health,
                "socioeconomic_vulnerability_index": socio,
                "informal_settlement_share": informal,
            }
            if scenario == Scenario.DATA_POOR_AREA:
                # Data-poor areas may lack several factors → null + MISSING flag.
                for key in ("electricity_reliability_index", "cooling_access_share",
                            "healthcare_accessibility_index"):
                    factors[key] = None
            return {"location_id": location_id, "factors": factors}
        return {
            "location_id": location_id,
            "factors": {f: None for f in (
                "elderly_population_share", "children_population_share",
                "outdoor_worker_share", "population_density_per_km2",
                "housing_vulnerability_index", "cooling_access_share",
                "electricity_reliability_index", "water_access_share",
                "healthcare_accessibility_index", "socioeconomic_vulnerability_index",
                "informal_settlement_share",
            )},
        }


class MockHealthOutcomeProvider:
    """Simulates an aggregated, de-identified health surveillance source.

    Produces area-level daily aggregates only. Never individual records.
    """

    name = "mock_health"
    domain = "health"

    def fetch_outcomes(
        self,
        location_id: str,
        period_start: datetime,
        period_end: datetime,
        **options: Any,
    ) -> List[Dict[str, Any]]:
        scenario = _current_scenario(location_id)
        seed = options.get("seed", 2026)
        outcomes: List[Dict[str, Any]] = []
        cursor = period_start
        while cursor <= period_end:
            key = seed, scenario, location_id, cursor
            heat = max(0, int(gen.noise(*key, 0, 8)))
            heat = heat + (40 if scenario in (
                Scenario.EXTREME_HEAT, Scenario.HOT_NIGHT,
                Scenario.PERSISTENT_HEAT, Scenario.HEAT_PLUS_POLLUTION,
            ) else 4)
            outcomes.append(
                {
                    "location_id": location_id,
                    "period_start": cursor,
                    "period_end": cursor + timedelta(days=1),
                    "heat_illness_cases": heat,
                    "emergency_visits": heat * 3,
                    "hospital_admissions": max(0, heat * 2),
                    "respiratory_admissions": max(0, int(heat * 1.2)),
                    "cardiovascular_admissions": max(0, int(heat * 0.9)),
                    "mortality_count": None,  # not lawfully available in demo
                    "surveillance_indicators": {"heat_shift_detected": heat > 30},
                }
            )
            cursor += timedelta(days=1)
        return outcomes


def register_all_mock_providers() -> Dict[str, object]:
    providers = [
        MockWeatherObservationProvider(),
        MockWeatherForecastProvider(),
        MockAirQualityProvider(),
        MockGeoSpatialProvider(),
        MockVulnerabilityProvider(),
        MockHealthOutcomeProvider(),
    ]
    for p in providers:
        register_provider(p)
    return {p.name: p for p in providers}