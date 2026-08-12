/// CR109 slice 8 — one progress marker rendered as one sentence (design
/// §8.4).
///
/// > *"If one player in 26 receives something, twenty-five received nothing,
/// > and that is the churn."*
///
/// The kind and its number are decided server-side; this file only chooses
/// the sentence, because that choice is a translation concern. Two rules ride
/// in the copy and are worth stating where the copy lives:
///
///   * **Evidence of movement, never a participation trophy.** Every line
///     names a threshold that was crossed. A close that crossed none gets no
///     line at all rather than a consolation.
///   * **Never a scold.** §10.4's rule over every mirror in the game applies
///     here too — a marker states what happened and stops.
///
/// An unrecognised kind renders nothing. A build that does not know a marker
/// the server has started sending must stay silent rather than print a raw
/// enum at the player.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';

const _markerFirstFinish = 'first_finish';
const _markerFirstPositive = 'first_positive';
const _markerFirstPodium = 'first_podium';
const _markerPersonalBest = 'personal_best_twr';
const _markerCleanStreak = 'clean_streak';

String _signedPct(num v) =>
    '${v >= 0 ? '+' : ''}${v.toDouble().toStringAsFixed(2)}%';

String _ordinal(int rank) {
  if (rank % 100 >= 11 && rank % 100 <= 13) return '${rank}th';
  switch (rank % 10) {
    case 1:
      return '${rank}st';
    case 2:
      return '${rank}nd';
    case 3:
      return '${rank}rd';
    default:
      return '${rank}th';
  }
}

/// The sentence for [marker], or an empty string when this build has no copy
/// for its kind.
String markerLine(AppLocalizations l, GameMarker marker) {
  final value = marker.value;
  switch (marker.kind) {
    case _markerFirstFinish:
      return l.gamesMarkerFirstFinish;
    case _markerFirstPositive:
      return value == null
          ? l.gamesMarkerFirstFinish
          : l.gamesMarkerFirstPositive(_signedPct(value));
    case _markerFirstPodium:
      return value == null ? '' : l.gamesMarkerFirstPodium(_ordinal(value.toInt()));
    case _markerPersonalBest:
      return value == null ? '' : l.gamesMarkerPersonalBest(_signedPct(value));
    case _markerCleanStreak:
      return value == null ? '' : l.gamesMarkerCleanStreak(value.toInt());
    default:
      return '';
  }
}
