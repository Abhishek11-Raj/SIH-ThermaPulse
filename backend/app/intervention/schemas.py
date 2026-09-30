"""KESHAV STEP 6: Intervention and Counterfactual Simulation Schemas.

Pydantic schemas for intervention definitions, scenario construction,
counterfactual predictions, and comparison results.

All schemas enforce strict validation and use qualified language
to avoid unsupported causal claims.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Literal


# ============================================================
# Supported Intervention Type Enum
# ============================================================

class InterventionType(str, Enum):
    """Enum for supported intervention types in KESHAV."""

    OUTDOOR_EXPOSURE_REDUCTION = "outdoor_exposure_reduction"
    WORK_REST_SCHEDULE = "work_rest_schedule"
    SHADE_INCREASE = "shade_increase"
    WATER_ACCESS_INCREASE = "water_access_increase"
    COOLING_ACCESS_INCREASE = "cooling_access_increase"
    POWER_RESTORATION = "power_restoration"
    EXPOSURE_TIME_SHIFT = "exposure_time_shift"
    COMBINED = "combined"


# ============================================================
# Intervention Constraint Schema
# ============================================================

class InterventionConstraint(BaseModel):
    """Constraints for an intervention variable."""

    minimum: Optional[float] = None
    maximum: Optional[float] = None
    strict_minimum: bool = False
    strict_maximum: bool = False
    unit: Optional[str] = None
    allowed_direction: Literal["increase", "decrease", "either"] = "either"

    @model_validator(mode="after")
    def validate_min_max(self) -> "InterventionConstraint":
        if self.minimum is not None and self.maximum is not None:
            if self.minimum > self.maximum:
                raise ValueError("minimum must be <= maximum")
        return self


# ============================================================
# Intervention Definition Schema
# ============================================================

class InterventionDefinition(BaseModel):
    """Registered metadata and defaults for an intervention type."""

    id: str
    name: str
    type: InterventionType
    target_variable: str
    description: str = ""
    constraints: Optional[InterventionConstraint] = None
    affects_thermal_stress: bool = True
    affects_exposure: bool = True
    affects_vulnerability: bool = False
    affects_operational: bool = False
    feasibility_constraints: Optional[Dict[str, Any]] = None


# ============================================================
# Intervention Instance Schema
# ============================================================

class Intervention(BaseModel):
    """A user-specified intervention instance for counterfactual simulation.

    Validated against the KESHAV feature pipeline. No causal claims
    are made about actual intervention outcomes.
    """

    intervention_id: str
    name: str = ""
    description: str = ""
    intervention_type: Union[InterventionType, str]
    target_variable: str
    baseline_value: float
    simulated_value: float
    unit: Optional[str] = None
    constraints: Optional[InterventionConstraint] = None
    affects_thermal_stress: bool = True
    affects_exposure: bool = True
    affects_vulnerability: bool = False
    affects_operational: bool = False
    feasibility_constraints: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def validate_fields(self) -> "Intervention":
        if not self.intervention_id or len(self.intervention_id) < 3:
            raise ValueError("intervention_id must be at least 3 characters")
        if isinstance(self.intervention_type, str):
            try:
                self.intervention_type = InterventionType(self.intervention_type)
            except ValueError:
                raise ValueError(f"Unsupported intervention_type: {self.intervention_type}")
        if not self.name:
            self.name = self.intervention_type.value
        return self


# ============================================================
# Intervention Registry
# ============================================================

class InterventionRegistry:
    """Registry for cataloging and validating supported intervention types."""

    _definitions: Dict[InterventionType, InterventionDefinition] = {
        InterventionType.OUTDOOR_EXPOSURE_REDUCTION: InterventionDefinition(
            id="int_outdoor_exposure",
            name="Outdoor Exposure Reduction",
            type=InterventionType.OUTDOOR_EXPOSURE_REDUCTION,
            target_variable="outdoor_exposure_hours",
            description="Reduction in duration of continuous or peak outdoor exposure.",
            constraints=InterventionConstraint(
                minimum=0.0,
                maximum=24.0,
                unit="hours",
                allowed_direction="decrease",
            ),
            affects_thermal_stress=True,
            affects_exposure=True,
            affects_vulnerability=False,
            affects_operational=False,
        ),
        InterventionType.WORK_REST_SCHEDULE: InterventionDefinition(
            id="int_work_rest",
            name="Work-Rest Cycle Schedule",
            type=InterventionType.WORK_REST_SCHEDULE,
            target_variable="rest_cycle_minutes_per_hour",
            description="Mandating regular rest periods in shaded/cooled rest areas.",
            constraints=InterventionConstraint(
                minimum=0.0,
                maximum=60.0,
                unit="minutes_per_hour",
                allowed_direction="increase",
            ),
            affects_thermal_stress=True,
            affects_exposure=True,
            affects_vulnerability=False,
            affects_operational=False,
        ),
        InterventionType.SHADE_INCREASE: InterventionDefinition(
            id="int_shade_increase",
            name="Shade Coverage Increase",
            type=InterventionType.SHADE_INCREASE,
            target_variable="shade_fraction",
            description="Providing tree canopy or artificial shade structures to reduce direct solar radiative load.",
            constraints=InterventionConstraint(
                minimum=0.0,
                maximum=1.0,
                unit="fraction",
                allowed_direction="increase",
            ),
            affects_thermal_stress=True,
            affects_exposure=True,
            affects_vulnerability=False,
            affects_operational=False,
        ),
        InterventionType.WATER_ACCESS_INCREASE: InterventionDefinition(
            id="int_water_access",
            name="Hydration / Water Access",
            type=InterventionType.WATER_ACCESS_INCREASE,
            target_variable="water_access_fraction",
            description="Ensuring readily accessible potable drinking water and oral rehydration solutions.",
            constraints=InterventionConstraint(
                minimum=0.0,
                maximum=1.0,
                unit="fraction",
                allowed_direction="increase",
            ),
            affects_thermal_stress=False,
            affects_exposure=False,
            affects_vulnerability=True,
            affects_operational=False,
        ),
        InterventionType.COOLING_ACCESS_INCREASE: InterventionDefinition(
            id="int_cooling_access",
            name="Cooling Shelter Access",
            type=InterventionType.COOLING_ACCESS_INCREASE,
            target_variable="cooling_access_fraction",
            description="Opening air-conditioned cooling centers, misting stations, and shaded rest zones.",
            constraints=InterventionConstraint(
                minimum=0.0,
                maximum=1.0,
                unit="fraction",
                allowed_direction="increase",
            ),
            affects_thermal_stress=True,
            affects_exposure=True,
            affects_vulnerability=True,
            affects_operational=False,
        ),
        InterventionType.POWER_RESTORATION: InterventionDefinition(
            id="int_power_restoration",
            name="Grid / Power Reliability",
            type=InterventionType.POWER_RESTORATION,
            target_variable="power_reliability_fraction",
            description="Prioritizing power grid stability and backup generation for domestic and commercial cooling.",
            constraints=InterventionConstraint(
                minimum=0.0,
                maximum=1.0,
                unit="fraction",
                allowed_direction="increase",
            ),
            affects_thermal_stress=False,
            affects_exposure=False,
            affects_vulnerability=False,
            affects_operational=True,
        ),
        InterventionType.EXPOSURE_TIME_SHIFT: InterventionDefinition(
            id="int_time_shift",
            name="Exposure Timing Shift",
            type=InterventionType.EXPOSURE_TIME_SHIFT,
            target_variable="exposure_hour_shift",
            description="Rescheduling strenuous outdoor activities away from peak solar hours (12:00-16:00) to morning/evening.",
            constraints=InterventionConstraint(
                minimum=0.0,
                maximum=8.0,
                unit="hours_shifted",
                allowed_direction="increase",
            ),
            affects_thermal_stress=True,
            affects_exposure=True,
            affects_vulnerability=False,
            affects_operational=False,
        ),
        InterventionType.COMBINED: InterventionDefinition(
            id="int_combined",
            name="Combined Multi-Intervention Package",
            type=InterventionType.COMBINED,
            target_variable="combined_package",
            description="Integrated package combining work-rest cycles, shade, hydration, and exposure time-shifting.",
            constraints=InterventionConstraint(
                minimum=0.0,
                maximum=1.0,
                unit="package_intensity",
                allowed_direction="increase",
            ),
            affects_thermal_stress=True,
            affects_exposure=True,
            affects_vulnerability=True,
            affects_operational=True,
        ),
    }

    @classmethod
    def is_supported(cls, interv_type: Union[str, InterventionType]) -> bool:
        """Check if an intervention type is supported."""
        if isinstance(interv_type, str):
            try:
                interv_type = InterventionType(interv_type)
            except ValueError:
                return False
        return interv_type in cls._definitions

    @classmethod
    def get(cls, interv_type: Union[str, InterventionType]) -> Optional[InterventionDefinition]:
        """Get the registered definition for an intervention type."""
        if isinstance(interv_type, str):
            try:
                interv_type = InterventionType(interv_type)
            except ValueError:
                return None
        return cls._definitions.get(interv_type)

    @classmethod
    def list_supported(cls) -> List[InterventionDefinition]:
        """List all supported intervention definitions."""
        return list(cls._definitions.values())


# ============================================================
# Counterfactual Scenario Schema
# ============================================================

class CounterfactualScenario(BaseModel):
    """A complete counterfactual simulation scenario."""

    scenario_id: str
    location_id: str
    model_version: str = "1.0"
    feature_version: str = "1.0"
    baseline_prediction_id: str
    interventions: List[Intervention] = Field(default_factory=list)
    scenario_name: str
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: Literal["PENDING", "COMPUTING", "COMPLETED", "FAILED"] = "COMPLETED"

    baseline_risk_probability: float = 0.0
    counterfactual_risk_probability: float = 0.0
    risk_delta: float = 0.0
    risk_category_baseline: str = "LOW"
    risk_category_counterfactual: str = "LOW"
    absolute_risk_delta: float = 0.0
    relative_change: Optional[float] = None
    ood_baseline: bool = False
    ood_counterfactual: bool = False
    data_quality_baseline: str = "GOOD"
    data_quality_counterfactual: str = "GOOD"
    feature_changes: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

    feature_manifest_version: str = "1.0"
    threshold_version: str = "1.0"
    causal_status: Literal["MODEL_BASED_COUNTERFACTUAL"] = "MODEL_BASED_COUNTERFACTUAL"
    disclaimer: str = (
        "This scenario result is a model-based counterfactual simulation. "
        "It does not predict actual health outcomes and should not be "
        "interpreted as medical advice or guaranteed risk reduction."
    )


# ============================================================
# Scenario Request / Response Schemas
# ============================================================

class ScenarioRequest(BaseModel):
    """Request to create and run a counterfactual scenario."""

    location_id: str
    baseline_prediction_id: str
    scenario_name: str
    description: str = ""
    interventions: List[Intervention] = Field(default_factory=list)
    model_version: Optional[str] = None
    feature_version: Optional[str] = None
    include_explanation: bool = True
    include_equity: bool = False
    include_uncertainty: bool = True


class ScenarioResponse(BaseModel):
    """Response from a counterfactual scenario simulation."""

    scenario_id: str
    status: Literal["PENDING", "COMPUTING", "COMPLETED", "FAILED"] = "COMPLETED"

    baseline: Dict[str, Any]
    counterfactual: Dict[str, Any]
    comparison: Dict[str, Any]
    changes: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

    feature_manifest_version: str = "1.0"
    model_version: str = "1.0"
    scenario_created_at: datetime = Field(default_factory=datetime.utcnow)

    causal_status: Literal["MODEL_BASED_COUNTERFACTUAL"] = "MODEL_BASED_COUNTERFACTUAL"
    disclaimer: str = (
        "This scenario result is a model-based counterfactual simulation. "
        "It does not predict actual health outcomes and should not be "
        "interpreted as medical advice or guaranteed risk reduction."
    )


class BatchScenarioRequest(BaseModel):
    """Request to simulate and compare multiple scenarios against a baseline."""

    baseline_prediction_id: str
    location_id: str
    scenarios: List[ScenarioRequest] = Field(default_factory=list)


class BatchScenarioResponse(BaseModel):
    """Response comparing multiple counterfactual scenarios side-by-side."""

    location_id: str
    baseline_prediction_id: str
    baseline: Dict[str, Any]
    scenarios: List[ScenarioResponse] = Field(default_factory=list)
    comparison_table: List[Dict[str, Any]] = Field(default_factory=list)
    causal_status: Literal["MODEL_BASED_COUNTERFACTUAL"] = "MODEL_BASED_COUNTERFACTUAL"
    disclaimer: str = (
        "These scenario results are model-based counterfactual simulations. "
        "Scenarios are presented side-by-side for comparison without hidden ranking."
    )


# ============================================================
# Equity and Data Coverage Schemas
# ============================================================

class ScenarioEquityResult(BaseModel):
    """Equity analysis results for a scenario across vulnerability subgroups."""

    scenario_id: str
    subgroup_sample_counts: Dict[str, int] = Field(default_factory=dict)
    baseline_risks: Dict[str, float] = Field(default_factory=dict)
    counterfactual_risks: Dict[str, float] = Field(default_factory=dict)
    risk_deltas: Dict[str, float] = Field(default_factory=dict)
    sufficient_sample: Dict[str, bool] = Field(default_factory=dict)
    data_coverage: Dict[str, float] = Field(default_factory=dict)
    insufficient_sample_subgroups: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class DataCoverageInfo(BaseModel):
    """Data coverage information for a scenario."""

    scenario_id: str
    overall_coverage: float = 1.0
    coverage_class: Literal["DATA_RICH", "ADEQUATE", "DATA_POOR"] = "DATA_RICH"
    per_feature: Dict[str, float] = Field(default_factory=dict)
    quality_class: Literal["BEST", "GOOD", "FAIR", "POOR"] = "GOOD"
    ood_status: bool = False
    message: Optional[str] = None
