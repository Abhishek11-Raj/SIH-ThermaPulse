"""Locations endpoint — canonical Location schema."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.enums import LocationType
from ...core.database import get_db
from ...models.location import Location as LocationModel
from ...schemas.common import SpatialReference
from ...schemas.location import Location

router = APIRouter()


class LocationList(BaseModel):
    locations: List[Location]
    count: int = 0


def _to_canonical(row: LocationModel) -> Location:
    return Location(
        location_id=row.location_id,
        parent_location_id=row.parent_location_id,
        name=row.name,
        type=row.type,
        latitude=row.latitude,
        longitude=row.longitude,
        spatial=SpatialReference(
            ref_type="polygon",
            geometry_reference=row.geometry_reference,
        ),
        population=row.population,
        area_sq_km=row.area_sq_km,
        source=row.source,
        created_at=row.created_at,
        last_updated_at=row.last_updated_at,
    )


@router.get("/api/v1/locations", response_model=LocationList, tags=["locations"])
def list_locations(
    location_type: Optional[LocationType] = None,
    db: Session = Depends(get_db),
) -> LocationList:
    q = db.query(LocationModel)
    if location_type:
        q = q.filter(LocationModel.type == location_type.value)
    rows = q.order_by(LocationModel.location_id).all()
    canonical = [_to_canonical(r) for r in rows]
    return LocationList(locations=canonical, count=len(canonical))


@router.get("/api/v1/locations/{location_id}", response_model=Location, tags=["locations"])
def get_location(location_id: str, db: Session = Depends(get_db)) -> Location:
    row = db.query(LocationModel).filter(LocationModel.location_id == location_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"location {location_id!r} not found")
    return _to_canonical(row)