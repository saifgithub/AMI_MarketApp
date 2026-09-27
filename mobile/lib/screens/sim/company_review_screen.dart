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
              _OverviewTab(ticker: ticker, profile: profile),
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

/// A source tag derived from a section's `sources` list. Falls back to
/// EDGAR-styling for an unrecognised/empty list rather than guessing wrong
/// the other way — EDGAR is this screen's more common source.
Widget sourceTagFor(List<String> sources, {String? fallbackLabel}) {
  final hasEdgar = sources.contains('edgar');
  final hasYfinance = sources.contains('yfinance');
  final label = fallbackLabel ??
      (hasEdgar && hasYfinance
          ? 'EDGAR + YFINANCE'
          : hasYfinance
              ? 'YFINANCE'
              : 'EDGAR');
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
  const _OverviewTab({required this.ticker, required this.profile});

  final String ticker;
  final CompanyProfile profile;

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
          sourceTag: sourceTagFor(overview.fieldState.sources, fallbackLabel: 'YFINANCE'),
          onExpand: overview.description == null
              ? null
              : () => _showTextSheet(
                  context, l.companyReviewBusinessDescription, overview.description!),
          expandLabel:
              overview.description == null ? null : l.companyReviewViewFullDetail,
          child: overview.description == null
              ? _StateNote(reason: overview.fieldState.reason)
              : Text(
                  overview.description!,
                  maxLines: 4,
                  overflow: TextOverflow.ellipsis,
                  style: AmiTypography.body.copyWith(color: AmiColors.textMed),
                ),
        ),
        _Card(
          title: l.companyReviewClassification,
          sourceTag: sourceTagFor(overview.fieldState.sources, fallbackLabel: 'EDGAR'),
          onExpand: () => _showAddressSheet(context, l, overview),
          expandLabel: l.companyReviewAddressContacts,
          child: overview.fieldState.isNotAvailable
              ? _StateNote(reason: overview.fieldState.reason)
              : _KvGrid(entries: [
                  (l.companyReviewFieldSic,
                      overview.sic ?? overview.sicDescription ?? '—'),
                  (l.companyReviewFieldCik, profile.cik ?? '—'),
                  (l.companyReviewFieldEmployees,
                      overview.employees?.toString() ?? '—'),
                  (l.companyReviewFieldExchange, overview.exchange ?? '—'),
                ]),
        ),
        if (filings.items.isNotEmpty)
          _Card(
            title: l.companyReviewMostRecentFiling,
            sourceTag:
                sourceTagFor(filings.fieldState.sources, fallbackLabel: 'EDGAR'),
            onExpand: () {
              final tabs = DefaultTabController.maybeOf(context);
              tabs?.animateTo(2);
            },
            expandLabel: l.companyReviewSeeAllFilings(filings.items.length),
            child: _FilingRow(item: filings.items.first),
          )
        else if (!filings.fieldState.isLive)
          _Card(
            title: l.companyReviewMostRecentFiling,
            sourceTag: sourceTagFor(filings.fieldState.sources, fallbackLabel: 'EDGAR'),
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
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => _DetailSheet(
        title: l.companyReviewAddressContacts,
        child: overview.fieldState.isNotAvailable
            ? _StateNote(reason: overview.fieldState.reason)
            : _KvGrid(entries: [
                (l.companyReviewFieldExchange, overview.exchange ?? '—'),
                ('Website', overview.website ?? '—'),
                ('Phone', overview.phone ?? '—'),
                ('Address', overview.address ?? '—'),
              ]),
      ),
    );
  }
}

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
            Text(title,
                style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
            const SizedBox(height: AmiSpacing.m),
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

class _FinancialsTab extends StatelessWidget {
  const _FinancialsTab({required this.financials});

  final CompanyFinancials financials;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final fmtCompact = NumberFormat.compact();
    final fmtPct = NumberFormat.percentPattern();
    String money(double? v) => v == null ? '—' : '\$${fmtCompact.format(v)}';
    String pct(double? v) => v == null ? '—' : fmtPct.format(v);
    String num_(double? v) => v == null ? '—' : v.toStringAsFixed(2);

    return ListView(
      padding: const EdgeInsets.fromLTRB(
          AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, AmiSpacing.xxl),
      children: [
        _Card(
          title: l.companyReviewFinancialsHeading,
          sourceTag: sourceTagFor(financials.fieldState.sources, fallbackLabel: 'YFINANCE'),
          child: financials.fieldState.isNotAvailable
              ? _StateNote(reason: financials.fieldState.reason)
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _KvGrid(entries: [
                      (l.companyReviewFieldMarketCap, money(financials.marketCap)),
                      (l.companyReviewFieldRevenueTtm, money(financials.revenueTtm)),
                      (l.companyReviewFieldGrossMargin, pct(financials.grossMargin)),
                      (l.companyReviewFieldOperatingMargin,
                          pct(financials.operatingMargin)),
                      (l.companyReviewFieldNetMargin, pct(financials.netMargin)),
                      (l.companyReviewFieldTrailingPe, num_(financials.trailingPe)),
                      (l.companyReviewFieldForwardPe, num_(financials.forwardPe)),
                      (l.companyReviewFieldEpsTtm, num_(financials.epsTtm)),
                      (l.companyReviewFieldDebtToEquity,
                          num_(financials.debtToEquity)),
                      (l.companyReviewFieldFreeCashFlow,
                          money(financials.freeCashFlow)),
                      (l.companyReviewFieldDividendYield,
                          pct(financials.dividendYield)),
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
          sourceTag: sourceTagFor(filings.fieldState.sources, fallbackLabel: 'EDGAR'),
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
      onTap: item.url == null
          ? null
          : () {
              final uri = Uri.tryParse(item.url!);
              if (uri != null) {
                launchUrl(uri, mode: LaunchMode.externalApplication);
              }
            },
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
                        : 'Filed ${item.filedDate}',
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
    final fmtPct = NumberFormat.percentPattern();
    final inst = ownership.pctInstitutions;
    final ins = ownership.pctInsiders;
    final float = (inst != null && ins != null) ? (1 - inst - ins) : null;

    return ListView(
      padding: const EdgeInsets.fromLTRB(
          AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, AmiSpacing.xxl),
      children: [
        _Card(
          title: l.companyReviewOwnershipSplit,
          sourceTag: sourceTagFor(ownership.fieldState.sources, fallbackLabel: 'YFINANCE'),
          child: ownership.fieldState.isNotAvailable
              ? _StateNote(reason: ownership.fieldState.reason)
              : _KvGrid(entries: [
                  (l.companyReviewFieldInstitutions,
                      inst == null ? '—' : fmtPct.format(inst)),
                  (l.companyReviewFieldInsiders,
                      ins == null ? '—' : fmtPct.format(ins)),
                  (l.companyReviewFieldPublicFloat,
                      float == null ? '—' : fmtPct.format(float)),
                ]),
        ),
        if (ownership.holders.isNotEmpty)
          _Card(
            title: l.companyReviewMajorHolders,
            sourceTag:
                sourceTagFor(ownership.fieldState.sources, fallbackLabel: 'YFINANCE'),
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
    final fmtPct = NumberFormat.percentPattern();
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
      loading: () =>
          const Center(child: CircularProgressIndicator(color: AmiColors.hexCyan)),
      error: (e, _) => Padding(
        padding: const EdgeInsets.all(AmiSpacing.m),
        child: _StateNote(reason: l.companyReviewInsiderLoadFailed),
      ),
    );
  }
}

class _InsiderLoaded extends StatelessWidget {
  const _InsiderLoaded({required this.activity});

  final InsiderActivity activity;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final summary = activity.summary;
    return ListView(
      padding: const EdgeInsets.fromLTRB(
          AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, AmiSpacing.xxl),
      children: [
        if (activity.fieldState.isNotAvailable)
          _Card(
            title: l.companyReviewInsiderLast90Days,
            sourceTag: const _SourceTag(label: 'FORMS 3/4/5', isEdgar: true),
            child: _StateNote(reason: activity.fieldState.reason),
          )
        else if (summary != null)
          _Card(
            title: l.companyReviewInsiderLast90Days,
            sourceTag: const _SourceTag(label: 'FORMS 3/4/5', isEdgar: true),
            child: _KvGrid(entries: [
              (l.companyReviewNetSentiment, _netDirectionLabel(l, summary.netDirection)),
              (l.companyReviewBuysSells, '${summary.buys} / ${summary.sells}'),
            ]),
          ),
        if (activity.transactions.isNotEmpty)
          _Card(
            title: l.companyReviewRecentForm4s,
            sourceTag: sourceTagFor(activity.fieldState.sources,
                fallbackLabel: 'EDGAR'),
            child: Column(
              children: [
                for (final t in activity.transactions)
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

  String _netDirectionLabel(AppLocalizations l, String v) {
    switch (v) {
      case 'buying':
        return l.companyReviewNetDirectionBuying;
      case 'selling':
        return l.companyReviewNetDirectionSelling;
      case 'mixed':
        return l.companyReviewNetDirectionMixed;
      default:
        return l.companyReviewNetDirectionNone;
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
    // CR244 correction: ONLY direction == buy/sell ever gets a BUY/SELL
    // badge. Everything else (M exercise, A grant, F withholding, G gift,
    // …) shows its own code_label in a neutral badge — never as BUY.
    if (t.isBuy) {
      badge = _Badge(
          label: l.companyReviewBadgeBuy, color: AmiColors.hexGreen);
    } else if (t.isSell) {
      badge =
          _Badge(label: l.companyReviewBadgeSell, color: AmiColors.hexRed);
    } else if (t.codeLabel != null) {
      badge = _Badge(label: t.codeLabel!.toUpperCase(), color: AmiColors.hexPurple);
    }

    return InkWell(
      onTap: t.url == null
          ? null
          : () {
              final uri = Uri.tryParse(t.url!);
              if (uri != null) {
                launchUrl(uri, mode: LaunchMode.externalApplication);
              }
            },
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
                      if (t.isScheduled10b5_1) ...[
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
                        '${fmt.format(t.shares)} sh',
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
    final earningsAsync = ref.watch(tickerEarningsProvider(ticker));
    final eightKs = filings.items.where((f) => f.isEightK).toList();

    return earningsAsync.when(
      data: (earnings) => _EventsLoaded(earnings: earnings, eightKs: eightKs),
      loading: () =>
          const Center(child: CircularProgressIndicator(color: AmiColors.hexCyan)),
      error: (_, __) => _EventsLoaded(earnings: null, eightKs: eightKs),
    );
  }
}

class _EventsLoaded extends StatelessWidget {
  const _EventsLoaded({required this.earnings, required this.eightKs});

  final SimEarnings? earnings;
  final List<FilingItem> eightKs;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final hasEarnings = earnings?.hasData ?? false;
    if (!hasEarnings && eightKs.isEmpty) {
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
        if (hasEarnings)
          _Card(
            title: l.companyReviewEventsHeading,
            sourceTag: const _SourceTag(label: 'YFINANCE', isEdgar: false),
            child: _KvGrid(entries: [
              ('Earnings date', earnings!.earningsDate ?? '—'),
              if (earnings!.quarter != null) ('Quarter', earnings!.quarter!),
              if (earnings!.epsEstimate != null)
                ('EPS estimate', earnings!.epsEstimate!.toStringAsFixed(2)),
            ]),
          ),
        if (eightKs.isNotEmpty)
          _Card(
            title: '8-K filings',
            sourceTag: const _SourceTag(label: 'EDGAR', isEdgar: true),
            child: Column(
              children: [for (final f in eightKs) _FilingRow(item: f)],
            ),
          ),
      ],
    );
  }
}
