export const coins = ['BTC', 'ETH', 'USDC'];
export const colors = { BTC: '#d8a36f', ETH: '#8194b0', USDC: '#82b99b', USD: '#234b3d' };
export const money = value => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(Number(value));
export const units = value => new Intl.NumberFormat('en-US', { maximumFractionDigits: 8 }).format(Number(value));

export function createInputs() {
  return {
    holdings: { BTC: '0.5', ETH: '8', USDC: '6000' }, cash: '12000', income: '1000', expense: '8500',
    payment_day: '25', start: new Date().toISOString().slice(0, 10), fee_percent: '0.1',
    reserve_months: '3', shocks: { BTC: '-35', ETH: '-45', USDC: '0' },
  };
}

export async function requestApi(path, options) {
  const response = await fetch(path, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error('The service did not return valid data. Check that the FastAPI backend is running.');
  }
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}

export function saveFile(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function buildCsv(report) {
  // Export backend decimal strings directly without floating-point conversion.
  const rows = [
    ['Runway Comparison Ledger', 'Simulation, not a forecast'], ['Generated at', report.generated_at],
    ['Data source', report.market.source], ['Quote mode', report.market.mode], ['Quote time', report.market.as_of],
    ['Stale/replay', String(report.market.stale)], ['Market note', report.market.warning],
    ['Scenario', report.scenario.label], ['Inputs', JSON.stringify(report.inputs)],
    ...report.result.assumptions.map(rule => ['Assumption', rule]), [],
    ['Strategy', 'Date', 'Type', 'Income USD', 'Due USD', 'Paid USD', 'Shortfall USD', 'BTC sold', 'ETH sold', 'USDC sold',
      'Net sale proceeds USD', 'Fees USD', 'Cash remaining USD', 'BTC remaining', 'ETH remaining', 'USDC remaining', 'Total assets USD'],
  ];
  for (const strategy of report.result.strategies) {
    rows.push([strategy.name, report.result.start, 'Initial reserve', 0, 0, 0, 0,
      ...coins.map(coin => strategy.initial_sale.sold[coin]), strategy.initial_sale.net, strategy.initial_sale.fee,
      strategy.reserve_cash, ...coins.map(coin => strategy.initial_holdings[coin]), strategy.curve[0].total]);
    for (const row of strategy.rows) {
      rows.push([strategy.name, row.date, 'Monthly payment', row.income, row.expense, row.paid, row.shortfall,
        ...coins.map(coin => row.sold[coin]), row.sale_net, row.fee, row.cash,
        ...coins.map(coin => row.holdings[coin]), row.total]);
    }
  }
  const escapeCell = value => '"' + String(value ?? '').replace(/"/g, '""') + '"';
  return '\uFEFF' + rows.map(row => row.map(escapeCell).join(',')).join('\r\n');
}
