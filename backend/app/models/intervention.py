"""SQLAlchemy ORM models for STEP 6: Intervention and Counterfactual Scenarios.

Tables created in Step 6:
    intervention_scenarios
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Float, Integer, String, Index, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..utils.time import utcnow


class InterventionScenarioDB(Base):
    """Database record of a model-based counterfactual simulation scenario."""

    __tablename__ = "intervention_scenarios"
    __table_args__ = (
        Index("ix_int_scenario_location", "location_id"),
        Index("ix_int_scenario_created", "created_at"),
        Index("ix_int_scenario_baseline_pred", "baseline_prediction_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    location_id: Mapped[str] = mapped_column(String(64), index=True)
    scenario_name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    baseline_prediction_id: Mapped[str] = mapped_column(String(64), index=True)
    model_version: Mapped[str] = mapped_column(String(32), default="1.0")
    feature_version: Mapped[str] = mapped_column(String(32), default="1.0")
    status: Mapped[str] = mapped_column(String(16), default="COMPLETED")

    baseline_risk_probability: Mapped[float] = mapped_column(Float, nullable=False)
    counterfactual_risk_probability: Mapped[float] = mapped_column(Float, nullable=False)
    risk_delta: Mapped[float] = mapped_column(Float, nullable=False)
    absolute_risk_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    relative_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    risk_category_baseline: Mapped[str] = mapped_column(String(16), default="LOW")
    risk_category_counterfactual: Mapped[str] = mapped_column(String(16), default="LOW")

    ood_baseline: Mapped[bool] = mapped_column(default=False)
    ood_counterfactual: Mapped[bool] = mapped_column(default=False)

    data_quality_baseline: Mapped[str] = mapped_column(String(16), default="GOOD")
    data_quality_counterfactual: Mapped[str] = mapped_column(String(16), default="GOOD")

    interventions_data: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    feature_changes: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    limitations: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    causal_status: Mapped[str] = mapped_column(
        String(64),
        default="MODEL_BASED_COUNTERFACTUAL",
        nullable=False,
    )
    disclaimer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
