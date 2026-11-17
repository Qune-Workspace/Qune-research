# Trial log: Study 014, the longshot spread premium at the horizon

Approval: the owner delegated all decisions on this research programme to the orchestrator on 2026-10-21 and set its scope to prediction markets on 2026-10-31. This pre-registration is approved by the orchestrator under that delegation on the date of its first commit. An `APPROVED` file is written at implementation time (PREREGISTRATION.md §14 step 4), after the engine's separate-session code review.

Every trial is logged here before it is run. **Criterion C3 is decided at N = 3** (a new family, PREREGISTRATION.md §9.4; a Bonferroni bar, t_cl ≥ 2.128); the programme-wide count is re-counted immediately before the analysis run, written below, and has no decision weight. Any further rule, parameter or sample change after the pre-registration's commit is a dated §16 amendment first and a row here second.

## Registered trials (N = 3)

| ID | Date logged | Description | Sample |
|---|---|---|---|
| M1 | 2026-11-17 (this commit) | Δ = mean(ln s \| longshot) − mean(ln s \| central), s the relative quoted spread max(ask − bid, tick) / mid on the snapshot-of-record row at h = 24 h before `closedTime` (§6.2); longshot 0.01 ≤ mid < 0.10, central 0.40 ≤ mid ≤ 0.60 (§6.3); SE clustered by parent event (§9.3); C1 Δ̂ ≥ 0.59, C2 t_cl ≥ 2.0, C3 t_cl ≥ 2.128, C4 Δ̂ > 0 on W1 and W2 (§9.5) | Study 013's C1 data-step rows less the two followed events (§6.3), W = `closedTime` in [2026-11-04, 2026-12-30) |
| M1a | 2026-11-17 (this commit) | Sports companion: M1 with every market flagged Sports on its sample row set aside | Study 013's C1a rows, as M1 |
| M1b | 2026-11-17 (this commit) | Horizon companion: h′ = 168 h; otherwise M1 | Study 013's C1b rows, as M1 |

None of the three has been run. No bid, ask, spread or mid of a windowed market has been read for this study; Study 013's sample file does not exist yet (its data step runs after 2027-01-20 00:00Z).

## Log

| Step | Date | Outcome |
|---|---|---|
| Question note (step 0) | 2026-11-16, commit `b2dbeb8` (18:3xZ by the clock; git holds the time) | No spread read; power from counts only (`tools/power_pm014.txt`, MDE 0.280, ratio 0.24, an upper bound); question gate pass. |
| Design review of the pre-registration (separate session, Opus 5.5, isolated, read-only, no network) | 2026-11-17, 00:22–00:29Z by the clock, before the first commit of PREREGISTRATION.md | Approve with changes ([DESIGN_REVIEW.md](DESIGN_REVIEW.md)): 6 must-fix (the window's first thirteen days closed before the document, so the timeline claim was false; two fields read but not listed; the inherited stop and halt undecidable from the listed inputs; "no fit" undefined; three unlisted departures from the note; a low-power label whose sentence was false between ratios 0.50 and 0.96) and 14 should-fix, all taken before the commit. |
| Pre-registration committed (§14 step 1) | 2026-11-17 (this commit; its own time is the record) | No spread read; no data of this study exists; `.gitignore` gains `research/014-polymarket-spread-at-horizon/results/rows.jsonl`. |
