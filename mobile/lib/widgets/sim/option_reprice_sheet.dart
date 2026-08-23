/// CR172 — the step between "yes" and the position.
///
/// The user has read a structure AMI costed and tapped accept. Before anything
/// opens, the app asks the server what it costs *now* and shows the difference.
/// Saiful's ruling on the consent flow (2026-08-23): *the verdict carries the
/// full structure the Room priced, and on accept the app re-prices live and
/// shows what moved before opening.*
///
/// **This is DEF305 stated as a product requirement.** That defect was a
/// position force-closed off a price nobody checked. The same shape here would
/// be a structure opened at a figure the user last saw four minutes and one
/// market move ago — and unlike a share, an option's premium can move a
/// double-digit percentage in that window while the underlying barely twitches.
/// A ticket that fills at the proposal's price would be showing the user a
/// number and charging them a different one.
///
/// **The sheet computes nothing.** Every figure, including every delta, arrives
/// from `POST /v1/sim/options/reprice` already computed. This file formats and
/// lays out; it does not subtract. That is the same fence
/// [OptionProposalTicket] holds, for the same reason — a client that derives a
/// max loss can be confidently wrong about the worst case (DEF059) — and it
/// extends to the drift because a wrong delta is a wrong story about why the
/// price changed.
///
/// **Three terminal states, deliberately distinct:**
///
///   * **priced, unchanged** — heading says so plainly rather than hiding the
///     step. A confirmation the user did not need still tells them the app
///     checked, which is what makes the checks they *do* need credible.
///   * **priced, moved** — the drift table, then the confirm.
///   * **could not price** / **floor now refuses** — no confirm button exists
///     at all. These are two different sentences and get two different
///     headings: "we cannot price this" is about the chain, "you may not open
///     this" is about the mandate, and collapsing them would teach the user
///     that a refusal is a glitch.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/option_reprice.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart' hide TextDirection;

final _money = NumberFormat('#,##0.00');

String _dollars(double v) => '${v < 0 ? '−' : ''}\$${_money.format(v.abs())}';

/// A signed change, always carrying its sign — `+$12.00`, `−$3.40`.
///
/// The plus is not decoration: on a net debit an increase costs the user more,
/// and a bare `12.00` beside a `−3.40` reads as a magnitude rather than a
/// direction.
String _signed(double v) =>
    '${v < 0 ? '−' : '+'}\$${_money.format(v.abs())}';

class OptionRepriceSheet extends StatelessWidget {
  const OptionRepriceSheet({
    super.key,
    required this.result,
    required this.ticker,
  });

  final OptionRepriceResult result;
  final String ticker;

  /// Presents the sheet. Resolves `true` only when the user confirmed against
  /// figures they were shown; `false` or `null` otherwise.
  ///
  /// `isDismissible: false` on the confirmable state would be the obvious
  /// instinct and is wrong — a user who wants out of a money-moving flow must
  /// always be able to leave, and a dismissal resolving `null` is already
  /// treated as "did not consent" by the caller.
  static Future<bool?> show(
    BuildContext context,
    OptionRepriceResult result, {
    required String ticker,
  }) {
    return showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => OptionRepriceSheet(result: result, ticker: ticker),
    );
  }

  bool get _canOpen =>
      result.repriced &&
      result.structure != null &&
      result.compliance.passed &&
      result.structure!.metrics != null;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final drift = result.drift;
    final moved = drift?.hasMoved ?? false;

    return Container(
      decoration: const BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.vertical(top: Radius.circular(AmiRadii.card)),
      ),
      padding: const EdgeInsets.fromLTRB(
        AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, AmiSpacing.l,
      ),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                _heading(l, moved),
                style: AmiTypography.labelMono.copyWith(
                  color: _canOpen ? AmiColors.hexCyan : AmiColors.hexAmber,
                  fontWeight: FontWeight.w700,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AmiSpacing.s),
              if (_canOpen) ...[
                Text(
                  l.optionRepriceSubheading,
                  style: AmiTypography.caption
                      .copyWith(color: AmiColors.textMed),
                  textAlign: TextAlign.center,
                ),
                if (drift != null) ...[
                  const SizedBox(height: AmiSpacing.m),
                  _DriftTable(drift: drift, ticker: ticker),
                  if (drift.agedSeconds != null) ...[
                    const SizedBox(height: AmiSpacing.s),
                    Text(
                      l.optionRepriceAged(_age(l, drift.agedSeconds!)),
                      style: AmiTypography.caption
                          .copyWith(color: AmiColors.textLow),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ],
                const SizedBox(height: AmiSpacing.l),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AmiColors.hexCyan,
                    foregroundColor: AmiColors.slate900,
                    padding:
                        const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
                  ),
                  onPressed: () => Navigator.of(context).pop(true),
                  child: Text(l.optionRepriceConfirmCta),
                ),
                const SizedBox(height: AmiSpacing.s),
                TextButton(
                  style: TextButton.styleFrom(
                      foregroundColor: AmiColors.textMed),
                  onPressed: () => Navigator.of(context).pop(false),
                  child: Text(l.optionRepriceCancelCta),
                ),
              ] else ...[
                Text(
                  l.optionRepriceFailedBody,
                  style: AmiTypography.body.copyWith(color: AmiColors.textMed),
                  textAlign: TextAlign.center,
                ),
                ..._reasons(),
                const SizedBox(height: AmiSpacing.l),
                OutlinedButton(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AmiColors.textMed,
                    side: const BorderSide(color: AmiColors.slate600),
                    padding:
                        const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
                  ),
                  onPressed: () => Navigator.of(context).pop(false),
                  child: Text(l.optionRepriceCancelCta),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  String _heading(AppLocalizations l, bool moved) {
    if (!result.repriced || result.structure == null) {
      return l.optionRepriceFailedHeading;
    }
    if (!result.compliance.passed) return l.optionRepriceRefusedHeading;
    return moved ? l.optionRepriceHeading : l.optionRepriceHeadingUnchanged;
  }

  /// The server's own sentences, verbatim. Violations and could-not-check both
  /// render — the ticket keeps them apart by colour and heading, and here the
  /// sheet is already headed by which case it is, so they read as one list of
  /// reasons rather than two panels the user must reconcile.
  List<Widget> _reasons() {
    final lines = [
      ...result.compliance.violations,
      ...result.compliance.notEvaluated,
    ].where((s) => s.trim().isNotEmpty).toList();
    if (lines.isEmpty) return const [];
    return [
      const SizedBox(height: AmiSpacing.m),
      for (final line in lines)
        Padding(
          padding: const EdgeInsets.only(bottom: AmiSpacing.xs),
          child: Text(
            line,
            style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber),
            textAlign: TextAlign.center,
          ),
        ),
    ];
  }

  /// Whole minutes once past a minute, whole seconds below it.
  ///
  /// Deliberately coarse. "4 minutes" is the fact that matters — that the price
  /// had aged — and `4m 12.6s` invites the reader to treat the precision as
  /// meaningful when the underlying figure is a round-trip latency away from
  /// exact anyway.
  String _age(AppLocalizations l, double seconds) {
    if (seconds >= 60) {
      return l.optionRepriceAgeMinutes((seconds / 60).round());
    }
    return l.optionRepriceAgeSeconds(seconds.round());
  }
}

