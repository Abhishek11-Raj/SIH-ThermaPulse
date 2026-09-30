# KESHAV Privacy Principles

Privacy is treated as an architectural property, not an afterthought. The
health layer is designed around **aggregation, de-identification, data
minimization and purpose limitation**.

## Data minimization

- The health-outcome contract (`app/schemas/health.py`) stores only what is
  needed to learn population-level HEAT → HEALTH relationships.
- No individual identifiers exist anywhere: no name, phone, Aadhaar, exact home
  address, or medical record number. The schema explicitly forbids them and the
  adapter refuses to carry them.
- Optional fields stay null when unavailable; nothing is fabricated.

## Purpose limitation

- Health outcomes are ingested only to (a) validate heat-risk signals and
  (b) evaluate forecast quality — never for unrelated analytics.
- The dashboard and public APIs expose aggregated data only, never raw
  sensitive records.

## Access control

- RBAC/ABAC foundations exist (`Role`, `require_role`). Enforcement against
  health resources is wired in a later stage with explicit, role-scoped routes.
- The public dashboard never displays sensitive health data.

## Retention

- Retention and deletion policy/pipelines are **documented future work**
  (see `docs/SECURITY.md`). Data is stored locally in SQLite in Step 1.

## De-identification / aggregation

- Health records are aggregated at area + time-period level
  (`HealthAggregationLevel`). Cases are counts, never case-level rows.

## Auditability

- Every ingestion is logged (`ingestion_logs`) with counts accepted/rejected/
  flagged and a quality summary.
- Audit events are written to `audit_logs`; provenance is preserved per record
  so the system can always answer “where did this value come from?”.

## Operational rules

- Never log health records unnecessarily.
- Never expose raw sensitive data through APIs.
- Never log API keys.
- If a new data source cannot satisfy aggregation + de-identification,
  it must not enter the health pipeline in Step 1.