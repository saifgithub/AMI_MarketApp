/// Company Review — CR244 Part 1, build slice 1.
///
/// Destination screen for the new "Review" action on the Floor omnibox and
/// the Ticker Detail chip row. Six horizontally-scrollable tabs (Overview,
/// Financials, Filings, Ownership, Insider, Events), each a succinct
/// source-tagged summary card with a "view full detail" expand — per
/// Saiful's "users are busy" requirement (CR244.md). Visual spec is the
/// approved mockup, `docs/forward_planning/CR244_.../mockup_company_review.html`.
///
/// **Degrade loudly (CR040).** Every section carries its own `state` (`live`
/// | `partial` | `not_available`) from the backend. This screen renders that
/// state directly — a `not_available`/`partial` section shows its `reason`
/// string in the card, never a blank card and never a fabricated number. The
/// whole-screen `companyProfileProvider` failing (network/5xx) is a
/// different, coarser failure and gets its own retry-able error state.
///
/// **Insider tab correction (CR244):** only Form 4 codes `P` (open-market
/// purchase) and `S` (open-market sale) are buy/sell. Every other code is
/// `other` and is never badged BUY/SELL — the v5 mockup's "BUY · option ex."
/// was wrong and does not appear here. `InsiderTransaction.direction` is the
/// single source of truth for the badge, computed server-side, never
/// re-derived from the code client-side.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/company_profile.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/state/company_review_providers.dart';
import 'package:ami_trade/state/ticker_history_provider.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

/// CR244 audit fix L6 — opens `uri` externally, surfacing a snackbar when
/// `launchUrl` fails (rather than the tap silently doing nothing). Shared by
/// every filing/Form-4 row so the failure mode is the same everywhere.
Future<void> _openLink(BuildContext context, String? url) async {
  if (url == null) return;
  final l = AppLocalizations.of(context);
  final uri = Uri.tryParse(url);
  var ok = false;
  if (uri != null) {
    try {
      ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      ok = false;
    }
  }
  if (!ok && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(l.companyReviewOpenLinkFailed)),
    );
  }
}

class CompanyReviewScreen extends ConsumerStatefulWidget {
  const CompanyReviewScreen({super.key, required this.ticker});

  final String ticker;

  @override
  ConsumerState<CompanyReviewScreen> createState() =>
      _CompanyReviewScreenState();
}

class _CompanyReviewScreenState extends ConsumerState<CompanyReviewScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 6, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final profileAsync =
        ref.watch(companyProfileProvider(widget.ticker));

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(
        backgroundColor: AmiColors.glassChrome,
        elevation: 0,
        iconTheme: const IconThemeData(color: AmiColors.hexCyan),
        title: Text(
          l.companyReviewTitle,
          style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan),
        ),
      ),
      body: SafeArea(
        child: profileAsync.when(
          data: (profile) => _Loaded(
            ticker: widget.ticker,
            profile: profile,
            tabController: _tabController,
          ),
          loading: () =>
              const Center(child: CircularProgressIndicator(color: AmiColors.hexCyan)),
          error: (e, _) => _WholeScreenError(
            message: friendlyError(e, action: 'load this company review'),
            onRetry: () =>
                ref.invalidate(companyProfileProvider(widget.ticker)),
          ),
        ),
      ),
    );
  }
}

class _WholeScreenError extends StatelessWidget {
  const _WholeScreenError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AmiSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, color: AmiColors.textLow, size: 40),
            const SizedBox(height: AmiSpacing.m),
            Text(l.companyReviewLoadFailedTitle,
                style: AmiTypography.h4, textAlign: TextAlign.center),
            const SizedBox(height: AmiSpacing.xs),
            Text(message,
                textAlign: TextAlign.center,
                style: AmiTypography.body.copyWith(color: AmiColors.textLow)),
            const SizedBox(height: AmiSpacing.m),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AmiColors.hexCyan,
                foregroundColor: AmiColors.slate900,
              ),
              onPressed: onRetry,
              child: Text(l.companyReviewRetry),
            ),
          ],
        ),
      ),
    );
  }
}

class _Loaded extends ConsumerWidget {
  const _Loaded({
    required this.ticker,
    required this.profile,
    required this.tabController,
  });

