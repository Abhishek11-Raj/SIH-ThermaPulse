"""Unit and integration tests for KESHAV STEP 8:
Outcome Verification, Forecast Track Record, Alert Effectiveness, Model Health Monitoring & Governed Learning.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal, init_db
from app.learning.alert_effectiveness import AlertEffectivenessEngine
from app.learning.drift_monitor import ModelHealthMonitor
from app.learning.governance import ModelGovernanceEngine
from app.learning.outcomes import OutcomeVerificationEngine
from app.learning.schemas import (
    CandidateTrainingRequest,
    ModelApprovalRequest,
    ModelDeploymentRequest,
    ModelHealthStatus,
    ModelRollbackRequest,
    OutcomeRecordCreate,
    OutcomeRevisionRequest,
    OutcomeVerificationRequest,
    VerificationWindowType,
)
from app.learning.track_record import ForecastTrackRecordEngine
from app.main import app
from app.models.alert import AlertDB, AlertDeliveryDB
from app.models.learning import (
    AlertPerformanceDB,
    ModelCandidateDB,
    ModelDeploymentDB,
    OutcomeRecordDB,
    OutcomeRevisionDB,
    OutcomeVerificationDB,
)
from app.models.risk import RiskModelRegistry, RiskPrediction
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


# ============================================================
# 1. Outcome Ingestion & Revision Tests
# ============================================================

def test_outcome_ingestion_and_privacy(db_session):
    """Verify aggregated, privacy-preserving health outcome ingestion."""
    payload = OutcomeRecordCreate(
        location_id="DEMO-WARD-01",
        outcome_date=utcnow(),
        outcome_type="heat_hospital_admissions",
        observed_count=8,
        heat_illness_cases=5,
        hospital_admissions=8,
        aggregation_level="WARD_DAY",
        source="synthetic_health_surveillance",
        provider="mock_health_provider",
        quality_status="VALID",
        revision_status="FINAL",
        is_synthetic=True,
    )
    record = OutcomeVerificationEngine.ingest_outcome(payload, db_session)
    assert record.outcome_id.startswith("out_")
    assert record.location_id == "DEMO-WARD-01"
    assert record.observed_count == 8
    assert record.is_synthetic is True


def test_outcome_revision_audit_trail(db_session):
    """Verify outcome revision updates count while preserving audit trail in OutcomeRevisionDB."""
    payload = OutcomeRecordCreate(
        location_id="DEMO-WARD-02",
        outcome_date=utcnow(),
        outcome_type="heat_hospital_admissions",
        observed_count=6,
        aggregation_level="WARD_DAY",
        revision_status="PRELIMINARY",
    )
    record = OutcomeVerificationEngine.ingest_outcome(payload, db_session)

    rev_req = OutcomeRevisionRequest(
        new_count=9,
        new_status="FINAL",
        reason="Updated with consolidated hospital admission register.",
        revised_by="HEALTH_OFFICIAL_01",
    )
    rev_log = OutcomeVerificationEngine.revise_outcome(record.outcome_id, rev_req, db_session)

    assert rev_log.previous_count == 6
    assert rev_log.new_count == 9
    assert rev_log.reason.startswith("Updated with")

    # Verify original record is updated
    updated = db_session.query(OutcomeRecordDB).filter(OutcomeRecordDB.outcome_id == record.outcome_id).first()
    assert updated.observed_count == 9
    assert updated.revision_status == "FINAL"


# ============================================================
# 2. Outcome Verification & Missing Data Tests
# ============================================================

def test_outcome_verification_matched_and_missing(db_session):
    """Verify temporal matching and verify that missing outcome data is NEVER treated as zero events."""
    now = utcnow()
    target_dt = now.replace(minute=0, second=0, microsecond=0)

    # 1. Create Prediction in DB
    pred_matched = RiskPrediction(
        prediction_id="PRED-TEST-MATCH-01",
        location_id="DEMO-WARD-01",
        prediction_time=now - timedelta(hours=24),
        target_date=target_dt,
        horizon_days=1,
        risk_probability=0.78,
        risk_category="HIGH",
        model_id="KESHAV_GBM_PROD",
        model_version="1.0",
        feature_version="1.0",
        threshold_version="1.0",
        source_type="forecast",
    )
    db_session.add(pred_matched)

    # Ingest matching outcome
    out_payload = OutcomeRecordCreate(
        location_id="DEMO-WARD-01",
        outcome_date=target_dt,
        outcome_type="heat_hospital_admissions",
        observed_count=7,  # event occurred (>= 5 threshold)
    )
    OutcomeVerificationEngine.ingest_outcome(out_payload, db_session)

    # Verify Matched Prediction
    verif_res = OutcomeVerificationEngine.verify_prediction(
        OutcomeVerificationRequest(
            prediction_id="PRED-TEST-MATCH-01",
            verification_window=VerificationWindowType.WINDOW_24H,
            event_risk_threshold=0.60,
            outcome_event_threshold=5,
        ),
        db_session,
    )
    assert verif_res.match_status == "MATCHED"
    assert verif_res.classification_outcome == "TP"
    assert verif_res.event_prediction is True
    assert verif_res.event_ground_truth is True
    assert verif_res.error_residual is not None
    assert verif_res.brier_contribution is not None

    # 2. Create Prediction in an area with MISSING outcome data
    pred_missing = RiskPrediction(
        prediction_id="PRED-TEST-MISSING-01",
        location_id="DATA-POOR-WARD-99",
        prediction_time=now - timedelta(hours=24),
        target_date=target_dt + timedelta(days=5),
        horizon_days=5,
        risk_probability=0.65,
        risk_category="HIGH",
        model_id="KESHAV_GBM_PROD",
        model_version="1.0",
        feature_version="1.0",
        threshold_version="1.0",
        source_type="forecast",
    )
    db_session.add(pred_missing)
    db_session.commit()

    verif_missing = OutcomeVerificationEngine.verify_prediction(
        OutcomeVerificationRequest(
            prediction_id="PRED-TEST-MISSING-01",
            verification_window=VerificationWindowType.WINDOW_24H,
        ),
        db_session,
    )
    # Critical Check: Missing outcome is flagged explicitly and NOT treated as 0 events
    assert verif_missing.match_status == "NO_OUTCOME_AVAILABLE"
    assert verif_missing.classification_outcome == "UNVERIFIED"
    assert verif_missing.observed_value is None
    assert verif_missing.error_residual is None


# ============================================================
# 3. Forecast Track Record & Metric Tests
# ============================================================

def test_forecast_track_record_metrics(db_session):
    """Verify computation of MAE, RMSE, Brier score, ECE, Sensitivity/POD, FAR, and CSI."""
    # Add synthetic verified records with known contingency values
    now = utcnow()
    records = [
        # TP
        OutcomeVerificationDB(
            verification_id=f"vfy_t_{uuid.uuid4().hex[:6]}",
            prediction_id="p1",
            location_id="DEMO-WARD-01",
            model_id="KESHAV_GBM_PROD",
            model_version="1.0",
            forecast_issued_at=now - timedelta(hours=24),
            forecast_valid_from=now,
            forecast_valid_to=now + timedelta(hours=24),
            forecast_horizon_hours=24,
            predicted_risk_probability=0.80,
            predicted_risk_category="HIGH",
            observed_value=8.0,
            error_residual=0.20,
            brier_contribution=0.04,
            match_status="MATCHED",
            event_ground_truth=True,
            event_prediction=True,
            classification_outcome="TP",
        ),
        # FP
        OutcomeVerificationDB(
            verification_id=f"vfy_t_{uuid.uuid4().hex[:6]}",
            prediction_id="p2",
            location_id="DEMO-WARD-01",
            model_id="KESHAV_GBM_PROD",
            model_version="1.0",
            forecast_issued_at=now - timedelta(hours=24),
            forecast_valid_from=now,
            forecast_valid_to=now + timedelta(hours=24),
            forecast_horizon_hours=24,
            predicted_risk_probability=0.70,
            predicted_risk_category="HIGH",
            observed_value=1.0,
            error_residual=0.70,
            brier_contribution=0.49,
            match_status="MATCHED",
            event_ground_truth=False,
            event_prediction=True,
            classification_outcome="FP",
        ),
        # TN
        OutcomeVerificationDB(
            verification_id=f"vfy_t_{uuid.uuid4().hex[:6]}",
            prediction_id="p3",
            location_id="DEMO-WARD-01",
            model_id="KESHAV_GBM_PROD",
            model_version="1.0",
            forecast_issued_at=now - timedelta(hours=24),
            forecast_valid_from=now,
            forecast_valid_to=now + timedelta(hours=24),
            forecast_horizon_hours=24,
            predicted_risk_probability=0.20,
            predicted_risk_category="LOW",
            observed_value=0.0,
            error_residual=0.20,
            brier_contribution=0.04,
            match_status="MATCHED",
            event_ground_truth=False,
            event_prediction=False,
            classification_outcome="TN",
        ),
    ]
    for r in records:
        db_session.add(r)
    db_session.commit()

    summary = ForecastTrackRecordEngine.get_track_record(db_session, location_id="DEMO-WARD-01")
    assert summary.total_verifications >= 3
    assert summary.metrics.sample_size >= 3
    assert summary.metrics.brier_score is not None
    assert summary.metrics.pod is not None
    assert summary.metrics.far is not None
    assert summary.metrics.csi is not None
    assert 20.0 <= summary.metrics.average_lead_time_hours <= 25.0


# ============================================================
# 4. Alert Operational Effectiveness & Fatigue Tests
# ============================================================

def test_alert_effectiveness_and_provider_performance(db_session):
    """Verify alert delivery tracking, timeliness, fatigue metrics, and provider breakdown."""
    now = utcnow()
    # Create test alert
    alert = AlertDB(
        alert_id="ALT-PERF-TEST-01",
        location_id="DEMO-WARD-01",
        alert_level="WARNING",
        status="DELIVERED",
        title="Heat Warning",
        summary="High wet-bulb temperature",
        valid_from=now + timedelta(hours=24),
        valid_to=now + timedelta(hours=48),
        created_at=now,
        acknowledged=True,
        acknowledged_at=now + timedelta(minutes=30),
        acknowledged_by="OPERATOR-01",
        channels=["MOCK", "WEB"],
    )
    db_session.add(alert)

    # Deliveries
    d1 = AlertDeliveryDB(
        delivery_id="DEL-P-01",
        alert_id="ALT-PERF-TEST-01",
        channel="MOCK",
        provider="mock_delivery_service",
        recipient_group="PUBLIC",
        status="MOCKED",
        is_mock=True,
    )
    d2 = AlertDeliveryDB(
        delivery_id="DEL-P-02",
        alert_id="ALT-PERF-TEST-01",
        channel="WEB",
        provider="web_notification_service",
        recipient_group="MUNICIPAL_OPERATORS",
        status="DELIVERED",
        is_mock=False,
    )
    db_session.add(d1)
    db_session.add(d2)
    db_session.commit()

    summary = AlertEffectivenessEngine.evaluate_summary(db_session, location_id="DEMO-WARD-01")
    assert summary.total_alerts >= 1
    assert summary.delivered_count >= 1
    assert summary.mocked_count >= 1
    assert summary.acknowledged_count >= 1
    assert summary.fatigue_metrics.acknowledgement_rate > 0.0
    assert any(p.is_mock is True for p in summary.provider_breakdown)
    assert any(p.is_mock is False for p in summary.provider_breakdown)


# ============================================================
# 5. Drift, OOD, and Equity Monitoring Tests
# ============================================================

def test_model_drift_and_health_monitoring(db_session):
    """Verify feature PSI data drift, concept drift, OOD trends, and equity monitoring."""
    report = ModelHealthMonitor.generate_health_report(db_session, model_id="KESHAV_GBM_PROD", model_version="1.0")
    
    assert report.model_id == "KESHAV_GBM_PROD"
    assert report.status in [
        ModelHealthStatus.HEALTHY,
        ModelHealthStatus.WATCH,
        ModelHealthStatus.DEGRADED,
        ModelHealthStatus.RETRAIN_RECOMMENDED,
    ]
    assert report.data_drift.total_features_evaluated >= 5
    assert len(report.data_drift.features) >= 5
    assert report.concept_drift.baseline_brier > 0.0
    assert report.ood_trend.total_predictions >= 0
    assert len(report.equity_status.subgroups) >= 3
    assert any(s.subgroup == "ELDERLY_POPULATION" for s in report.equity_status.subgroups)


# ============================================================
# 6. Governed Candidate Training & Safety Gates Tests
# ============================================================

def test_candidate_training_and_leakage_safety_gates(db_session):
    """Verify candidate model training, temporal leakage prevention, and safety gate checks."""
    now = utcnow()
    
    # 1. Invalid temporal order must fail with ValueError (leakage prevention)
    with pytest.raises(ValueError, match="Temporal leakage violation"):
        ModelGovernanceEngine.train_candidate(
            CandidateTrainingRequest(
                algorithm="LightGBM",
                dataset_version="2.0",
                training_start_date=now - timedelta(days=10),
                training_end_date=now - timedelta(days=2),
                validation_start_date=now - timedelta(days=5),  # starts before train ends!
                validation_end_date=now,
            ),
            db_session,
        )

    # 2. Valid temporal training run
    req = CandidateTrainingRequest(
        algorithm="LightGBM",
        dataset_version="2.0",
        feature_manifest_version="1.0",
        training_start_date=now - timedelta(days=60),
        training_end_date=now - timedelta(days=20),
        validation_start_date=now - timedelta(days=19),
        validation_end_date=now,
        hyperparameters={"max_depth": 6, "n_estimators": 150},
        random_seed=2026,
    )
    candidate = ModelGovernanceEngine.train_candidate(req, db_session, actor="admin_tester")

    assert candidate.candidate_id.startswith("cand_")
    assert candidate.status in ["VALIDATED", "TRAINED"]
    assert candidate.artifact_hash != ""
    assert candidate.safety_gates_passed is True
    assert "gates" in candidate.safety_gate_details


# ============================================================
# 7. Model Comparison, Approval, Deployment & Rollback Tests
# ============================================================

def test_model_comparison_approval_deployment_and_rollback(db_session):
    """Complete governance lifecycle: Candidate -> Compare -> Approve -> Deploy -> Rollback."""
    now = utcnow()
    
    # 1. Train candidate
    cand = ModelGovernanceEngine.train_candidate(
        CandidateTrainingRequest(
            algorithm="LightGBM",
            dataset_version="2.1",
            training_start_date=now - timedelta(days=90),
            training_end_date=now - timedelta(days=30),
            validation_start_date=now - timedelta(days=29),
            validation_end_date=now,
        ),
        db_session,
        actor="admin",
    )

    # 2. Compare Champion vs Challenger
    comp_report = ModelGovernanceEngine.compare_champion_challenger(cand.candidate_id, db_session)
    assert comp_report.challenger_version == cand.model_version
    assert comp_report.all_safety_gates_passed is True
    assert comp_report.recommendation in ["APPROVE_CANDIDATE", "HUMAN_REVIEW_REQUIRED"]

    # 3. Approve Candidate
    approved = ModelGovernanceEngine.approve_candidate(
        cand.candidate_id,
        ModelApprovalRequest(approved_by="CHIEF_DATA_OFFICER", approval_notes="Validated on extreme heatwave retrospective data."),
        db_session,
    )
    assert approved.status == "APPROVED"
    assert approved.approved_by == "CHIEF_DATA_OFFICER"

    # 4. Deploy Candidate to Production Champion
    deployment = ModelGovernanceEngine.deploy_candidate(
        cand.candidate_id,
        ModelDeploymentRequest(deployed_by="ML_OPERATOR_01", reason="New model v2.1 improves PR-AUC and heatwave sensitivity."),
        db_session,
    )
    assert deployment.deployment_id.startswith("dep_")
    assert deployment.status == "ACTIVE"
    assert deployment.new_champion_version == cand.model_version

    # Verify model registry has new production champion
    prod_model = db_session.query(RiskModelRegistry).filter(RiskModelRegistry.status == "PRODUCTION").first()
    assert prod_model is not None
    assert prod_model.model_version == cand.model_version

    # 5. Rollback Deployment
    rollback = ModelGovernanceEngine.rollback_deployment(
        ModelRollbackRequest(
            target_model_version=deployment.previous_champion_version,
            reason="Observed minor data drift in non-monsoon baseline; reverting to stable champion.",
            executed_by="ADMIN_SAFETY",
        ),
        db_session,
    )
    assert rollback.rollback_id.startswith("roll_")
    assert rollback.restored_model_version == deployment.previous_champion_version

    # Verify model status after rollback
    gov_status = ModelGovernanceEngine.get_status(db_session)
    assert gov_status.last_rollback is not None
    assert gov_status.last_rollback["executed_by"] == "ADMIN_SAFETY"


# ============================================================
# 8. REST API & RBAC Security Tests
# ============================================================

def test_api_outcomes_and_rbac(client: TestClient):
    """Test /api/v1/outcomes routes and RBAC protection."""
    payload = {
        "location_id": "DEMO-WARD-01",
        "outcome_date": utcnow().isoformat(),
        "outcome_type": "heat_hospital_admissions",
        "observed_count": 6,
        "aggregation_level": "WARD_DAY",
    }

    # Public viewer forbidden from ingesting outcomes
    unauth = client.post("/api/v1/outcomes/ingest", json=payload, headers={"X-User-Role": "public_viewer"})
    assert unauth.status_code == 403

    # Authorized health official
    auth = client.post("/api/v1/outcomes/ingest", json=payload, headers={"X-User-Role": "health_official"})
    assert auth.status_code == 201
    out_id = auth.json()["outcome_id"]

    # List outcomes
    list_resp = client.get("/api/v1/outcomes?location_id=DEMO-WARD-01")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1


def test_api_track_record_and_health(client: TestClient):
    """Test /api/v1/track-record and /api/v1/model-health endpoints."""
    tr_resp = client.get("/api/v1/track-record")
    assert tr_resp.status_code == 200
    assert "metrics" in tr_resp.json()

    health_resp = client.get("/api/v1/model-health")
    assert health_resp.status_code == 200
    h_data = health_resp.json()
    assert "status" in h_data
    assert "data_drift" in h_data
    assert "concept_drift" in h_data

    perf_resp = client.get("/api/v1/alert-performance")
    assert perf_resp.status_code == 200
    p_data = perf_resp.json()
    assert "confusion_matrix" in p_data
    assert "fatigue_metrics" in p_data


def test_api_model_learning_lifecycle_rbac(client: TestClient):
    """Test /api/v1/model-learning/* endpoints and RBAC protection."""
    now = utcnow()
    train_payload = {
        "algorithm": "LightGBM",
        "dataset_version": "2.2",
        "training_start_date": (now - timedelta(days=60)).isoformat(),
        "training_end_date": (now - timedelta(days=15)).isoformat(),
        "validation_start_date": (now - timedelta(days=14)).isoformat(),
        "validation_end_date": now.isoformat(),
    }

    # 1. Unauthorized training attempt
    unauth_train = client.post("/api/v1/model-learning/train", json=train_payload, headers={"X-User-Role": "field_worker"})
    assert unauth_train.status_code == 403

    # 2. Authorized training by Admin
    auth_train = client.post("/api/v1/model-learning/train", json=train_payload, headers={"X-User-Role": "admin"})
    assert auth_train.status_code == 201
    cand_data = auth_train.json()
    cand_id = cand_data["candidate_id"]

    # 3. Compare candidate
    comp_resp = client.post(f"/api/v1/model-learning/compare?challenger_candidate_id={cand_id}")
    assert comp_resp.status_code == 200
    assert comp_resp.json()["all_safety_gates_passed"] is True

    # 4. Approve candidate
    appr_resp = client.post(
        f"/api/v1/model-learning/{cand_id}/approve",
        json={"approved_by": "ADMIN_APPROVER", "approval_notes": "All safety gates passed."},
        headers={"X-User-Role": "admin"},
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "APPROVED"

    # 5. Deploy candidate
    dep_resp = client.post(
        f"/api/v1/model-learning/{cand_id}/deploy",
        json={"deployed_by": "ADMIN_DEPLOYER", "reason": "Promoting candidate v2.2 to PRODUCTION."},
        headers={"X-User-Role": "admin"},
    )
    assert dep_resp.status_code == 200
    assert "deployment_id" in dep_resp.json()

    # 6. Status check
    status_resp = client.get("/api/v1/model-learning/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["champion"] is not None
