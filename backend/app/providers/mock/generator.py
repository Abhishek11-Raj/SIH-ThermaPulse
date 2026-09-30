"""Deterministic generator core for mock providers.

Every value derives from a seeded RNG keyed by ``(seed, scenario, location,
timestamp)`` so outputs are stable across runs and machines.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime
from typing import Dict, Optional, Tuple

from ...core.enums import Scenario

FLOAT_EPS = 1e-9

# Scenario → environmental profile. Synthetic for demo/tests only.
SCENARIO_PROFILES: Dict[Scenario, Dict[str, float]] = {
    Scenario.NORMAL_DAY: {
        "tmin": 24.0, "tmax": 32.0, "rh_base": 55.0,
        "pm25": 40.0, "aqi": 90.0, "gap_prob": 0.0,
    },
    Scenario.EXTREME_HEAT: {
        "tmin": 28.0, "tmax": 45.0, "rh_base": 28.0,
        "pm25": 60.0, "aqi": 140.0, "gap_prob": 0.0,
    },
    Scenario.HOT_NIGHT: {
        "tmin": 30.0, "tmax": 42.0, "rh_base": 55.0,
        "pm25": 65.0, "aqi": 150.0, "gap_prob": 0.0,
    },
    Scenario.PERSISTENT_HEAT: {
        "tmin": 27.0, "tmax": 41.0, "rh_base": 35.0,
        "pm25": 70.0, "aqi": 155.0, "gap_prob": 0.0,
    },
    Scenario.HEAT_PLUS_POLLUTION: {
        "tmin": 28.0, "tmax": 44.0, "rh_base": 40.0,
        "pm25": 185.0, "aqi": 260.0, "gap_prob": 0.0,
    },
    Scenario.DATA_POOR_AREA: {
        "tmin": 26.0, "tmax": 38.0, "rh_base": 45.0,
        "pm25": 80.0, "aqi": 170.0, "gap_prob": 0.6,
    },
}


def _rng(seed: int, scenario: Scenario, location_id: str, moment: datetime) -> random.Random:
    key = f"{seed}|{scenario.value}|{location_id}|{moment.isoformat()}"
    digest = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:12], 16)
    return random.Random(digest)


def noise(
    seed: int,
    scenario: Scenario,
    location_id: str,
    moment: datetime,
    low: float = -1.0,
    high: float = 1.0,
) -> float:
    """Deterministic per-(time, location) noise in [low, high]."""
    return _rng(seed, scenario, location_id, moment).uniform(low, high)


def profile(scenario: Scenario) -> Dict[str, float]:
    return SCENARIO_PROFILES[scenario]


def should_record(
    seed: int,
    scenario: Scenario,
    location_id: str,
    moment: datetime,
    gap_prob: float,
) -> bool:
    """Whether a record exists at this timestep (false ⇒ genuine data gap)."""
    if gap_prob <= FLOAT_EPS:
        return True
    return _rng(seed, scenario, location_id, moment).random() >= gap_prob


def diurnal_temperature(
    seed: int,
    scenario: Scenario,
    location_id: str,
    moment: datetime,
) -> float:
    p = profile(scenario)
    hour = moment.hour + moment.minute / 60.0
    tmin, tmax = p["tmin"], p["tmax"]
    # Daily cycle: maximum ≈ 15:00, minimum ≈ 03:00.
    mean = (tmax + tmin) / 2.0
    amp = (tmax - tmin) / 2.0
    base = mean - amp * _cos_cycle(hour)
    return round(base + noise(seed, scenario, location_id, moment, -1.5, 1.5), 1)


def _cos_cycle(hour: float) -> float:
    # cos(2π(hour - 15)/24): +1 at 15:00 (max), -1 at 03:00 (min).
    import math

    return math.cos(2.0 * math.pi * (hour - 15.0) / 24.0)


def relative_humidity(
    seed: int,
    scenario: Scenario,
    location_id: str,
    moment: datetime,
) -> float:
    p = profile(scenario)
    hour = moment.hour
    # Higher RH at night, lower in the afternoon.
    cycle = 0.5 + 0.5 * _cos_cycle(hour)
    rh = max(10.0, min(98.0, p["rh_base"] + (cycle - 0.5) * 20.0))
    return round(rh + noise(seed, scenario, location_id, moment, -6, 6), 1)


def base_weather_fields(
    seed: int,
    scenario: Scenario,
    location_id: str,
    moment: datetime,
) -> dict:
    """Provider-native weather field set (note: NOT canonical keys)."""
    p = profile(scenario)
    return {
        "temp_c": diurnal_temperature(seed, scenario, location_id, moment),
        "rel_hum_pct": relative_humidity(seed, scenario, location_id, moment),
        "wind_mps": round(3.0 + abs(noise(seed, scenario, location_id, moment, -1.5, 4.0)), 1),
        "wind_dir_deg": round(abs(noise(seed, scenario, location_id, moment) * 180), 1),
        "pressure_hpa": round(1004.0 + noise(seed, scenario, location_id, moment, -4, 4), 1),
        "rainfall_mm": 0.0,
        "cloud_cover_pct": round(max(0.0, p["rh_base"] * 0.4 + noise(
            seed, scenario, location_id, moment, -15, 15
        )), 1),
        "solar_wm2": _solar(seed, scenario, location_id, moment),
        "visibility_km": round(8.0 + abs(noise(seed, scenario, location_id, moment, -3, 5)), 1),
        "uv_index": _uv(seed, scenario, location_id, moment),
    }


def _solar(
    seed: int, scenario: Scenario, location_id: str, moment: datetime
) -> float:
    hour = moment.hour + moment.minute / 60.0
    if 6 <= hour <= 18:
        factor = 0.5 - 0.5 * _cos_cycle(hour)  # ≈1 around noon
        watt = 1000.0 * factor + noise(seed, scenario, location_id, moment, -60, 60)
        return round(max(0.0, watt), 1)
    return 0.0


def _uv(seed: int, scenario: Scenario, location_id: str, moment: datetime) -> float:
    hour = moment.hour
    if 9 <= hour <= 16:
        v = (11.0 if hour >= 11 else 6.0) + noise(seed, scenario, location_id, moment, -1, 1)
        return round(max(0.0, v), 1)
    return 0.0


def air_quality_fields(
    seed: int, scenario: Scenario, location_id: str, moment: datetime
) -> dict:
    """Provider-native AQ field set."""
    p = profile(scenario)
    base = p["pm25"]
    return {
        "pm25_ugm3": round(max(5.0, base + noise(seed, scenario, location_id, moment, -15, 15)), 1),
        "pm10_ugm3": None,  # some sensors omit PM10 — must stay null downstream
        "o3_ugm3": round(60.0 + noise(seed, scenario, location_id, moment, -20, 40), 1),
        "no2_ugm3": round(40.0 + noise(seed, scenario, location_id, moment, -15, 30), 1),
        "so2_ugm3": round(12.0 + noise(seed, scenario, location_id, moment, -5, 12), 1),
        "co_mgm3": round(0.9 + noise(seed, scenario, location_id, moment, -0.4, 0.9), 2),
        "aqi_index": round(p["aqi"] + noise(seed, scenario, location_id, moment, -20, 20), 0),
    }


def hourly_step(seed: int, scenario: Scenario, location_id: str, moment: datetime) -> float:
    """Deterministic hourly temperature step used by forecast generator."""
    return diurnal_temperature(seed, scenario, location_id, moment)