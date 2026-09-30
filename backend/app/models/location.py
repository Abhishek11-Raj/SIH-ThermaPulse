"""Location ORM model supporting the country→state→district→city→ward→zone
hierarchy plus point stations, with room for GIS geometry references."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from ..utils.time import utcnow


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    parent_location_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("locations.location_id", use_alter=True), index=True
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geometry_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    population: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    area_sq_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    parent = relationship("Location", remote_side=[location_id], backref="children")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Location {self.location_id} {self.name} {self.type}>"