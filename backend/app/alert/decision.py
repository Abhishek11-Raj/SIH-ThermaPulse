"""KESHAV STEP 7: Alert Decision Engine.

Converts risk predictions into actionable alerts
using configurable policy thresholds.

Scientific safety:
- Does NOT modify model probabilities
- Does NOT invent risk scores
- Preserves uncertainty and data-quality state
- Missing data is never treated as low risk
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .schemas import (
    Alert,
    AlertEvaluateRequest,
    AlertEvaluateResponse,
    AlertLevel,
    AlertPolicy,
    AlertReason,
)

logger = logging.getLogger("keshav.alert")


# Quality level ordering for comparison
_QUALITY_ORDER = {"BEST": 3, "GOOD": 2, "FAIR": 1, "POOR": 0, "UNKNOWN": -1}

# Reason priority for deduplication
_REASON_PRIORITY = {
    AlertReason.EXTREME_THERMAL_STRESS: 4,
    AlertReason.HIGH_VULNERABILITY: 4,
    AlertReason.COMPOUND_HEAT_POLLUTION: 4,
    AlertReason.FORECAST_ESCALATION: 3,
    AlertReason.PERSISTENT_HEAT: 3,
    AlertReason.HOT_NIGHT_RECOVERY_DEFICIT: 2,
    AlertReason.PROLONGED_EXPOSURE: 2,
    AlertReason.ELEVATED_HEALTH_RISK: 1,
}


def _quality_sufficient(
    data_quality: Optional[str],
    min_data_quality: str,
) -> bool:
    """Check if data quality meets minimum requirement."""
    if data_quality is None:
        return False
    q_order = _QUALITY_ORDER.get(data_quality, -1)
    min_order = _QUALITY_ORDER.get(min_data_quality, 0)
    return q_order >= min_order


def _determine_level(
    risk: float,
    uncertainty: Optional[float],
    data_quality: Optional[str],
    policy: AlertPolicy,
) -> Tuple[AlertLevel, List[AlertReason], bool]:
    """Determine alert level based on risk, uncertainty, and policy.

    Returns (level, reasons, suppressed).
    If suppressed is True, no alert should be generated.
    """
    reasons: List[AlertReason] = []

    # Suppress if uncertainty too high
    if uncertainty is not None and uncertainty > policy.max_uncertainty:
        logger.info(
            "Alert suppressed for risk=%.2f: uncertainty=%.2f exceeds max=%.2f",
            risk, uncertainty, policy.max_uncertainty,
        )
        return AlertLevel.NORMAL, reasons, True

    # Suppress if data quality insufficient
    if not _quality_sufficient(data_quality, policy.min_data_quality):
        logger.info(
            "Alert suppressed for risk=%.2f: data_quality=%s below min=%s",
            risk, data_quality, policy.min_data_quality,
        )
        return AlertLevel.NORMAL, reasons, True

    # Determine level based on risk thresholds
    if risk > policy.warning_max_risk:
        level = AlertLevel.HIGH_RISK
        reasons.append(AlertReason.EXTREME_THERMAL_STRESS)
    elif risk > policy.watch_max_risk:
        level = AlertLevel.WARNING
        reasons.append(AlertReason.ELEVATED_HEALTH_RISK)
    elif risk > policy.normal_max_risk:
        level = AlertLevel.WATCH
        reasons.append(AlertReason.ELEVATED_HEALTH_RISK)
    else:
        level = AlertLevel.NORMAL

    return level, reasons, False


def _generate_reason_details(
    request: AlertEvaluateRequest,
    level: AlertLevel,
) -> Dict[str, Any]:
    """Generate detailed reason information."""
    details: Dict[str, Any] = {}

    if request.ood_status:
        details["ood_warning"] = (
            "Prediction is outside training distribution; "
            "confidence is reduced."
        )

    if request.uncertainty is not None:
        details["uncertainty"] = request.uncertainty
        details["confidence"] = round(1.0 - request.uncertainty, 2)

    if request.data_completeness is not None:
        details["data_completeness"] = request.data_completeness

    if level == AlertLevel.HIGH_RISK:
        details["risk_gap"] = round(request.risk_probability - 0.75, 2)
    elif level == AlertLevel.WARNING:
        details["risk_gap"] = round(request.risk_probability - 0.50, 2)
    elif level == AlertLevel.WATCH:
        details["risk_gap"] = round(request.risk_probability - 0.25, 2)

    return details


def _generate_fingerprint(
    location_id: str,
    level: AlertLevel,
    policy_version: str,
    valid_from: Optional[datetime],
    valid_to: Optional[datetime],
    reasons: List[AlertReason],
) -> str:
    """Generate a fingerprint for alert deduplication."""
    material = "|".join([
        location_id,
        level.value,
        policy_version,
        valid_from.isoformat() if valid_from else "",
        valid_to.isoformat() if valid_to else "",
        ",".join(sorted(r.value for r in reasons)),
    ])
    return hashlib.sha256(material.encode()).hexdigest()[:16]


def evaluate_alert(
    request: AlertEvaluateRequest,
    policy: AlertPolicy,
    previous_alert: Optional[Alert] = None,
) -> AlertEvaluateResponse:
    """Evaluate whether an alert should be triggered for a prediction.

    Decision logic:
    1. Check uncertainty - suppress if too high
    2. Check data quality - suppress if insufficient
    3. Determine alert level from risk thresholds
    4. Check deduplication against previous alert
    5. Check escalation / de-escalation

    Returns AlertEvaluateResponse with trigger decision.
    """
    reasons: List[AlertReason] = []
    escalated = False
    de_escalated = False
    deduplicated = False

    # Determine level
    level, reasons, suppressed = _determine_level(
        request.risk_probability,
        request.uncertainty,
        request.data_quality,
        policy,
    )

    if suppressed:
        return AlertEvaluateResponse(
            triggered=False,
            level=AlertLevel.NORMAL,
            policy_version=policy.policy_version,
            message="Alert suppressed: uncertainty or data quality below threshold",
        )

    # If risk is NORMAL but there was a previous alert, check de-escalation
    if level == AlertLevel.NORMAL and previous_alert is not None:
        if previous_alert.level != AlertLevel.NORMAL:
            de_escalated = True
            return AlertEvaluateResponse(
                triggered=False,
                level=AlertLevel.NORMAL,
                policy_version=policy.policy_version,
                de_escalated=True,
                message="Alert de-escalated: risk below threshold",
            )
        return AlertEvaluateResponse(
            triggered=False,
            level=AlertLevel.NORMAL,
            policy_version=policy.policy_version,
            message="No alert: risk within normal range",
        )

    # Check escalation against previous alert
    if previous_alert is not None and previous_alert.level != AlertLevel.NORMAL:
        level_order = {
            AlertLevel.NORMAL: 0,
            AlertLevel.WATCH: 1,
            AlertLevel.WARNING: 2,
            AlertLevel.HIGH_RISK: 3,
        }
        prev_order = level_order.get(previous_alert.level, 0)
        curr_order = level_order.get(level, 0)
        if curr_order > prev_order:
            escalated = True
        elif curr_order == prev_order:
            # Same level - check deduplication
            fp_new = _generate_fingerprint(
                request.location_id,
                level,
                policy.policy_version,
                request.forecast_valid_from,
                request.forecast_valid_to,
                reasons,
            )
            fp_old = _generate_fingerprint(
                previous_alert.location_id,
                previous_alert.level,
                previous_alert.policy_version,
                previous_alert.forecast_valid_from,
                previous_alert.forecast_valid_to,
                previous_alert.reasons,
            )
            if fp_new == fp_old:
                deduplicated = True
                return AlertEvaluateResponse(
                    triggered=False,
                    level=level,
                    reasons=reasons,
                    deduplicated=True,
                    policy_version=policy.policy_version,
                    message="Duplicate alert suppressed",
                )

    # Build response
    reason_details = _generate_reason_details(request, level)
    actions = recommend_actions(level, reasons, request)

    response = AlertEvaluateResponse(
        triggered=True,
        level=level,
        reasons=reasons,
        actions=actions,
        escalated=escalated,
        de_escalated=de_escalated,
        policy_version=policy.policy_version,
        message=f"Alert triggered at {level.value} level",
    )

    logger.info(
        "Alert evaluated: location=%s level=%s triggered=%s reasons=%s",
        request.location_id, level.value, response.triggered,
        [r.value for r in reasons],
    )

    return response


def recommend_actions(
    level: AlertLevel,
    reasons: List[AlertReason],
    request: AlertEvaluateRequest,
) -> List[str]:
    """Generate action recommendations based on alert level and reasons.

    Actions are linked to the alert reason / intervention context.
    """
    actions: List[str] = []

    if level == AlertLevel.HIGH_RISK:
        actions.extend([
            "reduce prolonged outdoor exposure",
            "increase work/rest breaks",
            "move strenuous activity to cooler hours",
            "ensure drinking-water access",
            "use shaded/cool environments",
            "check vulnerable people",
            "follow local heat-health guidance",
            "activate community response",
            "prepare cooling facilities",
        ])
    elif level == AlertLevel.WARNING:
        actions.extend([
            "limit outdoor exposure during peak heat",
            "increase work/rest breaks",
            "ensure drinking-water access",
            "check vulnerable people",
            "follow local heat-health guidance",
        ])
    elif level == AlertLevel.WATCH:
        actions.extend([
            "monitor vulnerable populations",
            "stay hydrated",
            "limit midday outdoor activity",
        ])
    else:
        actions.append("no action required")

    # Reason-specific actions
    if AlertReason.HOT_NIGHT_RECOVERY_DEFICIT in reasons:
        actions.append("ensure cool sleeping environment")
    if AlertReason.PROLONGED_EXPOSURE in reasons:
        actions.append("shift outdoor work to cooler hours")
    if AlertReason.HIGH_VULNERABILITY in reasons:
        actions.append("prioritise vulnerable population outreach")
    if AlertReason.COMPOUND_HEAT_POLLUTION in reasons:
        actions.append("monitor air quality alongside heat")

    # Deduplicate while preserving order
    seen: set = set()
    unique_actions: List[str] = []
    for a in actions:
        if a not in seen:
            seen.add(a)
            unique_actions.append(a)

    return unique_actions
