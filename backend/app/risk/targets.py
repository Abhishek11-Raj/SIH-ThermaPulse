"""Risk target definition and construction — STEP 4.

Defines health risk targets and builds target variables from health outcomes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..schemas.health import HealthOutcome
from .schemas import (
    HealthRiskTarget,
    RiskFeatureConfig,
    RiskModelConfig,
)


class TargetBuilder:
    """Builds health risk targets from health outcome data."""

    def __init__(self, target_config: HealthRiskTarget):
        self.config = target_config

    def build_binary_target(
        self,
        health_data: pd.DataFrame,
        thermal_data: pd.DataFrame,
        threshold: Optional[float] = None,
    ) -> pd.Series:
        """
        Build binary target: did a heat health event occur?

        Args:
            health_data: Health outcome data (daily aggregates)
            thermal_data: Thermal stress data (for alignment)
            threshold: Minimum cases to consider positive (default: 1)

        Returns:
            Binary target series aligned to thermal data timestamps
        """
        threshold = threshold or self.config.positive_threshold or 1.0

        # Prepare health data
        health_df = self._prepare_health_data(health_data)

        # Align to thermal data timestamps
        thermal_df = thermal_data[["location_id", "timestamp"]].copy()
        thermal_df = thermal_df.sort_values(["location_id", "timestamp"])

        # Merge health outcomes onto thermal timestamps
        health_df = health_df.sort_values(["location_id", "period_start"])
        merged = pd.merge_asof(
            thermal_df.sort_values("timestamp"),
            health_df.rename(columns={"period_start": "timestamp"}).sort_values("timestamp"),
            on="timestamp",
            by="location_id",
            direction="backward"
        )

        # Define positive case
        if self.config.target_type == "binary":
            if self.config.positive_definition:
                # Custom definition
                # Could be extended for complex definitions
                positive = (merged["heat_illness_cases"] >= threshold).astype(int)
            else:
                positive = (merged["heat_illness_cases"] >= threshold).astype(int)
        else:
            positive = (merged["heat_illness_cases"] >= threshold).astype(int)

        return positive

    def build_count_target(
        self,
        health_data: pd.DataFrame,
        thermal_data: pd.DataFrame,
    ) -> pd.Series:
        """Build count target: number of heat illness cases."""
        health_df = self._prepare_health_data(health_data)

        thermal_df = thermal_data[["location_id", "timestamp"]].copy()
        thermal_df = thermal_df.sort_values(["location_id", "timestamp"])

        health_df = health_df.sort_values(["location_id", "period_start"])
        merged = pd.merge_asof(
            thermal_df.sort_values("timestamp"),
            health_df.rename(columns={"period_start": "timestamp"}).sort_values("timestamp"),
            on="timestamp",
            by="location_id",
            direction="backward"
        )

        return merged["heat_illness_cases"].fillna(0).astype(int)

    def build_rate_target(
        self,
        health_data: pd.DataFrame,
        thermal_data: pd.DataFrame,
        population_data: Optional[pd.DataFrame] = None,
    ) -> pd.Series:
        """Build rate target: cases per population."""
        health_df = self._prepare_health_data(health_data)

        thermal_df = thermal_data[["location_id", "timestamp"]].copy()
        thermal_df = thermal_df.sort_values(["location_id", "timestamp"])

        health_df = health_df.sort_values(["location_id", "period_start"])
        merged = pd.merge_asof(
            thermal_df.sort_values("timestamp"),
            health_df.rename(columns={"period_start": "timestamp"}).sort_values("timestamp"),
            on="timestamp",
            by="location_id",
            direction="backward"
        )

        if population_data is not None:
            pop_df = population_data.rename(columns={"date": "timestamp"})
            pop_df = pop_df.sort_values(["location_id", "timestamp"])
            merged = pd.merge_asof(
                merged.sort_values("timestamp"),
                pop_df.sort_values("timestamp"),
                on="timestamp",
                by="location_id",
                direction="backward"
            )
            rate = merged["heat_illness_cases"] / merged["population"] * 100000
            return rate.fillna(0)
        else:
            # Return count if no population data
            return merged["heat_illness_cases"].fillna(0)

    def _prepare_health_data(self, health_data: pd.DataFrame) -> pd.DataFrame:
        """Prepare and validate health outcome data."""
        df = health_data.copy()

        # Ensure required columns
        required = ["location_id", "period_start", "heat_illness_cases"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Health data missing required column: {col}")

        # Ensure datetime
        df["period_start"] = pd.to_datetime(df["period_start"], utc=True)
        if "period_end" in df.columns:
            df["period_end"] = pd.to_datetime(df["period_end"], utc=True)

        # Fill missing cases with 0
        df["heat_illness_cases"] = df["heat_illness_cases"].fillna(0).astype(int)

        # Sort
        df = df.sort_values(["location_id", "period_start"]).reset_index(drop=True)

        return df

    def create_target_from_outcomes(
        self,
        health_outcomes: List[HealthOutcome],
        thermal_data: pd.DataFrame,
    ) -> pd.Series:
        """Create target from HealthOutcome schema objects."""
        if not health_outcomes:
            return pd.Series(0, index=thermal_data.index)

        # Convert to DataFrame
        records = []
        for o in health_outcomes:
            records.append({
                "location_id": o.location_id,
                "period_start": o.period_start,
                "period_end": o.period_end,
                "heat_illness_cases": o.heat_illness_cases or 0,
                "emergency_visits": o.emergency_visits or 0,
                "hospital_admissions": o.hospital_admissions or 0,
                "respiratory_admissions": o.respiratory_admissions or 0,
                "cardiovascular_admissions": o.cardiovascular_admissions or 0,
                "mortality_count": o.mortality_count,
            })
        health_df = pd.DataFrame(records)

        if self.config.target_type == "binary":
            return self.build_binary_target(health_df, thermal_data)
        elif self.config.target_type == "count":
            return self.build_count_target(health_df, thermal_data)
        elif self.config.target_type == "rate":
            return self.build_rate_target(health_df, thermal_data)
        else:
            raise ValueError(f"Unknown target type: {self.config.target_type}")


def create_default_target_config() -> HealthRiskTarget:
    """Create default binary heat-health event target."""
    return HealthRiskTarget(
        target_name="heat_health_event",
        target_type="binary",
        description="Binary indicator: did any heat-related health event occur in the 24h period?",
        positive_threshold=1.0,
        positive_definition="heat_illness_cases >= 1",
        outcome_window_days=1,
    )


def create_count_target_config() -> HealthRiskTarget:
    """Create count target config."""
    return HealthRiskTarget(
        target_name="heat_illness_count",
        target_type="count",
        description="Number of heat-related illness cases",
        outcome_window_days=1,
    )


def create_rate_target_config(population_field: str = "population") -> HealthRiskTarget:
    """Create rate target config."""
    return HealthRiskTarget(
        target_name="heat_illness_rate",
        target_type="rate",
        description="Heat illness cases per 100k population",
        population_normalization="per_100k",
        population_field=population_field,
        outcome_window_days=1,
    )