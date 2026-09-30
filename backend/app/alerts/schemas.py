"""Pydantic V2 schemas and enums for STEP 7: Last-Mile Alerts, Action Delivery & Governance."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from ..utils.time import utcnow


# ============================================================
# Enums
# ============================================================

class AlertLevel(str, Enum):
    """Tiered alert severity levels."""
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    WARNING = "WARNING"
    HIGH_RISK = "HIGH_RISK"


class AlertStatus(str, Enum):
    """Lifecycle states of an alert."""
    DRAFT = "DRAFT"
    EVALUATED = "EVALUATED"
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    MOCKED = "MOCKED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    SUPPRESSED = "SUPPRESSED"
    CANCELLED = "CANCELLED"


class AlertChannel(str, Enum):
    """Available delivery channels."""
    WEB = "WEB"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    IVR = "IVR"
    EMAIL = "EMAIL"
    MOCK = "MOCK"


class AlertRecipientGroup(str, Enum):
    """Target stakeholder and demographic recipient cohorts."""
    PUBLIC = "PUBLIC"
    VULNERABLE_RESIDENTS = "VULNERABLE_RESIDENTS"
    OUTDOOR_WORKERS = "OUTDOOR_WORKERS"
    HEALTH_WORKERS = "HEALTH_WORKERS"
    COMMUNITY_HEALTH_WORKERS = "COMMUNITY_HEALTH_WORKERS"
    MUNICIPAL_OPERATORS = "MUNICIPAL_OPERATORS"
    EMERGENCY_OPERATORS = "EMERGENCY_OPERATORS"
    HOSPITALS = "HOSPITALS"
    ADMINISTRATORS = "ADMINISTRATORS"


class AlertReasonCode(str, Enum):
    """Structured and auditable reason codes driving alert decisions."""
    HIGH_HEALTH_RISK = "HIGH_HEALTH_RISK"
    EXTREME_THERMAL_STRESS = "EXTREME_THERMAL_STRESS"
    PERSISTENT_HEAT = "PERSISTENT_HEAT"
    HOT_NIGHT = "HOT_NIGHT"
    RECOVERY_DEFICIT = "RECOVERY_DEFICIT"
    HIGH_EXPOSURE_MEMORY = "HIGH_EXPOSURE_MEMORY"
    HIGH_VULNERABILITY = "HIGH_VULNERABILITY"
    HEAT_POLLUTION_COMPOUND_RISK = "HEAT_POLLUTION_COMPOUND_RISK"
    LOW_DATA_CONFIDENCE = "LOW_DATA_CONFIDENCE"
    OOD_PREDICTION = "OOD_PREDICTION"
    LONG_FORECAST_LEAD = "LONG_FORECAST_LEAD"
    RAPID_RISK_ESCALATION = "RAPID_RISK_ESCALATION"
    ROUTINE_MONITORING = "ROUTINE_MONITORING"


class LanguageCode(str, Enum):
    """Supported message localization languages."""
    EN = "en"
    HI = "hi"


# ============================================================
# Domain Data Classes / Schemas
# ============================================================

class AlertReason(BaseModel):
    """A single structured signal or physical rationale contributing to an alert."""
    code: AlertReasonCode
    title: str
    description: str
    trigger_value: Optional[float] = None
    threshold_value: Optional[float] = None
    source_domain: str = "THERMAL_RISK"


class ActionRecommendation(BaseModel):
    """An operational or public health guidance recommendation."""
    action_id: str
    category: str  # e.g., "WORKPLACE_SAFETY", "HYDRATION", "CLINICAL_PREPAREDNESS", "COMMUNITY_SUPPORT"
    title: str
    description: str
    priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT"] = "MEDIUM"
    target_groups: List[AlertRecipientGroup] = Field(default_factory=list)
    step6_scenario_id: Optional[str] = None
    counterfactual_summary: Optional[str] = None


class AlertMessagePayload(BaseModel):
    """Structured multilingual alert message payload formatted for low-literacy clarity."""
    language: LanguageCode
    headline: str
    what_is_happening: str
    who_should_take_care: str
    what_to_do_now: str
    until_when: str
    full_text: str


class AlertPolicy(BaseModel):
    """Configurable rule set governing alert triggering, thresholding, and suppression."""
    policy_id: str
    policy_name: str
    version: str = "1.0"
    description: str = ""

    # Thresholds
    watch_probability_threshold: float = 0.40
    warning_probability_threshold: float = 0.60
    high_risk_probability_threshold: float = 0.80

    # Uncertainty & OOD handling
    max_tolerated_uncertainty: float = 0.35
    ood_policy: Literal["ALLOW_WITH_FLAG", "DOWNGRADE", "SUPPRESS"] = "ALLOW_WITH_FLAG"
    poor_data_policy: Literal["FLAG_AND_CAUTION", "DOWNGRADE", "SUPPRESS"] = "FLAG_AND_CAUTION"

    # Governance & Fatigue Control
    cooldown_minutes: int = 120
    quiet_hours_enabled: bool = False
    quiet_hours_start: int = 22  # 22:00
    quiet_hours_end: int = 6     # 06:00
    emergency_override_enabled: bool = True  # High risk overrides quiet hours

    # Defaults
    default_recipient_groups: List[AlertRecipientGroup] = Field(default_factory=lambda: [AlertRecipientGroup.PUBLIC])
    default_channels: List[AlertChannel] = Field(default_factory=lambda: [AlertChannel.WEB, AlertChannel.SMS])


# ============================================================
# Request / Response Schemas
# ============================================================

class AlertEvaluationRequest(BaseModel):
    """Request to evaluate risk signals and preview alert decision without dispatch."""
    location_id: str
    prediction_id: Optional[str] = None
    target_date: Optional[datetime] = None
    current_features: Optional[Dict[str, Any]] = None
    policy_id: Optional[str] = None
    recipient_group: Optional[AlertRecipientGroup] = None
    include_preview_messages: bool = True


class AlertEvaluationResponse(BaseModel):
    """Evaluation result detailing whether an alert triggers, reasons, and actions."""
    should_alert: bool
    alert_level: AlertLevel
    previous_level: Optional[AlertLevel] = None
    escalation_state: Literal["STABLE", "ESCALATED", "DE_ESCALATED", "INITIAL"] = "INITIAL"

    reasons: List[AlertReason] = Field(default_factory=list)
    recommendations: List[ActionRecommendation] = Field(default_factory=list)

    risk_probability: float
    risk_category: str
    uncertainty_score: float = 0.0
    data_quality: str = "GOOD"
    is_ood: bool = False

    is_suppressed: bool = False
    suppression_reason: Optional[str] = None

    policy_id: str
    target_recipient_groups: List[AlertRecipientGroup] = Field(default_factory=list)
    eligible_channels: List[AlertChannel] = Field(default_factory=list)

    preview_messages: Dict[str, AlertMessagePayload] = Field(default_factory=dict)
    evaluated_at: datetime = Field(default_factory=utcnow)
    causal_status: str = "MODEL_BASED_COUNTERFACTUAL"


class AlertCreateRequest(BaseModel):
    """Request to generate, register, and queue an approved operational alert."""
    location_id: str
    alert_level: AlertLevel
    title: str
    summary: str
    reasons: List[AlertReason] = Field(default_factory=list)
    recommendations: List[ActionRecommendation] = Field(default_factory=list)
    target_recipient_groups: List[AlertRecipientGroup] = Field(
        default_factory=lambda: [AlertRecipientGroup.PUBLIC, AlertRecipientGroup.VULNERABLE_RESIDENTS]
    )
    channels: List[AlertChannel] = Field(default_factory=lambda: [AlertChannel.WEB, AlertChannel.MOCK])
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    prediction_id: Optional[str] = None
    policy_id: Optional[str] = "POLICY_STANDARD_2026"
    notes: Optional[str] = None


class AlertDeliveryRecord(BaseModel):
    """Record of a dispatched notification via a specific channel and provider."""
    delivery_id: str
    alert_id: str
    channel: AlertChannel
    provider: str
    recipient_group: AlertRecipientGroup
    status: AlertStatus
    attempt_count: int = 1
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    is_mock: bool = True
    provider_message_id: Optional[str] = None


class AlertResponse(BaseModel):
    """Complete representation of an alert record with provenance and delivery tracking."""
    alert_id: str
    location_id: str
    alert_level: AlertLevel
    status: AlertStatus
    title: str
    summary: str
    reasons: List[AlertReason] = Field(default_factory=list)
    recommendations: List[ActionRecommendation] = Field(default_factory=list)
    messages: Dict[str, AlertMessagePayload] = Field(default_factory=dict)
    target_recipient_groups: List[AlertRecipientGroup] = Field(default_factory=list)
    channels: List[AlertChannel] = Field(default_factory=list)
    valid_from: datetime
    valid_to: datetime
    created_at: datetime
    created_by: str = "system"

    prediction_id: Optional[str] = None
    policy_id: str
    data_quality: str = "GOOD"
    is_ood: bool = False
    uncertainty_score: float = 0.0

    deliveries_count: int = 0
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None

    causal_status: str = "MODEL_BASED_COUNTERFACTUAL"
    disclaimer: str = (
        "Alert issued based on AI-estimated physiological heat stress and health risk. "
        "Intended for early public health readiness and operational decision support."
    )


class AlertAcknowledgementRequest(BaseModel):
    """Request by an operational actor to acknowledge and record action taken."""
    acknowledged_by: str
    role: str
    action_taken: str
    notes: Optional[str] = None


class AlertAcknowledgementResponse(BaseModel):
    """Acknowledgement response."""
    acknowledgement_id: str
    alert_id: str
    acknowledged_at: datetime
    acknowledged_by: str
    status: str = "ACKNOWLEDGED"


class AlertListResponse(BaseModel):
    """Paginated list of alerts."""
    total: int
    limit: int
    offset: int
    alerts: List[AlertResponse] = Field(default_factory=list)


class AlertGovernanceStatus(BaseModel):
    """Operational health and metric summary for alert subsystem."""
    active_alerts_count: int
    total_alerts_count: int
    suppressed_count: int
    deliveries_count: int
    failures_count: int
    active_providers: List[Dict[str, Any]] = Field(default_factory=list)
