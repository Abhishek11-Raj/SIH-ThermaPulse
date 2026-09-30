"""Security foundation for KESHAV.

Provides:
- secret exclusion helpers (never log / return credentials)
- audit log writer (structured, immutable-by-convention records)
- CORS policy builder
- RBAC-ready role model and guards
- rate-limit-ready interface placeholder (enforcement ships later)

This is a FOUNDATION only. TLS termination, encrypted storage, pseudonymization,
attribute-based access and incident response are documented future work.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import Depends, Header, HTTPException, status

from .config import REDACTED, Settings, settings

SECRET_KEYS: frozenset = frozenset(
    {"password", "secret", "token", "apikey", "api_key", "access_key", "authorization"}
)


def redact(value: Any) -> Any:
    """Recursively redact known secret-ish keys from a value."""
    if isinstance(value, dict):
        return {k: (REDACTED if _looks_secret(k) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def _looks_secret(key: str) -> bool:
    lower = key.lower()
    return any(token in lower for token in SECRET_KEYS)


class Role(str, Enum):
    """RBAC-ready roles across KESHAV modules."""

    ADMIN = "admin"
    OPERATOR = "operator"
    MUNICIPAL_OPERATOR = "municipal_operator"
    HEALTH_OFFICIAL = "health_official"
    ANALYST = "analyst"
    FIELD_WORKER = "field_worker"
    VIEWER = "viewer"
    PUBLIC_VIEWER = "public_viewer"
    PUBLIC = "public"


ROLE_RANK: Dict[Role, int] = {
    Role.PUBLIC: 0,
    Role.PUBLIC_VIEWER: 0,
    Role.VIEWER: 10,
    Role.FIELD_WORKER: 15,
    Role.ANALYST: 20,
    Role.HEALTH_OFFICIAL: 25,
    Role.OPERATOR: 30,
    Role.MUNICIPAL_OPERATOR: 30,
    Role.ADMIN: 40,
}


def parse_role(raw: Optional[str]) -> Role:
    """Normalize and match role from header/token string."""
    if not raw:
        return Role.PUBLIC
    cleaned = raw.strip().lower().replace("-", "_")
    for r in Role:
        if r.value == cleaned or r.name.lower() == cleaned:
            return r
    return Role.PUBLIC


def get_current_role(
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Role:
    """Extract authenticated/caller role from request headers."""
    if x_user_role:
        return parse_role(x_user_role)
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        return parse_role(token)
    return Role.PUBLIC


def has_role(required: Role, current: Role = Role.PUBLIC) -> bool:
    """Check whether ``current`` satisfies at least ``required``."""
    return ROLE_RANK.get(current, 0) >= ROLE_RANK.get(required, 0)


def require_role(required: Role):
    """Dependency factory for protecting routes with RBAC."""

    def _guard(current_role: Role = Depends(get_current_role)) -> Role:
        if not has_role(required, current_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role: requires at least '{required.value}', caller has '{current_role.value}'",
            )
        return current_role

    return _guard


@dataclass
class AuditEvent:
    """Structured, tamper-evident-by-convention audit record."""

    actor: str
    action: str
    resource: str
    details: Dict[str, Any] = dc_field(default_factory=dict)
    occurred_at: datetime = dc_field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class AuditLogger:
    """Writes audit events.

    In Step 1 the audit log is persisted to the ``audit_logs`` SQL table when a
    database session is available, and always mirrored to the structured logger.
    """

    def __init__(self, logger=None) -> None:
        self._log = logger

    def record(self, event: AuditEvent, session=None) -> None:
        safe = redact(event.details)
        if session is not None:
            try:
                from ..models.audit_log import AuditLog

                session.add(AuditLog(
                    actor=event.actor[:255],
                    action=event.action[:255],
                    resource=event.resource[:255],
                    details=safe,
                    occurred_at=event.occurred_at,
                ))
                session.commit()
            except Exception:
                session.rollback()
        if self._log is not None:
            self._log.info(
                "AUDIT",
                extra={"ctx": {"action": event.action, "resource": event.resource,
                               "actor": event.actor}},
            )


class RateLimitPolicy:
    """Rate-limit-ready placeholder.

    Actual token-bucket/redis enforcement is future work; this captures the policy
    contract so endpoints can declare limits without coupling to an implementation.
    """

    def __init__(self, requests_per_window: int, window_seconds: int) -> None:
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds

    def as_metadata(self) -> Dict[str, Any]:
        return {
            "policy": "rate_limit_ready",
            "requests_per_window": self.requests_per_window,
            "window_seconds": self.window_seconds,
            "enforced": False,
            "note": "Enforcement implemented in a later stage.",
        }


def cors_settings(cfg: Settings = settings) -> Dict[str, Any]:
    """CORS-ready configuration bundle (used by FastAPI middleware)."""
    return {
        "allow_origins": list(cfg.cors_origins),
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }