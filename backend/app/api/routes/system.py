"""System information endpoint — exposes SAFE metadata only.

Never exposes API keys, passwords, credentials or private health information.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...core.config import API_VERSION, settings
from ...core.security import RateLimitPolicy, cors_settings
from ...schemas.system import SystemInfo
from ...utils.time import utcnow

router = APIRouter()


@router.get("/api/v1/system/info", response_model=SystemInfo, tags=["system"])
def system_info() -> SystemInfo:
    safe = settings.safe_dict()
    db_url = settings.database_url
    dialect = db_url.split(":", 1)[0] if db_url else "unknown"
    return SystemInfo(
        application=safe["app_name"],
        environment=safe["app_env"],
        api_version=API_VERSION,
        data_pipeline_version=safe["data_pipeline_version"],
        model_version=settings.model_version,
        mock_mode=settings.mock_mode,
        database_dialect=dialect,
        utc_time=utcnow(),
        security={
            "cors": cors_settings(),
            "rate_limit": RateLimitPolicy(
                requests_per_window=100, window_seconds=60
            ).as_metadata(),
            "secrets_excluded": True,
            "notes": [
                "TLS, encrypted storage, pseudonymization, RBAC enforcement, "
                "attribute-based access and data retention are documented future work.",
            ],
        },
        note=(
            "Foundation stage. No health-risk predictions are made yet; "
            "this endpoint returns configuration metadata only."
        ),
    )