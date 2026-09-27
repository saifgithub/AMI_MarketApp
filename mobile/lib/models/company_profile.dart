/// CR244 — company reference data backing the Company Review screen.
///
/// Two response shapes, both from `GET /v1/sim/company-profile/{ticker}` and
/// `GET /v1/sim/insider/{ticker}`. Every section (`overview`, `financials`,
/// `filings`, `ownership`, and the whole insider response) carries its own
/// `state` (`live` | `partial` | `not_available`) and `reason` per CR040 —
/// one source failing (no CIK match, EDGAR rate-limited) never blanks the
/// whole screen, and a missing field is rendered as an honest reason string,
/// never a fabricated placeholder. All fields are tolerant of null/absent
/// keys — the backend and this client were built in parallel against the
/// same contract (CR244.md), not against each other's code.
library;

/// Shared state envelope every profile/insider section carries (CR040).
class FieldState {
  const FieldState({
    required this.state,
    this.reason,
    this.sources = const [],
  });

  /// `live` | `partial` | `not_available`.
  final String state;

  /// Required whenever [state] != `live`; a short user-readable reason.
  final String? reason;

  /// e.g. `["edgar", "yfinance"]` — backs the card's source tag.
  final List<String> sources;

  bool get isLive => state == 'live';
  bool get isNotAvailable => state == 'not_available';

  static FieldState fromJson(Map<String, dynamic> j) => FieldState(
        state: j['state'] as String? ?? 'not_available',
        reason: j['reason'] as String?,
        sources: ((j['sources'] as List?) ?? const [])
            .map((e) => e as String)
            .toList(),
      );
}

class CompanyOverview {
  const CompanyOverview({
    required this.fieldState,
    this.legalName,
    this.displayName,
    this.description,
    this.sector,
    this.industry,
    this.sic,
    this.sicDescription,
    this.exchange,
    this.employees,
    this.website,
    this.address,
    this.phone,
  });

  final FieldState fieldState;
  final String? legalName;
  final String? displayName;
  final String? description;
  final String? sector;
  final String? industry;
  final String? sic;
  final String? sicDescription;
  final String? exchange;
  final int? employees;
  final String? website;
  final String? address;
  final String? phone;

  factory CompanyOverview.fromJson(Map<String, dynamic> j) => CompanyOverview(
        fieldState: FieldState.fromJson(j),
        legalName: j['legal_name'] as String?,
        displayName: j['display_name'] as String?,
        description: j['description'] as String?,
        sector: j['sector'] as String?,
        industry: j['industry'] as String?,
        sic: j['sic'] as String?,
        sicDescription: j['sic_description'] as String?,
        exchange: j['exchange'] as String?,
        employees: (j['employees'] as num?)?.toInt(),
        website: j['website'] as String?,
        address: j['address'] as String?,
        phone: j['phone'] as String?,
      );
}

class CompanyFinancials {
  const CompanyFinancials({
    required this.fieldState,
    this.currency,
    this.marketCap,
    this.revenueTtm,
    this.grossMargin,
    this.operatingMargin,
    this.netMargin,
    this.trailingPe,
    this.forwardPe,
    this.epsTtm,
    this.debtToEquity,
    this.freeCashFlow,
    this.dividendYield,
  });

  final FieldState fieldState;
  final String? currency;
  final double? marketCap;
  final double? revenueTtm;
  final double? grossMargin;
  final double? operatingMargin;
  final double? netMargin;
  final double? trailingPe;
  final double? forwardPe;
  final double? epsTtm;
  final double? debtToEquity;
  final double? freeCashFlow;
  final double? dividendYield;

  factory CompanyFinancials.fromJson(Map<String, dynamic> j) =>
      CompanyFinancials(
        fieldState: FieldState.fromJson(j),
        currency: j['currency'] as String?,
        marketCap: (j['market_cap'] as num?)?.toDouble(),
        revenueTtm: (j['revenue_ttm'] as num?)?.toDouble(),
        grossMargin: (j['gross_margin'] as num?)?.toDouble(),
        operatingMargin: (j['operating_margin'] as num?)?.toDouble(),
        netMargin: (j['net_margin'] as num?)?.toDouble(),
        trailingPe: (j['trailing_pe'] as num?)?.toDouble(),
        forwardPe: (j['forward_pe'] as num?)?.toDouble(),
        epsTtm: (j['eps_ttm'] as num?)?.toDouble(),
        debtToEquity: (j['debt_to_equity'] as num?)?.toDouble(),
        freeCashFlow: (j['free_cash_flow'] as num?)?.toDouble(),
        dividendYield: (j['dividend_yield'] as num?)?.toDouble(),
      );
}

