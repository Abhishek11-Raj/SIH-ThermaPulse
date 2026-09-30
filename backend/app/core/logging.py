"""Structured logging foundation.

Logs are emitted as structured key/value records. Request context (request id,
user, route) can be attached via ``contextvars`` so that multi-request logs can
be correlated for auditability.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict

request_id_var: ContextVar[str] = ContextVar("keshav_request_id", default="-")
actor_var: ContextVar[str] = ContextVar("keshav_actor", default="anonymous")
route_var: ContextVar[str] = ContextVar("keshav_route", default="-")


class StructuredFormatter(logging.Formatter):
    """Emit one JSON object per log line with sanitized metadata."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "actor": actor_var.get(),
            "route": route_var.get(),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        extra = getattr(record, "ctx", None)
        if isinstance(extra, dict):
            # Never log anything that merely looks like a secret.
            safe = {k: ("[REDACTED]" if "key" in k.lower() or "secret" in k.lower() else v)
                    for k, v in extra.items()}
            payload["ctx"] = safe
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    logging.getLogger("uvicorn.access").disabled = True


def set_request_context(request_id: str, actor: str = "anonymous", route: str = "-") -> None:
    request_id_var.set(request_id)
    actor_var.set(actor)
    route_var.set(route)