"""REST API routes for STEP 7: Last-Mile Alerts, Action Delivery & Alert Governance."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...alerts.channels import AlertDeliveryRegistry
from ...alerts.decision_engine import (
    ActionRecommendationEngine,
    AlertDecisionEngine,
    MessageTemplateEngine,
)
from ...alerts.policies import AlertPolicyRegistry
from ...alerts.schemas import (
    ActionRecommendation,
    AlertAcknowledgementRequest,
    AlertAcknowledgementResponse,
    AlertChannel,
    AlertCreateRequest,
    AlertDeliveryRecord,
    AlertEvaluationRequest,
    AlertEvaluationResponse,
    AlertGovernanceStatus,
    AlertLevel,
    AlertListResponse,
    AlertMessagePayload,
    AlertPolicy,
    AlertReason,
    AlertRecipientGroup,
    AlertResponse,
    AlertStatus,
)
from ...core.database import get_db
from ...core.security import AuditEvent, AuditLogger, Role, get_current_role, require_role
from ...models.alert import (
    AlertAcknowledgementDB,
    AlertDB,
    AlertDeliveryDB,
    AlertPolicyDB,
)
from ...models.risk import RiskPrediction
from ...utils.time import utcnow

logger = logging.getLogger("keshav.api.alerts")

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def _map_alert_db_to_schema(db_obj: AlertDB) -> AlertResponse:
    """Helper to convert ORM model to Pydantic AlertResponse schema."""
    msgs: Dict[str, AlertMessagePayload] = {}
    if db_obj.messages_data:
        for k, v in db_obj.messages_data.items():
            if isinstance(v, dict):
                msgs[k] = AlertMessagePayload(**v)

    reasons: List[AlertReason] = []
    if db_obj.reasons_data:
        for r in db_obj.reasons_data:
            if isinstance(r, dict):
                reasons.append(AlertReason(**r))

    recommendations: List[ActionRecommendation] = []
    if db_obj.recommendations_data:
        for rec in db_obj.recommendations_data:
            if isinstance(rec, dict):
                recommendations.append(ActionRecommendation(**rec))

    return AlertResponse(
        alert_id=db_obj.alert_id,
        location_id=db_obj.location_id,
        alert_level=AlertLevel(db_obj.alert_level),
        status=AlertStatus(db_obj.status),
        title=db_obj.title,
        summary=db_obj.summary,
        reasons=reasons,
        recommendations=recommendations,
        messages=msgs,
        target_recipient_groups=[
            AlertRecipientGroup(g) for g in (db_obj.target_recipient_groups or [])
        ],
        channels=[AlertChannel(c) for c in (db_obj.channels or [])],
        valid_from=db_obj.valid_from,
        valid_to=db_obj.valid_to,
        created_at=db_obj.created_at,
        created_by=db_obj.created_by,
        prediction_id=db_obj.prediction_id,
        policy_id=db_obj.policy_id,
        data_quality=db_obj.data_quality,
        is_ood=db_obj.is_ood,
        uncertainty_score=db_obj.uncertainty_score,
        deliveries_count=0,
        acknowledged=db_obj.acknowledged,
        acknowledged_at=db_obj.acknowledged_at,
        acknowledged_by=db_obj.acknowledged_by,
        causal_status=db_obj.causal_status,
    )


@router.post("/evaluate", response_model=AlertEvaluationResponse)
def evaluate_alert(
    request: AlertEvaluationRequest,
    db: Session = Depends(get_db),
    current_role: Role = Depends(get_current_role),
) -> Any:
    """Evaluate heat-health risk features against policy and preview alert decision without dispatching."""
    # Look up prediction features if prediction_id provided
    features: Dict[str, Any] = request.current_features or {}
    if request.prediction_id:
        pred = db.query(RiskPrediction).filter(RiskPrediction.prediction_id == request.prediction_id).first()
        if pred:
            features.setdefault("risk_probability", pred.risk_probability)
            features.setdefault("risk_category", pred.risk_category)
            features.setdefault("forecast_uncertainty", pred.forecast_uncertainty or 0.15)
            features.setdefault("data_quality", pred.input_quality or "GOOD")
            if pred.provenance and isinstance(pred.provenance, dict):
                f_dict = pred.provenance.get("feature_values") or pred.provenance.get("features")
                if isinstance(f_dict, dict):
                    for k, v in f_dict.items():
                        features.setdefault(k, v)

    # If features empty, supply representative ward thermal baseline
    if not features:
        features = {
            "risk_probability": 0.65,
            "risk_category": "HIGH",
            "heat_index_c": 41.5,
            "wbgt_c": 31.8,
            "t_min_c": 29.2,
            "recovery_deficit": 2.6,
            "exposure_memory": 2.8,
            "vulnerability_score": 0.65,
            "uncertainty_score": 0.12,
            "data_quality": "GOOD",
            "is_ood": False,
        }

    eval_req = AlertEvaluationRequest(
        location_id=request.location_id,
        prediction_id=request.prediction_id,
        target_date=request.target_date,
        current_features=features,
        policy_id=request.policy_id,
        recipient_group=request.recipient_group,
        include_preview_messages=request.include_preview_messages,
    )

    engine = AlertDecisionEngine()
    return engine.evaluate(eval_req)


@router.post("/create", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
def create_alert(
    request: AlertCreateRequest,
    db: Session = Depends(get_db),
    current_role: Role = Depends(require_role(Role.FIELD_WORKER)),
) -> Any:
    """Create, persist, and queue an approved operational alert (Requires FIELD_WORKER, HEALTH_OFFICIAL, OPERATOR, or ADMIN)."""
    alert_id = f"alt_{uuid.uuid4().hex[:10]}"
    valid_from = request.valid_from or utcnow()
    valid_to = request.valid_to or (valid_from + timedelta(hours=24))

    # Generate localized messages
    msgs_map = MessageTemplateEngine.generate_messages(
        location_id=request.location_id,
        alert_level=request.alert_level,
        reasons=request.reasons,
        recommendations=request.recommendations,
        valid_until=valid_to,
    )

    db_alert = AlertDB(
        alert_id=alert_id,
        location_id=request.location_id,
        alert_level=request.alert_level.value,
        status=AlertStatus.CREATED.value,
        title=request.title,
        summary=request.summary,
        reasons_data=[r.model_dump(mode="json") for r in request.reasons],
        recommendations_data=[rec.model_dump(mode="json") for rec in request.recommendations],
        messages_data={k: v.model_dump(mode="json") for k, v in msgs_map.items()},
        target_recipient_groups=[g.value for g in request.target_recipient_groups],
        channels=[c.value for c in request.channels],
        valid_from=valid_from,
        valid_to=valid_to,
        prediction_id=request.prediction_id,
        policy_id=request.policy_id or "POLICY_STANDARD_2026",
        created_by=current_role.value,
        created_at=utcnow(),
        causal_status="MODEL_BASED_COUNTERFACTUAL",
    )

    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)

    # Dispatch delivery records across selected channels and recipient cohorts
    en_msg = msgs_map.get("en") or list(msgs_map.values())[0]
    for ch in request.channels:
        for grp in request.target_recipient_groups:
            del_rec = AlertDeliveryRegistry.dispatch(
                alert_id=alert_id,
                channel=ch,
                recipient_group=grp,
                message=en_msg,
                allow_mock_fallback=True,
            )
            db_del = AlertDeliveryDB(
                delivery_id=del_rec.delivery_id,
                alert_id=alert_id,
                channel=del_rec.channel.value,
                provider=del_rec.provider,
                recipient_group=del_rec.recipient_group.value,
                status=del_rec.status.value,
                attempt_count=del_rec.attempt_count,
                sent_at=del_rec.sent_at,
                delivered_at=del_rec.delivered_at,
                error_message=del_rec.error_message,
                is_mock=del_rec.is_mock,
                provider_message_id=del_rec.provider_message_id,
            )
            db.add(db_del)

    db.commit()

    AuditLogger(logger).record(
        AuditEvent(
            actor=current_role.value,
            action="create_alert",
            resource="alerts",
            details={
                "alert_id": alert_id,
                "location_id": request.location_id,
                "level": request.alert_level.value,
            },
        ),
        session=db,
    )

    return _map_alert_db_to_schema(db_alert)


@router.get("", response_model=AlertListResponse)
def list_alerts(
    location_id: Optional[str] = Query(None, description="Filter by location ID"),
    alert_level: Optional[AlertLevel] = Query(None, description="Filter by severity level"),
    status_filter: Optional[AlertStatus] = Query(None, alias="status", description="Filter by alert status"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> Any:
    """List operational and public alerts with optional filtering."""
    query = db.query(AlertDB)
    if location_id:
        query = query.filter(AlertDB.location_id == location_id)
    if alert_level:
        query = query.filter(AlertDB.alert_level == alert_level.value)
    if status_filter:
        query = query.filter(AlertDB.status == status_filter.value)

    total = query.count()
    rows = query.order_by(AlertDB.created_at.desc()).offset(offset).limit(limit).all()

    alerts_list = [_map_alert_db_to_schema(r) for r in rows]
    return AlertListResponse(
        total=total,
        limit=limit,
        offset=offset,
        alerts=alerts_list,
    )


@router.get("/policies", response_model=List[AlertPolicy])
def list_alert_policies() -> Any:
    """List all registered and configured alert trigger policies."""
    return AlertPolicyRegistry.list_all()


@router.get("/templates", response_model=Dict[str, Any])
def list_alert_templates() -> Any:
    """List message templates and low-literacy components across supported languages."""
    return {
        "supported_languages": [LanguageCode.EN.value, LanguageCode.HI.value],
        "message_structure": [
            "WHAT_IS_HAPPENING",
            "WHO_SHOULD_TAKE_CARE",
            "WHAT_TO_DO_NOW",
            "UNTIL_WHEN",
        ],
        "sample_template_en": {
            "headline": "[LOCATION] HEAT WARNING: Severe heat stress expected",
            "what_is_happening": "High wet-bulb globe temperature exceeding physiological safety.",
            "who_should_take_care": "Outdoor laborers, elders, and young children.",
            "what_to_do_now": "Drink ORS/water every 20 mins; take 15 min shaded breaks hourly.",
            "until_when": "Next 24 to 48 hours",
        },
        "sample_template_hi": {
            "headline": "[स्थान] हीट चेतावनी: अत्यधिक गर्मी और लू का गंभीर खतरा",
            "what_is_happening": "धूप और उमस के कारण हीट-स्ट्रोक का गंभीर खतरा है।",
            "who_should_take_care": "धूप में काम करने वाले मजदूर, बुजुर्ग और बच्चे।",
            "what_to_do_now": "खूब पानी पिएं, ओआरएस लें और दोपहर में आराम करें।",
            "until_when": "अगले 24 से 48 घंटे तक",
        },
    }


@router.get("/status", response_model=AlertGovernanceStatus)
def get_alert_system_status(
    db: Session = Depends(get_db),
) -> Any:
    """Get operational health, active alert counts, and delivery provider registry status."""
    total_alerts = db.query(AlertDB).count()
    active_alerts = db.query(AlertDB).filter(AlertDB.status.in_(["CREATED", "DELIVERED", "ACKNOWLEDGED"])).count()
    deliveries_count = db.query(AlertDeliveryDB).count()
    failures_count = db.query(AlertDeliveryDB).filter(AlertDeliveryDB.status == "FAILED").count()

    providers_status = AlertDeliveryRegistry.list_providers()

    return AlertGovernanceStatus(
        active_alerts_count=active_alerts,
        total_alerts_count=total_alerts,
        suppressed_count=0,
        deliveries_count=deliveries_count,
        failures_count=failures_count,
        active_providers=providers_status,
    )


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert_by_id(
    alert_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve details, reasons, recommendations, and provenance of a single alert."""
    alert_row = db.query(AlertDB).filter(AlertDB.alert_id == alert_id).first()
    if not alert_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found",
        )

    # Count deliveries
    del_count = db.query(AlertDeliveryDB).filter(AlertDeliveryDB.alert_id == alert_id).count()
    resp = _map_alert_db_to_schema(alert_row)
    resp.deliveries_count = del_count
    return resp


