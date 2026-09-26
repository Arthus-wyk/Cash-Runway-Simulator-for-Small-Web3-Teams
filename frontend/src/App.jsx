import React, { useEffect, useRef, useState } from 'react';
import { buildCsv, coins, colors, createInputs, money, requestApi, saveFile, units } from './report.js';
import StressPanel from './StressPanel.jsx';

function NumberField({ id, label, value, onChange, min = '0', max = '1000000000000000', step = 'any', note }) {
  return <label className="field" htmlFor={id}>
    <span>{label}</span>
    <input id={id} type="number" min={min} max={max} step={step} value={value} onChange={onChange} required />
    {note && <small>{note}</small>}
  </label>;
}

function Quantities({ values }) {
  return coins.map(coin => <small key={coin}>{coin} {units(values[coin])}</small>);
}

function StrategyCard({ strategy, index }) {
  return <section className={`panel card ${index ? 'b' : ''}`}>
    <div className="card-head"><span><i className="letter">{strategy.name}</i>{index ? 'Build cash reserve early' : 'Sell monthly as needed'}</span>
      {index === 1 && <span className="badge-outline">Cash buffer</span>}</div>
    <p className="count">{strategy.covered_payments}<span>full monthly payments{strategy.failure ? '' : ' or more'}</span></p>
    <p className="outcome">{strategy.failure
      ? <>First shortfall <b>{strategy.failure.date}</b><br />Payment shortfall <b style={{ color: 'var(--red)' }}>{money(strategy.failure.shortfall)}</b></>
      : <>Covers at least the simulation period<br />No payment shortfall within 12 months</>}</p>
    <div className="card-bottom"><span>Starting cash <b>{money(strategy.reserve_cash)}</b></span><span>Cumulative sale fees <b>{money(strategy.fees)}</b></span></div>
  </section>;
}

function CashChart({ result }) {
  const chartId = React.useId();
  const width = 880, height = 252, left = 68, right = 20, top = 20, bottom = 34;
  const start = Date.parse(result.start), duration = Date.parse(result.end) - start;
  const maximum = Math.max(1, ...result.strategies.flatMap(strategy => strategy.curve.map(point => Number(point.total)))) * 1.08;
  const getX = day => left + (Date.parse(day) - start) / duration * (width - left - right);
  const getY = value => top + (1 - Number(value) / maximum) * (height - top - bottom);
  return <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={`${chartId}-title ${chartId}-description`}>
    <title id={`${chartId}-title`}>Daily remaining assets for both strategies</title>
    <desc id={`${chartId}-description`}>Orange is Strategy A and green is Strategy B. A curve ends at the first payment shortfall. See the ledger below for income, expenses, and remaining holdings.</desc>
    {[0, 1, 2, 3, 4].map(index => {
      const value = maximum * index / 4;
      const day = new Date(start + duration * index / 4).toISOString().slice(0, 10);
      return <g key={index}>
        <line x1={left} y1={getY(value)} x2={width - right} y2={getY(value)} stroke="#e7ebe3" strokeDasharray="3 5" />
        <text x={left - 12} y={getY(value) + 4} textAnchor="end" fontSize="10" fill="#7b867e">${new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value)}</text>
        <text x={getX(day)} y={height - 9} textAnchor="middle" fontSize="10" fill="#7b867e">{day.slice(5).replace('-', '/')}</text>
      </g>;
    })}
    {result.strategies.map((strategy, index) => {
      const color = index ? '#137654' : '#c47738';
      const last = strategy.curve.at(-1);
      return <g key={strategy.name}>
        <polyline points={strategy.curve.map(point => `${getX(point.date).toFixed(2)},${getY(point.total).toFixed(2)}`).join(' ')} fill="none" stroke={color} strokeWidth="2.8" strokeLinejoin="round" />
        <circle cx={getX(last.date)} cy={getY(last.total)} r="4.5" fill={color} stroke="white" strokeWidth="2">
          <title>Strategy {strategy.name} — {last.date} — {money(last.total)}{strategy.failure ? ' — first payment shortfall' : ''}</title>
        </circle>
      </g>;
    })}
  </svg>;
}