  final String ticker;
  final CompanyProfile profile;
  final TabController tabController;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
              AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, 0),
          child: _Header(ticker: ticker, profile: profile),
        ),
        TabBar(
          controller: tabController,
          isScrollable: true,
          labelColor: AmiColors.textHigh,
          unselectedLabelColor: AmiColors.textLow,
          indicatorColor: AmiColors.hexBlue,
          labelStyle: AmiTypography.labelMono.copyWith(fontSize: 11),
          unselectedLabelStyle:
              AmiTypography.labelMono.copyWith(fontSize: 11),
          tabs: [
            Tab(text: l.companyReviewTabOverview),
            Tab(text: l.companyReviewTabFinancials),
            Tab(text: l.companyReviewTabFilings),
            Tab(text: l.companyReviewTabOwnership),
            Tab(text: l.companyReviewTabInsider),
            Tab(text: l.companyReviewTabEvents),
          ],
        ),
        Expanded(
          child: TabBarView(
            controller: tabController,
            children: [
              _OverviewTab(
                  ticker: ticker,
                  profile: profile,
                  tabController: tabController),
              _FinancialsTab(financials: profile.financials),
              _FilingsTab(filings: profile.filings),
              _OwnershipTab(ownership: profile.ownership),
              _InsiderTab(ticker: ticker),
              _EventsTab(ticker: ticker, filings: profile.filings),
            ],
          ),
        ),
      ],
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.ticker, required this.profile});

  final String ticker;
  final CompanyProfile profile;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final name = profile.overview.displayName ??
        profile.overview.legalName ??
        ticker;
    final exchange = profile.overview.exchange;
    final asOf = _fmtAsOf(profile.asOf);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(ticker,
                  style: AmiTypography.labelMono.copyWith(fontSize: 18)),
              const SizedBox(height: 2),
              Text(
                exchange == null ? name : '$name · $exchange',
                style: AmiTypography.caption.copyWith(color: AmiColors.textMed),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
        if (asOf != null)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: AmiColors.slate800,
              border: Border.all(color: AmiColors.slate700),
              borderRadius: BorderRadius.circular(AmiRadii.sm),
            ),
            child: Text(
              l.companyReviewAsOf(asOf),
              style: AmiTypography.caption.copyWith(
                  color: AmiColors.textLow, fontFamily: AmiTypography.plexMono),
            ),
          ),
      ],
    );
  }

  static String? _fmtAsOf(String? iso) {
    if (iso == null) return null;
    final dt = DateTime.tryParse(iso);
    if (dt == null) return null;
    return DateFormat('MM/dd').format(dt);
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Shared card chrome
// ─────────────────────────────────────────────────────────────────────────

class _SourceTag extends StatelessWidget {
  const _SourceTag({required this.label, required this.isEdgar});

  final String label;
  final bool isEdgar;

  @override
  Widget build(BuildContext context) {
    final color = isEdgar ? AmiColors.hexBlue : AmiColors.hexCyan;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(5),
      ),
      child: Text(
        label,
        style: AmiTypography.caption.copyWith(
          color: color,
          fontFamily: AmiTypography.plexMono,
          fontWeight: FontWeight.bold,
          fontSize: 9,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}

/// A source tag derived from a section's `sources` list.
///
/// M4 audit fix — `fallbackLabel` now applies ONLY when `sources` is empty.
/// Previously it always won over a real, non-empty `sources` list, so a
/// live EDGAR + yfinance section still showed whatever caller-supplied
/// fallback string (label AND colour) regardless of what actually backed
/// it. An empty list still falls back to EDGAR-styling — EDGAR is this
/// screen's more common source — but only then.
Widget sourceTagFor(List<String> sources,
    {String? fallbackLabel, required AppLocalizations l}) {
  if (sources.isEmpty) {
    return _SourceTag(label: fallbackLabel ?? l.companyReviewSourceEdgar, isEdgar: true);
  }
  final hasEdgar = sources.contains('edgar');
  final hasYfinance = sources.contains('yfinance');
  final label = hasEdgar && hasYfinance
      ? l.companyReviewSourceEdgarYfinance
      : hasYfinance
          ? l.companyReviewSourceYfinance
          : l.companyReviewSourceEdgar;
  return _SourceTag(label: label, isEdgar: !hasYfinance || hasEdgar);
}

class _Card extends StatelessWidget {
  const _Card({
    required this.title,
    required this.sourceTag,
    required this.child,
    this.onExpand,
    this.expandLabel,
  });

  final String title;
  final Widget sourceTag;
  final Widget child;
  final VoidCallback? onExpand;
  final String? expandLabel;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: AmiSpacing.sm),
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        border: Border.all(color: AmiColors.slate700),
        borderRadius: BorderRadius.circular(AmiRadii.card),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(title,
                    style: AmiTypography.body.copyWith(
                        color: AmiColors.textHigh, fontWeight: FontWeight.bold)),
              ),
              const SizedBox(width: AmiSpacing.s),
              sourceTag,
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          child,
          if (onExpand != null && expandLabel != null) ...[
            const SizedBox(height: AmiSpacing.s),
            InkWell(
              onTap: onExpand,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(expandLabel!,
                      style: AmiTypography.body.copyWith(
                          color: AmiColors.hexBlue,
                          fontWeight: FontWeight.bold,
                          fontSize: 12)),
                  const SizedBox(width: 4),
                  const Icon(Icons.arrow_forward,
                      color: AmiColors.hexBlue, size: 14),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// CR040 — the honest not_available/partial card. Rendered instead of the
/// normal card body whenever a section's state != live and there's no live
/// data at all to show alongside the reason. A `partial` section with SOME
/// live fields renders those fields plus this note appended, handled inline
/// per-tab rather than here.
class _StateNote extends StatelessWidget {
  const _StateNote({required this.reason});

  final String? reason;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
      margin: const EdgeInsets.only(top: AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        border: Border.all(color: AmiColors.slate700, style: BorderStyle.solid),
        borderRadius: BorderRadius.circular(AmiRadii.card),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.warning_amber_rounded,
              color: AmiColors.textLow, size: 14),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              reason ?? l.companyReviewNotAvailable,
              style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
            ),
          ),
        ],
      ),
    );
  }
}

