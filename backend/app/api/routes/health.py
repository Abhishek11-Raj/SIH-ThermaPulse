"""Root, health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...core.config import APP_NAME, API_VERSION, settings
from ...core.database import get_db
from ...schemas.system import ServiceHealth
from ...utils.time import utcnow

router = APIRouter()

LANDING = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=/dashboard/index.html">
<title>Thermapulse — AI Heatwave Early Warning & Resilience Platform</title>
<style>
body{font-family:system-ui,-apple-system,sans-serif;max-width:840px;margin:40px auto;color:#1f2937;line-height:1.6;background:#f9fafb;padding:0 20px}
.badge{display:inline-block;background:#0f766e;color:#fff;padding:3px 12px;border-radius:999px;font-size:12px;font-weight:700}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:18px;margin:12px 0;box-shadow:0 1px 3px rgba(0,0,0,0.05)}
a{color:#0f766e;text-decoration:none;font-weight:600}
a:hover{text-decoration:underline}
ul{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px;list-style:none;padding:0}
li{background:#f3f4f6;padding:8px 12px;border-radius:6px}
</style>
</head>
<body>
<h1>Thermapulse <span class="badge">STEPS 1–10 PRODUCTION PLATFORM</span></h1>
<p>AI-Based Extreme Heatwave Early Warning, Human Thermal Stress, Health Risk Prediction, City Operations & Heat Resilience Digital Twin.</p>
<div class="card">
  <h3>Quick Access</h3>
  <p>👉 <strong><a href="/dashboard/index.html">Open Interactive Frontend Dashboard (/dashboard/)</a></strong></p>
  <p>👉 <strong><a href="/docs">Open Interactive API Documentation (/docs)</a></strong></p>
  <p>👉 <strong><a href="/openapi.json">Open OpenAPI 3.1 JSON Specification (/openapi.json)</a></strong></p>
</div>
<div class="card">
  <h3>Active Core Endpoints</h3>
  <ul>
    <li><a href="/health">/health</a> (Service Status)</li>
    <li><a href="/api/v1/locations">/api/v1/locations</a> (Ward GIS)</li>
    <li><a href="/api/v1/weather">/api/v1/weather</a> (Telemetry)</li>
    <li><a href="/api/v1/forecast">/api/v1/forecast</a> (NWP Forecast)</li>
    <li><a href="/api/v1/thermal/methods">/api/v1/thermal/methods</a> (HI / WBGT / UTCI)</li>
    <li><a href="/api/v1/risk/methods">/api/v1/risk/methods</a> (AI Health Risk)</li>
    <li><a href="/api/v1/alerts/status">/api/v1/alerts/status</a> (Alert Dispatch)</li>
    <li><a href="/api/v1/operations/priorities">/api/v1/operations/priorities</a> (Priority Ranks)</li>
    <li><a href="/api/v1/twin/state">/api/v1/twin/state</a> (Digital Twin)</li>
    <li><a href="/api/v1/resilience/profile">/api/v1/resilience/profile</a> (10-D Resilience)</li>
    <li><a href="/api/v1/adaptation/portfolios">/api/v1/adaptation/portfolios</a> (Adaptation)</li>
    <li><a href="/api/v1/strategic-plans/roadmap">/api/v1/strategic-plans/roadmap</a> (2026-2050)</li>
  </ul>
</div>
<p><em>All Step 1–10 engines active with strict scientific data classification and human-in-the-loop governance.</em></p>
</body>
</html>"""


def _health(db: Session) -> ServiceHealth:
    db_ok = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = "unavailable"
    return ServiceHealth(
        status="degraded" if db_ok != "ok" else "ok",
        application=APP_NAME,
        api_version=API_VERSION,
        environment=settings.app_env,
        database=db_ok,
        utc_time=utcnow(),
    )


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def landing() -> HTMLResponse:
    return HTMLResponse(content=LANDING)


@router.get("/health", response_model=ServiceHealth, tags=["system"])
def health_short(db: Session = Depends(get_db)) -> ServiceHealth:
    return _health(db)


@router.get("/api/v1/health", response_model=ServiceHealth, tags=["system"])
def health(db: Session = Depends(get_db)) -> ServiceHealth:
    return _health(db)