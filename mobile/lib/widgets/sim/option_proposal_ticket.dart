/// CR172 §10 step 4 — the option ticket: one structure, two buttons.
///
/// AMI generated the candidates, the PM picked one, the deterministic floor
/// re-validated it. This renders the result and takes a yes or a no. There is
/// no strike picker, no expiry picker and no chain to browse — a manual
/// chain-browsing ticket is named in CR172's "Not in scope" and is deliberately
/// absent, not merely unbuilt.
///
/// **Every figure on the card comes off the payload.** This file formats
/// numbers and it never produces one: no premium × multiplier, no days from a
/// date, no break-even from strikes, no max loss from legs. If the server sent
/// nothing, the row says *not computed* — loudly, in the place the figure would
/// have been. A zero would be indistinguishable from a real zero, and on a max
/// loss that is the difference between "you cannot lose money" and "we do not
/// know what you can lose" (DEF059, CR129-MOBILE's server-sourced-only fence).
///
/// **Three refusal-shaped states, kept apart because they mean different
/// things:**
///
///   * `violations` — the floor said no. Red panel, the server's sentences
///     verbatim, and **no YES button exists at all**. D3's uncovered short call
///     lands here, and the refusal explains the containment reasoning rather
///     than stating a rule number.
///   * `not_evaluated` — a check could not run (DEF169). Amber, its own
///     heading. "Checked and clear" and "could not check" must never render
///     the same.
///   * `advisories` — checked, found something, deliberately did not block
///     (CR171 §6, extended to options sell-to-open on 2026-08-20). Amber
///     notice, and the YES button routes through
///     [OptionDisclosureDialog] before it fires.
///
/// A refusal with an empty `violations` list still renders a sentence
/// ([AppLocalizations.optionTicketRefusedNoReason]): an error state is never an
/// empty state (CR040), and a blank red panel teaches the user that refusals
/// are noise.
///
/// **The disclosure structurally precedes the confirm.** `onAccept` is reached
/// from exactly one place — the branch after the dialog resolved `true`. It is
/// not a callback the dialog fires "as well"; there is no second path to it.
/// The equity ticket shows its advisory after the fill because the server only
/// decides at submit; here the structure is costed and checked before the user
/// is asked, so the notice can come first, and it does.
///
/// **No payoff diagram, deliberately.** §12 wants one, and drawing it means
/// evaluating the structure's payoff at a few hundred prices — client-side
/// arithmetic on exactly the figures this fence exists to keep server-side. It
/// ships when the server serves the curve, not before.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/option_proposal.dart';
import 'package:ami_trade/widgets/sim/option_payoff_chart.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/sim/option_disclosure_dialog.dart';
import 'package:flutter/material.dart';
// `intl` exports its own `TextDirection`, which shadows `dart:ui`'s.
import 'package:intl/intl.dart' hide TextDirection;

final _money = NumberFormat('#,##0.00');
final _count = NumberFormat('#,##0.##');

String _dollars(double v) =>
    '${v < 0 ? '−' : ''}\$${_money.format(v.abs())}';

class OptionProposalTicket extends StatefulWidget {
  const OptionProposalTicket({
    super.key,
    required this.proposal,
    required this.onAccept,
    required this.onDecline,
  });

  final OptionProposal proposal;

  /// Fired only after the disclosure gate, when there is one. Never called for
  /// a refused proposal — that state has no accept control to press.
  final void Function(OptionProposal) onAccept;
  final void Function(OptionProposal) onDecline;

  /// Presents the ticket as a modal sheet. Resolves `true` on accept, `false`
  /// on decline, `null` if the sheet was dismissed without an answer — three
  /// outcomes, because "dismissed" is not "declined" and the caller may want
  /// to ask again.
  static Future<bool?> show(BuildContext context, OptionProposal proposal) {
    return showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => OptionProposalTicket(
        proposal: proposal,
        onAccept: (_) => Navigator.of(ctx).pop(true),
        onDecline: (_) => Navigator.of(ctx).pop(false),
      ),
    );
  }

  @override
  State<OptionProposalTicket> createState() => _OptionProposalTicketState();
}

