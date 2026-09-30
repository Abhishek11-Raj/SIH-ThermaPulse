"""Forecast track record and performance metrics computation engine for KESHAV Step 8."""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from ..models.learning import OutcomeVerificationDB
from .schemas import (
    TrackRecordItem,
    TrackRecordMetrics,
    TrackRecordSummary,
)

logger = logging.getLogger("keshav.learning.track_record")


class ForecastTrackRecordEngine:
    """Computes rigorous forecast track record metrics, calibration, and skill scores."""

    @classmethod
    def get_track_record(
        cls,
        db: Session,
        location_id: Optional[str] = None,
        model_id: Optional[str] = None,
        horizon_hours: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> TrackRecordSummary:
        """Retrieve historical forecast verifications and compute aggregate skill metrics."""
        query = db.query(OutcomeVerificationDB)

        if location_id:
            query = query.filter(OutcomeVerificationDB.location_id == location_id)
        if model_id:
            query = query.filter(OutcomeVerificationDB.model_id == model_id)
        if horizon_hours is not None:
            query = query.filter(OutcomeVerificationDB.forecast_horizon_hours == horizon_hours)
        if start_date:
            query = query.filter(OutcomeVerificationDB.forecast_valid_from >= start_date)
        if end_date:
            query = query.filter(OutcomeVerificationDB.forecast_valid_to <= end_date)

        rows = query.order_by(OutcomeVerificationDB.forecast_valid_from.desc()).all()
        total_count = len(rows)

        matched_rows = [r for r in rows if r.match_status == "MATCHED"]
        missing_count = sum(1 for r in rows if r.match_status == "NO_OUTCOME_AVAILABLE")

        metrics = cls.compute_metrics(matched_rows)

        items = [
            TrackRecordItem(
                verification_id=r.verification_id,
                prediction_id=r.prediction_id,
                location_id=r.location_id,
                model_version=r.model_version,
                forecast_issued_at=r.forecast_issued_at,
                forecast_valid_from=r.forecast_valid_from,
                forecast_valid_to=r.forecast_valid_to,
                forecast_horizon_hours=r.forecast_horizon_hours,
                predicted_risk_probability=r.predicted_risk_probability,
                predicted_risk_category=r.predicted_risk_category,
                observed_value=r.observed_value,
                error_residual=r.error_residual,
                match_status=r.match_status,
                classification_outcome=r.classification_outcome,
            )
            for r in rows[:limit]
        ]

        return TrackRecordSummary(
            total_verifications=total_count,
            matched_verifications=len(matched_rows),
            missing_outcomes=missing_count,
            metrics=metrics,
            records=items,
        )

    @classmethod
    def compute_metrics(cls, matched_records: List[OutcomeVerificationDB]) -> TrackRecordMetrics:
        """Compute verification skill metrics over matched prediction-outcome pairs."""
        n = len(matched_records)
        if n == 0:
            return TrackRecordMetrics(sample_size=0)

        probs: List[float] = []
        truths: List[float] = []
        residuals: List[float] = []
        brier_list: List[float] = []
        lead_times: List[float] = []

        tp = fp = tn = fn = 0

        for r in matched_records:
            p = float(r.predicted_risk_probability)
            y = 1.0 if r.event_ground_truth else 0.0
            probs.append(p)
            truths.append(y)

            if r.error_residual is not None:
                residuals.append(r.error_residual)
            if r.brier_contribution is not None:
                brier_list.append(r.brier_contribution)
            if r.forecast_horizon_hours:
                lead_times.append(float(r.forecast_horizon_hours))

            cls_out = r.classification_outcome
            if cls_out == "TP":
                tp += 1
            elif cls_out == "FP":
                fp += 1
            elif cls_out == "TN":
                tn += 1
            elif cls_out == "FN":
                fn += 1

        # Continuous / Probability metrics
        mae = float(np.mean(residuals)) if residuals else None
        rmse = float(np.sqrt(np.mean([res ** 2 for res in residuals]))) if residuals else None
        brier = float(np.mean(brier_list)) if brier_list else None
        avg_lead = float(np.mean(lead_times)) if lead_times else None

        # Expected Calibration Error (ECE) over 5 equal bins
        ece = cls._calculate_ece(probs, truths, n_bins=5)

        # Binary contingency / event metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0  # Also Sensitivity / POD
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        pod = recall
        far = fp / (tp + fp) if (tp + fp) > 0 else 0.0
        csi = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0

        # Approximate ROC-AUC & PR-AUC if both classes present
        roc_auc = cls._calculate_roc_auc(probs, truths)
        pr_auc = cls._calculate_pr_auc(probs, truths)

        return TrackRecordMetrics(
            sample_size=n,
            mae=mae,
            rmse=rmse,
            brier_score=brier,
            calibration_error=ece,
            precision=precision,
            recall=recall,
            f1_score=f1,
            roc_auc=roc_auc,
            pr_auc=pr_auc,
            specificity=specificity,
            pod=pod,
            far=far,
            csi=csi,
            average_lead_time_hours=avg_lead,
        )

    @classmethod
    def _calculate_ece(cls, probs: List[float], truths: List[float], n_bins: int = 5) -> float:
        """Compute Expected Calibration Error (ECE)."""
        if not probs or len(probs) != len(truths):
            return 0.0

        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        n_total = len(probs)

        for i in range(n_bins):
            bin_lower = bin_boundaries[i]
            bin_upper = bin_boundaries[i + 1]
            in_bin = [
                (p, y) for p, y in zip(probs, truths)
                if (bin_lower <= p <= bin_upper if i == n_bins - 1 else bin_lower <= p < bin_upper)
            ]
            bin_size = len(in_bin)
            if bin_size > 0:
                avg_prob = np.mean([p for p, _ in in_bin])
                avg_true = np.mean([y for _, y in in_bin])
                ece += (bin_size / n_total) * abs(avg_prob - avg_true)

        return float(ece)

    @classmethod
    def _calculate_roc_auc(cls, probs: List[float], truths: List[float]) -> Optional[float]:
        """Compute ROC-AUC rank statistic safely without scikit-learn dependency."""
        pos = [p for p, y in zip(probs, truths) if y == 1.0]
        neg = [p for p, y in zip(probs, truths) if y == 0.0]
        if not pos or not neg:
            return None
        # Mann-Whitney U statistic calculation
        u_sum = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
        return float(u_sum / (len(pos) * len(neg)))

    @classmethod
    def _calculate_pr_auc(cls, probs: List[float], truths: List[float]) -> Optional[float]:
        """Compute PR-AUC using trapezoidal Riemann integration across thresholds."""
        if not any(y == 1.0 for y in truths) or not any(y == 0.0 for y in truths):
            return None
        thresholds = sorted(set(probs), reverse=True)
        recalls = [0.0]
        precisions = [1.0]

        for t in thresholds:
            tp = sum(1 for p, y in zip(probs, truths) if p >= t and y == 1.0)
            fp = sum(1 for p, y in zip(probs, truths) if p >= t and y == 0.0)
            fn = sum(1 for p, y in zip(probs, truths) if p < t and y == 1.0)

            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
            recalls.append(rec)
            precisions.append(prec)

        recalls.append(1.0)
        precisions.append(0.0)

        # Trapezoidal area compatible with NumPy 1.x and 2.x
        trapz_fn = getattr(np, "trapezoid", getattr(np, "trapz", None))
        if trapz_fn:
            area = float(trapz_fn(precisions, recalls))
        else:
            area = float(sum((recalls[i] - recalls[i - 1]) * (precisions[i] + precisions[i - 1]) / 2.0 for i in range(1, len(recalls))))
        return float(abs(area))
