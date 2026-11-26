# Bursa Malaysia data — access reference for counsel

Prepared 2026-11-26 for AMI Trade (a simulation-only trading-education app; no real orders, no investment advice). It lists where Malaysian market and company data can be obtained, how each source is reached, and what each one offers. It is a factual reference; it does not interpret any terms of use.

Items marked *(from search excerpts)* were gathered from search-engine excerpts of the page, not from reading the page in full.

## 1. What AMI uses for Bursa today

| Data | Source | How it is reached |
|---|---|---|
| Prices, history, fundamentals, company profile | Yahoo Finance, via the open-source `yfinance` library | HTTP requests per ticker (`.KL` suffix); the Bursa universe is listed with Yahoo's screener over exchange `KLS` |
| Malaysian headline CPI | OpenDOSM / data.gov.my | API: `https://api.data.gov.my/data-catalogue/?id=cpi_headline` (CC BY 4.0) |
| Malaysian business headlines | Malay Mail, Money section RSS | `https://www.malaymail.com/feed/rss/money` (headline, link and date only) |
| Shariah-compliant securities list | Securities Commission Malaysia | Published list: `https://www.sc.com.my/development/icm/shariah-compliant-securities/` (document download via `https://www.sc.com.my/api/documentms/download.ashx?id=<document id>`) |

## 2. Bursa Malaysia — official sources

### 2.1 Company announcements

- **URL:** https://www.bursamalaysia.com/market_information/announcements/company_announcement
- **Content:** every listed issuer's announcements to the market: quarterly results, annual reports, material announcements, corporate actions (rights issues, restructurings), changes in directors' and substantial shareholders' interests, PN17/GN3 notifications, trading suspensions and delisting notices. Each announcement has a detail page; many carry PDF attachments (annual reports and financial statements are PDFs).
- **Search:** the announcements page is searchable. Fields expected on the search form *(from search excerpts, to be confirmed on the page)*: company name or stock code, announcement category, date range, keyword. Results list date, company, title and a link to the detail page.
- **Machine-readable delivery:** Bursa moved company announcements to the ISO 20022 standard in 2020 for machine-readable distribution through its licensed channels — https://www.finextra.com/pressarticle/81987/bursa-malaysia-implements-iso-20022-for-corporate-announcements

### 2.2 PN17 and GN3 companies

- **URL:** https://www.bursamalaysia.com/trade/trading_resources/listing_directory/pn17_and_gn3_companies
- **Content:** the current list of financially distressed ("affected") listed issuers — PN17 (Main Market, Practice Note 17) and GN3 (ACE Market, Guidance Note 3) — with a Main / ACE selector and groupings such as regularisation plan pending, plan under review, plan approved awaiting uplift *(from search excerpts)*. The page shows current status only.
- **Related rule change:** under Main Market Listing Requirements paragraph 8.03A, issuers are "affected listed issuers" and are not tagged "PN17", though the obligations correspond — Bursa FAQ (31 Oct 2025): https://www.bursamalaysia.com/sites/5d809dcf39fba22790cad230/assets/69047751e6414a573b2a6916/QA_MainChap8_AdditionalFAQs__31Oct2025_.pdf
- **History:** classifications and uplifts are each announced, so a history can be assembled from the company announcements (2.1) by category and date. PN17 dates from 2005 (Main Market); GN3 from 2009 (ACE Market).

### 2.3 RSS feeds

- **URL:** https://bursa.listedcompany.com/ (feed list)
- **Content:** media releases, newsroom, listing rules and IPO information. Company announcements are not among the feeds.

### 2.4 Licensed market data — Bursa Malaysia Information Sdn Bhd

- **Information Services Licence Agreement (ISLA):** https://www.bursamalaysia.com/market_information/market_data/information_services_license
- **ISLA Guidelines (v1.1, 29 Oct 2019):** https://www.bursamalaysia.com/sites/5d809dcf39fba22790cad230/assets/5dc0e9fd39fba246b7c87516/ISLA_Guidelines_V1.1_29102019.pdf
- **Content:** licensed feeds and connections for market data, including company announcements, prices, indices, bonds and derivatives. Licence categories (display, non-display, redistribution, internal) and fees are set out in Bursa's fee schedule and guidelines; USD and MYR price lists are published (USD list updated 2026-02-04). Minimum term 12 months *(from search excerpts)*.
- **Authorised information vendors:** https://www.bursamalaysia.com/market_information/market_data/information_vendors
- **Website Linking Service:** listed under Market Data on Bursa's site (page not read).

