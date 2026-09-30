"""KESHAV STEP 7: Alert Escalation.

Policy-driven escalation logic.
Escalation considers risk change, persistence,
forecast horizon, uncertainty, and data quality.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from .schemas import Alert, AlertLevel


class AlertEscalator:
    """Handles alert escalation.

    Escalation rules:
    - WATCH -> WARNING if risk persists beyond persistence_hours
    - WARNING -> HIGH_RISK if risk escalates
    - HIGH_RISK stays HIGH_RISK until risk drops below de-escalation threshold
    """

    def __init__(self, escalation_minutes: int = 120):
        self.escalation_minutes = escalation_minutes

    def should_escalate(
        self,
        alert: Alert,
        current_risk: float,
        hours_since_creation: Optional[float] = None,
    ) -> bool:
        """Check if an alert should be escalated."""
        if alert.level == AlertLevel.WATCH:
            if hours_since_creation is not None:
                if hours_since_creation >= self.escalation_minutes / 60:
                    return True
            if current_risk > 0.50:
                return True
        elif alert.level == AlertLevel.WARNING:
            if current_risk > 0.75:
                return True
        return False

    def escalate(
        self,
        alert: Alert,
        current_risk: float,
        hours_since_creation: Optional[float] = None,
    ) -> AlertLevel:
        """Return the escalated level for an alert."""
        if alert.level == AlertLevel.WATCH:
            if hours_since_creation is not None:
                if hours_since_creation >= self.escalation_minutes / 60:
                    return AlertLevel.WARNING
            if current_risk > 0.50:
                return AlertLevel.WARNING
        elif alert.level == AlertLevel.WARNING:
            if current_risk > 0.75:
                return AlertLevel.HIGH_RISK
        return alert.level

    def should_de_escalate(
        self,
        alert: Alert,
        current_risk: float,
        hours_at_current_level: Optional[float] = None,
        de_escalation_threshold: float = 0.25,
    ) -> bool:
        """Check if an alert should be de-escalated."""
        if alert.level == AlertLevel.HIGH_RISK:
            if current_risk < de_escalation_threshold:
                if hours_at_current_level is not None:
                    if hours_at_current_level >= 2:
                        return True
                else:
                    return True
        elif alert.level == AlertLevel.WARNING:
            if current_risk < 0.25:
                return True
        elif alert.level == AlertLevel.WATCH:
            if current_risk < 0.25:
                return True
        return False

    def de_escalate(
        self,
        alert: Alert,
        current_risk: float,
        hours_at_current_level: Optional[float] = None,
        de_escalation_threshold: float = 0.25,
    ) -> AlertLevel:
        """Return the de-escalated level."""
        if alert.level == AlertLevel.HIGH_RISK:
            if current_risk < de_escalation_threshold:
                if hours_at_current_level is not None and hours_at_current_level >= 2:
                    return AlertLevel.WARNING
                elif hours_at_current_level is None:
                    return AlertLevel.WARNING
        elif alert.level == AlertLevel.WARNING:
            if current_risk < 0.25:
                return AlertLevel.NORMAL
        elif alert.level == AlertLevel.WATCH:
            if current_risk < 0.25:
                return AlertLevel.NORMAL
        return alert.level


def compute_hours_since(created_at: datetime) -> float:
    """Compute hours since a datetime."""
    delta = datetime.utcnow() - created_at
    return delta.total_seconds() / 3600