function Comparison({ report, ledgerIndex, onLedgerChange }) {
  const result = report.result;
  const total = Number(result.initial_total);
  const [first, second] = result.strategies;
  const difference = second.covered_payments - first.covered_payments;
  const strategy = result.strategies[ledgerIndex];
  let insight = difference > 0 ? `In this scenario, building a cash reserve early covers ${difference} more full payment${difference === 1 ? '' : 's'}.`
    : difference < 0 ? `In this scenario, selling monthly as needed covers ${-difference} more full payment${difference === -1 ? '' : 's'}.`
      : 'In this scenario, both strategies cover the same number of full payments.';
  if (!first.failure && !second.failure) insight = 'Both strategies cover at least the simulation period; this does not establish a longer runway.';
  insight += Number(second.reserve_shortfall) > 1e-18
    ? ` Strategy B cannot fully fund its reserve target and is short by ${money(second.reserve_shortfall)}.`
    : ' Holding cash reduces market exposure but also gives up some upside.';

  return <>
    <section className="valuation" aria-label="Initial asset value and allocation">
      <div><p className="small">{report.market.mode === 'recorded' ? 'Initial assets at recorded quotes — USD' : 'Initial assets at snapshot quotes — USD'}</p><strong>{money(result.initial_total)}</strong></div>
      <div className="composition"><div className="composition-bar">
        {Object.entries(result.allocation).map(([coin, value]) => <span key={coin} style={{ width: `${total ? Number(value) / total * 100 : 0}%`, background: colors[coin] }} />)}
      </div><div className="composition-labels">
        {Object.entries(result.allocation).map(([coin, value]) => <span key={coin} title={money(value)}><i className="key" style={{ background: colors[coin] }} />{coin} {total ? (Number(value) / total * 100).toFixed(0) : 0}%</span>)}
      </div></div>
    </section>
    <div className="cards">{result.strategies.map((item, index) => <StrategyCard key={item.name} strategy={item} index={index} />)}</div>
    <div className="insight">{insight}</div>
    <section className="panel chart-panel">
      <div className="chart-head"><div><h2>How will the treasury change?</h2><p className="small">Daily remaining asset value — USD</p></div>
        <div className="legend"><span><i className="line-key" style={{ background: 'var(--orange)' }} />A Sell monthly as needed</span><span><i className="line-key" style={{ background: 'var(--green)' }} />B Build cash reserve early</span></div></div>
      <div className="chart-wrap"><CashChart result={result} /></div>
      <div className="chart-caption"><span>Income, payments, and fees are included; each curve stops at its first shortfall.</span><span>{result.start} → {result.end}</span></div>
    </section>
    <section className="panel">
      <div className="ledger-head"><div><h2>Every transaction, accounted for.</h2><p className="small">Monthly cash flow and remaining holdings</p></div>
        <div className="segmented" aria-label="Select strategy ledger">{['A', 'B'].map((name, index) => <button key={name} type="button" aria-pressed={ledgerIndex === index} onClick={() => onLedgerChange(index)}>Strategy {name}</button>)}</div></div>
      <div className="table-scroll" tabIndex="0" aria-label="Monthly ledger, horizontally scrollable"><table>
        <thead><tr>{['Payment date', 'Income', 'Due / paid', 'Units sold', 'Net sale proceeds', 'Fees', 'Cash remaining', 'Holdings remaining', 'Total assets', 'Shortfall'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
        <tbody>{strategy.rows.map(row => <tr key={row.date} className={Number(row.shortfall) > 0 ? 'failure' : ''}>
          <td>{row.date}</td><td>{money(row.income)}</td><td>{money(row.expense)}<small>Paid {money(row.paid)}</small></td>
          <td><Quantities values={row.sold} /></td><td>{money(row.sale_net)}</td><td>{money(row.fee)}</td><td>{money(row.cash)}</td>
          <td><Quantities values={row.holdings} /></td><td>{money(row.total)}</td><td>{Number(row.shortfall) > 0 ? money(row.shortfall) : '—'}</td>
        </tr>)}</tbody>
      </table></div>
      <p className="table-note">Initial sale: {coins.map(coin => coin + ' ' + units(strategy.initial_sale.sold[coin])).join(' / ')}; net proceeds {money(strategy.initial_sale.net)}; fees {money(strategy.initial_sale.fee)}. Table amounts are USD and token units show up to 8 decimals; see the JSON report for full precision.</p>
    </section>
    <details className="panel details"><summary>View calculation rules and assumptions</summary><ol>{result.assumptions.map(rule => <li key={rule}>{rule}</li>)}</ol></details>
  </>;
}

export default function App() {
  const [inputs, setInputs] = useState(createInputs);
  const [example, setExample] = useState(true);
  const [scenario, setScenario] = useState('custom');
  const [scenarios, setScenarios] = useState([]);
  const [historyNotice, setHistoryNotice] = useState('Checking historical scenario availability…');
  const [snapshot, setSnapshot] = useState(null);
  const [completed, setCompleted] = useState(null);
  const [ledgerIndex, setLedgerIndex] = useState(0);
  const [marketBusy, setMarketBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('Retrieving CMC quotes…');
  const form = useRef(null);
  const marketRequest = useRef(0);
  const generation = useRef(0);
  const requestKey = JSON.stringify([snapshot?.snapshot_id, scenario, inputs]);
  const report = completed?.report;
  const ready = Boolean(report && completed.key === requestKey && !marketBusy && !error);
  const market = ready ? report.market : snapshot;

  async function loadMarket(mode) {
    const current = ++marketRequest.current;
    generation.current++;
    setSnapshot(null);
    setMarketBusy(true);
    setError('');
    setStatus(mode === 'recorded' ? 'Loading recorded real quotes…' : 'Retrieving CMC quotes…');
    try {
      const value = await requestApi('/api/market?mode=' + mode);
      if (current !== marketRequest.current) return;
      setSnapshot(value);
    } catch (failure) {
      if (current !== marketRequest.current) return;
      setError(failure.message + '. Select “Use recorded real quotes” to try the simulation.');
      setStatus('Market data not loaded; calculation paused');
    } finally {
      if (current === marketRequest.current) setMarketBusy(false);
    }
  }

  useEffect(() => {
    loadMarket('live');
    const controller = new AbortController();
    requestApi('/api/scenarios', { signal: controller.signal }).then(values => {
      if (controller.signal.aborted) return;
      setScenarios(values);
      const unavailable = values.filter(value => !value.available);
      setHistoryNotice(unavailable.length
        ? `${unavailable.length}/${values.length} historical scenarios are unavailable because complete historical data has not been retrieved. Try a custom scenario or see the README for setup.` : '');
    }).catch(failure => {
      if (!controller.signal.aborted) setHistoryNotice('Failed to read historical scenario status: ' + failure.message);
    });
    return () => { controller.abort(); marketRequest.current++; generation.current++; };
  }, []);

  useEffect(() => {
    const current = ++generation.current;
    if (!snapshot) return;
    if (!form.current.checkValidity()) {
      setError('Complete all inputs and check their ranges: amounts cannot be negative, expenses must be positive, and payment day must be 1–31.');
      setStatus('Inputs are incomplete; results have not been updated');
      return;
    }
    setError('');
    setStatus('Updating comparison…');
    const controller = new AbortController();
    // Sliders only recalculate; cancel stale requests and check versions before applying responses.
    const timer = setTimeout(async () => {
      try {
        const value = await requestApi('/api/simulate', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
          body: JSON.stringify({ snapshot_id: snapshot.snapshot_id, scenario, inputs }),
        });
        if (current !== generation.current || controller.signal.aborted) return;
        setCompleted({ key: requestKey, report: value });
        setStatus('Comparison updated — same treasury, cash flow, and market path');
      } catch (failure) {
        if (current !== generation.current || controller.signal.aborted) return;
        setError(failure.message);
        setStatus('Calculation incomplete; any results below are from the previous calculation');
      }
    }, 120);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [inputs, scenario, snapshot, requestKey]);

  function updateInput(event, group, name) {
    generation.current++;
    const { value } = event.target;
    setInputs(previous => group ? { ...previous, [group]: { ...previous[group], [name]: value } } : { ...previous, [name]: value });
    setExample(false);
  }

  function resetInputs() {
    generation.current++;
    setInputs(createInputs());
    setScenario('custom');
    setExample(true);
  }

  return <div className="shell">
    <header className="topbar"><div className="brand"><span className="mark" aria-hidden="true">↗</span>Runway<small>TEAM TREASURY LAB</small></div><div className="topright"><span>Give your small team room for what comes next</span><span><i className="dot" />Powered by CMC data</span></div></header>
    <section className="intro"><div><div className="eyebrow">PLAN FOR PAYDAY, NOT JUST PRICE.</div><h1>See the next payday clearly.</h1><p>If the market changes, how long can your team keep going? Compare monthly sales with an upfront cash reserve.</p></div>
      <div className="export-buttons"><button type="button" disabled={!ready} onClick={() => saveFile('runway-comparison.csv', buildCsv(report), 'text/csv;charset=utf-8')}>Download ledger CSV ↓</button><button type="button" className="download" disabled={!ready} onClick={() => saveFile('runway-comparison.json', JSON.stringify(report, null, 2), 'application/json')}>Download full report ↓</button></div></section>
    <p className="stress-link"><a href="#stress-testing">How much cash should you hold? Open payment targets and stress testing ↓</a></p>
    <form id="settings" ref={form} noValidate onSubmit={event => event.preventDefault()}>
      <div className="workspace"><aside className="panel sidebar">
        <div className="section-title"><h2><span className="section-num">01</span>Team treasury</h2><span className="tag">{example ? 'Sample team' : 'Custom team'}</span></div>
        <p className="small">Enter token holdings and USD cash.</p>
        {coins.map((coin, index) => <div className="asset" key={coin}>
          <span className={`coin ${coin.toLowerCase()}`} aria-hidden="true">{['₿', 'Ξ', '$'][index]}</span><label htmlFor={coin.toLowerCase()}>{coin}</label>
          <input id={coin.toLowerCase()} type="number" min="0" max="1000000000000" step="any" required aria-label={`${coin} holdings`} value={inputs.holdings[coin]} onChange={event => updateInput(event, 'holdings', coin)} />
        </div>)}
        <div className="asset"><span className="coin usd" aria-hidden="true">$</span><label htmlFor="cash">Cash</label><input id="cash" type="number" min="0" max="1000000000000000" step="any" required aria-label="USD cash balance" value={inputs.cash} onChange={event => updateInput(event, null, 'cash')} /></div>
        <div className="divider" /><h2><span className="section-num">02</span>Monthly cash flow</h2>
        <NumberField id="expense" label="Payroll and operating expenses — USD / month" min="0.01" value={inputs.expense} onChange={event => updateInput(event, null, 'expense')} />
        <NumberField id="income" label="Recurring income — USD / month" value={inputs.income} onChange={event => updateInput(event, null, 'income')} note="May be 0; arrives before the monthly payment." />
        <div className="twocol"><NumberField id="payment-day" label="Monthly payment day" min="1" max="31" step="1" value={inputs.payment_day} onChange={event => updateInput(event, null, 'payment_day')} note="Uses month-end in shorter months" />
          <NumberField id="fee" label="Sale fee — %" max="20" value={inputs.fee_percent} onChange={event => updateInput(event, null, 'fee_percent')} note="Editable sample assumption" /></div>
        <label className="field" htmlFor="start"><span>Simulation start date — UTC</span><input id="start" type="date" min="2000-01-01" max="2100-12-31" required value={inputs.start} onChange={event => updateInput(event, null, 'start')} /></label>
        <button type="button" className="reset" onClick={resetInputs}>↺ Restore sample team</button>
        <p className="footnote">Sample assets and cash flow are for exploration only and do not represent a real team. Calculations run locally without connecting a wallet.</p>
      </aside><main className="content">
        <section className="panel controls" aria-labelledby="scenario-title"><div className="scenario-row"><h2 id="scenario-title"><span className="section-num">03</span>If the market changes</h2>
          <select aria-label="Market scenario" value={scenario} onChange={event => { generation.current++; setScenario(event.target.value); setExample(false); }}>
            <option value="custom">Custom — one-time change</option>{scenarios.map(value => <option key={value.id} value={value.id} disabled={!value.available}>{value.label}{value.available ? ' — real history' : ' — unavailable'}</option>)}
          </select></div>
          {scenario === 'custom' && <div className="shock-fields">{coins.map(coin => <NumberField key={coin} id={`shock-${coin.toLowerCase()}`} label={`${coin} change — %`} min="-100" max="1000" value={inputs.shocks[coin]} onChange={event => updateInput(event, 'shocks', coin)} />)}</div>}
          <p className="footnote">{scenario === 'custom' ? 'Build the cash reserve first, apply one price change the next day, then hold prices flat. The simulation runs for 12 months.' : 'Apply real historical daily relative changes to the starting quote. This replays relative days and is not a future forecast.'}</p>
          <div className="reserve"><div><h3>Strategy B: hold <strong>{inputs.reserve_months}</strong> months of expenses in cash</h3><p className="small">Existing cash counts; any required conversion happens once at the start.</p></div><div><input aria-label="Cash reserve months" type="range" min="0" max="12" step="1" value={inputs.reserve_months} onChange={event => updateInput(event, null, 'reserve_months')} /><div className="ticks"><span>0 months</span><span>6 months</span><span>12 months</span></div></div></div>
        </section>
        {historyNotice && <div className="notice">{historyNotice}</div>}
        {market?.warning && <div className="notice">{market.warning}</div>}
        {error && <div className="notice error" role="alert">{error}</div>}
        <div className="status-line" role="status" aria-live="polite">{status}</div>
        {!report && !error && <div className="loading panel">Calculating the team runway…</div>}
        {report && <div className={`results ${ready ? '' : 'pending'}`} aria-busy={!ready} inert={!ready}>
          <Comparison report={report} ledgerIndex={ledgerIndex} onLedgerChange={setLedgerIndex} />
        </div>}
        <div className="source"><div>{market
          ? `${market.mode === 'recorded' ? 'Recorded replay' : 'Pinned market snapshot'} — CoinMarketCap — quote time ${market.as_of.replace('T', ' ').replace('+00:00', ' UTC')} — credits used: ${market.credit_count ?? 'unknown'}`
          : 'Data source: CoinMarketCap — read-only market data'}</div>
          <div className="source-buttons"><button type="button" disabled={marketBusy} onClick={() => loadMarket('live')}>Refresh live market data</button><button type="button" disabled={marketBusy} onClick={() => loadMarket('recorded')}>Use recorded real quotes</button></div>
        </div>
      </main></div>
    </form>
    <StressPanel inputs={inputs} snapshot={snapshot} renderDetail={(value, index, onChange) => <Comparison report={value} ledgerIndex={index} onLedgerChange={onChange} />} />
    <footer className="footer"><span>Runway / Built with CoinMarketCap</span><span>Scenario simulation, not a forecast — no real trades</span></footer>
  </div>;
}
