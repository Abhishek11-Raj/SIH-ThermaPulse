"""Mean Radiant Temperature (MRT) implementation — STEP 3.

MRT is the uniform temperature of an imaginary enclosure in which the radiant
heat transfer from the human body is equal to the radiant heat transfer in
the actual non-uniform environment.

Full MRT calculation requires:
- Shortwave (solar) radiation
- Longwave (terrestrial/atmospheric) radiation
- Surface temperatures and view factors

This implementation provides:
1. Solar-only estimation (when only shortwave is available)
2. Full radiative estimation (when longwave data available)
3. Clear unavailable status when inputs insufficient

References:
- Thorsson, S., et al. (2007). "Estimation of mean radiant temperature."
- ISO 7726:1998 "Ergonomics of the thermal environment"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .schemas import ThermalInput, ThermalQualityUncertainty
from ..core.enums import QualityFlag


@dataclass
class MRTResult:
    """MRT calculation result."""
    mrt_c: Optional[float]
    method: str
    quality: QualityFlag
    extrapolated: bool
    validity_note: Optional[str]
    missing_inputs: list


def estimate_mrt_from_solar(
    temp_c: float,
    solar_radiation_wm2: float,
    cloud_cover_pct: Optional[float] = None,
    quality: Optional[QualityFlag] = None
) -> MRTResult:
    """
    Estimate MRT from solar radiation and air temperature.
    This is a simplified method for when only shortwave data is available.

    MRT ≈ Ta + (α * S * (1 - cloud_factor) / (4 * ε * σ * Ta^3 + h_c))

    Where:
    - α = absorptivity (~0.7 for human)
    - S = solar radiation
    - ε = emissivity (~0.95)
    - σ = Stefan-Boltzmann constant
    - h_c = convective heat transfer coefficient
    """
    base_quality = quality or QualityFlag.VALID
    extrapolated = False
    validity_notes = []
    missing = []

    if solar_radiation_wm2 is None or solar_radiation_wm2 <= 0:
        return MRTResult(
            mrt_c=None,
            method="solar_estimation",
            quality=QualityFlag.MISSING,
            extrapolated=False,
            validity_note="No solar radiation data available for MRT estimation",
            missing_inputs=["solar_radiation_wm2"],
        )

    # Cloud cover factor
    if cloud_cover_pct is not None:
        cloud_factor = cloud_cover_pct / 100.0
    else:
        cloud_factor = 0.0  # Assume clear sky

    # Human body properties
    alpha = 0.7  # Absorptivity
    epsilon = 0.95  # Emissivity
    sigma = 5.67e-8  # Stefan-Boltzmann

    # Convective heat transfer coefficient (forced convection)
    # For a standing person, h_c ≈ 3-10 W/m²K depending on wind
    # Assume moderate wind for estimation
    h_c = 5.0

    # Net radiative temperature increment
    # Simplified: MRT = Ta + (α * S * (1 - cloud) / (4 * ε * σ * Ta^3 + h_c))
    ta_k = temp_c + 273.15
    denominator = 4 * epsilon * sigma * ta_k**3 + h_c

    if denominator > 0:
        delta_t = alpha * solar_radiation_wm2 * (1 - cloud_factor) / denominator
        mrt = temp_c + delta_t
    else:
        mrt = temp_c
        extrapolated = True
        validity_notes.append("Invalid denominator in MRT calculation")

    # MRT cannot be less than air temp in sunlight (roughly)
    if mrt < temp_c:
        mrt = temp_c

    return MRTResult(
        mrt_c=mrt,
        method="solar_estimation_v1",
        quality=QualityFlag.SUSPECT if extrapolated else base_quality,
        extrapolated=extrapolated,
        validity_note="; ".join(validity_notes) if validity_notes else None,
        missing_inputs=missing,
    )


def estimate_mrt_full_radiative(
    temp_c: float,
    solar_radiation_wm2: float,
    longwave_radiation_wm2: float,
    cloud_cover_pct: Optional[float] = None,
    quality: Optional[QualityFlag] = None
) -> MRTResult:
    """
    Full radiative MRT estimation including longwave radiation.

    MRT^4 = (α_s * S + α_l * L_down + ε * σ * T_surf^4 * F_surf) / (ε * σ * F_total)

    This is a placeholder for a more complete implementation.
    """
    base_quality = quality or QualityFlag.VALID
    extrapolated = False
    validity_notes = []

    if solar_radiation_wm2 is None:
        return MRTResult(
            mrt_c=None,
            method="full_radiative",
            quality=QualityFlag.MISSING,
            extrapolated=False,
            validity_note="Missing solar radiation",
            missing_inputs=["solar_radiation_wm2"],
        )

    if longwave_radiation_wm2 is None:
        # Fall back to solar-only
        return estimate_mrt_from_solar(temp_c, solar_radiation_wm2, cloud_cover_pct, quality)

    # Stefan-Boltzmann
    sigma = 5.67e-8
    epsilon = 0.95

    # Approximate MRT from radiative fluxes
    # Net radiative flux ≈ α_s * S + α_l * L - ε * σ * MRT^4
    # At equilibrium: MRT^4 = (α_s * S + α_l * L) / (ε * σ)

    alpha_s = 0.7  # Shortwave absorptivity
    alpha_l = 0.95  # Longwave absorptivity

    net_radiative = alpha_s * solar_radiation_wm2 + alpha_l * longwave_radiation_wm2
    mrt_k4 = net_radiative / (epsilon * sigma)

    if mrt_k4 > 0:
        mrt_k = mrt_k4 ** 0.25
        mrt = mrt_k - 273.15
    else:
        mrt = temp_c
        extrapolated = True
        validity_notes.append("Negative net radiative flux")

    return MRTResult(
        mrt_c=mrt,
        method="full_radiative_v1",
        quality=QualityFlag.SUSPECT if extrapolated else base_quality,
        extrapolated=extrapolated,
        validity_note="; ".join(validity_notes) if validity_notes else None,
        missing_inputs=[],
    )


def calculate_mrt(
    inp: ThermalInput,
    quality: Optional[QualityFlag] = None,
    method: str = "solar_only"
) -> MRTResult:
    """
    Calculate MRT from available inputs.

    Args:
        inp: ThermalInput with available meteorological data
        quality: Input quality flag
        method: "solar_only", "full_radiative", or "unavailable"

    Returns:
        MRTResult with mean radiant temperature in Celsius
    """
    if inp.air_temperature_c is None:
        return MRTResult(
            mrt_c=None,
            method=method,
            quality=QualityFlag.MISSING,
            extrapolated=False,
            validity_note="Missing air temperature",
            missing_inputs=["air_temperature_c"],
        )

    if method == "full_radiative":
        # Check if longwave available (not in standard inputs)
        # For now, fall back to solar
        return estimate_mrt_from_solar(
            inp.air_temperature_c,
            inp.solar_radiation_wm2,
            inp.cloud_cover_pct,
            quality,
        )
    elif method == "solar_only":
        return estimate_mrt_from_solar(
            inp.air_temperature_c,
            inp.solar_radiation_wm2,
            inp.cloud_cover_pct,
            quality,
        )
    else:
        return MRTResult(
            mrt_c=None,
            method="unavailable",
            quality=QualityFlag.MISSING,
            extrapolated=False,
            validity_note="MRT calculation disabled (method=unavailable)",
            missing_inputs=["configuration"],
        )