import React, { useEffect, useRef, useState } from 'react';
import { coins, money, requestApi, saveFile, units } from './report.js';
import { buildStressCsv } from './stressReport.js';

export default function StressPanel({ inputs, snapshot, renderDetail }) {
  const [target, setTarget] = useState('9');
  const [definitions, setDefinitions] = useState([]);
  const [enabled, setEnabled] = useState([]);
  const [completed, setCompleted] = useState(null);
  const [selection, setSelection] = useState(null);
  const [detail, setDetail] = useState(null);
  const [ledgerIndex, setLedgerIndex] = useState(1);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [detailBusy, setDetailBusy] = useState(false);
  const form = useRef(null);
  const runRequest = useRef(0);
  const detailRequest = useRef(0);
  const abortRun = useRef(null);
  const abortDetail = useRef(null);
  // The single-scenario slider and one-time shock do not affect the stress test; treasury inputs still carry over.
  const funds = { ...inputs, reserve_months: 0 };
  delete funds.shocks;
  const selectedDefinitions = definitions.filter(item => enabled.includes(item.id));
  const requestKey = JSON.stringify({ snapshot_id: snapshot?.snapshot_id, inputs: funds, target, scenarios: selectedDefinitions });
  const latestKey = useRef(requestKey);
  latestKey.current = requestKey;
  const report = completed?.report;
  const ready = Boolean(report && completed.key === requestKey && !busy);
  const row = ready && selection ? report.stress.rows[selection.reserve] : null;
  const cell = row?.cells.find(item => item.scenario_id === selection.scenarioId);
  const detailReady = ready && detail && !detailBusy && detail.key === JSON.stringify(selection);

  useEffect(() => {
    const controller = new AbortController();
    requestApi('/api/stress-presets', { signal: controller.signal }).then(values => {
      setDefinitions(values);
      setEnabled(values.map(item => item.id));
    }).catch(failure => { if (!controller.signal.aborted) setError('Failed to load scenarios: ' + failure.message); });
    return () => { controller.abort(); abortRun.current?.abort(); abortDetail.current?.abort(); };
  }, []);

  useEffect(() => {
    abortRun.current?.abort(); abortDetail.current?.abort();
    setBusy(false); setDetailBusy(false); setError('');
  }, [requestKey]);

  function editNode(identifier, index, coin, value) {
    setDefinitions(previous => previous.map(item => item.id === identifier
      ? { ...item, nodes: item.nodes.map((node, position) => position === index ? { ...node, changes: { ...node.changes, [coin]: value } } : node) }
      : item));
  }

  async function loadDetail(value, reserve, scenarioId, key) {
    const current = ++detailRequest.current;
    abortDetail.current?.abort();
    const controller = new AbortController();
    abortDetail.current = controller;
    const chosen = { reserve, scenarioId };
    setSelection(chosen); setDetail(null); setDetailBusy(true); setError(''); setLedgerIndex(1);
    const source = value.stress.scenarios.find(item => item.id === scenarioId);
    try {
      const data = await requestApi('/api/simulate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ snapshot_id: value.market.snapshot_id, inputs: { ...value.inputs, reserve_months: reserve },
          scenario_definition: { id: source.id, label: source.label, nodes: source.nodes } }),
      });
      if (controller.signal.aborted || current !== detailRequest.current || key !== latestKey.current) return;
      setDetail({ key: JSON.stringify(chosen), report: data });
    } catch (failure) {
      if (!controller.signal.aborted && current === detailRequest.current && key === latestKey.current) setError('Failed to load the ledger: ' + failure.message);
    } finally {
      if (current === detailRequest.current && key === latestKey.current) setDetailBusy(false);
    }
  }

  async function runAnalysis(event) {
    event.preventDefault();
    if (!form.current.checkValidity()) {
      setError('Check the target (an integer from 1 to 12) and selected scenario nodes (-100% to +1000%). Expand each path to correct invalid inputs.');
      return;
    }
    if (!snapshot || !selectedDefinitions.length) return;
    const current = ++runRequest.current;
    const key = requestKey;
    abortRun.current?.abort(); abortDetail.current?.abort();
    const controller = new AbortController();
    abortRun.current = controller;
    setBusy(true); setError(''); setDetail(null);
    try {
      const data = await requestApi('/api/stress', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ snapshot_id: snapshot.snapshot_id, inputs: funds, target_payments: target, scenarios: selectedDefinitions }),
      });
      if (controller.signal.aborted || current !== runRequest.current || key !== latestKey.current) return;
      setCompleted({ key, report: data });
      await loadDetail(data, data.stress.minimum_reserve ?? 0, data.stress.scenarios[0].id, key);
    } catch (failure) {
      if (!controller.signal.aborted && current === runRequest.current && key === latestKey.current) setError(failure.message);
    } finally {
      if (current === runRequest.current && key === latestKey.current) setBusy(false);
    }
  }

  return <section id="stress-testing" className="stress-section">
    <div className="section-title"><div><div className="eyebrow">FROM SIMULATION TO DECISION</div><h2>04 Payment targets and stress testing</h2></div><a href="#settings">Edit team treasury ↑</a></div>
    <p>Use the treasury and monthly cash flow above to compare cash reserves from 0 to 12 months. Set a payment target, then select the hypothetical scenarios to withstand.</p>
    <form ref={form} noValidate onSubmit={runAnalysis} className="panel controls stress-form">
      <label className="field" htmlFor="target-payments"><span>How many consecutive monthly payments should be completed?</span>
        <input id="target-payments" type="number" min="1" max="12" step="1" required value={target} onChange={event => setTarget(event.target.value)} />
        <small>For example, 9 means making 9 full consecutive payments from the first payment date; it does not guarantee 9 safe future months.</small></label>
      <p className="small">Every path below is hypothetical and editable. Percentages are relative to the starting quote; month 0 is 0%, with linear interpolation over calendar days between nodes. Real history remains available in the single-scenario selector above.</p>
      {!definitions.length && <p>Loading hypothetical scenarios. Refresh the page if loading fails.</p>}
      <div className="scenario-editors">{definitions.map(item => <div key={item.id} className="scenario-editor">
        <label className="scenario-check"><input type="checkbox" checked={enabled.includes(item.id)} onChange={event => setEnabled(previous => event.target.checked ? [...previous, item.id] : previous.filter(id => id !== item.id))} />{item.label}<span className="tag">Hypothetical</span></label>
        <details><summary>View / edit the {item.label} path</summary>
          <fieldset disabled={!enabled.includes(item.id)}><legend>Change from starting quote (%)</legend>
            <div className="node-grid"><span>Node</span>{coins.map(coin => <strong key={coin}>{coin}</strong>)}
              {item.nodes.map((node, index) => <React.Fragment key={node.month}><span>Month {node.month}</span>
                {coins.map(coin => <input key={coin} type="number" min="-100" max="1000" step="any" required
                  aria-label={`${item.label}, month ${node.month}, ${coin} change`} value={node.changes[coin]}
                  onChange={event => editNode(item.id, index, coin, event.target.value)} />)}</React.Fragment>)}
            </div>
          </fieldset>
        </details>
      </div>)}</div>
      <div className="stress-actions"><button type="submit" className="download" disabled={!snapshot || busy || !selectedDefinitions.length}>{busy ? 'Calculating…' : 'Run stress test'}</button>
        <span className="small">{!snapshot ? 'Load market data or select recorded replay above first.' : !selectedDefinitions.length ? 'Select at least one scenario.' : 'Compares 13 reserve levels without additional market requests.'}</span></div>
    </form>
    {error && <div className="notice error" role="alert">{error}</div>}
    <p role="status" className="status-line">{busy ? 'Calculating stress test…' : report && !ready ? 'Inputs or market data changed. Run again; the old matrix and report are disabled.' : ready ? 'Stress test complete. Select a matrix cell to view evidence.' : 'Stress test has not been run.'}</p>
    {report && <div className={ready ? 'stress-results' : 'stress-results pending'} inert={!ready}>
      <div className="notice">{report.stress.limitation}</div>
      <div className="insight"><strong>{report.stress.minimum_reserve === null
        ? 'No feasible option: from 0 to 12 months, no reserve level both meets every scenario target and is fully funded.'
        : `Minimum fully funded reserve meeting all selected scenario targets: ${report.stress.minimum_reserve} months.`}</strong>
        <p>Target: complete {report.stress.target_payments} consecutive payments. This filter compares reserve levels only and does not identify an overall optimal strategy. A shortfall may still occur after the target is met.</p></div>
      <div className="small">{report.market.mode === 'recorded' ? 'Recorded replay' : 'Pinned market snapshot'} — quote time {report.market.as_of} — {report.market.warning || 'CMC starting quotes followed by hypothetical paths'}</div>
      <div className="panel table-scroll stress-matrix" tabIndex="0" aria-label="Reserve and scenario matrix, horizontally scrollable"><table>
        <caption>Each cell shows full consecutive payments / target of {report.stress.target_payments}; select a cell to view the ledger</caption>
        <thead><tr><th scope="col">Cash reserve</th>{report.stress.scenarios.map(item => <th scope="col" key={item.id}>{item.label} (hypothetical)</th>)}<th scope="col">Scenarios meeting target</th><th scope="col">Reserve funded</th></tr></thead>
        <tbody>{report.stress.rows.map(item => <tr key={item.reserve_months}>
          <th scope="row">{item.reserve_months} months{item.reserve_months === report.stress.minimum_reserve ? ' — minimum feasible' : ''}</th>
          {item.cells.map(value => <td key={value.scenario_id}><button type="button" className={value.meets_target ? 'pass-cell' : 'fail-cell'}
            aria-label={`${item.reserve_months}-month reserve, ${value.label}, ${value.covered_payments} payments completed, ${value.meets_target ? 'target met' : 'target missed'}`}
            aria-pressed={selection?.reserve === item.reserve_months && selection?.scenarioId === value.scenario_id}
            onClick={() => loadDetail(report, item.reserve_months, value.scenario_id, requestKey)}>
            {value.covered_payments} / {report.stress.target_payments} — {value.meets_target ? 'met' : 'missed'}</button></td>)}
          <td>{item.passed_count} / {item.cells.length}</td><td>{item.fully_funded ? 'Fully funded' : `Short ${money(item.reserve_shortfall)}`}</td>
        </tr>)}</tbody>
      </table></div>
      {row && cell && <section className="panel controls decision-card" aria-label="Strategy trade-off explanation">
        <h2>{row.reserve_months}-month reserve: strategy trade-offs</h2>
        <p>Scenarios meeting target: {row.cells.filter(item => item.meets_target).map(item => item.label).join(', ') || 'None'}.</p>
        <p>Scenarios missing target: {row.cells.filter(item => !item.meets_target).map(item => item.label).join(', ') || 'None'}.</p>
        <p>{row.earliest_failure ? `Earliest shortfall among selected scenarios: ${row.earliest_failure.date}, ${row.earliest_failure.label}, short by ${money(row.earliest_failure.shortfall)}.` : 'No selected scenario has a payment shortfall during the full simulation period.'}</p>
        <p>Initial sale: {coins.map(coin => `${coin} ${units(row.initial_sale.sold[coin])}`).join(' / ')}; net proceeds {money(row.initial_sale.net)}; fees {money(row.initial_sale.fee)}.</p>
        <p>Initial cash target {money(row.reserve_target)}, actual cash {money(row.reserve_cash)}. {row.fully_funded ? 'The reserve is fully funded.' : `The target is short by ${money(row.reserve_shortfall)}; results below use the cash actually raised.`}</p>
        <h3>Current evidence: {cell.label} (hypothetical)</h3>
        <p>{cell.covered_payments} full payments; cumulative sale fees {money(cell.fees)} (including initial fees).</p>
        <p>{cell.failure ? `First shortfall on ${cell.failure.date}: ${money(cell.failure.shortfall)}.` : 'No payment shortfall during this simulation period.'}</p>
        <p>{cell.terminal_difference === null ? cell.comparison_note
          : `At the shared end date ${cell.comparison_date}, Strategy B has ${money(Math.abs(Number(cell.terminal_difference)))} ${Number(cell.terminal_difference) < 0 ? 'less' : 'more'} than Strategy A. ${Number(cell.terminal_difference) < 0 ? 'On this path, that is the ending-asset cost of holding cash.' : 'On this path, holding cash does not reduce ending assets.'}`}</p>
        <p className="small">The ending difference includes market exposure and fees; it is not an additional fee. Not every scenario rises. Select “Continued growth” to inspect that trade-off.</p>
      </section>}
      <div className="stress-actions"><button type="button" disabled={!ready} onClick={() => saveFile('runway-stress-matrix.csv', buildStressCsv(report), 'text/csv;charset=utf-8')}>Download stress matrix CSV</button>
        <button type="button" disabled={!detailReady} onClick={() => saveFile('runway-stress-report.json', JSON.stringify({ ...report, selection, selected_report: detail.report }, null, 2), 'application/json')}>Download decision report JSON</button>
        <span className="small">The JSON includes the target, all scenario nodes and daily ratios, matrix, market snapshot, and full ledger for the selected cell.</span></div>
      {detailBusy && <p role="status">Loading the selected strategy curve and ledger…</p>}
      {detailReady && <div className="results stress-detail"><h2>Evidence ledger — {cell.label} — {row.reserve_months}-month reserve</h2>{renderDetail(detail.report, ledgerIndex, setLedgerIndex)}</div>}
    </div>}
  </section>;
}
