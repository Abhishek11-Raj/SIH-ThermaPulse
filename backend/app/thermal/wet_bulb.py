"""Wet-Bulb Temperature implementation — STEP 3.

Implements multiple methods for wet-bulb temperature calculation:
1. Stull (2011) - fast approximation, valid for typical meteorological conditions
2. Davies-Jones (2008) - iterative psychrometric solution
3. Iterative solution - most accurate but slower

References:
- Stull, R. (2011). Wet-bulb temperature from relative humidity and air temperature.
  Journal of Applied Meteorology and Climatology, 50(11), 2267-2269.
- Davies-Jones, R. (2008). An efficient and accurate method for computing
  wet-bulb temperature along pseudoadiabats. Monthly Weather Review, 136(7), 2764-2785.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .schemas import ThermalInput
from ..core.enums import QualityFlag


@dataclass
class WetBulbResult:
    """Wet-bulb temperature calculation result."""
    wet_bulb_c: Optional[float]
    method: str
    quality: QualityFlag
    extrapolated: bool
    validity_note: Optional[str]


# Constants
ES0 = 611.2  # Saturation vapor pressure at 0°C (Pa)
LV0 = 2.501e6  # Latent heat of vaporization at 0°C (J/kg)
CP = 1005.0  # Specific heat of dry air at constant pressure (J/kg·K)
R_D = 287.04  # Gas constant for dry air (J/kg·K)
R_V = 461.5  # Gas constant for water vapor (J/kg·K)
EPS = R_D / R_V  # Ratio of gas constants (~0.622)


def saturation_vapor_pressure(temp_c: float) -> float:
    """Saturation vapor pressure over liquid water (Pa) using Tetens formula."""
    return ES0 * math.exp((17.67 * temp_c) / (temp_c + 243.5))


def mixing_ratio_from_rh(temp_c: float, rh_pct: float, pressure_hpa: float = 1013.25) -> float:
    """Calculate mixing ratio from temperature, RH, and pressure."""
    es = saturation_vapor_pressure(temp_c)
    e = es * rh_pct / 100.0
    p_pa = pressure_hpa * 100.0
    return EPS * e / (p_pa - e)


def calculate_wet_bulb_stull(temp_c: float, rh_pct: float) -> tuple:
    """
    Stull (2011) approximation for wet-bulb temperature.
    Valid for: -20°C <= T <= 50°C, 1% <= RH <= 100%
    Accuracy: ~0.3°C RMSE for typical conditions.
    """
    if temp_c is None or rh_pct is None:
        return None, "Missing inputs"

    # Clamp RH to valid range
    rh = max(1.0, min(100.0, rh_pct))

    tw = (temp_c * math.atan(0.151977 * math.sqrt(rh + 8.313659))
          + math.atan(temp_c + rh)
          - math.atan(rh - 1.676331)
          + 0.00391838 * rh**1.5 * math.atan(0.023101 * rh)
          - 4.686035)

    return tw, "stull"


def calculate_wet_bulb_davies_jones(temp_c: float, rh_pct: float, pressure_hpa: float = 1013.25) -> tuple:
    """
    Davies-Jones (2008) iterative psychrometric solution.
    More accurate than Stull, especially at extremes.
    """
    if temp_c is None or rh_pct is None:
        return None, "Missing inputs"

    rh = max(0.01, min(100.0, rh_pct))

    # Initial guess using Stull
    tw, _ = calculate_wet_bulb_stull(temp_c, rh)
    if tw is None:
        return None, "Stull failed"

    # Iterate to convergence
    p_pa = pressure_hpa * 100.0
    w = mixing_ratio_from_rh(temp_c, rh, pressure_hpa)

    for _ in range(10):
        es_tw = saturation_vapor_pressure(tw)
        e_tw = es_tw  # saturated at wet-bulb temp
        w_s = EPS * e_tw / (p_pa - e_tw)

        # Psychrometric equation: w = w_s - CP * (T - Tw) / LV
        lv = LV0 - 2370.0 * tw  # Latent heat as function of temperature
        f = w - w_s + CP * (temp_c - tw) / lv

        # Derivative for Newton-Raphson
        des_dtw = es_tw * (17.67 * 243.5) / (tw + 243.5)**2
        dw_s_dtw = EPS * p_pa * des_dtw / (p_pa - e_tw)**2
        df_dtw = -dw_s_dtw - CP / lv

        if abs(df_dtw) < 1e-10:
            break

        tw_new = tw - f / df_dtw

        if abs(tw_new - tw) < 0.001:
            tw = tw_new
            break
        tw = tw_new

    return tw, "davies_jones"


def calculate_wet_bulb_iterative(temp_c: float, rh_pct: float, pressure_hpa: float = 1013.25) -> tuple:
    """
    Iterative solution using energy balance.
    Most physically accurate but slower.
    """
    if temp_c is None or rh_pct is None:
        return None, "Missing inputs"

    rh = max(0.01, min(100.0, rh_pct))
    p_pa = pressure_hpa * 100.0

    # Initial guess
    tw = temp_c * 0.8  # Rough initial guess
    w = mixing_ratio_from_rh(temp_c, rh, pressure_hpa)

    for _ in range(20):
        es_tw = saturation_vapor_pressure(tw)
        e_tw = es_tw
        w_s = EPS * e_tw / (p_pa - e_tw)

        lv = LV0 - 2370.0 * tw
        # Energy balance: CP * (T - Tw) = LV * (w_s - w)
        tw_new = temp_c - lv * (w_s - w) / CP

        if abs(tw_new - tw) < 0.0001:
            tw = tw_new
            break
        tw = tw_new

    return tw, "iterative"


def calculate_wet_bulb(
    temp_c: float,
    rh_pct: float,
    pressure_hpa: float = 1013.25,
    method: str = "stull",
    quality: Optional[QualityFlag] = None
) -> WetBulbResult:
    """
    Calculate wet-bulb temperature using specified method.

    Args:
        temp_c: Air temperature in Celsius
        rh_pct: Relative humidity in percent (0-100)
        pressure_hpa: Atmospheric pressure in hPa
        method: "stull", "davies_jones", or "iterative"
        quality: Input quality flag

    Returns:
        WetBulbResult with wet-bulb temperature in Celsius
    """
    extrapolated = False
    validity_note = None
    base_quality = quality or QualityFlag.VALID

    if method == "stull":
        tw, used_method = calculate_wet_bulb_stull(temp_c, rh_pct)
        if temp_c < -20 or temp_c > 50 or rh_pct < 1 or rh_pct > 100:
            extrapolated = True
            validity_note = "Inputs outside Stull validity range (-20 to 50°C, 1-100% RH)"
    elif method == "davies_jones":
        tw, used_method = calculate_wet_bulb_davies_jones(temp_c, rh_pct, pressure_hpa)
    elif method == "iterative":
        tw, used_method = calculate_wet_bulb_iterative(temp_c, rh_pct, pressure_hpa)
    else:
        tw, used_method = calculate_wet_bulb_stull(temp_c, rh_pct)

    if tw is None:
        return WetBulbResult(
            wet_bulb_c=None,
            method=method,
            quality=QualityFlag.INVALID,
            extrapolated=False,
            validity_note="Calculation failed",
        )

    # Wet-bulb cannot exceed dry-bulb
    if tw > temp_c:
        tw = temp_c
        extrapolated = True
        validity_note = "Wet-bulb exceeds dry-bulb; clamped"

    # Determine quality
    if extrapolated:
        result_quality = QualityFlag.SUSPECT
    else:
        result_quality = base_quality

    return WetBulbResult(
        wet_bulb_c=tw,
        method=used_method,
        quality=result_quality,
        extrapolated=extrapolated,
        validity_note=validity_note,
    )


def calculate_wet_bulb_from_input(
    inp: ThermalInput,
    quality: Optional[QualityFlag] = None,
    method: str = "stull"
) -> WetBulbResult:
    """Calculate wet-bulb temperature from ThermalInput object."""
    if inp.air_temperature_c is None or inp.relative_humidity is None:
        return WetBulbResult(
            wet_bulb_c=None,
            method=method,
            quality=QualityFlag.MISSING,
            extrapolated=False,
            validity_note="Missing required inputs: air_temperature_c and/or relative_humidity",
        )

    pressure = inp.pressure_hpa or 1013.25
    return calculate_wet_bulb(
        inp.air_temperature_c,
        inp.relative_humidity,
        pressure,
        method,
        quality,
    )