class _OptionProposalTicketState extends State<OptionProposalTicket> {
  bool _awaitingDisclosure = false;

  OptionProposal get _p => widget.proposal;

  /// The only route to [OptionProposalTicket.onAccept].
  Future<void> _accept() async {
    if (!_p.canAccept || _awaitingDisclosure) return;
    if (_p.requiresDisclosure) {
      setState(() => _awaitingDisclosure = true);
      final acknowledged =
          await OptionDisclosureDialog.show(context, _p.compliance.advisories);
      if (!mounted) return;
      setState(() => _awaitingDisclosure = false);
      if (acknowledged != true) return;
    }
    widget.onAccept(_p);
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final c = _p.compliance;
    final refused = _p.isRefused;

    return Container(
      decoration: const BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.vertical(top: Radius.circular(AmiRadii.sheet)),
      ),
      padding: const EdgeInsets.all(AmiSpacing.m),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _header(l),
              const SizedBox(height: AmiSpacing.m),
              if (refused) ...[
                _refusalPanel(l),
                const SizedBox(height: AmiSpacing.m),
              ],
              if (c.notEvaluated.isNotEmpty) ...[
                _noticePanel(
                  heading: l.optionTicketNotEvaluatedHeading,
                  icon: Icons.help_outline,
                  lines: c.notEvaluated,
                ),
                const SizedBox(height: AmiSpacing.m),
              ],
              if (c.advisories.isNotEmpty) ...[
                _noticePanel(
                  heading: l.optionTicketAdvisoryHeading,
                  icon: Icons.info_outline,
                  lines: c.advisories,
                ),
                const SizedBox(height: AmiSpacing.m),
              ],
              _legsBlock(l),
              // CR172 §12 — the payoff diagram sits between the legs and the
              // figures, because it is the thing that makes the figures mean
              // something: max loss and break-even are abstractions until you
              // see the shape they describe. Draws nothing when the server
              // sent no curve (CR040 — an empty axis is a failed chart
              // rendered as an empty one).
              if (_p.payoffCurve.length >= 2) ...[
                const SizedBox(height: AmiSpacing.m),
                OptionPayoffChart(
                  curve: _p.payoffCurve,
                  spot: _p.spot,
                  breakEvens: _p.metrics?.breakEvens ?? const [],
                ),
              ],
              const SizedBox(height: AmiSpacing.m),
              _metricsBlock(l),
              const SizedBox(height: AmiSpacing.m),
              _greeksBlock(l),
              if ((_p.narration ?? '').trim().isNotEmpty) ...[
                const SizedBox(height: AmiSpacing.m),
                Text(
                  l.optionTicketNarrationLabel,
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.textMed, fontSize: 11),
                ),
                const SizedBox(height: AmiSpacing.xs),
                Text(_p.narration!.trim(), style: AmiTypography.body),
              ],
              const SizedBox(height: AmiSpacing.l),
              _decisionRow(l),
            ],
          ),
        ),
      ),
    );
  }

  Widget _header(AppLocalizations l) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.hexagon_outlined,
                color: AmiColors.hexBlue, size: 16),
            const SizedBox(width: AmiSpacing.xs),
            Text(
              l.optionTicketHeading,
              style: AmiTypography.labelMono
                  .copyWith(color: AmiColors.hexBlue, fontSize: 11),
            ),
          ],
        ),
        const SizedBox(height: AmiSpacing.xs),
        Text('${_p.strategyLabel} · ${_p.underlying}', style: AmiTypography.h3),
        const SizedBox(height: AmiSpacing.xs),
        Text(l.optionTicketSubheading, style: AmiTypography.bodySm),
      ],
    );
  }

  Widget _refusalPanel(AppLocalizations l) {
    final c = _p.compliance;
    // CR040 — a refusal whose reasons did not arrive still says something.
    final lines = c.violations.isNotEmpty
        ? c.violations
        : <String>[l.optionTicketRefusedNoReason];
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.hexRed.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexRed),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.block, color: AmiColors.hexRed, size: 16),
              const SizedBox(width: AmiSpacing.xs),
              Text(
                l.optionTicketRefusedHeading,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.hexRed, fontSize: 11),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          for (final line in lines)
            Padding(
              padding: const EdgeInsets.only(bottom: AmiSpacing.xs),
              child: Text(line, style: AmiTypography.body),
            ),
          if ((c.blockedBy ?? '').trim().isNotEmpty)
            Text(
              l.optionTicketBlockedByLabel(c.blockedBy!.toUpperCase()),
              style: AmiTypography.caption.copyWith(color: AmiColors.hexRed),
            ),
        ],
      ),
    );
  }

  Widget _noticePanel({
    required String heading,
    required IconData icon,
    required List<String> lines,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.hexAmber.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexAmber),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: AmiColors.hexAmber, size: 16),
              const SizedBox(width: AmiSpacing.xs),
              Text(
                heading,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.hexAmber, fontSize: 11),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.xs),
          for (final line in lines)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(line, style: AmiTypography.body),
            ),
        ],
      ),
    );
  }

  Widget _legsBlock(AppLocalizations l) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          l.optionTicketLegsLabel,
          style: AmiTypography.labelMono
              .copyWith(color: AmiColors.textMed, fontSize: 11),
        ),
        const SizedBox(height: AmiSpacing.xs),
        for (final leg in _p.legs) _legRow(l, leg),
      ],
    );
  }

  Widget _legRow(AppLocalizations l, OptionProposalLeg leg) {
    final qty = leg.quantity;
    final action =
        leg.isSellToOpen ? l.optionTicketLegSellWord : l.optionTicketLegBuyWord;
    final contracts =
        qty == null ? l.optionTicketNotComputed : _count.format(qty.abs());
    final strike = leg.strike == null
        ? l.optionTicketNotComputed
        : _dollars(leg.strike!);
    return Padding(
      padding: const EdgeInsets.only(bottom: AmiSpacing.xs),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l.optionTicketLegLine(
              action,
              contracts,
              leg.right.toUpperCase(),
              strike,
              leg.expiry,
            ),
            style: AmiTypography.statSmall.copyWith(
              color: leg.isSellToOpen ? AmiColors.hexAmber : AmiColors.textHigh,
            ),
          ),
          Text(
            l.optionTicketLegPremium(
              leg.premium == null
                  ? l.optionTicketNotComputed
                  : _dollars(leg.premium!),
            ),
            style: AmiTypography.caption,
          ),
        ],
      ),
    );
  }

  Widget _metricsBlock(AppLocalizations l) {
    final m = _p.metrics;
    if (m == null) {
      return _absentBlock(l.optionTicketUnpriceable);
    }
    final netLabel = m.netCost == null
        ? l.optionTicketNetCost
        : (m.netCost! < 0 ? l.optionTicketNetCredit : l.optionTicketNetDebit);
    return Column(
      children: [
        _row(l, netLabel, _valueOrAbsent(l, m.netCost)),
        _row(l, l.optionTicketMaxLoss, _maxLossValue(l, m),
            emphasis: m.unboundedLoss ? AmiColors.hexRed : null),
        _row(l, l.optionTicketMaxGain, _maxGainValue(l, m),
            emphasis: m.unboundedGain ? AmiColors.hexGreen : null),
        _row(l, l.optionTicketBreakEven, _breakEvenValue(l, m)),
        // A structure containing an uncovered short call carries NO collateral
        // figure — no cash number bounds an unbounded loss, so the server sends
        // none and this reads "not computed". The refusal panel above is where
        // that gets its explanation; a number invented here would contradict it.
        _row(l, l.optionTicketCollateral, _valueOrAbsent(l, m.collateralRequired),
            sub: (m.sharesLocked ?? 0) > 0
                ? l.optionTicketSharesLocked(_count.format(m.sharesLocked!))
                : null),
        _row(
          l,
          l.optionTicketDaysToExpiry,
          _p.daysToExpiry == null
              ? l.optionTicketNotComputed
              : '${_p.daysToExpiry}',
        ),
      ],
    );
  }

  String _valueOrAbsent(AppLocalizations l, double? v) =>
      v == null ? l.optionTicketNotComputed : _dollars(v);

  String _maxLossValue(AppLocalizations l, OptionProposalMetrics m) {
    if (m.unboundedLoss) return l.optionTicketUnbounded;
    if (m.maxLoss != null) return _dollars(m.maxLoss!);
    if (m.coveredByShares) return l.optionTicketCoveredByShares;
    return l.optionTicketNotComputed;
  }

  String _maxGainValue(AppLocalizations l, OptionProposalMetrics m) {
    if (m.unboundedGain) return l.optionTicketUnbounded;
    if (m.maxGain != null) return _dollars(m.maxGain!);
    return l.optionTicketNotComputed;
  }

  String _breakEvenValue(AppLocalizations l, OptionProposalMetrics m) {
    if (m.breakEvens.isEmpty) return l.optionTicketBreakEvenNone;
    return m.breakEvens.map(_dollars).join(' · ');
  }

  Widget _greeksBlock(AppLocalizations l) {
    final g = _p.greeks;
    if (g == null) {
      final reason = (_p.greeksReason ?? '').trim();
      return _absentBlock(reason.isEmpty
          ? l.optionTicketGreeksNotComputed
          : l.optionTicketGreeksNotComputedReason(reason));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          l.optionTicketGreeksLabel,
          style: AmiTypography.labelMono
              .copyWith(color: AmiColors.textMed, fontSize: 11),
        ),
        const SizedBox(height: AmiSpacing.xs),
        _row(l, l.optionTicketDeltaLabel, _greek(l, g.delta)),
        _row(l, l.optionTicketGammaLabel, _greek(l, g.gamma)),
        _row(l, l.optionTicketThetaLabel, _greek(l, g.thetaPerDay)),
        _row(l, l.optionTicketVegaLabel, _greek(l, g.vegaPerPoint)),
        _row(l, l.optionTicketRhoLabel, _greek(l, g.rhoPerPoint)),
      ],
    );
  }

  String _greek(AppLocalizations l, double? v) =>
      v == null ? l.optionTicketNotComputed : v.toStringAsFixed(4);

  Widget _absentBlock(String message) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate900,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Text(message, style: AmiTypography.bodySm),
    );
  }

  Widget _row(AppLocalizations l, String label, String value,
      {Color? emphasis, String? sub}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  label,
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.textMed, fontSize: 11),
                ),
              ),
              const SizedBox(width: AmiSpacing.s),
              Text(
                value,
                textAlign: TextAlign.right,
                style: AmiTypography.statSmall.copyWith(
                  color: emphasis ?? AmiColors.textHigh,
                  fontWeight: emphasis == null ? null : FontWeight.w700,
                ),
              ),
            ],
          ),
          if (sub != null)
            Align(
              alignment: Alignment.centerRight,
              child: Text(sub, style: AmiTypography.caption),
            ),
        ],
      ),
    );
  }

  Widget _decisionRow(AppLocalizations l) {
    final decline = OutlinedButton(
      style: OutlinedButton.styleFrom(
        foregroundColor: AmiColors.textHigh,
        side: const BorderSide(color: AmiColors.slate600),
        minimumSize: const Size.fromHeight(44),
      ),
      onPressed: () => widget.onDecline(_p),
      child: Text(l.optionTicketDecline,
          style: AmiTypography.labelMono.copyWith(fontSize: 12)),
    );
    // A refused or unpriceable proposal has NO accept control — not a disabled
    // one. A greyed-out YES invites the user to hunt for the setting that
    // re-enables it; there isn't one, and the refusal above already said so.
    if (!_p.canAccept) {
      return SizedBox(width: double.infinity, child: decline);
    }
    return Row(
      children: [
        Expanded(child: decline),
        const SizedBox(width: AmiSpacing.s),
        Expanded(
          flex: 2,
          child: ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AmiColors.hexBlue,
              foregroundColor: Colors.white,
              minimumSize: const Size.fromHeight(44),
            ),
            onPressed: _accept,
            child: Text(
              l.optionTicketAccept,
              style: AmiTypography.labelMono
                  .copyWith(color: Colors.white, fontSize: 12),
            ),
          ),
        ),
      ],
    );
  }
}
