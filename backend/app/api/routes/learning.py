"""REST API routes for STEP 8:
Outcome Verification, Forecast Track Record, Alert Performance, Model Health Monitoring & Governed Learning.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import AuditEvent, AuditLogger, Role, get_current_role, require_role
from ...learning.alert_effectiveness import AlertEffectivenessEngine
from ...learning.drift_monitor import ModelHealthMonitor
from ...learning.governance import ModelGovernanceEngine
from ...learning.outcomes import OutcomeVerificationEngine
from ...learning.schemas import (
    AlertPerformanceSummary,
    CandidateTrainingRequest,
    ChampionChallengerStatus,
    ConceptDriftReport,
    DataDriftReport,
    EquityMonitoringReport,
    ModelApprovalRequest,
    ModelCandidateResponse,
    ModelComparisonReport,
    ModelDeploymentRequest,
    ModelHealthReport,
    ModelRollbackRequest,
    OutcomeListResponse,
    OutcomeRecordCreate,
    OutcomeRecordResponse,
    OutcomeRevisionRequest,
    OutcomeRevisionResponse,
    OutcomeVerificationRequest,
    OutcomeVerificationResponse,
    TrackRecordMetrics,
    TrackRecordSummary,
)
from ...learning.track_record import ForecastTrackRecordEngine
from ...models.learning import (
    AlertPerformanceDB,
    ModelCandidateDB,
    OutcomeRecordDB,
    OutcomeRevisionDB,
    OutcomeVerificationDB,
)

logger = logging.getLogger("keshav.api.learning")

router = APIRouter(prefix="/api/v1", tags=["learning", "outcomes", "track-record", "model-health"])


# ============================================================
# 1. Outcome Ingestion & Verification Routes
# ============================================================

@router.post("/outcomes/ingest", response_model=OutcomeRecordResponse, status_code=status.HTTP_201_CREATED)
def ingest_health_outcome(
    payload: OutcomeRecordCreate,
    db: Session = Depends(get_db),
    current_role: Role = Depends(require_role(Role.HEALTH_OFFICIAL)),
) -> Any:
    """Ingest aggregated, privacy-preserving health outcome data (Requires HEALTH_OFFICIAL or ADMIN)."""
    record = OutcomeVerificationEngine.ingest_outcome(payload, db)
    AuditLogger(logger).record(
        AuditEvent(
            actor=current_role.value,
            action="ingest_outcome",
            resource="outcomes",
            details={"outcome_id": record.outcome_id, "location_id": record.location_id, "count": record.observed_count},
        ),
        session=db,
    )
    return OutcomeRecordResponse(
        outcome_id=record.outcome_id,
        location_id=record.location_id,
        outcome_date=record.outcome_date,
        outcome_type=record.outcome_type,
        observed_count=record.observed_count,
        heat_illness_cases=record.heat_illness_cases,
        emergency_visits=record.emergency_visits,
        hospital_admissions=record.hospital_admissions,
        mortality_count=record.mortality_count,
        aggregation_level=record.aggregation_level,
        source=record.source,
        provider=record.provider,
        quality_status=record.quality_status,
        revision_status=record.revision_status,
        is_synthetic=record.is_synthetic,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/outcomes", response_model=OutcomeListResponse)
def list_health_outcomes(
    location_id: Optional[str] = Query(None, description="Filter by location ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Any:
    """List aggregated health outcome records."""
    query = db.query(OutcomeRecordDB)
    if location_id:
        query = query.filter(OutcomeRecordDB.location_id == location_id)

    total = query.count()
    rows = query.order_by(OutcomeRecordDB.outcome_date.desc()).offset(offset).limit(limit).all()

    outcomes = [
        OutcomeRecordResponse(
            outcome_id=r.outcome_id,
            location_id=r.location_id,
            outcome_date=r.outcome_date,
            outcome_type=r.outcome_type,
            observed_count=r.observed_count,
            heat_illness_cases=r.heat_illness_cases,
            emergency_visits=r.emergency_visits,
            hospital_admissions=r.hospital_admissions,
            mortality_count=r.mortality_count,
            aggregation_level=r.aggregation_level,
            source=r.source,
            provider=r.provider,
            quality_status=r.quality_status,
            revision_status=r.revision_status,
            is_synthetic=r.is_synthetic,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]

    return OutcomeListResponse(total=total, limit=limit, offset=offset, outcomes=outcomes)


@router.get("/outcomes/{outcome_id}", response_model=OutcomeRecordResponse)
def get_health_outcome(
    outcome_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve details of a single health outcome record."""
    r = db.query(OutcomeRecordDB).filter(OutcomeRecordDB.outcome_id == outcome_id).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"Outcome '{outcome_id}' not found")
    return OutcomeRecordResponse(
        outcome_id=r.outcome_id,
        location_id=r.location_id,
        outcome_date=r.outcome_date,
        outcome_type=r.outcome_type,
        observed_count=r.observed_count,
        heat_illness_cases=r.heat_illness_cases,
        emergency_visits=r.emergency_visits,
        hospital_admissions=r.hospital_admissions,
        mortality_count=r.mortality_count,
        aggregation_level=r.aggregation_level,
        source=r.source,
        provider=r.provider,
        quality_status=r.quality_status,
        revision_status=r.revision_status,
        is_synthetic=r.is_synthetic,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.post("/outcomes/{outcome_id}/revise", response_model=OutcomeRevisionResponse)
def revise_health_outcome(
    outcome_id: str,
    payload: OutcomeRevisionRequest,
    db: Session = Depends(get_db),
    current_role: Role = Depends(require_role(Role.HEALTH_OFFICIAL)),
) -> Any:
    """Apply an auditable revision to a health outcome record (Requires HEALTH_OFFICIAL or ADMIN)."""
    rev = OutcomeVerificationEngine.revise_outcome(outcome_id, payload, db)
    AuditLogger(logger).record(
        AuditEvent(
            actor=current_role.value,
            action="revise_outcome",
            resource="outcomes",
            details={"outcome_id": outcome_id, "prev": rev.previous_count, "new": rev.new_count},
        ),
        session=db,
    )
    return OutcomeRevisionResponse(
        revision_id=rev.revision_id,
        outcome_id=rev.outcome_id,
        previous_count=rev.previous_count,
        new_count=rev.new_count,
        previous_status=rev.previous_status,
        new_status=rev.new_status,
        reason=rev.reason,
        revised_by=rev.revised_by,
        revised_at=rev.revised_at,
    )


@router.post("/outcomes/verify", response_model=OutcomeVerificationResponse)
def verify_prediction_outcome(
    payload: OutcomeVerificationRequest,
    db: Session = Depends(get_db),
    current_role: Role = Depends(get_current_role),
) -> Any:
    """Verify a historical risk prediction against actual observed outcomes in target window."""
    try:
        verif = OutcomeVerificationEngine.verify_prediction(payload, db)
        return verif
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/outcomes/verification/{prediction_id}", response_model=List[OutcomeVerificationResponse])
def get_prediction_verifications(
    prediction_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Get all verification records associated with a specific prediction."""
    rows = db.query(OutcomeVerificationDB).filter(OutcomeVerificationDB.prediction_id == prediction_id).all()
    return [
        OutcomeVerificationResponse(
            verification_id=r.verification_id,
            prediction_id=r.prediction_id,
            location_id=r.location_id,
            model_id=r.model_id,
            model_version=r.model_version,
            forecast_issued_at=r.forecast_issued_at,
            forecast_valid_from=r.forecast_valid_from,
            forecast_valid_to=r.forecast_valid_to,
            forecast_horizon_hours=r.forecast_horizon_hours,
            predicted_risk_probability=r.predicted_risk_probability,
            predicted_risk_category=r.predicted_risk_category,
            observed_outcome_id=r.observed_outcome_id,
            observed_value=r.observed_value,
            verification_window=r.verification_window,
            error_residual=r.error_residual,
            brier_contribution=r.brier_contribution,
            match_status=r.match_status,
            event_ground_truth=r.event_ground_truth,
            event_prediction=r.event_prediction,
            classification_outcome=r.classification_outcome,
            is_synthetic=r.is_synthetic,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ============================================================
# 2. Forecast Track Record Routes
# ============================================================

@router.get("/track-record", response_model=TrackRecordSummary)
def get_forecast_track_record(
    location_id: Optional[str] = Query(None, description="Filter by ward ID"),
    model_id: Optional[str] = Query(None, description="Filter by model ID"),
    horizon_hours: Optional[int] = Query(None, description="Filter by forecast horizon"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve historical forecast track record and verification skill metrics."""
    return ForecastTrackRecordEngine.get_track_record(
        db=db,
        location_id=location_id,
        model_id=model_id,
        horizon_hours=horizon_hours,
        limit=limit,
    )


@router.get("/track-record/model/{model_id}", response_model=TrackRecordSummary)
def get_track_record_by_model(
    model_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve track record for a specific model."""
    return ForecastTrackRecordEngine.get_track_record(db=db, model_id=model_id, limit=limit)


@router.get("/track-record/location/{location_id}", response_model=TrackRecordSummary)
def get_track_record_by_location(
    location_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve track record for a specific ward / location."""
    return ForecastTrackRecordEngine.get_track_record(db=db, location_id=location_id, limit=limit)


@router.get("/track-record/forecast-horizon/{hours}", response_model=TrackRecordSummary)
def get_track_record_by_horizon(
    hours: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve track record for a specific forecast lead-time horizon (e.g. 24, 48, 72 hours)."""
    return ForecastTrackRecordEngine.get_track_record(db=db, horizon_hours=hours, limit=limit)


@router.get("/track-record/metrics", response_model=TrackRecordMetrics)
def get_track_record_aggregate_metrics(
    location_id: Optional[str] = Query(None),
    model_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Any:
    """Compute aggregate forecast performance, Brier score, and contingency metrics."""
    summary = ForecastTrackRecordEngine.get_track_record(db=db, location_id=location_id, model_id=model_id)
    return summary.metrics


# ============================================================
# 3. Alert Performance Routes
# ============================================================

@router.get("/alert-performance", response_model=AlertPerformanceSummary)
@router.get("/alert-performance/summary", response_model=AlertPerformanceSummary)
def get_alert_performance_summary(
    location_id: Optional[str] = Query(None, description="Filter by location ID"),
    channel: Optional[str] = Query(None, description="Filter by channel"),
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve operational alert performance, delivery metrics, confusion matrix, and fatigue metrics."""
    return AlertEffectivenessEngine.evaluate_summary(db=db, location_id=location_id, channel=channel)


@router.get("/alert-performance/location/{location_id}", response_model=AlertPerformanceSummary)
def get_alert_performance_by_location(
    location_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve alert performance for a specific location."""
    return AlertEffectivenessEngine.evaluate_summary(db=db, location_id=location_id)


@router.get("/alert-performance/channel/{channel}", response_model=AlertPerformanceSummary)
def get_alert_performance_by_channel(
    channel: str,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve alert delivery performance for a specific channel."""
    return AlertEffectivenessEngine.evaluate_summary(db=db, channel=channel)


# ============================================================
# 4. Model Health & Drift Monitoring Routes
# ============================================================

@router.get("/model-health", response_model=ModelHealthReport)
def get_model_health_report(
    model_id: str = Query("KESHAV_GBM_PROD"),
    model_version: str = Query("1.0"),
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve synthesized model health report including drift, calibration, OOD, and equity monitoring."""
    return ModelHealthMonitor.generate_health_report(db=db, model_id=model_id, model_version=model_version)


@router.get("/model-health/{model_id}", response_model=ModelHealthReport)
def get_model_health_for_model(
    model_id: str,
    model_version: str = Query("1.0"),
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve health report for a specific registered model ID."""
    return ModelHealthMonitor.generate_health_report(db=db, model_id=model_id, model_version=model_version)


@router.get("/model-health/drift", response_model=DataDriftReport)
def get_data_drift_report(
    model_id: str = Query("KESHAV_GBM_PROD"),
    db: Session = Depends(get_db),
) -> Any:
    """Evaluate feature data drift via Population Stability Index (PSI)."""
    return ModelHealthMonitor.evaluate_data_drift(db=db, model_id=model_id)


@router.get("/model-health/calibration", response_model=ConceptDriftReport)
def get_concept_and_calibration_drift(
    model_id: str = Query("KESHAV_GBM_PROD"),
    db: Session = Depends(get_db),
) -> Any:
    """Evaluate concept drift and calibration stability over time."""
    return ModelHealthMonitor.evaluate_concept_drift(db=db, model_id=model_id)


@router.get("/model-health/equity", response_model=EquityMonitoringReport)
def get_subgroup_equity_monitoring(
    model_version: str = Query("1.0"),
    db: Session = Depends(get_db),
) -> Any:
    """Evaluate subgroup performance disparity trends across vulnerable cohorts."""
    return ModelHealthMonitor.evaluate_equity_monitoring(db=db, model_version=model_version)


# ============================================================
# 5. Controlled Model Learning & Governance Routes
# ============================================================

@router.post("/model-learning/train", response_model=ModelCandidateResponse, status_code=status.HTTP_201_CREATED)
def train_candidate_model(
    payload: CandidateTrainingRequest,
    db: Session = Depends(get_db),
    current_role: Role = Depends(require_role(Role.ADMIN)),
) -> Any:
    """Train a candidate challenger model with strict temporal splitting and safety gates (Requires ADMIN)."""
    try:
        cand = ModelGovernanceEngine.train_candidate(payload, db, actor=current_role.value)
        AuditLogger(logger).record(
            AuditEvent(
                actor=current_role.value,
                action="train_candidate_model",
                resource="model_governance",
                details={"candidate_id": cand.candidate_id, "algorithm": cand.algorithm, "version": cand.model_version},
            ),
            session=db,
        )
        return ModelCandidateResponse(
            candidate_id=cand.candidate_id,
            model_id=cand.model_id,
            model_version=cand.model_version,
            training_run_id=cand.training_run_id,
            algorithm=cand.algorithm,
            dataset_version=cand.dataset_version,
            feature_manifest_version=cand.feature_manifest_version,
            status=cand.status,
            artifact_hash=cand.artifact_hash,
            metrics=cand.metrics,
            safety_gates_passed=cand.safety_gates_passed,
            safety_gate_details=cand.safety_gate_details,
            comparison_summary=cand.comparison_summary,
            created_at=cand.created_at,
            created_by=cand.created_by,
            approved_at=cand.approved_at,
            approved_by=cand.approved_by,
            approval_notes=cand.approval_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/model-learning/runs", response_model=List[ModelCandidateResponse])
def list_candidate_runs(
    db: Session = Depends(get_db),
) -> Any:
    """List all trained model candidates and challenger evaluations."""
    rows = db.query(ModelCandidateDB).order_by(ModelCandidateDB.created_at.desc()).all()
    return [
        ModelCandidateResponse(
            candidate_id=r.candidate_id,
            model_id=r.model_id,
            model_version=r.model_version,
            training_run_id=r.training_run_id,
            algorithm=r.algorithm,
            dataset_version=r.dataset_version,
            feature_manifest_version=r.feature_manifest_version,
            status=r.status,
            artifact_hash=r.artifact_hash,
            metrics=r.metrics,
            safety_gates_passed=r.safety_gates_passed,
            safety_gate_details=r.safety_gate_details,
            comparison_summary=r.comparison_summary,
            created_at=r.created_at,
            created_by=r.created_by,
            approved_at=r.approved_at,
            approved_by=r.approved_by,
            approval_notes=r.approval_notes,
        )
        for r in rows
    ]


@router.get("/model-learning/runs/{candidate_id}", response_model=ModelCandidateResponse)
def get_candidate_run(
    candidate_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve details for a specific model candidate run."""
    r = db.query(ModelCandidateDB).filter(ModelCandidateDB.candidate_id == candidate_id).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found")
    return ModelCandidateResponse(
        candidate_id=r.candidate_id,
        model_id=r.model_id,
        model_version=r.model_version,
        training_run_id=r.training_run_id,
        algorithm=r.algorithm,
        dataset_version=r.dataset_version,
        feature_manifest_version=r.feature_manifest_version,
        status=r.status,
        artifact_hash=r.artifact_hash,
        metrics=r.metrics,
        safety_gates_passed=r.safety_gates_passed,
        safety_gate_details=r.safety_gate_details,
        comparison_summary=r.comparison_summary,
        created_at=r.created_at,
        created_by=r.created_by,
        approved_at=r.approved_at,
        approved_by=r.approved_by,
        approval_notes=r.approval_notes,
    )


@router.post("/model-learning/compare", response_model=ModelComparisonReport)
def compare_champion_challenger(
    challenger_candidate_id: str = Query(..., description="Candidate ID to compare against active champion"),
    db: Session = Depends(get_db),
) -> Any:
    """Compare candidate challenger against the production champion across comprehensive metrics and safety gates."""
    try:
        report = ModelGovernanceEngine.compare_champion_challenger(challenger_candidate_id, db)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/model-learning/{candidate_id}/approve", response_model=ModelCandidateResponse)
def approve_candidate_model(
    candidate_id: str,
    payload: ModelApprovalRequest,
    db: Session = Depends(get_db),
    current_role: Role = Depends(require_role(Role.ADMIN)),
) -> Any:
    """Approve a validated challenger model for production deployment (Requires ADMIN)."""
    try:
        cand = ModelGovernanceEngine.approve_candidate(candidate_id, payload, db)
        AuditLogger(logger).record(
            AuditEvent(
                actor=current_role.value,
                action="approve_candidate_model",
                resource="model_governance",
                details={"candidate_id": candidate_id, "approved_by": payload.approved_by},
            ),
            session=db,
        )
        return ModelCandidateResponse(
            candidate_id=cand.candidate_id,
            model_id=cand.model_id,
            model_version=cand.model_version,
            training_run_id=cand.training_run_id,
            algorithm=cand.algorithm,
            dataset_version=cand.dataset_version,
            feature_manifest_version=cand.feature_manifest_version,
            status=cand.status,
            artifact_hash=cand.artifact_hash,
            metrics=cand.metrics,
            safety_gates_passed=cand.safety_gates_passed,
            safety_gate_details=cand.safety_gate_details,
            comparison_summary=cand.comparison_summary,
            created_at=cand.created_at,
            created_by=cand.created_by,
            approved_at=cand.approved_at,
            approved_by=cand.approved_by,
            approval_notes=cand.approval_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/model-learning/{candidate_id}/deploy", response_model=Dict[str, Any])
def deploy_candidate_model(
    candidate_id: str,
    payload: ModelDeploymentRequest,
    db: Session = Depends(get_db),
    current_role: Role = Depends(require_role(Role.ADMIN)),
) -> Any:
    """Deploy an approved candidate to active PRODUCTION champion status (Requires ADMIN)."""
    try:
        dep = ModelGovernanceEngine.deploy_candidate(candidate_id, payload, db)
        AuditLogger(logger).record(
            AuditEvent(
                actor=current_role.value,
                action="deploy_candidate_model",
                resource="model_governance",
                details={"deployment_id": dep.deployment_id, "new_champion": dep.new_champion_version},
            ),
            session=db,
        )
        return {
            "deployment_id": dep.deployment_id,
            "previous_champion_version": dep.previous_champion_version,
            "new_champion_version": dep.new_champion_version,
            "deployed_by": dep.deployed_by,
            "deployed_at": dep.deployed_at,
            "status": dep.status,
            "message": f"Model {dep.new_champion_version} successfully deployed to PRODUCTION champion.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/model-learning/rollback", response_model=Dict[str, Any])
def rollback_model_deployment(
    payload: ModelRollbackRequest,
    db: Session = Depends(get_db),
    current_role: Role = Depends(require_role(Role.ADMIN)),
) -> Any:
    """Rollback active production champion to the previous stable model version (Requires ADMIN)."""
    try:
        roll = ModelGovernanceEngine.rollback_deployment(payload, db)
        AuditLogger(logger).record(
            AuditEvent(
                actor=current_role.value,
                action="rollback_model_deployment",
                resource="model_governance",
                details={"rollback_id": roll.rollback_id, "restored_version": roll.restored_model_version},
            ),
            session=db,
        )
        return {
            "rollback_id": roll.rollback_id,
            "rolled_back_model_version": roll.rolled_back_model_version,
            "restored_model_version": roll.restored_model_version,
            "executed_by": roll.executed_by,
            "executed_at": roll.executed_at,
            "reason": roll.reason,
            "message": f"Successfully rolled back from {roll.rolled_back_model_version} to {roll.restored_model_version}.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/model-learning/status", response_model=ChampionChallengerStatus)
def get_model_learning_status(
    db: Session = Depends(get_db),
) -> Any:
    """Get high-level status of Champion model, candidate Challengers, and deployment history."""
    return ModelGovernanceEngine.get_status(db)
