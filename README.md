# Runway | Cash Runway Simulator for Small Web3 Teams

**How many full paydays remain? When is the first shortfall? What does an upfront cash reserve cost?**

Runway combines real CoinMarketCap quotes for BTC, ETH, and USDC with USD cash in an auditable monthly cash-flow simulation. Strategy A sells assets monthly as needed. Strategy B builds a cash reserve at the start. The app does not connect a wallet or execute trades.

## Current delivery status

The app includes editable stress paths, a 13-level reserve matrix, decision explanations, monthly ledgers, and CSV/JSON exports. Changing treasury inputs, targets, nodes, or market data immediately invalidates old matrix results so stale conclusions cannot be exported.

Decision details show:

- which selected scenarios meet or miss the payment target;
- the earliest shortfall date, scenario, and unpaid amount;
- initial BTC, ETH, and USDC sales, net proceeds, fees, and reserve funding gap;
- cumulative fees through the end of a run or its first shortfall; and
- `B - A` ending assets only when both strategies reach the same end date.

The stress matrix CSV is designed for spreadsheet comparison. The decision JSON preserves inputs, market provenance, selected scenario nodes, daily ratios, matrix summaries, and the selected cell's complete curve and ledger.

Five editable **hypothetical** paths are included: Fall then recover, Rise then fall, Continued decline, Stablecoin depeg, and Continued growth. Each defines separate BTC, ETH, and USDC changes at months 1, 3, 6, and 12, with calendar-day linear interpolation. A node value of `-40%` means 60% of the starting quote, not another 40% drop from the prior node.

Three real historical windows are also enabled locally after successful Startup-tier retrieval on 2026-09-26. Each contains 367 complete days for all three assets and consumed 12 credits, for 36 credits total. The validated data lives in the ignored `.cache/` directory and is not committed for redistribution.

## Requirements and startup

Requirements: Python 3.11+, Node.js 22.12+, and a modern browser. The frontend uses React and Vite; the backend uses FastAPI and Uvicorn; the calculation engine uses Python `Decimal`.

```powershell
cd D:\Python_Program\CoinMarketCap
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
.venv/Scripts/python server.py
```

Open <http://127.0.0.1:8000>. After the frontend is built, the Python backend serves both the API and React app. Rebuild and refresh after changing frontend source.

Use another port with `.venv/Scripts/python server.py --port 8001`. Press Ctrl+C to stop.

### Development mode

Run these in separate terminals:

```powershell
# Terminal 1: FastAPI backend
.venv/Scripts/python -m uvicorn server:create_app --factory --reload --host 127.0.0.1 --port 8000 --no-access-log
```

```powershell
# Terminal 2: React/Vite frontend
npm --prefix frontend run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api` to port 8000 and fails explicitly if its fixed port 5173 is occupied. Development mode does not require a frontend build.

If the npm cache is not writable, add `--cache .cache/npm` to `npm ci`.

The backend supports `CMC_API_KEY`, `CMC_API`, and `COINMARKETCAP_API_KEY`. A new environment can copy `.env.example` to `.env` and set `CMC_API_KEY`. Never overwrite an existing `.env`, expose keys in chat or screenshots, commit them, or place them in a `VITE_` variable. Only the backend sends the key to `https://pro-api.coinmarketcap.com`.

On first load, the app displays a clearly labeled sample team and requests live CMC quotes. If refresh fails, the error is explicit. Users can select recorded replay, which uses `evidence/latest.json` and always displays its capture time and replay status rather than presenting it as current data.

## Workflow

1. Enter token holdings, USD cash, monthly income and expenses, payment day, and simulation start date.
2. Choose a custom one-time change or one of the validated real historical windows.
3. Adjust cash reserve months and compare full payments and first shortfalls.
4. Switch between Strategy A and B ledgers to inspect income, payments, asset sales, fees, and remaining assets.
5. Download the exact JSON report or UTF-8 BOM CSV ledger.
6. Optionally set a payment target and run the multi-scenario stress matrix.

## Calculation rules

