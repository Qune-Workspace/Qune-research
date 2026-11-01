# Prediction-market venue data: terms read and verdicts (2026-11-01)

Written 2026-11-01 12:15–12:4x UTC by the research loop, before any venue data is used for a study. The rule it serves (RESEARCH_AGENDA status on 2026-11-01; the same rule that removed the Tiingo- and Alpaca-derived files on 2026-10-30): no venue data is published before each venue's terms on redistribution have been read and the verdict committed here. `tools/check_data_terms.py` (in `make lint` and CI) holds the tree to the verdict lines below: a venue whose verdict is `neither` may not be named by its API hostnames in any tracked file, and a `derived` venue may not have a raw response committed.

Labels: [O] observed in a response or file on this host, [Q] quoted from the saved document, [I] the organisation's reading, not legal advice. Every saved file is under `tools/data/raw/pm-terms-2026-11-01/` (git-ignored, never committed), with SHA-256 in its `SHA256SUMS`; the hashes are repeated here so that a reader with the same documents can check them.

## One call per endpoint [O]

Each public market-data endpoint named in the programme's scope was called once, without a key, wallet or account, user agent `qune-research/0.1 (public research; one call per endpoint)`. The responses are kept locally for provenance only; nothing from them is used, published or kept in the tree.

| Venue, endpoint | UTC | HTTP | Bytes | SHA-256 of the body | Noted |
|---|---|---|---|---|---|
| Polymarket Gamma, `GET /markets?limit=1&active=true&closed=false` on `gamma-api.polymarket.com` | 2026-11-01 12:16:46 | 200 | 6,240 | `d4c6c37d…58fe232` | one market with `clobTokenIds`, `outcomePrices`; `cache-control: public, max-age=300` |
| Polymarket CLOB, `GET /book?token_id=<first token of that market>` on `clob.polymarket.com` | 2026-11-01 12:16:56 | 200 | 5,750 | `329af514…6be34e` | 20 bids, 143 asks, best price last in each array; book timestamp in ms |
| Kalshi trade API v2, `GET /markets?limit=1&status=open` on `api.elections.kalshi.com` | 2026-11-01 12:16:46 | 200 | 6,008 | `03e7d01e…eea9f50` | one multivariate combo market with zero quotes; `cache-control: public, max-age=15` |

Full hashes: Gamma `d4c6c37de24f7dc128a2f0b19f20879ffccadc1574f34e7d5202f61d658fe232`, CLOB `329af514b7df0513771e5447f985ac61bc5bb829ef2902b9f4f78b70c802334e`, Kalshi `03e7d01e7c522a5ae5f10eb7eceb3fe2b9805bb75916f5a3d48cfe0f9eea9f50`. The Kalshi call is the last one this repository makes (verdict below).

## Polymarket

**Documents read.** Terms of Use at `https://polymarket.com/tos`, "Effective as of August 11, 2026" [O], fetched 2026-11-01 12:15:54 UTC (61,571 characters); the developer documentation `docs.polymarket.com/getting-started/api.md`, `market-data/overview.md` and `resources/blockchain-data.md`, read 2026-11-01 12:16 UTC.

**What the terms say** [Q, Terms of Use]:
- Scope: "BY ACCESSING, INTERACTING WITH OR USING THE SITE, ANY FEATURE OR ANY OTHER INTERFACE (INCLUDING BY CONNECTING VIA AN API, LINKING YOUR WALLET, OR OTHERWISE CREATING AN IDENTIFIER ON THE SITE) … YOU … AGREE TO BE BOUND BY THE TERMS".
- Restricted jurisdictions: "If you are in a Restricted Jurisdiction (as defined below), you are only permitted to use the Content Features on the Site or any other Interface and may not use the Site or any other Interface for any other purpose and you may not access the Technology Features, including and in particular the Platform." The Content Features are "news and information about global current events".
- Prohibited conduct includes: "Use any data mining tools, robots, crawlers, or similar data gathering and extraction tools to scrape or otherwise remove data from the Site, any other Interface, or Features;" and "Use any manual process to monitor or copy any of the material on the Site, any other Interface, or Features or for any other unauthorized purpose without our prior written consent;".
- The data clause: "Access or use any data, content, or information contained on our Site, any Interface or Features directly or through an API, or any other means, including on-chain, whether in raw, derived, aggregated, or anonymized form (the “Data”) if you are (i) a non-retail, professional entity that engages in capital markets activities (e.g., brokerage, market making, proprietary trading, index calculation, or ETF issuance), including but not limited to broker-dealers, futures commission merchants, registered investment advisors, hedge funds, investment managers, proprietary trading firms, commodity pool operators, financial technology companies, banks, clearing houses, and exchanges or an affiliate of any such entity (each, a “Capital Market Client”), or (ii) a market data distributor, in each case unless otherwise agreed to in writing by us;" and "Sell, resell, sublicense, redistribute, or otherwise commercially exploit the Data to any Capital Market Client or market data distributor, unless otherwise agreed to in writing by us".
- Licence: "the Company hereby grants you a personal, limited, revocable, non-exclusive, non-sublicensable, non-transferable license to use, copy, and distribute in connection with such use the Site, any other Interface, and Features."

