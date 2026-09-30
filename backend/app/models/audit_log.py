"""Audit log ORM model."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..utils.time import utcnow


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(255), index=True)
    action: Mapped[str] = mapped_column(String(255), index=True)
    resource: Mapped[str] = mapped_column(String(255))
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)