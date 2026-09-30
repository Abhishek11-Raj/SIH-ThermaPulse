"""Provider-health endpoint — public-safe status for registered providers.

Exposes reachability, freshness and failure counts — never API keys or other
credentials.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.operations import ProviderStatus as ProviderStatusModel
from ...providers import registry
from ...schemas.system import ProviderHealth

router = APIRouter()


def _row_to_health(row: ProviderStatusModel) -> ProviderHealth:
    ptype = registry.type_of(row.name) or "mock"
    enabled = registry.is_enabled(row.name)
    return ProviderHealth(
        name=row.name,
        domain=row.domain,
        status=row.status,
        provider_type=ptype,
        enabled=enabled,
        last_successful_request_at=row.last_successful_request_at,
        last_failure_at=row.last_failure_at,
        last_latency_ms=row.last_latency_ms,
        auth_configured=row.auth_configured,
        freshness=row.freshness,
        failure_count=row.failure_count,
        success_count=row.success_count,
    )


@router.get(
    "/api/v1/provider-status",
    response_model=List[ProviderHealth],
    tags=["system"],
)
def provider_status(db: Session = Depends(get_db)) -> List[ProviderHealth]:
    rows = db.query(ProviderStatusModel).order_by(ProviderStatusModel.name).all()
    return [_row_to_health(r) for r in rows]