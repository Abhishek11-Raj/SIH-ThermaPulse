"""KESHAV FastAPI application — Step 1 foundation.

Startup:
    uvicorn app.main:app --reload   (from backend/)
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import (
    air_quality,
    alerts,
    coverage,
    data_quality,
    data_sources,
    digital_twin,
    forecast,
    health,
    health_outcomes,
    ingestion_status,
    learning,
    locations,
    operations,
    provider_registry,
    providers,
    risk,
    explainability,
    intervention,
    system,
    thermal,
    vulnerability,
    weather,
)
from .core.config import APP_NAME, API_VERSION, settings
from .core.enums import Scenario
from .core.logging import set_request_context, setup_logging
from .core.security import AuditEvent, AuditLogger
from .services.bootstrap import bootstrap, list_canonical_flows

setup_logging(settings.log_level)
logger = logging.getLogger("keshav.api")

app = FastAPI(
    title=f"{APP_NAME} API",
    description=(
        "Extreme Heatwave Early Warning and Human Thermal Stress / Health Risk "
        "Prediction System — Step 1 foundation (canonical data contracts, "
        "provider/adapter architecture, data quality, security)."
    ),
    version=API_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _request_context(request: Request, call_next):
    request_id = uuid.uuid4().hex[:12]
    set_request_context(request_id, actor="public", route=request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )
    response.headers["X-Request-Id"] = request_id
    return response


@app.on_event("startup")
def _startup() -> None:
    scenario = Scenario(settings.mock_scenario) if hasattr(Scenario, settings.mock_scenario) else Scenario.NORMAL_DAY
    from .core.database import SessionLocal

    session = SessionLocal()
    try:
        bootstrap(
            mock_mode=settings.mock_mode,
            mock_seed=settings.mock_seed,
            scenario=scenario,
            db=session,
        )
        AuditLogger(logger).record(
            AuditEvent(actor="system", action="startup", resource="app", details={"env": settings.app_env}),
            session=session,
        )
    finally:
        session.close()
    logger.info(
        "KESHAV started env=%s mock=%s scenario=%s",
        settings.app_env,
        settings.mock_mode,
        scenario.value,
    )


# --- Routers ----------------------------------------------------------------
API_PREFIX = "/api/v1"
for router in [
    health.router,
    system.router,
    locations.router,
    weather.router,
    forecast.router,
    air_quality.router,
    data_quality.router,
    coverage.router,
    providers.router,
    provider_registry.router,
data_sources.router,
    ingestion_status.router,
    vulnerability.router,
    health_outcomes.router,
    thermal.router,
    risk.router,
    explainability.router,
    intervention.router,
    alerts.router,
    learning.router,
    operations.router,
    digital_twin.router,
]:
    app.include_router(router)

# --- Frontend shell ---------------------------------------------------------
_frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount(
        "/dashboard",
        StaticFiles(directory=_frontend_dir, html=True),
        name="dashboard",
    )


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/dashboard/")


@app.get("/authority", include_in_schema=False)
@app.get("/authority/", include_in_schema=False)
def authority_redirect():
    return RedirectResponse(url="/dashboard/authority.html")



@app.get("/api/v1/model-registry", include_in_schema=True, tags=["system"])
def model_registry() -> dict:
    """Future model registry placeholder.

    No models exist in Step 1. This returns an explicit empty registry so the
    dashboard never implies a trained model where none exists.
    """
    return {
        "models": [],
        "note": "No health-risk model is registered or trained in Step 1."
    }


@app.get("/api/v1/canonical-flows", include_in_schema=True, tags=["system"])
def canonical_flows() -> dict:
    return {"flows": list_canonical_flows()}