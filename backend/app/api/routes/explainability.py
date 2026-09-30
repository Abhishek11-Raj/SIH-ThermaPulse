"""KESHAV STEP 5: Explanation, Uncertainty, and Equity API Endpoints.

Provides REST endpoints for:
- Prediction explainability (local SHAP/model-native explanations)
- Global feature importance
- Uncertainty estimation
- Out-of-distribution detection
- Equity/fairness auditing
- Data coverage auditing
- Model audit records
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...explainability.explanation_service import ExplanationService
from ...explainability.schemas import (
    ExplanationQualityCheck,
    UncertaintyRecord,
    OODRecord,
    EquityAuditRecord,
    CalibrationDiagnostics,
    ExplanationProvenance,
)
from ...risk.schemas import (
    RiskPredictionOutput,
    RiskModelRegistryOutput,
    RiskEvaluationOutput,
)
from ...models.risk import RiskModelRegistry, RiskPrediction, RiskExplanation, FeatureImportanceSnapshot, UncertaintyRecordDB, OODRecordDB, EquityAuditDB, CalibrationDiagnosticsDB


router = APIRouter(prefix="/api/v1/explainability", tags=["explainability"])


@router.get("/prediction/{prediction_id}", response_model=Dict[str, Any])
def get_prediction_explanation(
    prediction_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Get local explanation for a specific prediction.

    Returns:
        - Risk probability and baseline comparison
        - Top positive and negative contributing factors
        - Feature values and contributions
        - In-distribution and OOD status
        - Explanation quality validation
    """
    # Query the prediction
    prediction = db.query(RiskPrediction).filter(RiskPrediction.prediction_id == prediction_id).first()
    if not prediction:
        raise HTTPException(status_code=404, detail=f"Prediction {prediction_id} not found")

    # Query the explanation
    explanation = db.query(RiskExplanation).filter(RiskExplanation.prediction_id == prediction_id).first()
    if not explanation:
        raise HTTPException(status_code=404, detail=f"Explanation {prediction_id} not found")

    # Build response
    result = {
        "prediction_id": explanation.prediction_id,
        "risk_probability": explanation.risk_probability,
        "baseline_probability": explanation.baseline_probability,
        "risk_category": explanation.risk_category,
        "top_positive_factors": explanation.top_positive_factors,
        "top_negative_factors": explanation.top_negative_factors,
        "feature_values": explanation.feature_values,
        "feature_contributions": explanation.feature_contributions,
        "model_version": explanation.model_version,
        "feature_version": explanation.feature_version,
        "explanation_method": explanation.explanation_method,
        "explanation_version": explanation.explanation_version,
        "timestamp": explanation.created_at.isoformat() if explanation.created_at else None,
        "in_distribution": explanation.in_distribution,
        "ood": explanation.ood,
        "ood_score": explanation.ood_score,
    }

    # Add quality check if available
    if explanation.quality_errors or explanation.quality_warnings:
        result["quality_check"] = {
            "valid": explanation.quality_valid,
            "errors": explanation.quality_errors,
            "warnings": explanation.quality_warnings,
        }

    # Add provenance
    provenance = explanation.provenance_json
    if isinstance(provenance, dict):
        result["provenance"] = {
            "prediction_id": provenance.get("prediction_id"),
            "model_id": provenance.get("model_id"),
            "model_version": provenance.get("model_version"),
            "explanation_method": provenance.get("explanation_method"),
            "input_feature_hash": provenance.get("input_feature_hash"),
        }

    return result


@router.get("/global/{model_id}", response_model=Dict[str, Any])
def get_global_explanation(
    model_id: str,
    db: Session = Depends(get_db),
    method: Literal["shap", "permutation", "model_native"] = "model_native",
) -> Any:
    """Get global feature importance for a model.

    Returns:
        - Ranked feature importance using specified method
        - Total number of features
        - Top contributing features
    """
    # Query the model registry
    model_registry = db.query(RiskModelRegistry).filter(RiskModelRegistry.model_id == model_id).first()
    if not model_registry:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    # Query the feature importance snapshot
    snapshot = db.query(FeatureImportanceSnapshot).filter(
        FeatureImportanceSnapshot.model_id == model_id,
        FeatureImportanceSnapshot.explanation_method == method,
    ).order_by(FeatureImportanceSnapshot.computation_timestamp.desc()).first()

    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Global explanation {model_id}/{method} not found")

    # Build response
    import json as _json
    importance_entries = _json.loads(snapshot.feature_importance_json)
    top_k_entries = _json.loads(snapshot.top_k_features_json)

    result = {
        "model_id": model_registry.model_id,
        "model_version": model_registry.model_version,
        "feature_version": model_registry.feature_version,
        "explanation_method": snapshot.explanation_method,
        "explanation_version": snapshot.explanation_version,
        "total_features": snapshot.total_features,
        "feature_importance": importance_entries,
        "top_k": top_k_entries,
        "computation_timestamp": snapshot.computation_timestamp.isoformat() if snapshot.computation_timestamp else None,
    }

    return result


