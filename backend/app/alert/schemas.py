"""KESHAV STEP 7: Alert domain models.

Alert schemas for last-mile alert generation, decision, and delivery.
All alerts preserve provenance and are traceable to predictions.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from typing_extensions import Literal


# ============================================================
# Enums
# ============================================================

class AlertLevel(str, Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    WARNING = "WARNING"
    HIGH_RISK = "HIGH_RISK"


class AlertStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    ESCALATED = "ESCALATED"
    DE_ESCALATED = "DE_ESCALATED"


class AlertChannel(str, Enum):
    WEB = "WEB"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    IVR = "IVR"
    EMAIL = "EMAIL"
    MOCK = "MOCK"


class DeliveryResult(str, Enum):
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    UNSUPPORTED = "UNSUPPORTED"
    MOCKED = "MOCKED"


class AcknowledgementStatus(str, Enum):
    UNREAD = "UNREAD"
    RECEIVED = "RECEIVED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    EXPIRED = "EXPIRED"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class RecipientGroup(str, Enum):
    PUBLIC = "public"
    VULNERABLE_POPULATION = "vulnerable_population"
    OUTDOOR_WORKERS = "outdoor_workers"
    COMMUNITY_HEALTH_WORKERS = "community_health_workers"
    MUNICIPAL_AUTHORITY = "municipal_authority"
    EMERGENCY_RESPONSE = "emergency_response"
    HEALTHCARE_FACILITY = "healthcare_facility"


class AlertReason(str, Enum):
    ELEVATED_HEALTH_RISK = "elevated_health_risk"
    EXTREME_THERMAL_STRESS = "extreme_thermal_stress"
    PROLONGED_EXPOSURE = "prolonged_exposure"
    HOT_NIGHT_RECOVERY_DEFICIT = "hot_night_recovery_deficit"
    PERSISTENT_HEAT = "persistent_heat"
    HIGH_VULNERABILITY = "high_vulnerability"
    COMPOUND_HEAT_POLLUTION = "compound_heat_pollution"
    FORECAST_ESCALATION = "forecast_escalation"


# ============================================================
# Policy
# ============================================================

class AlertPolicy(BaseModel):
    """Configurable alert policy.

    Thresholds are policy-driven, not hardcoded.
    """

    policy_id: str
    policy_version: str = "1.0"
    name: str
    description: str = ""
    location_id: str
    enabled: bool = True

    # Risk thresholds for each alert level
    normal_max_risk: float = 0.25
    watch_max_risk: float = 0.50
    warning_max_risk: float = 0.75

    # Uncertainty requirement: alerts suppressed if uncertainty too high
    max_uncertainty: float = 0.30

    # Data quality requirement: minimum acceptable quality
    min_data_quality: Literal["BEST", "GOOD", "FAIR", "POOR"] = "FAIR"

    # Persistence: alerts persist this many hours before de-escalation
    persistence_hours: int = 6

    # Forecast lead time (hours) for early alerts
    forecast_lead_time_hours: int = 24

    # Escalation: minutes before auto-escalation if unacknowledged
    escalation_minutes: int = 120

    # De-escalation: risk below this for persistence_hours to de-escalate
    de_escalation_risk_threshold: float = 0.25

    # Recipient groups for this policy
    recipient_groups: List[RecipientGroup] = Field(
        default_factory=list
    )

    # Channels for this policy
    channels: List[AlertChannel] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ============================================================
# Alert
# ============================================================

class Alert(BaseModel):
    """A generated last-mile alert.

    Every alert is traceable to a prediction via provenance.
    """

    alert_id: str
    policy_id: str
    policy_version: str
    level: AlertLevel
    status: AlertStatus = AlertStatus.ACTIVE
    location_id: str
    location_name: Optional[str] = None

    # Provenance
    prediction_id: str
    model_version: str
    feature_version: str = "1.0"
    forecast_valid_from: Optional[datetime] = None
    forecast_valid_to: Optional[datetime] = None
    prediction_timestamp: datetime

    # Risk context
    predicted_risk: float
    risk_category: str
    uncertainty: Optional[float] = None
    ood_status: bool = False
    data_quality: str = "UNKNOWN"
    data_quality_flag: Optional[str] = None

    # Reasons
    reasons: List[AlertReason] = Field(default_factory=list)
    reason_details: Dict[str, Any] = Field(default_factory=dict)

    # Actions
    recommended_actions: List[str] = Field(default_factory=list)
    recipient_groups: List[RecipientGroup] = Field(default_factory=list)
    channels: List[AlertChannel] = Field(default_factory=list)

    # State
    previous_alert_id: Optional[str] = None
    escalation_level: int = 0
    acknowledgement_status: AcknowledgementStatus = AcknowledgementStatus.UNREAD
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Counters
    delivery_attempts: int = 0
    delivery_failures: int = 0

    @field_validator("predicted_risk")
    @classmethod
    def risk_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("predicted_risk must be between 0 and 1")
        return v

    @field_validator("uncertainty")
    @classmethod
    def uncertainty_in_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not 0.0 <= v <= 1.0:
            raise ValueError("uncertainty must be between 0 and 1")
        return v


# ============================================================
# Alert Message
# ============================================================

class AlertMessage(BaseModel):
    """Structured alert message for a channel."""

    alert_id: str
    channel: AlertChannel
    language: str = "en"
    subject: str
    body: str
    actions: List[str] = Field(default_factory=list)
    disclaimer: str = (
        "This is a model-based alert simulation. "
        "It does not predict actual health outcomes."
    )
    source: str = "KESHAV"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# Alert Delivery
# ============================================================

class AlertDelivery(BaseModel):
    """Record of an alert delivery attempt."""

    delivery_id: str
    alert_id: str
    channel: AlertChannel
    recipient_group: RecipientGroup
    result: DeliveryResult
    message: str = ""
    provider_name: Optional[str] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


# ============================================================
# Alert Acknowledgement
# ============================================================

class AlertAcknowledgement(BaseModel):
    """Alert acknowledgement record."""

    acknowledgement_id: str
    alert_id: str
    recipient_id: str
    status: AcknowledgementStatus
    acknowledged_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# Evaluate Request / Response
# ============================================================

class AlertEvaluateRequest(BaseModel):
    """Request to evaluate whether an alert should be triggered."""

    prediction_id: str
    location_id: str
    policy_id: Optional[str] = None
    risk_probability: float
    risk_category: str
    uncertainty: Optional[float] = None
    ood_status: bool = False
    data_quality: Optional[str] = None
    data_completeness: Optional[float] = None
    forecast_valid_from: Optional[datetime] = None
    forecast_valid_to: Optional[datetime] = None
    prediction_timestamp: Optional[datetime] = None
    model_version: Optional[str] = None
    feature_version: Optional[str] = None


class AlertEvaluateResponse(BaseModel):
    """Response from alert evaluation."""

    alert_id: Optional[str] = None
    triggered: bool = False
    level: Optional[AlertLevel] = None
    reasons: List[AlertReason] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    deduplicated: bool = False
    escalated: bool = False
    de_escalated: bool = False
    policy_version: str = "1.0"
    message: str = ""


# ============================================================
# Template
# ============================================================

class AlertTemplate(BaseModel):
    """Multilingual alert message template."""

    template_id: str
    alert_level: AlertLevel
    language: str
    subject: str
    body: str


# ============================================================
# Status
# ============================================================

class AlertStatusSummary(BaseModel):
    """Summary of alert status for a location."""

    location_id: str
    active_alerts: int = 0
    current_level: AlertLevel = AlertLevel.NORMAL
    latest_alert_id: Optional[str] = None
    updated_at: Optional[datetime] = None
