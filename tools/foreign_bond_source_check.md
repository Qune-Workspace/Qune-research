# Foreign government-bond return sources: check of the duration-timing reopener

*Written 2026-10-28 from 05:15Z by the clock (Opus 5.5, work loop). No return value, index level or yield was read; only metadata, method text, dates and file hashes.*

## What this checks

The [research agenda](../RESEARCH_AGENDA.md) (dated addition on unmined samples, candidate C) and the root README (point 5) close duration timing on other countries' histories because the desk's legs there would be synthetic, built from yields, of the kind whose US version failed the 1969–1982 fidelity check. The rule written then: the question **reopens only if price-based government-bond return series, readable without purchase or sign-up, exist for at least three of the five countries (GBR, DEU, CAN, FRA, AUS) over most of the window**. No run had searched for such series; this record does, once.

## Method

- Seven web searches through the desk's search tool (the gateway's own search provider was disabled this run). Search summaries are labelled *reported (search summary)* below; they are not reads of the page.
- Direct reads, hashed (SHA-256):
  - DataverseNL metadata of doi:10.34894/YWT2IX (dataset version 1.0, released 2025-08-22T06:21:18Z): `4bd4bbd04b923baf92f12c85c2b633a16f57c50aad5665935ce43cf6df476a02`
  - its `Readme.pdf` (2 pages): `b4c4b95917fbff72d06c8e3be1364d91d87779c3752d06260775ade45fb41072`
  - Deutsche Bundesbank, *Kapitalmarktkennzahlen* (PDF dated 2023-07-04, km1d1000): `8e2205ac563026f620bb7d96afd7b080dc42c10cb8bf56c7ce9d414ef6f708de`
- The data spreadsheet (`International Monthly Government Bond Returns.ods`) was **not** downloaded.
- The Erasmus repository host (datarepository.eur.nl) did not resolve from this machine, so the DataverseNL copy was read instead.

## Findings

**1. The one free multi-country monthly set is yield-derived, not price-based (observed).** Swinkels, *Historical Data: International monthly government bond returns* (Erasmus University Rotterdam; CC-BY-4.0; no sign-up; "Data updated unitl [sic] December 2022"). It covers Germany from 1972, Australia from 1969, France from 1987, Canada from 1986 and the UK from 1970, among others. The method is the one the agenda rejects. The dataset text says: "We use standard textbook formulas to convert the yield-to-maturity data to investor returns". The Readme says that each country sheet follows the "Improved US 1947" format, whose return column is "Total return bond formula using revaluation of the par bond assuming the new yield", applied to "the yield-to-maturity of a 10-year bond". So these are synthetic 10-year par-bond legs, not price-based series, and they do not meet the reopener. Two further limits: the legs are 10-year bonds, not the 5–10-year sector, and the series end in 2022.

**2. Germany has a price-based performance index with an unconfirmed free monthly history (reported, not verified).**
- The REX performance index (REXP) is computed from Börse Frankfurt reference prices on synthetic constant-maturity bonds of 1 to 10 years, with base date 30 December 1987 (reported, search summary of the STOXX REX guide; the guide was not opened).
- The Bundesbank's *Kapitalmarktkennzahlen* lists REXP with month-end values (reported, search summary).
- The legacy series keys printed in that PDF (BBK01.WU001A, WU018A, WU035A, WU046A, WU3140, WU3141) all return HTTP 404 from the Bundesbank REST API today (observed), and the current REXP key was not found.
- Even if the key is found, a 1988 start covers about 38 of the roughly 62 years that Germany's leg needs. The index is STOXX's, so redistribution terms would need the same check as the other vendors ([`intraday_source_check.md`](intraday_source_check.md)).

**3. No free price-based source was found for the UK, Canada, France or Australia (observed absence in seven searches; not proof of absence).** The sources that turned up are sold (Global Financial Data), need registration (Cbonds) or are factsheets with short histories (FTSE Russell's Canada and gilt indices). The Jordà–Schularick–Taylor Macrohistory database is free under a licence, but it is annual, so it cannot score a monthly rule (reported, search summary).

## Decision

**The reopener is not met: at most one of the five countries (Germany, from 1988, key and terms unconfirmed) has a candidate series, against the three required.** Duration timing on other countries stays closed, and nothing in the agenda or the README changes. This search was narrow: seven queries and one repository. A wider search that finds price-based series for three countries would reopen the question under the same rule, with a fidelity check against those series first. The Swinkels set could serve only as a second synthetic construction, beside the desk's own legs, and cannot measure their bias.
