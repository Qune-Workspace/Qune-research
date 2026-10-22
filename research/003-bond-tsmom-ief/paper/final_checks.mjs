#!/usr/bin/env node
// final_checks.mjs: Tester's final checks of the three fixed paths (desk commit 5ce326c: M4, M5, S6 of RUNNER_REREVIEW.md),
// looking for regressions the hoisted blocked() could cause on a normal (non-retry) day. Written 2026-10-22 by the Tester
// agent; it did not write the runner or the fixes. Same harness as rereview_checks.mjs: the real run-monthly-core.mjs, the
// real risk engine on a temp root with a COPY of config/risk.json, the real journal on a temp file; placeOrder and the fill
// poll stubbed; state in memory; execution records in a temp dir. F3 also loads the PRE-FIX core (git show 5ce326c^) into a
// temp dir to compare behaviour. No network, no credentials, nothing written under ops/ or paper-log/. Run from this folder:
//   DESK=<desk workspace root> node final_checks.mjs
// "bar under 2 h" checks substitute a fresh signal_bar_time on buy orders (as runner_dryrun.mjs does); checks with
// freshBar: false let the real engine refuse on the daily bar's age, the refusal in force on any real retry day.
import { mkdtempSync, mkdirSync, copyFileSync, existsSync, writeFileSync, readdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const DESK = process.env.DESK;
if (!DESK) { console.error('set DESK to the desk workspace root'); process.exit(2); }
const T = join(DESK, 'ops', 'trading');
const core = await import(pathToFileURL(join(T, 'bin', 'run-monthly-core.mjs')));
const risk = await import(pathToFileURL(join(T, 'lib', 'risk.mjs')));
const journal = await import(pathToFileURL(join(T, 'lib', 'journal.mjs')));
const { stopRecord, writeRecordOnce, freshState, STRATEGY_ID } = core;
// the core as it was before the fix commit, for before/after comparisons (read from git into a temp dir; never run against anything real)
const preDir = mkdtempSync(join(tmpdir(), 'study003-prefix-core-'));
writeFileSync(join(preDir, 'run-monthly-core.mjs'), execFileSync('git', ['-C', DESK, 'show', '5ce326c^:ops/trading/bin/run-monthly-core.mjs'], { encoding: 'utf8' }));
const preCore = await import(pathToFileURL(join(preDir, 'run-monthly-core.mjs')));

const OK_MD = `## Strategy: ${STRATEGY_ID} v1 -> **CLEARED for paper at the 2 250 USD sleeve**\n`;
const RISK = { status: 'reviewed', allowed_hosts: ['paper-api.alpaca.markets', 'data.alpaca.markets'] };
const D = (s) => new Date(s);
const NOV2 = D('2026-11-02T20:50:00Z'), NOV3 = D('2026-11-03T20:50:00Z');
const REC = (over = {}) => ({ strategy_id: STRATEGY_ID, strategy_version: '1', status: 'ok', signal_date: '2026-10-30', execution_date: '2026-11-02',
  holding_before: 'BIL', target: 'IEF', mom: 0.0123, switch: true, run_at_utc: '2026-10-30T22:05:00Z', ...over });
const REC_IEF_TO_BIL = REC({ holding_before: 'IEF', target: 'BIL', mom: -0.0042 });

const results = [];
const check = (id, name, ok, detail) => { results.push({ id, name, ok, detail }); console.log(`${ok ? 'PASS' : 'FAIL'} [${id}] ${name}: ${detail}`); };
const r2 = (x) => Math.round(x * 100) / 100;

function tempRoot() {
  const root = mkdtempSync(join(tmpdir(), 'study003-final-'));
  for (const d of ['config', 'strategies', 'journal', 'state']) mkdirSync(join(root, 'ops', 'trading', d), { recursive: true });
  copyFileSync(join(T, 'config', 'risk.json'), join(root, 'ops', 'trading', 'config', 'risk.json'));
  for (const f of [`${STRATEGY_ID}.md`, `${STRATEGY_ID}-backtest.json`]) copyFileSync(join(T, 'strategies', f), join(root, 'ops', 'trading', 'strategies', f));
  return root;
}
const describeState = (s) => (s ? `h=${s.holding ?? '-'}:${s.qty} cash=${s.sleeve_cash_usd ?? 'n/a'} ps=${s.pending_sell?.client_order_id ?? '-'} pb=${s.pending_buy?.client_order_id ?? '-'} eb=${s.engine_blocked ? `${s.engine_blocked.signal_date}/${s.engine_blocked.retries}@${s.engine_blocked.date}` : '-'} sp=${s.stop_pending?.date ?? '-'} lsd=${s.last_signal_date}` : 'null');
const files = (dir) => (existsSync(dir) ? readdirSync(dir).sort().join(',') : '');
const reasonOf = (o) => o.record?.reason ?? o.reason; // finish() puts the reason on the record (core :180), stopRun() on the output (core :120)

// Harness around runMonthly. o: { id, now, state, record, mode, quotes {SYM: [bid, ask]}, positions(state) -> [], freshBar (default true),
//   fills(order) -> fill, decisionDates, decisionMd, root, execDir, core (default: the fixed core) }
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
    const rc = engine(order, s);
    calls.engine.push({ side: ord.side, symbol: ord.symbol, qty: ord.qty, jid: !!ord.journal_entry_id, approved: rc.approved, reasons: rc.reasons });
    return rc;
  };
  const defaultFill = (ord) => { const q = quotes()[ord.symbol]; return { status: 'filled', filled_qty: ord.qty, filled_avg_price: String(ord.side === 'sell' ? r2(q.bid - 0.01) : r2(q.ask + 0.01)) }; };
  const mode = o.mode || 'execute';
  const deps = {
    runId: `FC-${o.id}`, now: () => now, record: o.record, mode, baseUrl: 'https://paper-api.alpaca.markets', params: {},
    readDecisionMd: () => o.decisionMd ?? OK_MD, readRisk: () => RISK, baselineRef: 'benchmarks/baseline.json@final',
    readState: () => state, writeState: (s) => { seq.push(`writeState[${describeState(s)}]`); state = s; },
    readDecisionRecord: (d) => ((o.decisionDates || ['2026-09-30', '2026-10-30']).includes(d) ? { signal_date: d, status: 'ok' } : null),
    executionExists: (sd) => existsSync(join(execDir, `${sd}.json`)),
    // same naming as run-monthly :70: a check run's record carries a -check-<ts> suffix so it never collides with an execute run's record
    writeExecution: (sd, suffix, rec) => writeRecordOnce(join(execDir, `${sd}${suffix}${mode === 'check' ? '-check-' + now.toISOString().slice(0, 16).replace(/[-:T]/g, '') : ''}.json`), rec),
    appendRunLog: (r) => calls.log.push(r), decide: () => {},
    buildState: async () => live(),
    riskCheck,
    recordEntry: (e) => { const rec = journal.recordEntry(e, { file: journalFile, now: () => now }); calls.entries.push(rec.id); return rec; },
    recordExit: (id, x) => { const rec = journal.recordExit(id, x, { file: journalFile, now: () => now }); calls.exits.push(id); return rec; },
    placeOrder: async (ord) => { if (mode === 'check') throw new Error('check mode never places an order'); calls.orders.push(ord); seq.push(`placeOrder(${ord.side} ${ord.symbol} ${ord.qty} ${ord.time_in_force} ${ord.client_order_id})`); return { id: `alp-${calls.orders.length}`, status: 'accepted' }; },
    recordOrder: () => {}, sleep: async () => {},
    getOrderByClientId: async (cid) => { const ord = calls.orders.find((x) => x.client_order_id === cid); return o.fills ? o.fills(ord) : defaultFill(ord); },
  };
  const seedEntry = (id, symbol, price, qty, when = '2026-10-02T20:50:00Z') => journal.recordEntry({ id, strategy_id: STRATEGY_ID, strategy_version: '1', rule: 'seed', signal_values: { mom: 0.01 },
    symbol, side: 'buy', notional: r2(price * qty), stop: r2(price * 0.95), target: r2(price * 1.0001), expected_price: price, exit_plan: { description: 'seed', max_hold_minutes: 64800 },
    risk_check: { approved: true }, benchmark_baseline_ref: 'benchmarks/baseline.json@seed', run_id: 'SEED' }, { file: journalFile, now: () => D(when) });
  const run = (over = {}) => (o.core || core).runMonthly({ ...deps, ...over });
  return { deps, run, calls, seq, opts: o, state: () => state, setState: (s) => { state = s; }, setNow: (d) => { now = d; }, root, execDir, seedEntry };
}
const heldIEF = (extra = {}) => ({ ...freshState(2250), sleeve_cash_usd: 64.31, holding: 'IEF', qty: 23, entry_id: 'T-0', entry_price: 95.03, entry_time: '2026-10-02T20:50:00Z', stop_price: 90.28,
  sleeve_equity_usd: 2248.85, equity_observed_at: '2026-10-30T21:00:00Z', last_signal_date: '2026-09-30', last_execution_date: '2026-10-01', no_stop_holding: 'IEF', ...extra });
