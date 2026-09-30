"""Wet Bulb Globe Temperature (WBGT) implementation — STEP 3.

Implements WBGT for both outdoor (sun) and indoor/shade contexts.

Outdoor (sun): WBGT = 0.7 * Tw + 0.2 * Tg + 0.1 * Ta
Indoor/shade: WBGT = 0.7 * Tw + 0.3 * Tg

Where:
- Tw = wet-bulb temperature (natural wet bulb)
- Tg = globe temperature
- Ta = air temperature (dry bulb)

If globe temperature is not directly available, it can be estimated from
solar radiation, wind speed, and air temperature using the Liljegren method.

References:
- Liljegren et al. (2008). "A heat stress model for the prevention of
  exertional heat illness." Medicine & Science in Sports & Exercise.
- ISO 7243:2017 "Ergonomics of the thermal environment"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .schemas import ThermalInput
from ..core.enums import QualityFlag
from .wet_bulb import calculate_wet_bulb, WetBulbResult


@dataclass
class WBGTResult:
    """WBGT calculation result."""
    wbgt_c: Optional[float]
    wbgt_indoor_c: Optional[float]
    method: str
    estimated_components: dict
    quality: QualityFlag
    extrapolated: bool
    validity_note: Optional[str]


def estimate_globe_temperature(
    temp_c: float,
    solar_radiation_wm2: float,
    wind_speed_ms: float,
    pressure_hpa: float = 1013.25
) -> tuple:
    """
    Estimate globe temperature (Tg) using Liljegren method.

    Tg = Ta + (S * (1 - albedo) / (h_c + h_r)) + (ε * σ * (Ta^4 - Tg^4) / (h_c + h_r))

    Simplified form for standard 150mm black globe:
    Tg ≈ Ta + 0.017 * S / (wind_speed^0.6)  (very rough approximation)

    More accurate formulation from Liljegren 2008:
    """
    if solar_radiation_wm2 is None or solar_radiation_wm2 <= 0:
        return temp_c, False  # No radiation = globe = air temp

    # Convection coefficient (W/m²·K) for 150mm sphere
    h_c = 1.4 * (wind_speed_ms**0.6) * (1013.25 / pressure_hpa)**0.6

    # Radiative heat transfer coefficient (linearized)
    # h_r ≈ 4 * ε * σ * T^3 ≈ 5.5 W/m²·K at 300K
    h_r = 5.5

    # Globe absorptivity (black globe = 0.95)
    alpha = 0.95
    # Net radiation absorbed by globe
    S = solar_radiation_wm2 * alpha

    # Tg ≈ Ta + S / (h_c + h_r)
    tg = temp_c + S / (h_c + h_r)

    return tg, True


def calculate_wbgt(
    temp_c: float,
    wet_bulb_c: float,
    globe_temp_c: float,
    indoor: bool = False,
    quality: Optional[QualityFlag] = None
) -> WBGTResult:
    """
    Calculate WBGT from component temperatures.

    Args:
        temp_c: Air temperature (dry bulb)
        wet_bulb_c: Natural wet-bulb temperature
        globe_temp_c: Globe temperature
        indoor: If True, use indoor formula (0.7 Tw + 0.3 Tg)
        quality: Input quality flag

    Returns:
        WBGTResult with outdoor and indoor WBGT values
    """
    base_quality = quality or QualityFlag.VALID
    extrapolated = False
    validity_note = None
    estimated = {}

    # Outdoor WBGT
    wbgt_out = 0.7 * wet_bulb_c + 0.2 * globe_temp_c + 0.1 * temp_c

    # Indoor WBGT
    wbgt_in = 0.7 * wet_bulb_c + 0.3 * globe_temp_c

    estimated["globe_temp"] = globe_temp_c != temp_c
    estimated["wet_bulb"] = True  # Always calculated

    if indoor:
        result = wbgt_in
        method = "indoor_0.7Tw_0.3Tg"
    else:
        result = wbgt_out
        method = "outdoor_0.7Tw_0.2Tg_0.1Ta"

    return WBGTResult(
        wbgt_c=wbgt_out if not indoor else None,
        wbgt_indoor_c=wbgt_in if indoor else None,
        method=method,
        estimated_components=estimated,
        quality=base_quality,
        extrapolated=extrapolated,
        validity_note=validity_note,
    )


def calculate_wbgt_from_input(
    inp: ThermalInput,
    wet_bulb_result: WetBulbResult,
    indoor: bool = False,
    quality: Optional[QualityFlag] = None,
    wbgt_method: str = "liljegren"
) -> WBGTResult:
    """
    Calculate WBGT from ThermalInput and wet-bulb result.

    If globe temperature is not available, estimates it from radiation and wind.
    """
    if inp.air_temperature_c is None:
        return WBGTResult(
            wbgt_c=None,
            wbgt_indoor_c=None,
            method="wbgt",
            estimated_components={},
            quality=QualityFlag.MISSING,
            extrapolated=False,
            validity_note="Missing air temperature",
        )

    if wet_bulb_result.wet_bulb_c is None:
        return WBGTResult(
            wbgt_c=None,
            wbgt_indoor_c=None,
            method="wbgt",
            estimated_components={},
            quality=QualityFlag.MISSING,
            extrapolated=False,
            validity_note="Wet-bulb temperature unavailable",
        )

    # Estimate globe temperature if not provided
    if inp.solar_radiation_wm2 is not None and inp.solar_radiation_wm2 > 0 and inp.wind_speed_ms is not None:
        globe_temp, estimated = estimate_globe_temperature(
            inp.air_temperature_c,
            inp.solar_radiation_wm2,
            inp.wind_speed_ms,
            inp.pressure_hpa or 1013.25
        )
    else:
        # No radiation data -> globe ≈ air temp (conservative)
        globe_temp = inp.air_temperature_c
        estimated = False

    return calculate_wbgt(
        inp.air_temperature_c,
        wet_bulb_result.wet_bulb_c,
        globe_temp,
        indoor,
        quality,
    )