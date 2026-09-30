# KESHAV Scientific Safety

These principles constrain every downstream stage and are already reflected in
the Step 1 contracts.

## Core statements

1. **KESHAV is not a medical diagnostic system.**
   A risk prediction produced by KESHAV is a population/exposure assessment —
   it is not an individual medical diagnosis and must never be presented as one.

2. **Population-level ≠ individual clinical prediction.**
   Health outcomes are aggregated and de-identified. Patterns learned operate
   at area level (wards, cities), not for any specific person.

3. **Official warnings remain distinguishable.**
   A KESHAV-derived risk metric is not an official meteorological or health
   warning. UIs/APIs must keep the KESHAV score visibly separate from any
   government-issued heatwave warning.

4. **Never auto-label as heatwave.**
   A calculated exposure/heat metric must not automatically be described as an
   *official heatwave declaration*.

5. **No health labels → no trained model claim.**
   If outcome/health labels are unavailable, the system must not pretend an AI
   health model has been trained. Step 1 ships an empty model registry precisely
   to make this explicit.

## Data-safety invariants (never silently …)

| Prohibited transformation | Correct behavior |
| --- | --- |
| missing → zero | null value + `MISSING` flag |
| invalid → valid | `INVALID` flag; value downgraded to null with reason recorded |
| stale → fresh | `STALE`/`AGING` status via per-source freshness |
| unknown → safe | missing data raises uncertainty, never lowers risk |
| no data → low risk | `DATA_POOR` coverage class → higher uncertainty |
| no health data → trained model | no model; empty model registry |
| no official warning → official warning | never; scores stay KESHAV-only |
| derived score → medical diagnosis | never; presented as population-level risk cue |

## Design implications in Step 1

- `QualityFlag` / `MissingState` enums distinguish missing, unavailable, stale,
  invalid and imputed states.
- `CoverageReport` encodes *"No data is never treated as low risk"*.
- The health contract refuses identifiable fields.
- The model registry endpoint returns an explicit empty list.