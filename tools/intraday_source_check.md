# Intraday source check: SPY minute bars on the desk's paper market-data feed

Written 2026-10-27 from 22:1xZ by the clock, for the reopener in RESEARCH_AGENDA's pre-FOMC drift
addition ("a free intraday S&P 500 (or SPY) source covering 2011–2026 for the 2pm-to-2pm form").

**What was run.** A private probe script (it loads the paper-account market-data keys from a file
outside this repository; it is not published) asked Alpaca's market-data API (`/v2/stocks/SPY/bars`,
`adjustment=raw`) for SPY bars. It printed **bar counts and first/last timestamps only; no price was
printed, read or kept**. Nothing was written to this repository by the probe. Run 2026-10-27
22:16Z (output observed by Qune and copied below by hand).

**Minute bars, 13:30–21:00 UTC on the date shown** (count, first, last):

| feed | 2011-03-15 | 2013-06-19 | 2015-12-16 | 2015-12-30 | 2015-12-31 | 2016-01-04 | 2016-01-05 | 2016-01-27 | 2020-01-29 | 2026-09-17 |
|---|---|---|---|---|---|---|---|---|---|---|
| sip | 0 | 0 | 0 | 0 | 0 | 451 (13:30Z–21:00Z) | 451 | 451 | 450 | 449 |
| iex | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 393 (13:30Z–20:02Z) |

**Daily bars per calendar year, sip feed** (count): 2015 0; 2016 252 (first 2016-01-04); 2017 251;
2018 251; 2019 252; 2020 253; 2021 252; 2022 251; 2023 250; 2024 252; 2025 250. The 2026 query was
refused ("subscription does not permit querying recent SIP data") because its end bound reached the
last 15 minutes; the 2026-09-17 minute query above succeeded. The yearly counts were not checked
against an exchange calendar file.

**Result (observed).** The free feed carries SPY minute bars from **2016-01-04**, not from 2011. The
reopener as written (2011–2026) is **not met**. The 2pm-to-2pm form can be built only for the
scheduled meetings of 2016-01..2026-09: **N = 85**. Power on that window is in section 6 of
[`power_fomc.txt`](power_fomc.txt): minimum detectable mean 0.375% a meeting = **0.77×** the
published 2pm-to-2pm edge at the paper's standard deviation (0.58×–0.96× across ±25%); Sharpe
0.872 = 0.77× (0.85× at the largest Newey-West ratio). Recomputed in a separate session before
commit ([`power_fomc_recompute.md`](power_fomc_recompute.md), section 6: every figure matched).

