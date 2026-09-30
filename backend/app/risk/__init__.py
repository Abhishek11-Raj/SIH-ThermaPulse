"""KESHAV Health Risk Prediction Engine — STEP 4.

This module provides the health risk prediction layer on top of
the thermal stress foundation (Step 3) and data integration layer (Step 2).

Components:
- Feature engineering from thermal, vulnerability, air quality, and health data
- Target definition from health outcomes
- Time-aware train/validation/test splits with leakage prevention
- Baseline (Logistic Regression) and ML (HistGradientBoosting) models
- Probability calibration (Platt/Isotonic)
- Model registry with versioning and promotion
- Prediction APIs for current and forecast risk
- Comprehensive evaluation (ROC-AUC, PR-AUC, POD, FAR, CSI, calibration)
- Synthetic data generation for deterministic testing

All components are designed for production use with:
- Leakage prevention (temporal and spatial)
- Data quality propagation
- Provenance tracking
- Model versioning and artifact persistence
- Deterministic synthetic data for testing
"""

from __future__ import annotations

from . import (
    calibration,
    dataset,
    evaluation,
    features,
    models,
    prediction,
    preprocessing,
    registry,
    schemas,
    service,
    targets,
    training,
)

__all__ = [
    "calibration",
    "dataset",
    "evaluation",
    "features",
    "models",
    "prediction",
    "preprocessing",
    "registry",
    "schemas",
    "service",
    "targets",
    "training",
]