# KESHAV Security Foundation

This document records what is **implemented** in Step 1 versus what is
**documented future work**. We do not claim deployed security controls that do
not exist yet.

## Implemented in Step 1

| Control | Implementation |
| --- | --- |
| Environment-based secrets | `app/core/config.py` loads via `pydantic-settings` from env / `.env`. No secrets in source code. |
| Secret exclusion | `Settings.safe_dict()` and `redact()` never return credentials; `/api/v1/system/info` and logs only ever see `[REDACTED]`. |
| Authentication-ready | No user auth is enabled yet, but the middleware/actor plumbing and `AuditEvent` actor field are in place. |
| Authorization-ready / RBAC-ready | Role enum (`admin/operator/analyst/viewer/public`) and `require_role()` dependency guard exist for later wiring. |
| Least privilege | Health data is only aggregated/de-identified; API exposes canonical schemas, never provider internals. |
| Input validation | All API payloads are validated via canonical Pydantic schemas and domain validators. |
| Structured logging | JSON-lines logging with request context (`app/core/logging.py`). |
| Audit logging | `AuditLog` table + `AuditLogger`; startup is audited. Not yet wired to every mutation (future work). |
| Secure error responses | Global middleware returns generic 500; no stack trace leaks to clients. |
| CORS configuration | Allow-list driven by `CORS_ORIGINS` setting. |
| Rate-limit-ready | `RateLimitPolicy` captures the contract metadata; enforcement is future work. |
| Dependency pinning | `requirements.txt` uses bounded ranges (`>= X, < Y`). |

## Documented future work

- TLS termination (reverse proxy / platform TLS).
- AES-256 (or equivalent) encrypted storage.
- Pseudonymization of any personally identifiable data that ever enters the
  platform.
- Deployment-level network segmentation for health data.
- Full RBAC/ABAC enforcement and identity provider integration.
- Data retention and deletion policies with tooling.
- Incident response and vendor-control procedures.
- Model/version auditability for every produced prediction.

## Rules enforced from day one

- Do not log API keys, passwords, tokens or health records unnecessarily.
- Do not expose credentials through any endpoint or serialized config.
- Every data record preserves provenance so audit questions like
  *“where did this value come from?”* can always be answered.