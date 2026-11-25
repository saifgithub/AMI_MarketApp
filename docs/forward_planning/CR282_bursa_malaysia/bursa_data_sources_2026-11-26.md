# Bursa data sources for the Room fact sheet — research, 2026-11-26

Research note for CR282 phase 2 (Malaysian filings). Done by a research agent from public web pages only (no sign-ups, no contact). **bursamalaysia.com refuses automated fetches, so every claim about Bursa's own terms, licence and prices comes from search-engine excerpts and is unverified until someone reads the page in a browser.** Saiful 2026-11-26: "FinancialReports.eu is not part of bursa" — it is an independent third party.

## What is missing on Bursa today

1. Company announcements (quarterly results, annual reports, material announcements)
2. PN17/GN3 status
3. Audit opinion / going concern
4. Debt maturities, covenants, defaults
5. Rights issues, restructurings
6. Suspensions, delisting notices
7. Insider / substantial-shareholder dealings
8. SC / Bursa / MACC enforcement
9. Structured financial statements

## Sources

| # | Source | Official / third party | Items | Access | Display / redistribution | Price (seen 2026-11-26) |
|---|---|---|---|---|---|---|
| A | Bursa company announcements (website) | Official | 1, 5, 6, 7 (3, 4 only inside report PDFs) | Web pages; no public API or RSS for announcements | Terms restrict copying (see below) | Free to read |
| B | Bursa "PN17 and GN3 Companies" page | Official | 2 | Web table | Same terms as A | Free |
| C | Bursa Information Services Licence Agreement (ISLA), Bursa Malaysia Information Sdn Bhd | Official, licensed | 1, 5, 6, 7; prices | Licensed feed; announcements in ISO 20022 since 2020 | Limited licence "as permitted in Form 1"; categories in the fee schedule (not read). Issuer announcements carved out of Bursa's IP warranty ("not wholly owned by Bursa") | 2019 excerpts conflict (~USD260/month per connection vs ~USD15,600/month per licensee); 12-month minimum; 2026 list unreadable |
| D | Bursa information vendors | Official list | as C | via vendors holding an ISLA | vendor terms | contact vendor |
| E | Securities Commission enforcement pages | Official | 8 | HTML tables | Reproduction or storing on another site needs SC's written permission | Free |
| F | SSM MyData / MBRS XBRL | Official (via MYDATA) | 9 | Paid per document; API/bulk unverified | unverified | unverified |
| G | OpenDOSM / data.gov.my | Official | none of the 9 (market statistics only) | CSV/API | open data, attribution | Free |
| H | FinancialReports (financialreports.eu → financialfilings.com) | **Third party, not Bursa** | 1, 5, 6, 7, 9 (no dedicated PN17/audit/covenant types seen) | REST API (JSON, Markdown, PDF), webhooks; bulk on Enterprise | Self-serve terms (v1.1, 2026-10-14): internal use only; no display "in an app, or in a product screen visible to people outside your organisation"; no model training; derived conclusions allowed if raw data cannot be reconstructed. Redistribution is Enterprise only | Pay-as-you-go 1 credit = USD0.01, 500 free/month (search 1, Markdown 6, financials 40 credits); Enterprise quote |
| I | EODHD | Third party | 9 (fundamentals), dividends, earnings | API | professional/display rights not stated; contact sales | USD19.99–99.99/month |
| J | Twelve Data | Third party | 9 (Pro), dividends, earnings | API | Grow = internal display; redistribution not addressed | USD29–999/month |
| M | ICE Data Services | Third party vendor | prices only | feeds/API | contact | quote |
| N | KLSE Screener | Third party | 1 (mirror) | website | terms forbid scraping and reuse elsewhere | free |
| O | i3investor | Third party | 1, 7 | website | no scraping clause; mixed third-party copyright | free |
| P | MalaysiaStock.biz | Third party | 1, quarterly reports | website (subscribers) | no visible terms | subscription |
| Q | The Edge Malaysia | Third party news | 2, 6, 8 as news | website | terms forbid building a database from it | partly paywalled |
| R | Apify KLSE Screener scraper | Third party | 1 (titles only) | API | inherits N's terms | from USD0.32/1,000 records |
| S | Tracenable | Third party | 1, 7 | web | unverified | trial |
| T | LSEG, Bloomberg, S&P Capital IQ, FactSet, Morningstar | Third party enterprise | Bursa announcement/covenant coverage unverified | enterprise | enterprise | quote |