@router.get("/features", response_model=Dict[str, Any])
def get_feature_manifest(
    db: Session = Depends(get_db),
    version: Optional[str] = Query(None, description="Feature version filter"),
) -> Any:
    """Get the feature manifest for the currently deployed model.

    Returns:
        - List of feature definitions with names, sources, units, and derivations
    """
    from ...models.risk import RiskFeatureManifest

    query = db.query(RiskFeatureManifest)
    if version:
        query = query.filter(RiskFeatureManifest.feature_version == version)

    manifest = query.order_by(RiskFeatureManifest.created_at.desc()).first()
    if not manifest:
        raise HTTPException(status_code=404, detail="Feature manifest not found")

    result = {
        "feature_version": manifest.feature_version,
        "features": manifest.features,
        "created_at": manifest.created_at.isoformat() if manifest.created_at else None,
        "description": manifest.description,
    }

    return result


@router.get("/uncertainty/{prediction_id}", response_model=Dict[str, Any])
def get_uncertainty(
    prediction_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Get uncertainty metadata for a prediction.

    Separates uncertainty from risk probability.

    Returns:
        - Data quality assessment
        - Data completeness score
        - Missing/stale feature counts
        - Forecast uncertainty (if applicable)
        - Model uncertainty estimate
        - Confidence category
    """
    # Query the uncertainty record
    uncertainty = db.query(UncertaintyRecordDB).filter(UncertaintyRecordDB.prediction_id == prediction_id).first()
    if not uncertainty:
        raise HTTPException(status_code=404, detail=f"Uncertainty record {prediction_id} not found")

    result = {
        "prediction_id": uncertainty.prediction_id,
        "data_quality": uncertainty.data_quality,
        "data_completeness": uncertainty.data_completeness,
        "missing_feature_count": uncertainty.missing_feature_count,
        "stale_feature_count": uncertainty.stale_feature_count,
        "forecast_uncertainty": uncertainty.forecast_uncertainty,
        "model_uncertainty": uncertainty.model_uncertainty,
        "confidence_category": uncertainty.confidence_category,
        "ood": uncertainty.ood,
        "ood_score": uncertainty.ood_score,
    }

    return result


@router.get("/ood/{prediction_id}", response_model=Dict[str, Any])
def get_ood_status(
    prediction_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Get out-of-distribution status for a prediction.

    Identifies features that are outside the model's training distribution.

    Returns:
        - Whether prediction is in-distribution
        - OOD score if applicable
        - Features outside training range with distances
        - Training range information
        - OOD warning message
    """
    # Query the OOD record
    ood_record = db.query(OODRecordDB).filter(OODRecordDB.prediction_id == prediction_id).first()
    if not ood_record:
        # Return default in-distribution status
        return {
            "prediction_id": prediction_id,
            "in_distribution": True,
            "ood": False,
            "ood_score": None,
            "warning_features": [],
            "training_ranges": {},
            "message": None,
        }

    import json as _json
    result = {
        "prediction_id": ood_record.prediction_id,
        "in_distribution": not ood_record.ood,
        "ood": ood_record.ood,
        "ood_score": ood_record.ood_score,
        "warning_features": _json.loads(ood_record.warning_features_json) if ood_record.warning_features_json else [],
        "training_ranges": _json.loads(ood_record.training_ranges_json) if ood_record.training_ranges_json else {},
        "message": ood_record.message,
    }

    return result


@router.get("/equity/model/{model_id}", response_model=Dict[str, Any])
def get_equity_audit(
    model_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Get equity audit results for a model.

    Evaluates whether the model performs differently across subgroups.

    Returns:
        - Subgroup performance metrics (recall, precision, FPR, FNR)
        - Sample sizes and prevalence per subgroup
        - Data coverage per subgroup
        - Sufficiency flags for each subgroup
    """
    # Query equity audit records for this model
    audits = db.query(EquityAuditDB).filter(EquityAuditDB.model_id == model_id).all()

    import json as _json
    result = []
    for audit in audits:
        entry = {
            "subgroup": audit.subgroup,
            "sample_count": audit.sample_count,
            "prevalence": audit.prevalence,
            "recall": audit.recall,
            "precision": audit.precision,
            "false_positive_rate": audit.false_positive_rate,
            "false_negative_rate": audit.false_negative_rate,
            "specificity": audit.specificity,
            "brier_score": audit.brier_score,
            "pr_auc": audit.pr_auc,
            "sufficient_sample": audit.sufficient_sample,
            "data_coverage": audit.data_coverage,
        }
        result.append(entry)

    return {
        "model_id": model_id,
        "audits": result,
        "total_subgroups": len(result),
    }


@router.get("/coverage", response_model=Dict[str, Any])
def get_data_coverage(
    db: Session = Depends(get_db),
    subgroup: Optional[str] = Query(None, description="Subgroup filter"),
) -> Any:
    """Get data coverage equity metrics across locations/wards.

    Measures whether different areas have different data quality.

    Returns:
        - Data coverage percentages per group/location
        - Sensor availability, weather completeness, AQ completeness
        - Forecast availability per area
    """
    from ...services.coverage import build_coverage_report

    report = build_coverage_report(db)

    result = {
        "data_overview": report.get("data_overview", {}),
        "equity_note": report.get("equity_note"),
        "coverage_metrics": report.get("coverage_metrics", {}),
    }

    return result


@router.get("/model-audit/{model_id}", response_model=Dict[str, Any])
def get_model_audit(
    model_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Get model audit records for a specific model.

    Includes calibration diagnostics, explanation provenance,
    and overall model audit summary.

    Returns:
        - Calibration diagnostics (Brier, ECE, reliability)
        - Model metadata and version history
        - Explanation provenance records
    """
    # Query calibration diagnostics
    cal_diag = db.query(CalibrationDiagnosticsDB).filter(CalibrationDiagnosticsDB.model_id == model_id).order_by(CalibrationDiagnosticsDB.created_at.desc()).first()

    # Query explanation records count
    explanation_count = db.query(RiskExplanation).filter(RiskExplanation.model_id == model_id).count() if hasattr(RiskExplanation, 'model_id') else 0

    # Query uncertainty records count
    uncertainty_count = db.query(UncertaintyRecordDB).filter(UncertaintyRecordDB.model_id == model_id).count() if hasattr(UncertaintyRecordDB, 'model_id') else 0

    import json as _json

    result = {
        "model_id": model_id,
        "calibration_diagnostics": None,
        "explanation_record_count": explanation_count,
        "uncertainty_record_count": uncertainty_count,
    }

    if cal_diag:
        cal_result = {
            "brier_score_raw": cal_diag.brier_score_raw,
            "brier_score_calibrated": cal_diag.brier_score_calibrated,
            "ece": cal_diag.ece,
            "created_at": cal_diag.created_at.isoformat() if cal_diag.created_at else None,
        }
        # Parse comparison JSON
        if cal_diag.comparison_json:
            try:
                cal_result["comparison"] = _json.loads(cal_diag.comparison_json)
            except Exception:
                cal_result["comparison"] = None

        result["calibration_diagnostics"] = cal_result

    return result


@router.get("/equity/coverage", response_model=Dict[str, Any])
def get_equity_coverage(
    db: Session = Depends(get_db),
) -> Any:
    """Get data coverage equity summary.

    Distinct from model fairness - measures whether different areas
    have different data quality availability.

    Returns:
        - Data coverage percentages by area type
        - Sensor availability gaps
        - Weather/AQ data completeness by region
    """
    from ...services.coverage import build_coverage_report

    report = build_coverage_report(db)

    result = {
        "data_rich_percentage": report.get("data_rich_percentage"),
        "data_poor_percentage": report.get("data_poor_percentage"),
        "coverage_by_vulnerability": report.get("coverage_by_vulnerability", {}),
        "equity_rule": report.get("equity_rule"),
        "important_note": report.get("important_note"),
    }

    return result