const blockedState = (date, extra = {}) => ({ ...freshState(2250), sleeve_cash_usd: 2195.76, last_signal_date: '2026-09-30', engine_blocked: { signal_date: '2026-10-30', date, target: 'IEF', retries: 1, proceeds_usd: 2195.76, reasons: ['x'] }, ...extra });

// ---------------------------------------------------------------- F1: a refusal on day 1 (no retry in the state) is NOT a retry
{
  // F1a fresh sleeve, the real engine refusing on the daily bar's age: plain no-order, no state write, record without a suffix;
  // a same-day rerun is refused on the existing record, the next day on the execution date; the state stays untouched throughout
  const m = mk({ id: 'F1a', now: NOV2, state: null, record: REC(), freshBar: false });
  const o = await m.run();
  const f1 = files(m.execDir);
  const again = mk({ id: 'F1a2', now: NOV2, state: m.state(), record: REC(), freshBar: false, execDir: m.execDir, root: m.root });
  const o2 = await again.run();
  again.setNow(NOV3);
  const o3 = await again.run();
  check('F1a', 'day-1 refusal from a fresh sleeve: no-order, no state write, no -retry suffix, no retry machinery on the rerun or the next day',
    o.action === 'no-order' && reasonOf(o) === 'buy refused by the risk engine' && o.exit_code === 3 && o.record.alert === undefined && o.record.retries === undefined
      && m.seq.length === 0 && m.state() === null && f1 === '2026-10-30.json' && m.calls.orders.length === 0
      && /already exists/.test(o2.failures?.join(';') ?? '') && /is not today/.test(o3.failures?.join(';') ?? '') && again.seq.length === 0 && again.state() === null && files(m.execDir) === f1,
    `${o.action} (${reasonOf(o)}); writes ${m.seq.length}; files ${f1}; rerun: ${o2.failures?.join(';')}; next day: ${o3.failures?.join(';')}; state ${describeState(again.state())}`);
  // F1b a stale engine_blocked flag left from an earlier signal (the owner never cleared it after the third retry): the new month's
  // day-1 refusal now goes through blocked() and starts a retry count for the new signal (before the fix: plain no-order). Observed, not a defect:
  // the sleeve is in USD and condition 6 wants the retry; but the retries then depend on a stale flag rather than on the sleeve being in USD.
  const stale = { ...freshState(2250), sleeve_cash_usd: 2195.76, last_signal_date: '2026-09-30', engine_blocked: { signal_date: '2026-09-30', date: '2026-10-05', target: 'IEF', retries: 3, proceeds_usd: 2195.76, reasons: ['x'] } };
  const s = mk({ id: 'F1b', now: NOV2, state: stale, record: REC(), freshBar: false });
  const os = await s.run();
  const p = mk({ id: 'F1b-pre', now: NOV2, state: stale, record: REC(), freshBar: false, core: preCore });
  const op = await p.run();
  check('F1b', 'stale engine_blocked from an earlier signal + day-1 refusal: fixed core counts a retry for the new signal (pre-fix: no-order); both fail closed, no order',
    os.action === 'engine-blocked, sleeve in USD' && s.state().engine_blocked.signal_date === '2026-10-30' && s.state().engine_blocked.retries === 1 && s.calls.orders.length === 0
      && op.action === 'no-order' && p.seq.length === 0 && p.calls.orders.length === 0,
    `fixed: ${os.action}, ${describeState(s.state())}, file ${files(s.execDir)}; pre-fix: ${op.action}, writes ${p.seq.length}`);
}