class _KvGrid extends StatelessWidget {
  const _KvGrid({required this.entries});

  final List<(String, String)> entries;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: AmiSpacing.m,
      runSpacing: AmiSpacing.s,
      children: [
        for (final e in entries)
          SizedBox(
            width: 140,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(e.$1,
                    style: AmiTypography.caption.copyWith(
                        color: AmiColors.textLow, fontSize: 9.5)),
                const SizedBox(height: 2),
                Text(e.$2,
                    style: AmiTypography.dataMd.copyWith(fontSize: 12.5)),
              ],
            ),
          ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Overview tab
// ─────────────────────────────────────────────────────────────────────────

class _OverviewTab extends StatelessWidget {
  const _OverviewTab({
    required this.ticker,
    required this.profile,
    required this.tabController,
  });

  final String ticker;
  final CompanyProfile profile;

  /// B1 audit fix — `DefaultTabController.maybeOf(context)` is always null
  /// here (this screen uses an explicit [TabController], not a
  /// `DefaultTabController`), so "See all N on Filings tab" used to be a
  /// dead tap. Wired to the real controller instead.
  final TabController tabController;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final overview = profile.overview;
    final filings = profile.filings;
    return ListView(
      padding: const EdgeInsets.fromLTRB(
          AmiSpacing.m, 0, AmiSpacing.m, AmiSpacing.xxl),
      children: [
        _Card(
          title: l.companyReviewBusinessDescription,
          sourceTag: sourceTagFor(overview.fieldState.sources, fallbackLabel: l.companyReviewSourceYfinance, l: l),
          onExpand: overview.description == null
              ? null
              : () => _showTextSheet(
                  context, l.companyReviewBusinessDescription, overview.description!),
          expandLabel:
              overview.description == null ? null : l.companyReviewViewFullDetail,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (overview.description != null)
                Text(
                  overview.description!,
                  maxLines: 4,
                  overflow: TextOverflow.ellipsis,
                  style: AmiTypography.body.copyWith(color: AmiColors.textMed),
                ),
              // B2 audit fix — a `partial` state must show its reason even
              // when SOME fields (here, description) came through live.
              if (!overview.fieldState.isLive)
                _StateNote(reason: overview.fieldState.reason),
            ],
          ),
        ),
        _Card(
          title: l.companyReviewClassification,
          sourceTag: sourceTagFor(overview.fieldState.sources, fallbackLabel: l.companyReviewSourceEdgar, l: l),
          onExpand: () => _showAddressSheet(context, l, overview),
          expandLabel: l.companyReviewAddressContacts,
          child: overview.fieldState.isNotAvailable
              ? _StateNote(reason: overview.fieldState.reason)
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _KvGrid(entries: [
                      (l.companyReviewFieldSector, overview.sector ?? '—'),
                      (l.companyReviewFieldIndustry, overview.industry ?? '—'),
                      (l.companyReviewFieldSic, overview.sic ?? '—'),
                      (l.companyReviewFieldSicDescription,
                          overview.sicDescription ?? '—'),
                      (l.companyReviewFieldCik, profile.cik ?? '—'),
                      (l.companyReviewFieldEmployees,
                          _fmtThousands(overview.employees)),
                      (l.companyReviewFieldExchange, overview.exchange ?? '—'),
                    ]),
                    // B2 audit fix — `partial` classification (e.g. no CIK
                    // match, EDGAR fields withheld) still needs its reason
                    // visible alongside whatever yfinance fields did load.
                    if (overview.fieldState.state == 'partial')
                      _StateNote(reason: overview.fieldState.reason),
                  ],
                ),
        ),
        if (filings.items.isNotEmpty)
          _Card(
            title: l.companyReviewMostRecentFiling,
            sourceTag:
                sourceTagFor(filings.fieldState.sources, fallbackLabel: l.companyReviewSourceEdgar, l: l),
            onExpand: () => tabController.animateTo(2),
            expandLabel: l.companyReviewSeeAllFilings(filings.items.length),
            child: _FilingRow(item: filings.items.first),
          )
        else if (!filings.fieldState.isLive)
          _Card(
            title: l.companyReviewMostRecentFiling,
            sourceTag: sourceTagFor(filings.fieldState.sources, fallbackLabel: l.companyReviewSourceEdgar, l: l),
            child: _StateNote(reason: filings.fieldState.reason),
          ),
      ],
    );
  }

  void _showTextSheet(BuildContext context, String title, String body) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AmiColors.slate800,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => _DetailSheet(
        title: title,
        child: Text(body, style: AmiTypography.body),
      ),
    );
  }

  void _showAddressSheet(
      BuildContext context, AppLocalizations l, CompanyOverview overview) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AmiColors.slate800,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => _DetailSheet(
        title: l.companyReviewAddressContacts,
        child: overview.fieldState.isNotAvailable
            ? _StateNote(reason: overview.fieldState.reason)
            : _KvGrid(entries: [
                (l.companyReviewFieldExchange, overview.exchange ?? '—'),
                (l.companyReviewFieldWebsite, overview.website ?? '—'),
                (l.companyReviewFieldPhone, overview.phone ?? '—'),
                (l.companyReviewFieldAddress, overview.address ?? '—'),
              ]),
      ),
    );
  }
}

