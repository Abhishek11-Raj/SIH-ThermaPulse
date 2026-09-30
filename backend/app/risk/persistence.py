"""Risk model persistence — STEP 4.

Handles saving and loading model artifacts.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import joblib
import numpy as np
from sklearn.base import BaseEstimator

from ..core.config import settings


MODEL_ARTIFACT_DIR = Path(settings.data_dir) / "models" if hasattr(settings, 'data_dir') else Path("data/models")
MODEL_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


class ModelArtifact:
    """Container for model and preprocessing artifacts."""

    def __init__(
        self,
        model: Any,
        preprocessor: Any,
        feature_names: List[str],
        feature_version: str,
        model_version: str,
        config: Dict[str, Any],
        metrics: Optional[Dict[str, Any]] = None,
    ):
        self.model = model
        self.preprocessor = preprocessor
        self.feature_names = feature_names
        self.feature_version = feature_version
        self.model_version = model_version
        self.config = config
        self.metrics = metrics or {}
        self.created_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "preprocessor": self.preprocessor,
            "feature_names": self.feature_names,
            "feature_version": self.feature_version,
            "model_version": self.model_version,
            "config": self.config,
            "metrics": self.metrics,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelArtifact":
        artifact = cls(
            model=data["model"],
            preprocessor=data["preprocessor"],
            feature_names=data["feature_names"],
            feature_version=data["feature_version"],
            model_version=data["model_version"],
            config=data["config"],
            metrics=data.get("metrics", {}),
        )
        if "created_at" in data:
            artifact.created_at = datetime.fromisoformat(data["created_at"])
        return artifact


def save_model(
    model: Any,
    preprocessor: Any,
    feature_names: List[str],
    feature_version: str,
    model_version: str,
    config: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    path: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Save model and preprocessor to disk.

    Args:
        model: Trained model
        preprocessor: Fitted preprocessor
        feature_names: List of feature names in order
        feature_version: Feature schema version
        model_version: Model version
        config: Model configuration
        metrics: Evaluation metrics
        path: Optional custom path

    Returns:
        Path to saved artifact
    """
    if path is None:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = MODEL_ARTIFACT_DIR / f"risk_model_{timestamp}.joblib"

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    artifact = {
        "model": model,
        "preprocessor": preprocessor,
        "feature_names": feature_names,
        "feature_version": feature_version,
        "model_version": model_version,
        "config": config,
        "metrics": metrics or {},
        "created_at": datetime.utcnow().isoformat(),
    }

    joblib.dump(artifact, path)
    return path


def load_model(
    path: Union[str, Path],
) -> Tuple[Any, Any, List[str], str, str, Dict[str, Any]]:
    """
    Load model and preprocessor from disk.

    Returns:
        (model, preprocessor, feature_names, feature_version, model_version, config)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Model artifact not found: {path}")

    artifact = joblib.load(path)

    model = artifact["model"]
    preprocessor = artifact["preprocessor"]
    feature_names = artifact["feature_names"]
    feature_version = artifact["feature_version"]
    model_version = artifact["model_version"]
    config = artifact.get("config", {})

    return model, preprocessor, feature_names, feature_version, artifact.get("model_version", "1.0"), artifact.get("config", {})


def load_model_by_id(
    model_id: str,
    artifact_dir: Optional[Path] = None,
) -> Tuple[Any, Any, List[str], str, str, Dict[str, Any]]:
    """
    Load model by ID (finds latest version).

    Args:
        model_id: Model identifier (e.g., "keshav_risk_v1")
        artifact_dir: Directory to search (uses default if None)

    Returns:
        (model, preprocessor, feature_names, feature_version, model_version, config)
    """
    artifact_dir = artifact_dir or MODEL_ARTIFACT_DIR

    # Find matching artifacts
    pattern = f"{model_id}*.joblib"
    matches = list(artifact_dir.glob(pattern))

    if not matches:
        raise FileNotFoundError(f"No model artifact found for {model_id}")

    # Use most recent
    latest = max(matches, key=lambda p: p.stat().st_mtime)
    return load_model(latest)


def save_preprocessor(
    preprocessor: Any,
    feature_version: str,
    path: Optional[Union[str, Path]] = None,
) -> Path:
    """Save preprocessor separately."""
    if path is None:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = MODEL_ARTIFACT_DIR / f"preprocessor_{feature_version}_{timestamp}.joblib"

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(preprocessor, path)
    return path


def load_preprocessor(
    path: Union[str, Path],
) -> Any:
    """Load preprocessor from disk."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Preprocessor not found: {path}")
    return joblib.load(path)


def get_model_metadata(path: Union[str, Path]) -> Dict[str, Any]:
    """Get model metadata without loading full model."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Model not found: {path}")

    artifact = joblib.load(path)

    return {
        "feature_names": artifact.get("feature_names", []),
        "feature_version": artifact.get("feature_version", "unknown"),
        "model_version": artifact.get("model_version", "unknown"),
        "config": artifact.get("config", {}),
        "metrics": artifact.get("metrics", {}),
        "created_at": artifact.get("created_at", "unknown"),
    }


def list_model_artifacts(artifact_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """List all model artifacts in directory."""
    artifact_dir = artifact_dir or MODEL_ARTIFACT_DIR
    artifacts = []

    for path in artifact_dir.glob("*.joblib"):
        try:
            meta = get_model_metadata(path)
            stat = path.stat()
            artifacts.append({
                "path": str(path),
                "filename": path.name,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                **meta,
            })
        except Exception as e:
            artifacts.append({
                "path": str(path),
                "filename": path.name,
                "error": str(e),
            })

    return sorted(artifacts, key=lambda x: x.get("modified", ""), reverse=True)


def cleanup_old_artifacts(
    artifact_dir: Optional[Path] = None,
    keep_latest: int = 10,
) -> int:
    """
    Remove old model artifacts, keeping only the latest N.

    Returns number of deleted artifacts.
    """
    artifact_dir = artifact_dir or MODEL_ARTIFACT_DIR
    artifacts = list_model_artifacts(artifact_dir)

    if len(artifacts) <= keep_latest:
        return 0

    to_delete = artifacts[keep_latest:]
    deleted = 0

    for art in to_delete:
        if "error" not in art:
            path = Path(art["path"])
            try:
                path.unlink()
                deleted += 1
            except Exception:
                pass

    return deleted