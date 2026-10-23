# Study 005: question choice and design constraints (step 0, before the pre-registration)

*Qune, 2026-10-23 08:2x London. Committed before `PREREGISTRATION.md` exists, before any file is fetched and before any return is computed for this study. This note fixes the question, the three design problems the agenda flagged, and the decisions that resolve them, so that the pre-registration can be written from it without a second look at any data. Where this note and the later pre-registration differ, the pre-registration governs and must say why.*

## 1. The question, and where it comes from

Study 003 asked whether a 12-month trend rule on IEF (long IEF when its trailing 12-month return exceeds bills, else bills) beats holding IEF. In-sample (2003-08 to 2018-12, 185 months) it did not: Sharpe 0.45 against 0.55, the cash months were the wrong months (IEF beat cash in 58% of them). Out of sample (2019-01 to 2026-09, run once) it did, on one decision: the rule sat in bills from February 2021 to July 2024 through the 2022 sell-off. The research agenda (`RESEARCH_AGENDA.md` §4 and §5 item 3) records the observation that the one episode in which the trend exit paid is the period in which the stock-bond correlation turned positive, and ranks the resulting question third:

> **Does a trend exit from duration add value when the stock-bond correlation is positive, and cost when it is negative?**

The mechanism is Campbell, Pflueger and Viceira (2020): when inflation shocks dominate, bonds and equities fall together and duration is a risk to be managed; when demand shocks dominate, bonds hedge equities, and selling duration after a sell-off gives up that hedge. Ilmanen (2003) and Brixton, Brooks, Hecht, Ilmanen, Maloney and McQuinn (2023) document the regime's long history and its 2022 reversal. In that reading, Study 003's in-sample failure and out-of-sample success are not a contradiction: both are what the mechanism predicts, because 2003-2018 was almost entirely a negative-correlation regime and 2021-2024 was not.

This is the programme's first question that comes from its own evidence rather than from a paper. That is its merit and its danger, and the next section is about the danger.

## 2. Three design problems, and the decisions that resolve them

### 2.1 The hypothesis was generated from the held-back window

The 2019-2026 window is the programme's shared out-of-sample period. Study 003 touched it once, as the rule permits, and the author saw the result: the hypothesis above was formed from that result. A test of the hypothesis on the same window would be a post-hoc story confirmed on the data that suggested it. The programme's rule ("never touch an out-of-sample window twice") exists for exactly this.

**Decision.** For Study 005 the 2019-2026 window is **not a test**. It is the hypothesis-generating episode and will be reported, once, under that label with no decision weight, so that the reader can see the episode the question came from. The study's tests are:

1. **In-sample 2003-08 to 2018-12.** The author has seen the unconditional rule's result on this window (Study 003: it lost) but formed no regime hypothesis from it. The regime split of that window is new information. Its limits are in §2.2.
2. **The forward record** from the first month-end after publication, scored under a stopping rule fixed in the pre-registration (§2.4). This is the only clean test, and the study is designed around it.

The consequence is that Study 005 cannot deliver a "supported" verdict from history. The pre-registration will say so in its first paragraph.

### 2.2 The in-sample test has almost no power, and the pre-registration must say by how much

The quantity on trial is the conditional edge: the mean of the differential d_t = (trend rule return − hold-IEF return) in positive-regime months minus the same mean in negative-regime months. The differential is zero in months the rule is long and equals minus IEF's excess return in months it is in bills. From Study 003's published in-sample figures (not a new computation): IEF's annualised volatility was 6.27%, so its monthly excess return has a standard deviation of about 1.8%; the rule was in bills in 30.8% of months, so the differential's unconditional standard deviation is about 1.8% × √0.308 ≈ 1.0% per month.

