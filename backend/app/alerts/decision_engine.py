"""Alert decision engine, reason generator, action mapper, and multilingual templater for KESHAV Step 7."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .policies import AlertPolicyRegistry
from .schemas import (
    ActionRecommendation,
    AlertChannel,
    AlertEvaluationRequest,
    AlertEvaluationResponse,
    AlertLevel,
    AlertMessagePayload,
    AlertPolicy,
    AlertReason,
    AlertReasonCode,
    AlertRecipientGroup,
    LanguageCode,
)
from ..utils.time import utcnow

logger = logging.getLogger("keshav.alerts.engine")


class ActionRecommendationEngine:
    """Generates structured, practical public-health and operational recommendations."""

    @classmethod
    def generate_recommendations(
        cls,
        alert_level: AlertLevel,
        reasons: List[AlertReason],
        recipient_groups: List[AlertRecipientGroup],
        vulnerability_score: float = 0.5,
    ) -> List[ActionRecommendation]:
        """Generate targeted action recommendations based on alert severity and driver signals."""
        recommendations: List[ActionRecommendation] = []

        if alert_level == AlertLevel.NORMAL:
            recommendations.append(
                ActionRecommendation(
                    action_id="rec_routine_hydration",
                    category="PUBLIC_HEALTH",
                    title="Routine Hydration & Sunlight Awareness",
                    description="Maintain standard daily hydration (2-3L water) and monitor local thermal advisories.",
                    priority="LOW",
                    target_groups=[AlertRecipientGroup.PUBLIC],
                )
            )
            return recommendations

        # WATCH Actions
        if alert_level in [AlertLevel.WATCH, AlertLevel.WARNING, AlertLevel.HIGH_RISK]:
            recommendations.append(
                ActionRecommendation(
                    action_id="rec_hydration_increase",
                    category="HYDRATION",
                    title="Increase Daily Water Intake (3–4 Liters)",
                    description="Drink oral rehydration solutions (ORS), buttermilk, or clean water at regular 20-30 min intervals even without feeling thirsty.",
                    priority="MEDIUM" if alert_level == AlertLevel.WATCH else "HIGH",
                    target_groups=[AlertRecipientGroup.PUBLIC, AlertRecipientGroup.VULNERABLE_RESIDENTS, AlertRecipientGroup.OUTDOOR_WORKERS],
                    step6_scenario_id="int_water_access",
                    counterfactual_summary="Model simulation indicates +50% hydration access reduces physiological vulnerability multipliers.",
                )
            )

        # Occupational / Workplace Actions
        has_occupational = any(
            g in recipient_groups for g in [AlertRecipientGroup.OUTDOOR_WORKERS, AlertRecipientGroup.MUNICIPAL_OPERATORS]
        ) or any(
            r.code in [AlertReasonCode.EXTREME_THERMAL_STRESS, AlertReasonCode.HIGH_EXPOSURE_MEMORY] for r in reasons
        )
        if has_occupational and alert_level in [AlertLevel.WARNING, AlertLevel.HIGH_RISK]:
            recommendations.append(
                ActionRecommendation(
                    action_id="rec_work_rest_shift",
                    category="WORKPLACE_SAFETY",
                    title="Mandate 15-20 Min Shaded Rest Breaks Hourly",
                    description="Reschedule heavy outdoor physical labor away from 12:00-16:00 peak hours; provide mandatory canopy shade at work sites.",
                    priority="HIGH" if alert_level == AlertLevel.WARNING else "URGENT",
                    target_groups=[AlertRecipientGroup.OUTDOOR_WORKERS, AlertRecipientGroup.MUNICIPAL_OPERATORS],
                    step6_scenario_id="int_work_rest",
                    counterfactual_summary="Model simulation indicates 20 min/hr rest reduces metabolic heat generation and thermal strain.",
                )
            )

        # Nighttime Heat Deficit Actions
        has_nighttime_heat = any(r.code in [AlertReasonCode.HOT_NIGHT, AlertReasonCode.RECOVERY_DEFICIT] for r in reasons)
        if has_nighttime_heat:
            recommendations.append(
                ActionRecommendation(
                    action_id="rec_night_cooling",
                    category="PHYSIOLOGICAL_RECOVERY",
                    title="Maximize Nighttime Passive/Active Ventilation",
                    description="Keep windows open during early morning hours; sleep in well-ventilated lower floors or community cooling shelters.",
                    priority="HIGH",
                    target_groups=[AlertRecipientGroup.VULNERABLE_RESIDENTS, AlertRecipientGroup.PUBLIC],
                    step6_scenario_id="int_cooling_access",
                    counterfactual_summary="Model simulation shows nocturnal cooling recovery reduces multi-day cumulative exposure memory.",
                )
            )

        # Vulnerable Resident Support & Medical Preparedness
        if vulnerability_score > 0.6 or alert_level == AlertLevel.HIGH_RISK:
            recommendations.append(
                ActionRecommendation(
                    action_id="rec_vulnerable_outreach",
                    category="COMMUNITY_SUPPORT",
                    title="Conduct Community Health Worker Visits for Elderly & Chronic Patients",
                    description="Check on isolated elderly citizens, pregnant women, and young children; ensure electrolyte packets and cooling packs are accessible.",
                    priority="URGENT" if alert_level == AlertLevel.HIGH_RISK else "HIGH",
                    target_groups=[AlertRecipientGroup.COMMUNITY_HEALTH_WORKERS, AlertRecipientGroup.HEALTH_WORKERS, AlertRecipientGroup.VULNERABLE_RESIDENTS],
                )
            )

        # Hospital Readiness
        if alert_level == AlertLevel.HIGH_RISK:
            recommendations.append(
                ActionRecommendation(
                    action_id="rec_hospital_heat_beds",
                    category="CLINICAL_PREPAREDNESS",
                    title="Activate Emergency Department Heat-Stroke Protocols",
                    description="Designate dedicated shaded/air-conditioned beds, IV fluid inventory, and rapid ice-immersion cooling baths in emergency wards.",
                    priority="URGENT",
                    target_groups=[AlertRecipientGroup.HOSPITALS, AlertRecipientGroup.HEALTH_WORKERS],
                )
            )

        return recommendations


class MessageTemplateEngine:
    """Generates structured, low-literacy, and multilingual alert messages."""

    @classmethod
    def generate_messages(
        cls,
        location_id: str,
        alert_level: AlertLevel,
        reasons: List[AlertReason],
        recommendations: List[ActionRecommendation],
        valid_until: Optional[datetime] = None,
    ) -> Dict[str, AlertMessagePayload]:
        """Generate formatted message payloads in English and Hindi."""
        duration_str_en = "Next 24 to 48 hours"
        duration_str_hi = "अगले 24 से 48 घंटे"
        if valid_until:
            duration_str_en = f"Until {valid_until.strftime('%Y-%m-%d %H:%M UTC')}"
            duration_str_hi = f"{valid_until.strftime('%Y-%m-%d %H:%M UTC')} तक"

        top_reason_en = reasons[0].description if reasons else "Elevated physiological heat-health risk detected."
        top_reason_hi = "अत्यधिक गर्मी और थर्मल तनाव का खतरा।"
        if reasons and reasons[0].code == AlertReasonCode.HOT_NIGHT:
            top_reason_hi = "रात का तापमान बहुत अधिक है, शरीर को ठंडक नहीं मिल पा रही है।"
        elif reasons and reasons[0].code == AlertReasonCode.EXTREME_THERMAL_STRESS:
            top_reason_hi = "धूप और उमस के कारण हीट-स्ट्रोक का गंभीर खतरा है।"

        top_action_en = recommendations[0].description if recommendations else "Drink ample water and stay shaded."
        top_action_hi = "खूब पानी पिएं, ओआरएस लें और दोपहर 12 से 4 बजे तक धूप में न जाएं।"

        # Level headlines
        level_map_en = {
            AlertLevel.NORMAL: "NORMAL CONDITIONS: Heat monitoring active",
            AlertLevel.WATCH: "HEAT WATCH: Moderate heat-health risk expected",
            AlertLevel.WARNING: "HEAT WARNING: Severe heat stress and health risk",
            AlertLevel.HIGH_RISK: "EXTREME HEAT EMERGENCY: Critical health danger",
        }
        level_map_hi = {
            AlertLevel.NORMAL: "सामान्य स्थिति: नियमित निगरानी जारी",
            AlertLevel.WATCH: "हीट वॉच (सतर्कता): गर्मी और स्वास्थ्य जोखिम की संभावना",
            AlertLevel.WARNING: "हीट चेतावनी: अत्यधिक गर्मी और लू का गंभीर खतरा",
            AlertLevel.HIGH_RISK: "आपातकालीन हीट अलर्ट: जानलेवा लू का खतरा, तुरंत बचाव करें",
        }

        # English Payload
        en_payload = AlertMessagePayload(
            language=LanguageCode.EN,
            headline=f"[{location_id}] {level_map_en.get(alert_level, 'HEAT ALERT')}",
            what_is_happening=top_reason_en,
            who_should_take_care="Elderly, outdoor laborers, young children, and pregnant women.",
            what_to_do_now=top_action_en,
            until_when=duration_str_en,
            full_text=(
                f"KESHAV HEAT ALERT ({alert_level.value}) for {location_id}.\n"
                f"• WHAT IS HAPPENING: {top_reason_en}\n"
                f"• WHO SHOULD TAKE CARE: Outdoor workers, elders, children.\n"
                f"• WHAT TO DO NOW: {top_action_en}\n"
                f"• DURATION: {duration_str_en}\n"
                f"Model-based early warning system."
            ),
        )

        # Hindi Payload
        hi_payload = AlertMessagePayload(
            language=LanguageCode.HI,
            headline=f"[{location_id}] {level_map_hi.get(alert_level, 'हीट अलर्ट')}",
            what_is_happening=top_reason_hi,
            who_should_take_care="बुजुर्ग, बाहर काम करने वाले मजदूर, छोटे बच्चे और बीमार व्यक्ति।",
            what_to_do_now=top_action_hi,
            until_when=duration_str_hi,
            full_text=(
                f"केशव हीट अलर्ट ({alert_level.value}) स्थान: {location_id}\n"
                f"• क्या हो रहा है: {top_reason_hi}\n"
                f"• किसे ध्यान रखना है: धूप में काम करने वाले मजदूर, बुजुर्ग और बच्चे।\n"
                f"• अभी क्या करें: {top_action_hi}\n"
                f"• समय: {duration_str_hi}\n"
                f"एआई आधारित स्वास्थ्य पूर्व-चेतावनी प्रणाली।"
            ),
        )

        return {
            "en": en_payload,
            "hi": hi_payload,
        }


class AlertDecisionEngine:
    """Core decision engine evaluating multi-domain risk features and policies to issue alerts."""

    def __init__(self, policy: Optional[AlertPolicy] = None) -> None:
        self.policy = policy or AlertPolicyRegistry.get("POLICY_STANDARD_2026")

    def evaluate(self, request: AlertEvaluationRequest) -> AlertEvaluationResponse:
        """Evaluate heat-health risk features against policy and synthesize alert decision."""
        policy = AlertPolicyRegistry.get(request.policy_id or self.policy.policy_id) or self.policy
        features = request.current_features or {}

        # 1. Extract Core Signals
        risk_prob = float(features.get("risk_probability", features.get("health_risk_probability", 0.50)))
        risk_cat = str(features.get("risk_category", "MODERATE")).upper()
        heat_index = float(features.get("heat_index_c", 38.0))
        wbgt = float(features.get("wbgt_c", 30.0))
        night_temp = float(features.get("t_min_c", features.get("night_t_min_c", 28.0)))
        recovery_deficit = float(features.get("recovery_deficit", 1.5))
        exposure_memory = float(features.get("exposure_memory", 2.0))
        vulnerability_score = float(features.get("vulnerability_score", 0.60))
        uncertainty_score = float(features.get("uncertainty_score", features.get("forecast_uncertainty", 0.15)))
        data_quality = str(features.get("data_quality", features.get("input_quality", "GOOD"))).upper()
        is_ood = bool(features.get("is_ood", features.get("ood_flag", False)))

        # 2. Determine Raw Severity Level
        if risk_prob >= policy.high_risk_probability_threshold or wbgt >= 33.0 or (heat_index >= 45.0 and recovery_deficit >= 3.0):
            raw_level = AlertLevel.HIGH_RISK
        elif risk_prob >= policy.warning_probability_threshold or wbgt >= 31.0 or heat_index >= 41.0:
            raw_level = AlertLevel.WARNING
        elif risk_prob >= policy.watch_probability_threshold or wbgt >= 28.0 or heat_index >= 36.0:
            raw_level = AlertLevel.WATCH
        else:
            raw_level = AlertLevel.NORMAL

        # 3. Policy Constraints & Safe Handling (OOD / Poor Data / Uncertainty)
        effective_level = raw_level
        is_suppressed = False
        suppression_reason: Optional[str] = None

        if is_ood and policy.ood_policy == "DOWNGRADE" and effective_level == AlertLevel.HIGH_RISK:
            effective_level = AlertLevel.WARNING
        elif is_ood and policy.ood_policy == "SUPPRESS" and effective_level in [AlertLevel.WATCH, AlertLevel.WARNING]:
            is_suppressed = True
            suppression_reason = "SUPPRESSED_DUE_TO_OOD_PREDICTION"

        if data_quality in ["POOR", "CRITICAL"] and policy.poor_data_policy == "DOWNGRADE" and effective_level == AlertLevel.HIGH_RISK:
            effective_level = AlertLevel.WARNING

        # 4. Generate Reason Codes
        reasons: List[AlertReason] = []
        if risk_prob >= policy.high_risk_probability_threshold:
            reasons.append(
                AlertReason(
                    code=AlertReasonCode.HIGH_HEALTH_RISK,
                    title="Extreme AI Health-Risk Probability",
                    description=f"Model-predicted heat-health hospitalization risk is elevated at {risk_prob:.1%}.",
                    trigger_value=risk_prob,
                    threshold_value=policy.high_risk_probability_threshold,
                )
            )
        if wbgt >= 31.0 or heat_index >= 41.0:
            reasons.append(
                AlertReason(
                    code=AlertReasonCode.EXTREME_THERMAL_STRESS,
                    title="Extreme Physiological Thermal Stress",
                    description=f"Combined environmental heat stress (WBGT {wbgt:.1f}°C, Heat Index {heat_index:.1f}°C) exceeds safe human threshold.",
                    trigger_value=wbgt,
                    threshold_value=31.0,
                )
            )
        if night_temp >= 29.0 or recovery_deficit >= 2.5:
            reasons.append(
                AlertReason(
                    code=AlertReasonCode.HOT_NIGHT,
                    title="Nocturnal Thermal Recovery Deficit",
                    description=f"Nighttime minimum temperature {night_temp:.1f}°C prevents physiological core body temperature cooling.",
                    trigger_value=night_temp,
                    threshold_value=29.0,
                )
            )
        if exposure_memory >= 3.0:
            reasons.append(
                AlertReason(
                    code=AlertReasonCode.HIGH_EXPOSURE_MEMORY,
                    title="Accumulated Multi-Day Heat Exposure",
                    description=f"Consecutive days of extreme thermal strain have accumulated significant physiological debt ({exposure_memory:.1f}).",
                    trigger_value=exposure_memory,
                    threshold_value=3.0,
                )
            )
        if vulnerability_score >= 0.70:
            reasons.append(
                AlertReason(
                    code=AlertReasonCode.HIGH_VULNERABILITY,
                    title="High Demographic / Infrastructure Vulnerability",
                    description=f"Ward vulnerability score ({vulnerability_score:.2f}) indicates elevated proportion of outdoor workers or low cooling access.",
                    trigger_value=vulnerability_score,
                    threshold_value=0.70,
                )
            )
        if data_quality in ["POOR", "CRITICAL"]:
            reasons.append(
                AlertReason(
                    code=AlertReasonCode.LOW_DATA_CONFIDENCE,
                    title="Low Observation Data Confidence",
                    description="Missing meteorological or air quality observations present; caution advised with heightened ground surveillance.",
                    source_domain="DATA_QUALITY",
                )
            )
        if is_ood:
            reasons.append(
                AlertReason(
                    code=AlertReasonCode.OOD_PREDICTION,
                    title="Out-of-Distribution Feature Profile",
                    description="Current meteorological combination exceeds model training bounds; uncertainty bounds widened.",
                    source_domain="STEP5_AUDIT",
                )
            )

        if not reasons:
            reasons.append(
                AlertReason(
                    code=AlertReasonCode.ROUTINE_MONITORING,
                    title="Routine Baseline Surveillance",
                    description="Thermal indices and health risk remain within normal seasonal ranges.",
                )
            )

        # 5. Target Cohorts & Eligible Channels
        target_groups = list(policy.default_recipient_groups)
        if request.recipient_group and request.recipient_group not in target_groups:
            target_groups.append(request.recipient_group)
        if effective_level in [AlertLevel.WARNING, AlertLevel.HIGH_RISK]:
            if AlertRecipientGroup.OUTDOOR_WORKERS not in target_groups:
                target_groups.append(AlertRecipientGroup.OUTDOOR_WORKERS)
            if AlertRecipientGroup.VULNERABLE_RESIDENTS not in target_groups:
                target_groups.append(AlertRecipientGroup.VULNERABLE_RESIDENTS)

        eligible_channels = list(policy.default_channels)
        if effective_level == AlertLevel.HIGH_RISK and AlertChannel.WHATSAPP not in eligible_channels:
            eligible_channels.append(AlertChannel.WHATSAPP)

        # 6. Action Recommendations
        recommendations = ActionRecommendationEngine.generate_recommendations(
            alert_level=effective_level,
            reasons=reasons,
            recipient_groups=target_groups,
            vulnerability_score=vulnerability_score,
        )

        # 7. Messages Preview
        valid_until = utcnow() + timedelta(hours=24)
        preview_msgs = {}
        if request.include_preview_messages:
            preview_msgs = MessageTemplateEngine.generate_messages(
                location_id=request.location_id,
                alert_level=effective_level,
                reasons=reasons,
                recommendations=recommendations,
                valid_until=valid_until,
            )

        should_alert = effective_level != AlertLevel.NORMAL and not is_suppressed

        return AlertEvaluationResponse(
            should_alert=should_alert,
            alert_level=effective_level,
            escalation_state="INITIAL",
            reasons=reasons,
            recommendations=recommendations,
            risk_probability=risk_prob,
            risk_category=risk_cat,
            uncertainty_score=uncertainty_score,
            data_quality=data_quality,
            is_ood=is_ood,
            is_suppressed=is_suppressed,
            suppression_reason=suppression_reason,
            policy_id=policy.policy_id,
            target_recipient_groups=target_groups,
            eligible_channels=eligible_channels,
            preview_messages=preview_msgs,
            evaluated_at=utcnow(),
            causal_status="MODEL_BASED_COUNTERFACTUAL",
        )