### 2.5 Website terms

- **Terms and conditions of use, disclaimer and linking policy:** https://www.bursamalaysia.com/term_conditions_of_use_disclaimer_and_linking_policy

## 3. Other official Malaysian sources

| Source | URL | Content | Access |
|---|---|---|---|
| Securities Commission — administrative actions (per year) | https://www.sc.com.my/regulation/enforcement/actions/administrative-actions/administrative-actions-in-2026 | Enforcement actions: nature of misconduct, parties, description, action, date; also compounded, criminal and civil case pages | HTML tables |
| Securities Commission — disclaimer | https://www.sc.com.my/about/disclaimer | Site terms | — |
| SSM (Companies Commission) — MyData | https://ssm.com.my/Pages/Buy_Corporate_Information/MyDATA.aspx | Company and business profiles, financial comparisons, certified copies; audited financial statements filed in XBRL through MBRS 2.0 (https://iriscarbon.com/mandates/ssm-mbrs) | Paid, per document |
| data.gov.my / OpenDOSM | https://data.gov.my/ | Government open data incl. Bursa market statistics (number of listed companies, market capitalisation, volumes) | Bulk CSV / API |

## 4. Third-party sources (not Bursa)

| Source | URL | Bursa content | Access | Price (seen 2026-11-26) |
|---|---|---|---|---|
| FinancialReports (financialreports.eu, served as financialfilings.com; FINANCIALREPORTS PTE. LTD.) | https://financialfilings.com/filings/countries/malaysia/ · pricing https://financialfilings.com/pricing/ · API terms https://financialfilings.com/api-terms/ | Bursa filings incl. interim/quarterly reports, regulatory filings, major shareholding notifications, directors' dealings; standardised financial statements; full text as Markdown and original PDF | REST API (JSON, Markdown, PDF), webhooks; bulk delivery (S3/Snowflake) on Enterprise | Pay-as-you-go 1 credit = USD0.01, 500 free credits/month (search 1, Markdown 6, financials 40 credits per call); Enterprise by quote |
| EODHD | https://eodhd.com/pricing · terms https://eodhd.com/financial-apis/terms-conditions | Fundamentals, dividends, splits, earnings calendar, news for `.KLSE` tickers | REST API | USD19.99–99.99/month |
| Twelve Data | https://twelvedata.com/pricing | Statements and insider transactions (Pro), dividends, splits, earnings for Bursa (MYX) | REST API | USD29–999/month |
| ICE Data Services — Bursa Malaysia catalogue | https://developer.ice.com/fixed-income-data-services/catalog/bursa-malaysia | Prices: equities, indices, options; real-time, delayed, end-of-day, historical; Level 2 | Feeds, API, files | By quote |
| Tracenable | https://tracenable.com/company/bursa-malaysia/disclosures | Disclosures monitor | Web | Trial |
| KLSE Screener | https://klsescreener.com/ · terms https://klsescreener.com/v2/pages/terms | Announcement mirror, prices, ratios | Web | Free |
| i3investor | https://klse.i3investor.com/ · terms https://klse.i3investor.com/web/general/tac | Announcements, filings aggregation | Web | Free |
| MalaysiaStock.biz | https://www.malaysiastock.biz/ | Bursa announcements page, quarterly reports | Web (subscribers) | Subscription |
| The Edge Malaysia | https://theedgemalaysia.com/ · terms https://theedgemalaysia.com/terms-of-use | News coverage of PN17/GN3, suspensions, enforcement | Web | Partly paywalled |
| LSEG (Refinitiv), Bloomberg, S&P Capital IQ, FactSet, Morningstar | e.g. https://www.lseg.com/en/data-analytics/financial-data/corporate-actions-data/listed-equity | Enterprise market and reference data; Bursa coverage of announcements not confirmed | Enterprise licence | By quote |

## 5. What AMI would like to obtain for Bursa stocks

1. Company announcements (quarterly results, annual reports, material announcements)
2. PN17/GN3 and "affected listed issuer" status, current and historical
3. Audit opinion, including any going-concern statement
4. Debt maturities, covenants and defaults
5. Rights issues and restructurings
6. Trading suspensions and delisting notices
7. Directors' and substantial shareholders' dealings
8. SC, Bursa and MACC enforcement actions
9. Structured financial statements

Planned first use (CR286): record each Bursa stock's PN17/GN3 status as facts (stock code, company name, status category, date first seen, date last seen, link to Bursa's page), refreshed weekly from the page in 2.2, and state it on the stock's fact sheet with an as-of date and a link to Bursa.