/// B4 audit fix — employees formatted with a thousands separator (L5), and
/// an honest '—' rather than a bare 'null'.toString() edge case.
String _fmtThousands(int? v) => v == null ? '—' : NumberFormat('#,##0').format(v);

class _DetailSheet extends StatelessWidget {
  const _DetailSheet({required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(AmiSpacing.m),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // A full-height sheet leaves no scrim to tap, so it carries the
            // app's own back affordance (CR232: a back arrow, never an X).
            Row(
              children: [
                IconButton(
                  key: const Key('company_review_sheet_back'),
                  icon: const Icon(Icons.arrow_back, color: AmiColors.textHigh),
                  tooltip: MaterialLocalizations.of(context).backButtonTooltip,
                  onPressed: () => Navigator.of(context).pop(),
                ),
                Expanded(
                  child: Text(title,
                      style: AmiTypography.labelMono
                          .copyWith(color: AmiColors.hexCyan)),
                ),
              ],
            ),
            const SizedBox(height: AmiSpacing.s),
            Flexible(child: SingleChildScrollView(child: child)),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Financials tab
// ─────────────────────────────────────────────────────────────────────────

class _FinancialsTab extends StatefulWidget {
  const _FinancialsTab({required this.financials});

  final CompanyFinancials financials;

  @override
  State<_FinancialsTab> createState() => _FinancialsTabState();
}

class _FinancialsTabState extends State<_FinancialsTab> {
  // M5 audit fix — "view full detail" expand revealing every financials
  // field; only a 4-field summary shows by default.
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final financials = widget.financials;
    final l = AppLocalizations.of(context);
    final fmtCompact = NumberFormat.compact();
    // M3 audit fix — currency from financials.currency, never a hardcoded
    // '$'. Falls back to a bare compact number (no invented currency symbol)
    // when currency is absent, per CR040 — never fabricate a unit.
    String money(double? v) {
      if (v == null) return '—';
      final currency = financials.currency;
      if (currency == null) return fmtCompact.format(v);
      return NumberFormat.compactSimpleCurrency(name: currency).format(v);
    }

    // M2 audit fix — up to 2 decimals so 0.042 -> "4.2%" and 0.0002 ->
    // "0.02%", never "0%" for a genuinely nonzero value.
    String pct(double? v) {
      if (v == null) return '—';
      final fmtPct = NumberFormat.decimalPercentPattern(decimalDigits: 2);
      final formatted = fmtPct.format(v);
      // decimalPercentPattern always pads to 2dp ("4.20%"); trim trailing
      // zeros but keep at least one significant digit after the point when
      // there is one, so 0.042 shows "4.2%" not "4.20%".
      return formatted.replaceAllMapped(
          RegExp(r'(\.\d*?)0+%$'), (m) => '${m[1]}%'.replaceAll('.%', '%'));
    }

    String num_(double? v) => v == null ? '—' : v.toStringAsFixed(2);

    return ListView(
      padding: const EdgeInsets.fromLTRB(
          AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, AmiSpacing.xxl),
      children: [
        _Card(
          title: l.companyReviewFinancialsHeading,
          sourceTag: sourceTagFor(financials.fieldState.sources, fallbackLabel: l.companyReviewSourceYfinance, l: l),
          onExpand: financials.fieldState.isNotAvailable
              ? null
              : () => setState(() => _expanded = !_expanded),
          expandLabel: financials.fieldState.isNotAvailable
              ? null
              : (_expanded
                  ? l.companyReviewShowLess
                  : l.companyReviewViewFullDetail),
          child: financials.fieldState.isNotAvailable
              ? _StateNote(reason: financials.fieldState.reason)
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _KvGrid(entries: [
                      (l.companyReviewFieldMarketCap, money(financials.marketCap)),
                      (l.companyReviewFieldRevenueTtm, money(financials.revenueTtm)),
                      (l.companyReviewFieldGrossMargin, pct(financials.grossMargin)),
                      (l.companyReviewFieldTrailingPe, num_(financials.trailingPe)),
                      if (_expanded) ...[
                        (l.companyReviewFieldOperatingMargin,
                            pct(financials.operatingMargin)),
                        (l.companyReviewFieldNetMargin, pct(financials.netMargin)),
                        (l.companyReviewFieldForwardPe, num_(financials.forwardPe)),
                        (l.companyReviewFieldEpsTtm, num_(financials.epsTtm)),
                        (l.companyReviewFieldDebtToEquity,
                            num_(financials.debtToEquity)),
                        (l.companyReviewFieldFreeCashFlow,
                            money(financials.freeCashFlow)),
                        (l.companyReviewFieldDividendYield,
                            pct(financials.dividendYield)),
                      ],
                    ]),
                    if (financials.fieldState.state == 'partial') ...[
                      const SizedBox(height: AmiSpacing.s),
                      _StateNote(reason: financials.fieldState.reason),
                    ],
                  ],
                ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Filings tab
// ─────────────────────────────────────────────────────────────────────────

class _FilingsTab extends StatelessWidget {
  const _FilingsTab({required this.filings});

  final CompanyFilings filings;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return ListView(
      padding: const EdgeInsets.fromLTRB(
          AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, AmiSpacing.xxl),
      children: [
        _Card(
          title: l.companyReviewFilingsHeading,
          sourceTag: sourceTagFor(filings.fieldState.sources, fallbackLabel: l.companyReviewSourceEdgar, l: l),
          child: filings.items.isEmpty
              ? _StateNote(reason: filings.fieldState.reason)
              : Column(
                  children: [
                    for (final item in filings.items) _FilingRow(item: item),
                  ],
                ),
        ),
      ],
    );
  }
}

class _FilingRow extends StatelessWidget {
  const _FilingRow({required this.item});

  final FilingItem item;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return InkWell(
      onTap: item.url == null ? null : () => _openLink(context, item.url),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
              decoration: BoxDecoration(
                color: AmiColors.hexPurple.withValues(alpha: 0.18),
                borderRadius: BorderRadius.circular(5),
              ),
              child: Text(
                item.form,
                style: AmiTypography.caption.copyWith(
                  color: AmiColors.hexPurple,
                  fontFamily: AmiTypography.plexMono,
                  fontWeight: FontWeight.bold,
                  fontSize: 9.5,
                ),
              ),
            ),
            const SizedBox(width: AmiSpacing.s),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(item.description ?? item.form,
                      style: AmiTypography.body.copyWith(
                          color: AmiColors.textHigh,
                          fontSize: 11.5,
                          fontWeight: FontWeight.w600)),
                  Text(
                    item.filedDate == null
                        ? '—'
                        : l.companyReviewFiledOn(item.filedDate!),
                    style: AmiTypography.caption
                        .copyWith(color: AmiColors.textLow, fontSize: 10),
                  ),
                ],
              ),
            ),
            if (item.url != null)
              Text(
                l.companyReviewFilingOpen,
                style: AmiTypography.body.copyWith(
                    color: AmiColors.hexBlue,
                    fontSize: 10.5,
                    fontWeight: FontWeight.bold),
              ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Ownership tab
// ─────────────────────────────────────────────────────────────────────────

class _OwnershipTab extends StatelessWidget {
  const _OwnershipTab({required this.ownership});

  final CompanyOwnership ownership;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final fmtPct = NumberFormat.decimalPercentPattern(decimalDigits: 2);
    final fmtShares = NumberFormat('#,##0');
    final inst = ownership.pctInstitutions;
    final ins = ownership.pctInsiders;
    // M1 audit fix — float is NEVER derived as 1 - institutions - insiders
    // (that both double-counts overlapping filers and can go negative).
    // Shown instead as float_shares / shares_outstanding, when the backend
    // provides both; clamped to >= 0 as defence in depth (CR040 — a
    // computed figure must never render as a fabricated negative).
    final sharesOut = ownership.sharesOutstanding;
    final floatShares = ownership.floatShares;
    final floatPct = (sharesOut != null && sharesOut > 0 && floatShares != null)
        ? (floatShares / sharesOut).clamp(0.0, 1.0)
        : null;

    return ListView(
      padding: const EdgeInsets.fromLTRB(
          AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, AmiSpacing.xxl),
      children: [
        _Card(
          title: l.companyReviewOwnershipSplit,
          sourceTag: sourceTagFor(ownership.fieldState.sources, fallbackLabel: l.companyReviewSourceYfinance, l: l),
          child: ownership.fieldState.isNotAvailable
              ? _StateNote(reason: ownership.fieldState.reason)
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _KvGrid(entries: [
                      (l.companyReviewFieldInstitutions,
                          inst == null ? '—' : fmtPct.format(inst)),
                      (l.companyReviewFieldInsiders,
                          ins == null ? '—' : fmtPct.format(ins)),
                      (l.companyReviewFieldFloat,
                          floatPct == null ? '—' : fmtPct.format(floatPct)),
                      (l.companyReviewFieldSharesOutstanding,
                          sharesOut == null ? '—' : fmtShares.format(sharesOut)),
                    ]),
                    if (ownership.fieldState.state == 'partial')
                      _StateNote(reason: ownership.fieldState.reason),
                  ],
                ),
        ),
        if (ownership.holders.isNotEmpty)
          _Card(
            title: l.companyReviewMajorHolders,
            sourceTag:
                sourceTagFor(ownership.fieldState.sources, fallbackLabel: l.companyReviewSourceYfinance, l: l),
            onExpand: () => _showHoldersSheet(context, l),
            expandLabel: l.companyReviewSeeAllHolders,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l.companyReviewMajorHoldersBody,
                    style:
                        AmiTypography.body.copyWith(color: AmiColors.textMed)),
                const SizedBox(height: AmiSpacing.s),
                for (final h in ownership.holders.take(3))
                  _HolderRow(holder: h, l: l),
              ],
            ),
          ),
        _OwnershipStateLine(text: l.companyReviewOwnershipStateLine),
      ],
    );
  }

  void _showHoldersSheet(BuildContext context, AppLocalizations l) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AmiColors.slate800,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => _DetailSheet(
        title: l.companyReviewMajorHolders,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final h in ownership.holders) _HolderRow(holder: h, l: l),
          ],
        ),
      ),
    );
  }
}

