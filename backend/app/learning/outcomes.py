"""Outcome ingestion, validation, revision, and prediction verification engine for KESHAV Step 8."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..core.enums import QualityFlag
from ..models.learning import (
    OutcomeRecordDB,
    OutcomeRevisionDB,
    OutcomeVerificationDB,
)
from ..models.risk import RiskPrediction
from ..utils.time import utcnow
from .schemas import (
    OutcomeMatchStatus,
    OutcomeRecordCreate,
    OutcomeRecordResponse,
    OutcomeRevisionRequest,
    OutcomeRevisionResponse,
    OutcomeVerificationRequest,
    OutcomeVerificationResponse,
    VerificationWindowType,
)

logger = logging.getLogger("keshav.learning.outcomes")


class OutcomeVerificationEngine:
    """Engine for ingesting privacy-preserving health outcomes and verifying prediction accuracy."""

    @classmethod
    def ingest_outcome(
        cls,
        payload: OutcomeRecordCreate,
        db: Session,
    ) -> OutcomeRecordDB:
        """Ingest aggregated, de-identified health outcome data."""
        outcome_id = f"out_{uuid.uuid4().hex[:10]}"
        now = utcnow()

        # Enforce aggregated / non-PII safeguards
        if payload.observed_count < 0:
            raise ValueError("Observed count cannot be negative")

        record = OutcomeRecordDB(
            outcome_id=outcome_id,
            location_id=payload.location_id,
            outcome_date=payload.outcome_date,
            outcome_type=payload.outcome_type,
            observed_count=payload.observed_count,
            heat_illness_cases=payload.heat_illness_cases,
            emergency_visits=payload.emergency_visits,
            hospital_admissions=payload.hospital_admissions,
            mortality_count=payload.mortality_count,
            aggregation_level=payload.aggregation_level,
            source=payload.source,
            provider=payload.provider,
            quality_status=payload.quality_status,
            revision_status=payload.revision_status,
            is_synthetic=payload.is_synthetic,
            provenance=payload.provenance or {"ingested_at": now.isoformat()},
            created_at=now,
            updated_at=now,
        )

        db.add(record)
        db.commit()
        db.refresh(record)
        logger.info("Ingested outcome %s for location %s (count=%d)", outcome_id, payload.location_id, payload.observed_count)
        return record

    @classmethod
    def revise_outcome(
        cls,
        outcome_id: str,
        revision: OutcomeRevisionRequest,
        db: Session,
    ) -> OutcomeRevisionDB:
        """Apply a tracked revision to an existing outcome without erasing history."""
        record = db.query(OutcomeRecordDB).filter(OutcomeRecordDB.outcome_id == outcome_id).first()
        if not record:
            raise ValueError(f"Outcome record '{outcome_id}' not found")

        now = utcnow()
        rev_id = f"rev_{uuid.uuid4().hex[:10]}"

        rev_log = OutcomeRevisionDB(
            revision_id=rev_id,
            outcome_id=outcome_id,
            previous_count=record.observed_count,
            new_count=revision.new_count,
            previous_status=record.revision_status,
            new_status=revision.new_status,
            reason=revision.reason,
            revised_by=revision.revised_by,
            revised_at=now,
        )
        db.add(rev_log)

        # Update record in-place
        record.observed_count = revision.new_count
        record.revision_status = revision.new_status
        record.updated_at = now
        db.commit()
        db.refresh(rev_log)

        logger.info("Revised outcome %s: count %d -> %d", outcome_id, rev_log.previous_count, rev_log.new_count)
        return rev_log

    @classmethod
    def verify_prediction(
        cls,
        request: OutcomeVerificationRequest,
        db: Session,
    ) -> OutcomeVerificationResponse:
        """Verify a historical risk prediction against actual observed health outcomes in the target window."""
        pred = db.query(RiskPrediction).filter(RiskPrediction.prediction_id == request.prediction_id).first()
        if not pred:
            raise ValueError(f"Prediction '{request.prediction_id}' not found in database")

        valid_from = pred.target_date
        valid_to = pred.target_date + timedelta(hours=24)
        if hasattr(pred, "prediction_time") and pred.prediction_time:
            issued_at = pred.prediction_time
        else:
            issued_at = valid_from - timedelta(hours=24)

        horizon_hours = int((valid_from - issued_at).total_seconds() / 3600) if valid_from > issued_at else 24

        # Search for matched outcome in database
        outcome = (
            db.query(OutcomeRecordDB)
            .filter(
                OutcomeRecordDB.location_id == pred.location_id,
                OutcomeRecordDB.outcome_date >= valid_from - timedelta(hours=12),
                OutcomeRecordDB.outcome_date <= valid_to + timedelta(hours=12),
            )
            .order_by(OutcomeRecordDB.outcome_date.asc())
            .first()
        )

        verification_id = f"vfy_{uuid.uuid4().hex[:10]}"
        now = utcnow()

        if outcome is None:
            # MISSING OUTCOME != NO OUTCOME (Never treat missing data as zero events)
            verif_db = OutcomeVerificationDB(
                verification_id=verification_id,
                prediction_id=pred.prediction_id,
                location_id=pred.location_id,
                model_id=pred.model_id or "KESHAV_GBM_PROD",
                model_version=pred.model_version or "1.0",
                forecast_issued_at=issued_at,
                forecast_valid_from=valid_from,
                forecast_valid_to=valid_to,
                forecast_horizon_hours=horizon_hours,
                predicted_risk_probability=pred.risk_probability,
                predicted_risk_category=pred.risk_category,
                observed_outcome_id=None,
                observed_value=None,
                verification_window=request.verification_window.value,
                error_residual=None,
                brier_contribution=None,
                match_status=OutcomeMatchStatus.NO_OUTCOME_AVAILABLE.value,
                event_ground_truth=None,
                event_prediction=pred.risk_probability >= request.event_risk_threshold,
                classification_outcome="UNVERIFIED",
                is_synthetic=True,
                provenance={"status": "missing_outcome_flagged"},
                created_at=now,
            )
            db.add(verif_db)
            db.commit()
            db.refresh(verif_db)

            return OutcomeVerificationResponse(
                verification_id=verif_db.verification_id,
                prediction_id=verif_db.prediction_id,
                location_id=verif_db.location_id,
                model_id=verif_db.model_id,
                model_version=verif_db.model_version,
                forecast_issued_at=verif_db.forecast_issued_at,
                forecast_valid_from=verif_db.forecast_valid_from,
                forecast_valid_to=verif_db.forecast_valid_to,
                forecast_horizon_hours=verif_db.forecast_horizon_hours,
                predicted_risk_probability=verif_db.predicted_risk_probability,
                predicted_risk_category=verif_db.predicted_risk_category,
                observed_outcome_id=None,
                observed_value=None,
                verification_window=verif_db.verification_window,
                error_residual=None,
                brier_contribution=None,
                match_status=verif_db.match_status,
                event_ground_truth=None,
                event_prediction=verif_db.event_prediction,
                classification_outcome="UNVERIFIED",
                is_synthetic=verif_db.is_synthetic,
                created_at=verif_db.created_at,
            )

        # Matched outcome evaluation
        observed_val = float(outcome.observed_count)
        event_true = observed_val >= request.outcome_event_threshold
        event_pred = pred.risk_probability >= request.event_risk_threshold

        ground_truth_binary = 1.0 if event_true else 0.0
        error_residual = abs(pred.risk_probability - ground_truth_binary)
        brier_contribution = (pred.risk_probability - ground_truth_binary) ** 2

        if event_pred and event_true:
            cls_outcome = "TP"
        elif event_pred and not event_true:
            cls_outcome = "FP"
        elif not event_pred and not event_true:
            cls_outcome = "TN"
        else:
            cls_outcome = "FN"

        verif_db = OutcomeVerificationDB(
            verification_id=verification_id,
            prediction_id=pred.prediction_id,
            location_id=pred.location_id,
            model_id=pred.model_id or "KESHAV_GBM_PROD",
            model_version=pred.model_version or "1.0",
            forecast_issued_at=issued_at,
            forecast_valid_from=valid_from,
            forecast_valid_to=valid_to,
            forecast_horizon_hours=horizon_hours,
            predicted_risk_probability=pred.risk_probability,
            predicted_risk_category=pred.risk_category,
            observed_outcome_id=outcome.outcome_id,
            observed_value=observed_val,
            verification_window=request.verification_window.value,
            error_residual=error_residual,
            brier_contribution=brier_contribution,
            match_status=OutcomeMatchStatus.MATCHED.value,
            event_ground_truth=event_true,
            event_prediction=event_pred,
            classification_outcome=cls_outcome,
            is_synthetic=outcome.is_synthetic,
            provenance={
                "outcome_source": outcome.source,
                "outcome_provider": outcome.provider,
                "verified_at": now.isoformat(),
            },
            created_at=now,
        )
        db.add(verif_db)
        db.commit()
        db.refresh(verif_db)

        return OutcomeVerificationResponse(
            verification_id=verif_db.verification_id,
            prediction_id=verif_db.prediction_id,
            location_id=verif_db.location_id,
            model_id=verif_db.model_id,
            model_version=verif_db.model_version,
            forecast_issued_at=verif_db.forecast_issued_at,
            forecast_valid_from=verif_db.forecast_valid_from,
            forecast_valid_to=verif_db.forecast_valid_to,
            forecast_horizon_hours=verif_db.forecast_horizon_hours,
            predicted_risk_probability=verif_db.predicted_risk_probability,
            predicted_risk_category=verif_db.predicted_risk_category,
            observed_outcome_id=outcome.outcome_id,
            observed_value=observed_val,
            verification_window=verif_db.verification_window,
            error_residual=error_residual,
            brier_contribution=brier_contribution,
            match_status=verif_db.match_status,
            event_ground_truth=event_true,
            event_prediction=event_pred,
            classification_outcome=cls_outcome,
            is_synthetic=verif_db.is_synthetic,
            created_at=verif_db.created_at,
        )
