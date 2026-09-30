"""Local explanation generation for individual KESHAV risk predictions.

Provides per-prediction explanations with:
- Baseline probability comparison
- Top positive and negative contributing factors
- Feature values and SHAP/contributions
- In-distribution and OOD status
- Explanation provenance tracking
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from ..explainability.schemas import (
    ExplanationProvenance,
    LocalExplanationOutput,
    UncertaintyRecord,
    OODRecord,
    ExplanationQualityCheck,
)


logger = logging.getLogger(__name__)


class LocalExplanationGenerator:
    """Generates local explanations for individual risk predictions.

    Takes a trained model, feature builder output, and prediction metadata,
    and produces a comprehensive local explanation.
    """

    def __init__(
        self,
        model: Any,
        feature_names: List[str],
        feature_manifest: Optional[List[Dict[str, Any]]] = None,
        model_version: str = "1.0",
    ):
        """Initialize local explanation generator.

        Args:
            model: Trained risk model (LogisticRegression or HistGradientBoosting)
            feature_names: List of feature names in prediction order
            feature_manifest: Optional feature manifest entries for validation
            model_version: Version string of the model
        """
        self.model = model
        self.feature_names = feature_names
        self.feature_manifest = feature_manifest or []
        self.model_version = model_version

        # Initialize SHAP engine if available
        try:
            from .shap_engine import SHAPEngine
            self.shap_engine = SHAPEngine(
                model,
                feature_names,
                model_type=self._detect_model_type(),
            )
        except Exception:
            logger.warning("SHAP engine initialization failed, will use fallback")
            self.shap_engine = None

    def _detect_model_type(self) -> str:
        """Detect model type for SHAP explainer selection."""
        if hasattr(self.model, "feature_importances_"):
            return "tree"
        elif hasattr(self.model, "coef_"):
            return "linear"
        return "other"

    def generate(
        self,
        prediction_id: str,
        feature_vector: np.ndarray,
        feature_values: Dict[str, float],
        data_quality: str = "GOOD",
        in_distribution: bool = True,
        ood: bool = False,
        ood_score: Optional[float] = None,
        training_ranges: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> LocalExplanationOutput:
        """Generate a local explanation for a prediction.

        Args:
            prediction_id: Unique identifier for this prediction
            feature_vector: Preprocessed feature vector (1, n_features)
            feature_values: Dictionary of feature_name -> raw value
            data_quality: Data quality category (BEST/GOOD/FAIR/POOR)
            in_distribution: Whether prediction is in-distribution
            ood: Whether out-of-distribution
            ood_score: OOD score if available
            training_ranges: Feature training ranges for OOD detection

        Returns:
            LocalExplanationOutput with complete explanation
        """
        # Get SHAP or model-native explanation
        if self.shap_engine is not None:
            shap_result = self.shap_engine.explain_prediction(
                feature_vector, feature_values
            )
        else:
            # Fallback to model-native importance
            contributions = self._compute_model_native_contributions(
                feature_vector, feature_values
            )
            shap_result = {
                "base_value": 0.5,
                "contributions": contributions,
                "top_positive_factors": self._format_factors(
                    contributions, feature_values, positive=True
                ),
                "top_negative_factors": self._format_factors(
                    contributions, feature_values, positive=False
                ),
                "explanation_method": "model_native_importance",
                "explanation_version": "5.0.0-fallback",
                "ood": ood,
                "ood_score": ood_score,
            }

        # Compute baseline probability
        baseline_prob = self._compute_baseline_probability(shap_result)

        # Compute risk probability
        risk_probability = self._compute_risk_probability(shap_result)

        # Build top factors lists
        top_positive = shap_result.get("top_positive_factors", [])
        top_negative = shap_result.get("top_negative_factors", [])

        # Quality check
        quality_check = self._validate_explanation(
            prediction_id,
            feature_values,
            shap_result,
            in_distribution,
            ood,
        )

        # Build provenance
        provenance = self._build_provenance(
            prediction_id,
            ood,
            ood_score,
        )

        # Build OOD record if applicable
        ood_record = None
        if ood:
            ood_record = self._build_ood_record(
                prediction_id,
                training_ranges,
                ood_score,
            )

        return LocalExplanationOutput(
            prediction_id=prediction_id,
            risk_probability=risk_probability,
            baseline_probability=baseline_prob,
            top_positive_factors=top_positive,
            top_negative_factors=top_negative,
            feature_values=feature_values,
            feature_contributions=shap_result.get("contributions", {}),
            model_version=self.model_version,
            feature_version=self._get_feature_version_from_manifest(),
            explanation_method=shap_result.get("explanation_method", "model_native_importance"),
            explanation_version=shap_result.get("explanation_version", "5.0.0"),
            timestamp=datetime.utcnow(),
            in_distribution=in_distribution and quality_check.valid,
            ood=ood or shap_result.get("ood", False),
            ood_score=ood_score if ood_score is not None else shap_result.get("ood_score"),
            quality_check=quality_check,
            provenance=provenance,
            ood_record=ood_record,
        )

    def _compute_baseline_probability(self, shap_result: Dict[str, Any]) -> float:
        """Compute baseline probability from SHAP explanation."""
        base_value = shap_result.get("base_value", 0.5)
        # Baseline is the expected probability without any feature influence
        return float(np.clip(base_value, 0.0, 1.0))

    def _compute_risk_probability(self, shap_result: Dict[str, Any]) -> float:
        """Compute final risk probability from SHAP explanation.

        probability = base_value + sum(positive_contributions) + sum(negative_contributions)
        clipped to [0, 1].
        """
        base_value = shap_result.get("base_value", 0.5)
        contributions = shap_result.get("contributions", {})

        total_contribution = sum(float(v) for v in contributions.values())
        probability = np.clip(base_value + total_contribution, 0.0, 1.0)
        return float(probability)

    def _format_factors(
        self,
        contributions: Dict[str, float],
        feature_values: Dict[str, float],
        positive: bool,
    ) -> List[Dict[str, Any]]:
        """Format top positive or negative factors.

        Args:
            contributions: Dictionary of feature_name -> contribution_value
            feature_values: Dictionary of feature_name -> raw_value
            positive: If True, return positive contributors; else negative

        Returns:
            List of factor dictionaries with feature, value, contribution
        """
        if not contributions:
            return []

        # Filter by sign
        if positive:
            filtered = {
                name: val
                for name, val in contributions.items()
                if val > 0
            }
        else:
            filtered = {
                name: val
                for name, val in contributions.items()
                if val < 0
            }

        # Sort by absolute contribution and take top 5
        sorted_items = sorted(filtered.items(), key=lambda x: abs(x[1]), reverse=True)[:5]

        factors = [
            {
                "feature": name,
                "value": feature_values.get(name, "N/A"),
                "contribution": float(val),
            }
            for name, val in sorted_items
        ]

        return factors

    def _compute_model_native_contributions(
        self,
        feature_vector: np.ndarray,
        feature_values: Dict[str, float],
    ) -> Dict[str, float]:
        """Compute model-native contributions when SHAP is unavailable.

        Uses model coefficients (linear) or feature importances (tree).
        Does not fabricate SHAP values.
        """
        contributions = {}

        if hasattr(self.model, "coef_"):
            # Linear model - use coefficients
            coefs = self.model.coef_[0] if self.model.coef_.ndim > 1 else self.model.coef_
            for i, name in enumerate(self.feature_names):
                # Scale contribution by feature value
                coef = float(coefs[i]) if i < len(coefs) else 0.0
                contributions[name] = coef  # raw coefficient contribution

        elif hasattr(self.model, "feature_importances_"):
            # Tree model - use importances
            importances = self.model.feature_importances_
            for i, name in enumerate(self.feature_names):
                imp = float(importances[i]) if i < len(importances) else 0.0
                # Importance is always positive; sign depends on direction
                # Use feature value * importance as contribution
                val = feature_values.get(name, 0.0)
                contributions[name] = imp * np.sign(val) if not np.isnan(val) else 0.0

        else:
            logger.warning("Model has no native contribution method")

        return contributions

    def _validate_explanation(
        self,
        prediction_id: str,
        feature_values: Dict[str, float],
        shap_result: Dict[str, Any],
        in_distribution: bool,
        ood: bool,
    ) -> ExplanationQualityCheck:
        """Validate an explanation against quality checks.

        Args:
            prediction_id: Prediction identifier
            feature_values: Input feature values
            shap_result: SHAP/explanation results
            in_distribution: Whether prediction is in-distribution
            ood: Whether out-of-distribution

        Returns:
            ExplanationQualityCheck with valid status and any errors/warnings
        """
        errors = []
        warnings = []

        # Check: all explained features exist in feature manifest
        explained_features = shap_result.get("contributions", {}).keys()
        manifest_feature_names = [
            m.get("name", "") for m in self.feature_manifest if m.get("name")
        ]
        for feat in explained_features:
            if feat not in manifest_feature_names:
                warnings.append(f"Feature '{feat}' not in feature manifest")

        # Check: feature values correspond to prediction input
        for feat_name, feat_val in feature_values.items():
            if np.isnan(feat_val) and feat_name in explained_features:
                warnings.append(f"Feature '{feat_name}' is NaN but included in explanation")

        # Check: contribution values are finite
        contributions = shap_result.get("contributions", {})
        for feat, val in contributions.items():
            if not np.isfinite(val):
                errors.append(f"Contribution value for '{feat}' is not finite: {val}")

        # Check: model version matches prediction
        # (validation happens at API level)

        # Check: explanation method matches model type
        method = shap_result.get("explanation_method", "")
        detected_type = self._detect_model_type()
        if method == "shap_tree" and detected_type != "tree":
            warnings.append(
                f"SHAP method 'shap_tree' selected but model type is '{detected_type}'"
            )

        valid = len(errors) == 0

        return ExplanationQualityCheck(
            explanation_id=prediction_id,
            valid=valid,
            errors=errors,
            warnings=warnings,
        )

    def _build_provenance(
        self,
        prediction_id: str,
        ood: bool,
        ood_score: Optional[float],
    ) -> ExplanationProvenance:
        """Build provenance tracking for the explanation.

        Makes explanation reproducible/auditable.
        """
        # Compute input feature hash for reproducibility
        import hashlib

        feature_str = "|".join(
            f"{k}={v}" for k, v in sorted(feature_values.items())
            if not np.isnan(v)
        )
        input_hash = hashlib.md5(feature_str.encode()).hexdigest()[:12] if feature_str else None

        return ExplanationProvenance(
            prediction_id=prediction_id,
            model_id=getattr(self.model, "model_id", "keshav_risk_v1") if hasattr(self, 'model') else "keshav_risk_v1",
            model_version=self.model_version,
            feature_version="1.0",
            explanation_method=self.shap_engine._get_explainer().__class__.__name__ if self.shap_engine else "model_native_importance",
            explainer_version=f"5.0.0",
            input_feature_hash=input_hash,
            dataset_version="1.0",
        )

    def _get_feature_version_from_manifest(self) -> str:
        """Get feature version from feature manifest if available."""
        if self.feature_manifest:
            # Get the most recent version
            versions = [
                m.get("version", "1.0") for m in self.feature_manifest if m.get("version")
            ]
            if versions:
                return max(versions, key=lambda v: int(v.split(".")[0]) if "." in v else v)
        return "1.0"

    def _build_ood_record(
        self,
        prediction_id: str,
        training_ranges: Optional[Dict[str, Dict[str, float]]],
        ood_score: Optional[float],
    ) -> Optional[OODRecord]:
        """Build OOD (out-of-distribution) record.

        Identifies which features are unusual compared to training data.
        """
        warning_features = []

        if training_ranges:
            for feat_name, feat_val in feature_values.items():
                if feat_name in training_ranges:
                    range_info = training_ranges[feat_name]
                    min_val = range_info.get("min", feat_val)
                    max_val = range_info.get("max", feat_val)

                    # Check if feature is outside training range
                    if feat_val < min_val or feat_val > max_val:
                        # Determine how far outside
                        if feat_val < min_val:
                            distance = min_val - feat_val
                        else:
                            distance = feat_val - max_val

                        warning_features.append(
                            {
                                "feature": feat_name,
                                "value": feat_val,
                                "training_range": [min_val, max_val],
                                "distance_from_range": distance,
                            }
                        )

        # Determine OOD message
        if warning_features:
            message = (
                f"Prediction is outside part of the model's observed training distribution. "
                f"{len(warning_features)} feature(s) outside training range."
            )
        else:
            message = None

        return OODRecord(
            prediction_id=prediction_id,
            in_distribution=not bool(ood),
            ood=bool(ood),
            ood_score=ood_score,
            warning_features=warning_features,
            training_ranges=training_ranges or {},
            message=message,
        )

    def _get_model_native_contribution_sign(
        self,
        feature_name: str,
        feature_vector: np.ndarray,
        feature_index: int,
    ) -> float:
        """Get the direction sign of a feature's contribution for tree models.

        For tree models, positive/negative direction depends on which side of
        the tree split the feature value falls.
        """
        # Simplified: return sign based on whether value is above/below median
        if feature_index < len(feature_vector):
            val = feature_vector[feature_index]
            if not np.isnan(val):
                return 1.0 if val > 0 else -1.0
        return 0.0