Minimum detectable effect at a one-sided 5% level with 80% power, 185 months, as a function of the share s of months in the positive regime (the share is not computed here; the published history says it was small, see Brixton et al. 2023 and the desk view's 8% of days in 2017-2021):

| s | positive-regime months | MDE, per month | MDE, annualised |
|---|---|---|---|
| 10% | 19 | 0.61% | 7.3% |
| 20% | 37 | 0.46% | 5.5% |
| 30% | 56 | 0.40% | 4.8% |

(MDE = (1.645 + 0.842) × σ_d × √(1/n₁ + 1/n₂).) A believable conditional edge is one to three percent a year. **The in-sample window cannot detect it.** Counting only the months in which the rule was actually in bills, where the differential is non-zero, makes the figure worse, not better.

**Decision.** The in-sample part of Study 005 is pre-registered as a **sign and mechanism check**, not as a test that can support the hypothesis: it can refute the hypothesis (the conditional edge has the wrong sign with a confidence interval that excludes the predicted magnitude) or leave it "inconclusive, forward record decides". The pre-registration will state the MDE table above with the actual regime share filled in after the data check and before any return, and the verdict table will have no "supported from history" row. The power problem is the honest reason this study is cheap: it reuses Study 003's frozen rule and the 004 library, adds one regime variable, and spends its effort on the forward record.

### 2.3 The regime variable must be defined from trailing data with no look-ahead

**Decision.** The primary regime variable (T1) is the sign of the trailing 63-trading-day correlation of daily SPY and IEF total returns at the signal date (the month-end close), from the same vendor files as the returns. Positive regime: correlation > 0; otherwise negative. No dead band, no smoothing, so that the rule cannot be tuned. The 63-day window is the convention the desk view adopted on 2026-10-23 before this study, not a choice made on Study 005's data. Two pre-registered alternatives, descriptive and with no decision weight: T2, the same with a 252-day window (slower, fewer regime changes); T3, an inflation regime from FRED CPI (trailing 12-month headline CPI inflation above 3%, using the value published before the signal date with a two-month lag so that no vintage is used before it existed). N = 3; the trial ledger is written before the first run.

SPY enters only as the regime input, never as a traded asset or a return in any table. Study 004 excluded SPY from its traded universe because its vendor-versus-broker level gap failed a ±0.20% gate; a level gap of that size does not move a 63-day correlation sign, and the pre-registration will say so and carry the overlap check as a descriptive, not a gate.

The conditional rule itself: in a positive regime, apply Study 003's T1 (long IEF when its 12-month return exceeds bills, else bills); in a negative regime, hold IEF regardless of the trend signal. Benchmarks: B1 hold IEF throughout; B2 the unconditional trend rule (Study 003's T1, frozen code, its in-sample path known to the author); B3 the constant mix with the conditional rule's average IEF exposure (the exposure-matched benchmark Studies 003 and 004 use). The decisive comparison in-sample is the conditional edge of §2.2, which is the same as "does conditioning improve B2, and does it do so for the stated reason"; B1 and B3 are there so that the conditional rule cannot be credited with the long bias.

### 2.4 The forward record needs a stopping rule fixed now

**Decision, to be written into §11 of the pre-registration.** The forward record starts at the first month-end after publication (shadow record only; no paper order under this study). It is scored once, when **either** 24 positive-regime months have accumulated **or** 60 months have passed, whichever is first, on the conditional edge's sign and its confidence interval; interim figures are published every month under a "not yet scored" label. The rule's purpose is to stop the author choosing when to score. It does not buy power: with 24 positive-regime and 36 negative-regime months the MDE formula of §2.2 gives about 0.65% per month, roughly 8% a year, so the forward record is a weak test too, and the pre-registration will say so rather than promise more. What the forward record has that history lacks is that nobody has seen it.

## 3. Why not the alternatives on the agenda's list

- **Bond carry, and carry plus trend (agenda item 2).** A better-powered study and a different signal; it does not come from the programme's own finding, which is what this slot in the plan is for. It is the next candidate after this study, and the pre-registration of this study must not borrow anything from it.
- **A multi-asset regime study on the 004 universe.** Adding TLT, SHY and LQD to the duration leg would not add independent regime episodes, because they share IEF's regime; it would add complexity to a study whose honest product is a single, well-defined forward test.
- **Extending history before 2002 with a synthetic bond series.** Studies 001 and 002 halted on exactly that; the rule is actual ETF history only.

## 4. What this note does not do

No file was fetched, no regime share was computed, no return was computed and no parameter was chosen on Study 005's data. The MDE table uses Study 003's published in-sample metrics and assumed regime shares. The pre-registration (`PREREGISTRATION.md`, with `trials.md`) is the next step and must be committed before the data check; it inherits the execution timing, cost model, metrics, statistical tests, verdict precedence and amendment rules by reference to Study 003 and writes out everything that differs (the regime variable, the conditional rule, the benchmarks, the criteria built around the conditional edge, the role of the 2019-2026 window, the stopping rule). Order of operations after that: library and study code with tests, `APPROVED`, data check once, in-sample run once, note, the 2019-2026 episode reported once under its label, independent review, forward record.

## References

Checked against Crossref by `tools/check_citations.py`; output in `citations_check.txt` beside this note.

- [BBHIMM23] Brixton, Brooks, Hecht, Ilmanen, Maloney, McQuinn (2023). A Changing Stock–Bond Correlation: Drivers and Implications. The Journal of Portfolio Management 49(4). doi:10.3905/jpm.2023.1.459
- [CPV20] Campbell, Pflueger, Viceira (2020). Macroeconomic Drivers of Bond and Equity Risks. Journal of Political Economy 128(8):3148–3185. doi:10.1086/707766
- [I03] Ilmanen (2003). Stock-Bond Correlations. The Journal of Fixed Income 13(2):55–66. doi:10.3905/jfi.2003.319353
