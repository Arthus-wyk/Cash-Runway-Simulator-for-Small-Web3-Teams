# React + FastAPI Migration Status

## Stress testing phases 1-3 (2026-09-22)

- [x] Five editable hypothetical paths with per-asset nodes at months 1, 3, 6, and 12.
- [x] Targets from 1 to 12 payments and a 13-level reserve matrix.
- [x] Evidence curves and ledgers from matrix cells, including initial sales, fees, shortfalls, and comparable ending differences.
- [x] Stress matrix CSV and decision JSON; stale reports are disabled after input changes.
- [x] README rules, workflow, boundaries, and file descriptions.
- [x] Python and Node tests, production build, review, and browser integration checks.
- [x] Three complete historical windows retrieved and enabled under Startup access on 2026-09-26.
- [ ] Confirm in a regular browser that downloaded CSV and JSON files are saved to disk.

Phase 4 operational stress and public deployment remain out of scope.

The React/FastAPI migration is complete. The remaining manual check is browser download persistence; see [docs/verification.md](docs/verification.md).