| Item | Rule |
|---|---|
| Horizon | 12 calendar months from the start; first payment is strictly later than the start |
| Dates | UTC; payment day 1-31, using month-end in shorter months |
| Cash-flow order | Monthly USD income arrives before the full monthly expense is paid |
| Strategy A | No initial trade; sell assets only when cash is insufficient for a payment |
| Strategy B | Initial cash target is `N x monthly expense`; existing cash counts, future income does not; establish once |
| Sale order | Cash, then USDC, then BTC/ETH in proportion to current market value; never short |
| Fees | Net cash = units x simulated price x `(1 - fee rate)`; editable from 0% to 20% |
| Custom path | Strategy B builds its reserve at the starting quote; each asset changes once on day 1 and stays flat |
| Historical path | Current quote x historical daily close / historical baseline close, mapped by relative day |
| USDC | Uses its own quote and path; it is never treated as identical to USD cash |
| Shortfall | Partially pay with available net assets, record due minus paid, then stop that strategy |
| Covered payments | Consecutive full payments before the first shortfall; never extrapolated to infinity |
| Curve | Cash plus remaining units times daily simulated price, after actual sale fees |
| Precision | Python `Decimal` precision 40; internal values are not rounded to cents |

Limits: holdings `1e12`; cash and cash flow `1e15`; nonzero magnitude at least `1e-18`; changes from -100% to +1000%; dates from 2000 through 2100. Displayed money is rounded to cents and token units to 8 decimals, while JSON and CSV retain backend values.

This is a cash-flow stress test under specified price paths, not an optimal trading strategy or forecast. It ignores tax, interest, settlement delay, minimum trade sizes, liquidity, and additional slippage. Payment count is not employee count.

## CMC API, cache, and historical data

Used endpoints:

- `/v1/cryptocurrency/map`: verifies IDs and slugs: BTC `1/bitcoin`, ETH `1027/ethereum`, USDC `3408/usd-coin`.
- `/v3/cryptocurrency/quotes/latest`: queries all three IDs with `convert=USD`. The real V3 response uses `data[]` and an asset-level `quote[]` array.
- `/v2/cryptocurrency/ohlcv/historical`: supplies the three validated historical windows under Startup access.

The quote cache lasts 60 seconds. Network or 429 failures trigger a 60-second cooldown. The most recent successful quote may be reused for at most 24 hours with a warning; quotes older than 5 minutes are marked stale. The latest 32 snapshots remain in memory.

Probe endpoints and update redacted evidence, usually using about 1-2 credits:

```powershell
.venv/Scripts/python server.py --probe
```

Download and validate all three historical windows, using about 36 credits:

```powershell
.venv/Scripts/python server.py --fetch-history
```

The windows are 2021-05-01 through 2022-05-02, 2022-01-01 through 2023-01-02, and 2023-01-01 through 2024-01-02. Every asset and date must be present exactly once with a positive price. Missing values are never interpolated or forward-filled. `time_start` is exclusive, so requests begin one day earlier.

Successful historical data is stored under ignored `.cache/`. Refresh the page after retrieval. Continued use and redistribution must follow CMC licensing. If Startup access expires, retrieving fresh history may fail, but a locally validated cache can still support the demo subject to those terms.

## Tests

```powershell
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m unittest -v
npm --prefix frontend test
npm --prefix frontend run build
```

Tests require no key or network access. They cover constant and falling prices, cash shortages, fees, payment ordering, USDC valuation, proportional sales, reserve funding, zero prices, month-end and leap-year behavior, missing history, invalid values, cache fallback, timeouts, private-file isolation, origin checks, snapshot validity, stress paths, and export precision. Historical parser fixtures are explicitly synthetic and are not product scenarios or API evidence.

## Project boundaries

- `engine.py`: deterministic cash-runway calculations.
- `stress.py`: hypothetical paths, reserve enumeration, target filtering, and summaries.
- `server.py`: FastAPI application factory, CMC client, cache, history loader, and JSON API.
- `frontend/src/App.jsx`: form, strategy cards, chart, ledger, and request state.
- `frontend/src/StressPanel.jsx`: targets, node editing, matrix, and explanations.
- `frontend/src/report.js` and `stressReport.js`: report exports.
- `evidence/`: redacted real responses; `docs/`: design, verification, and submission material.

The local server binds only to `127.0.0.1`, exposes allowlisted routes, and does not serve the project directory. Requests for `.env`, source files, and `.git` paths return 404. Simulation inputs are not sent to CMC or persisted.

This is a local demo service, not a public production deployment. Public hosting still requires a reverse proxy, TLS, access and resource limits, and verified key management.

## Submission

See [docs/submission.md](docs/submission.md) for the demo script, project copy, social draft, and submission checklist. The project remains local; no public repository, deployment, post, or final submission has been created.
