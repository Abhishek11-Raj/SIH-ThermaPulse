"""Risk prediction service — STEP 4.

Generates health risk predictions from thermal, vulnerability,
and environmental features.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..core.enums import QualityFlag
from ..explainability.explanation_service import ExplanationService
from ..models.risk import RiskPrediction, RiskModelRegistry
from ..models.thermal import ThermalStressResult as ThermalModel
from ..models.vulnerability import VulnerabilityData as VulnModel
from ..models.weather import AirQualityObservation as AQModel
from ..schemas.weather import WeatherObservation
from ..schemas.forecast import WeatherForecast
from ..schemas.air_quality import AirQualityObservation
from ..schemas.health import HealthOutcome
from ..schemas.vulnerability import VulnerabilityRecord
from ..utils.time import utcnow

from .schemas import (
    RiskPredictionOutput,
    RiskPredictionList,
    RiskPredictionRequest,
    RiskForecastOutput,
    RiskCalculateRequest,
)


class RiskPredictor:
    """Generates health risk predictions from features."""

    def __init__(self, db: Session):
        self.db = db

    def _get_model_info(self, model_id: Optional[str]) -> Any:
        """Get model info from registry."""
        if model_id is None:
            model = self.db.query(RiskModelRegistry).filter(
                RiskModelRegistry.status == "PRODUCTION"
            ).order_by(RiskModelRegistry.created_at.desc()).first()
            if not model:
                raise ValueError("No production model available")
            return model
        else:
            model = self.db.query(RiskModelRegistry).filter(
                RiskModelRegistry.model_id == model_id
            ).first()
            if not model:
                raise ValueError(f"Model {model_id} not found")
            return model

    def predict_current(
        self,
        location_id: str,
        model_id: Optional[str] = None,
    ) -> RiskPredictionOutput:
        """
        Generate current (nowcast) health risk prediction.

        Args:
            location_id: Location identifier
            model_id: Optional specific model to use (uses production if None)

        Returns:
            Risk prediction for current conditions
        """
        # Get model info
        model_info = self._get_model_info(model_id)
        model_id = model_info.model_id

        # Load model
        model, preprocessor = self._load_model(model_id)

        # Get current thermal data
        thermal_data = self._get_current_thermal(location_id)
        if thermal_data is None:
            raise ValueError(f"No thermal data available for {location_id}")

        # Get vulnerability data
        vuln_data = self._get_vulnerability(location_id)

        # Get air quality data
        aq_data = self._get_air_quality(location_id)

        # Build feature vector AND feature values dict
        feature_vector, feature_values = self._build_feature_vector(
            thermal_data, vuln_data, model_info.feature_version
        )

        # Generate prediction with explanation
        prediction = self._predict(
            model_id, feature_vector, location_id, "NOWCAST", feature_values=feature_values
        )

        return prediction

    def predict_forecast(
        self,
        location_id: str,
        horizon_days: int = 3,
        model_id: Optional[str] = None,
    ) -> RiskForecastOutput:
        """
        Generate forecast health risk prediction.

        Args:
            location_id: Location identifier
            horizon_days: Forecast horizon (1-5 days)
            model_id: Optional specific model to use

        Returns:
            Forecast risk predictions for each day
        """
        if model_id is None:
            model_info = self._get_production_model()
            if not model_info:
                raise ValueError("No production model available")
            model_id = model_info.model_id

        model, preprocessor = self._load_model(model_id)

        # Get forecast thermal data
        forecast_data = self._get_forecast_thermal(location_id, horizon_days)
        if not forecast_data:
            raise ValueError(f"No forecast data available for {location_id}")

        # Get vulnerability data (static)
        vuln_data = self._get_vulnerability(location_id)

        forecasts = []
        for day_data in forecast_data:
            # Build feature vector AND feature values dict
            feature_vector, feature_values = self._build_feature_vector(
                day_data, None, model_info.feature_version
            )
            pred = self._predict(
                model_id, feature_vector, location_id, "FORECAST", feature_values=feature_values
            )
            forecasts.append(pred)

        return RiskForecastOutput(
            location_id=location_id,
            prediction_time=datetime.utcnow(),
            forecasts=forecasts,
            model_id=model_id,
            model_version=model_info.model_version,
            feature_version=model_info.feature_version,
        )

    def predict_custom(
        self,
        request: RiskCalculateRequest,
        model_id: Optional[str] = None,
    ) -> RiskPredictionOutput:
        """
        Generate prediction from custom input features.

        Args:
            request: Custom prediction request
            model_id: Optional model to use

        Returns:
            Risk prediction
        """
        if model_id is None:
            model_info = self._get_production_model()
            if not model_info:
                raise ValueError("No production model available")
            model_id = model_info.model_id

        model, preprocessor = self._load_model(model_id)

        # Build feature vector AND feature values dict from request inputs
        feature_vector, feature_values = self._build_feature_vector_from_request(request)

        prediction = self._predict(
            model_id, feature_vector, request.location_id, request.source_type, feature_values=feature_values
        )

        return prediction

    def _get_production_model(self) -> Optional[Any]:
        """Get the current production model from registry."""
        from ..models.risk import RiskModelRegistry
        model = self.db.query(RiskModelRegistry).filter(
            RiskModelRegistry.status == "PRODUCTION"
        ).order_by(RiskModelRegistry.created_at.desc()).first()
        return model

    def _load_model(self, model_id: str) -> Tuple[Any, Any]:
        """Load model and preprocessor from disk."""
        from .persistence import load_model
        return load_model(model_id)

    def _get_current_thermal(self, location_id: str) -> Optional[pd.Series]:
        """Get most recent thermal observation for location."""
        thermal = self.db.query(ThermalModel).filter(
            ThermalModel.location_id == location_id
        ).order_by(ThermalModel.timestamp.desc()).first()

        if thermal:
            return thermal
        return None

    def _get_forecast_thermal(
        self,
        location_id: str,
        horizon_days: int,
    ) -> List[pd.Series]:
        """Get forecast thermal data for horizon."""
        from ..models.thermal import ThermalStressResult as ThermalModel
        from ..services.ingest import ingest_forecast

        # Get forecast thermal data
        forecast_thermal = self.db.query(ThermalModel).filter(
            ThermalModel.location_id == location_id,
            ThermalModel.source_type == "FORECAST",
        ).order_by(ThermalModel.timestamp.asc()).limit(horizon_days * 24).all()

        return list(forecast_thermal)

    def _get_vulnerability(self, location_id: str) -> Optional[pd.Series]:
        """Get latest vulnerability data for location."""
        vuln = self.db.query(VulnModel).filter(
            VulnModel.location_id == location_id
        ).order_by(VulnModel.reference_date.desc()).first()
        return vuln

    def _get_air_quality(self, location_id: str) -> Optional[pd.Series]:
        """Get latest air quality observation."""
        aq = self.db.query(AQModel).filter(
            AQModel.location_id == location_id
        ).order_by(AQModel.observed_at.desc()).first()
        return aq

    def _build_feature_vector(
        self,
        thermal_data: pd.Series,
        vulnerability_data: Optional[pd.Series],
        feature_version: str,
    ) -> np.ndarray:
        """Build feature vector from thermal and vulnerability data."""
        # Extract thermal features
        features = {}

        # Thermal indices
        thermal_features = [
            "air_temperature_c", "heat_index_c", "wet_bulb_c",
            "wbgt_c", "utci_c", "mrt_c",
            "daily_stress", "exposure_memory",
        ]

        for feat in thermal_features:
            if hasattr(thermal_data, feat):
                features[feat] = getattr(thermal_data, feat)
            else:
                features[feat] = np.nan

        # Nighttime features
        nighttime_features = [
            "nighttime_temperature_c", "nighttime_anomaly_c",
            "hot_night", "consecutive_hot_nights",
            "recovery_deficit", "recovery_hours",
        ]

        for feat in nighttime_features:
            if hasattr(thermal_data, feat):
                val = getattr(thermal_data, feat)
                if isinstance(val, bool):
                    features[feat] = float(val)
                else:
                    features[feat] = val
            else:
                features[feat] = np.nan

        # Exposure features
        exposure_features = [
            "cumulative_exposure_24h", "cumulative_exposure_72h",
            "cumulative_exposure_168h", "exposure_memory",
        ]

        for feat in exposure_features:
            if hasattr(thermal_data, feat):
                features[feat] = getattr(thermal_data, feat)
            else:
                features[feat] = np.nan

        # Vulnerability features
        if vulnerability_data is not None:
            vuln_features = [
                "elderly_population_share", "children_population_share",
                "outdoor_worker_share", "population_density_per_km2",
                "housing_vulnerability_index", "cooling_access_share",
                "electricity_reliability_index", "water_access_share",
                "healthcare_accessibility_index", "socioeconomic_vulnerability_index",
                "informal_settlement_share",
            ]

            factors = vulnerability_data.factors if hasattr(vulnerability_data, 'factors') else {}
            for feat in vulnerability_features:
                features[feat] = factors.get(feat, np.nan)

        # Convert to array in consistent order
        feature_names = sorted(features.keys())
        vector = np.array([features.get(f, np.nan) for f in feature_names])

        return vector.reshape(1, -1)

    def _build_feature_vector_from_request(
        self,
        request: RiskCalculateRequest,
    ) -> np.ndarray:
        """Build feature vector from custom request."""
        # This is a simplified version - in practice, use the feature builder
        features = {}

        for i, inp in enumerate(request.inputs):
            features[f"temperature_c"] = inp.air_temperature_c
            features[f"relative_humidity"] = inp.relative_humidity
            features[f"wind_speed_ms"] = inp.wind_speed_ms
            features[f"solar_radiation_wm2"] = inp.solar_radiation_wm2

        # Add placeholder for other features
        # In practice, use feature builder with historical data for lag/rolling

        feature_names = sorted(features.keys())
        vector = np.array([features.get(f, np.nan) for f in feature_names])

        return vector.reshape(1, -1)

    def _build_feature_vector(
        self,
        thermal_data: pd.Series,
        vulnerability_data: Optional[pd.Series],
        feature_version: str,
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """Build feature vector from thermal and vulnerability data.

        Returns:
            Tuple of (feature_vector, feature_values_dict)
        """
        # Extract thermal features
        features: Dict[str, float] = {}

        # Thermal indices
        thermal_features = [
            "air_temperature_c", "heat_index_c", "wet_bulb_c",
            "wbgt_c", "utci_c", "mrt_c",
            "daily_stress", "exposure_memory",
        ]

        for feat in thermal_features:
            if hasattr(thermal_data, feat):
                features[feat] = float(getattr(thermal_data, feat))
            else:
                features[feat] = np.nan

        # Nighttime features
        nighttime_features = [
            "nighttime_temperature_c", "nighttime_anomaly_c",
            "hot_night", "consecutive_hot_nights",
            "recovery_deficit", "recovery_hours",
        ]

        for feat in nighttime_features:
            if hasattr(thermal_data, feat):
                val = getattr(thermal_data, feat)
                if isinstance(val, bool):
                    features[feat] = float(val)
                else:
                    features[feat] = val
            else:
                features[feat] = np.nan

        # Exposure features
        exposure_features = [
            "cumulative_exposure_24h", "cumulative_exposure_72h",
            "cumulative_exposure_168h", "exposure_memory",
        ]

        for feat in exposure_features:
            if hasattr(thermal_data, feat):
                features[feat] = float(getattr(thermal_data, feat))
            else:
                features[feat] = np.nan

        # Vulnerability features
        if vulnerability_data is not None:
            vuln_features = [
                "elderly_population_share", "children_population_share",
                "outdoor_worker_share", "population_density_per_km2",
                "housing_vulnerability_index", "cooling_access_share",
                "electricity_reliability_index", "water_access_share",
                "healthcare_accessibility_index", "socioeconomic_vulnerability_index",
                "informal_settlement_share",
            ]

            factors = vulnerability_data.factors if hasattr(vulnerability_data, 'factors') else {}
            for feat in vulnerability_features:
                features[feat] = float(factors.get(feat, np.nan))

        # Convert to array in consistent order
        feature_names = sorted(features.keys())
        vector = np.array([features.get(f, np.nan) for f in feature_names])

        return vector.reshape(1, -1), features

    def _build_feature_vector_from_request(
        self,
        request: RiskCalculateRequest,
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """Build feature vector from custom request.

        Returns:
            Tuple of (feature_vector, feature_values_dict)
        """
        features: Dict[str, float] = {}

        for i, inp in enumerate(request.inputs):
            features["temperature_c"] = inp.air_temperature_c
            features["relative_humidity"] = inp.relative_humidity
            features["wind_speed_ms"] = inp.wind_speed_ms
            features["solar_radiation_wm2"] = inp.solar_radiation_wm2

        # Add placeholder for other features
        feature_names = sorted(features.keys())
        vector = np.array([features.get(f, np.nan) for f in feature_names])

        return vector.reshape(1, -1), features

    def _predict(
        self,
        model_id: str,
        feature_vector: np.ndarray,
        location_id: str,
        source_type: str,
        feature_values: Optional[Dict[str, float]] = None,
    ) -> RiskPredictionOutput:
        """Run prediction with loaded model.

        Also generates a local explanation for the prediction.
        """
        model, preprocessor = self._load_model(model_id)

        # Preprocess
        X_proc = preprocessor.transform(feature_vector)

        # Predict
        proba = model.predict_proba(feature_vector)[0, 1]

        # Determine category
        thresholds = [0.25, 0.5, 0.75]
        labels = ["LOW", "MODERATE", "HIGH", "VERY_HIGH"]
        category = "LOW"
        for i, thresh in enumerate(thresholds):
            if proba >= thresh:
                category = labels[i]

        # Data quality
        n_features = np.sum(~np.isnan(feature_vector))
        total_features = len(feature_vector)
        completeness = n_features / total_features if total_features > 0 else 0

        missing = []
        if np.isnan(feature_vector).any():
            missing = [f"feature_{i}" for i, v in enumerate(feature_vector) if np.isnan(v)]

        # Determine quality
        if completeness >= 0.95:
            quality = "BEST"
        elif completeness >= 0.8:
            quality = "GOOD"
        elif completeness >= 0.6:
            quality = "FAIR"
        else:
            quality = "POOR"

        # Use provided feature values or extract from feature vector
        if feature_values is None:
            feature_values = {}

        # Generate local explanation
        explanation = self._generate_local_explanation(
            model_id, feature_vector, feature_values, location_id, source_type
        )

        # Create prediction record
        prediction = RiskPredictionOutput(
            prediction_id=explanation["prediction_id"],
            location_id=location_id,
            latitude=None,  # Would come from location
            longitude=None,
            prediction_time=datetime.utcnow(),
            target_date=datetime.utcnow().date(),
            horizon_days=0,
            risk_probability=float(np.clip(proba, 0, 1)),
            risk_category=explanation["risk_category"],
            model_id=explanation["model_id"],
            model_version=explanation["model_version"],
            feature_version=explanation["feature_version"],
            threshold_version="1.0",
            data_completeness=completeness,
            input_quality=quality,
            missing_features=missing,
            forecast_uncertainty=explanation.get("uncertainty", {}).get("forecast_uncertainty"),
            source_type=source_type,
            in_distribution=explanation["in_distribution"],
            ood_score=explanation.get("ood_record", {}).get("ood_score") if explanation.get("ood_record") else None,
            prediction_status="SUCCESS",
            provenance=explanation["provenance"],
            # STEP 5: Explanation and uncertainty fields
            explanation_version="5.0.0",
        )

        return RiskPredictionOutput(
            prediction_id=prediction.prediction_id,
            location_id=prediction.location_id,
            latitude=prediction.latitude,
            longitude=prediction.longitude,
            prediction_time=prediction.prediction_time,
            target_date=prediction.target_date,
            horizon_days=prediction.horizon_days,
            risk_probability=prediction.risk_probability,
            risk_category=prediction.risk_category,
            model_id=prediction.model_id,
            model_version=prediction.model_version,
            feature_version=prediction.feature_version,
            threshold_version=prediction.threshold_version,
            data_completeness=prediction.data_completeness,
            input_quality=prediction.input_quality,
            missing_features=prediction.missing_features,
            forecast_uncertainty=prediction.forecast_uncertainty,
            source_type=prediction.source_type,
            in_distribution=prediction.in_distribution,
            ood_score=prediction.ood_score,
            prediction_status=prediction.prediction_status,
            error_message=prediction.error_message,
            provenance=prediction.provenance,
            created_at=prediction.created_at,
            # STEP 5: Explanation and uncertainty fields (extend schema)
            # These will be stored in the explanation table separately
        )

    def _generate_local_explanation(
        self,
        model_id: str,
        feature_vector: np.ndarray,
        feature_values: Dict[str, float],
        location_id: str,
        source_type: str,
    ) -> Dict[str, Any]:
        """Generate a local explanation for a prediction.

        Uses SHAP if available, falls back to model-native importance.
        Returns a dictionary with all explanation components.
        """
        # Get model info
        from ..models.risk import RiskModelRegistry
        model_info = (
            self.db.query(RiskModelRegistry)
            .filter(RiskModelRegistry.model_id == model_id)
            .first()
        )

        if not model_info:
            # Fallback explanation without model info
            return self._fallback_explanation(feature_vector, feature_values)

        # Load model
        model, preprocessor = self._load_model(model_id)

        # Initialize explanation service
        service = ExplanationService(
            model=model,
            feature_names=list(feature_values.keys()),
            feature_manifest=[],  # Will be populated from DB if available
            model_version=model_info.feature_version or "1.0",
            training_ranges={},  # Would be populated from training data
        )

        # Generate explanation
        result = service.explain_prediction(
            prediction_id=f"pred_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{np.random.randint(1000, 9999)}",
            feature_vector=feature_vector,
            feature_values=feature_values,
            data_quality=quality,
            in_distribution=True,
        )

        # Build output dictionary
        ood_record = result.get("ood_record")
        local_explanation = result.get("local_explanation", {})

        output = {
            "prediction_id": local_explanation.get("prediction_id", f"pred_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{np.random.randint(1000, 9999)}"),
            "risk_category": local_explanation.get("risk_category", "LOW" if local_explanation.get("risk_probability", 0) < 0.25 else "MODERATE"),
            "model_id": model_id,
            "model_version": model_info.feature_version or "1.0",
            "feature_version": model_info.feature_version or "1.0",
            "in_distribution": local_explanation.get("in_distribution", True),
            "provenance": result.get("provenance", {}),
        }

        # Add OOD info if applicable
        if ood_record:
            output["ood"] = ood_record.get("ood", False)
            output["ood_score"] = ood_record.get("ood_score")
        else:
            output["ood"] = False
            output["ood_score"] = None

        # Add top positive/negative factors
        top_pos = local_explanation.get("top_positive_factors", [])
        top_neg = local_explanation.get("top_negative_factors", [])
        output["top_positive_factors"] = top_pos
        output["top_negative_factors"] = top_neg

        # Add feature contributions
        output["feature_contributions"] = local_explanation.get("feature_contributions", {})

        return output

    def _fallback_explanation(
        self,
        feature_vector: np.ndarray,
        feature_values: Dict[str, float],
    ) -> Dict[str, Any]:
        """Fallback explanation when SHAP or model engine fails.

        Uses model-native importance only. Does not fabricate SHAP values.
        """
        contributions = {}

        if hasattr(self.model, "coef_"):
            # Linear model - use coefficients
            coefs = self.model.coef_[0] if self.model.coef_.ndim > 1 else self.model.coef_
            for i, name in enumerate(self.feature_names if hasattr(self, 'feature_names') else []):
                if i < len(coefs):
                    contributions[name] = float(coefs[i])

        elif hasattr(self.model, "feature_importances_"):
            # Tree model - use importances
            importances = self.model.feature_importances_
            for i, name in enumerate(self.feature_names if hasattr(self, 'feature_names') else []):
                if i < len(importances):
                    contributions[name] = float(importances[i])

        # Sort by absolute contribution
        sorted_items = sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)

        top_positive = [
            {"feature": name, "value": feature_values.get(name, "N/A"), "contribution": float(contributions.get(name, 0))}
            for name, _ in sorted_items
            if contributions.get(name, 0) > 0
        ][:5]

        top_negative = [
            {"feature": name, "value": feature_values.get(name, "N/A"), "contribution": float(contributions.get(name, 0))}
            for name, _ in sorted_items
            if contributions.get(name, 0) < 0
        ][:5]

        risk_probability = 0.5  # default
        if hasattr(self.model, "predict_proba"):
            try:
                risk_probability = float(
                    np.clip(self.model.predict_proba(feature_vector)[0, 1], 0, 1)
                )
            except Exception:
                pass

        return {
            "prediction_id": f"pred_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{np.random.randint(1000, 9999)}",
            "risk_category": "LOW" if risk_probability < 0.25 else "MODERATE" if risk_probability < 0.5 else "HIGH",
            "model_id": "keshav_risk_v1",
            "model_version": "1.0",
            "feature_version": "1.0",
            "in_distribution": True,
            "provenance": {
                "prediction_id": f"pred_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                "model_id": "keshav_risk_v1",
                "model_version": "1.0",
                "explanation_method": "model_native_importance",
                "explainer_version": "5.0.0-fallback",
            },
            "top_positive_factors": top_positive,
            "top_negative_factors": top_negative,
            "feature_contributions": contributions,
            "ood": False,
            "ood_score": None,
        }


def predict_health_risk(
    db: Session,
    location_id: str,
    model_id: Optional[str] = None,
    horizon_days: int = 0,
) -> Union[RiskPredictionOutput, RiskForecastOutput]:
    """Convenience function for health risk prediction."""
    predictor = RiskPredictor(db)

    if horizon_days == 0:
        return predictor.predict_current(location_id, model_id)
    else:
        return predictor.predict_forecast(location_id, horizon_days, model_id)


def generate_forecast_risk(
    db: Session,
    location_id: str,
    horizon_days: int = 3,
    model_id: Optional[str] = None,
) -> RiskForecastOutput:
    """Generate multi-day health risk forecast."""
    predictor = RiskPredictor(db)
    return predictor.predict_forecast(location_id, horizon_days, model_id)