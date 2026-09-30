"""Thermal Stress Classification — STEP 3.

Implements transparent classification categories based on multiple thermal indices.
Categories are configurable and do not claim to be official medical categories.

Categories:
- NORMAL: No significant thermal stress
- CAUTION: Elevated stress, precautions advised
- HIGH: High stress, limit exposure
- VERY_HIGH: Very high stress, avoid exposure
- EXTREME: Extreme stress, dangerous conditions

Each classification is based on specific index thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from ..core.enums import QualityFlag
from .schemas import ThermalIndices, ThermalClassification


@dataclass
class ClassificationThresholds:
    """Thresholds for thermal stress classification."""
    # Heat Index thresholds (°C)
    hi_caution: float = 27.0
    hi_high: float = 32.0
    hi_very_high: float = 41.0
    hi_extreme: float = 54.0

    # WBGT thresholds (°C)
    wbgt_caution: float = 25.0
    wbgt_high: float = 28.0
    wbgt_very_high: float = 30.0
    wbgt_extreme: float = 32.0

    # UTCI thresholds (°C)
    utci_no_stress: float = 9.0
    utci_moderate: float = 26.0
    utci_strong: float = 32.0
    utci_very_strong: float = 38.0
    utci_extreme: float = 46.0

    # Wet-bulb thresholds (°C)
    wb_caution: float = 25.0
    wb_high: float = 28.0
    wb_very_high: float = 31.0
    wb_extreme: float = 35.0


def classify_heat_index(hi_c: float, thresholds: ClassificationThresholds) -> str:
    """Classify based on Heat Index."""
    if hi_c >= thresholds.hi_extreme:
        return "EXTREME"
    elif hi_c >= thresholds.hi_very_high:
        return "VERY_HIGH"
    elif hi_c >= thresholds.hi_high:
        return "HIGH"
    elif hi_c >= thresholds.hi_caution:
        return "CAUTION"
    return "NORMAL"


def classify_wbgt(wbgt_c: float, thresholds: ClassificationThresholds) -> str:
    """Classify based on WBGT."""
    if wbgt_c >= thresholds.wbgt_extreme:
        return "EXTREME"
    elif wbgt_c >= thresholds.wbgt_very_high:
        return "VERY_HIGH"
    elif wbgt_c >= thresholds.wbgt_high:
        return "HIGH"
    elif wbgt_c >= thresholds.wbgt_caution:
        return "CAUTION"
    return "NORMAL"


def classify_utci(utci_c: float, thresholds: ClassificationThresholds) -> str:
    """Classify based on UTCI."""
    if utci_c >= thresholds.utci_extreme:
        return "EXTREME"
    elif utci_c >= thresholds.utci_very_strong:
        return "VERY_HIGH"
    elif utci_c >= thresholds.utci_strong:
        return "HIGH"
    elif utci_c >= thresholds.utci_moderate:
        return "CAUTION"
    elif utci_c >= thresholds.utci_no_stress:
        return "NORMAL"
    return "COLD"  # Below 9°C


def classify_wet_bulb(wb_c: float, thresholds: ClassificationThresholds) -> str:
    """Classify based on Wet-bulb temperature."""
    if wb_c >= thresholds.wb_extreme:
        return "EXTREME"
    elif wb_c >= thresholds.wb_very_high:
        return "VERY_HIGH"
    elif wb_c >= thresholds.wb_high:
        return "HIGH"
    elif wb_c >= thresholds.wb_caution:
        return "CAUTION"
    return "NORMAL"


def classify_occupational_heat(
    wbgt_c: Optional[float],
    utci_c: Optional[float],
    thresholds: ClassificationThresholds
) -> Optional[str]:
    """
    Occupational heat stress classification (ISO 7243 / ACGIH style).
    Based primarily on WBGT with UTCI as secondary.
    """
    categories = []

    if wbgt_c is not None:
        cat = classify_wbgt(wbgt_c, thresholds)
        categories.append(cat)

    if utci_c is not None:
        cat = classify_utci(utci_c, thresholds)
        categories.append(cat)

    if not categories:
        return None

    # Take the most severe category
    severity = {"NORMAL": 0, "CAUTION": 1, "HIGH": 2, "VERY_HIGH": 3, "EXTREME": 4, "COLD": -1}
    return max(categories, key=lambda c: severity.get(c, 0))


def classify_nighttime_recovery(
    recovery_status: Optional[str],
    consecutive_hot_nights: int,
    recovery_deficit: Optional[float]
) -> Optional[str]:
    """
    Nighttime recovery classification.

    Categories:
    - GOOD_RECOVERY: Full nighttime recovery
    - MODERATE_RECOVERY: Partial recovery
    - POOR_RECOVERY: Impaired recovery
    - NO_RECOVERY: Minimal/no recovery
    """
    if recovery_status == "full_recovery":
        return "GOOD_RECOVERY"
    elif recovery_status == "partial_recovery":
        return "MODERATE_RECOVERY"
    elif recovery_status == "impaired_recovery":
        return "POOR_RECOVERY"
    elif recovery_status == "minimal_recovery":
        return "NO_RECOVERY"
    return "UNKNOWN"


def classify_combined(
    indices,
    nighttime_result,
    thresholds: Optional[ClassificationThresholds] = None,
) -> ThermalClassification:
    """
    Multi-index synthesis classification.

    Returns classification across multiple dimensions:
    - thermal_stress_category: Overall thermal stress
    - occupational_heat_category: Occupational heat stress
    - nighttime_recovery_category: Nighttime recovery
    """
    thresholds = thresholds or ClassificationThresholds()

    # Thermal stress category: take most severe from available indices
    categories = []

    if indices.heat_index_c is not None:
        categories.append(classify_heat_index(indices.heat_index_c, thresholds))
    if indices.wbgt_c is not None:
        categories.append(classify_wbgt(indices.wbgt_c, thresholds))
    if indices.utci_c is not None:
        categories.append(classify_utci(indices.utci_c, thresholds))
    if indices.wet_bulb_c is not None:
        categories.append(classify_wet_bulb(indices.wet_bulb_c, thresholds))

    severity = {"NORMAL": 0, "CAUTION": 1, "HIGH": 2, "VERY_HIGH": 3, "EXTREME": 4, "COLD": -1}
    thermal_category = max(categories, key=lambda c: severity.get(c, 0)) if categories else "NORMAL"

    # Occupational heat category
    occ_category = classify_occupational_heat(
        indices.wbgt_c, indices.utci_c, thresholds
    )

    # Nighttime recovery category
    night_cat = None
    if nighttime_result is not None:
        night_cat = classify_nighttime_recovery(
            nighttime_result.recovery_status,
            nighttime_result.consecutive_hot_nights,
            nighttime_result.recovery_deficit,
        )

    return ThermalClassification(
        thermal_stress_category=thermal_category,
        occupational_heat_category=occ_category,
        nighttime_recovery_category=night_cat,
    )


def get_classification_explanation(
    classification: ThermalClassification,
    indices,
    nighttime_result,
) -> str:
    """Generate human-readable explanation of classification."""
    lines = []

    lines.append(f"Thermal stress category: {classification.thermal_stress_category}")

    if classification.occupational_heat_category:
        lines.append(f"Occupational heat category: {classification.occupational_heat_category}")

    if classification.nighttime_recovery_category:
        lines.append(f"Nighttime recovery: {classification.nighttime_recovery_category}")

    # Contributing factors
    factors = []
    if indices.heat_index_c and indices.heat_index_c > 32:
        factors.append(f"high heat index ({indices.heat_index_c:.1f}°C)")
    if indices.wbgt_c and indices.wbgt_c > 28:
        factors.append(f"high WBGT ({indices.wbgt_c:.1f}°C)")
    if indices.utci_c and indices.utci_c > 32:
        factors.append(f"high UTCI ({indices.utci_c:.1f}°C)")
    if indices.wet_bulb_c and indices.wet_bulb_c > 28:
        factors.append(f"high wet-bulb ({indices.wet_bulb_c:.1f}°C)")

    if nighttime_result and nighttime_result.hot_night:
        factors.append("hot night")

    if nighttime_result and nighttime_result.consecutive_hot_nights > 1:
        factors.append(f"{nighttime_result.consecutive_hot_nights} consecutive hot nights")

    if nighttime_result and nighttime_result.recovery_status in ("impaired_recovery", "minimal_recovery"):
        factors.append("limited nighttime recovery")

    if factors:
        lines.append("Contributing factors: " + ", ".join(factors))

    return "\n".join(lines)