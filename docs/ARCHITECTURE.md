# KESHAV Architecture (Step 1)

## Layered design

```
      ┌────────────────────────────────────────────────────────┐
      │                API layer (FastAPI routes)               │
      │  /health /api/v1/*  — canonical schemas in/out          │
      └─────────────────────────┬──────────────────────────────┘
                                │ canonical contracts only
      ┌─────────────────────────▼──────────────────────────────┐
      │              Service layer (app/services)              │
      │  quality · coverage · freshness · ingestion · bootstrap│
      └─────────────────────────┬──────────────────────────────┘
                                │ adapter boundary
      ┌─────────────────────────▼──────────────────────────────┐
      │               Adapter layer (app/adapters)             │
      │ provider-native  →  canonical  (+ provenance, quality) │
      └─────────────────────────┬──────────────────────────────┘
                                │ provider-native records
      ┌─────────────────────────▼──────────────────────────────┐
      │               Provider layer (app/providers)           │
      │ interfaces/protocols · registry · health · mock impls  │
      └────────────────────────────────────────────────────────┘

      SQLAlchemy models ── persistence (SQLite now, PG later)
```

## The central rule

```
PROVIDER → ADAPTER → CANONICAL DATA MODEL
```

No provider-specific format ever reaches the services, API or models. Adding a
new source = implement an interface + adapter, register it. The rest of the
application is untouched.

## Canonical schema families

| Family | Schema module | Distinct concept |
| --- | --- | --- |
| Weather observation | `schemas/weather.py` | measured, point-in-time |
| Weather forecast | `schemas/forecast.py` | issued_at vs valid_from/valid_to (track-record ready) |
| Air quality | `schemas/air_quality.py` | null-safe pollutants |
| Location / GIS | `schemas/location.py` | country→…→ward → point hierarchy |
| Vulnerability | `schemas/vulnerability.py` | null-safe population factors |
| Health outcome | `schemas/health.py` | aggregated, de-identified only |
| Common | `schemas/common.py` | provenance, spatial/temporal refs, quality, coverage, freshness, TimeWindow, LocationMapping |

## Quality pipeline (per record)

1. Provider returns raw native records (`RawObservation`/`RawForecast`).
2. Adapter maps fields → canonical variables; builds provisional values.
3. `services/quality.py` assesses ranges, units, missingness, timestamps →
   structured `QualityAssessment` (`VALID/SUSPECT/MISSING/STALE/INVALID/IMPUTED`).
4. Invalid variables are downgraded to null, original values kept in issues.
5. Canonical record (with provenance + quality) is persisted; non-valid records
   also land in `data_quality_records`.
6. `ingestion_logs` records received/accepted/rejected/flagged + summary;
   `provider_status` is updated.

## Missing-data policy

Missing ⇒ `None` + `MISSING` flag. Never zero. Invalid ⇒ `INVALID` + null.
Stale/imputed are distinct states. Downstream stages decide interpolation later.

## Coverage & equity

`services/coverage.py` computes per-domain, per-location missingness against the
domain's own expected granularity (hourly weather/AQ, daily health/vulnerability).
`DATA_RICH / ADEQUATE / DATA_POOR` classes feed the equity layer; a data-poor
area must raise uncertainty, never lower apparent risk.

## Freshness

`services/quality.freshness_status()` applies per-domain cadence
(FRESH / AGING / STALE / UNAVAILABLE). No universal threshold.

## Database

`models/` tables: `locations`, `weather_observations`, `weather_forecasts`,
`air_quality_observations`, `vulnerability_data`, `health_outcomes`,
`data_quality_records`, `ingestion_logs`, `provider_status`, `audit_logs`.
UTC internally; source timestamp and ingestion timestamp are both preserved and
indexed on `location_id`, `observed_at`, `valid_from`, `valid_to`.

Later-stage tables (thermal_features, exposure_memory, predictions, models,
evaluations, interventions, alerts, outcomes) are deliberately not created yet.

## Provider registry & health

`providers/base.py` defines Protocols and the `ProviderRegistry`, plus
`ProviderHealthState` (success/failure counts, latency, auth-configured — never
credentials). Mock providers (`providers/mock/`) are registered at startup when
`MOCK_MODE=true`.

## Frontend shell

`frontend/` is a static single-page shell (no build step) served by FastAPI at
`/dashboard`. It renders the foundation dashboard and provides navigation for
all future modules; unimplemented modules show explicit placeholders.