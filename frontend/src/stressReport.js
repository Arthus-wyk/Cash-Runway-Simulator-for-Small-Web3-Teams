import { coins } from './report.js';

export function buildStressCsv(report) {
  const { stress, market } = report;
  const rows = [
    ['Runway Stress Test', 'Hypothetical scenarios, not a forecast'], ['Generated at', report.generated_at],
    ['Market source', market.source], ['Market mode', market.mode], ['Market time', market.as_of],
    ['Market snapshot', market.snapshot_id], ['Market note', market.warning], ['Inputs', JSON.stringify(report.inputs)],
    ['Target consecutive payments', stress.target_payments], ['Minimum fully funded reserve meeting every target', stress.minimum_reserve ?? 'No feasible option'],
    ['Path rule', stress.path_rule], ['Limitation', stress.limitation], ...stress.assumptions.map(rule => ['Assumption', rule]),
    ...stress.scenarios.map(scenario => ['Hypothetical scenario nodes', scenario.label, JSON.stringify(scenario.nodes)]), [],
    ['Reserve months', 'Scenario', 'Completed payments', 'Target met', 'First shortfall date', 'Shortfall USD', 'Reserve fully funded', 'Cash target USD',
      'Initial cash USD', 'Reserve shortfall USD', 'Initial BTC sold', 'Initial ETH sold', 'Initial USDC sold', 'Initial net proceeds USD',
      'Initial fees USD', 'Cumulative fees USD', 'Ending B minus A USD', 'Comparison date', 'Comparison basis'],
  ];
  for (const row of stress.rows) {
    for (const cell of row.cells) {
      rows.push([row.reserve_months, cell.label, cell.covered_payments, cell.meets_target ? 'Yes' : 'No',
        cell.failure?.date ?? '', cell.failure?.shortfall ?? '0', row.fully_funded ? 'Yes' : 'No',
        row.reserve_target, row.reserve_cash, row.reserve_shortfall, ...coins.map(coin => row.initial_sale.sold[coin]),
        row.initial_sale.net, row.initial_sale.fee, cell.fees, cell.terminal_difference ?? 'Not applicable',
        cell.comparison_date ?? '', cell.comparison_note]);
    }
  }
  // Preserve negative values and decimal precision while preventing editable labels from becoming formulas.
  const escapeCell = value => {
    let text = String(value ?? '');
    if (/^[\s]*[=+@-]/.test(text) && !/^-?\d+(\.\d+)?$/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  };
  return '\uFEFF' + rows.map(row => row.map(escapeCell).join(',')).join('\r\n');
}
