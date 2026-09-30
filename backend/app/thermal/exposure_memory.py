"""Heat Exposure Memory — STEP 3.

Implements a stateful exposure memory model based on the conceptual form:

E_t = λ * E_(t-1) + S_t - R_t

Where:
- E_t = current exposure memory
- E_(t-1) = previous exposure memory
- λ = persistence/decay factor (0 < λ <= 1)
- S_t = current thermal stress contribution
- R_t = recovery contribution

This is a MODEL FEATURE / exposure-state metric, not a direct measure of
biological fatigue. The decay factor λ is configurable and should be
empirically calibrated against health outcomes in later steps.

References:
- Conceptual framework for cumulative heat exposure
- Various cumulative heat stress indices in literature
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from .schemas import ThermalInput, ThermalClassification, ThermalIndices, ThermalQualityUncertainty
from ..core.enums import QualityFlag


@dataclass
class ExposureMemoryResult:
    """Exposure memory calculation result."""
    previous_exposure_memory: Optional[float]
    current_stress_contribution: float
    recovery_contribution: float
    decay_factor: float
    exposure_memory: float
    window_hours: int
    method: str
    quality: QualityFlag
    extrapolated: bool
    validity_note: Optional[str]


def calculate_daily_stress(
    indices: ThermalIndices,
    nighttime_hot: bool = False,
    consecutive_hot_nights: int = 0,
    config: Optional[dict] = None
) -> float:
    """
    Calculate daily thermal stress contribution from indices.

    Uses a weighted combination of thermal indices, with higher weights
    for more physiologically relevant indices.

    Args:
        indices: Computed thermal indices
        nighttime_hot: Whether the preceding night was hot
        consecutive_hot_nights: Number of consecutive hot nights
        config: Configuration with weights

    Returns:
        Daily stress value (dimensionless, higher = more stress)
    """
    config = config or {}

    # Default weights (can be calibrated)
    weights = config.get("stress_weights") or {
        "heat_index": 0.3,
        "wbgt": 0.3,
        "utci": 0.2,
        "wet_bulb": 0.2,
    }

    stress = 0.0
    total_weight = 0.0

    # Heat Index contribution
    if indices.heat_index_c is not None:
        # Normalize: HI of 40°C = high stress
        hi_normalized = min(indices.heat_index_c / 40.0, 1.0)
        stress += weights["heat_index"] * hi_normalized
        total_weight += weights["heat_index"]

    # WBGT contribution
    if indices.wbgt_c is not None:
        # Normalize: WBGT of 32°C = high stress
        wbgt_normalized = min(indices.wbgt_c / 32.0, 1.0)
        stress += weights["wbgt"] * wbgt_normalized
        total_weight += weights["wbgt"]

    # UTCI contribution
    if indices.utci_c is not None:
        # Normalize: UTCI of 38°C = high stress
        utci_normalized = min(indices.utci_c / 38.0, 1.0)
        stress += weights["utci"] * utci_normalized
        total_weight += weights["utci"]

    # Wet-bulb contribution
    if indices.wet_bulb_c is not None:
        # Normalize: WB of 31°C = high stress
        wb_normalized = min(indices.wet_bulb_c / 31.0, 1.0)
        stress += weights["wet_bulb"] * wb_normalized
        total_weight += weights["wet_bulb"]

    # Normalize by total weight
    if total_weight > 0:
        stress = stress / total_weight
    else:
        stress = 0.0

    # Nighttime amplification
    if nighttime_hot:
        stress *= 1.2
    if consecutive_hot_nights > 0:
        stress *= (1.0 + 0.1 * min(consecutive_hot_nights, 5))

    return min(stress, 1.0)  # Cap at 1.0


def calculate_recovery_contribution(
    nighttime_result,
    config: Optional[dict] = None
) -> float:
    """
    Calculate recovery contribution from nighttime analysis.

    Recovery is higher when nighttime temperatures are lower
    and there are fewer consecutive hot nights.

    Args:
        nighttime_result: NighttimeResult from nighttime analysis
        config: Configuration

    Returns:
        Recovery contribution (0 to 1)
    """
    if nighttime_result is None:
        return 0.5  # Default moderate recovery

    config = config or {}
    max_recovery = config.get("max_recovery", 1.0)

    if nighttime_result.recovery_status == "full_recovery":
        return max_recovery
    elif nighttime_result.recovery_status == "partial_recovery":
        return max_recovery * 0.6
    elif nighttime_result.recovery_status == "impaired_recovery":
        return max_recovery * 0.3
    elif nighttime_result.recovery_status == "minimal_recovery":
        return max_recovery * 0.1
    else:
        return max_recovery * 0.5


def calculate_exposure_memory(
    previous_memory: Optional[float],
    current_stress: float,
    recovery: float,
    decay_factor: float = 0.95,
    quality: Optional[QualityFlag] = None,
) -> ExposureMemoryResult:
    """
    Calculate exposure memory using the state equation:

    E_t = λ * E_(t-1) + S_t - R_t

    Args:
        previous_memory: Previous exposure memory value (E_(t-1))
        current_stress: Current thermal stress contribution S_t
        recovery: Recovery contribution R_t
        decay_factor: Persistence factor λ (0 < λ <= 1)
        quality: Input quality flag

    Returns:
        ExposureMemoryResult with new exposure memory value
    """
    base_quality = quality or QualityFlag.VALID
    extrapolated = False
    validity_note = None

    if previous_memory is None:
        # No previous state - start from current stress minus recovery
        previous_memory = 0.0
        extrapolated = True
        validity_note = "No previous exposure memory; initialized to zero"

    # Validate decay factor
    if not (0 < decay_factor <= 1):
        decay_factor = 0.95
        extrapolated = True
        validity_note = f"Invalid decay factor; using default 0.95"

    # State equation: E_t = λ * E_(t-1) + S_t - R_t
    new_memory = decay_factor * previous_memory + current_stress - recovery

    # Memory cannot be negative
    new_memory = max(0.0, new_memory)

    # Cap at reasonable maximum
    new_memory = min(new_memory, 10.0)

    return ExposureMemoryResult(
        previous_exposure_memory=previous_memory,
        current_stress_contribution=current_stress,
        recovery_contribution=recovery,
        decay_factor=decay_factor,
        exposure_memory=new_memory,
        window_hours=168,  # Default 7-day window
        method="exposure_memory_v1",
        quality=base_quality,
        extrapolated=extrapolated,
        validity_note=validity_note,
    )


def calculate_cumulative_exposure(
    daily_stress_history: List[float],
    windows_hours: List[int] = None
) -> dict:
    """
    Calculate cumulative exposure over specified windows.

    Args:
        daily_stress_history: List of daily stress values (most recent last)
        windows_hours: List of window sizes in hours (default: 24, 72, 168)

    Returns:
        Dict with cumulative exposure for each window
    """
    if windows_hours is None:
        windows_hours = [24, 72, 168]  # 1 day, 3 days, 7 days

    result = {}

    for window in windows_hours:
        days = max(1, window // 24)
        # Use most recent 'days' values
        recent = daily_stress_history[-days:] if len(daily_stress_history) >= days else daily_stress_history
        if recent:
            result[f"cumulative_exposure_{window}h"] = sum(recent)
        else:
            result[f"cumulative_exposure_{window}h"] = None

    return result


def run_exposure_memory_step(
    indices: ThermalIndices,
    nighttime_result,
    previous_memory: Optional[float],
    config: Optional[dict] = None,
    quality: Optional[QualityFlag] = None,
) -> ExposureMemoryResult:
    """
    Run one step of the exposure memory model.

    Args:
        indices: Current thermal indices
        nighttime_result: Nighttime analysis result
        previous_memory: Previous exposure memory state
        config: Configuration (decay_factor, weights, etc.)
        quality: Input quality flag

    Returns:
        ExposureMemoryResult with updated memory
    """
    config = config or {}
    decay_factor = config.get("memory_decay_factor", 0.95)

    # Calculate current stress
    current_stress = calculate_daily_stress(indices, config=config)

    # Calculate recovery
    recovery = calculate_recovery_contribution(nighttime_result, config)

    # Update memory
    return calculate_exposure_memory(
        previous_memory,
        current_stress,
        recovery,
        decay_factor,
        quality,
    )