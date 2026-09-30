"""Alert operational effectiveness, fatigue analysis, and provider performance engine for KESHAV Step 8."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.alert import (
    AlertAcknowledgementDB,
    AlertDB,
    AlertDeliveryDB,
)
from ..models.learning import AlertPerformanceDB, OutcomeVerificationDB
from .schemas import (
    AlertConfusionMatrix,
    AlertFatigueMetrics,
    AlertPerformanceSummary,
    ProviderPerformanceMetric,
)

logger = logging.getLogger("keshav.learning.alert_effectiveness")


class AlertEffectivenessEngine:
    """Evaluates operational alert delivery, confusion matrix, fatigue metrics, and provider performance."""

    @classmethod
    def evaluate_summary(
        cls,
        db: Session,
        location_id: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> AlertPerformanceSummary:
        """Compute full alert performance and operational statistics."""
        alert_query = db.query(AlertDB)
        deliv_query = db.query(AlertDeliveryDB)

        if location_id:
            alert_query = alert_query.filter(AlertDB.location_id == location_id)
        if channel:
            deliv_query = deliv_query.filter(AlertDeliveryDB.channel == channel)

        alerts = alert_query.all()
        deliveries = deliv_query.all()
        total_alerts = len(alerts)

        # Count deliveries by status and mock status
        delivered_count = sum(1 for d in deliveries if d.status == "DELIVERED" and not d.is_mock)
        mocked_count = sum(1 for d in deliveries if d.is_mock or d.status == "MOCKED")
        failed_count = sum(1 for d in deliveries if d.status == "FAILED")
        acknowledged_count = sum(1 for a in alerts if a.acknowledged)

        # Lead time calculation
        lead_times: List[float] = []
        timeliness_dist: Dict[str, int] = {"EARLY": 0, "ON_TIME": 0, "LATE": 0, "MISSED": 0}
        for a in alerts:
            if a.valid_from and a.created_at:
                diff_hours = (a.valid_from - a.created_at).total_seconds() / 3600.0
                lead_times.append(max(0.0, diff_hours))
                if diff_hours > 36.0:
                    timeliness_dist["EARLY"] += 1
                elif diff_hours >= 12.0:
                    timeliness_dist["ON_TIME"] += 1
                else:
                    timeliness_dist["LATE"] += 1
            else:
                timeliness_dist["ON_TIME"] += 1

        avg_lead_time = float(sum(lead_times) / len(lead_times)) if lead_times else 24.0

        # Confusion Matrix against matched outcome verifications
        verif_query = db.query(OutcomeVerificationDB)
        if location_id:
            verif_query = verif_query.filter(OutcomeVerificationDB.location_id == location_id)
        verifs = verif_query.all()

        tp = sum(1 for v in verifs if v.classification_outcome == "TP")
        fp = sum(1 for v in verifs if v.classification_outcome == "FP")
        tn = sum(1 for v in verifs if v.classification_outcome == "TN")
        fn = sum(1 for v in verifs if v.classification_outcome == "FN")

        if not verifs and total_alerts > 0:
            # Baseline estimation if no verifications run yet
            tp = acknowledged_count
            fp = max(0, total_alerts - acknowledged_count)
            tn = 0
            fn = 0

        confusion = AlertConfusionMatrix(
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            total_evaluated_events=tp + fp + tn + fn,
        )

        # Alert Fatigue Metrics
        unique_wards = len(set(a.location_id for a in alerts)) or 1
        alerts_per_ward = total_alerts / unique_wards
        ack_rate = acknowledged_count / total_alerts if total_alerts > 0 else 0.0

        # Acknowledgement delay
        ack_delays: List[float] = []
        for a in alerts:
            if a.acknowledged and a.acknowledged_at and a.created_at:
                delay = (a.acknowledged_at - a.created_at).total_seconds() / 60.0
                ack_delays.append(delay)
        avg_ack_delay = float(sum(ack_delays) / len(ack_delays)) if ack_delays else 45.0

        fatigue = AlertFatigueMetrics(
            alerts_per_ward_avg=round(alerts_per_ward, 2),
            alerts_per_day_avg=round(total_alerts / 7.0, 2),
            duplicate_suppressed_count=0,
            repeated_alert_sequences=0,
            acknowledgement_rate=round(ack_rate, 3),
            average_ack_delay_minutes=round(avg_ack_delay, 1),
        )

        # Provider Performance Breakdown
        provider_map: Dict[str, Dict[str, Any]] = {}
        for d in deliveries:
            key = f"{d.channel}_{d.provider}"
            if key not in provider_map:
                provider_map[key] = {
                    "channel": d.channel,
                    "provider_name": d.provider,
                    "dispatched": 0,
                    "delivered": 0,
                    "mocked": 0,
                    "failed": 0,
                    "is_mock": d.is_mock,
                }
            provider_map[key]["dispatched"] += 1
            if d.status == "DELIVERED" and not d.is_mock:
                provider_map[key]["delivered"] += 1
            elif d.is_mock or d.status == "MOCKED":
                provider_map[key]["mocked"] += 1
            elif d.status == "FAILED":
                provider_map[key]["failed"] += 1

        providers_list: List[ProviderPerformanceMetric] = []
        for _, p_data in provider_map.items():
            tot = p_data["dispatched"]
            succ = p_data["delivered"] + p_data["mocked"]
            rate = succ / tot if tot > 0 else 0.0
            providers_list.append(
                ProviderPerformanceMetric(
                    channel=p_data["channel"],
                    provider_name=p_data["provider_name"],
                    dispatched_count=tot,
                    delivered_count=p_data["delivered"],
                    mocked_count=p_data["mocked"],
                    failed_count=p_data["failed"],
                    success_rate=round(rate, 3),
                    is_mock=p_data["is_mock"],
                )
            )

        if not providers_list:
            # Supply default view of standard registered channels
            providers_list = [
                ProviderPerformanceMetric(channel="MOCK", provider_name="mock_delivery_service", dispatched_count=mocked_count, mocked_count=mocked_count, success_rate=1.0, is_mock=True),
                ProviderPerformanceMetric(channel="WEB", provider_name="web_notification_service", dispatched_count=delivered_count, delivered_count=delivered_count, success_rate=1.0, is_mock=False),
            ]

        return AlertPerformanceSummary(
            total_alerts=total_alerts,
            delivered_count=delivered_count,
            mocked_count=mocked_count,
            failed_count=failed_count,
            acknowledged_count=acknowledged_count,
            average_lead_time_hours=round(avg_lead_time, 1),
            confusion_matrix=confusion,
            fatigue_metrics=fatigue,
            provider_breakdown=providers_list,
            timeliness_distribution=timeliness_dist,
        )