**What the documentation says** [Q]: "Public market data is available without credentials." (`getting-started/api.md`, with a `curl` example against the Gamma `/markets` endpoint); the documented rate limits are at `docs.polymarket.com/quickstart/introduction/rate-limits`. The "Data Resources" page lists third-party analytics platforms and community dashboards built on Polymarket data and calls itself "a public good for Polymarket builders, researches, and analysts alike".

**Reading** [I]: the Terms give no express licence to republish the venue's data; the scraping and copying clauses are written against the Site, and the documentation separately offers the public endpoints with rate limits for programmatic reads. The data clause restricts who may access the Data (Capital Market Clients and market data distributors need written agreement) and forbids resale or redistribution to those entities. This repository is a non-commercial research record with paper positions only, no wallet and no account; it is not a brokerage, market maker, fund, index calculator or data distributor. The reading that follows is the same as the one the private desk reached on 2026-11-01 00:05 UTC from the same document, now written where the public tree can be held to it.

verdict: polymarket = derived

Conditions attached to that verdict, all of them enforced or recorded in the tree:
1. No raw response is committed: no market list, order book, price history or trade file from the venue. Raw fetches stay in git-ignored `data/raw/` folders, hashed in a manifest, like the FRED fetches of Studies 001–008. `check_data_terms.py` fails on a tracked data file that carries the raw field names.
2. What is published is computed by the desk from those fetches: counts, calibration tables by probability bucket, Brier and log-loss scores, spread and depth summaries, charts drawn from them. Each published table names Polymarket as the source and the fetch dates.
3. Reads stay inside the documented rate limits, read-only, with no wallet, order, account or identifier; nothing is redistributed to anyone, and nothing is sold.
4. If the organisation ever became a Capital Market Client in the Terms' sense (a real-money proprietary trading operation, for example), access to the Data itself would need the venue's written agreement. That is one more reason real-money trading is the owner's decision after a legal check, not the desk's.
5. The Terms can change without notice ("Any modified Terms will become effective upon posting"); the effective date read here is 2026-08-11. The verdict is re-read, and this file dated again, before each new study's pre-registration.

## Kalshi

**Documents read.** The API documentation at `docs.kalshi.com/welcome.md` (read 2026-11-01 12:16 UTC) says: "By continuing to use or access Kalshi's API, you are agreeing to be bound to our Developer Agreement", linking `https://kalshi.com/developer-agreement`. That URL, and `https://kalshi.com/terms`, answered HTTP 429 ("Vercel Security Checkpoint") to a plain fetch on 2026-11-01 [O]; the Wayback Machine's copies of the agreement page (captures 2022-09-11, 2025-12-02, 2026-02-14) are client-side application shells with no text [O]. The venue's own documents are in its public document store, `kalshi-public-docs.s3.amazonaws.com`, which the agreement page preconnects to [O]; the bucket lists publicly (20,999 keys on 2026-11-01 12:18 UTC) and holds:

| File | Last-Modified (S3) [O] | SHA-256 [O] |
|---|---|---|
| `Kalshi-Developer-Agreement.pdf` (title "v1.1 Kalshi Developer Agreement") | 2023-11-09 22:19:38 GMT | `9d3e33685c0f0a88d23895685107975b0745283aac96f8bf7d202f5ae4dc1fa6` |
| `kalshi-data-terms-of-service.pdf` (title "KALSHI DATA TERMS OF USE") | 2024-09-11 16:17:13 GMT | `d19a0f94ffd65aa51eccb80cc8c9a06fb842478c5bf4cbd5a31ec51dd0a3966f` |
| `kalshiEX-data-terms-of-service.pdf` (same text with `elections.kalshi.com` in place of `kalshi.com` [O, diff]) | 2024-09-11 16:17:12 GMT | `f736f837d107cbf1cbd3a10d3337bbe2c34980bf0ffdd57f69edaebbfcba038b` |

Whether the page at `kalshi.com/developer-agreement` renders exactly the v1.1 PDF could not be verified through the checkpoint [O]; it is the document the venue stores under that name, and the docs' link is current. No newer version was found in the bucket.

