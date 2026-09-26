# CMC API Verification Evidence

Captured on 2026-09-20 UTC using the user's then-current Basic key. Authentication headers retain only `[REDACTED]`; no key is stored in response files.

| File | Endpoint | Observed result | `status.credit_count` |
|---|---|---|---|
| `map.json` | `/v1/cryptocurrency/map?symbol=BTC,ETH,USDC` | HTTP 200 | 0 |
| `latest.json` | `/v3/cryptocurrency/quotes/latest?id=1,1027,3408&convert=USD` | HTTP 200 | 1 |
| `historical.json` | `/v2/cryptocurrency/ohlcv/historical`, two-day BTC probe | HTTP 403, error 1006 | 0 |

The successful map response contains ambiguous symbols, so assets are verified by ID and slug. The actual V3 latest response is wrapped as `{data: [...], status: {...}}`; each asset's `quote` value is an array, with USD identified by ID 2781. The historical file records the earlier Basic-tier denial and remains valid evidence of that attempt.

After the account received Startup access, all three configured historical windows were successfully downloaded and validated on 2026-09-26: 367 complete days per window, 12 credits each, 36 credits total. Those licensed responses live in ignored `.cache/` files and are not part of public evidence or redistribution.

The latest-quote response is available only as an explicitly selected recorded replay. It is not a silent live-data fallback. See `Market.request`, `probe`, and `fetch_history` in `server.py`.

Documentation references:

- https://coinmarketcap.com/api/documentation/pro-api-reference/cryptocurrency
- https://coinmarketcap.com/api/pricing/
- https://coinmarketcap.com/api/resources/api-hackathon/

These files are real local API evidence, not documentation examples. Synthetic historical parser fixtures in unit tests are not competition evidence.