// ---------------------------------------------------------------- F2: the pre-existing gates on a normal day, and the held-sleeve day-1 refusal
{
  const cases = [
    ['verdict line', { state: null, record: REC(), decisionMd: '## Strategy: study003-tsmom-ief-bil v1 -> **NOT CLEARED**\n' }, /not cleared by RISK-02/],
    ['window', { state: null, record: REC(), now: D('2026-11-02T21:05:00Z') }, /outside the 15:30-16:00 ET window/],
    ['no decision record', { state: null, record: null }, /no decision record/],
    ['holding_before mismatch (non-retry)', { state: null, record: REC({ holding_before: 'IEF' }) }, /holding_before IEF does not match the sleeve state BIL/],
    ['execution date not today', { state: null, record: REC({ execution_date: '2026-11-03' }) }, /is not today 2026-11-02/],
    ['previous record missing', { state: { ...freshState(2250), last_signal_date: '2026-08-31' }, record: REC() }, /decision record 2026-08-31 is missing/],
    ['pending order', { state: { ...freshState(2250), last_signal_date: '2026-09-30', pending_buy: { client_order_id: 'T-9', signal_date: '2026-10-30' } }, record: REC() }, /unconfirmed order T-9 .* is pending/],
    ['reconciliation (flat state, account holds IEF)', { state: null, record: REC(), positions: () => [{ symbol: 'IEF', qty: '23', side: 'long', market_value: '2184.54' }] }, /reconcile before any order/],
  ];
  const out = [];
  let ok = true;
  for (const [name, over, re] of cases) {
    const m = mk({ id: `F2-${name}`, now: NOV2, ...over });
    const o = await m.run();
    const text = [reasonOf(o), ...(o.failures ?? [])].join(';');
    const good = o.action === 'no-order' && o.exit_code === 3 && re.test(text) && m.seq.length === 0 && m.calls.orders.length === 0 && files(m.execDir) === '';
    ok = ok && good;
    out.push(`${good ? 'ok' : 'NOT OK'} ${name}`);
  }
  check('F2a', 'eight pre-existing gates on a normal day refuse as before: no state write, no record file, no order', ok, out.join('; '));
  // F2b held sleeve, day 1, the engine refusing the buy at the pre-check (post-sell state): holding kept, no sell, no state write, no retry suffix
  const h = mk({ id: 'F2b', now: NOV2, state: heldIEF(), record: REC_IEF_TO_BIL, freshBar: false });
  h.seedEntry('T-0', 'IEF', 95.03, 23);
  const oh = await h.run();
  check('F2b', 'held sleeve, day-1 refusal at the pre-check: holding kept, no sell, no state write, record without a suffix (condition 6 unchanged)',
    oh.action === 'no-order' && /holding kept, no sell/.test(reasonOf(oh)) && h.seq.length === 0 && h.state().qty === 23 && h.state().holding === 'IEF' && h.calls.orders.length === 0 && files(h.execDir) === '2026-10-30.json' && oh.record.retries === undefined,
    `${oh.action} (${reasonOf(oh)}); writes ${h.seq.length}; ${describeState(h.state())}; files ${files(h.execDir)}; engine ${h.calls.engine.map((e) => `${e.side}${e.symbol}:${e.approved}`).join(',')}`);
}