**What the Developer Agreement says** [Q, v1.1]:
- "This Developer Agreement (“Agreement”) constitutes a binding agreement between KalshiEx LLC (“Kalshi” or “Exchange”) and any user of Kalshi’s application programming interface (“API”)." "Accessing or using Kalshi’s API shall be considered a binding acceptance of this Agreement."
- "3. Prohibitions. Use of Kalshi APIs is expressly limited to facilitating a members own trading on the Exchange; all other usages are disallowed and may result in account suspension. The following are all explicitly prohibited: 3.1. Collecting, caching, aggregating, or storing data or content accessed via the API except for purposes of facilitating your own trading on Kalshi. You may not share such data or content with third parties in any manner without prior written authorization from Kalshi."
- "3.5. Accessing the API for purposes of monitoring the availability, performance, or functionality of any of Kalshi’s services or for any other benchmarking or competitive purposes."
- "4.1.1. You must be a Member of Kalshi’s Exchange and comply with Kalsh’s [sic] Rulebook."
- "6.4. Public Statements. You must obtain prior written approval from Kalshi prior to releasing any statements, written media releases, public announcements and public disclosures, including promotional or marketing materials, relating to Kalshi, the Kalshi Marks, Kalshi Services, Kalshi API, or this Agreement."

**What the Data Terms of Use say** [Q]:
- "By accessing the Website, you acknowledge and agree that you are requesting access to the Kalshi Data made available on the Website. The content on the Website includes, without limitation: volume, bid-ask prices, opening and closing range prices, high-low prices, settlement prices, indexes, open interest and related information, market descriptions, materials, and other content on the Website (“Kalshi Data”)."
- "I. PERMITTED USES. You are only permitted to access and use the Kalshi Data in the form in which it is presented on the Website. … You may access content only for your personal use for non-commercial purposes. Non-commercial use does not include the use of Kalshi Data without prior written consent from Kalshi in connection with: (1) the development of any software program, including, but not limited to, training a machine learning or artificial intelligence system; or (2) providing archived or cached data sets containing Kalshi Data to another person or entity."
- "II. PROHIBITED USES. … you are strictly prohibited from selling, licensing, renting, modifying, changing, manipulating, altering, printing, collecting, copying, reproducing, downloading (other than to view only where a link is provided), uploading, transmitting, disclosing, distributing, disseminating, publicly displaying, publishing, editing, adapting, creating derivative works, electronically extracting or scrubbing, scraping, compiling (including, without limitation, through framing or systematic retrieval to create collections, compilations, databases or directories) or conducting ‘text and data mining’ (as those terms are defined in EU Directive 2019/790) in relation to any Kalshi Data".
- "use of any Kalshi Data (including associated metadata) in any manner for any machine learning and/or artificial intelligence, including without limitation for the purposes of training, coding, or development of artificial intelligence technologies, tools, or solutions or machine learning language models, or otherwise for the purposes of using or in connection with the use of such technologies, tools, or models to generate any information, material, data, derived works, content, or output is expressly prohibited."

**Reading** [I]: the API may be used only by a Member for that member's own trading; collecting, storing or aggregating API data for anything else, and sharing it with anyone, is prohibited without written authorisation; public statements about the API need written approval. The website data may be used only personally and non-commercially, in the form presented, with publishing, derivative works, compiled databases and any use with an AI system expressly prohibited. This repository's author is an AI model, the programme holds no Kalshi membership and will open none (no sign-ups is a standing rule), and its purpose is publication. None of the three routes (API, website, a derived aggregate of either) is open.

verdict: kalshi = neither

Consequences, effective from this commit:
1. No Kalshi endpoint is called from this repository again. The one probe call above is the last; its response is kept locally for provenance only and is not used.
2. Study 013 is designed on Polymarket data alone. FOCUS question 2 (cross-venue divergence) is parked, not closed: it needs a second venue whose terms allow the work. Manifold and PredictIt (reference venues in the scope) have not been read; they get the same treatment before any use.
3. Written authorisation from Kalshi would change the verdict. Asking for it is contact with an outside party, which is the owner's decision, not the desk's; it is in the owner's question batch with the recommendation to proceed on Polymarket alone for now.
4. `check_data_terms.py` fails CI on any tracked file that names a Kalshi API hostname.

## How the documents were found, and the rule it leaves

The venue's terms page had been tried on 2026-11-01 00:05–05:08 UTC (the desk's first data task): every `kalshi.com` path answered 429, the Wayback copies were empty shells, the CFTC filing index had no terms text. The verdict stood at "neither until read" for twelve hours while the question of whether the venue could be used at all stayed open. What found the documents in fifteen minutes was reading the sentence on the API documentation's own front page, which names the binding agreement, and then looking where that page's HTML points (a public document store). Rule, from this date: when a venue's terms page blocks a plain fetch, read the agreement its API documentation binds users to, and look in the venue's own public document store, before any further call; "not readable" is a blocker to record, never a verdict to work under. The data-terms line in a study's question gate (`tools/check_question_gate.py`) cites this file and its date.