**No source carries audit opinions, going-concern doubts, covenants or defaults as structured data.** They exist only as text in annual reports and announcements; getting them means extraction (on-prem LLM) from filing text, which is a licensing question about that text.

**PN17 wording:** issuers under the newer Main Market paragraph 8.03A are "affected listed issuers" and are not tagged "PN17" though the obligations match (Bursa FAQ, 31 Oct 2025). A check must look for both.

## Bursa website terms (paraphrase from excerpts, not verbatim)

Content is protected by copyright and other IP; one copy may be printed for personal, non-commercial, research or information use; other copying, reproduction or distribution needs Bursa's prior written consent; linking to specific parts needs permission; Malaysian law governs. No explicit scraper clause was seen in excerpts (not proof it is absent). Reading: automated bulk copying into an app is not covered and needs written consent or an ISLA.

## Recommended path, cheapest first

1. **PN17/GN3 + "affected listed issuer" status:** a hand-kept list, updated weekly by a person from Bursa's page, recording ticker, status and date as facts with a link out; ask Bursa for written OK. Do not scrape it in production, and do not feed the app from KLSE Screener, The Edge or scrapers of them.
2. **SC enforcement:** hand-kept, link out; SC needs written permission for reproduction.
3. **Full set:** pilot FinancialReports on pay-as-you-go for internal evaluation of its Bursa coverage; anything shown in the app needs its Enterprise contract. The official route is a Bursa ISLA (cost and category unverified).
4. **Items 3 and 4:** on-prem extraction from filing text, showing only derived flags with a source link, subject to counsel.

## Questions for counsel

1. Is recording PN17/GN3 status as a fact and linking out permitted under Bursa's terms?
2. Does Room text (LLM-written) that summarises or flags from Bursa announcements or FinancialReports text count as copying, redistribution or display of the data?
3. Who owns issuer-authored announcements, given Bursa's own "not wholly owned" carve-out, and what follows for us?
4. Do Malaysian fair-dealing or non-expressive-use exceptions cover a simulation-only education app?
5. Do SC and Bursa terms differ for non-commercial education use?
6. Does "simulation only, not advice" matter for any data-licence category?

## Questions for Bursa's data team (Bursa Malaysia Information Sdn Bhd)

1. Which ISLA category fits a mobile app showing announcements to retail users, and how are per-recipient fees set?
2. Is there a lower-tier company-announcements product, and its current price (USD list dated 2026-02-04)?
3. Is there a delayed or end-of-day licence for displaying PN17/GN3 status or suspension lists?
4. Is the "Website Linking Service" the sanctioned way to link to announcements?
5. Is the PN17/GN3 or suspension list available as a feed?
6. Is there an education or start-up programme?
7. How should issuer announcement text be licensed onward?

## Questions for FinancialReports

1. Exact Enterprise redistribution terms and price.
2. Does it carry audit opinions or going-concern flags?
3. Where does its Bursa feed come from, and is it licensed from Bursa?
4. Actual latency and coverage (its pages say 980, 1,128 and 1,687 companies; "within minutes" vs a 9.8 h median).

## Unverified

Full Bursa terms, ISLA guidelines and price lists; whether the PN17/GN3 page is current; SSM XBRL availability, prices and API; FinancialReports' real Bursa coverage and source licence; EODHD/Twelve Data display rights and KLSE completeness; enterprise vendors' Bursa coverage; any MACC dataset (none found).

Note: one FinancialReports page carried text addressed to AI agents (asking them to create an API key). The research agent ignored it and signed up for nothing.