**Not checked (for any later step):** whether Alpaca's market-data terms allow publishing statistics
derived from SIP bars (raw bars would not be published either way); whether every meeting day and
the day before have a 14:00 ET bar (checked since, below); FOMC statement release times 2016–2026 (checked since, below); SPY against the S&P 500
index (an ETF with dividends and tracking error, not the paper's series).

## Check 3 of the 2026-10-27 22:1xZ agenda addition: a 2pm bar on every meeting day and the day before (2026-10-27 22:2xZ)

Statement dates for the 85 scheduled meetings held 2016-01..2026-09 were read from the Fed's pages
([`fomc_statement_dates_2016_2026-09.txt`](fomc_statement_dates_2016_2026-09.txt): 8 a year, 2020 7,
2026 6, the same per-year counts as the separate-session recount). A second private probe took the
trading days from SIP daily-bar timestamps (2,701 days, 2016-01-04..2026-09-30; not checked against an
exchange calendar) and asked for the SPY minute bars stamped 13:59 and 14:00 New York time on each
statement date and the trading day before it, comparing timestamps only (no price field read).
**Result (observed): 85 statement dates, all trading days in the feed; 340 bars checked; 0 missing.**
Check 3 passes.

## Check 2: statement release times (2026-10-27 22:3xZ)

[`fomc_calendar.py`](fomc_calendar.py) (public pages only; output [`fomc_calendar.txt`](fomc_calendar.txt))
reads each of the 85 statements' own "For release at ..." line. **Result (observed): all 85 state
2:00 p.m. New York time (24 EST, 61 EDT).** The script also regenerates the statement-dates file; its
run reproduced the file committed with check 3 unchanged, and its 85 times equal an earlier ad hoc
run's. Check 2 passes, with one consequence for any QUESTION.md: the release falls on the 2pm mark,
so the minute bar stamped 14:00 contains the release minute and cannot be the pre-announcement price.
Which earlier price is used (the 13:59 bar's close or an earlier cut) is a construction choice to be
fixed and justified in QUESTION.md, before any price is read. The release time is the stated embargo
time, not an observed timestamp.

Earlier record (kept): check 1 (whether Alpaca's market-data terms allow publishing statistics derived from SIP bars).
Read so far (2026-10-27 22:25Z): Alpaca's "About Market Data API" page (docs.alpaca.markets, page
metadata updatedAt 2026-10-06) states "Historical data timeframe: Since 2016" for both equity plans
and "latest 15 minutes" as the free plan's historical limitation, which agrees with the probe above
(reported, corroborating the observed start). It says nothing on publishing derived statistics. The
website's Terms & Conditions PDF was downloaded but not read (no PDF text tool in this environment),
and a market-data agreement was not found at the paths tried. Check 1 stays open.

## Check 1: market-data terms (2026-10-27 23:1xZ; this heading first said 23:2xZ, corrected from the commit time 23:17:46Z)

Read this run: Alpaca's Terms and Conditions, linked as "Terms & Conditions" from alpaca.markets/disclosures
(https://s3.amazonaws.com/files.alpaca.markets/disclosures/library/TermsAndConditions.pdf, fetched
2026-10-27 23:15Z, 27,092 bytes, SHA-256 `2dc774d4aeeafbe4c7f0565e7842d932bc8bc10488af805fce43b8734e7b9859`,
four pages, read in full with a PDF reader; the earlier "no PDF text tool" was mine: one was available).
The clauses that bear on publishing (quoted):

- "Content includes, without limitation: ... (3) market data such as quotations for securities transactions
  and/or last sale information for completed securities transactions ..."
- "Other than as set forth herein, you agree to use the Services and Content solely for your own personal and
  non-commercial purposes." Other uses, or "making the Services and Content available to others through your
  own application", need 30 days' advance written notice to Alpaca.
- "Content is provided exclusively for personal and noncommercial access and use. No part of the Service or
  Content may be copied, reproduced, republished, uploaded, posted, publicly displayed, encoded, translated,
  transmitted or distributed in any way (including "mirroring") to any other computer, server, web site or
  other medium for publication or distribution or for any commercial enterprise, without Alpaca's express
  prior written consent."
- The free 'Basic' plan names no further exchange agreement; the paid 'Pro' plan adds the NASDAQ OMX Global
  Subscriber Agreement or the Agreement for Market Data Display Services. No separate market-data agreement
  for the free plan was found.

**Result (observed, as read; not legal advice): check 1 does not pass as written.** The queue line required
the terms to *allow* publishing statistics derived from the bars. They forbid publishing the market data
itself (bars, prices, any bar-level series) without written consent and say nothing either way about
statistics derived from it. Silence is not an allowance.

What follows (decided by Qune, 2026-10-27 23:1xZ):

1. Study 012 stays queued. Its QUESTION.md may be written (no price is read and nothing from the feed is
   published by writing it), but it must carry a publication clause: only aggregate statistics over the
   85 meetings (count, mean, standard deviation, t, share positive, and the same by sub-period), never a
   price, a bar, a per-meeting return or any series from which bars could be rebuilt.
2. No price is read for Study 012 until the owner has chosen between (a) publishing aggregates under that
   clause on this reading of the terms, and (b) asking Alpaca for written consent first. Contacting Alpaca is
   outside the desk's rights, so (b) is the owner's step. Qune's recommendation: (b) if it costs a single
   message, otherwise (a), because aggregate test statistics are not the quotations or last-sale data the
   clause names, and nothing here is commercial.
3. The same reading applies to what is already public. Studies 001, 003, 006, 007 and 008 list Alpaca daily
   IEF and BIL bars in their data manifests ("licensed, not redistributed"; the raw files were never
   committed). Whether any committed monthly or daily series rests on those bars, rather than on the
   Tiingo files, was not traced this run; Tiingo's own terms were not re-read. Both are open, recorded here
   so that the answer to item 2 covers them too. Nothing already published was changed or removed.

### Correction (2026-10-27 23:2xZ, same run; the paragraph above stays as written)

Item 1 above departed from the rule fixed before the check: the agenda's 22:1xZ addition said "no
QUESTION.md until three checks pass" and "If (1) fails, the question closes again". A separate Opus
review of a draft QUESTION.md caught the departure before anything was committed. **The rule is kept:
the pre-FOMC question closes again.** No QUESTION.md was committed; the draft and its review stay private
and are not evidence. Items 2 and 3 above become the reopener: the question reopens only by a new dated
agenda addition, made before any SPY price is read, after either (a) the owner decides that aggregate
statistics may be published on this reading of the terms, or (b) Alpaca gives written consent. The
aggregates-only publication clause would bind either way.

### Item 3 traced (2026-10-27 23:2xZ, same run; from the code and its docstrings, nothing re-run)

Committed series computed from Alpaca daily bars of IEF and BIL (`adjustment='all'` closes; the bars
themselves were never committed):

- Study 001: the validation checks and report (`src/validate.py`, `src/report.py` load the bars).
- Study 003: the out-of-sample run (`src/report.py`: "out-of-sample window once on Alpaca bars and writes
  `results/oos/`"), so `results/oos/monthly_base.csv` and `monthly_stress.csv` hold monthly returns of
  the IEF and BIL legs from those bars; `results/checks/bil_vendor_decision.*` compares Tiingo and Alpaca
  BIL returns (aggregates only).
- Studies 006, 007 and 008: the actual-ETF episode (`src/episode.py`: "Actual IEF and BIL from Alpaca"),
  so `results/episode/actual/monthly_*.csv`; their forward code fetches Alpaca closes for the forward
  records.

These are monthly returns, not quotations or last-sale reports, but they are series derived from the
bars, not only aggregates over many periods, so they are a step closer to the terms' "Content" than the
aggregates-only clause would allow for Study 012. Recorded for the owner's decision; nothing changed or
removed. Tiingo's terms (the other licensed vendor) were not re-read.

### Tiingo terms read, Tiingo-derived series traced (2026-10-28 from 01:15Z; the sections above stay as written)

The 23:2xZ trace left two things open: Tiingo's terms (the other licensed vendor) and which committed
series rest on Tiingo files. Both are answered here. Nothing published was changed or removed.

**Terms.** The current terms page (`www.tiingo.com/tos`, the link the site's sign-up form uses) returned a
bot challenge to every plain request this run, and the browser tool was unavailable, so the current text
was **not read**. Read instead:

- The Internet Archive copy of `https://www.tiingo.com/tos/` captured 2022-06-03 (the only capture with
  status 200), "Effective Date: January 16th, 2022", decompressed HTML SHA-256
  `44a61ee5416ec674d304a868488781cb5c318c5e90c82646e795ed632bad0708`. Section 7.3, "Use of the Tiingo API":
  "All data via the API is for internal consumption only. If you are an individual, you may sign up for an
  Individual plan; however, if you are representing an organization or business, you must sign up for a
  Commercial plan. Redistribution is only available upon special request and permission, and comes with
  additional fees." If redistribution is permitted, the attribution "Data sourced by Tiingo" with a link is
  required. Section 1.4(a) also bars reproducing or distributing "Company Properties", which include "the
  information and content available on the Website and in the Application and the Services".
- The live site's pricing text, from its current JavaScript bundle (fetched 2026-10-28, SHA-256
  `4d6004e95fc26d2de7c7e619b06a52a82f731abfbf524b49b29811c75a11b492`): plan rows marked "Internal Use Only";
  "Commercial plans allow for internal use for up to two (2) developers. For more developers or to
  redistribute data, please contact" sales; "Our API is included in a Tiingo.com subscription for
  individuals & personal use. For those who have commercial or redistribution needs, we offer [...]
  pricing". This agrees in substance with the 2022 text but is not the terms themselves.

Reading (not legal advice): Tiingo's API data is for internal use; publishing it, or series from which it
can be rebuilt, needs Tiingo's permission. Like Alpaca's terms, the text says nothing about aggregate
statistics. Which plan the desk's token is on (Individual or Commercial) is an account fact this run did not
check; the 2022 text ties organisational use to a Commercial plan.

**Committed series computed from Tiingo daily files** (from the code and config; one row checked by hand):

- Studies 003 and 005, `results/insample/monthly_base.csv` and `monthly_stress.csv` (185 months,
  2003-07 to 2018): column B1 is the buy-and-hold IEF return between execution dates from Tiingo `adjClose`.
  Checked this run against the git-ignored raw file: 2003-08-01 to 2003-09-02 gives −0.006918072288497168
  from the raw file and −0.006918072288497057 in the committed file; 2010-03-01 to 2010-04-01 matches to
  every printed digit. The IEF adjusted close at monthly execution dates can therefore be rebuilt from the
  committed file, up to a scale.
- Study 004 (twelve-ETF universe; IEF reused from 002, BIL from 003, the others fetched under 004, all
  Tiingo): `results/insample/` and `results/oos/` daily and monthly index files of the benchmark and rule
  portfolios (multi-asset mixes; B0 out of sample is BIL alone), and the per-asset monthly signal tables
  `signal_s3/s6/s12/vol_*.csv` (each ETF's trailing return and volatility at every signal date).
- Study 002 used Tiingo IEF for its validation and overlap checks; its committed outputs found here are
  validation statistics (aggregates).
- Studies 006, 007 and 008: their long histories run on yields from FRED (public), not on Tiingo; Tiingo IEF
  enters their overlap checks (aggregates).

So the owner's decision (items 2 and 3 above) has a second vendor in it, with stricter wording than Alpaca's
("internal consumption only"). For each vendor the same three choices stand: (a) keep the derived series
public on the reading that returns are not the vendor's data; (b) ask the vendor for permission (external
contact, so only the owner can); (c) remove the per-asset and single-asset return series from HEAD and
publish aggregates only. Under (c), removal from HEAD does not remove them from the public git history;
only a history rewrite and force-push would, which cannot be fully undone once clones exist, and is an
owner decision. The front page's "Not a data distribution" line was qualified this run to say what is
committed.

### French Data Library and FRED terms read, their committed series traced (2026-10-28 from 02:15Z; the sections above stay as written)

The two traces above covered the licensed vendors (Alpaca, Tiingo). The programme's other two sources are
the Kenneth French Data Library (Studies 010 and 011) and FRED (yields, CPI and the desk view). This
section reads their terms and lists what is committed from them. Nothing published was changed or removed.
Tiingo's current terms page was tried again this run (`www.tiingo.com/tos`, which redirects to
`app.tiingo.com/tos`): HTTP 403 with a bot challenge to plain requests, browser tool still unavailable, so it
is still **not read**; the challenge was not bypassed.

**Bad news first: the front page was wrong.** It said "Raw vendor data is re-fetched by the scripts and
never committed". For the French library that is false: two committed files are exact copies of a block of
a library file, and four columns of a third are copies of library factor series. Checked this run against
the git-ignored raw zips, value by value:

- Study 011 `results/history/industries_17.csv` and `industries_30.csv`: the "Average Value Weighted Returns
  -- Monthly" block of `17_Industry_Portfolios.csv` and `30_Industry_Portfolios.csv` ("created using the
  202608 CRSP database"), 1926-07 to 2026-08; **1,202 of 1,202 rows identical** in each file. They were
  committed so that a separate session could rebuild the rule without the study's code (011 README).
- Study 010 `results/history/monthly_base.csv` and `monthly_stress.csv`: columns `f_SMB`, `f_HML`,
  `f_ST_Rev`, `f_LT_Rev` are the library's factor returns; `f_SMB` and `f_HML` equal
  `F-F_Research_Data_Factors.csv` on **1,190 of 1,190 months** (the two reversal columns were not checked
  this run).

**French Data Library terms.** The library page
(`mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html`, fetched 2026-10-28 02:17Z, SHA-256
`dd48316327898aea2e3ad3dd070b34c3325ce3b25ced7f719245efd5ad36146a`) carries one line on rights: "Copyright
Eugene F. Fama and Kenneth R. French". It has no licence, no terms of use and no word on redistribution or
permission (searched: "licen", "terms", "permission", "redistribut", "commercial": none). The returns are
built from CRSP files (the page and each file say so). Reading (not legal advice): a copyright notice with
no licence grants no right to republish; academic practice is to cite the library, and many public
repositories carry copies, but that is practice, not permission. Republishing full tables is closer to
copying the files than publishing statistics computed from them.

**FRED terms.** The live site did not answer this run (every request to `fred.stlouisfed.org`, including
`/legal/` and three series pages, failed or timed out). Read instead from the Internet Archive:

- `fred.stlouisfed.org/legal/` captured 2026-10-25 04:31:27Z, decompressed HTML SHA-256
  `a5a80d2b67566ddcaf4d021df0ff37193a45c763b3e321ade5c0ac95b24998e2`. Three copyright classes: "Copyrighted:
  Pre-approval required ... Without first obtaining the express written permission of the copyright holder
  ... these series may only be used for non-commercial educational or personal use"; "Copyrighted: Citation
  required ... you may use these data series with proper attribution"; "Public Domain: Citation requested".
  Also: "Before using data with a copyright notice for anything other than your own personal use, you must
  contact the data owner to obtain permission. Unfortunately, the Federal Reserve Bank of St. Louis cannot
  give you such permission."
- `SP500` series page captured 2026-10-27 14:40:22Z (SHA-256
  `1103cb113164edc1aa02d0899287a3605c71e62479f1a75fbd4abb87e5a278fa`): "Copyright © 2016, S&P Dow Jones
  Indices LLC. All rights reserved. Reproduction of S&P 500 in any form is prohibited except with the prior
  written permission of S&P Dow Jones Indices LLC".
- `BAMLH0A0HYM2` series page captured 2026-10-21 00:47:14Z (SHA-256
  `f4b97b7045fb9a671fd79ee9bd4dcc7d2a9e3f292189aa4a23d35dedbc1f18c6`): "Copyright, 2023, ICE Data Indices.
  Reproduction of this data in any form is prohibited except with the prior written permission of ICE Data
  Indices. The end of day Index values, Index returns, and Index statistics ("Top Level Data") are being
  provided for your internal use only and you are not authorized or permitted to publish, distribute or
  otherwise furnish Top Level Data to any third-party without prior written approval".
- `VIXCLS`: the nearest capture (2026-10-22) is a site-maintenance page, so its notes were **not read**.
- The copyright class of the other FRED series the programme uses (Treasury yields, TIPS, breakevens, the
  Kim-Wright term premium, EFFR, the target range, CPI) was **not checked** this run.

**Committed from the three flagged FRED series** (raw files are git-ignored under `desk-view/data/raw/` and
`predictions/raw/`): one level each in `desk-view/data/snapshot_2026-10-23.csv` and
`numbers_2026-10-23.json` (S&P 500 7,757.17; high-yield OAS 3.27%; VIX 16.68), the high-yield OAS row with
its 1-, 3- and 12-month changes and the VIX row in `DESK_VIEW.md`, and the 63-day stock-bond correlation
chart computed from daily S&P 500 and 10-year yield changes (a statistic, not the index).

Reading (not legal advice): S&P's and ICE's notes forbid reproduction "in any form" without permission and
ICE limits its values to internal use; the desk view publishes one level of each. FRED's own page allows
"non-commercial educational or personal use" of such series without permission; whether this public
research showcase is that is an owner judgement, not mine. So the owner's decision now has four sources in
it, with the same three choices per source as above ((a) keep, (b) ask the owner of the data, which only the
owner can do, (c) remove from HEAD). For the French tables a fourth choice exists: (d) replace the committed
copies with a download script checked against the SHA-256 hashes already in each study's
`results/data_manifest.json`. Its cost: the library rebuilds its files from each new CRSP release (these are
from the 202608 database), so after the next release the hashes will not match and an outside reader could
no longer rebuild the histories exactly; the committed copies are what make that rebuild possible today.
Recommendation: (a) for the French tables, cited, unless the owner judges the risk otherwise ((d) if not);
(c) for the three single FRED values (the desk view argues from none of them); both reversible from git; for
new work, statistics only. The front page's line is corrected this run.
