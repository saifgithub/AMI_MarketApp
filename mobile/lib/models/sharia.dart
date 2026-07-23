/// Mobile mirror of the backend's Sharia verdict type (CR069 Phase 1b).
///
/// Hand-mirrored from `backend/app/schemas/sharia.py` — the backend↔mobile seam
/// is over-the-wire JSON with no codegen, so this file is the *only* thing
/// keeping the two sides in step. A rename on the backend fails silently here
/// behind a `??` default, which is the failure mode DEF084 and CR040 both point
/// at. `ShariaStatus.fromWire` therefore returns null on an unrecognised value
/// rather than defaulting to a state, so a drifted enum surfaces as "no verdict"
/// instead of a confidently wrong one.
///
/// Four states, never two (CR069 constraint 2):
///   pass         — in the compliant set. Tradeable.
///   screenedOut  — in the parent index (S&P 500) but absent from the compliant
///                  set. A real exclusion — blocks the trade.
///   unknown      — not in the parent index at all. The standard never looked at
///                  it, so it is *no ruling either way*. PERMITTED, with the
///                  disclosure attached (G3, resolved 2026-07-23). Its copy
///                  therefore lands on a SUCCESSFUL trade, not on a rejection,
///                  and must never read as a warning that the trade was risky.
///   unavailable  — the source could not be refreshed / is stale beyond its
///                  window. The flag pauses loudly (CR040) — never a silent
///                  stale read.
///
/// The strings are NOT built here. The backend composes an English sentence in
/// `ShariaVerdict.message()`; the app renders its own localized copy from the
/// ARB so AR/MS can diverge. This type carries only the structured facts —
/// status, ticker, standard, source, as-of date — which are what constraint 1
/// requires travel with every verdict.
library;

enum ShariaStatus {
  pass,
  screenedOut,
  unknown,
  unavailable;

  /// Wire values as emitted by `backend/app/schemas/sharia.py::ShariaStatus`.
  static const Map<String, ShariaStatus> _wire = {
    'pass': ShariaStatus.pass,
    'screened_out': ShariaStatus.screenedOut,
    'unknown': ShariaStatus.unknown,
    'unavailable': ShariaStatus.unavailable,
  };

  /// Null on an unrecognised wire value — see the library doc. Do NOT add a
  /// default; a silent fallback re-creates the exact class of bug this type
  /// exists to close.
  static ShariaStatus? fromWire(Object? raw) =>
      raw is String ? _wire[raw] : null;

  /// SCREENED_OUT and UNAVAILABLE block a trade; PASS and UNKNOWN permit it.
  /// Mirrors `ShariaVerdict.is_blocking`. UNKNOWN must never block (G3) — an
  /// unknown ticker is *no ruling*, not a soft no.
  bool get isBlocking =>
      this == ShariaStatus.screenedOut || this == ShariaStatus.unavailable;
}

class ShariaVerdict {
  const ShariaVerdict({
    required this.status,
    required this.ticker,
    required this.standard,
    required this.source,
    this.asOf,
  });

  final ShariaStatus status;
  final String ticker;

  /// e.g. "AAOIFI". Named wherever the verdict is shown (constraint 1).
  final String standard;

  /// e.g. "S&P 500 Sharia Industry Exclusions Index (via SPUS)".
  final String source;

  /// ISO date from the source's own as-of stamp. Null only when the backend
  /// could not stamp one (an unavailable/paused screen).
  final DateTime? asOf;

  bool get isBlocking => status.isBlocking;

  /// Returns null when the payload carries no verdict at all (halal flag off,
  /// or a backend that does not yet serialize the field) and when the status
  /// is unrecognised. A caller that gets null must render NOTHING rather than
  /// guess a state.
  static ShariaVerdict? fromJson(Map<String, dynamic>? j) {
    if (j == null) return null;
    final status = ShariaStatus.fromWire(j['status']);
    if (status == null) return null;
    return ShariaVerdict(
      status: status,
      ticker: (j['ticker'] as String? ?? '').toUpperCase(),
      standard: j['standard'] as String? ?? '',
      source: j['source'] as String? ?? '',
      asOf: _parseDate(j['as_of']),
    );
  }

  static DateTime? _parseDate(Object? raw) =>
      raw is String ? DateTime.tryParse(raw) : null;
}
