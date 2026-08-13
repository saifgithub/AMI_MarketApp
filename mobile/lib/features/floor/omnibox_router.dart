/// CR173 slice 2 — where the omnibox sends you, decided here and nowhere else.
///
/// One box replaces the Floor's two entry points (the Concierge hex and the
/// CONVENE sheet). What the box does with your text is therefore a routing
/// decision, and §4 fixes how it is made: **deterministically, on the client,
/// with no LLM in the path.**
///
/// That is not a performance choice. CR038 measured agents ignoring an emphatic
/// instruction ~70% of the time; a model asked "is this a ticker?" is a control
/// that fails silently and differently every run, on the first thing a user
/// touches. A regex is boring, auditable, and wrong in exactly one predictable
/// way — which the surface then shows the user *before* they commit, because
/// the CTA renames itself to match the route ([OmniboxRoute.convene] →
/// CONVENE THE ROOM, [OmniboxRoute.concierge] → ASK AMI). Deterministic and
/// visible beats clever and hidden.
///
/// **Tap-first** (§5): an empty box is not an error. CONVENE on empty opens the
/// ticker picker, so typing is the accelerant and never the toll.
library;

/// US equities at MVP (D-002): 1–5 ASCII letters. Deliberately not a
/// known-symbol list — the app carries no such list, and inventing one here
/// would reject valid tickers it had never heard of, which is worse than
/// convening on a word.
final _tickerShape = RegExp(r'^[A-Za-z]{1,5}$');

enum OmniboxRoute {
  /// Ticker-shaped: arm the Room.
  convene,

  /// Anything else: the Concierge, carrying the text as the first message.
  /// D-015 holds — the Concierge routes analysis to the firm, never answers it.
  concierge,

  /// Nothing typed: the ticker picker, not a refusal.
  picker,
}

class OmniboxDecision {
  const OmniboxDecision(this.route, {this.ticker, this.text});

  final OmniboxRoute route;

  /// Set only on [OmniboxRoute.convene], always upper-case — the rest of the
  /// app keys on upper-case tickers, and normalising at the boundary means no
  /// call site has to remember to.
  final String? ticker;

  /// Set only on [OmniboxRoute.concierge]: the user's text, trimmed, exactly
  /// as they typed it otherwise.
  final String? text;
}

OmniboxDecision routeOmnibox(String raw) {
  // A leading `$` is how half the internet writes a ticker, and dropping it is
  // the difference between convening on AAPL and asking AMI about "$AAPL".
  final trimmed = raw.trim().replaceFirst(RegExp(r'^\$'), '').trim();
  if (trimmed.isEmpty) return const OmniboxDecision(OmniboxRoute.picker);
  if (_tickerShape.hasMatch(trimmed)) {
    return OmniboxDecision(OmniboxRoute.convene,
        ticker: trimmed.toUpperCase());
  }
  // Note the fall-through: `HI` is ticker-shaped and will arm CONVENE. That is
  // the one predictable wrong answer, and it is why the CTA renames itself —
  // the user reads "CONVENE THE ROOM · HI" and corrects it, rather than
  // discovering the mistake after spending a credit.
  return OmniboxDecision(OmniboxRoute.concierge, text: raw.trim());
}