@router.get("/{alert_id}/deliveries", response_model=List[AlertDeliveryRecord])
def get_alert_deliveries(
    alert_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve delivery history and provider dispatch records for an alert."""
    rows = db.query(AlertDeliveryDB).filter(AlertDeliveryDB.alert_id == alert_id).all()
    results: List[AlertDeliveryRecord] = []
    for r in rows:
        results.append(
            AlertDeliveryRecord(
                delivery_id=r.delivery_id,
                alert_id=r.alert_id,
                channel=AlertChannel(r.channel),
                provider=r.provider,
                recipient_group=AlertRecipientGroup(r.recipient_group),
                status=AlertStatus(r.status),
                attempt_count=r.attempt_count,
                sent_at=r.sent_at,
                delivered_at=r.delivered_at,
                error_message=r.error_message,
                is_mock=r.is_mock,
                provider_message_id=r.provider_message_id,
            )
        )
    return results


@router.post("/{alert_id}/acknowledge", response_model=AlertAcknowledgementResponse)
def acknowledge_alert(
    alert_id: str,
    request: AlertAcknowledgementRequest,
    db: Session = Depends(get_db),
    current_role: Role = Depends(require_role(Role.FIELD_WORKER)),
) -> Any:
    """Acknowledge an alert and record operational mitigation actions taken (Requires FIELD_WORKER or above)."""
    alert_row = db.query(AlertDB).filter(AlertDB.alert_id == alert_id).first()
    if not alert_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found",
        )

    ack_id = f"ack_{uuid.uuid4().hex[:10]}"
    now = utcnow()

    db_ack = AlertAcknowledgementDB(
        ack_id=ack_id,
        alert_id=alert_id,
        acknowledged_by=request.acknowledged_by,
        role=request.role,
        action_taken=request.action_taken,
        notes=request.notes,
        acknowledged_at=now,
    )
    db.add(db_ack)

    # Update alert record
    alert_row.acknowledged = True
    alert_row.acknowledged_at = now
    alert_row.acknowledged_by = request.acknowledged_by
    alert_row.status = AlertStatus.ACKNOWLEDGED.value

    db.commit()

    AuditLogger(logger).record(
        AuditEvent(
            actor=request.acknowledged_by,
            action="acknowledge_alert",
            resource="alerts",
            details={
                "ack_id": ack_id,
                "alert_id": alert_id,
                "role": request.role,
            },
        ),
        session=db,
    )

    return AlertAcknowledgementResponse(
        acknowledgement_id=ack_id,
        alert_id=alert_id,
        acknowledged_at=now,
        acknowledged_by=request.acknowledged_by,
        status="ACKNOWLEDGED",
    )
