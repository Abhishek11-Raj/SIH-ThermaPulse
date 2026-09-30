"""Data-sources endpoint — static configuration for every known source.

Separate from provider-status (runtime health) and provider-registry (merged
view). This one is purely the configuration registry: type, enablement,
auth requirements (presence, never values) and fallback policy.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.step2 import DataSource as DataSourceModel
from ...schemas.datasource import DataSourceInfo

router = APIRouter()


@router.get(
    "/api/v1/data-sources",
    response_model=List[DataSourceInfo],
    tags=["system"],
)
def data_sources(db: Session = Depends(get_db)) -> List[DataSourceInfo]:
    rows = db.query(DataSourceModel).order_by(DataSourceModel.domain, DataSourceModel.name).all()
    return [
        DataSourceInfo(
            name=row.name,
            domain=row.domain,
            provider_type=row.provider_type,
            enabled=row.enabled,
            requires_api_key=row.requires_api_key,
            auth_configured=row.auth_configured,
            fallback_enabled=row.fallback_enabled,
            description=row.description,
            updated_at=row.updated_at,
        )
        for row in rows
    ]