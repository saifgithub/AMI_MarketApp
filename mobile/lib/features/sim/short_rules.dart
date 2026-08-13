/// CR171 §1 and §5 — what a sell does, and which way a short's bracket points.
///
/// Pure. Mirrors the rules the backend owns, with the same split of authority
/// as `order_pricing.dart`: **this predicts, the server decides.** The value of
/// predicting here is that both rules produce a *refusal*, and a refusal the
/// user meets at the tap is a sentence they can act on, while the same refusal
/// three seconds later out of a server round trip reads as the app being
/// broken.
///
/// Two rules, and both exist because of defects this project has already paid
/// for.
///
/// **A sell never crosses zero (§1).** With `h` held and `q` asked:
///
///   - `h >= q` closes, byte-identical to today.
///   - `h == 0` opens a short.
///   - `0 < h < q` is **refused** — not split into a close plus a short.
///
/// Splitting one action into two is the P&L-attribution bug class DEF166 and
/// DEF110 have already cost us twice: the resulting rows are indistinguishable
/// downstream from two things the user actually did, and every average-cost and
/// realised-P&L figure computed off them is quietly wrong. Refusing costs one
/// sentence of copy.
///
/// **The bracket inverts on a short (§5).** A stop sits *above* the entry and a
/// target *below* it, because the position profits as price falls. A user who
/// sets a short's stop below entry has written a stop that cannot fire until the
/// position has already gone the whole way to zero — which is the one shape a
/// stop exists to prevent. The CR is explicit: refuse it at submit with a
/// sentence, do not silently accept it.
///
/// **Not modelled here, deliberately:** borrow cost, margin thresholds, forced
/// buy-in, gross concentration. Those need position state and a rate the client
/// does not have, and a client-side approximation of a margin call is the
/// CR040/DEF252 sin — a number that looks authoritative and is invented.
library;

enum SellIntent {
  /// `h >= q` — reduces or closes a long. What every sell does today.
  closesLong,

  /// `h == 0` — a sell-to-open. A short entry.
  opensShort,

  /// `0 < h < q` — refused. See the library docstring.
  crossesZero,
}

SellIntent classifySell({required double held, required double quantity}) {
  if (held >= quantity) return SellIntent.closesLong;
  if (held <= 0) return SellIntent.opensShort;
  return SellIntent.crossesZero;
}

/// The quantity that would close the long, for the copy that offers it as the
/// alternative to the refused order.
double closeableQuantity(double held) => held < 0 ? 0 : held;

/// Where a stop belongs relative to entry.
///
/// Long: below (`price <= stop` fires). Short: above (`price >= stop` fires).
/// Null entry or stop means "nothing to check yet" — an unset field is not a
/// violation, and reporting it as one trains the user to ignore the message.
bool? stopIsWrongSide({
  required bool isShort,
  required double? entry,
  required double? stop,
}) {
  if (entry == null || stop == null || entry <= 0 || stop <= 0) return null;
  return isShort ? stop <= entry : stop >= entry;
}

/// Where a target belongs relative to entry. The mirror of [stopIsWrongSide]:
/// long targets sit above, short targets below.
bool? targetIsWrongSide({
  required bool isShort,
  required double? entry,
  required double? target,
}) {
  if (entry == null || target == null || entry <= 0 || target <= 0) return null;
  return isShort ? target >= entry : target <= entry;
}
