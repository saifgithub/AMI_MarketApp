/// CR173 — the consensus strip and the named dissent, adopted from the KIMI
/// lane: *the team as evidence before the team as people.*
///
/// The Verdict Board already draws eleven hexes in three bands, which answers
/// "who thought what" for someone willing to read a comb. This answers the
/// prior question — *was this close?* — in one line, and then names the single
/// most useful thing the comb buries: **who disagreed with the call that was
/// made**, in their own words.
///
/// Pure, and computed from `RoomBoardData` alone. No new field, no new event.
///
/// **What it refuses to say**, because each of these would be a confident
/// answer to a question nobody asked:
///
///  - Nothing at all when no stance was recorded. A run that predates CR106 B2
///    has eleven null stances; `0–0` would read as "nobody had a view" rather
///    than "we did not write this down" (T-SUM11's cousin).
///  - No dissent line on a NO_VERDICT or an outcome this build does not
///    recognise. NO_VERDICT is the PM refusing to price a trade without a
///    market read — a professional refusal is not a position, so nothing can
///    dissent from it, and an unknown token is not a position we can reason
///    about at all (DEF210).
///  - No dissent line when nobody dissented. "Unanimous" is a real finding and
///    gets said; an empty line where a name should be is a rendering fault.
library;

import 'package:ami_trade/models/room_board.dart';

/// How strongly a dissenter held the view, when they said. Ordered so the
/// loudest objection is the one that gets named.
const Map<String, int> _convictionRank = {'high': 3, 'medium': 2, 'low': 1};

class RoomConsensus {
  const RoomConsensus({
    required this.withCall,
    required this.againstCall,
    required this.neutral,
    required this.dissenter,
    required this.dissentApplies,
  });

  /// Voices on the same side as the PM's call.
  final int withCall;

  /// Voices on the opposite side.
  final int againstCall;

  final int neutral;

  /// The dissenting voice worth naming — highest conviction, then first in
  /// speaking order. Null when nobody dissented, or when [dissentApplies] is
  /// false.
  final RoomVoice? dissenter;

  /// Whether "dissent" is a meaningful idea for this outcome at all. False for
  /// NO_VERDICT and for an action token this build does not know.
  final bool dissentApplies;

  bool get unanimous => dissentApplies && againstCall == 0;

  int get stated => withCall + againstCall + neutral;
}

/// Null when there is nothing honest to say — the caller renders no strip.
RoomConsensus? consensusFor(RoomBoardData data) {
  if (!data.stancesRecorded) return null;

  final forVoices = data.voicesFor;
  final againstVoices = data.voicesAgainst;
  if (forVoices.isEmpty && againstVoices.isEmpty) return null;

  // Which side of the comb agrees with the call the PM actually made. An
  // APPROVE is acting on the idea, so `for` is with it; a REJECT is declining
  // it, so `against` is. A PASS is "not now" — declining to act — and a voice
  // arguing FOR the trade is genuinely dissenting from that.
  final bool? approveSide = switch (data.outcome) {
    VerdictOutcome.approve => true,
    VerdictOutcome.reject => false,
    VerdictOutcome.pass => false,
    // The PM refused to rule, or the token is one we do not recognise. Report
    // the split, name nobody.
    VerdictOutcome.noVerdict => null,
    VerdictOutcome.unknown => null,
    VerdictOutcome.noResult => null,
  };

  final applies = approveSide != null;
  final with_ = approveSide == false ? againstVoices : forVoices;
  final against = approveSide == false ? forVoices : againstVoices;

  RoomVoice? dissenter;
  if (applies && against.isNotEmpty) {
    final ranked = [...against]..sort((a, b) =>
        (_convictionRank[b.conviction] ?? 0)
            .compareTo(_convictionRank[a.conviction] ?? 0));
    dissenter = ranked.first;
  }

  return RoomConsensus(
    withCall: with_.length,
    againstCall: against.length,
    neutral: data.voicesNeutral.length,
    dissenter: dissenter,
    dissentApplies: applies,
  );
}
