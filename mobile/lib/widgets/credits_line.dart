/// CR236 — the shared compact "how many credits do I have" text line.
///
/// One rendering rule serves every surface Saiful named (the Convene sheet,
/// the 1-on-1 composer, Settings): a plain `labelMono` line, never a number
/// this build did not actually receive. `creditsResetDateLabel` is the one
/// place a `credits_reset_at` timestamp becomes the short localized date
/// string ("1 Oct") every caller needs — so there is exactly one formatter,
/// not the three ad-hoc `'the 1st'` fallbacks CR236 replaces
/// (`room_screen.dart`'s `_resetDateStr`/`_verdictResetDateStr` stay as they
/// were; they format a *different* string, the sentence-form paywall copy).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

/// Formats a `credits_reset_at` instant as the short date every CR236 surface
/// shows — "1 Oct" (day-then-month, matching Saiful's approved copy exactly;
/// `DateFormat.MMMd()` gives the US "Oct 1" ordering instead). Localized via
/// `intl`'s current default locale — the same mechanism `DateFormat` uses
/// elsewhere in this codebase (`ticker_detail_screen.dart`'s
/// `DateFormat.yMMMd()`), so the month name itself still follows the app's
/// locale.
String creditsResetDateLabel(DateTime resetsAt) =>
    DateFormat('d MMM').format(resetsAt.toLocal());

/// The Convene sheet's line: "Room: 8 credits · you have 63 · resets 1 Oct".
///
/// [cost] / [balance] null means UNKNOWN (mandate not loaded, or the field
/// came back null off the wire per DEF437) — renders [creditsLineUnknown]
/// rather than a guessed number. [resetsAt] absent simply drops the
/// "· resets …" clause; it never fabricates a date (DEF059 class).
class ConveneCreditsLine extends StatelessWidget {
  const ConveneCreditsLine({
    super.key,
    required this.cost,
    required this.balance,
    this.resetsAt,
  });

  final int? cost;
  final int? balance;
  final DateTime? resetsAt;

  bool get _insufficient =>
      cost != null && balance != null && balance! < cost!;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    if (cost == null || balance == null) {
      return Text(
        l.creditsLineUnknown,
        style: AmiTypography.labelMono
            .copyWith(fontSize: 11, color: AmiColors.textLow),
      );
    }
    final reset = resetsAt;
    final base = reset == null
        ? l.creditsLineCost(cost.toString(), balance.toString())
        : l.creditsLineCostWithReset(
            cost.toString(), balance.toString(), creditsResetDateLabel(reset));
    final color = _insufficient ? AmiColors.hexAmber : AmiColors.textMed;
    return Text.rich(
      TextSpan(
        style: AmiTypography.labelMono.copyWith(fontSize: 11, color: color),
        children: [
          TextSpan(text: base),
          if (_insufficient)
            TextSpan(text: ' · ${l.creditsLineInsufficient}'),
        ],
      ),
    );
  }
}

/// The 1-on-1 composer's line: "You have 63 credits". No cost shown — the
/// client has no per-turn 1-on-1 price to read (unlike the Room's
/// `mandate.room_cost`), only the ledger balance itself.
class OneOnOneCreditsLine extends StatelessWidget {
  const OneOnOneCreditsLine({super.key, required this.balance});

  final int? balance;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    if (balance == null) {
      return Text(
        l.creditsLineUnknown,
        style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
      );
    }
    return Text(
      l.oneOnOneCreditsBalance(balance.toString()),
      style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
    );
  }
}

/// The post-Room quiet line: "This Room used 8 credits · 55 left" ("This
/// Room used 8 credits" until the refreshed balance arrives), the refunded
/// variant when CR039/DEF425/DEF432 gave the charge back, or (CR237) the
/// third, truthful branch for a run whose "Ask the CIO again" retry
/// succeeded. Renders nothing when [cost] is null (a backend predating
/// CR236, or the done event's row read raced away) — silence, not a guess.
class RoomResultCostLine extends StatelessWidget {
  const RoomResultCostLine({
    super.key,
    required this.cost,
    required this.refunded,
    required this.balanceAfter,
    this.cioRetried = false,
  });

  final int? cost;
  final bool refunded;
  final int? balanceAfter;

  /// CR237 — true once a successful "Ask the CIO again" retry has replaced
  /// this run's outage PASS with a real verdict. The run DID finish (so
  /// [roomResultRefunded]'s "didn't reach a verdict" framing would read
  /// false here) but was never net-charged (the original DEF432 refund
  /// stands and the retry itself is free) — a fact [refunded]/[cost] alone
  /// cannot distinguish from an ordinary charged completion, which is why
  /// this needs its own flag rather than reusing [refunded]. Takes priority
  /// over both other branches: a retried run is neither the plain-refunded
  /// case nor a normal charge.
  final bool cioRetried;

  @override
  Widget build(BuildContext context) {
    final c = cost;
    if (c == null) return const SizedBox.shrink();
    final l = AppLocalizations.of(context);
    final left = balanceAfter;
    final text = cioRetried
        ? l.roomResultCioRetried
        : refunded
            ? l.roomResultRefunded
            : left == null
                ? l.roomResultCostNoBalance(c.toString())
                : l.roomResultCost(c.toString(), left.toString());
    return Text(
      text,
      style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
    );
  }
}
