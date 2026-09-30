"""Unit and integration tests for KESHAV STEP 7: Last-Mile Alerts, Action Delivery & Governance."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

from app.alerts.channels import (
    AlertDeliveryRegistry,
    MockDeliveryProvider,
    WebNotificationProvider,
    SmsDeliveryProvider,
    EmailDeliveryProvider,
)
from app.alerts.decision_engine import (
    ActionRecommendationEngine,
    AlertDecisionEngine,
    MessageTemplateEngine,
)
from app.alerts.policies import AlertPolicyRegistry
from app.alerts.schemas import (
    ActionRecommendation,
    AlertChannel,
    AlertCreateRequest,
    AlertEvaluationRequest,
    AlertLevel,
    AlertMessagePayload,
    AlertPolicy,
    AlertReason,
    AlertReasonCode,
    AlertRecipientGroup,
    AlertStatus,
    LanguageCode,
)
from app.core.database import SessionLocal, init_db
from app.core.security import Role
from app.main import app
from app.models.alert import AlertDB, AlertDeliveryDB, AlertAcknowledgementDB
from app.models.risk import RiskPrediction
from app.utils.time import utcnow


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session():
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_alert_policy_registry_defaults():
    """Verify default policies are registered with expected properties."""
    AlertPolicyRegistry.initialize_defaults()
    policies = AlertPolicyRegistry.list_all()
    assert len(policies) >= 3

    std = AlertPolicyRegistry.get("POLICY_STANDARD_2026")
    assert std is not None
    assert std.policy_id == "POLICY_STANDARD_2026"
    assert std.watch_probability_threshold == 0.35
    assert std.warning_probability_threshold == 0.60
    assert std.high_risk_probability_threshold == 0.80
    assert std.cooldown_minutes == 120

    worker = AlertPolicyRegistry.get("POLICY_OCCUPATIONAL_WORKERS")
    assert worker is not None
    assert worker.high_risk_probability_threshold == 0.70
    assert AlertRecipientGroup.OUTDOOR_WORKERS in worker.default_recipient_groups


def test_alert_decision_engine_severity_levels():
    """Test mapping of health risk and thermal indicators to alert severity levels."""
    policy = AlertPolicyRegistry.get("POLICY_STANDARD_2026")
    engine = AlertDecisionEngine(policy=policy)

    # 1. Normal day
    req_normal = AlertEvaluationRequest(
        location_id="DEMO-WARD-01",
        current_features={
            "risk_probability": 0.15,
            "heat_index_c": 32.0,
            "wbgt_c": 26.0,
            "t_min_c": 22.0,
            "recovery_deficit": 0.5,
            "exposure_memory": 0.5,
            "vulnerability_score": 0.3,
            "data_quality": "GOOD",
            "is_ood": False,
        },
    )
    eval_normal = engine.evaluate(req_normal)
    assert eval_normal.alert_level == AlertLevel.NORMAL
    assert eval_normal.should_alert is False

    # 2. Watch day
    req_watch = AlertEvaluationRequest(
        location_id="DEMO-WARD-01",
        current_features={
            "risk_probability": 0.42,
            "heat_index_c": 39.0,
            "wbgt_c": 29.5,
            "t_min_c": 26.0,
            "recovery_deficit": 1.2,
            "exposure_memory": 1.5,
            "vulnerability_score": 0.5,
            "data_quality": "GOOD",
            "is_ood": False,
        },
    )
    eval_watch = engine.evaluate(req_watch)
    assert eval_watch.alert_level == AlertLevel.WATCH
    assert eval_watch.should_alert is True

    # 3. Warning day
    req_warning = AlertEvaluationRequest(
        location_id="DEMO-WARD-01",
        current_features={
            "risk_probability": 0.68,
            "heat_index_c": 44.0,
            "wbgt_c": 31.5,
            "t_min_c": 29.5,
            "recovery_deficit": 3.0,
            "exposure_memory": 3.5,
            "vulnerability_score": 0.75,
            "data_quality": "GOOD",
            "is_ood": False,
        },
    )
    eval_warning = engine.evaluate(req_warning)
    assert eval_warning.alert_level == AlertLevel.WARNING
    assert eval_warning.should_alert is True
    codes = [r.code for r in eval_warning.reasons]
    assert AlertReasonCode.HIGH_EXPOSURE_MEMORY in codes or AlertReasonCode.HOT_NIGHT in codes or AlertReasonCode.EXTREME_THERMAL_STRESS in codes

    # 4. High Risk day
    req_high = AlertEvaluationRequest(
        location_id="DEMO-WARD-01",
        current_features={
            "risk_probability": 0.85,
            "heat_index_c": 49.0,
            "wbgt_c": 33.5,
            "t_min_c": 30.5,
            "recovery_deficit": 4.0,
            "exposure_memory": 4.5,
            "vulnerability_score": 0.8,
            "data_quality": "GOOD",
            "is_ood": False,
        },
    )
    eval_high = engine.evaluate(req_high)
    assert eval_high.alert_level == AlertLevel.HIGH_RISK
    assert eval_high.should_alert is True


def test_alert_decision_engine_ood_and_poor_data_safety():
    """Verify safety boundaries: OOD downgrading/cautioning and poor data warnings."""
    # Healthcare policy has ood_policy="DOWNGRADE"
    healthcare_engine = AlertDecisionEngine(
        policy=AlertPolicyRegistry.get("POLICY_HEALTHCARE_PREPAREDNESS")
    )

    # High probability but OOD -> downgraded to WARNING under healthcare policy
    req_ood = AlertEvaluationRequest(
        location_id="DEMO-WARD-01",
        policy_id="POLICY_HEALTHCARE_PREPAREDNESS",
        current_features={
            "risk_probability": 0.88,
            "heat_index_c": 48.0,
            "wbgt_c": 32.0,
            "is_ood": True,
            "data_quality": "GOOD",
        },
    )
    eval_ood = healthcare_engine.evaluate(req_ood)
    assert eval_ood.alert_level == AlertLevel.WARNING
    assert eval_ood.is_ood is True
    assert any(r.code == AlertReasonCode.OOD_PREDICTION for r in eval_ood.reasons)

    # Poor data quality flag
    std_engine = AlertDecisionEngine(
        policy=AlertPolicyRegistry.get("POLICY_STANDARD_2026")
    )
    req_poor = AlertEvaluationRequest(
        location_id="DEMO-WARD-01",
        policy_id="POLICY_STANDARD_2026",
        current_features={
            "risk_probability": 0.72,
            "heat_index_c": 43.0,
            "wbgt_c": 31.0,
            "data_quality": "POOR",
            "is_ood": False,
        },
    )
    eval_poor = std_engine.evaluate(req_poor)
    assert any(r.code == AlertReasonCode.LOW_DATA_CONFIDENCE for r in eval_poor.reasons)


def test_action_recommendations_and_counterfactual_links():
    """Verify action recommendation engine produces targeted advice with counterfactual references."""
    reasons = [
        AlertReason(
            code=AlertReasonCode.EXTREME_THERMAL_STRESS,
            title="Extreme Physiological Thermal Stress",
            description="High WBGT",
            trigger_value=32.0,
            threshold_value=31.0,
        ),
        AlertReason(
            code=AlertReasonCode.HOT_NIGHT,
            title="Nocturnal Thermal Recovery Deficit",
            description="Hot night",
            trigger_value=29.5,
            threshold_value=29.0,
        ),
    ]

    recs = ActionRecommendationEngine.generate_recommendations(
        alert_level=AlertLevel.WARNING,
        reasons=reasons,
        recipient_groups=[
            AlertRecipientGroup.PUBLIC,
            AlertRecipientGroup.OUTDOOR_WORKERS,
            AlertRecipientGroup.MUNICIPAL_OPERATORS,
            AlertRecipientGroup.HOSPITALS,
        ],
        vulnerability_score=0.75,
    )
    assert len(recs) >= 3

    # Check that worker recommendation is present
    worker_rec = next((r for r in recs if AlertRecipientGroup.OUTDOOR_WORKERS in r.target_groups), None)
    assert worker_rec is not None
    assert worker_rec.category in ["WORKPLACE_SAFETY", "HYDRATION"]

    # Check counterfactual scenario link presence
    assert any(r.step6_scenario_id is not None for r in recs)


def test_multilingual_message_template_engine():
    """Verify message generation in English and Hindi with low-literacy clarity and no causal claims."""
    reasons = [
        AlertReason(
            code=AlertReasonCode.EXTREME_THERMAL_STRESS,
            title="Extreme Physiological Thermal Stress",
            description="Combined environmental heat stress exceeds safe human threshold.",
            trigger_value=32.5,
            threshold_value=31.0,
        )
    ]
    recs = [
        ActionRecommendation(
            action_id="rec_hydration_increase",
            category="HYDRATION",
            title="Increase Daily Water Intake (3–4 Liters)",
            description="Drink oral rehydration solutions (ORS) at regular 20-30 min intervals.",
            priority="HIGH",
            target_groups=[AlertRecipientGroup.PUBLIC],
        )
    ]

    messages = MessageTemplateEngine.generate_messages(
        location_id="DEMO-WARD-01",
        alert_level=AlertLevel.HIGH_RISK,
        reasons=reasons,
        recommendations=recs,
        valid_until=utcnow() + timedelta(hours=24),
    )

    assert "en" in messages
    assert "hi" in messages

    # English message check
    en_msg = messages["en"]
    assert en_msg.language == LanguageCode.EN
    assert "DEMO-WARD-01" in en_msg.headline
    assert "what_is_happening" in en_msg.model_dump()
    assert "what_to_do_now" in en_msg.model_dump()
    assert "who_should_take_care" in en_msg.model_dump()

    # Hindi message check
    hi_msg = messages["hi"]
    assert hi_msg.language == LanguageCode.HI
    assert "DEMO-WARD-01" in hi_msg.headline
    assert "गर्मी" in hi_msg.headline or "अलर्ट" in hi_msg.headline or "चेतावनी" in hi_msg.headline


def test_channel_delivery_registry_and_mock_execution():
    """Verify delivery provider dispatch, mock recording, and graceful unconfigured channels."""
    msg = AlertMessagePayload(
        language=LanguageCode.EN,
        headline="[DEMO-WARD-01] HEAT WARNING",
        what_is_happening="High heat index",
        who_should_take_care="Everyone",
        what_to_do_now="Drink water",
        until_when="Next 24 hours",
        full_text="Sample alert text",
    )

    # 1. Mock delivery
    mock_res = AlertDeliveryRegistry.dispatch(
        alert_id="ALERT-TEST-001",
        channel=AlertChannel.MOCK,
        recipient_group=AlertRecipientGroup.PUBLIC,
        message=msg,
        allow_mock_fallback=False,
    )
    assert mock_res.status == AlertStatus.MOCKED
    assert mock_res.is_mock is True
    assert mock_res.delivered_at is not None

    # 2. Web delivery
    web_res = AlertDeliveryRegistry.dispatch(
        alert_id="ALERT-TEST-001",
        channel=AlertChannel.WEB,
        recipient_group=AlertRecipientGroup.MUNICIPAL_OPERATORS,
        message=msg,
        allow_mock_fallback=False,
    )
    assert web_res.status == AlertStatus.DELIVERED
    assert web_res.is_mock is False

    # 3. Unconfigured SMS with mock fallback
    sms_fallback_res = AlertDeliveryRegistry.dispatch(
        alert_id="ALERT-TEST-001",
        channel=AlertChannel.SMS,
        recipient_group=AlertRecipientGroup.OUTDOOR_WORKERS,
        message=msg,
        allow_mock_fallback=True,
    )
    assert sms_fallback_res.status == AlertStatus.MOCKED
    assert sms_fallback_res.is_mock is True


def test_api_alert_evaluation_endpoint(client: TestClient):
    """Test POST /api/v1/alerts/evaluate preview endpoint without persistence."""
    req_payload = {
        "location_id": "DEMO-WARD-01",
        "current_features": {
            "risk_probability": 0.76,
            "risk_category": "HIGH",
            "heat_index_c": 45.2,
            "wbgt_c": 31.8,
            "t_min_c": 29.5,
            "recovery_deficit": 2.8,
            "exposure_memory": 3.2,
            "vulnerability_score": 0.70,
            "uncertainty_score": 0.14,
            "data_quality": "GOOD",
            "is_ood": False,
        },
        "policy_id": "POLICY_STANDARD_2026",
        "include_preview_messages": True,
    }
    response = client.post("/api/v1/alerts/evaluate", json=req_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["alert_level"] in ["WARNING", "HIGH_RISK"]
    assert data["should_alert"] is True
    assert "preview_messages" in data
    assert "en" in data["preview_messages"]
    assert "hi" in data["preview_messages"]
    assert len(data["recommendations"]) >= 1


def test_api_alert_policies_and_status(client: TestClient):
    """Test GET /api/v1/alerts/policies and GET /api/v1/alerts/status."""
    pol_resp = client.get("/api/v1/alerts/policies")
    assert pol_resp.status_code == 200
    policies = pol_resp.json()
    assert len(policies) >= 3

    stat_resp = client.get("/api/v1/alerts/status")
    assert stat_resp.status_code == 200
    status_data = stat_resp.json()
    assert "total_alerts_count" in status_data
    assert "active_providers" in status_data
    provider_names = [p["name"] for p in status_data["active_providers"]]
    assert "mock_delivery_service" in provider_names
    assert "web_notification_service" in provider_names


def test_api_alert_creation_persistence_and_rbac(client: TestClient):
    """Test POST /api/v1/alerts/create with RBAC role authorization and delivery logging."""
    create_payload = {
        "location_id": "DEMO-WARD-01",
        "alert_level": "HIGH_RISK",
        "title": "Severe Heat Stress Emergency Alert",
        "summary": "Model estimated high thermal strain and hospitalization risk.",
        "reasons": [
            {
                "code": "HIGH_HEALTH_RISK",
                "title": "High AI Health Risk",
                "description": "Risk probability 0.84",
                "trigger_value": 0.84,
                "threshold_value": 0.80,
                "source_domain": "RISK_MODEL",
            }
        ],
        "recommendations": [
            {
                "action_id": "rec_water_01",
                "category": "HYDRATION",
                "title": "Drink ORS and water",
                "description": "Consume 3-4L water throughout shift",
                "priority": "HIGH",
                "target_groups": ["PUBLIC", "OUTDOOR_WORKERS"],
            }
        ],
        "target_recipient_groups": ["PUBLIC", "OUTDOOR_WORKERS", "MUNICIPAL_OPERATORS"],
        "channels": ["MOCK", "WEB"],
        "notes": "Emergency municipal test alert",
    }

    # 1. Unprivileged public viewer should receive 403 Forbidden
    unauth_resp = client.post(
        "/api/v1/alerts/create",
        json=create_payload,
        headers={"X-User-Role": "public_viewer"},
    )
    assert unauth_resp.status_code == 403

    # 2. Authorized municipal operator creates alert
    auth_resp = client.post(
        "/api/v1/alerts/create",
        json=create_payload,
        headers={"X-User-Role": "municipal_operator"},
    )
    assert auth_resp.status_code == 201
    alert = auth_resp.json()
    alert_id = alert["alert_id"]
    assert alert["alert_level"] == "HIGH_RISK"
    assert alert["location_id"] == "DEMO-WARD-01"

    # 3. Fetch alert by ID
    get_resp = client.get(f"/api/v1/alerts/{alert_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["alert_id"] == alert_id

    # 4. Fetch deliveries for alert
    deliv_resp = client.get(f"/api/v1/alerts/{alert_id}/deliveries")
    assert deliv_resp.status_code == 200
    deliveries = deliv_resp.json()
    assert len(deliveries) >= 2

    # 5. Acknowledge alert (Field worker or Health official or Operator)
    ack_payload = {
        "acknowledged_by": "OPERATOR-DELHI-01",
        "role": "MUNICIPAL_OPERATOR",
        "action_taken": "Issued public water distribution and adjusted shifts for 500 outdoor workers.",
        "notes": "All cooling shelters verified active.",
    }
    ack_resp = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json=ack_payload,
        headers={"X-User-Role": "municipal_operator"},
    )
    assert ack_resp.status_code == 200
    ack_data = ack_resp.json()
    assert ack_data["status"] == "ACKNOWLEDGED"

    # 6. Verify list alerts filter
    list_resp = client.get("/api/v1/alerts?location_id=DEMO-WARD-01")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert any(a["alert_id"] == alert_id for a in list_data["alerts"])
