/// CR260 / CR267 WP-21b — "How the Street rates it": the Room's call set beside
/// the sell-side analyst consensus, on the Verdict Board.
///
/// The Room decides blind (CR275); the backend computes this comparison AFTER
/// the verdict and the card only displays it. Three refusals shape it:
///
///  1. No usable Street rating means the card says so ("No Street rating
///     available for this run.") — never an empty or zero rating, count or
///     target dressed up as a reading.
///  2. The source label the backend sent is always visible, verbatim, so the
///     user can see where the figure comes from. A missing label is shown as
///     missing, not hidden.
///  3. Wording is educational: it states whether the two agree and, where they
///     differ, that a reasoned pass on a Street-Buy name is a legitimate call.
///     It never tells the user what to do.
///
/// Whether the card appears at all is the user's setting
/// (`streetComparisonEnabledProvider`); `RoomBoard` applies it.
library;

import 'package:ami_trade/features/markets/market.dart';
import 'package:ami_trade/features/markets/money.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class RoomStreetCard extends StatelessWidget {
  const RoomStreetCard({
    super.key,
    required this.comparison,
    required this.roomCallLabel,
    required this.ticker,
  });

  /// CR282 - the stock the street target belongs to; its market sets the
  /// currency the target is printed in.
  final String ticker;

  final StreetComparison comparison;

  /// The Room's own verdict heading ("THE ROOM APPROVED"), already localised.
  final String roomCallLabel;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final c = comparison;
    final caution = c.isAvailable && c.approvedAgainstStreetSell;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(
            color: caution ? AmiColors.hexAmber : AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l.roomStreetHeading,
            style: AmiTypography.labelMono
                .copyWith(fontSize: 10, color: AmiColors.textLow),
          ),
          const SizedBox(height: AmiSpacing.xs),
          if (!c.isAvailable)
            Text(l.roomStreetUnavailable, style: AmiTypography.caption)
          else ...[
            _StreetRow(
              label: l.roomStreetRatingLabel,
              value: _ratingLabel(l, c.streetRating),
            ),
            if (c.analystCount != null)
              _StreetRow(
                label: l.roomStreetAnalystsLabel,
                value: '${c.analystCount}',
                lockLtr: true,
              ),
            if (c.targetMean != null)
              _StreetRow(
                label: l.roomStreetMeanTargetLabel,
                value: formatMoney(c.targetMean!,
                    market: marketForTicker(ticker), grouped: false),
                lockLtr: true,
              ),
            _StreetRow(label: l.roomStreetRoomCallLabel, value: roomCallLabel),
            const SizedBox(height: AmiSpacing.xs),
            Text(
              _statusLine(l, c),
              style: AmiTypography.caption.copyWith(
                  color: caution ? AmiColors.hexAmber : AmiColors.textHigh),
            ),
          ],
          const SizedBox(height: AmiSpacing.xs),
          Text(
            c.sourceLabel.isEmpty
                ? l.roomStreetSourceUnknown
                : l.roomStreetSource(c.sourceLabel),
            style: AmiTypography.labelMono
                .copyWith(fontSize: 9, color: AmiColors.textLow),
          ),
          if (c.asOf != null && c.asOf!.isNotEmpty)
            Text(
              l.roomStreetAsOf(c.asOf!),
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 9, color: AmiColors.textLow),
            ),
        ],
      ),
    );
  }
}

String _ratingLabel(AppLocalizations l, String? rating) {
  switch (rating) {
    case 'strong buy':
      return l.roomStreetRatingStrongBuy;
    case 'buy':
      return l.roomStreetRatingBuy;
    case 'hold':
      return l.roomStreetRatingHold;
    case 'underperform':
      return l.roomStreetRatingUnderperform;
    case 'sell':
      return l.roomStreetRatingSell;
    case 'strong sell':
      return l.roomStreetRatingStrongSell;
    default:
      // The feed's own word, verbatim: better than a wrong translation.
      return rating ?? '';
  }
}

String _statusLine(AppLocalizations l, StreetComparison c) {
  if (c.agreement == 'agree') return l.roomStreetAgree;
  if (c.agreement == 'differ') {
    if (c.approvedAgainstStreetSell) return l.roomStreetDifferApprovedSell;
    if (c.streetStance == 'buy') return l.roomStreetDifferDeclined;
    return l.roomStreetDifferGeneric;
  }
  return l.roomStreetNotComparable;
}

class _StreetRow extends StatelessWidget {
  const _StreetRow({
    required this.label,
    required this.value,
    this.lockLtr = false,
  });
  final String label;
  final String value;

  /// Numbers keep their order under RTL (T-BIDI).
  final bool lockLtr;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 11, color: AmiColors.textLow),
            ),
          ),
          Text(
            value,
            style: AmiTypography.statSmall.copyWith(color: AmiColors.textHigh),
            textDirection: lockLtr ? TextDirection.ltr : null,
          ),
        ],
      ),
    );
  }
}
