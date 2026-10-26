# Study 009 — pooled forward check of Studies 006–008 (low-power check)

**Status: pre-registered 2026-10-26; no data.** Nothing is fetched by this study; it reads the forward files of Studies 006, 007 and 008 once, when their first 60 holding periods are complete (about 2031).

- **Question.** Does the equal-weight average of the three rules' forward differences over their exposure-matched mixes (d = T1 − B3, IEF and BIL, base costs) beat zero on data that did not exist when the rules were fixed?
- **Why.** The three histories are one in-sample look at one spent sample (average edge +0.70% a year, mostly before 1986). The forward records are the only clean data. Pooling them is fixed now, before any record exists, so that no pool can be chosen after the fact ([second cold read](../../COLD_READ.md#second-cold-read-2026-10-26), point 2).
- **What it can see.** About 1% to 2.75% a year over 60 months, depending on the dispersion assumed ([`tools/power_pooled.txt`](../../tools/power_pooled.txt)). Not the +0.70% a year the histories showed. "Inconclusive" is the likely outcome whatever the truth; this is a low-power check, not a test that could confirm the histories.
- **Files.** [PREREGISTRATION.md](PREREGISTRATION.md) (rule, members, exclusion, scoring, power), [trials.md](trials.md) (one trial, P1, logged before it runs), [DESIGN_REVIEW.md](DESIGN_REVIEW.md) (separate-session design review before commit, with the response).