// ---------------------------------------------------------------- F3: check mode on a retry day (the hoisted blocked() sits above the check-mode return, core :217 vs :219)
{
  // the owner runs `run-monthly check` inside the window on a retry day and the engine refuses (the daily bar's age, the refusal in force on any retry day)
  const c = mk({ id: 'F3-check', now: NOV3, state: blockedState('2026-11-02'), record: REC(), freshBar: false, mode: 'check' });
  const oc = await c.run();
  const afterCheck = c.state();
  // the execute run the same day, from the state the check run left behind
  const e = mk({ id: 'F3-exec', now: NOV3, state: afterCheck, record: REC(), freshBar: false, execDir: c.execDir, root: c.root });
  const oe = await e.run();
  // the same check run against the pre-fix core
  const p = mk({ id: 'F3-pre', now: NOV3, state: blockedState('2026-11-02'), record: REC(), freshBar: false, mode: 'check', core: preCore });
  const op = await p.run();
  check('F3', 'check mode on a retry day with a refusing engine leaves the state alone (expected: no state write, the same-day execute still gets its retry)',
    c.seq.length === 0 && afterCheck.engine_blocked.retries === 1 && !/retried at a later session/.test(oe.failures?.join(';') ?? ''),
    `fixed core, check: ${oc.action}, writes ${c.seq.length}, ${describeState(afterCheck)}, files ${files(c.execDir)}; same-day execute: ${oe.action} ${JSON.stringify(oe.failures ?? [reasonOf(oe)])}; pre-fix core, check: ${op.action}, writes ${p.seq.length}, ${describeState(p.state())}`);
}