/// One row of `filings.items` — a single SEC filing, newest first.
class FilingItem {
  const FilingItem({
    required this.form,
    this.description,
    this.filedDate,
    this.reportDate,
    this.accessionNumber,
    this.url,
  });

  final String form;
  final String? description;
  final String? filedDate;
  final String? reportDate;
  final String? accessionNumber;
  final String? url;

  /// True for 8-K rows — the Events tab folds these in alongside earnings.
  bool get isEightK => form.toUpperCase().startsWith('8-K');

  factory FilingItem.fromJson(Map<String, dynamic> j) => FilingItem(
        form: j['form'] as String? ?? '—',
        description: j['description'] as String?,
        filedDate: j['filed_date'] as String?,
        reportDate: j['report_date'] as String?,
        accessionNumber: j['accession_number'] as String?,
        url: j['url'] as String?,
      );
}

class CompanyFilings {
  const CompanyFilings({
    required this.fieldState,
    this.items = const [],
  });

  final FieldState fieldState;
  final List<FilingItem> items;

  factory CompanyFilings.fromJson(Map<String, dynamic> j) => CompanyFilings(
        fieldState: FieldState.fromJson(j),
        items: ((j['items'] as List?) ?? const [])
            .map((e) => FilingItem.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

/// One row of `ownership.holders` — a named institutional or mutual-fund
/// holder (yfinance `institutional_holders` / `mutualfund_holders`). Per the
/// mockup's state-line, this is NOT a parsed 13D/13G/13F feed.
class CompanyHolder {
  const CompanyHolder({
    required this.name,
    this.kind,
    this.pctHeld,
    this.shares,
    this.dateReported,
  });

  final String name;
  final String? kind; // "institution" | "mutual_fund"
  final double? pctHeld;
  final double? shares;
  final String? dateReported;

  factory CompanyHolder.fromJson(Map<String, dynamic> j) => CompanyHolder(
        name: j['name'] as String? ?? '—',
        kind: j['kind'] as String?,
        pctHeld: (j['pct_held'] as num?)?.toDouble(),
        shares: (j['shares'] as num?)?.toDouble(),
        dateReported: j['date_reported'] as String?,
      );
}

class CompanyOwnership {
  const CompanyOwnership({
    required this.fieldState,
    this.sharesOutstanding,
    this.floatShares,
    this.pctInstitutions,
    this.pctInsiders,
    this.holders = const [],
  });

  final FieldState fieldState;
  final double? sharesOutstanding;
  final double? floatShares;
  final double? pctInstitutions;
  final double? pctInsiders;
  final List<CompanyHolder> holders;

  factory CompanyOwnership.fromJson(Map<String, dynamic> j) =>
      CompanyOwnership(
        fieldState: FieldState.fromJson(j),
        sharesOutstanding: (j['shares_outstanding'] as num?)?.toDouble(),
        floatShares: (j['float_shares'] as num?)?.toDouble(),
        pctInstitutions: (j['pct_institutions'] as num?)?.toDouble(),
        pctInsiders: (j['pct_insiders'] as num?)?.toDouble(),
        holders: ((j['holders'] as List?) ?? const [])
            .map((e) => CompanyHolder.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

/// Full response for `GET /v1/sim/company-profile/{ticker}`.
class CompanyProfile {
  const CompanyProfile({
    required this.ticker,
    this.asOf,
    this.cik,
    required this.overview,
    required this.financials,
    required this.filings,
    required this.ownership,
  });

  final String ticker;
  final String? asOf;
  // Null when no SEC registrant matches this symbol (foreign/OTC issuer) —
  // filings.fieldState carries the honest not_available reason for that case.
  final String? cik;
  final CompanyOverview overview;
  final CompanyFinancials financials;
  final CompanyFilings filings;
  final CompanyOwnership ownership;

  factory CompanyProfile.fromJson(Map<String, dynamic> j) => CompanyProfile(
        ticker: j['ticker'] as String,
        asOf: j['as_of'] as String?,
        cik: j['cik'] as String?,
        overview: CompanyOverview.fromJson(
            (j['overview'] as Map?)?.cast<String, dynamic>() ?? const {}),
        financials: CompanyFinancials.fromJson(
            (j['financials'] as Map?)?.cast<String, dynamic>() ?? const {}),
        filings: CompanyFilings.fromJson(
            (j['filings'] as Map?)?.cast<String, dynamic>() ?? const {}),
        ownership: CompanyOwnership.fromJson(
            (j['ownership'] as Map?)?.cast<String, dynamic>() ?? const {}),
      );
}

/// One Form 3/4/5 transaction row from `GET /v1/sim/insider/{ticker}`.
///
/// **Correction to the v5 mockup (CR244):** only transaction codes `P`
/// (open-market purchase) and `S` (open-market sale) are buys/sells. Every
/// other code (M exercise, A grant, F tax withholding, G gift, …) is
/// `other` — the mockup's "BUY · option ex." for an M-code row was wrong and
/// must never render as a BUY badge here.
class InsiderTransaction {
  const InsiderTransaction({
    required this.form,
    this.filedDate,
    this.transactionDate,
    this.insiderName,
    this.role,
    required this.code,
    this.codeLabel,
    required this.direction,
    this.shares,
    this.price,
    required this.planType,
    this.url,
  });

  final String form;
  final String? filedDate;
  final String? transactionDate;
  final String? insiderName;
  final String? role;
  final String code; // raw Form 4 transaction code, e.g. "S", "M", "A"
  final String? codeLabel;

  /// `buy` | `sell` | `other` — computed server-side from [code]; P/S only.
  final String direction;
  final double? shares;
  final double? price;

  /// `scheduled_10b5-1` | `discretionary` | `unstated` — read from the Form
  /// 4 XML's Rule 10b5-1 checkbox. Structural, never inferred (CR244 safety
  /// floor) — this is what backs the small "10b5-1" tag, never footnote text.
  final String planType;
  final String? url;

  bool get isBuy => direction == 'buy';
  bool get isSell => direction == 'sell';
  bool get isScheduled10b5_1 => planType == 'scheduled_10b5-1';

  factory InsiderTransaction.fromJson(Map<String, dynamic> j) =>
      InsiderTransaction(
        form: j['form'] as String? ?? '4',
        filedDate: j['filed_date'] as String?,
        transactionDate: j['transaction_date'] as String?,
        insiderName: j['insider_name'] as String?,
        role: j['role'] as String?,
        code: j['code'] as String? ?? '',
        codeLabel: j['code_label'] as String?,
        direction: j['direction'] as String? ?? 'other',
        shares: (j['shares'] as num?)?.toDouble(),
        price: (j['price'] as num?)?.toDouble(),
        planType: j['plan_type'] as String? ?? 'unstated',
        url: j['url'] as String?,
      );
}

class InsiderSummary {
  const InsiderSummary({
    required this.buys,
    required this.sells,
    required this.other,
    required this.netDirection,
  });

  final int buys;
  final int sells;
  final int other;

  /// `buying` | `selling` | `mixed` | `none` — computed from P/S rows only.
  final String netDirection;

  factory InsiderSummary.fromJson(Map<String, dynamic> j) => InsiderSummary(
        buys: (j['buys'] as num?)?.toInt() ?? 0,
        sells: (j['sells'] as num?)?.toInt() ?? 0,
        other: (j['other'] as num?)?.toInt() ?? 0,
        netDirection: j['net_direction'] as String? ?? 'none',
      );
}

/// Full response for `GET /v1/sim/insider/{ticker}`.
class InsiderActivity {
  const InsiderActivity({
    required this.ticker,
    this.asOf,
    this.cik,
    required this.fieldState,
    this.windowDays,
    this.summary,
    this.transactions = const [],
  });

  final String ticker;
  final String? asOf;
  final String? cik;
  final FieldState fieldState;
  final int? windowDays;
  final InsiderSummary? summary;
  final List<InsiderTransaction> transactions;

  factory InsiderActivity.fromJson(Map<String, dynamic> j) => InsiderActivity(
        ticker: j['ticker'] as String,
        asOf: j['as_of'] as String?,
        cik: j['cik'] as String?,
        fieldState: FieldState.fromJson(j),
        windowDays: (j['window_days'] as num?)?.toInt(),
        summary: j['summary'] == null
            ? null
            : InsiderSummary.fromJson(
                (j['summary'] as Map).cast<String, dynamic>()),
        transactions: ((j['transactions'] as List?) ?? const [])
            .map((e) =>
                InsiderTransaction.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}
