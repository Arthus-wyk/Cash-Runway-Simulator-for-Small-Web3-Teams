import assert from 'node:assert/strict';
import test from 'node:test';
import { buildCsv } from './report.js';

test('CSV preserves precision, provenance, ledgers, quotes, and newlines', () => {
  const holdings = { BTC: '0.1234567890123456789', ETH: '2', USDC: '3' };
  const sale = { sold: holdings, net: '10', fee: '0.01' };
  const report = {
    generated_at: '2026-01-01',
    market: { source: 'CMC', mode: 'recorded', as_of: '2025-12-31', stale: true, warning: 'Recorded "replay"\nNot live' },
    scenario: { label: 'Custom' }, inputs: { cash: '1.000000000000000001' },
    result: { start: '2026-01-01', assumptions: ['Rule'], strategies: [
      { name: 'A', initial_sale: sale, reserve_cash: '10', initial_holdings: holdings,
        curve: [{ total: '100' }], rows: [{ date: '2026-02-01', income: '0', expense: '10', paid: '10',
          shortfall: '0', sold: holdings, sale_net: '10', fee: '0.01', cash: '0', holdings, total: '90' }] },
    ] },
  };
  const csv = buildCsv(report);
  assert.ok(csv.startsWith('\uFEFF'));
  assert.ok(csv.includes('"Recorded ""replay""\nNot live"'));
  assert.ok(csv.includes('"Initial reserve"'));
  assert.ok(csv.includes('"Monthly payment"'));
  assert.ok(csv.includes('"0.1234567890123456789"'));
  assert.ok(csv.includes('1.000000000000000001'));
  assert.ok(csv.includes('"recorded"'));
  assert.ok(csv.includes('\r\n'));
});
