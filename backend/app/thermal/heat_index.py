"""Heat Index implementation — STEP 3.

Implements the NOAA/NWS Rothfusz regression equation for Heat Index.
Valid for temperatures >= 27°C (80°F) and relative humidity >= 40%.
Outside this domain, the result is flagged as extrapolated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .schemas import ThermalInput, ThermalQualityUncertainty
from ..core.enums import QualityFlag


@dataclass
class HeatIndexResult:
    """Heat Index calculation result."""
    heat_index_c: Optional[float]
    heat_index_f: Optional[float]
    method: str
    quality: QualityFlag
    extrapolated: bool
    validity_note: Optional[str]


def calculate_heat_index(
    temp_c: float,
    rh_pct: float,
    quality: Optional[QualityFlag] = None
) -> HeatIndexResult:
    """
    Calculate Heat Index using NOAA/NWS Rothfusz equation.

    The equation is valid for:
    - Temperature >= 27°C (80.6°F)
    - Relative humidity >= 40%

    Outside this domain, a simplified linear approximation is used
    and the result is flagged as extrapolated.

    Args:
        temp_c: Air temperature in Celsius
        rh_pct: Relative humidity in percent (0-100)
        quality: Input quality flag

    Returns:
        HeatIndexResult with heat index in Celsius and Fahrenheit
    """
    # Convert to Fahrenheit for the formula
    temp_f = temp_c * 9.0 / 5.0 + 32.0
    rh = rh_pct

    extrapolated = False
    validity_note = None
    base_quality = quality or QualityFlag.VALID

    # Check validity domain
    if temp_f < 80.0 or rh < 40.0:
        extrapolated = True
        if temp_f < 80.0:
            validity_note = f"Temperature {temp_f:.1f}°F below Heat Index validity threshold (80°F)"
        else:
            validity_note = f"Relative humidity {rh:.1f}% below Heat Index validity threshold (40%)"

    # Rothfusz regression equation
    hi_f = (
        -42.379
        + 2.04901523 * temp_f
        + 10.14333127 * rh
        - 0.22475541 * temp_f * rh
        - 0.00683783 * temp_f * temp_f
        - 0.05481717 * rh * rh
        + 0.00122874 * temp_f * temp_f * rh
        + 0.00085282 * temp_f * rh * rh
        - 0.00000199 * temp_f * temp_f * rh * rh
    )

    # Adjustments for extreme conditions
    if rh < 13.0 and 80.0 <= temp_f <= 112.0:
        # Low humidity adjustment
        adj = ((13.0 - rh) / 4.0) * math.sqrt((17.0 - abs(temp_f - 95.0)) / 17.0)
        hi_f -= adj
    elif rh > 85.0 and 80.0 <= temp_f <= 87.0:
        # High humidity adjustment
        adj = ((rh - 85.0) / 10.0) * ((87.0 - temp_f) / 5.0)
        hi_f += adj

    hi_c = (hi_f - 32.0) * 5.0 / 9.0

    # Determine quality
    if extrapolated:
        result_quality = QualityFlag.SUSPECT
        if base_quality == QualityFlag.VALID:
            result_quality = QualityFlag.SUSPECT
        elif base_quality in (QualityFlag.SUSPECT, QualityFlag.AGING):
            result_quality = base_quality
    else:
        result_quality = base_quality

    return HeatIndexResult(
        heat_index_c=hi_c,
        heat_index_f=hi_f,
        method="rothfusz",
        quality=result_quality,
        extrapolated=extrapolated,
        validity_note=validity_note,
    )


def calculate_heat_index_from_input(
    inp: ThermalInput,
    quality: Optional[QualityFlag] = None
) -> HeatIndexResult:
    """Calculate Heat Index from ThermalInput object."""
    if inp.air_temperature_c is None or inp.relative_humidity is None:
        return HeatIndexResult(
            heat_index_c=None,
            heat_index_f=None,
            method="rothfusz",
            quality=QualityFlag.MISSING,
            extrapolated=False,
            validity_note="Missing required inputs: air_temperature_c and/or relative_humidity",
        )

    return calculate_heat_index(inp.air_temperature_c, inp.relative_humidity, quality)