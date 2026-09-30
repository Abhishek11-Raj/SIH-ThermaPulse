"""SQLAlchemy ORM models for the KESHAV foundation.

Tables created in Step 1:
    locations, weather_observations, weather_forecasts,
    air_quality_observations, vulnerability_data, health_outcomes,
    data_quality_records, ingestion_logs, provider_status, audit_logs

Tables created in Step 2:
    data_sources, provider_cache, spatial_mapping

Tables created in Step 3:
    thermal_stress_results, thermal_daily_summary,
    nighttime_heat_metrics, exposure_memory_states,
    thermal_calculation_runs

Tables created in Step 4:
    risk_predictions, risk_training_runs,
    risk_model_registry, risk_evaluation_metrics,
    risk_feature_manifest, risk_calibration

Later steps add predictions, models, evaluations, interventions, alerts and outcome tables.
"""

from .audit_log import AuditLog  # noqa: F401
from .location import Location  # noqa: F401
from .risk import (  # noqa: F401
    RiskCalibration,
    RiskEvaluationMetrics,
    RiskFeatureManifest,
    RiskModelRegistry,
    RiskPrediction,
    RiskTrainingRun,
)
from .step2 import (  # noqa: F401
    DataSource,
    ProviderCache,
    SpatialMapping,
)
from .alert import (  # noqa: F401
    AlertAcknowledgementDB,
    AlertDB,
    AlertDeliveryDB,
    AlertPolicyDB,
)
from .intervention import InterventionScenarioDB  # noqa: F401
from .learning import (  # noqa: F401
    AlertPerformanceDB,
    DriftRecordDB,
    ModelCandidateDB,
    ModelDeploymentDB,
    ModelRollbackDB,
    OutcomeRecordDB,
    OutcomeRevisionDB,
    OutcomeVerificationDB,
)
from .city_operations import (  # noqa: F401
    ActionTaskDB,
    OperationalPlanDB,
    OperationalPolicyDB,
    OperationalScenarioDB,
    OperationalZoneDB,
    ResourceDB,
    ResourceGapDB,
    ResponseExecutionDB,
)
from .operations import (  # noqa: F401
    DataQualityRecord,
    IngestionLog,
    ProviderStatus,
)
from .thermal import (  # noqa: F401
    ExposureMemoryState,
    NighttimeHeatMetric,
    ThermalCalculationRun,
    ThermalDailySummary,
    ThermalStressResult,
)
from .vulnerability import (  # noqa: F401
    HealthOutcome,
    VulnerabilityData,
)
from .weather import (  # noqa: F401
    AirQualityObservation,
    WeatherForecast,
    WeatherObservation,
)

__all__ = [
    "AuditLog",
    "Location",
    "DataSource",
    "ProviderCache",
    "SpatialMapping",
    "DataQualityRecord",
    "IngestionLog",
    "ProviderStatus",
    "HealthOutcome",
    "VulnerabilityData",
    "AirQualityObservation",
    "WeatherForecast",
    "WeatherObservation",
    "ThermalStressResult",
    "ThermalDailySummary",
    "NighttimeHeatMetric",
    "ExposureMemoryState",
    "ThermalCalculationRun",
    "RiskPrediction",
    "RiskTrainingRun",
    "RiskModelRegistry",
    "RiskEvaluationMetrics",
    "RiskFeatureManifest",
    "RiskCalibration",
    "InterventionScenarioDB",
    "AlertDB",
    "AlertPolicyDB",
    "AlertDeliveryDB",
    "AlertAcknowledgementDB",
    "OutcomeRecordDB",
    "OutcomeVerificationDB",
    "OutcomeRevisionDB",
    "AlertPerformanceDB",
    "DriftRecordDB",
    "ModelCandidateDB",
    "ModelDeploymentDB",
    "ModelRollbackDB",
    "OperationalZoneDB",
    "ResourceDB",
    "ResourceGapDB",
    "OperationalPlanDB",
    "ActionTaskDB",
    "ResponseExecutionDB",
    "OperationalScenarioDB",
    "OperationalPolicyDB",
]