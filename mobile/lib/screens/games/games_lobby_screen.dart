/// CR109 slice 6 — the cadence lobby: the five games, and which ones you're
/// already in.
///
/// Saiful, playing the shipped build: *"How do I join the monthly, quarterly,
/// etc games?"* You couldn't — the backend supported one cadence and the home
/// screen's fallback card picked the weekly entry out of the list and ignored
/// whatever else arrived. Both halves are fixed; this is the surface.
///
/// The rule the screen has to carry is §4.1: **one live run per cadence,
/// never two of a kind.** It reads as a UI limit and is not one — career
/// points pay +100 for a win and only −40 for a loss, so two parallel entries
/// in the *same* cadence are strictly +EV and the optimal play would be to
/// stack a dozen annual runs and let the best one place. The player does not
/// need that reasoning, only the rule, so the copy states the rule and the
/// ENTER action is simply absent on a cadence already held.
///
/// Each row also carries what the cadence is *worth* (§6.3's gain weight).
/// A quarterly run is thirteen weeks of attention; showing that it pays 13×
/// a weekly win is the difference between an informed commitment and a
/// surprise. The loss side is deliberately not shown here — it is √13, the
/// asymmetry is in the player's favour, and a risk figure at the moment of
/// choice reads as a warning about a decision that carries no real downside.
///
/// Unreachable in a store build — under the `/games` subtree, const-folded
/// out without `--dart-define=AMI_GAMES=true`.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_entry_sheet.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

final _dayMonth = DateFormat('d MMM');

/// §6.3's gain weights, for display only. The scoring itself lives on the
/// server — this is the same table rendered, not a second source of truth,
/// and a cadence missing from it simply shows no weight line rather than
/// inventing one.
const _gainWeight = <String, String>{
  'month': '4',
  'quarter': '13',
  'half': '26',
  'year': '52',
};

class GamesLobbyScreen extends ConsumerWidget {
  const GamesLobbyScreen({super.key});

  static Future<void> push(BuildContext context) {
    return Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const GamesLobbyScreen()),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final cadencesAsync = ref.watch(gamesCadencesProvider);

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(title: Text(l.gamesLobbyTitle)),
      body: SafeArea(
        child: cadencesAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (_, __) => Center(
            child: Padding(
              padding: const EdgeInsets.all(AmiSpacing.l),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(l.gamesLoadError,
                      style: AmiTypography.body, textAlign: TextAlign.center),
                  const SizedBox(height: AmiSpacing.m),
                  HexButton(
                    label: l.gamesRetry.toUpperCase(),
                    onPressed: () => ref.invalidate(gamesCadencesProvider),
                  ),
                ],
              ),
            ),
          ),
          data: (cadences) => RefreshIndicator(
            onRefresh: () async => ref.invalidate(gamesCadencesProvider),
            child: ListView(
              padding: const EdgeInsets.all(AmiSpacing.m),
              children: [
                Text(l.gamesLobbyIntro, style: AmiTypography.caption),
                const SizedBox(height: AmiSpacing.m),
                ...cadences.map((c) => _CadenceCard(info: c)),
                const SizedBox(height: AmiSpacing.l),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

String cadenceLabel(AppLocalizations l, String cadence) {
  switch (cadence) {
    case 'month':
      return l.gamesCadenceMonth;
    case 'quarter':
      return l.gamesCadenceQuarter;
    case 'half':
      return l.gamesCadenceHalf;
    case 'year':
      return l.gamesCadenceYear;
    case 'week':
      return l.gamesCadenceWeek;
    default:
      // A cadence this build does not know about renders under its own wire
      // name rather than being dropped — an unknown game the server offers is
      // a shipping-lag problem, not a reason to hide it.
      return cadence.toUpperCase();
  }
}

class _CadenceCard extends StatelessWidget {
  const _CadenceCard({required this.info});
  final GameCadenceInfo info;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final field = info.nextField;
    final isOpen = info.entryState == 'entry_open' ||
        info.entryState == 'announced';
    final weight = _gainWeight[info.cadence];

    return Container(
      margin: const EdgeInsets.only(bottom: AmiSpacing.m),
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(
          color: info.alreadyHolds
              ? AmiColors.hexGreen.withValues(alpha: 0.4)
              : AmiColors.slate700,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  cadenceLabel(l, info.cadence),
                  style: AmiTypography.h4.copyWith(color: AmiColors.textHigh),
                ),
              ),
              if (info.alreadyHolds)
                HexChip(
                  label: l.gamesCadenceYoureIn,
                  color: AmiColors.hexGreen,
                  variant: HexChipVariant.tinted,
                ),
            ],
          ),
          if (field?.startsOn != null && field?.endsOn != null) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(
              l.gamesCadenceRuns(
                _dayMonth.format(field!.startsOn!),
                _dayMonth.format(field.endsOn!),
              ),
              style: AmiTypography.caption,
            ),
          ],
          if (weight != null) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(l.gamesCadenceWeightNote(weight),
                style: AmiTypography.caption),
          ],
          if (info.queueCount > 0) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(l.gamesFieldEntrantCount(info.queueCount),
                style: AmiTypography.caption),
          ],
          const SizedBox(height: AmiSpacing.m),
          if (info.alreadyHolds)
            // No action, and no disabled button either: §4.1 means there is
            // nothing to do here, and a greyed-out CTA invites tapping at it.
            const SizedBox.shrink()
          else if (!isOpen)
            Text(l.gamesCadenceEntryClosed, style: AmiTypography.caption)
          else
            SizedBox(
              width: double.infinity,
              child: HexButton(
                // NOT `gamesEnterCta` — that string reads "enter this
                // week's field", which is wrong copy on a Monthly or
                // Quarterly row.
                label: l.gamesLobbyEnterCta,
                color: AmiColors.hexGreen,
                onPressed: () =>
                    GamesEntrySheet.show(context, cadence: info.cadence),
              ),
            ),
        ],
      ),
    );
  }
}
