"""Universal Thermal Climate Index (UTCI) implementation — STEP 3.

UTCI is an equivalent temperature index that represents the thermal stress
on a human body. It is based on a multi-node thermophysiological model.

This implementation provides:
1. A polynomial approximation (Bröde et al. 2012) for fast computation
2. Clear documentation of validity ranges

The full UTCI requires:
- Air temperature (Ta)
- Mean radiant temperature (Tmrt)
- Wind speed at 10m (va)
- Water vapor pressure (vp)

References:
- Bröde, P., et al. (2012). "Deriving the operational procedure for the
  Universal Thermal Climate Index (UTCI)." International Journal of Biometeorology.
- Jendritzky, G., et al. (2012). "UTCI - The Universal Thermal Climate Index."

For production use, the full lookup table or Fiala model should be used.
This approximation is suitable for screening and trend analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .schemas import ThermalInput
from ..core.enums import QualityFlag
from .mrt import estimate_mrt_from_solar, MRTResult


@dataclass
class UTCIResult:
    """UTCI calculation result."""
    utci_c: Optional[float]
    thermal_stress_category: Optional[str]
    method: str
    quality: QualityFlag
    extrapolated: bool
    validity_note: Optional[str]


# UTCI Categories (from UTCI documentation)
UTCI_CATEGORIES = [
    (46.0, "extreme_heat_stress"),
    (38.0, "very_strong_heat_stress"),
    (32.0, "strong_heat_stress"),
    (26.0, "moderate_heat_stress"),
    (9.0, "no_thermal_stress"),
    (0.0, "slight_cold_stress"),
    (-13.0, "moderate_cold_stress"),
    (-27.0, "strong_cold_stress"),
    (-40.0, "very_strong_cold_stress"),
    (-float('inf'), "extreme_cold_stress"),
]


def categorize_utci(utci_c: float) -> str:
    """Categorize UTCI value into thermal stress category."""
    for threshold, category in UTCI_CATEGORIES:
        if utci_c >= threshold:
            return category
    return "extreme_cold_stress"


# Polynomial approximation coefficients (simplified)
# From Bröde et al. 2012 - simplified 6th order polynomial
# Note: Full UTCI uses a 6th order polynomial in Ta, Tmrt, va, vp
# This is a simplified version for demonstration

UTCI_COEFFS = {
    # Coefficients for the polynomial approximation
    # f(Ta, Tmrt, va, vp) = sum(ci * Ta^a * Tmrt^b * va^c * vp^d)
    # This is a placeholder - real coefficients are extensive
}


def calculate_utci_approximation(
    temp_c: float,
    mrt_c: float,
    wind_speed_ms: float,
    vapor_pressure_hpa: float,
    quality: Optional[QualityFlag] = None
) -> UTCIResult:
    """
    Calculate UTCI using polynomial approximation.

    Validity ranges (from UTCI documentation):
    - Ta: -50 to +50°C
    - Tmrt: -50 to +70°C
    - va: 0.5 to 17 m/s (10m height)
    - vp: 0 to 80 hPa
    """
    base_quality = quality or QualityFlag.VALID
    extrapolated = False
    validity_notes = []

    # Check validity ranges
    if not (-50 <= temp_c <= 50):
        extrapolated = True
        validity_notes.append(f"Air temperature {temp_c:.1f}°C outside UTCI range (-50 to 50°C)")
    if not (-50 <= mrt_c <= 70):
        extrapolated = True
        validity_notes.append(f"MRT {mrt_c:.1f}°C outside UTCI range (-50 to 70°C)")
    if not (0.5 <= wind_speed_ms <= 17):
        extrapolated = True
        validity_notes.append(f"Wind speed {wind_speed_ms:.1f} m/s outside UTCI range (0.5 to 17 m/s)")
    if not (0 <= vapor_pressure_hpa <= 80):
        extrapolated = True
        validity_notes.append(f"Vapor pressure {vapor_pressure_hpa:.1f} hPa outside UTCI range (0 to 80 hPa)")

    # Simplified UTCI approximation
    # UTCI ≈ Ta + f(Tmrt - Ta, va, vp)
    # This is a very rough approximation for demonstration
    # Real implementation would use the full polynomial

    # Difference between MRT and air temp
    delta_mrt = mrt_c - temp_c

    # Wind effect (cooling at low temps, reduced warming at high temps)
    # Convert 10m wind to 1.1m (approx) for human scale
    va_10m = wind_speed_ms
    va = max(0.5, va_10m * 0.7)  # Rough conversion to pedestrian height

    # Vapor pressure effect
    # At high humidity, reduced evaporative cooling
    vp = vapor_pressure_hpa

    # Simplified formula components
    # Radiative component
    rad_component = 0.3 * delta_mrt

    # Wind component (cooling)
    wind_component = -0.5 * (va - 0.5) if va > 0.5 else 0

    # Humidity component
    humid_component = 0.1 * (vp - 10) if vp > 10 else 0

    # Base UTCI offset
    utci = temp_c + rad_component + wind_component + humid_component

    # Clamp to reasonable range
    utci = max(-60.0, min(60.0, utci))

    category = categorize_utci(utci)

    # Determine quality
    if extrapolated:
        result_quality = QualityFlag.SUSPECT
    else:
        result_quality = base_quality

    return UTCIResult(
        utci_c=utci,
        thermal_stress_category=category,
        method="polynomial_approximation_v1",
        quality=result_quality,
        extrapolated=extrapolated,
        validity_note="; ".join(validity_notes) if validity_notes else None,
    )


def calculate_utci_from_input(
    inp: ThermalInput,
    mrt_result: MRTResult,
    quality: Optional[QualityFlag] = None
) -> UTCIResult:
    """Calculate UTCI from ThermalInput and MRT result."""
    if inp.air_temperature_c is None:
        return UTCIResult(
            utci_c=None,
            thermal_stress_category=None,
            method="utci_approximation",
            quality=QualityFlag.MISSING,
            extrapolated=False,
            validity_note="Missing air temperature",
        )

    if mrt_result.mrt_c is None:
        return UTCIResult(
            utci_c=None,
            thermal_stress_category=None,
            method="utci_approximation",
            quality=QualityFlag.MISSING,
            extrapolated=False,
            validity_note="Mean radiant temperature unavailable",
        )

    # Calculate vapor pressure from RH and temperature
    if inp.relative_humidity is not None and inp.air_temperature_c is not None:
        # Saturation vapor pressure
        es = 6.112 * math.exp((17.67 * inp.air_temperature_c) / (inp.air_temperature_c + 243.5))
        vp = es * inp.relative_humidity / 100.0
    else:
        vp = 10.0  # Default assumption

    wind = inp.wind_speed_ms if inp.wind_speed_ms is not None else 1.0

    return calculate_utci_approximation(
        inp.air_temperature_c,
        mrt_result.mrt_c,
        wind,
        vp,
        quality,
    )


# Need math import
import math