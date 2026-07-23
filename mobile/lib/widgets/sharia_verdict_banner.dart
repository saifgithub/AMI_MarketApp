/// Renders a per-ticker Sharia verdict with its provenance (CR069 Phase 1b).
///
/// One widget for all four states, because the states must be *told apart*, and
/// the way that fails is two surfaces each rendering two of them with different
/// wording. CR069 design constraint 2 is precisely this: a universe is not a
/// screen, and collapsing "unknown" into "screened out" is a false assurance in
/// the direction nobody checks.
///
/// The colour is doing semantic work and is chosen per state, not per outcome:
///
///   pass         → green. Screened and cleared by the named standard.
///   screenedOut  → amber. A real exclusion; the trade is blocked.
///   unknown      → NEUTRAL slate, deliberately. The trade WENT THROUGH (G3:
///                  unknown permits). Amber here would read as "this trade was
///                  risky", which is the same false-negative CR069 forbids in
///                  words, re-introduced through colour. It is not a warning —
///                  it is an absence of a ruling.
///   unavailable  → amber. An AMI-side refresh failure, surfaced loudly
///                  (CR040) rather than answered from a stale set.
///
/// The strings come from the ARB, never from the backend's English
/// `ShariaVerdict.message()`. The backend composes that sentence for agent
/// prompts and for the `violations[]` list; rendering it here would hardcode
/// English into every locale.
library;

import 'package:flutter/material.dart';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sharia.dart';
import 'package:ami_trade/theme/ami_theme.dart';

class ShariaVerdictBanner extends StatelessWidget {
  const ShariaVerdictBanner({super.key, required this.verdict});

  final ShariaVerdict verdict;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final accent = _accentFor(verdict.status);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate900,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: accent),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(_iconFor(verdict.status), color: accent, size: 16),
              const SizedBox(width: 4),
              Text(
                _headerFor(l, verdict.status),
                style: AmiTypography.labelMono
                    .copyWith(color: accent, fontSize: 11),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(messageFor(l, verdict), style: AmiTypography.caption),
        ],
      ),
    );
  }

  /// Exposed for the widget test: the four states must resolve to four
  /// distinct strings, and the assertion that matters is that `unknown` does
  /// NOT resolve to the screened-out copy.
  static String messageFor(AppLocalizations l, ShariaVerdict v) {
    final date = formatAsOf(l, v.asOf);
    switch (v.status) {
      case ShariaStatus.pass:
        return l.shariaVerdictPass(v.ticker, v.standard, v.source, date);
      case ShariaStatus.screenedOut:
        return l.shariaVerdictScreenedOut(v.ticker, v.standard, v.source, date);
      case ShariaStatus.unknown:
        return l.shariaVerdictUnknown(v.ticker, v.standard);
      case ShariaStatus.unavailable:
        return l.shariaVerdictPaused(date);
    }
  }

  /// ISO-8601, matching the backend's own `as_of` stamp so the date a user
  /// reads is byte-identical to the one in the source's published CSV. A null
  /// stamp renders as the literal "unknown" rather than as today's date —
  /// inventing a freshness stamp is the failure this CR exists to close.
  static String formatAsOf(AppLocalizations l, DateTime? asOf) {
    if (asOf == null) return 'unknown';
    final m = asOf.month.toString().padLeft(2, '0');
    final d = asOf.day.toString().padLeft(2, '0');
    return '${asOf.year}-$m-$d';
  }

  static Color _accentFor(ShariaStatus s) {
    switch (s) {
      case ShariaStatus.pass:
        return AmiColors.hexGreen;
      case ShariaStatus.screenedOut:
      case ShariaStatus.unavailable:
        return AmiColors.hexAmber;
      case ShariaStatus.unknown:
        return AmiColors.slate600;
    }
  }

  static IconData _iconFor(ShariaStatus s) {
    switch (s) {
      case ShariaStatus.pass:
        return Icons.verified_outlined;
      case ShariaStatus.screenedOut:
        return Icons.lock;
      case ShariaStatus.unknown:
        return Icons.help_outline;
      case ShariaStatus.unavailable:
        return Icons.pause_circle_outline;
    }
  }

  /// `pass` and `unknown` share a neutral header on purpose — both land on a
  /// successful trade, and a header that differed would let the user read a
  /// verdict off the chrome before reading the sentence.
  static String _headerFor(AppLocalizations l, ShariaStatus s) =>
      s == ShariaStatus.unavailable
          ? l.shariaVerdictLabelPaused
          : l.shariaVerdictLabelPass;
}
