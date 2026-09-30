"""Risk feature engineering — STEP 4.

Builds feature vectors from thermal, vulnerability, air quality,
and health data for health risk prediction.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..core.enums import QualityFlag
from ..schemas.weather import WeatherObservation
from ..schemas.forecast import WeatherForecast
from ..schemas.air_quality import AirQualityObservation
from ..schemas.health import HealthOutcome
from ..schemas.vulnerability import VulnerabilityRecord
from .schemas import (
    RiskFeatureConfig,
    FeatureManifestEntry,
    HealthRiskTarget,
    RiskModelConfig,
)


class FeatureManifest:
    """Manages the feature manifest for leakage auditing."""

    def __init__(self, config: RiskFeatureConfig):
        self.config = config
        self._manifest: List[FeatureManifestEntry] = []
        self._build_manifest()

    def _build_manifest(self) -> None:
        """Build the complete feature manifest from config."""
        # Thermal indices (current)
        for feat in self.config.thermal_indices:
            self._manifest.append(FeatureManifestEntry(
                name=feat,
                source="thermal",
                unit="celsius" if "temperature" in feat or "index" in feat else "unitless",
                time_window="current",
                lag=None,
                allowed_at_prediction_time=True,
                missing_policy="impute",
                imputation_policy=self.config.imputation_policy,
                derivation="thermal_index"
            ))

        # Nighttime features
        for feat in self.config.nighttime_features:
            self._manifest.append(FeatureManifestEntry(
                name=feat,
                source="thermal",
                unit="celsius" if "temperature" in feat or "anomaly" in feat else "unitless",
                time_window="nighttime",
                lag=None,
                allowed_at_prediction_time=True,
                missing_policy="impute",
                imputation_policy=self.config.imputation_policy,
                derivation="nighttime_analysis"
            ))

        # Exposure features
        for feat in self.config.exposure_features:
            self._manifest.append(FeatureManifestEntry(
                name=feat,
                source="thermal",
                unit="unitless",
                time_window="cumulative",
                lag=None,
                allowed_at_prediction_time=True,
                missing_policy="impute",
                imputation_policy=self.config.imputation_policy,
                derivation="exposure_memory"
            ))

        # Vulnerability features
        for feat in self.config.vulnerability_features:
            self._manifest.append(FeatureManifestEntry(
                name=feat,
                source="vulnerability",
                unit="proportion" if "share" in feat else "index",
                time_window="reference_date",
                lag=None,
                allowed_at_prediction_time=True,
                missing_policy="impute",
                imputation_policy=self.config.imputation_policy,
                derivation="vulnerability_data"
            ))

        # Air quality features
        for feat in self.config.air_quality_features:
            self._manifest.append(FeatureManifestEntry(
                name=feat,
                source="air_quality",
                unit="ugm3" if "ugm3" in feat else "mgm3" if "mgm3" in feat else "index",
                time_window="current",
                lag=None,
                allowed_at_prediction_time=True,
                missing_policy="impute",
                imputation_policy=self.config.imputation_policy,
                derivation="air_quality_observation"
            ))

        # Lag features
        for base_feat in self.config.lag_features:
            for lag in self.config.lag_hours:
                self._manifest.append(FeatureManifestEntry(
                    name=f"{base_feat}_lag_{lag}h",
                    source="thermal",
                    unit="celsius" if "c" in base_feat else "unitless",
                    time_window=f"lag_{lag}h",
                    lag=lag,
                    allowed_at_prediction_time=True,
                    missing_policy="impute",
                    imputation_policy=self.config.imputation_policy,
                    derivation=f"lag_{lag}h({base_feat})"
                ))

        # Rolling window features
        for base_feat in self.config.rolling_features:
            for window in self.config.rolling_windows_hours:
                for stat in ["mean", "max", "min", "std"]:
                    self._manifest.append(FeatureManifestEntry(
                        name=f"{base_feat}_rolling_{window}h_{stat}",
                        source="thermal",
                        unit="celsius" if "c" in base_feat else "unitless",
                        time_window=f"rolling_{window}h",
                        lag=None,
                        allowed_at_prediction_time=True,
                        missing_policy="impute",
                        imputation_policy=self.config.imputation_policy,
                        derivation=f"rolling_{window}h_{stat}({base_feat})"
                    ))

    def to_list(self) -> List[Dict[str, Any]]:
        return [m.model_dump() for m in self._manifest]

    def get_feature_names(self) -> List[str]:
        return [m.name for m in self._manifest]

    def get_allowed_at_prediction(self) -> List[str]:
        return [m.name for m in self._manifest if m.allowed_at_prediction_time]


class RiskFeatureBuilder:
    """Builds feature matrices for risk prediction from raw data."""

    def __init__(self, config: RiskFeatureConfig):
        self.config = config
        self.manifest = FeatureManifest(config)

    def build_features(
        self,
        thermal_data: pd.DataFrame,
        vulnerability_data: Optional[pd.DataFrame] = None,
        air_quality_data: Optional[pd.DataFrame] = None,
        health_data: Optional[pd.DataFrame] = None,
        target_config: Optional[HealthRiskTarget] = None,
        prediction_time: Optional[datetime] = None,
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Build feature matrix and target vector.

        Args:
            thermal_data: DataFrame with thermal stress results (from Step 3)
            vulnerability_data: DataFrame with vulnerability data
            air_quality_data: DataFrame with air quality data
            health_data: DataFrame with health outcomes (for target)
            target_config: Target configuration
            prediction_time: If set, only use data available up to this time (leakage prevention)

        Returns:
            (X, y) feature matrix and target vector
        """
        # Filter by prediction time if provided (leakage prevention)
        if prediction_time is not None:
            thermal_data = thermal_data[thermal_data["timestamp"] <= prediction_time]
            if vulnerability_data is not None:
                vulnerability_data = vulnerability_data[vulnerability_data["reference_date"] <= prediction_time]
            if air_quality_data is not None:
                air_quality_data = air_quality_data[air_quality_data["observed_at"] <= prediction_time]

        # Start with thermal data as base (must have timestamp and location_id)
        df = thermal_data.copy()
        df = df.sort_values(["location_id", "timestamp"]).reset_index(drop=True)

        # Merge vulnerability data
        if vulnerability_data is not None and not vulnerability_data.empty:
            vuln_df = vulnerability_data.copy()
            vuln_df = vuln_df.rename(columns={"reference_date": "timestamp"})
            vuln_df = vuln_df.sort_values(["location_id", "timestamp"])
            # Forward fill vulnerability data (slowly changing)
            vuln_df = vuln_df.groupby("location_id").apply(
                lambda g: g.set_index("timestamp").resample("1H").ffill().reset_index()
            ).reset_index(drop=True)
            df = pd.merge_asof(
                df.sort_values("timestamp"),
                vuln_df.sort_values("timestamp"),
                on="timestamp",
                by="location_id",
                direction="backward"
            )

        # Merge air quality data
        if air_quality_data is not None and not air_quality_data.empty:
            aq_df = air_quality_data.copy()
            aq_df = aq_df.sort_values(["location_id", "observed_at"])
            df = pd.merge_asof(
                df.sort_values("timestamp"),
                aq_df.rename(columns={"observed_at": "timestamp"}).sort_values("timestamp"),
                on="timestamp",
                by="location_id",
                direction="backward"
            )

        # Build target if health data provided
        y = None
        if health_data is not None and not health_data.empty and target_config:
            y = self._build_target(df, health_data, target_config)

        # Build lag features
        df = self._build_lag_features(df)

        # Build rolling features
        df = self._build_rolling_features(df)

        # Build nighttime features (from thermal daily summary if available)
        # This would typically come from a separate nighttime analysis table

        # Handle missing values
        df = self._handle_missing(df)

        # Select feature columns
        feature_cols = self.manifest.get_allowed_at_prediction()
        # Only keep columns that exist in the dataframe
        available_cols = [c for c in feature_cols if c in df.columns]

        X = df[available_cols].copy()
        # Ensure feature columns are numeric
        for col in X.columns:
            try:
                X[col] = pd.to_numeric(X[col], errors="coerce")
            except (TypeError, ValueError):
                # If conversion fails, fill with NaN
                X[col] = np.nan

        return X, y

    def _build_target(
        self,
        df: pd.DataFrame,
        health_data: pd.DataFrame,
        target_config: HealthRiskTarget,
    ) -> pd.Series:
        """Build target variable from health outcomes."""
        # Merge health data
        health_df = health_data.copy()
        health_df = health_df.sort_values(["location_id", "period_start"])

        # For daily aggregation, align to daily frequency
        df_daily = df.set_index("timestamp").groupby("location_id").resample("1D").last().reset_index()

        # Merge with health outcomes
        merged = pd.merge_asof(
            df_daily.sort_values("timestamp"),
            health_df.rename(columns={"period_start": "timestamp"}).sort_values("timestamp"),
            on="timestamp",
            by="location_id",
            direction="backward"
        )

        # Define target based on target_type
        if target_config.target_type == "binary":
            if target_config.positive_threshold is not None:
                # Use threshold on heat_illness_cases
                merged["target"] = (merged["heat_illness_cases"] >= target_config.positive_threshold).astype(int)
            else:
                # Default: any heat illness case
                merged["target"] = (merged["heat_illness_cases"] > 0).astype(int)
        elif target_config.target_type == "count":
            merged["target"] = merged["heat_illness_cases"].fillna(0).astype(int)
        elif target_config.target_type == "rate":
            # Rate per 100k population (would need population data)
            merged["target"] = merged["heat_illness_cases"].fillna(0).astype(float)
        else:
            merged["target"] = 0

        # Align back to original dataframe
        target_series = merged.set_index(["location_id", "timestamp"])["target"]
        df_index = df.set_index(["location_id", "timestamp"])
        y = df_index.index.map(target_series).fillna(0).astype(int)

        return y

    def _build_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create lag features for specified base features."""
        lag_features = self.config.lag_features
        lag_hours = self.config.lag_hours

        for feat in lag_features:
            if feat not in df.columns:
                continue
            for lag in lag_hours:
                lag_col = f"{feat}_lag_{lag}h"
                df[lag_col] = df.groupby("location_id")[feat].shift(lag)

        return df

    def _build_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create rolling window features."""
        rolling_features = self.config.rolling_features
        windows = self.config.rolling_windows_hours
        stats = ["mean", "max", "min", "std"]

        for feat in rolling_features:
            if feat not in df.columns:
                continue
            for window in self.config.rolling_windows_hours:
                for stat in stats:
                    col_name = f"{feat}_rolling_{window}h_{stat}"
                    if stat == "mean":
                        df[col_name] = df.groupby("location_id")[feat].rolling(
                            window, min_periods=1
                        ).mean().reset_index(level=0, drop=True)
                    elif stat == "max":
                        df[col_name] = df.groupby("location_id")[feat].rolling(
                            window, min_periods=1
                        ).max().reset_index(level=0, drop=True)
                    elif stat == "min":
                        df[col_name] = df.groupby("location_id")[feat].rolling(
                            window, min_periods=1
                        ).min().reset_index(level=0, drop=True)
                    elif stat == "std":
                        df[col_name] = df.groupby("location_id")[feat].rolling(
                            window, min_periods=2
                        ).std().reset_index(level=0, drop=True)

        return df

    def _handle_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values according to imputation policy."""
        policy = self.config.imputation_policy

        if policy == "none":
            return df

        numeric_cols = df.select_dtypes(include=[np.number]).columns

        if policy == "forward_fill":
            df[numeric_cols] = df.groupby("location_id")[numeric_cols].ffill()
            df[numeric_cols] = df[numeric_cols].fillna(0)
        elif policy == "interpolate":
            df[numeric_cols] = df.groupby("location_id")[numeric_cols].apply(
                lambda g: g.interpolate(method="time", limit_direction="both")
            )
            df[numeric_cols] = df[numeric_cols].fillna(0)
        elif policy == "historical_mean":
            # Use global mean per feature
            for col in numeric_cols:
                mean_val = df[col].mean()
                df[col] = df[col].fillna(mean_val if not np.isnan(mean_val) else 0)

        return df

    def build_feature_vector(
        self,
        thermal_obs: pd.Series,
        vulnerability_data: Optional[pd.Series] = None,
        air_quality_data: Optional[pd.Series] = None,
        historical_thermal: Optional[pd.DataFrame] = None,
        prediction_time: Optional[datetime] = None,
    ) -> np.ndarray:
        """
        Build a single feature vector for prediction.

        Args:
            thermal_obs: Single thermal observation (from current/latest data)
            vulnerability_data: Current vulnerability data for location
            air_quality_data: Current air quality data
            historical_thermal: Historical thermal data for lag/rolling features
            prediction_time: Time of prediction (for leakage prevention)

        Returns:
            Feature vector as numpy array
        """
        # Build a mini dataframe from current observations
        current_data = thermal_obs.to_dict()
        current_data["timestamp"] = thermal_obs.get("timestamp", datetime.utcnow())
        current_data["location_id"] = thermal_obs.get("location_id", "unknown")

        df = pd.DataFrame([current_data])

        if vulnerability_data is not None:
            for k, v in vulnerability_data.items():
                df[k] = v

        if air_quality_data is not None:
            for k, v in air_quality_data.items():
                df[k] = v

        # If we have historical data, compute lag/rolling features
        if historical_thermal is not None and not historical_thermal.empty:
            # Filter by prediction time if provided
            if prediction_time is not None:
                historical_thermal = historical_thermal[historical_thermal["timestamp"] <= prediction_time]

            # Combine historical with current
            combined = pd.concat([historical_thermal, df], ignore_index=True)
            combined = combined.sort_values(["location_id", "timestamp"]).reset_index(drop=True)

            # Build lag and rolling features on combined
            combined = self._build_lag_features(combined)
            combined = self._build_rolling_features(combined)

            # Take the last row (current prediction)
            df = combined.tail(1).copy()
        else:
            # No historical data - fill lag/rolling with NaN
            for feat in self.config.lag_features:
                for lag in self.config.lag_hours:
                    df[f"{feat}_lag_{lag}h"] = np.nan
            for feat in self.config.rolling_features:
                for window in self.config.rolling_windows_hours:
                    for stat in ["mean", "max", "min", "std"]:
                        df[f"{feat}_rolling_{feat}_{stat}"] = np.nan

        # Handle missing
        df = self._handle_missing(df)

        # Select features
        feature_cols = self.manifest.get_allowed_at_prediction()
        available_cols = [c for c in self.manifest.get_feature_names() if c in df.columns]

        # Ensure all feature columns exist
        for col in feature_cols:
            if col not in df.columns:
                df[col] = np.nan

        X = df[feature_cols].copy()
        for col in X.columns:
            try:
                X[col] = pd.to_numeric(X[col], errors="coerce")
            except (TypeError, ValueError):
                # If conversion fails, fill with NaN
                X[col] = np.nan

        return X.values.reshape(1, -1)

    def get_feature_manifest(self) -> List[Dict[str, Any]]:
        return self.manifest.to_list()


def build_risk_features(
    thermal_data: pd.DataFrame,
    vulnerability_data: Optional[pd.DataFrame] = None,
    air_quality_data: Optional[pd.DataFrame] = None,
    health_data: Optional[pd.DataFrame] = None,
    config: Optional[RiskFeatureConfig] = None,
    target_config: Optional[HealthRiskTarget] = None,
    prediction_time: Optional[datetime] = None,
) -> Tuple[pd.DataFrame, Optional[pd.Series], FeatureManifest]:
    """Convenience function to build risk features."""
    config = config or RiskFeatureConfig()
    builder = RiskFeatureBuilder(config)
    X, y = builder.build_features(
        thermal_data, vulnerability_data, air_quality_data, None,
        target_config=target_config, prediction_time=prediction_time
    )
    return X, builder.manifest.get_feature_names()


def create_feature_manifest(config: RiskFeatureConfig) -> List[Dict[str, Any]]:
    """Create feature manifest from config."""
    manifest = FeatureManifest(config)
    return manifest.to_list()