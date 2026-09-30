"""SQLAlchemy ORM models for STEP 7: Last-Mile Alerts, Action Delivery & Governance.

Tables created in Step 7:
    alerts, alert_policies, alert_deliveries, alert_acknowledgements
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Index, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..utils.time import utcnow


class AlertDB(Base):
    """Database record for an operational or public heatwave alert."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_location_time", "location_id", "created_at"),
        Index("ix_alerts_level_status", "alert_level", "status"),
        Index("ix_alerts_pred_id", "prediction_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    location_id: Mapped[str] = mapped_column(String(64), index=True)
    alert_level: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="CREATED", index=True)

    title: Mapped[str] = mapped_column(String(256))
    summary: Mapped[str] = mapped_column(Text)

    reasons_data: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    recommendations_data: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    messages_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    target_recipient_groups: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    channels: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    prediction_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    policy_id: Mapped[str] = mapped_column(String(64), default="POLICY_STANDARD_2026")

    data_quality: Mapped[str] = mapped_column(String(32), default="GOOD")
    is_ood: Mapped[bool] = mapped_column(Boolean, default=False)
    uncertainty_score: Mapped[float] = mapped_column(Float, default=0.0)

    created_by: Mapped[str] = mapped_column(String(64), default="system")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    causal_status: Mapped[str] = mapped_column(String(64), default="MODEL_BASED_COUNTERFACTUAL")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AlertPolicyDB(Base):
    """Database record of a configured alert threshold and fatigue policy."""

    __tablename__ = "alert_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    policy_name: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(32), default="1.0")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    config_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlertDeliveryDB(Base):
    """Database audit record of a dispatched notification via a specific channel/provider."""

    __tablename__ = "alert_deliveries"
    __table_args__ = (
        Index("ix_delivery_alert_channel", "alert_id", "channel"),
        Index("ix_delivery_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delivery_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    alert_id: Mapped[str] = mapped_column(String(64), index=True)

    channel: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(64))
    recipient_group: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), index=True)

    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class AlertAcknowledgementDB(Base):
    """Database audit record of an operational user acknowledging an alert."""

    __tablename__ = "alert_acknowledgements"
    __table_args__ = (
        Index("ix_ack_alert_id", "alert_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ack_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    alert_id: Mapped[str] = mapped_column(String(64), index=True)

    acknowledged_by: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(64))
    action_taken: Mapped[str] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
