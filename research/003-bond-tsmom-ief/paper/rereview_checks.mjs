#!/usr/bin/env node
// rereview_checks.mjs: Tester's re-review checks of the FIXED monthly paper runner (desk commit db0bced) against the
// findings of RUNNER_REVIEW.md. Written 2026-10-22 by the Tester agent; it did not write the runner or the fixes.
//
// What is real:    run-monthly-core.mjs (runMonthly, stopCheck, stopRecord), the risk engine (risk.mjs bound to a temp root
//                  holding a COPY of the desk's config/risk.json, the study003 spec and backtest file, no KILL file unless a
//                  check raises one), the desk journal (journal.mjs writing to a temp trades.jsonl).
// What is stubbed: placeOrder (records the call and the ORDER of writeState/placeOrder calls), getOrderByClientId (fills at
//                  the quote, overridable per check), state (in memory), execution records (temp dir), run log (in memory).
// No network, no credentials, nothing written under ops/ or paper-log/. Run from this folder:
//   DESK=<desk workspace root> node rereview_checks.mjs
// Checks marked "bar under 2 h" substitute a fresh signal_bar_time on buy orders only (as runner_dryrun.mjs does), so the
// path past the bar-age gate (condition 3, owner's) can be exercised; everything else reaches the engine unchanged.
import { mkdtempSync, mkdirSync, copyFileSync, existsSync, readFileSync, writeFileSync, unlinkSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const DESK = process.env.DESK;
if (!DESK) { console.error('set DESK to the desk workspace root'); process.exit(2); }
const T = join(DESK, 'ops', 'trading');
const core = await import(pathToFileURL(join(T, 'bin', 'run-monthly-core.mjs')));
const risk = await import(pathToFileURL(join(T, 'lib', 'risk.mjs')));
const journal = await import(pathToFileURL(join(T, 'lib', 'journal.mjs')));
const { runMonthly, stopCheck, stopRecord, writeRecordOnce, freshState, sleeveCash, STRATEGY_ID } = core;

const OK_MD = `## Strategy: ${STRATEGY_ID} v1 -> **CLEARED for paper at the 2 250 USD sleeve**\n`;
const RISK = { status: 'reviewed', allowed_hosts: ['paper-api.alpaca.markets', 'data.alpaca.markets'] };
const D = (s) => new Date(s);
const NOV2 = D('2026-11-02T20:50:00Z'), NOV3 = D('2026-11-03T20:50:00Z'), NOV4 = D('2026-11-04T20:50:00Z');
const REC = (over = {}) => ({ strategy_id: STRATEGY_ID, strategy_version: '1', status: 'ok', signal_date: '2026-10-30', execution_date: '2026-11-02',
  holding_before: 'BIL', target: 'IEF', mom: 0.0123, switch: true, run_at_utc: '2026-10-30T22:05:00Z', ...over });
const REC_IEF_TO_BIL = REC({ holding_before: 'IEF', target: 'BIL', mom: -0.0042 });

const results = [];
const check = (id, name, ok, detail) => { results.push({ id, name, ok, detail }); console.log(`${ok ? 'PASS' : 'FAIL'} [${id}] ${name}: ${detail}`); };
const r2 = (x) => Math.round(x * 100) / 100;

function tempRoot() {
  const root = mkdtempSync(join(tmpdir(), 'study003-rereview-'));
  for (const d of ['config', 'strategies', 'journal', 'state']) mkdirSync(join(root, 'ops', 'trading', d), { recursive: true });
  copyFileSync(join(T, 'config', 'risk.json'), join(root, 'ops', 'trading', 'config', 'risk.json'));
  for (const f of [`${STRATEGY_ID}.md`, `${STRATEGY_ID}-backtest.json`]) copyFileSync(join(T, 'strategies', f), join(root, 'ops', 'trading', 'strategies', f));
  return root;
}
const describeState = (s) => `h=${s.holding ?? '-'}:${s.qty} cash=${s.sleeve_cash_usd ?? 'n/a'} ps=${s.pending_sell?.client_order_id ?? '-'} pb=${s.pending_buy?.client_order_id ?? '-'} eb=${s.engine_blocked ? `${s.engine_blocked.retries}@${s.engine_blocked.date}` : '-'} lsd=${s.last_signal_date} nsh=${s.no_stop_holding ?? '-'}`;

// A harness around runMonthly. o: { id, now, state, record, quotes {SYM: [bid, ask]}, positions(state) -> [], freshBar (default true),
//   fills(order) -> fill, placeOrderThrows, killBeforeBinding, decisionDates, root (share a journal across runs) }
function mk(o) {
  const root = o.root || tempRoot();
  const journalFile = join(root, 'ops', 'trading', 'journal', 'trades.jsonl');
  const execDir = o.execDir || join(root, 'executions');
  const engine = risk._engineForTests(root);
  const seq = []; const calls = { engine: [], orders: [], entries: [], exits: [], log: [] };
  let state = o.state === undefined ? null : o.state;
  let now = o.now;
  const quotes = () => Object.fromEntries(Object.entries(o.quotes || { IEF: [94.98, 95.02], BIL: [91.49, 91.51] })
    .map(([s, [bid, ask]]) => [s, { bid, ask, time: new Date(now.getTime() - 30e3).toISOString() }]));
  const positions = () => (o.positions ? o.positions(state) : (state?.qty > 0 ? [{ symbol: state.holding, qty: String(state.qty), side: 'long', market_value: String(r2(state.qty * quotes()[state.holding].bid)) }] : []));
  const live = () => ({ now: now.toISOString(), hosts: ['paper-api.alpaca.markets', 'data.alpaca.markets'],
    account: { equity: '100000', cash: '90000', buying_power: '180000', status: 'ACTIVE' }, positions: positions(), quotes: quotes(),
    day_start_equity: 100000, orders_today: 0, recent_orders: [], open_orders: [] });
  const riskCheck = (ord, s) => {
    const order = (o.freshBar ?? true) && ord.side === 'buy' ? { ...ord, signal_bar_time: new Date(now.getTime() - 30 * 60e3).toISOString() } : ord;
    if (o.killBeforeBinding && ord.side === 'buy' && ord.journal_entry_id) writeFileSync(join(root, 'ops', 'trading', 'KILL'), '{"reason":"test"}\n'); // a kill switch raised between pre-check and the binding call
    const rc = engine(order, s);
    calls.engine.push({ side: ord.side, symbol: ord.symbol, qty: ord.qty, jid: !!ord.journal_entry_id, approved: rc.approved, reasons: rc.reasons });
    return rc;
  };
  const defaultFill = (ord) => { const q = quotes()[ord.symbol]; return { status: 'filled', filled_qty: ord.qty, filled_avg_price: String(ord.side === 'sell' ? r2(q.bid - 0.01) : r2(q.ask + 0.01)) }; };
  const deps = {
    runId: `RR-${o.id}`, now: () => now, record: o.record, mode: 'execute', baseUrl: 'https://paper-api.alpaca.markets', params: {},
    readDecisionMd: () => OK_MD, readRisk: () => RISK, baselineRef: 'benchmarks/baseline.json@rereview',
    readState: () => state, writeState: (s) => { seq.push(`writeState[${describeState(s)}]`); state = s; },
    readDecisionRecord: (d) => ((o.decisionDates || ['2026-09-30', '2026-10-30']).includes(d) ? { signal_date: d, status: 'ok' } : null),
    executionExists: (sd) => existsSync(join(execDir, `${sd}.json`)),
    writeExecution: (sd, suffix, rec) => writeRecordOnce(join(execDir, `${sd}${suffix}.json`), rec),
    appendRunLog: (r) => calls.log.push(r), decide: () => {},
    buildState: async () => live(),
    riskCheck,
    recordEntry: (e) => { const rec = journal.recordEntry(e, { file: journalFile, now: () => now }); calls.entries.push(rec.id); return rec; },
    recordExit: (id, x) => { const rec = journal.recordExit(id, x, { file: journalFile, now: () => now }); calls.exits.push(id); return rec; },
    placeOrder: async (ord) => { calls.orders.push(ord); seq.push(`placeOrder(${ord.side} ${ord.symbol} ${ord.qty} ${ord.time_in_force} ${ord.client_order_id})`); if (o.placeOrderThrows) throw new Error('connection reset after send'); return { id: `alp-${calls.orders.length}`, status: 'accepted' }; },
    recordOrder: () => {}, sleep: async () => {},
    getOrderByClientId: async (cid) => { const ord = calls.orders.find((x) => x.client_order_id === cid); return o.fills ? o.fills(ord) : defaultFill(ord); },
  };
  const seedEntry = (id, symbol, price, qty, when = '2026-10-02T20:50:00Z') => journal.recordEntry({ id, strategy_id: STRATEGY_ID, strategy_version: '1', rule: 'seed', signal_values: { mom: 0.01 },
    symbol, side: 'buy', notional: r2(price * qty), stop: r2(price * 0.95), target: r2(price * 1.0001), expected_price: price, exit_plan: { description: 'seed', max_hold_minutes: 64800 },
    risk_check: { approved: true }, benchmark_baseline_ref: 'benchmarks/baseline.json@seed', run_id: 'SEED' }, { file: journalFile, now: () => D(when) });
  return { deps, calls, seq, opts: o, state: () => state, setState: (s) => { state = s; }, setNow: (d) => { now = d; }, root, execDir, seedEntry, killFile: join(root, 'ops', 'trading', 'KILL') };
}
const heldIEF = (extra = {}) => ({ ...freshState(2250), sleeve_cash_usd: 64.31, holding: 'IEF', qty: 23, entry_id: 'T-0', entry_price: 95.03, entry_time: '2026-10-02T20:50:00Z', stop_price: 90.28,
  sleeve_equity_usd: 2248.85, equity_observed_at: '2026-10-30T21:00:00Z', last_signal_date: '2026-09-30', last_execution_date: '2026-10-01', no_stop_holding: 'IEF', ...extra });
const heldBIL = (extra = {}) => ({ ...freshState(2250), sleeve_cash_usd: 54.24, holding: 'BIL', qty: 24, entry_id: 'T-0', entry_price: 91.49, entry_time: '2026-10-02T20:50:00Z', stop_price: 90.58,
  sleeve_equity_usd: 2250, equity_observed_at: '2026-10-30T21:00:00Z', last_signal_date: '2026-09-30', last_execution_date: '2026-10-01', no_stop_holding: 'BIL', ...extra });
const stopDeps = (m, when, close) => ({ runId: 'RR-stop', now: () => D(when), readState: m.deps.readState, writeState: m.deps.writeState, appendStopLog: () => {}, lastDailyBar: async () => ({ t: when, c: close }) });

// ---------------------------------------------------------------- (a) M1 + (d) S2: stop switch, then the next month-end run
{
  const m = mk({ id: 'a', now: D('2026-11-11T20:50:00Z'), state: heldIEF(), record: null, quotes: { IEF: [90.10, 90.12], BIL: [91.49, 91.51] }, decisionDates: ['2026-09-30', '2026-11-30'] });
  m.seedEntry('T-0', 'IEF', 95.03, 23);
  await stopCheck(stopDeps(m, '2026-11-10T20:35:00Z', 90.1)); // close 90.1 <= stop 90.28 -> trigger
  check('a1', 'stop trigger marks stop_pending', m.state().stop_pending?.date === '2026-11-10', JSON.stringify(m.state().stop_pending));
  m.deps.record = stopRecord(m.state(), '2026-11-11');
  const sw = await runMonthly(m.deps);
  const s1 = m.state();
  check('a2', 'stop switch runs with the real engine (sell IEF exit, buy BIL)', sw.action === 'switch' && m.calls.orders.map((x) => x.side + x.symbol).join(',') === 'sellIEF,buyBIL', `${sw.action}; orders ${m.calls.orders.map((x) => `${x.side} ${x.symbol} ${x.qty} ${x.time_in_force}`).join(' | ')}; engine ${m.calls.engine.map((e) => `${e.side}${e.symbol}:${e.approved}`).join(',')}`);
  check('a3', 'M1: last_signal_date kept across the stop switch (core :302)', s1.last_signal_date === '2026-09-30', `last_signal_date ${s1.last_signal_date}, holding ${s1.holding} ${s1.qty}, cash ${s1.sleeve_cash_usd}`);
  check('a4', 'S2: no_stop_holding is IEF after the stop switch, in state (core :303)', s1.no_stop_holding === 'IEF', `no_stop_holding ${s1.no_stop_holding}`);
  const line = await stopCheck(stopDeps(m, '2026-11-12T20:35:00Z', 91.5));
  check('a5', 'S2: stop-check line after the switch reports no_stop_holding IEF (core :324)', line.no_stop_holding === 'IEF' && line.holding === 'BIL', `line holding ${line.holding}, no_stop_holding ${line.no_stop_holding}, equity ${line.sleeve_equity_usd}`);
  // December month-end: the previous-record gate must look for 2026-09-30 (present), not the stop date
  m.setNow(D('2026-12-01T20:50:00Z')); m.deps.record = REC({ signal_date: '2026-11-30', execution_date: '2026-12-01', holding_before: 'BIL', target: 'IEF' });
  m.deps.quotes = undefined; // defaults
  const dec = await runMonthly({ ...m.deps, buildState: async () => ({ ...(await m.deps.buildState()), quotes: { IEF: { bid: 94.98, ask: 95.02, time: '2026-12-01T20:49:30Z' }, BIL: { bid: 91.49, ask: 91.51, time: '2026-12-01T20:49:30Z' } } }) });
  check('a6', 'M1: December run after a November stop switch proceeds (not refused at the previous-record gate)', dec.action === 'switch', `${dec.action} ${JSON.stringify(dec.failures ?? [])}; state ${describeState(m.state())}`);
}

// ---------------------------------------------------------------- (b) M2: write-ahead state, pending gate, reconciliation
{
  // b1 buy: placeOrder throws after sending
  const m = mk({ id: 'b1', now: NOV2, state: null, record: REC(), placeOrderThrows: true });
  let err = null; try { await runMonthly(m.deps); } catch (e) { err = e.message; }
  const i = m.seq.findIndex((x) => x.startsWith('placeOrder(buy'));
  check('b1', 'M2 buy: writeState with pending_buy is the call immediately before placeOrder (core :280-281)', /connection reset/.test(err) && i > 0 && /pb=T-/.test(m.seq[i - 1]) && m.state().pending_buy?.client_order_id === m.calls.orders[0].client_order_id, `seq: ${m.seq.join(' -> ')}`);
  const again = mk({ id: 'b1b', now: NOV2, state: m.state(), record: REC() }); // same-day rerun: the pending order is the only failure
  const o = await runMonthly(again.deps);
  check('b1b', 'M2 buy: the next run is refused by the pending order and sends nothing (core :150-151)', o.action === 'no-order' && /unconfirmed order .* is pending/.test(o.failures.join(';')) && again.calls.orders.length === 0, o.failures.join(';'));
  // b2 sell: placeOrder throws after sending
  const s = mk({ id: 'b2', now: NOV2, state: heldIEF(), record: REC_IEF_TO_BIL, placeOrderThrows: true });
  s.seedEntry('T-0', 'IEF', 95.03, 23);
  err = null; try { await runMonthly(s.deps); } catch (e) { err = e.message; }
  const j = s.seq.findIndex((x) => x.startsWith('placeOrder(sell'));
  check('b2', 'M2 sell: writeState with pending_sell is the call immediately before placeOrder (core :218-219)', /connection reset/.test(err) && j > 0 && /ps=T-0-x/.test(s.seq[j - 1]) && s.state().pending_sell?.client_order_id === 'T-0-x' && s.state().qty === 23, `seq: ${s.seq.join(' -> ')}`);
  const again2 = mk({ id: 'b2b', now: NOV2, state: s.state(), record: REC_IEF_TO_BIL });
  const o2 = await runMonthly(again2.deps);
  check('b2b', 'M2 sell: the next run is refused by the pending sell, no second sell', o2.action === 'no-order' && /unconfirmed order T-0-x/.test(o2.failures.join(';')) && again2.calls.orders.length === 0, o2.failures.join(';'));
  // b3 full switch: the sequence of writes and orders
  const f = mk({ id: 'b3', now: NOV2, state: heldIEF(), record: REC_IEF_TO_BIL });
  f.seedEntry('T-0', 'IEF', 95.03, 23);
  const o3 = await runMonthly(f.deps);
  const kinds = f.seq.map((x) => x.startsWith('placeOrder(sell') ? 'S' : x.startsWith('placeOrder(buy') ? 'B' : /ps=T-0-x/.test(x) ? 'w:ps' : /pb=T-/.test(x) ? 'w:pb' : /h=-:0 cash=/.test(x) && !/pb=T-/.test(x) ? 'w:cash' : 'w');
  check('b3', 'M2 switch: order of calls is write(pending_sell) -> sell -> write(post-sell cash) -> write(pending_buy) -> buy -> write(final) (core :218, :219, :240, :280, :281, :298)', o3.action === 'switch' && kinds.join(',') === 'w:ps,S,w:cash,w:pb,B,w', `${o3.action}; ${kinds.join(',')}; final ${describeState(f.state())}`);
  // b4 reconciliation
  const r1 = mk({ id: 'b4a', now: NOV2, state: null, record: REC(), positions: () => [{ symbol: 'IEF', qty: '23', side: 'long', market_value: '2184.54' }] });
  const o4 = await runMonthly(r1.deps);
  check('b4a', 'M2: empty state but the account holds IEF 23 -> refused with alert, no order (core :159)', o4.action === 'no-order' && /account holds IEF 23 \/ BIL 0 while the sleeve state holds nothing/.test(o4.reason) && r1.calls.log[0].alert === true && r1.calls.orders.length === 0, o4.reason);
  const r2m = mk({ id: 'b4b', now: NOV2, state: heldIEF(), record: REC_IEF_TO_BIL, positions: () => [] });
  const o5 = await runMonthly(r2m.deps);
  check('b4b', 'M2: state says IEF 23 but the account holds 0 -> refused with alert, no order (core :158)', o5.action === 'no-order' && /account holds 0 IEF, the sleeve state says 23/.test(o5.reason) && r2m.calls.log[0].alert === true && r2m.calls.orders.length === 0, o5.reason);
}

// ---------------------------------------------------------------- (c) M3 + S1: sizing on the sleeve cash; equity = shares x bid + cash
{
  const m = mk({ id: 'c1', now: NOV3, record: REC(), state: { ...freshState(2250), sleeve_cash_usd: 2100, last_signal_date: '2026-09-30', engine_blocked: { signal_date: '2026-10-30', date: '2026-11-02', target: 'IEF', retries: 1, proceeds_usd: 2100, reasons: ['x'] } } });
  const o = await runMonthly(m.deps);
  check('c1', 'M3: engine-blocked retry with 2 100 USD at ask 95.02 buys 22 shares (core :199, :249), real engine approves', o.action === 'initial-buy' && m.calls.orders[0].qty === '22', `${o.action}; qty ${m.calls.orders[0]?.qty}; engine ${m.calls.engine.map((e) => `${e.approved}:${e.reasons.join('/')}`).join(' | ')}; cash after ${m.state().sleeve_cash_usd}`);
  const b = mk({ id: 'c2', now: NOV2, record: REC(), state: null });
  const ob = await runMonthly(b.deps);
  const st = b.state();
  check('c2', 'S1: residual after the first buy is in the state and in the equity (2250 - 23 x 95.03 = 64.31; 23 x 94.98 + 64.31 = 2248.85)', ob.action === 'initial-buy' && st.sleeve_cash_usd === 64.31 && st.sleeve_equity_usd === 2248.85 && ob.record.sleeve_cash_before_usd === 2250, `cash ${st.sleeve_cash_usd}, equity ${st.sleeve_equity_usd}, record sleeve_cash_before_usd ${ob.record.sleeve_cash_before_usd}`);
  // halt computed on shares x bid + cash: bid 78 -> 23 x 78 + 64.31 = 1858.31, loss 391.69 < 450 (old formula: 456 -> halt)
  const h1 = mk({ id: 'c3a', now: NOV2, record: REC_IEF_TO_BIL, state: heldIEF({ sleeve_equity_usd: 1860 }), quotes: { IEF: [78, 78.1], BIL: [91.49, 91.51] }, freshBar: false }); // yesterday's mark 1860: no one-day review, so the halt line alone decides
  const oh1 = await runMonthly(h1.deps);
  check('c3a', 'S1: halt line sees the cash: bid 78 -> equity 1858.31, no halt (core :162-164)', oh1.reason !== 'sleeve halt' && oh1.record?.sleeve_equity_before_usd === 1858.31 && !h1.state().halted, `${oh1.action} ${oh1.reason}; sleeve_equity_before ${oh1.record?.sleeve_equity_before_usd}`);
  const h2 = mk({ id: 'c3b', now: NOV2, record: REC_IEF_TO_BIL, state: heldIEF(), quotes: { IEF: [75, 75.1], BIL: [91.49, 91.51] }, freshBar: false });
  const oh2 = await runMonthly(h2.deps);
  check('c3b', 'S1: bid 75 -> equity 1789.31, loss 460.69 -> halt, no order', oh2.reason === 'sleeve halt' && /460\.69 USD reached the 450/.test(h2.state().halted?.reason) && h2.calls.orders.length === 0, h2.state().halted?.reason);
  const h3 = mk({ id: 'c3c', now: NOV2, record: REC_IEF_TO_BIL, state: heldIEF({ sleeve_equity_usd: 2248.85 }), quotes: { IEF: [92, 92.1], BIL: [91.49, 91.51] }, freshBar: false });
  const oh3 = await runMonthly(h3.deps);
  check('c3c', 'S1: one-day review on shares x bid + cash: 2248.85 -> 2180.31 = 68.54 >= 67.50 -> review hold (core :168)', oh3.reason === 'one-day loss review' && /68\.54 USD/.test(h3.state().review_hold?.reason), h3.state().review_hold?.reason);
}

// ---------------------------------------------------------------- (e) S5: ioc; an unfilled order leaves pending_* and refuses the next run
{
  const u = mk({ id: 'e1', now: NOV2, record: REC(), state: null, fills: () => ({ status: 'canceled', filled_qty: '0', filled_avg_price: null }) });
  const o = await runMonthly(u.deps);
  check('e1', 'S5: unfilled ioc buy -> buy-unconfirmed, pending_buy set, cash untouched (core :305-306)', o.action === 'buy-unconfirmed' && o.exit_code === 3 && u.state().pending_buy?.client_order_id === u.calls.orders[0].client_order_id && u.state().sleeve_cash_usd === 2250 && u.calls.orders[0].time_in_force === 'ioc', `${o.action}; ${describeState(u.state())}`);
  const n1 = mk({ id: 'e1b', now: NOV2, record: REC(), state: u.state() });
  const o1 = await runMonthly(n1.deps);
  check('e1b', 'S5: the next run is refused by pending_buy', /is pending/.test(o1.failures?.join(';') ?? '') && n1.calls.orders.length === 0, o1.failures?.join(';'));
  const v = mk({ id: 'e2', now: NOV2, record: REC_IEF_TO_BIL, state: heldIEF(), fills: () => ({ status: 'canceled', filled_qty: '0', filled_avg_price: null }) });
  v.seedEntry('T-0', 'IEF', 95.03, 23);
  const o2 = await runMonthly(v.deps);
  check('e2', 'S5: unfilled ioc sell -> sell-unconfirmed, pending_sell set, no buy sent, holding kept in state (core :226-227)', o2.action === 'sell-unconfirmed' && v.state().pending_sell?.client_order_id === 'T-0-x' && v.calls.orders.length === 1 && v.state().qty === 23, `${o2.action}; ${describeState(v.state())}; orders ${v.calls.orders.length}`);
  const n2 = mk({ id: 'e2b', now: NOV2, record: REC_IEF_TO_BIL, state: v.state() });
  const o3 = await runMonthly(n2.deps);
  check('e2b', 'S5: the next run is refused by pending_sell', /unconfirmed order T-0-x/.test(o3.failures?.join(';') ?? '') && n2.calls.orders.length === 0, o3.failures?.join(';'));
}

// ---------------------------------------------------------------- (f) N4: same-day rerun does not consume a retry; does a refusal on a retry count?
{
  const blockedState = (date) => ({ ...freshState(2250), sleeve_cash_usd: 2195.76, last_signal_date: '2026-09-30', engine_blocked: { signal_date: '2026-10-30', date, target: 'IEF', retries: 1, proceeds_usd: 2195.76, reasons: ['x'] } });
  const m = mk({ id: 'f1', now: NOV2, record: REC(), state: blockedState('2026-11-02') });
  const o = await runMonthly(m.deps);
  check('f1', 'N4: a same-day rerun while engine-blocked is refused and the counter stays at 1 (core :144)', /retried at a later session/.test(o.failures?.join(';') ?? '') && m.state().engine_blocked.retries === 1 && m.calls.orders.length === 0, o.failures?.join(';'));
  // the author: "a refusal on a retry now counts the retry". Retry on 2026-11-03 with the engine refusing (daily bar -> bar age, the refusal in force today)
  const n = mk({ id: 'f2', now: NOV3, record: REC(), state: blockedState('2026-11-02'), freshBar: false });
  const o2 = await runMonthly(n.deps);
  const eb = n.state().engine_blocked;
  check('f2', 'claim: a refusal on a retry counts the retry (expected retries 2, date 2026-11-03, action engine-blocked)', o2.action === 'engine-blocked, sleeve in USD' && eb.retries === 2 && eb.date === '2026-11-03', `action "${o2.action}", engine_blocked ${JSON.stringify(eb)}, record file ${o2.record?.file?.split('/').pop()}`);
  // the day after: same state, same record
  n.setNow(NOV4);
  let err = null, o3 = null; try { o3 = await runMonthly(n.deps); } catch (e) { err = e.message; }
  check('f3', 'the retry on the following day runs cleanly (no throw)', err === null && o3 !== null, err ? `THROWS: ${err.replace(n.execDir, '<execDir>')}` : `${o3.action}; ${JSON.stringify(n.state().engine_blocked)}`);
}

// ---------------------------------------------------------------- (g) backward compatibility: older state without sleeve_cash_usd
{
  check('g1', 'sleeveCash: holding -> 0; engine-blocked -> proceeds; else sleeve start (core :38)', sleeveCash({ sleeve_start_usd: 2250, qty: 23 }) === 0 && sleeveCash({ sleeve_start_usd: 2250, qty: 0, engine_blocked: { proceeds_usd: 2100 } }) === 2100 && sleeveCash({ sleeve_start_usd: 2250, qty: 0 }) === 2250 && sleeveCash({ sleeve_start_usd: 2250, qty: 0, sleeve_cash_usd: null }) === 2250, 'four direct calls');
  const old = heldIEF(); delete old.sleeve_cash_usd; delete old.no_stop_holding; delete old.pending_sell; delete old.pending_buy;
  const m = mk({ id: 'g2', now: NOV2, state: old, record: REC({ holding_before: 'IEF', target: 'IEF', switch: false }) });
  const o = await runMonthly(m.deps);
  check('g2', 'older held state: cash read as 0, hold record written, state gains sleeve_cash_usd 0 and no_stop_holding (core :189)', o.action === 'hold' && o.record.sleeve_cash_before_usd === 0 && m.state().sleeve_cash_usd === 0 && m.state().no_stop_holding === 'IEF' && o.record.sleeve_equity_before_usd === r2(23 * 94.98), `${o.action}; cash_before ${o.record.sleeve_cash_before_usd}; equity ${o.record.sleeve_equity_before_usd}; ${describeState(m.state())}`);
  const oldBlocked = { ...freshState(2250), last_signal_date: '2026-09-30', engine_blocked: { signal_date: '2026-10-30', target: 'IEF', retries: 1, proceeds_usd: 2100, reasons: ['x'] } }; delete oldBlocked.sleeve_cash_usd;
  const b = mk({ id: 'g3', now: NOV3, state: oldBlocked, record: REC() });
  const ob = await runMonthly(b.deps);
  check('g3', 'older engine-blocked state without date or sleeve_cash_usd: retry sized on proceeds (22 shares), proceeds', ob.action === 'initial-buy' && b.calls.orders[0]?.qty === '22', `${ob.action} qty ${b.calls.orders[0]?.qty} ${JSON.stringify(ob.failures ?? [])}`);
}

// ---------------------------------------------------------------- R: regression probes on the fixed paths
{
  // R1 engine-blocked after selling IEF (kill switch raised between the pre-check and the binding call), then the retry
  const m = mk({ id: 'R1', now: NOV2, state: heldIEF(), record: REC_IEF_TO_BIL, killBeforeBinding: true });
  m.seedEntry('T-0', 'IEF', 95.03, 23);
  const o = await runMonthly(m.deps);
  const eb = m.state().engine_blocked;
  check('R1a', 'setup: IEF -> BIL switch blocked at the binding call -> engine-blocked, sleeve in USD, retries 1', o.action === 'engine-blocked, sleeve in USD' && eb?.retries === 1 && m.state().holding === null && m.calls.orders.length === 1, `${o.action}; ${describeState(m.state())}; reasons ${o.record?.reasons?.join('/')}`);
  unlinkSync(m.killFile); m.opts.killBeforeBinding = false; // the kill switch is lifted
  m.setNow(NOV3);
  const o2 = await runMonthly(m.deps);
  check('R1b', 'retry of an IEF -> BIL block on the next day proceeds (expected: buy BIL with the proceeds)', o2.action === 'initial-buy' && m.calls.orders.length === 2, `${o2.action}; failures ${JSON.stringify(o2.failures ?? [])}; orders ${m.calls.orders.length}`);
  // the same in the BIL -> IEF direction
  const b = mk({ id: 'R1c', now: NOV2, state: heldBIL(), record: REC(), killBeforeBinding: true });
  b.seedEntry('T-0', 'BIL', 91.49, 24);
  const ob = await runMonthly(b.deps);
  unlinkSync(b.killFile); b.opts.killBeforeBinding = false; b.setNow(NOV3);
  const ob2 = await runMonthly(b.deps);
  check('R1c', 'retry of a BIL -> IEF block on the next day proceeds', ob.action === 'engine-blocked, sleeve in USD' && ob2.action === 'initial-buy' && b.calls.orders.length === 2, `${ob.action} -> ${ob2.action}; ${describeState(b.state())}`);
}
{
  // R2 a stop switch blocked after the sell: what record would run-monthly select next day? (selection logic copied from run-monthly :48-52)
  const m = mk({ id: 'R2', now: D('2026-11-11T20:50:00Z'), state: heldIEF({ stop_pending: { date: '2026-11-10', close: 90.1 }, sleeve_equity_usd: 2136.61 }), record: null, quotes: { IEF: [90.10, 90.12], BIL: [91.49, 91.51] }, killBeforeBinding: true });
  m.seedEntry('T-0', 'IEF', 95.03, 23);
  m.deps.record = stopRecord(m.state(), '2026-11-11');
  const o = await runMonthly(m.deps);
  const st = m.state();
  const files = ['2026-09-30.json', '2026-10-30.json']; // decision files that exist in paper-log/decisions (no file for a stop date)
  const records = files.map((f) => ({ signal_date: f.slice(0, 10), execution_date: f === '2026-10-30.json' ? '2026-11-02' : '2026-10-01' }));
  let record = records.find((x) => x.execution_date === '2026-11-12') ?? null;
  if (!record && st?.engine_blocked) record = records.find((x) => x.signal_date === st.engine_blocked.signal_date) ?? null;
  if (!record && st?.stop_pending) record = stopRecord(st, '2026-11-12');
  check('R2', 'a stop switch blocked after the sell has a record to retry from on the next day (run-monthly :50-52)', record !== null, `${o.action}; state stop_pending ${JSON.stringify(st.stop_pending)}, engine_blocked.signal_date ${st.engine_blocked?.signal_date}; selected record: ${JSON.stringify(record)}`);
}
{
  // R3 reconciliation with another strategy's position in the same symbols (IEF and BIL are approved for Study 001 too)
  const m = mk({ id: 'R3a', now: NOV2, state: null, record: REC(), positions: () => [{ symbol: 'BIL', qty: '49', side: 'long', market_value: '4483' }] });
  const o = await runMonthly(m.deps);
  check('R3a', 'first run with another strategy holding BIL 49 in the account (sleeve state fresh) proceeds', o.action === 'initial-buy', `${o.action}: ${o.reason ?? ''}; alert ${m.calls.log[0]?.alert}`);
  const h = mk({ id: 'R3b', now: NOV2, state: heldIEF(), record: REC_IEF_TO_BIL, positions: () => [{ symbol: 'IEF', qty: '46', side: 'long', market_value: '4369' }] });
  h.seedEntry('T-0', 'IEF', 95.03, 23);
  const oh = await runMonthly(h.deps);
  check('R3b', 'held IEF 23 with the account at IEF 46 (another strategy holds 23) passes the gate and sells 23 only (core :158 uses <)', oh.action === 'switch' && h.calls.orders[0].qty === '23', `${oh.action}; sell qty ${h.calls.orders[0]?.qty}; ${oh.reason ?? ''}`);
}
{
  // R4 a partial ioc fill on the buy (24 ordered, 23 filled, order canceled for the rest)
  const m = mk({ id: 'R4', now: NOV2, state: heldIEF(), record: REC_IEF_TO_BIL, fills: (ord) => (ord.side === 'sell' ? { status: 'filled', filled_qty: '23', filled_avg_price: '94.97' } : { status: 'canceled', filled_qty: '23', filled_avg_price: '91.52' }) });
  m.seedEntry('T-0', 'IEF', 95.03, 23);
  const o = await runMonthly(m.deps);
  const st = m.state();
  const n = mk({ id: 'R4b', now: NOV3, state: st, record: REC_IEF_TO_BIL });
  const o2 = await runMonthly(n.deps);
  check('R4', 'partial ioc buy fill: buy-unconfirmed, pending_buy set, next run refused; state cash and qty do NOT reflect the 23 shares held (owner reconciles by hand)', o.action === 'buy-unconfirmed' && st.pending_buy && st.qty === 0 && st.sleeve_cash_usd === r2(64.31 + 23 * 94.97) && /is pending/.test(o2.failures?.join(';') ?? '') && n.calls.orders.length === 0, `${o.action}; ${describeState(st)}; record filled_qty ${o.record.orders[1].filled_qty} status ${o.record.orders[1].status}; next run: ${o2.failures?.[0]}`);
}
{
  // R5 pending flags: can the runner clear one itself in a wrong case? Owner clears pending_buy by hand but the buy had filled (account holds IEF 23, state qty 0)
  const m = mk({ id: 'R5', now: NOV2, state: { ...freshState(2250), last_signal_date: '2026-09-30', sleeve_cash_usd: 2250, pending_buy: null, engine_blocked: null }, record: REC(), positions: () => [{ symbol: 'IEF', qty: '23', side: 'long', market_value: '2184.54' }] });
  const o = await runMonthly(m.deps);
  check('R5', 'after a by-hand clear of pending_buy with the fill actually in the account, the reconciliation gate still refuses (no second buy)', o.action === 'no-order' && /sleeve state holds nothing/.test(o.reason) && m.calls.orders.length === 0, o.reason);
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length} checks, ${results.length - failed.length} as expected, ${failed.length} not as expected: ${failed.map((f) => f.id).join(', ') || 'none'}`);
