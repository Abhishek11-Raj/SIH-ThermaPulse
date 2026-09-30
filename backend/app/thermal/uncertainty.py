"""Uncertainty and Quality Propagation — STEP 3.

Implements quality propagation from input data through thermal calculations.
Every derived metric retains input-quality context.

Quality flags:
- VALID: High confidence, all inputs valid
- SUSPECT: Some concerns, extrapolated or borderline
- MISSING: Required inputs missing
- STALE: Data older than freshness threshold
- INVALID: Inputs outside plausible bounds
- IMPUTED: Value estimated from other variables
- UNAVAILABLE: Cannot be computed (missing dependencies)

Uncertainty propagation rules:
- If any required input is MISSING → output is MISSING
- If any required input is INVALID → output is INVALID
- If any required input is SUSPECT → output is SUSPECT
- If inputs have mixed quality → output takes worst quality
- Extrapolated results are at most SUSPECT
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..core.enums import QualityFlag
from .schemas import ThermalIndices, ThermalQualityUncertainty


@dataclass
class InputQuality:
    """Quality assessment for a single input variable."""
    variable: str
    value: Optional[float]
    quality: QualityFlag
    issue: Optional[str] = None


@dataclass
class QualityPropagationResult:
    """Result of quality propagation for a thermal index."""
    index_name: str
    output_quality: QualityFlag
    input_qualities: Dict[str, QualityFlag]
    limiting_factors: List[str]
    estimated: bool = False
    extrapolation: bool = False


# Quality hierarchy (worst to best)
QUALITY_HIERARCHY = {
    QualityFlag.INVALID: 0,
    QualityFlag.MISSING: 1,
    QualityFlag.STALE: 2,
    QualityFlag.SUSPECT: 3,
    QualityFlag.IMPUTED: 4,
    QualityFlag.VALID: 5,
}


def worst_quality(qualities: List[QualityFlag]) -> QualityFlag:
    """Return the worst quality from a list."""
    if not qualities:
        return QualityFlag.MISSING
    return min(qualities, key=lambda q: QUALITY_HIERARCHY.get(q, 100))


def propagate_quality(
    index_name: str,
    required_inputs: List[str],
    input_qualities: Dict[str, QualityFlag],
    estimated: bool = False,
    extrapolation: bool = False,
) -> QualityPropagationResult:
    """
    Propagate input qualities to output index.

    Args:
        index_name: Name of the thermal index
        required_inputs: List of required input variable names
        input_qualities: Dict of input variable -> quality
        estimated: Whether the index was estimated (not directly calculated)
        extrapolation: Whether the result was extrapolated beyond validity range

    Returns:
        QualityPropagationResult with output quality
    """
    # Ensure input_qualities is a dict
    if not isinstance(input_qualities, dict):
        input_qualities = {}
    
    # Get qualities for required inputs
    req_qualities = []
    limiting = []

    for var in required_inputs:
        qual = input_qualities.get(var, QualityFlag.MISSING)
        req_qualities.append(qual)
        if qual in (QualityFlag.MISSING, QualityFlag.INVALID):
            limiting.append(f"{var}={qual.value}")

    # Base quality is worst of required inputs
    output_quality = worst_quality(req_qualities)

    # If estimated, quality cannot be better than SUSPECT
    if estimated:
        if QUALITY_HIERARCHY[output_quality] > QUALITY_HIERARCHY[QualityFlag.SUSPECT]:
            output_quality = QualityFlag.SUSPECT
            limiting.append("estimated")

    # If extrapolated, quality cannot be better than SUSPECT
    if extrapolation:
        if QUALITY_HIERARCHY[output_quality] > QUALITY_HIERARCHY[QualityFlag.SUSPECT]:
            output_quality = QualityFlag.SUSPECT
            limiting.append("extrapolated")

    return QualityPropagationResult(
        index_name=index_name,
        output_quality=output_quality,
        input_qualities={k: v for k, v in input_qualities.items() if k in required_inputs},
        limiting_factors=limiting,
        estimated=estimated,
        extrapolation=extrapolation,
    )


def build_input_quality_map(
    inp,
    inp_quality: Optional[Dict[str, QualityFlag]] = None
) -> Dict[str, QualityFlag]:
    """
    Build input quality map from ThermalInput and optional quality dict.

    Args:
        inp: ThermalInput object
        inp_quality: Optional dict of variable -> quality

    Returns:
        Dict of all thermal input variables -> quality
    """
    quality_map = inp_quality or {}

    # Default quality for present values
    for var, val in {
        "air_temperature_c": inp.air_temperature_c,
        "relative_humidity": inp.relative_humidity,
        "wind_speed_ms": inp.wind_speed_ms,
        "wind_direction_deg": inp.wind_direction_deg,
        "pressure_hpa": inp.pressure_hpa,
        "solar_radiation_wm2": inp.solar_radiation_wm2,
        "cloud_cover_pct": inp.cloud_cover_pct,
    }.items():
        if var not in quality_map:
            if val is None:
                quality_map[var] = QualityFlag.MISSING
            else:
                quality_map[var] = QualityFlag.VALID

    return quality_map


def assess_thermal_input_quality(
    inp,
    inp_quality: Optional[Dict[str, QualityFlag]] = None
) -> ThermalQualityUncertainty:
    """
    Assess quality and uncertainty for all thermal indices based on inputs.

    Returns a ThermalQualityUncertainty object with per-index quality flags
    and overall summaries.
    """
    quality_map = build_input_quality_map(inp, inp_quality)

    # Define required inputs for each index
    index_requirements = {
        "heat_index": ["air_temperature_c", "relative_humidity"],
        "wet_bulb": ["air_temperature_c", "relative_humidity"],
        "wbgt": ["air_temperature_c", "relative_humidity", "wind_speed_ms", "solar_radiation_wm2"],
        "utci": ["air_temperature_c", "relative_humidity", "wind_speed_ms", "solar_radiation_wm2"],
        "mrt": ["air_temperature_c", "solar_radiation_wm2"],
        "nighttime": ["air_temperature_c"],
        "exposure": ["air_temperature_c", "relative_humidity", "wind_speed_ms", "solar_radiation_wm2"],
    }

    # Check each index
    per_index_quality = {}
    for index_name, required in index_requirements.items():
        result = propagate_quality(index_name, required, quality_map)
        per_index_quality[index_name] = result

    # Build summary
    quality_summary = {
        "overall": worst_quality(list(quality_map.values())).value,
        "input_variables": {k: v.value for k, v in quality_map.items()},
        "per_index": {k: v.output_quality.value for k, v in per_index_quality.items()},
        "limiting_factors": {k: v.limiting_factors for k, v in per_index_quality.items()},
    }

    uncertainty_summary = {
        "estimated_indices": [k for k, v in per_index_quality.items() if v.estimated],
        "extrapolated_indices": [k for k, v in per_index_quality.items() if v.extrapolation],
        "unavailable_indices": [k for k, v in per_index_quality.items()
                               if v.output_quality == QualityFlag.MISSING],
    }

    return ThermalQualityUncertainty(
        quality_summary=quality_summary,
        uncertainty_summary=uncertainty_summary,
        heat_index_quality=per_index_quality.get("heat_index", {}).output_quality,
        wet_bulb_quality=per_index_quality.get("wet_bulb", {}).output_quality,
        wbgt_quality=per_index_quality.get("wbgt", {}).output_quality,
        utci_quality=per_index_quality.get("utci", {}).output_quality,
        mrt_quality=per_index_quality.get("mrt", {}).output_quality,
        nighttime_quality=per_index_quality.get("nighttime", {}).output_quality,
        exposure_quality=per_index_quality.get("exposure", {}).output_quality,
        memory_quality=per_index_quality.get("exposure", {}).output_quality,  # Same as exposure
    )


def round_to_precision(value: Optional[float], quality: QualityFlag) -> Optional[float]:
    """
    Round value to appropriate precision based on quality.

    - VALID/FRESH: 0.1°C precision
    - AGING/SUSPECT: 0.5°C precision
    - IMPUTED/STALE: 1.0°C precision
    - Others: None (no value)
    """
    if value is None:
        return None

    if quality in (QualityFlag.VALID, QualityFlag.FRESH):
        return round(value, 1)
    elif quality in (QualityFlag.AGING, QualityFlag.SUSPECT):
        return round(value * 2) / 2  # Round to 0.5
    elif quality in (QualityFlag.IMPUTED, QualityFlag.STALE):
        return round(value)  # Round to 1.0
    else:
        return None  # Don't report value for missing/invalid/unavailable