class _HolderRow extends StatelessWidget {
  const _HolderRow({required this.holder, required this.l});

  final CompanyHolder holder;
  final AppLocalizations l;

  @override
  Widget build(BuildContext context) {
    final fmtPct = NumberFormat.decimalPercentPattern(decimalDigits: 2);
    final fmtShares = NumberFormat('#,##0');
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(holder.name,
                    style: AmiTypography.body.copyWith(
                        color: AmiColors.textHigh,
                        fontSize: 11.5,
                        fontWeight: FontWeight.w600)),
                // L5 audit fix — show holder shares alongside pct held.
                if (holder.shares != null)
                  Text(
                      '${l.companyReviewFieldHolderShares}: '
                      '${fmtShares.format(holder.shares)}',
                      style: AmiTypography.caption
                          .copyWith(color: AmiColors.textLow, fontSize: 10)),
                if (holder.dateReported != null)
                  Text(l.companyReviewReportedOn(holder.dateReported!),
                      style: AmiTypography.caption
                          .copyWith(color: AmiColors.textLow, fontSize: 10)),
              ],
            ),
          ),
          Text(
            holder.pctHeld == null ? '—' : fmtPct.format(holder.pctHeld!),
            style: AmiTypography.dataMd.copyWith(fontSize: 12.5),
          ),
        ],
      ),
    );
  }
}

