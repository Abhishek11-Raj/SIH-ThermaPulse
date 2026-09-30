"""Alert policy management and catalog for KESHAV Step 7."""

from __future__ import annotations

from typing import Dict, List, Optional
from .schemas import AlertChannel, AlertPolicy, AlertRecipientGroup


class AlertPolicyRegistry:
    """Registry managing standard and customizable alert trigger policies."""

    _policies: Dict[str, AlertPolicy] = {}

    @classmethod
    def initialize_defaults(cls) -> None:
        """Seed default municipal and sector-specific alert policies."""
        cls._policies = {
            "POLICY_STANDARD_2026": AlertPolicy(
                policy_id="POLICY_STANDARD_2026",
                policy_name="National Heat-Health Standard Policy 2026",
                version="1.0",
                description="Default thresholding aligned with physiological thermal indices and health risk model.",
                watch_probability_threshold=0.35,
                warning_probability_threshold=0.60,
                high_risk_probability_threshold=0.80,
                max_tolerated_uncertainty=0.35,
                ood_policy="ALLOW_WITH_FLAG",
                poor_data_policy="FLAG_AND_CAUTION",
                cooldown_minutes=120,
                quiet_hours_enabled=False,
                emergency_override_enabled=True,
                default_recipient_groups=[
                    AlertRecipientGroup.PUBLIC,
                    AlertRecipientGroup.VULNERABLE_RESIDENTS,
                    AlertRecipientGroup.MUNICIPAL_OPERATORS,
                ],
                default_channels=[AlertChannel.WEB, AlertChannel.MOCK],
            ),
            "POLICY_OCCUPATIONAL_WORKERS": AlertPolicy(
                policy_id="POLICY_OCCUPATIONAL_WORKERS",
                policy_name="Outdoor & Construction Worker Protection Policy",
                version="1.0",
                description="Low-latency triggers prioritizing wet-bulb globe temperature and metabolic rest breaks.",
                watch_probability_threshold=0.30,
                warning_probability_threshold=0.50,
                high_risk_probability_threshold=0.70,
                max_tolerated_uncertainty=0.40,
                ood_policy="ALLOW_WITH_FLAG",
                poor_data_policy="FLAG_AND_CAUTION",
                cooldown_minutes=60,
                quiet_hours_enabled=False,
                emergency_override_enabled=True,
                default_recipient_groups=[
                    AlertRecipientGroup.OUTDOOR_WORKERS,
                    AlertRecipientGroup.MUNICIPAL_OPERATORS,
                ],
                default_channels=[AlertChannel.WEB, AlertChannel.SMS, AlertChannel.MOCK],
            ),
            "POLICY_HEALTHCARE_PREPAREDNESS": AlertPolicy(
                policy_id="POLICY_HEALTHCARE_PREPAREDNESS",
                policy_name="Hospital & Healthcare Facility Surveillance Policy",
                version="1.0",
                description="Surveillance policy for emergency departments, clinics, and community health workers.",
                watch_probability_threshold=0.40,
                warning_probability_threshold=0.65,
                high_risk_probability_threshold=0.85,
                max_tolerated_uncertainty=0.30,
                ood_policy="DOWNGRADE",
                poor_data_policy="FLAG_AND_CAUTION",
                cooldown_minutes=180,
                quiet_hours_enabled=True,
                quiet_hours_start=22,
                quiet_hours_end=6,
                emergency_override_enabled=True,
                default_recipient_groups=[
                    AlertRecipientGroup.HOSPITALS,
                    AlertRecipientGroup.HEALTH_WORKERS,
                    AlertRecipientGroup.COMMUNITY_HEALTH_WORKERS,
                ],
                default_channels=[AlertChannel.WEB, AlertChannel.EMAIL, AlertChannel.MOCK],
            ),
        }

    @classmethod
    def get(cls, policy_id: str) -> Optional[AlertPolicy]:
        """Retrieve policy by ID (falls back to default standard policy)."""
        if not cls._policies:
            cls.initialize_defaults()
        return cls._policies.get(policy_id, cls._policies.get("POLICY_STANDARD_2026"))

    @classmethod
    def list_all(cls) -> List[AlertPolicy]:
        """List all registered policies."""
        if not cls._policies:
            cls.initialize_defaults()
        return list(cls._policies.values())

    @classmethod
    def register(cls, policy: AlertPolicy) -> None:
        """Register or overwrite an alert policy."""
        cls._policies[policy.policy_id] = policy


# Ensure defaults are initialized on import
AlertPolicyRegistry.initialize_defaults()
