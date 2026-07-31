/// DEF208 — the *single* "that isn't a listed ticker" surface, plus the
/// single piece of behaviour that decides when to show it.
///
/// CR128 shipped a submit-time `AlertDialog`; DEF207 then needed a signal
/// that fires *while the user types* (a modal cannot pop on every
/// keystroke), so it added an inline panel to the trade ticket and left the
/// dialog in place. Counting the un-styled Material `SnackBar` used for the
/// no-suggestion case, the same fact — "this string is not a security" —
/// was being told three different ways across three flows, and on the trade
/// ticket you could be told twice for one ticker. Saiful: *"we seemed to
/// have multiple ways to informing the customers. why do we not have only
/// one design"*.
///
/// So there is one panel and one validator, and Convene the Room, the trade
/// ticket, and watchlist add all use both. The inline panel is the surface
/// that survived because it is the only one that works on the
/// live-as-you-type path — a dialog there would re-open DEF207, whose whole
/// complaint was *"there is no indication that the ticker selected does not
/// exist"* while a fabricated price sat on screen.
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

/// Owns the debounce, the in-flight check, and the not-found state for one
/// ticker field. Held by the hosting `State`, which supplies [onChanged] as
/// its own `setState` and disposes this alongside its controllers.
///
/// Sharing the *behaviour* and not just the pixels is deliberate: three
/// hand-rolled copies of "debounce, validate, decide what to show" is how
/// the three designs diverged in the first place.
class TickerFieldValidator {
  TickerFieldValidator({
    required Future<TickerValidation> Function(String ticker) validate,
    required VoidCallback onChanged,
    void Function(String ticker)? onExists,
    Duration debounce = const Duration(milliseconds: 450),
  })  : _validate = validate,
        _onChanged = onChanged,
        _onExists = onExists,
        _debounceFor = debounce;

  final Future<TickerValidation> Function(String) _validate;
  final VoidCallback _onChanged;

  /// Fired when a check resolves to a ticker that *does* exist. The trade
  /// ticket chains its quote fetch off this so the price can never be
  /// requested for a string the reference table doesn't know — the
  /// mock-walk provider will happily mint a plausible price for any input,
  /// which was DEF207's fabricated `$287.82` for "NETFLIX".
  final void Function(String)? _onExists;
  final Duration _debounceFor;

  Timer? _debounce;
  bool _disposed = false;
  String? _unknownTicker;
  TickerSuggestion? _suggestion;
  bool _checking = false;

  /// The string the panel is about, or null when there is nothing to say.
  /// Render [TickerNotFoundPanel] if and only if this is non-null.
  String? get unknownTicker => _unknownTicker;

  /// The closest match, when the backend found one. Null means the panel
  /// shows the plain "check the symbol" copy instead of an answer.
  TickerSuggestion? get suggestion => _suggestion;

  /// A check is in flight. Hosts use this to disable their submit control
  /// so a tap can't outrun the answer.
  bool get checking => _checking;

  /// Wire to the field's `TextEditingController` listener.
  ///
  /// Clears the panel immediately — the user is already fixing it, and
  /// leaving a stale "NETFLIX was not found" above a field that now reads
  /// "NFLX" is its own small lie — then re-checks once they pause.
  void onTextChanged(String raw) {
    _debounce?.cancel();
    if (_unknownTicker != null) {
      _unknownTicker = null;
      _suggestion = null;
      _emit();
    }
    final t = _normalize(raw);
    if (t.isEmpty) return;
    _debounce = Timer(_debounceFor, () => _run(t));
  }

  /// Submit-time gate: resolves now rather than waiting out the debounce,
  /// for the user who types and taps faster than 450ms.
  ///
  /// Returns false only when the ticker is *known* not to exist, and by
  /// then the panel is already showing why. An unreachable backend returns
  /// true — see [_run] for why failing open is the right call here.
  Future<bool> check(String raw) async {
    _debounce?.cancel();
    final t = _normalize(raw);
    if (t.isEmpty) return false;
    return await _run(t) ?? true;
  }

  void reset() {
    _debounce?.cancel();
    if (_unknownTicker == null && !_checking) return;
    _unknownTicker = null;
    _suggestion = null;
    _checking = false;
    _emit();
  }

  void dispose() {
    _disposed = true;
    _debounce?.cancel();
  }

  /// True = listed, false = definitively not listed, null = couldn't tell.
  Future<bool?> _run(String t) async {
    _checking = true;
    _emit();
    try {
      final v = await _validate(t);
      if (_disposed) return null;
      if (v.exists) {
        _unknownTicker = null;
        _suggestion = null;
        _onExists?.call(t);
        return true;
      }
      _unknownTicker = t;
      _suggestion = v.suggestion;
      return false;
    } catch (_) {
      if (_disposed) return null;
      // DEF207's lesson, kept: a network failure is NOT "this ticker
      // doesn't exist", and accusing a real ticker because the wifi dropped
      // is the worse error. Callers fail open — the server-side guard on
      // room / sim / watchlist is the actual gate (CR128 defense in depth),
      // and a client that can't reach `/tickers/validate` can't reach those
      // endpoints either, so their own error paths take it from here.
      _unknownTicker = null;
      _suggestion = null;
      return null;
    } finally {
      _checking = false;
      _emit();
    }
  }

  static String _normalize(String raw) => raw.trim().toUpperCase();

  void _emit() {
    if (_disposed) return;
    _onChanged();
  }
}

/// The one not-found surface. Sits directly under the ticker field in every
/// flow, amber-bordered, non-modal, and — when there is a suggestion —
/// tappable: one tap rewrites the field, which re-triggers the same
/// debounce and resolves to a real ticker without retyping.
class TickerNotFoundPanel extends StatelessWidget {
  const TickerNotFoundPanel({
    super.key,
    required this.typed,
    required this.suggestion,
    required this.onAccept,
  });

  final String typed;
  final TickerSuggestion? suggestion;
  final ValueChanged<String> onAccept;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final s = suggestion;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.hexAmber.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexAmber.withValues(alpha: 0.5)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.only(top: 2),
                child: Icon(Icons.error_outline,
                    color: AmiColors.hexAmber, size: 16),
              ),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  // "check the symbol and try again" is the right
                  // instruction ONLY when we have nothing better to offer.
                  // With a suggestion on the next line it contradicts
                  // itself, so the two states get different copy rather
                  // than one string that is wrong half the time.
                  s == null
                      ? l.tickerNotFound(typed)
                      : l.tickerNotFoundWithSuggestion(typed),
                  style: AmiTypography.body,
                ),
              ),
            ],
          ),
          if (s != null) ...[
            const SizedBox(height: AmiSpacing.s),
            OutlinedButton(
              style: OutlinedButton.styleFrom(
                foregroundColor: AmiColors.hexCyan,
                side: const BorderSide(color: AmiColors.hexCyan),
                padding: const EdgeInsets.symmetric(
                    horizontal: AmiSpacing.s, vertical: 8),
              ),
              onPressed: () => onAccept(s.ticker),
              child: Text(
                l.tickerDidYouMean(s.ticker, s.companyName),
                textAlign: TextAlign.start,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