class _OwnershipStateLine extends StatelessWidget {
  const _OwnershipStateLine({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: AmiSpacing.s),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        border: Border.all(color: AmiColors.slate700),
        borderRadius: BorderRadius.circular(AmiRadii.card),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('⚠', style: TextStyle(fontSize: 12)),
          const SizedBox(width: 6),
          Expanded(
            child: Text(text,
                style: AmiTypography.caption
                    .copyWith(color: AmiColors.textLow, fontSize: 10.5)),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Insider tab
// ─────────────────────────────────────────────────────────────────────────

class _InsiderTab extends ConsumerWidget {
  const _InsiderTab({required this.ticker});

  final String ticker;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final async = ref.watch(insiderActivityProvider(ticker));
    return async.when(
      data: (activity) => _InsiderLoaded(activity: activity),
      // L2 audit fix — a short caption under the spinner, since this is the
      // documented slow endpoint (up to 25 Form 4 XML fetches).
      loading: () => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(color: AmiColors.hexCyan),
            const SizedBox(height: AmiSpacing.s),
            Text(l.companyReviewInsiderLoadingCaption,
                style: AmiTypography.caption
                    .copyWith(color: AmiColors.textLow)),
          ],
        ),
      ),
      // L2 audit fix — add a retry, mirroring the whole-screen error state.
      error: (e, _) => Padding(
        padding: const EdgeInsets.all(AmiSpacing.m),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _StateNote(reason: l.companyReviewInsiderLoadFailed),
            const SizedBox(height: AmiSpacing.s),
            OutlinedButton(
              onPressed: () => ref.invalidate(insiderActivityProvider(ticker)),
              child: Text(l.companyReviewRetry),
            ),
          ],
        ),
      ),
    );
  }
}

class _InsiderLoaded extends StatefulWidget {
  const _InsiderLoaded({required this.activity});

  final InsiderActivity activity;

  @override
  State<_InsiderLoaded> createState() => _InsiderLoadedState();
}

