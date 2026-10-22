#!/usr/bin/env node
// runner_dryrun.mjs: Tester's dry run of the desk's monthly paper runner (RISK_CLEARANCE condition 5 check:
// "a dry run against the engine with placeOrder stubbed"). Written 2026-10-22 by the Tester agent; it did not write the runner.
//
// What is real:    run-monthly-core.mjs (runMonthly), the risk engine (risk.mjs, bound to a temp root holding a COPY of the
//                  desk's config/risk.json and the study003 spec + backtest file, no KILL file), the desk journal (journal.mjs,
//                  writing to a temp trades.jsonl).
// What is stubbed: placeOrder (records the call, returns accepted), getOrderByClientId (plausible fills), state (in memory),
//                  execution records (temp dir), run log (in memory). No network, no credentials, nothing under ops/ or
//                  paper-log/ is written. Run from this folder: `node runner_dryrun.mjs` (needs the desk workspace at DESK).
import { mkdtempSync, mkdirSync, copyFileSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const DESK = process.env.DESK; // the desk's private workspace root (author's edit 2026-10-22: the absolute default was removed, the leak scan blocks private paths)
if (!DESK) { console.error('set DESK to the desk workspace root'); process.exit(2); }
const T = join(DESK, 'ops', 'trading');
const core = await import(pathToFileURL(join(T, 'bin', 'run-monthly-core.mjs')));
const risk = await import(pathToFileURL(join(T, 'lib', 'risk.mjs')));
const journal = await import(pathToFileURL(join(T, 'lib', 'journal.mjs')));
const { runMonthly, writeRecordOnce, freshState, STRATEGY_ID } = core;

// 2026-11-02 15:50 ET = 20:50 UTC (EST from 2026-11-01). First execution date of the study.
const NOW = new Date('2026-11-02T20:50:00Z');
const OK_MD = `## Strategy: ${STRATEGY_ID} v1 -> **CLEARED for paper at the 2 250 USD sleeve**\n`;
const RISK = { status: 'reviewed', allowed_hosts: ['paper-api.alpaca.markets', 'data.alpaca.markets'] };
const quoteAt = (bid, ask) => ({ bid, ask, time: new Date(NOW.getTime() - 30e3).toISOString() }); // 30 s old
const quotes = () => ({ IEF: quoteAt(94.98, 95.02), BIL: quoteAt(91.49, 91.51) });

// A temp desk root for the real engine: real limits, the real spec and backtest record, no KILL file, empty state.
function tempRoot() {
  const root = mkdtempSync(join(tmpdir(), 'study003-dryrun-'));
  for (const d of ['config', 'strategies', 'journal', 'state']) mkdirSync(join(root, 'ops', 'trading', d), { recursive: true });
  copyFileSync(join(T, 'config', 'risk.json'), join(root, 'ops', 'trading', 'config', 'risk.json'));
  for (const f of [`${STRATEGY_ID}.md`, `${STRATEGY_ID}-backtest.json`]) copyFileSync(join(T, 'strategies', f), join(root, 'ops', 'trading', 'strategies', f));
  return root;
}

// liveState: what run-monthly's buildState would hand the engine (equity 100 000, cash 90 000, fresh quotes, no crypto).
function liveState(positions) {
  return { now: NOW.toISOString(), hosts: ['paper-api.alpaca.markets', 'data.alpaca.markets'],
    account: { equity: '100000', cash: '90000', buying_power: '180000', status: 'ACTIVE' }, positions, quotes: quotes(),
    day_start_equity: 100000, orders_today: 0, recent_orders: [], open_orders: [] };
}

async function runCase({ name, holding, freshBar }) {
  const root = tempRoot();
  const journalFile = join(root, 'ops', 'trading', 'journal', 'trades.jsonl');
  const execDir = join(root, 'executions');
  const engine = risk._engineForTests(root);
  const calls = { engine: [], orders: [], entries: [], exits: [], log: [] };
  let state = null;
  const positions = [];
  if (holding === 'IEF') {
    // Seed: the sleeve holds 23 IEF bought at 95.03 on 2026-10-02 under journal entry T-0 (so the real journal can write the exit).
    journal.recordEntry({ id: 'T-0', strategy_id: STRATEGY_ID, strategy_version: '1', rule: 'mom_t > 0 -> IEF', signal_values: { mom: 0.01 },
      symbol: 'IEF', side: 'buy', notional: 2185.69, stop: 90.28, target: 95.04, expected_price: 95.03, exit_plan: { description: 'seed', max_hold_minutes: 64800 },
      risk_check: { approved: true }, benchmark_baseline_ref: 'benchmarks/baseline.json@seed', run_id: 'SEED' }, { file: journalFile, now: () => new Date('2026-10-02T20:50:00Z') });
    state = { ...freshState(2250), sleeve_cash_usd: 64.31 /* author's edit 2026-10-22 after the S1 fix: the sleeve's residual cash after case B's 23 x 95.03; the field did not exist when this script was written */, holding: 'IEF', qty: 23, entry_id: 'T-0', entry_price: 95.03, entry_time: '2026-10-02T20:50:00Z', stop_price: 90.28,
      sleeve_equity_usd: 2184.54, equity_observed_at: '2026-10-30T21:00:00Z', last_signal_date: '2026-09-30', last_execution_date: '2026-10-01' };
    positions.push({ symbol: 'IEF', qty: '23', side: 'long', market_value: String(23 * 94.98), avg_entry_price: '95.03', unrealized_pl: '-1.15' });
  }
  const record = holding === 'IEF'
    ? { strategy_id: STRATEGY_ID, strategy_version: '1', status: 'ok', signal_date: '2026-10-30', execution_date: '2026-11-02', holding_before: 'IEF', target: 'BIL', mom: -0.0042, switch: true, run_at_utc: '2026-10-30T22:05:00Z' }
    : { strategy_id: STRATEGY_ID, strategy_version: '1', status: 'ok', signal_date: '2026-10-30', execution_date: '2026-11-02', holding_before: 'BIL', target: 'IEF', mom: 0.0123, switch: true, run_at_utc: '2026-10-30T22:05:00Z' };

  // The runner stamps every buy with signal_bar_time = <signal_date>T04:00:00Z (the daily bar). Case "fresh": substitute a bar
  // timestamp under 2 h old, i.e. what a timeframe-aware engine (condition 3) would effectively see. Nothing else is touched.
  const riskCheck = (o, s) => {
    const order = freshBar && o.side === 'buy' ? { ...o, signal_bar_time: new Date(NOW.getTime() - 30 * 60e3).toISOString() } : o;
    const rc = engine(order, s);
    calls.engine.push({ side: o.side, symbol: o.symbol, qty: o.qty, journal_entry_id: o.journal_entry_id ?? null, signal_bar_time: order.signal_bar_time ?? null,
      stop_price: o.stop_price ?? null, cash_seen: s.account?.cash, positions_seen: (s.positions || []).map((p) => `${p.symbol}:${p.qty}`), approved: rc.approved, reasons: rc.reasons });
    return rc;
  };
  const fills = { sell: { status: 'filled', filled_qty: '23', filled_avg_price: '94.97' }, buy: holding === 'IEF' ? { status: 'filled', filled_qty: '23', filled_avg_price: '91.52' } : { status: 'filled', filled_qty: '23', filled_avg_price: '95.03' } };
  const deps = {
    runId: `DRYRUN-${name}`, now: () => NOW, record, mode: 'execute', baseUrl: 'https://paper-api.alpaca.markets', params: {},
    readDecisionMd: () => OK_MD, readRisk: () => RISK, baselineRef: 'benchmarks/baseline.json@dryrun',
    readState: () => state, writeState: (s) => { state = s; },
    readDecisionRecord: (d) => (d === '2026-09-30' ? { ...record, signal_date: '2026-09-30', execution_date: '2026-10-01' } : null),
    executionExists: (sd) => existsSync(join(execDir, `${sd}.json`)),
    writeExecution: (sd, suffix, rec) => writeRecordOnce(join(execDir, `${sd}${suffix}.json`), rec),
    appendRunLog: (r) => calls.log.push(r), decide: () => {},
    buildState: async () => liveState(state?.qty > 0 ? positions : []),
    riskCheck,
    recordEntry: (e) => { const rec = journal.recordEntry(e, { file: journalFile, now: () => NOW }); calls.entries.push({ id: rec.id, symbol: rec.symbol, notional: rec.notional, stop: rec.stop, rule: rec.rule }); return rec; },
    recordExit: (id, x) => { const rec = journal.recordExit(id, x, { file: journalFile, now: () => NOW }); calls.exits.push({ entry_id: id, fills: x.fills, exit_reason: x.exit_reason, pnl_net: rec.pnl.net }); return rec; },
    placeOrder: async (o) => { calls.orders.push(o); return { id: `alpaca-${calls.orders.length}`, status: 'accepted', client_order_id: o.client_order_id }; },
    recordOrder: () => {}, sleep: async () => {},
    getOrderByClientId: async (cid) => (cid.endsWith('-x') ? fills.sell : fills.buy),
  };
  const out = await runMonthly(deps);
  const execFile = out.record?.file;
  const execRec = execFile ? JSON.parse(readFileSync(execFile, 'utf8')) : null;
  return { case: name, action: out.action, exit_code: out.exit_code, reason: out.reason ?? out.record?.reason ?? null, reasons: out.record?.reasons ?? null,
    engine_calls: calls.engine, orders_placed: calls.orders, journal_entries: calls.entries, journal_exits: calls.exits,
    execution_record: execRec && { label: execRec.label, kind: execRec.kind, halt_usd: execRec.halt_usd, one_day_review_usd: execRec.one_day_review_usd, orders: execRec.orders, fill_review: execRec.fill_review ?? null, within_tolerance: execRec.within_tolerance ?? null },
    final_state: state && { holding: state.holding, qty: state.qty, entry_id: state.entry_id, stop_price: state.stop_price, sleeve_equity_usd: state.sleeve_equity_usd, review_hold: state.review_hold, engine_blocked: state.engine_blocked, last_signal_date: state.last_signal_date },
    kill_file_written: existsSync(join(root, 'ops', 'trading', 'KILL')), temp_root: root };
}

const results = [];
for (const c of [
  { name: 'A-buy-IEF-daily-bar', holding: 'BIL', freshBar: false },
  { name: 'B-buy-IEF-bar-under-2h', holding: 'BIL', freshBar: true },
  { name: 'C-sell-IEF-buy-BIL-daily-bar', holding: 'IEF', freshBar: false },
  { name: 'D-sell-IEF-buy-BIL-bar-under-2h', holding: 'IEF', freshBar: true },
]) results.push(await runCase(c));
console.log(JSON.stringify(results, null, 2));
