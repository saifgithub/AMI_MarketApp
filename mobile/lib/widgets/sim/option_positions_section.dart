/// CR172 §12 — the option book, on the Portfolio screen.
///
/// This widget is the gate the rest of CR172 was held behind. The backend
/// `Portfolio` schema has carried `options` since §3 and `sim_engine`
/// populates it, but nothing on the client read it — so a user could accept a
/// structure AMI had priced and then find no trace of it on their own
/// portfolio. A position you consented to and cannot see is worse than one you
/// were never offered.
///
/// **Grouped by structure, not listed as legs.** The Room prices a structure
/// and the user says yes to a structure; a vertical spread rendered as two
/// loose rows would show them something they never agreed to, and would invite
/// closing one half of a position whose whole risk profile depends on both.
///
/// **Deliberately shows no profit or loss.** The option marks feed (§11) is not
/// built, so there is no mark and no unrealised figure is computable. The
/// obvious placeholder — `$0.00` — is the one thing that must not appear: it
/// reads as *flat*, which is a measurement, when the truth is *not measured*
/// (DEF059). The card states cost and says the mark is missing instead. When
/// §11 lands, the figure arrives from the server the way `SimShort` already
/// does, and this file gains a row rather than a calculation.
///
/// **Renders nothing when there are no options**, which today is every
/// portfolio — the path is gated on `mandate.compliance.derivatives_allowed`
/// and no current mandate sets it. An empty "OPTION POSITIONS" heading on
/// every portfolio in the app is the placeholder CR040 forbids.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
// `intl` exports its own `TextDirection`, which shadows `dart:ui`'s and makes
// `TextDirection.ltr` an undefined getter.
import 'package:intl/intl.dart' hide TextDirection;

final _money = NumberFormat('#,##0.00');
final _strike = NumberFormat('#,##0.##');
final _expiryFmt = DateFormat('d MMM yyyy');
final _legExpiryFmt = DateFormat('d MMM');

/// How long the structure has left, as a sentence.
///
/// Exported so a test can assert each boundary without building a widget tree.
/// The last two days and the past-expiry case each get their own wording
/// rather than falling through to "{n} days to expiry": "0 days to expiry"
/// reads as though nothing is happening on the one day the user most needs to
/// act, and a negative count would render as literal nonsense on a leg that is
/// genuinely still open awaiting settlement.
String optionExpirySentence(AppLocalizations l, int daysToExpiry) {
  if (daysToExpiry < 0) return l.optionExpiredSettling;
  if (daysToExpiry == 0) return l.optionExpiresToday;
  if (daysToExpiry == 1) return l.optionExpiresTomorrow;
  return l.optionDaysToExpiry('$daysToExpiry');
}

/// One leg's line, e.g. `LONG 1 CALL $195`.
///
/// [dated] appends the leg's own expiry, and the caller passes true only when
/// the structure's legs expire on different dates — otherwise every line in a
/// vertical spread would repeat a date that is already stated once below.
String optionLegLine(AppLocalizations l, SimOptionLeg leg,
    {required bool dated}) {
  final side = leg.isShort ? l.optionSideShort : l.optionSideLong;
  final right = leg.right == 'put' ? l.optionRightPut : l.optionRightCall;
  final contracts = leg.quantity.abs().toStringAsFixed(0);
  final strike = _strike.format(leg.strike);
  return dated
      ? l.optionLegLineDated(
          side, contracts, right, strike, _legExpiryFmt.format(leg.expiry))
      : l.optionLegLine(side, contracts, right, strike);
}

class OptionPositionsSection extends ConsumerWidget {
  const OptionPositionsSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = ref.watch(simNotifierProvider).portfolio;
    if (p == null) return const SizedBox.shrink();
    final structures = p.optionStructures;
    if (structures.isEmpty) return const SizedBox.shrink();
    final l = AppLocalizations.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
          child:
              Text(l.portfolioOptionsHeading, style: AmiTypography.labelMono),
        ),
        for (final s in structures) OptionStructureCard(structure: s),
        // Stated once for the group, not once per card: it is a property of
        // the missing feed, not of any one position.
        Padding(
          padding: const EdgeInsets.only(
              bottom: AmiSpacing.s, left: AmiSpacing.xs, right: AmiSpacing.xs),
          child: Text(
            l.optionMarkUnavailable,
            style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
          ),
        ),
      ],
    );
  }
}

class OptionStructureCard extends StatelessWidget {
  const OptionStructureCard({super.key, required this.structure});

  final SimOptionStructure structure;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final legs = structure.legs;
    // Only date the individual legs when they actually differ — a calendar
    // spread needs it, a vertical would just repeat itself.
    final expiries = legs.map((x) => x.expiry).toSet();
    final dated = expiries.length > 1;
    final expired = structure.isExpired;
    final dte = structure.daysToExpiry;
    // Amber inside the last two sessions, red once it is past expiry and
    // still on the book. Everything else is the ordinary slate border: an
    // option with a month left is not a warning.
    final Color borderColor;
    if (expired) {
      borderColor = AmiColors.hexRed;
    } else if (dte <= 1) {
      borderColor = AmiColors.hexAmber;
    } else {
      borderColor = AmiColors.slate700;
    }
    final net = structure.netCostBasis;
    final collateral = structure.collateralPosted;

    return Container(
      margin: const EdgeInsets.only(bottom: AmiSpacing.s),
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(structure.underlying,
                    style: AmiTypography.dataMd),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: AmiColors.slate600),
                ),
                child: Text(
                  // The server's own strategy name, uppercased and
                  // de-underscored — never a label this file invents, so a
                  // strategy added backend-side cannot render as blank.
                  structure.strategyName
                      .replaceAll('_', ' ')
                      .toUpperCase(),
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.textMed),
                ),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.xs),
          for (final leg in legs)
            Padding(
              padding: const EdgeInsets.only(bottom: 2),
              child: Text(
                optionLegLine(l, leg, dated: dated),
                style: AmiTypography.statSmall.copyWith(
                  color: leg.isShort ? AmiColors.hexRed : AmiColors.textHigh,
                ),
              ),
            ),
          const SizedBox(height: AmiSpacing.xs),
          Text(
            optionExpirySentence(l, dte),
            style: AmiTypography.caption.copyWith(
              color: expired
                  ? AmiColors.hexRed
                  : (dte <= 1 ? AmiColors.hexAmber : AmiColors.textLow),
            ),
          ),
          if (!dated)
            Text(
              _expiryFmt.format(legs.first.expiry),
              style:
                  AmiTypography.caption.copyWith(color: AmiColors.textLow),
            ),
          const SizedBox(height: AmiSpacing.xs),
          Text(
            // A debit is what it cost; a credit is cash received against an
            // obligation still outstanding. Two different facts, two
            // different sentences.
            net >= 0
                ? l.optionPaidAtOpen(_money.format(net))
                : l.optionCollectedAtOpen(_money.format(net.abs())),
            style: AmiTypography.statSmall.copyWith(color: AmiColors.textMed),
          ),
          if (collateral > 0)
            Text(
              l.optionCollateralHeld(_money.format(collateral)),
              style:
                  AmiTypography.caption.copyWith(color: AmiColors.textLow),
            ),
        ],
      ),
    );
  }
}