class _InsiderLoadedState extends State<_InsiderLoaded> {
  // M5 audit fix — "view full detail" expand on the summary card, revealing
  // the full transaction list (companyReviewFullTransactionList).
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final activity = widget.activity;
    final summary = activity.summary;
    // L3 audit fix — the heading uses the backend's own window_days, never a
    // hardcoded "Last 90 days".
    final heading = l.companyReviewLastNDays(activity.windowDays ?? 90);
    final transactions = activity.transactions;
    final visibleTransactions =
        _expanded ? transactions : transactions.take(5).toList();
    return ListView(
      padding: const EdgeInsets.fromLTRB(
          AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, AmiSpacing.xxl),
      children: [
        if (activity.fieldState.isNotAvailable)
          _Card(
            title: heading,
            sourceTag: _SourceTag(label: l.companyReviewSourceForms345, isEdgar: true),
            child: _StateNote(reason: activity.fieldState.reason),
          )
        else if (summary != null)
          _Card(
            title: heading,
            sourceTag: _SourceTag(label: l.companyReviewSourceForms345, isEdgar: true),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _KvGrid(entries: [
                  (l.companyReviewNetSentiment,
                      _netDirectionLabel(l, summary.netDirection)),
                  (l.companyReviewBuysSells,
                      '${summary.buys} / ${summary.sells}'),
                ]),
                // B2 audit fix — a `partial` state must show its reason even
                // when a summary object came through.
                if (activity.fieldState.state == 'partial')
                  _StateNote(reason: activity.fieldState.reason),
              ],
            ),
          )
        else
          // L3 audit fix — a missing summary is an honest "—", never a
          // fabricated zero-count summary.
          _Card(
            title: heading,
            sourceTag: _SourceTag(label: l.companyReviewSourceForms345, isEdgar: true),
            child: _KvGrid(entries: [
              (l.companyReviewNetSentiment, l.companyReviewMissingCount),
              (l.companyReviewBuysSells, l.companyReviewMissingCount),
            ]),
          ),
        if (transactions.isNotEmpty)
          _Card(
            title: l.companyReviewRecentForm4s,
            sourceTag: sourceTagFor(activity.fieldState.sources,
                fallbackLabel: l.companyReviewSourceEdgar, l: l),
            onExpand: transactions.length <= 5
                ? null
                : () => setState(() => _expanded = !_expanded),
            expandLabel: transactions.length <= 5
                ? null
                : (_expanded
                    ? l.companyReviewShowLess
                    : l.companyReviewFullTransactionList),
            child: Column(
              children: [
                for (final t in visibleTransactions)
                  _InsiderRow(t: t, l: l),
              ],
            ),
          ),
        Container(
          margin: const EdgeInsets.only(top: AmiSpacing.s),
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: AmiColors.slate800,
            border: Border.all(color: AmiColors.slate700),
            borderRadius: BorderRadius.circular(AmiRadii.card),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('⚠', style: TextStyle(fontSize: 12)),
              const SizedBox(width: 6),
              Expanded(
                child: Text(l.companyReviewInsiderStateLine,
                    style: AmiTypography.caption
                        .copyWith(color: AmiColors.textLow, fontSize: 10.5)),
              ),
            ],
          ),
        ),
      ],
    );
  }

  // L3 audit fix — an unknown net_direction value renders the raw string
  // rather than being silently folded into NONE, which would fabricate an
  // "activity" reading (none) the backend never asserted.
  String _netDirectionLabel(AppLocalizations l, String v) {
    switch (v) {
      case 'buying':
        return l.companyReviewNetDirectionBuying;
      case 'selling':
        return l.companyReviewNetDirectionSelling;
      case 'mixed':
        return l.companyReviewNetDirectionMixed;
      case 'none':
        return l.companyReviewNetDirectionNone;
      default:
        return v.toUpperCase();
    }
  }
}

class _InsiderRow extends StatelessWidget {
  const _InsiderRow({required this.t, required this.l});

  final InsiderTransaction t;
  final AppLocalizations l;

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat('#,##0');
    Widget? badge;
    // CR244 correction, plus L4 audit fix (defence in depth): a BUY/SELL
    // badge requires BOTH direction == buy/sell AND code in {P, S} — never
    // direction alone. That way a server-side direction bug can't put a
    // BUY/SELL badge on a non-P/S row; this client independently re-checks
    // the code before ever rendering one. Everything else (M exercise, A
    // grant, F withholding, G gift, …) shows its own code_label in a neutral
    // badge — falling back to the raw code when code_label is null, so an
    // unrecognised code still renders something honest, never a blank badge.
    final isBuySellCode = t.code == 'P' || t.code == 'S';
    if (t.isBuy && isBuySellCode) {
      badge = _Badge(
          label: l.companyReviewBadgeBuy, color: AmiColors.hexGreen);
    } else if (t.isSell && isBuySellCode) {
      badge =
          _Badge(label: l.companyReviewBadgeSell, color: AmiColors.hexRed);
    } else {
      final neutralLabel = t.codeLabel ?? t.code;
      if (neutralLabel.isNotEmpty) {
        badge = _Badge(
            label: neutralLabel.toUpperCase(), color: AmiColors.hexPurple);
      }
    }
    final showsBuySellBadge =
        (t.isBuy || t.isSell) && isBuySellCode;

