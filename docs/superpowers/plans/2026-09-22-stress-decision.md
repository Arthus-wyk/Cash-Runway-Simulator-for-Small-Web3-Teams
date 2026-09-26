# Stress-Test Decision Loop

The user approved the first three phases and authorized implementation. Update the README business explanation after each feature. Stop and update the TODO if either usage window falls below 10%.

## Deliverables and implementation order

- [x] Staged paths: `stress.py` defines Fall then recover, Rise then fall, Continued decline, Stablecoin depeg, and Continued growth. Each asset has editable changes at months 1, 3, 6, and 12 with calendar-day linear interpolation. `engine.py` permits zero prices for hypothetical paths while real history remains strictly positive.
- [x] Targets and matrix: evaluate targets from 1 to 12 consecutive payments and reserve levels from 0 to 12 months on one shared market snapshot. Return summaries in bulk and retrieve full ledgers through the existing simulation endpoint when a cell is selected. Preserve the original one-time shock and historical modes.
- [x] Explanation and export: summarize passing and failing scenarios, earliest shortfall, initial sales, and cumulative fees. Compare ending `B - A` only when both strategies reach the same end date. Select the smallest fully funded reserve that meets every chosen target, or show no feasible option. Export a complete decision JSON and matrix CSV.
- [x] Integration: run offline unit and API tests, export tests, production build, recorded-browser checks, stale-input checks, and independent review.

## Test basis

Compare matrix results against `compare`; ensure reserve zero matches Strategy A; prove payment order matters for paths with equal ending prices; cover zero, month-end, invalid nodes and labels, empty scenarios, duplicate IDs, target limits, no solution, comparable ending values, the 16 KB limit, and snapshot protection. Old results cannot be exported after input changes, and selecting a cell must not request new market data.

## Boundaries

Historical permissions and data use the existing entry point; unavailable data is never presented as available. These phases do not add income delays, accounts, wallets, real trades, or dependencies. Path ratios and exported amounts use Decimal strings. The project is not a Git repository and is implemented in the current workspace.

Acceptance completed with 31 Python tests, 2 Node tests, a production build, and no material independent-review finding. Browser results are in `docs/verification.md`; manual download persistence remains in `TODO.md`.
