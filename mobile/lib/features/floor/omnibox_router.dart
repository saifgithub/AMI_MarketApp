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
///
/// **CR283 — names, with Bursa on.** Shape cannot tell "CIMB" the Malaysian bank
/// from a US ticker "CIMB", so with Bursa on a word is resolved against both
/// markets by the backend ([lookupName]) before it is routed. [routeOmnibox]
/// itself stays pure and synchronous and is untouched for the Bursa-off build,
/// which never reaches [lookupName] at all.
library;

import '../../models/tickers.dart';
import '../markets/bursa_flag.dart';
import '../markets/market.dart';

/// US equities at MVP (D-002): 1–5 ASCII letters. Deliberately not a
/// known-symbol list — the app carries no such list, and inventing one here
/// would reject valid tickers it had never heard of, which is worse than
/// convening on a word.
final _tickerShape = RegExp(r'^[A-Za-z]{1,5}$');

/// CR282: a Bursa code - four digits, optionally one trailing letter, with or
/// without the `.KL` suffix. Only consulted when Bursa is switched on.
final _bursaShape = RegExp(r'^[0-9]{4,5}[A-Za-z]?(\.[Kk][Ll])?$');

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

OmniboxDecision routeOmnibox(String raw, {bool bursaEnabled = kBursaEnabled}) {
  // A leading `$` is how half the internet writes a ticker, and dropping it is
  // the difference between convening on AAPL and asking AMI about "$AAPL".
  final trimmed = raw.trim().replaceFirst(RegExp(r'^\$'), '').trim();
  if (trimmed.isEmpty) return const OmniboxDecision(OmniboxRoute.picker);
  if (_tickerShape.hasMatch(trimmed)) {
    return OmniboxDecision(OmniboxRoute.convene,
        ticker: trimmed.toUpperCase());
  }
  if (bursaEnabled && _bursaShape.hasMatch(trimmed)) {
    final upper = trimmed.toUpperCase();
    return OmniboxDecision(OmniboxRoute.convene,
        ticker: upper.endsWith('.KL') ? upper : '$upper.KL');
  }
  // Note the fall-through: `HI` is ticker-shaped and will arm CONVENE. That is
  // the one predictable wrong answer, and it is why the CTA renames itself —
  // the user reads "CONVENE THE ROOM · HI" and corrects it, rather than
  // discovering the mistake after spending a credit.
  return OmniboxDecision(OmniboxRoute.concierge, text: raw.trim());
}

/// CR283: ask the backend for the candidates on one market. Throws when the
/// lookup is unavailable; an empty list means it answered and nothing matched.
typedef TickerResolver = Future<List<ResolvedTicker>> Function(
    String query, AppMarket market);

/// What the box may treat as a company name: a short phrase of letters (no
/// digits - a Bursa code is routed by [routeOmnibox] and never resolved). A
/// sentence for the Concierge is longer than this, and one that slips under it
/// resolves to nothing and falls through to the Concierge anyway.
final _nameShape = RegExp(r"^[A-Za-z][A-Za-z .&'\-]{0,29}$");

bool isNameQuery(String raw) {
  final t = raw.trim().replaceFirst(RegExp(r'^\$'), '').trim();
  if (!_nameShape.hasMatch(t)) return false;
  return t.split(RegExp(r'\s+')).length <= 3;
}

enum NameLookupKind {
  /// Exactly one market matched: [NameLookup.candidates] holds its top hit.
  single,

  /// Both markets matched: [NameLookup.candidates] is the top hit of each,
  /// the active market first. Never a silent pick.
  choice,

  /// The lookup answered and neither market matched.
  none,

  /// A market's lookup failed, so a match on the other proves nothing.
  down,
}

class NameLookup {
  const NameLookup(this.kind, [this.candidates = const []]);

  final NameLookupKind kind;
  final List<ResolvedTicker> candidates;
}

/// Resolve [query] against both markets. Any failed leg is [NameLookupKind.down]
/// - one market matching while the other is unreachable is not "only one
/// matches".
Future<NameLookup> lookupName(
  String query, {
  required AppMarket active,
  required TickerResolver resolve,
}) async {
  final order = [active, active == AppMarket.my ? AppMarket.us : AppMarket.my];
  final legs = await Future.wait(order.map((m) async {
    try {
      return await resolve(query.trim(), m);
    } catch (_) {
      return null;
    }
  }));
  if (legs.any((l) => l == null)) return const NameLookup(NameLookupKind.down);
  final tops = [
    for (final l in legs)
      if (l!.isNotEmpty) l.first,
  ];
  return switch (tops.length) {
    0 => const NameLookup(NameLookupKind.none),
    1 => NameLookup(NameLookupKind.single, tops),
    _ => NameLookup(NameLookupKind.choice, tops),
  };
}

/// The CTA's ticker argument: a Bursa hit names the company and its code
/// ("CIMB · 1023"), a US hit is its ticker.
String resolvedLabel(ResolvedTicker c) {
  if (marketForTicker(c.ticker) == AppMarket.my) {
    final code = c.ticker.toUpperCase().replaceAll('.KL', '');
    return '${c.shortName.toUpperCase()} · $code';
  }
  return c.ticker.toUpperCase();
}