    return InkWell(
      onTap: t.url == null ? null : () => _openLink(context, t.url),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            if (badge != null) ...[badge, const SizedBox(width: AmiSpacing.s)],
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          [t.insiderName, t.role]
                              .whereType<String>()
                              .join(' · '),
                          style: AmiTypography.body.copyWith(
                              color: AmiColors.textHigh,
                              fontSize: 11.5,
                              fontWeight: FontWeight.w600),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      // L4 audit fix — the 10b5-1 tag is shown ONLY on P/S
                      // rows; it is meaningless (and could read as spurious
                      // reassurance) on an M/A/F/G/other row.
                      if (showsBuySellBadge && t.isScheduled10b5_1) ...[
                        const SizedBox(width: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 5, vertical: 1),
                          decoration: BoxDecoration(
                            color: AmiColors.slate700,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            l.companyReview10b51Tag,
                            style: AmiTypography.caption.copyWith(
                                color: AmiColors.textMed,
                                fontSize: 8.5,
                                fontFamily: AmiTypography.plexMono),
                          ),
                        ),
                      ],
                    ],
                  ),
                  Text(
                    [
                      t.transactionDate,
                      if (t.shares != null)
                        l.companyReviewSharesUnit(fmt.format(t.shares)),
                      if (t.price != null)
                        '@ \$${t.price!.toStringAsFixed(2)}',
                    ].whereType<String>().join(' · '),
                    style: AmiTypography.caption
                        .copyWith(color: AmiColors.textLow, fontSize: 10),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.18),
        borderRadius: BorderRadius.circular(5),
      ),
      child: Text(
        label,
        style: AmiTypography.caption.copyWith(
          color: color,
          fontFamily: AmiTypography.plexMono,
          fontWeight: FontWeight.bold,
          fontSize: 9.5,
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Events tab — no new endpoint: existing earnings feed + the 8-K filings.
// ─────────────────────────────────────────────────────────────────────────

class _EventsTab extends ConsumerWidget {
  const _EventsTab({required this.ticker, required this.filings});

  final String ticker;
  final CompanyFilings filings;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final earningsAsync = ref.watch(tickerEarningsProvider(ticker));
    final eightKs = filings.items.where((f) => f.isEightK).toList();

    return earningsAsync.when(
      data: (earnings) =>
          _EventsLoaded(earnings: earnings, eightKs: eightKs, filings: filings),
      loading: () =>
          const Center(child: CircularProgressIndicator(color: AmiColors.hexCyan)),
      // B3 audit fix — a provider error is NOT "no earnings" (that would
      // fabricate an absence the backend never asserted). Render an
      // explicit error note instead, distinct from the empty state.
      error: (_, __) => Padding(
        padding: const EdgeInsets.all(AmiSpacing.m),
        child: _StateNote(reason: l.companyReviewEarningsLoadFailed),
      ),
    );
  }
}

class _EventsLoaded extends StatefulWidget {
  const _EventsLoaded(
      {required this.earnings, required this.eightKs, required this.filings});

  final SimEarnings? earnings;
  final List<FilingItem> eightKs;
  final CompanyFilings filings;

  @override
  State<_EventsLoaded> createState() => _EventsLoadedState();
}

class _EventsLoadedState extends State<_EventsLoaded> {
  // M5 audit fix — "view full detail" expand on the 8-K list; only the 3
  // most recent show by default.
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final earnings = widget.earnings;
    final eightKs = widget.eightKs;
    final filings = widget.filings;
    final l = AppLocalizations.of(context);
    // B3 audit fix — earnings loaded OK (this widget only builds on the
    // `data` branch) but with no date is a genuine "no upcoming earnings";
    // that combines with the filings feed to decide the empty state below.
    final hasEarnings = earnings?.hasData ?? false;
    final filingsLive = filings.fieldState.isLive;
    // The all-clear empty state may ONLY fire when earnings loaded with no
    // date AND filings is live with zero 8-Ks — never when filings is
    // partial/not_available, which would silently claim "no recent 8-K
    // filings" when the truth is "we don't know."
    if (!hasEarnings && eightKs.isEmpty && filingsLive) {
      return Padding(
        padding: const EdgeInsets.all(AmiSpacing.m),
        child: Text(l.companyReviewNoEvents,
            style: AmiTypography.body.copyWith(color: AmiColors.textLow)),
      );
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(
          AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, AmiSpacing.xxl),
      children: [
        if (hasEarnings && earnings != null)
          _Card(
            title: l.companyReviewEventsHeading,
            sourceTag: _SourceTag(label: l.companyReviewSourceYfinance, isEdgar: false),
            child: _KvGrid(entries: [
              (l.companyReviewFieldEarningsDate, earnings.earningsDate ?? '—'),
              if (earnings.quarter != null)
                (l.companyReviewFieldQuarter, earnings.quarter!),
              if (earnings.epsEstimate != null)
                (l.companyReviewFieldEpsEstimate,
                    earnings.epsEstimate!.toStringAsFixed(2)),
            ]),
          ),
        if (eightKs.isNotEmpty)
          _Card(
            title: l.companyReviewEightKFilingsHeading,
            sourceTag: _SourceTag(label: l.companyReviewSourceEdgar, isEdgar: true),
            onExpand: eightKs.length <= 3
                ? null
                : () => setState(() => _expanded = !_expanded),
            expandLabel: eightKs.length <= 3
                ? null
                : (_expanded
                    ? l.companyReviewShowLess
                    : l.companyReviewViewFullDetail),
            child: Column(
              children: [
                for (final f in (_expanded ? eightKs : eightKs.take(3)))
                  _FilingRow(item: f),
              ],
            ),
          )
        else if (!filingsLive)
          // B3 audit fix — filings not live must show ITS OWN reason, never
          // the blanket "no recent 8-K filings" line (that would fabricate
          // an absence from an unknown).
          _Card(
            title: l.companyReviewEightKFilingsHeading,
            sourceTag: _SourceTag(label: l.companyReviewSourceEdgar, isEdgar: true),
            child: _StateNote(reason: filings.fieldState.reason),
          ),
      ],
    );
  }
}
