# Source check: the FOMC meeting list against the Fed's pages

The bill-implied FOMC reading (`pm-view/fomc_calibrate.py`) is scored and read on the scheduled meetings of
[`fomc_statement_dates_2016_2026-09.txt`](fomc_statement_dates_2016_2026-09.txt) plus the two dates the
pre-specification names in `EXTRA_MEETINGS` (2026-10-28, 2026-12-09). The published calibration (net Brier
0.298 on 74 meetings 2017-07..2026-10, R2 pass; `pm-view/README.md` rule 5) rests on that list. Since
2026-11-16 the list is named by hash on every record, which holds the bytes still but says nothing about
whether the bytes were right. This file records each re-read of the list against its source. A re-read is
`python tools/fomc_calendar.py --check [--pages DIR]` from the repository root: it writes nothing and exits 1 on
any difference. Dates are UTC from the machine clock.

## 2026-11-18, read 00:17:42–00:17:43Z (learning-loop 00:15Z run)

**Pages read** (HTTP 200 each, `curl`, no credentials; copies kept git-ignored under
`tools/data/raw/fed_pages_2026-11-18/`, SHA-256 of the bytes as fetched):

| page | bytes | SHA-256 |
|---|---|---|
| /monetarypolicy/fomccalendars.htm | 166,065 | 1cc173516bb1e576ca72c9b9fbde5b1dd95560c2b1dedf1d23b5be48798c671e |
| /monetarypolicy/fomchistorical2016.htm | 96,005 | 92187b39c89028dbf5b722c9fa6ffdd846d96e3cfe0f7849aef24faf71f17422 |
| /monetarypolicy/fomchistorical2017.htm | 95,376 | 00a196412254782768f39bcf765d0d11f9498e2d67b9d57ac4120b67d04285f6 |
| /monetarypolicy/fomchistorical2018.htm | 95,881 | 922150ed202fa9a531dee4b97086e58655a08e5e6bfa7203fc5a19dc428c2137 |
| /monetarypolicy/fomchistorical2019.htm | 97,520 | bcd40c98d56c5b32c35a605152dc5a1a012a6c5a638f7abef0d16bef105331e5 |
| /monetarypolicy/fomchistorical2020.htm | 98,731 | 3647fd1cc93154c7aace996b501d86440721728089ecca98bd16cb33ec89b9d2 |

The current page states "Last Update: November 12, 2026".

**Result [observed].** Under the rule of 2026-10-27 (the `monetaryYYYYMMDDa.htm` statement link of each meeting
row; rows marked unscheduled, cancelled, notation vote or conference call excluded; dates after 2026-09-30
excluded) the pages give 85 dates, per year 2016 8, 2017 8, 2018 8, 2019 8, 2020 7, 2021–2025 8 each, 2026 6.
The committed file (SHA-256 `8f7d75a3…e8253a`, one commit 9e93b4a of 2026-10-27 22:22:02Z) holds the same 85
dates in the same order: none only on the pages, none only in the file. **The list the calibration was scored
on is the Fed's list.** No published figure changes.

**Rows beyond the cut-off [observed].** 2026: October 27-28 has its statement (`monetary20261028a.htm`); December
8-9 has none yet. Both are the dates in `EXTRA_MEETINGS`. 2027, no statements, the page's own caveat quoted:
"Each meeting date is tentative until confirmed at the meeting immediately preceding it": January 26-27,
March 16-17, April 27-28, June 8-9, July 27-28, September 14-15, October 26-27 (the row reads "October 26-27
Monetary Policy Strategy Meeting"), November 16-17; "A two-day meeting is scheduled for January 25-26, 2028".
Eight rows, none in December; 21 days between the October and November rows.

**What this found about the desk's list [observed, then built].** The list ends at 2026-12-09. The reading's
"a meeting in between" rule (`fomc_calibrate.reading`) can only refuse a meeting it knows: a reading made for
2027-11-17 at the 35-day lag would span 2027-10-27 and, with the list ending in 2026, would have been made.
And the rule of 2026-11-16 bound every record to the whole file's hash and count, so the first extension of
the list would have made every candidate, and the calibration's own `inputs_meetings`, unreadable at
recomputation. Changed on 2026-11-18 00:15Z (`predictions/POST_MORTEMS.md`, follow-up to "A sample held by
nothing but the file that listed it"): a record carries `through` (its last meeting) and `dates_digest`
(SHA-256 of the dates alone), a list that carries the same dates through `through` is the record's list, and
`live_figures` refuses a meeting the list does not reach, naming the last listed date.

**Not done, dated.** The 2027 dates are not in the list: they are tentative by the Fed's own words, and the
extension is a decision for the run that first needs them (the first reading of 2027-01-27 is possible from
the view after 2026-12-09, so before the view of 2026-12-11, or that view's reading is refused by name, not
made wrongly). When extended, the file's header, name and `fomc_calendar.py`'s cut-off say what the list
covers; `--check` is re-run; the record of that run goes under a dated heading here.
