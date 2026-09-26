# Runway Submission Draft

Last updated: 2026-09-26. Startup access is active locally and three historical scenarios have been downloaded and validated. The user has chosen to keep the project local for now; this file does not claim publication, deployment, or submission.

## Project description

Runway is a cash-runway simulator for small Web3 teams that hold crypto but pay recurring expenses in dollars. Instead of stopping at portfolio value, it shows how many monthly payments a team can fully cover, the first payment shortfall, and the trade-off between selling crypto as bills arrive and keeping a cash buffer upfront.

It uses CoinMarketCap IDs and real USD quotes for BTC, ETH, and USDC. A deterministic Decimal-based engine applies the same cash flows and market path to both strategies, deducts sold units and fees, and exposes a monthly ledger and downloadable report. There is no wallet connection, real trade, price prediction, or LLM-based accounting.

The app supports custom one-time price shocks, five editable hypothetical paths, and three validated real historical windows. The recommended track is **Data and Visualisation**, emphasizing scenario comparison and explainable ledgers. Track-specific weights and final fields still need confirmation on the live submission page.

## What the API enabled and constrained

- Enabled: stable asset identity through CMC IDs, live multi-asset USD valuation, separate USDC market valuation, timestamped snapshots shared by both strategies, and validated historical replay.
- Constraint encountered: Basic access denied historical OHLCV with HTTP 403 / error 1006. The app exposed that limitation instead of inventing data. Startup access later enabled complete retrieval.
- Actual response validation also caught that V3 uses arrays for both `data` and `quote`, unlike a V2-shaped parser.
- Endpoints: `/v1/cryptocurrency/map`, `/v3/cryptocurrency/quotes/latest`, and `/v2/cryptocurrency/ohlcv/historical`.
- Evidence: `server.py`, `evidence/map.json`, `evidence/latest.json`, and `evidence/historical.json`. Complete licensed history remains in ignored `.cache/`.

## Two-minute demo script

| Time | Screen and action | Narration |
|---|---|---|
| 00:00-00:15 | Open the sample team and show the label | Portfolio value alone does not show whether a small team can make payroll. Runway shows how many full payments remain and when the first shortfall occurs. |
| 00:15-00:30 | Show assets, cash flow, and CMC quote time | BTC, ETH, USDC, and USD cash are valued separately. Only the backend requests CMC data; simulation inputs are not sent to CMC. |
| 00:30-00:50 | Show the default custom changes and a real historical option | Custom changes are stress assumptions, not forecasts. Historical options replay validated daily relative moves from real CMC data. |
| 00:50-01:10 | Move reserve from 3 to 6 and then 0 | Strategy A sells monthly as needed; Strategy B raises cash at the start. Both use the same snapshot. At zero reserve the strategies should match. |
| 01:10-01:30 | Return to 6 and inspect the chart, initial sale, and ledger | Every sale reduces holdings and deducts fees. A payment shortfall displays its date and amount. Holding cash also gives up market exposure. |
| 01:30-01:45 | Open the stress matrix and compare scenarios | The matrix compares payment targets across editable assumptions. A pass count is not a market probability. |
| 01:45-02:00 | Download reports and show rules, tests, and API evidence | Inputs, quote time, sales, fees, paths, and assumptions are auditable. The app is deterministic and performs no real trades. |

Check the network before the demo. If using recorded replay, state that it is a replay of captured real quotes rather than live market data. Close editors and terminals containing keys before recording. Never hard-code result values in the narration because they vary with quotes and start date.

## X post draft (not published)

Built Runway for small Web3 teams: how many paydays can your crypto treasury cover? Compare monthly selling with an upfront cash buffer using CoinMarketCap data, transparent assumptions, real historical scenarios, and a full cash-flow ledger. #BuildwithCMC

Add the real DoraHacks submission and demo-video links before publishing. Publication requires explicit user authorization. The project does not execute asset trades.

## Final submission checklist

Based on the [CMC competition site](https://coinmarketcap.com/api/resources/api-hackathon/):

- [ ] Confirm every participant is at least 18, the team has at most four members, and the work is original or clearly identifies the new CMC integration.
- [ ] Register on DoraHacks with the email associated with the CMC account.
- [ ] Recheck the [DoraHacks competition page](https://dorahacks.io/hackathon/coinmarketcap-api-202609/detail) for current fields and track rules.
- [x] Provide a runnable local app and clearly labeled sample team.
- [x] Provide real API code, redacted evidence, endpoint list, and clear success/failure history.
- [x] Validate three shared historical windows for BTC, ETH, and USDC under Startup access.
- [x] Provide README, calculation rules, tests, API notes, demo script, and draft material.
- [ ] Create a public repository and confirm it runs without private dependencies; scan for keys and exclude `.env`, `.idea`, and complete history cache.
- [ ] Provide a deployed demo or recording; localhost is not accessible to judges.
- [ ] Select one track; Data and Visualisation is recommended.
- [ ] After user authorization, publish the X post with submission and video links plus `#BuildwithCMC`.
- [ ] Complete and submit all required fields before **2026-09-30 23:59 UTC / 2026-10-01 07:59 Beijing time**.
- [ ] After submission, verify repository, video, demo permissions, and links; do not mistake a saved draft for a completed submission.

The competition site lists general scoring as: functionality 30, real user value 25, API use 20, code and documentation 15, presentation 10. Track weights remain subject to the live Tracks page. Competition Startup access may end after the deadline; continued operation then requires eligible access or an explicitly labeled recorded-data demo.
