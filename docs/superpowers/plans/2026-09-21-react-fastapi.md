# React + FastAPI Migration Implementation Plan

**Goal:** Migrate the confirmed technology stack while preserving simulation rules, UI features, and data-security boundaries.

**Architecture:** React and Vite render the page. FastAPI and Uvicorn provide the existing JSON API. `engine.py` remains the Decimal calculation engine.

**Execution:** Implement directly in the current session without adding a database, UI framework, or chart dependency. The directory is not a Git repository, so no commit or worktree is created.

## Constraints

- Use English function and class names.
- Keep API keys on the backend and preserve quote caching, recorded replay, historical scenarios, CSV/JSON export, and CLI retrieval.
- In development, Vite proxies `/api`; after building, FastAPI serves only `frontend/dist` and its assets.
- Stop and update `TODO.md` if either account-usage window falls below 10%.

## Implementation steps

- [x] Convert `test_server.py` to FastAPI TestClient and verify recorded simulation, invalid input, cross-origin rejection, request limits, and private-file isolation against the missing old entry point.
- [x] Convert `server.py` and add `requirements.txt` and `requirements-dev.txt`, preserving Market and calculation contracts.
- [x] Add the frontend package, lockfile, Vite config, HTML entry, React components, styles, and report module while preserving responsive behavior.
- [x] Use Node's built-in test runner for CSV precision and escaping; verify replay, edits, slider, ledgers, exports, and the development proxy.
- [x] Update the README, ignore rules, TODO, and verification record.

## Regression focus

1. Out-of-order async responses must never overwrite newer input; invalid or pending results cannot be exported.
2. An unbuilt frontend receives a clear startup message; secrets and source files remain inaccessible.
3. Malformed or oversized requests preserve 400/403/409/413/415 responses and the 16 KB cap.
4. Backend decimal strings must not become floating-point values during export.
5. Unavailable historical market data stays disabled with an explicit reason rather than fabricated values.

## Verification commands

```powershell
.venv/Scripts/python -m unittest -v
npm --prefix frontend test
npm --prefix frontend run build
.venv/Scripts/python server.py
npm --prefix frontend run dev
```

Baseline: all 21 original unit tests passed. Initial usage: 85% of the five-hour window and 82% of the weekly window remained.

## Completion record

All 25 Python tests, the Node CSV test, the Vite production build, and dependency checks passed at migration time. Ports 8000 and 5173 were integrated. Independent review found no blocker. The built-in browser could not confirm download persistence, so the manual item remains in `TODO.md`.
