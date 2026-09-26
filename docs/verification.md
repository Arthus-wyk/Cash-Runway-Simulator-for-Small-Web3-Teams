# React + FastAPI Migration Verification (2026-09-21)

## Stress testing phases 1-3 acceptance (2026-09-22)

- All 31 Python unit tests passed at the time of acceptance. Coverage included four-node interpolation, leap-year month-end, zero prices, invalid input, equal-ending paths with different order, 13 reserve levels against individual results, no-solution behavior, comparable ending values, shared snapshots, provenance checks, and request-size limits.
- Both Node tests passed. Stress CSV retained decimal precision, provenance, and targets, distinguished incomparable ending values, and prevented labels from becoming spreadsheet formulas.
- The Vite production build passed with no new dependencies.
- A read-only review found no material defect and independently reran the automated checks.
- With recorded real quotes, the sample team, a target of 9 payments, and all five hypothetical scenarios, the smallest feasible reserve was 7 months. This is evidence for that input and start date only, not a fixed product conclusion.
- Changing the target to 12 immediately disabled the old matrix and JSON export; rerunning showed no feasible option.
- A node at -101% produced an explicit validation error; -100% completed successfully and supported a hypothetical asset reaching zero.
- Browser checks captured no console warnings or errors.

## Automated checks

- Before migration: 21 Python unit tests passed.
- New HTTP tests failed against the old implementation because `create_app` did not exist, then passed after the FastAPI entry point was implemented.
- After migration: 25 Python tests passed for Decimal calculations, caching, replay, simulation, malformed input, origin checks, the 16 KB limit, media types, private-file isolation, and static serving.
- `npm --prefix frontend test` passed the CSV export checks for exact precision, BOM, quote/newline escaping, and both ledgers.
- `npm --prefix frontend run build` produced the React/Vite production build.
- Real HTTP integration on ports 8000 and 5173 returned the React page. Recorded quotes and a same-origin simulation request returned HTTP 200 with both strategies.

## Browser checks

The production and Vite development pages were opened in the built-in browser:

- Live quotes loaded and triggered simulation; recorded replay was explicitly labeled.
- Monthly expense set to zero displayed a validation error and disabled the full-report button.
- Restoring the sample team recalculated successfully.
- Setting the reserve slider to 12 updated Strategy B and displayed its reserve shortfall.
- Ledger B showed the initial asset sale and full monthly records.
- Rapidly changing cash from 100 to 20000 left the result associated with the latest input.
- Narrow and wide layouts showed no page-level horizontal overflow; the ledger kept independent horizontal scrolling.
- No console warning or error was captured on the Vite page.

## Historical access update (2026-09-26)

After Startup access became active, `.venv/Scripts/python server.py --fetch-history` retrieved all three configured windows. Each passed the 367-day completeness check for BTC, ETH, and USDC and consumed 12 credits, for 36 credits total. `/api/scenarios` then returned HTTP 200 with all three scenarios marked `available: true`. The licensed responses remain under ignored `.cache/`.

## Verification limitation

The built-in browser timed out while waiting for download events at both 3 and 10 seconds. CSV content and button state were verified, but browser persistence of CSV/JSON files was not. Confirm both downloads in a regular browser; the item remains in `TODO.md`.

## Observed environment

Python 3.14.4; Node 22.22.2; React 19.3.0; Vite 8.3.0; FastAPI 0.141.1; Uvicorn 0.53.0.

References: [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/) and [Vite proxy configuration](https://vite.dev/config/server-options).