// ---------------------------------------------------------------- F4: S6 follow-on: stop_pending after a stop switch whose BIL buy is unconfirmed
{
  const m = mk({ id: 'F4', now: D('2026-11-11T20:50:00Z'), state: heldIEF({ stop_pending: { date: '2026-11-10', close: 90.1 }, sleeve_equity_usd: 2136.61 }), record: null,
    quotes: { IEF: [90.10, 90.12], BIL: [91.49, 91.51] }, fills: (ord) => (ord.side === 'sell' ? { status: 'filled', filled_qty: '23', filled_avg_price: '90.1' } : { status: 'canceled', filled_qty: '0', filled_avg_price: null }) });
  m.seedEntry('T-0', 'IEF', 95.03, 23);
  m.deps.record = stopRecord(m.state(), '2026-11-11');
  const o = await m.run({ record: m.deps.record });
  const s1 = m.state();
  // next day: run-monthly :50-52 would select the re-synthesised stop record (engine_blocked is null); the pending gate refuses
  m.setNow(D('2026-11-12T20:50:00Z'));
  const o2 = await m.run({ record: stopRecord(s1, '2026-11-12') });
  // the owner finds the buy did fill after all (account holds BIL 23) and reconciles the state by hand: holding BIL, pending cleared; stop_pending as the runner left it
  const fixedByHand = { ...s1, holding: 'BIL', qty: 23, entry_price: 91.52, sleeve_cash_usd: r2(s1.sleeve_cash_usd - 23 * 91.52), pending_buy: null };
  m.setState(fixedByHand); m.setNow(D('2026-11-13T20:50:00Z'));
  const o3 = await m.run({ record: stopRecord(fixedByHand, '2026-11-13') });
  check('F4', 'S6 follow-on: an unconfirmed BIL buy keeps stop_pending; after a by-hand reconciliation the re-synthesised stop record is refused on the existing record (fails closed, no order; the owner must also clear stop_pending)',
    o.action === 'buy-unconfirmed' && s1.stop_pending?.date === '2026-11-10' && s1.pending_buy && s1.engine_blocked === null
      && /is pending/.test(o2.failures?.join(';') ?? '') && o3.action === 'no-order' && /execution record for signal date 2026-11-10 already exists/.test(o3.failures?.join(';') ?? '') && m.calls.orders.length === 2,
    `${o.action}; ${describeState(s1)}; day 2: ${o2.failures?.join(';')}; day 3 after reconciliation: ${o3.failures?.join(';')}; orders ${m.calls.orders.map((x) => `${x.side} ${x.symbol} ${x.qty}`).join(' | ')}`);
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length} checks, ${results.length - failed.length} as expected, ${failed.length} not as expected: ${failed.map((f) => f.id).join(', ') || 'none'}`);
