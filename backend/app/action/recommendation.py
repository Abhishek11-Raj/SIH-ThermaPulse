"""KESHAV STEP 7: Action Recommendation Engine.

Generates actionable recommendations based on alert level,
reasons, and intervention context.

Actions are linked to alert reasons and intervention types.
All recommendations are qualified - no causal claims.
"""
from __future__ import annotations

from typing import List, Optional

from .schemas import AlertLevel, AlertReason


# Action mappings per reason
_REASON_ACTIONS: dict = {
    AlertReason.ELEVATED_HEALTH_RISK: [
        "monitor vulnerable populations",
        "stay hydrated",
        "limit midday outdoor activity",
    ],
    AlertReason.EXTREME_THERMAL_STRESS: [
        "reduce prolonged outdoor exposure",
        "increase work/rest breaks",
        "move strenuous activity to cooler hours",
        "ensure drinking-water access",
        "use shaded/cool environments",
        "check vulnerable people",
        "follow local heat-health guidance",
        "activate community response",
        "prepare cooling facilities",
    ],
    AlertReason.PROLONGED_EXPOSURE: [
        "shift outdoor work to cooler hours",
        "reduce exposure duration",
        "increase rest breaks",
    ],
    AlertReason.HOT_NIGHT_RECOVERY_DEFICIT: [
        "ensure cool sleeping environment",
        "use fans or cooling",
        "check on elderly neighbours",
    ],
    AlertReason.PERSISTENT_HEAT: [
        "continue monitoring conditions",
        "maintain hydration",
        "avoid prolonged outdoor exposure",
    ],
    AlertReason.HIGH_VULNERABILITY: [
        "prioritise vulnerable population outreach",
        "check on at-risk individuals",
        "ensure access to cooling centres",
    ],
    AlertReason.COMPOUND_HEAT_POLLUTION: [
        "monitor air quality alongside heat",
        "limit outdoor activity if AQI also elevated",
        "use indoor air filtration if available",
    ],
    AlertReason.FORECAST_ESCALATION: [
        "prepare for worsening conditions",
        "pre-position cooling resources",
        "inform community of forecast",
    ],
}

# Action mappings per alert level (fallback)
_LEVEL_ACTIONS: dict = {
    AlertLevel.HIGH_RISK: [
        "reduce prolonged outdoor exposure",
        "increase work/rest breaks",
        "move strenuous activity to cooler hours",
        "ensure drinking-water access",
        "use shaded/cool environments",
        "check vulnerable people",
        "follow local heat-health guidance",
        "activate community response",
        "prepare cooling facilities",
    ],
    AlertLevel.WARNING: [
        "limit outdoor exposure during peak heat",
        "increase work/rest breaks",
        "ensure drinking-water access",
        "check vulnerable people",
        "follow local heat-health guidance",
    ],
    AlertLevel.WATCH: [
        "monitor vulnerable populations",
        "stay hydrated",
        "limit midday outdoor activity",
    ],
    AlertLevel.NORMAL: [
        "no action required",
    ],
}


def recommend_actions(
    level: AlertLevel,
    reasons: List[AlertReason],
    intervention_context: Optional[dict] = None,
) -> List[str]:
    """Generate action recommendations based on alert level and reasons.

    Args:
        level: Alert level
        reasons: List of alert reasons
        intervention_context: Optional context from Step 6
            intervention engine (what-if simulation results).

    Returns:
        List of unique, ordered action recommendations.
    """
    actions: List[str] = []

    # Add reason-specific actions
    for reason in reasons:
        reason_actions = _REASON_ACTIONS.get(reason, [])
        actions.extend(reason_actions)

    # Add level fallback actions if no reason-specific actions
    if not actions:
        actions.extend(_LEVEL_ACTIONS.get(level, []))

    # Add intervention context actions if available
    if intervention_context:
        _add_intervention_actions(actions, intervention_context)

    # Deduplicate while preserving order
    seen: set = set()
    unique_actions: List[str] = []
    for a in actions:
        if a not in seen:
            seen.add(a)
            unique_actions.append(a)

    return unique_actions


def _add_intervention_actions(
    actions: List[str],
    context: dict,
) -> None:
    """Add intervention-specific actions from Step 6 context."""
    interventions = context.get("interventions", [])
    for interv in interventions:
        interv_type = interv.get("intervention_type", "")
        if interv_type == "outdoor_exposure_reduction":
            if "reduce prolonged outdoor exposure" not in actions:
                actions.append("reduce prolonged outdoor exposure")
        elif interv_type == "work_rest_schedule":
            if "increase work/rest breaks" not in actions:
                actions.append("increase work/rest breaks")
        elif interv_type == "shade_increase":
            if "use shaded/cool environments" not in actions:
                actions.append("use shaded/cool environments")
        elif interv_type == "water_access_increase":
            if "ensure drinking-water access" not in actions:
                actions.append("ensure drinking-water access")
        elif interv_type == "cooling_access_increase":
            if "use shaded/cool environments" not in actions:
                actions.append("use shaded/cool environments")
        elif interv_type == "power_restoration":
            if "ensure access to cooling facilities" not in actions:
                actions.append("ensure access to cooling facilities")
        elif interv_type == "exposure_time_shift":
            if "move strenuous activity to cooler hours" not in actions:
                actions.append("move strenuous activity to cooler hours")