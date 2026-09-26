import assert from 'node:assert/strict';
import test from 'node:test';
import { buildStressCsv } from './stressReport.js';

test('stress report preserves targets, provenance, precision, and incomparable totals without running formulas', () => {
  const report = { generated_at: '2026-09-22', market: { mode: 'recorded', as_of: '2026-09-20', snapshot_id: 'snapshot', source: 'CMC', warning: 'Replay' },
    inputs: { expense: '100' }, stress: { target_payments: 6, minimum_reserve: null, path_rule: 'Hypothetical', limitation: 'Not a probability',
      assumptions: ['Test rule'], scenarios: [{ id: 'growth', label: '=1+1', nodes: [] }], rows: [{ reserve_months: 3, passed_count: 0, all_passed: false,
        fully_funded: false, reserve_cash: '10', reserve_target: '300', reserve_shortfall: '290', initial_sale: { sold: { BTC: '0.1234567890123456789', ETH: '0', USDC: '0' }, net: '10', fee: '0.01' },
        cells: [{ scenario_id: 'growth', label: '=1+1', covered_payments: 0, meets_target: false, failure: { date: '2026-10-01', shortfall: '90' }, fees: '0.01', terminal_difference: null, comparison_date: null, comparison_note: 'Not applicable' }] }] } };
  const csv = buildStressCsv(report);
  assert.ok(csv.startsWith('\uFEFF'));
  assert.ok(csv.includes('"Runway Stress Test"'));
  assert.ok(csv.includes('"Not applicable"'));
  assert.ok(csv.includes('0.1234567890123456789'));
  assert.ok(csv.includes("'=1+1"));
  assert.ok(csv.includes('Not applicable'));
  assert.ok(csv.includes('recorded'));
  assert.ok(csv.includes('Not a probability'));
});
