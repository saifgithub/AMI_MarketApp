# Bursa Malaysia Authorised Information Vendors: equity data research (2026-11-26)

Method: public web search and public page fetches only. No sign-ups, no contact, no bursamalaysia.com page fetched (one search *returned* the Bursa vendor-list URL as a result; its text was used only via the search excerpt, marked *(excerpt)*). Anything marked *(excerpt)* came from a search result summary, not a page read. "Not found" means I looked and found nothing public, not that the vendor lacks it. Most vendors publish no price and no coverage detail for a single exchange; coverage lists are behind logins or sales contact.

Fetch failures (no evasion attempted): baha.com 403; bloomberg.com/professional 403; bpam.com.my 403; morningstar.com key-metrics page 403; insight.factset.com fundamentals page 404; factset.com and tq.net returned only a title / "Loading..."; activfinancial.com redirects to options-it.com (ACTIV is now part of Options Technology), whose home page said nothing about ACTIV data.

Legend: a = announcements; b = PN17/GN3/suspension/delisting status; c = corporate actions, director/substantial-shareholder dealings; d = structured financials; e = prices.

## 1. Table

| Vendor | Type | a | b | c | d | e | Delivery | Small-co / retail display | Price | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| ICE Data Services | Data reseller (largest confirmed Bursa equities source) | Not found | Not found | Not confirmed. Bursa catalog page text does not mention corporate actions (fetched). A search summary *(excerpt)* claimed corporate actions/reference data are bundled; not verified on the page. ICE sells a separate global corporate-actions product (80k issuers, 100+ countries, ISO 15022, hourly) *(excerpt)*; Malaysia coverage not stated | Not found | Real-time, delayed, EOD, historical; Level 2, MBO and MBP; history from Oct 2002 *(excerpt)* | ICE Connect (terminal), Consolidated Feed, Consolidated History, Data API, Data Files | Not stated. Catalog says users must log in to check coverage or contact ICE. Third-party IDs (CUSIP/ISIN) may need separate licences | Not published | https://developer.ice.com/fixed-income-data-services/catalog/bursa-malaysia ; https://www.ice.com/market-data/pricing-and-analytics/consolidated-feed/coverage-list ("Bursa Malaysia Equities" listed under Asia Pacific, no data level shown) ; https://developer.ice.com/fixed-income-data-services/catalog/ice-reference-data-corporate-actions *(excerpt)* |
| LSEG (Refinitiv Asia) | Data reseller (Bursa's own data-distribution platform builder, 2009) | Not confirmed. "Exchange News" product covers "official announcements, market notices and issuer disclosure updates" but page names no exchange and no Malaysia | Not found (suspensions/corporate actions not named for Exchange News) | Corporate actions product exists (143k companies, 100 nations, 200+ venues *(excerpt)*); Malaysia not named | Company fundamentals: 110k+ public firms, 150+ exchanges; Malaysia not named | Not confirmed for Bursa (LSEG has a "Real-Time Delayed Optimized" product; Bursa not named) *(excerpt)* | Workspace, Datastream, DataScope, APIs, SFTP/bulk (Machine Readable News). Their News API page says "individual users only; no redistribution or server side usage" *(excerpt)* | Enterprise. No public small-co or redistribution terms found | Not published ("Request details") | https://www.lseg.com/en/data-analytics/financial-data/news/exchange-news ; https://lseg.com/en/data-analytics/financial-data/company-data/fundamentals-data ; https://www.finextra.com/newsarticle/20850/thomson-reuters-wins-bursa-malaysia-market-data-deal (fetch returned 403; used as search excerpt only) *(excerpt)* ; https://developers.lseg.com/en/product/news/workspace_news *(excerpt)* |
| Bloomberg L.P. | Data reseller / terminal | Not found | Not found | Bloomberg Corporate Actions Data License exists (Malaysia not named) *(excerpt)* | Not found for Bursa | Not found | Terminal, Data License (not verified) | Not found; bloomberg.com returned 403 | Not found | https://www.waterstechnology.com/node/1930541 *(excerpt)* |
| FactSet | Data reseller | Not found | Not found | Not found | FactSet Fundamentals DataFeed exists; Malaysia not confirmed. A Xignite staging page lists Malaysia among Asia-Pacific countries for FactSet-sourced fundamentals *(excerpt, weak)* | Not found | Not found (FactSet pages blocked/empty) | Not found | Not found | https://insight.factset.com/resources/at-a-glance-factset-fundamental-datafeed *(excerpt)* ; https://cmsstaging.xignite.com/pages/version/61906bcf-8445-4d56-80e2-7e6637183eb3 *(excerpt)* |
| Morningstar Real-Time | Data reseller | Not found | Not found | Not found | Public morningstar.com shows Bursa stocks and ETFs, but that is its consumer site, not a licensing statement | Public site shows delayed Bursa quotes *(excerpt)*. No source says Morningstar sells real-time Bursa data. Morningstar claims real-time data on ~35M instruments and 260+ sources, with no exchange list *(excerpt)* | Data feeds / API components *(excerpt)* | Not found | Not found | https://www.morningstar.com/stocks/xkls/1818/quote *(excerpt)* ; https://www.morningstar.com/en-au/business/products/direct/data-feeds *(excerpt)* ; https://my.morningstar.com/my/news/156180/how-morningstar-asia-can-add-value-for-you-in-2017.aspx *(excerpt)* |
| SIX Financial Information | Data reseller (strong in reference data and corporate actions) | Not found | Not found | SIX Global Corporate Actions: 70+ event types incl. dividends, M&A, rights issues, IPOs; file, API (SIX Bulk API), display; ISO 15022/MT564. Page does not mention Malaysia, Bursa, restructurings, delistings or suspensions | Not found for Bursa | Not found for Bursa (SIX Global Market Data PDF unreadable) | Files, APIs, display | Page says it serves wealth/asset management and global financial institutions. No small-co terms | Not published | https://www.six-group.com/en/products-services/financial-information/market-reference-data/corporate-actions-data.html |
| ACTIV Financial (now part of Options Technology) | Data reseller / feed infrastructure | Not found | Not found | Not found | Not found | Bursa real-time covered: ACTIV added Bursa to its Asia feed, and set up a co-located point of presence at Bursa *(excerpt, old Waters/Finextra items; current coverage unconfirmed)*. activfinancial.com now redirects to options-it.com | Feed / normalised API *(excerpt)* | Not found. Targets trading firms and enterprises | Not found | https://www.waterstechnology.com/node/2283717 *(excerpt)* ; https://www.finextra.com/pressarticle/50840/activ-expand-market-coverage-in-asia *(excerpt)* ; https://financefeeds.com/options-expands-market-data-feeds-after-partnership-with-tools-for-brokers/ *(excerpt)* ; https://www.options-it.com/ |
| Colt Technology Services | Infrastructure / connectivity (PrizmNet private network) | Not offered (no mention) | Not offered | Not offered | Not offered | Equities (10-level depth) and Bursa sectoral indices, real time, delivered over Colt's network. This is Bursa's data pipe, not a licence to display it | Network PoPs, x-connects, last-mile circuits | Not stated. Customer still needs its own Bursa vendor/data agreement | Not stated | https://docs.colt.net/datasheets/capital-markets/regions/malaysia |
| DZH International | Broker-tech / terminal vendor with a real-time data business (Shanghai DZH subsidiary) | Not found | Not found | Not found | "Financial fundamental data" under DZH FinChina; China-focused, Bursa not stated | Site claims real-time data for Southeast Asian equity, futures, commodity traders. No page names Bursa feeds | Terminals and mobile apps (DZHI Trader, Advisor Trader, Advisor Xs, ODIN order routing, White-Label) | Sells to financial institutions, professionals; "White-Label business solutions" listed. No retail redistribution terms | Not found | https://www.dzhintl.com/ ; https://www.dzhintl.com/about-us.php |
| Excel Force MSC Bhd | Broker-tech (stockbroking trading systems). Bursa-listed (code 0065, EFORCE) | Not found | Not found | Not found | Not found | Not found. Site says it has "know-how in market data feed" and sells dealer/remisier, e-ordering, mobile trading, back-office systems. Bursa lists it with a "website ticker" service, but I found nothing on that on its site | Trading systems | Targets "stockbroking companies, investment and commercial banks" | Not found | https://www.excelforce.com.my |
| N2N Global Solutions (N2N Connect Bhd) | Broker-tech (trading/settlement platforms, Asia E-Broker, Information Terminal, exchange connectivity). The site carries a scam notice that its name is being misused | Not found. "Company Announcements" section is N2N's own | Not found | Not found | Not found | "Information Terminal" and Asia E-Broker give market data to broker clients; Bursa connectivity listed. No data product described | Platforms for brokers | Brokers/institutions | Not found | https://www.n2nconnect.com |
| Telequote (M) Sdn Bhd | Data reseller to retail/professionals (older products: WinQuote Windows app) | Not found | Not found | Not found | Not found | Real-time quotes via its own products (old company page) *(excerpt)*. Bursa lists it for equities and derivatives, no website ticker *(excerpt)* | Desktop app (WinQuote) *(excerpt)*; my.tq.net site loads, shows title only | Not found | Not found | https://my.tq.net ; http://www.telequote.com.my/ (not resolvable now) ; Bursa vendor-list URL appeared in search results *(excerpt)* |
| BAHA Tech Holding AG | Data reseller (Swiss) | Not found | Not found | Not found | Not found | Not found (site 403) | Not found | Not found | Not found | https://www.baha.com (403) |
| Fidessa (ION) | Broker-tech / trading front-end | Not researched (trading platform, not a data publisher) | | | | | | | | none |
| FIS Financial Systems (ex-SunGard) | Broker-tech / trading front-end | Not researched | | | | | | | | none |
| Bond Pricing Agency Malaysia | Out of scope: bond only (bpam.com.my returned 403) | | | | | | | | | |
| CenturyLink/Lumen, CQG, DTN, Options Information Technology | Out of scope: derivatives only | | | | | | | | | |

Notes on Options Information Technology: unrelated to Options Technology/ACTIV above. Vendor list gives it as derivatives only; no check made.

### Unlisted alternative found in passing (not a Bursa vendor)

| Source | What | Source URL |
|---|---|---|
| financialfilings.com (formerly financialreports.eu) | Claims "every annual, interim and ad-hoc report from 1,128 Malaysian listed companies", 2000 to 2026; categories include quarterly reports, annual reports, material announcements, prospectuses, circulars; REST API and webhooks; JSON/Markdown/PDF; "free for the web". Own figures conflict: median availability 9.8 h vs "within seconds/minutes"; 1,128 vs 1,687 vs ~980 companies. PN17/GN3 status not mentioned. Pricing not shown. Not an authorised Bursa information vendor, so its licence to redistribute Bursa-originated filings is unknown | https://financialfilings.com/api-solutions/countries/malaysia/ |

## 2. Ranked shortlist (announcements + PN17/suspension status for a retail app)

Honest caveat: no vendor publicly confirms PN17/GN3 status or announcements for Bursa. None of these is verified for the target use. The shortlist is about who is worth a question, not who is proven.

1. LSEG (Refinitiv Asia). Has an Exchange News product for "official announcements, market notices and issuer disclosure updates" plus a long record as Bursa's data-platform builder. But Malaysia is not named on the page, and their news API page says individual-use only, no redistribution.
2. ICE Data Services. Only vendor with a public, specific Bursa equities catalog page: real-time/delayed/EOD, API and file delivery, Level 2. Weak on announcements and PN17, but may have corporate actions via reference data.
3. SIX Financial Information. Strong corporate-actions product with file/API delivery, but Malaysia coverage is unconfirmed and it targets institutions.
4. Bloomberg. Large enterprise corporate-actions and regulatory content, likely to include Malaysian events, but nothing public confirms it and no small-company/redistribution route is visible.
5. FactSet. Fundamentals and corporate actions exist in general; nothing public on Bursa announcements or status; evidence is a single weak excerpt.

Not on the shortlist: Colt (network only), N2N/Excel Force/DZH/Telequote (broker-tech or terminal vendors, no public data-feed product for announcements), ACTIV/Options (prices only), Morningstar (no real-time Bursa evidence), BAHA (site blocked), Fidessa/FIS (trading front-ends).

Observation: the fields we are missing (announcements, PN17/GN3, suspensions, delisting notices) are exchange-issued disclosures. The vendors above are mostly price and reference-data resellers. Several may not sell announcement text at all, in which case this data may need to come from Bursa directly (their Bursa Connectivity Services is described as connecting "buy- and sell-sides, information vendors as well as third-party solution providers": https://www.thestar.com.my/business/business-news/2023/02/16/bursa-malaysia-launches-new-data-connectivity-service) rather than through a vendor.

## 3. Questions to ask each shortlisted vendor

All vendors:
1. Do you carry Bursa Malaysia issuer announcements (full text and PDF attachments, with category and timestamp)? Delay vs Bursa publication?
2. Do you carry Bursa's PN17/GN3 "affected listed issuer" classifications, trading suspensions, resumptions and delisting notices as a structured field or event, or only as free-text announcements?
3. Which Bursa corporate actions, and which director/substantial-shareholder dealings, are covered?
4. Do you carry quarterly financial statements for Bursa Main/ACE/LEAP in structured form? History depth?
5. Does your Bursa licence allow display in a mobile app to retail end users with no order routing (simulation/education)? Is redistribution licensed by you, or do we need our own Bursa agreement and vendor sign-off? Is there a non-display or delayed-display tier?
6. Minimum contract size and term for a start-up? Per-user vs per-app pricing? Delayed (15-20 min) and EOD price tiers vs real-time?
7. Delivery: API, streaming, files? Rate limits and SLAs?
8. Who pays the Bursa exchange fee (pass-through), and what are the retail-display reporting obligations?

LSEG additionally:
9. Is Bursa in Exchange News coverage? Is the "individual users only, no redistribution" restriction on the News API lifted under an enterprise or redistribution agreement?

ICE additionally:
10. Does the Bursa catalog entry include corporate actions or reference data (Bursa-specific) or only instrument names and codes? Does ICE's global corporate-actions feed cover Bursa?

SIX additionally:
11. Is Malaysia in the Global Corporate Actions coverage (rights issues, restructurings, delistings, suspensions)? Any real-time Bursa price source?

Bloomberg additionally:
12. Is there an enterprise data-license route (not the terminal) for a retail-facing app, and does it permit redistribution of Bursa-sourced content?

FactSet additionally:
13. Does FactSet Fundamentals DataFeed cover Bursa small caps (ACE/LEAP) and PN17 companies? Is there a retail display or white-label licence?
