# GoblinOS Assistant — Backend Documentation (Canonical)

This folder is the canonical location for all backend-specific documentation. If you are adding or updating backend documentation, please modify files here rather than the root of `apps/goblin-assistant`.

Moved files in this folder include:

- `ENDPOINT_AUDIT.md` — Comprehensive endpoint audit and fixes
- `ENDPOINT_SUMMARY.md` — Summary of endpoints and production checklist
- `MONITORING_IMPLEMENTATION.md` — Monitoring, metrics, and logging implementation
- `PRODUCTION_MONITORING.md` — Production monitoring & deployment recommendations
- `BACKEND_CORE_FIXED.md` — Post-fix backend verification and health
- `FIXES_APPLIED.md` — Ongoing fixes and status
- `QUICKSTART_PRODUCTION.md` — Production quickstart for backend operations
- `RAPTOR_INTEGRATION_COMPLETE.md` — Raptor integration notes

Note on infra files:

The infra and deployment scripts (Fly.io, Render, Terraform, etc.) are considered infrastructure artifacts and remain under `apps/goblin-assistant/infra` or `goblin-infra`. Please do not move infra-specific files into this backend docs directory.

If you update any backend docs, please also update any matching manifest entries at `goblin-infra/projects/goblin-assistant/MANIFEST.md` if they are infra-related.
