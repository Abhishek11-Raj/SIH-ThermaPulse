"""Risk feature preprocessing — STEP 4.

Handles feature scaling, encoding, imputation, and data quality checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import StandardScaler, RobustScaler, LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from .schemas import RiskFeatureConfig, RiskModelConfig


@dataclass
class PreprocessingArtifacts:
    """Artifacts from preprocessing for later use on new data."""
    feature_names: List[str]
    scaler: Any
    imputer: Any
    feature_types: Dict[str, str]
    fitted: bool = False


class RiskPreprocessor:
    """Preprocesses risk features for training and prediction."""

    def __init__(self, config: RiskFeatureConfig, model_config: RiskModelConfig):
        self.feature_config = config
        self.model_config = model_config
        self.artifacts: Optional[PreprocessingArtifacts] = None
        self._pipeline: Optional[Pipeline] = None

    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> "RiskPreprocessor":
        """Fit preprocessing pipeline on training data."""
        # Identify feature types
        self.feature_types = self._infer_feature_types(X)

        # Build preprocessing pipeline
        self._build_pipeline(X, self.feature_types)

        # Fit pipeline
        self._pipeline.fit(X)

        # Store artifacts
        self.artifacts = PreprocessingArtifacts(
            feature_names=list(X.columns),
            scaler=self._pipeline.named_steps.get("scaler"),
            imputer=self._pipeline.named_steps.get("imputer"),
            feature_types=self.feature_types,
            fitted=True,
        )

        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        """Transform features using fitted pipeline."""
        if self._pipeline is None:
            raise RuntimeError("Preprocessor not fitted. Call fit() first.")

        # Ensure columns match
        X = X.reindex(columns=self.artifacts.feature_names, fill_value=np.nan)

        # Transform
        X_transformed = self._pipeline.transform(X)

        return X_transformed

    def fit_transform(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> np.ndarray:
        """Fit and transform in one step."""
        return self.fit(X, y).transform(X)

    def _infer_feature_types(self, X: pd.DataFrame) -> Dict[str, str]:
        """Infer feature types for appropriate preprocessing."""
        types = {}
        for col in X.columns:
            if X[col].dtype in ["object", "category"]:
                types[col] = "categorical"
            elif X[col].dtype in ["int64", "int32", "float64", "float32"]:
                # Check if binary
                unique = X[col].nunique()
                if unique <= 2:
                    types[col] = "binary"
                else:
                    types[col] = "numeric"
            elif np.issubdtype(X[col].dtype, np.datetime64):
                types[col] = "datetime"
            else:
                types[col] = "unknown"
        return types

    def _build_pipeline(self, X: pd.DataFrame, feature_types: Dict[str, str]) -> None:
        """Build sklearn preprocessing pipeline."""
        # Identify column groups
        numeric_cols = [c for c, t in self.feature_types.items() if t in ["numeric", "binary"]]
        categorical_cols = [c for c, t in self.feature_types.items() if t == "categorical"]

        # Build transformers
        transformers = []

        if numeric_cols:
            # Use RobustScaler for thermal features (outlier resistant)
            numeric_transformer = Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", RobustScaler()),
            ])
            transformers.append(("numeric", numeric_transformer, numeric_cols))

        if categorical_cols:
            cat_transformer = Pipeline([
                ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
                ("encoder", LabelEncoder()),  # Will need custom handling
            ])
            transformers.append(("categorical", cat_transformer, categorical_cols))

        # Build column transformer
        preprocessor = ColumnTransformer(
            transformers=transformers,
            remainder="drop",  # Drop columns not specified
            sparse_threshold=0,
        )

        # Full pipeline
        self._pipeline = Pipeline([
            ("preprocessor", preprocessor),
        ])

    def save_artifacts(self, path: str) -> None:
        """Save preprocessing artifacts to disk."""
        import joblib
        if self.artifacts is None:
            raise RuntimeError("No artifacts to save. Call fit() first.")
        joblib.dump(self.artifacts, path)

    def load_artifacts(self, path: str) -> None:
        """Load preprocessing artifacts from disk."""
        import joblib
        self.artifacts = joblib.load(path)
        # Rebuild pipeline from artifacts
        self._rebuild_pipeline_from_artifacts()

    def _rebuild_pipeline_from_artifacts(self) -> None:
        """Rebuild pipeline from saved artifacts."""
        if self.artifacts is None:
            raise RuntimeError("No artifacts loaded")

        # Rebuild minimal pipeline
        self._pipeline = Pipeline([
            ("preprocessor", self.artifacts.imputer),  # Simplified
        ])
        self._pipeline.named_steps["preprocessor"] = self.artifacts.scaler


class RiskFeatureSelector:
    """Selects most important features for risk prediction."""

    def __init__(
        self,
        max_features: Optional[int] = None,
        min_importance: float = 0.0,
        method: str = "importance",
    ):
        self.max_features = max_features
        self.min_importance = min_importance
        self.method = method
        self.selected_features_: Optional[List[str]] = None
        self.importances_: Optional[Dict[str, float]] = None

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        feature_names: Optional[List[str]] = None,
    ) -> "RiskFeatureSelector":
        """Fit feature selector using model-based importance."""
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.feature_selection import SelectFromModel

        if self.method == "importance":
            # Train a quick model to get feature importances
            model = HistGradientBoostingClassifier(
                max_iter=100,
                random_state=42,
                class_weight="balanced",
            )
            model.fit(X, y)

            importances = dict(zip(X.columns, model.feature_importances_))
            self.importances_ = importances

            # Select features above threshold
            selector = SelectFromModel(
                model,
                threshold=self.min_importance,
                max_features=self.max_features,
            )
            selector.fit(X, y)

            self.selected_features_ = X.columns[selector.get_support()].tolist()

        elif self.method == "variance":
            from sklearn.feature_selection import VarianceThreshold
            selector = VarianceThreshold(threshold=self.min_importance)
            selector.fit(X)
            self.selected_features_ = X.columns[selector.get_support()].tolist()

        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if self.selected_features_ is None:
            raise RuntimeError("Feature selector not fitted")
        return X[self.selected_features_]

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        return self.fit(X, y).transform(X)


def create_preprocessing_pipeline(
    config: RiskFeatureConfig,
    model_config: RiskModelConfig,
) -> RiskPreprocessor:
    """Create a preprocessing pipeline from config."""
    return RiskPreprocessor(config, model_config)


def validate_data_quality(
    X: pd.DataFrame,
    y: Optional[pd.Series] = None,
    config: Optional[RiskFeatureConfig] = None,
) -> Dict[str, Any]:
    """
    Validate data quality for risk modeling.

    Returns a dictionary with quality metrics and flags.
    """
    issues = []
    warnings = []
    metrics = {}

    # Check for missing values
    missing_pct = X.isnull().mean()
    high_missing = missing_pct[missing_pct > 0.5].index.tolist()
    if high_missing:
        warnings.append(f"Features with >50% missing: {high_missing}")

    metrics["missing_percentage"] = missing_pct.to_dict()

    # Check for constant features
    nunique = X.nunique()
    constant = nunique[nunique <= 1].index.tolist()
    if constant:
        warnings.append(f"Constant features: {constant}")

    metrics["nunique"] = nunique.to_dict()

    # Check for extreme values
    numeric_cols = X.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        q1 = X[col].quantile(0.25)
        q3 = X[col].quantile(0.75)
        iqr = q3 - q1
        outliers = ((X[col] < q1 - 3 * (q3 - q1)) | (X[col] > q3 + 3 * (q3 - q1))).sum()
        if outliers > len(X) * 0.05:
            warnings.append(f"Feature {col} has {outliers} extreme outliers")

    # Check target if provided
    if y is not None:
        target_balance = pd.Series(y).value_counts(normalize=True)
        min_class_pct = target_balance.min()
        if min_class_pct < 0.01:
            warnings.append(f"Severe class imbalance: minority class {min_class_pct:.2%}")

    return {
        "issues": issues,
        "warnings": warnings,
        "metrics": metrics,
        "passed": len(issues) == 0,
    }