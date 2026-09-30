"""KESHAV STEP 7: Alert Deduplication.

Prevents repeated identical alerts.
Uses fingerprinting based on location, level, policy version,
valid window, and material risk state.
"""
from __future__ import annotations

from typing import Optional

from .schemas import Alert, AlertEvaluateResponse, AlertLevel, AlertReason
from .decision import _generate_fingerprint


class AlertDeduplicator:
    """Deduplicates alerts based on fingerprint.

    If a new prediction does not materially change the alert,
    the duplicate is suppressed.
    If risk materially escalates, an escalation alert is created.
    If risk materially decreases, a de-escalation alert is created
    where policy allows.
    """

    def __init__(self):
        self._fingerprints: dict[str, str] = {}

    def check(
        self,
        alert: Alert,
    ) -> tuple[bool, Optional[str]]:
        """Check if an alert is a duplicate.

        Returns (is_duplicate, fingerprint).
        """
        fp = _generate_fingerprint(
            alert.location_id,
            alert.level,
            alert.policy_version,
            alert.forecast_valid_from,
            alert.forecast_valid_to,
            alert.reasons,
        )
        key = f"{alert.location_id}:{alert.policy_id}"
        existing_fp = self._fingerprints.get(key)
        if existing_fp == fp:
            return True, fp
        self._fingerprints[key] = fp
        return False, fp

    def check_evaluate(
        self,
        response: AlertEvaluateResponse,
        location_id: str,
        policy_id: str,
    ) -> tuple[bool, Optional[str]]:
        """Check an evaluation response for deduplication.

        Returns (is_duplicate, fingerprint).
        """
        if not response.triggered:
            return False, None
        fp = _generate_fingerprint(
            location_id,
            response.level,
            response.policy_version,
            None,
            None,
            response.reasons,
        )
        key = f"{location_id}:{policy_id}"
        existing_fp = self._fingerprints.get(key)
        if existing_fp == fp:
            return True, fp
        self._fingerprints[key] = fp
        return False, fp

    def clear(self) -> None:
        """Clear all fingerprints."""
        self._fingerprints.clear()


def classify_escalation(
    current: AlertLevel,
    previous: AlertLevel,
) -> str:
    """Classify escalation relationship.

    Returns 'escalation', 'de_escalation', 'same', or 'none'.
    """
    order = {
        AlertLevel.NORMAL: 0,
        AlertLevel.WATCH: 1,
        AlertLevel.WARNING: 2,
        AlertLevel.HIGH_RISK: 3,
    }
    curr_ord = order.get(current, 0)
    prev_ord = order.get(previous, 0)
    if curr_ord > prev_ord:
        return "escalation"
    elif curr_ord < prev_ord:
        return "de_escalation"
    elif curr_ord == prev_ord and curr_ord > 0:
        return "same"
    return "none"