/// then / now, per figure. A row is drawn only for a figure whose baseline the
/// server could state — an unknown "then" is not a zero change.
class _DriftTable extends StatelessWidget {
  const _DriftTable({required this.drift, required this.ticker});

  final OptionPriceDrift drift;
  final String ticker;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final rows = <Widget>[];

    if (drift.spotThen != null && drift.spotNow != null) {
      rows.add(_row(
        l.optionRepriceSpotLabel(ticker),
        _dollars(drift.spotThen!),
        _dollars(drift.spotNow!),
        drift.spotChange,
      ));
    }
    if (drift.netCostThen != null) {
      rows.add(_row(
        drift.netCostNow < 0
            ? l.optionTicketNetCredit
            : l.optionTicketNetDebit,
        _dollars(drift.netCostThen!),
        _dollars(drift.netCostNow),
        drift.netCostChange,
      ));
    }
    if (drift.maxLossThen != null && drift.maxLossNow != null) {
      rows.add(_row(
        l.optionTicketMaxLoss,
        _dollars(drift.maxLossThen!),
        _dollars(drift.maxLossNow!),
        null,
      ));
    }
    if (rows.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            const Spacer(),
            Expanded(
              flex: 2,
              child: Text(
                l.optionRepriceThen,
                textAlign: TextAlign.right,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.textLow, fontSize: 10),
              ),
            ),
            Expanded(
              flex: 2,
              child: Text(
                l.optionRepriceNow,
                textAlign: TextAlign.right,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.hexCyan, fontSize: 10),
              ),
            ),
          ],
        ),
        const SizedBox(height: AmiSpacing.xs),
        ...rows,
      ],
    );
  }

  Widget _row(String label, String then, String now, double? change) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AmiSpacing.xs),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: AmiTypography.labelMono
                  .copyWith(color: AmiColors.textMed, fontSize: 11),
            ),
          ),
          Expanded(
            flex: 2,
            child: Text(
              then,
              textAlign: TextAlign.right,
              style: AmiTypography.dataMd.copyWith(
                color: AmiColors.textLow,
                decoration: change != null && change.abs() >= 0.005
                    ? TextDecoration.lineThrough
                    : null,
              ),
            ),
          ),
          Expanded(
            flex: 2,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  now,
                  textAlign: TextAlign.right,
                  style: AmiTypography.dataMd
                      .copyWith(color: AmiColors.textHigh),
                ),
                if (change != null && change.abs() >= 0.005)
                  Text(
                    _signed(change),
                    textAlign: TextAlign.right,
                    style: AmiTypography.caption.copyWith(
                      color: change > 0
                          ? AmiColors.hexAmber
                          : AmiColors.hexGreen,
                      fontSize: 10,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
