/// CR234 — one shared "ALPACA PAPER" identity, used everywhere Alpaca data
/// appears on the Portfolio screen and the trade ticket.
///
/// Saiful, from a TestFlight screenshot: the Alpaca section on Portfolio
/// looked visibly different from AMI's own — a plain text header instead of
/// a badge, bare rows instead of position cards, a value that wrapped onto
/// two lines. *"The alpaca section needs to be done along the same design
/// as the rest, but with a clear indicator for alpaca paper."*
///
/// This file is that indicator, in one place so it cannot drift: a single
/// [AlpacaBadge] widget and the one accent colour ([alpacaAccent]) every
/// Alpaca-sourced surface uses — the account card, position cards, open
/// orders, order history, and the trade ticket's own destination labels.
///
/// **CR234 round 2 (MINOR-3):** `hexPurple` was the original pick, on the
/// (unverified) claim that it carried no meaning elsewhere on this screen.
/// The auditor found two collisions ON the portfolio screen itself:
/// `hexPurple` is already in the sector-allocation palette
/// (`portfolio_screen.dart`, an AMI sector slice can render purple) and is
/// `RestingOrderState.unknown`'s colour (`resting_orders_section.dart`, AMI's
/// own resting-order book directly above the Alpaca open-orders section on
/// the same Orders tab). `hexFuchsia500` replaces it: audited against every
/// `AmiColors.*` use on `portfolio_screen.dart` and every widget it renders
/// (sim/position_card, value_card, resting_orders_section,
/// option_positions_section, short_positions_section, portfolio_health/
/// health_card, the alpaca/ widgets themselves) — not used as an accent
/// anywhere in that tree, so it reads as "a different account" without
/// colliding with a meaning a user already learned on this exact screen.
///
/// Deliberately NOT Alpaca's own brand colour (their yellow/green) — this
/// badge identifies which BOOK the data came from inside AMI's own design
/// language, not an endorsement or a co-branding mark.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:flutter/widgets.dart';

/// The one accent every Alpaca-sourced surface on Portfolio uses. Exported
/// so a card that isn't a [HexChip] (e.g. a card border) can still match.
const Color alpacaAccent = AmiColors.hexFuchsia500;

/// The literal, un-localized "ALPACA PAPER" label every surface uses. Not an
/// ARB key: this is a destination name, the exact string
/// `trade_ticket_sheet.dart`'s own destination picker already renders
/// un-localized (`'ALPACA PAPER'` — see `_destination` chips there), and
/// this badge exists specifically so nothing re-derives or rewords it.
const String kAlpacaPaperLabel = 'ALPACA PAPER';

/// The shared "which book is this" badge. `dot` shows the small live/linked
/// indicator (used on the account-level header, not on every row — a dot
/// per position card would be noise the AMI side does not have either).
class AlpacaBadge extends StatelessWidget {
  const AlpacaBadge({super.key, this.dot = false, this.fontSize = 10});

  final bool dot;
  final double fontSize;

  @override
  Widget build(BuildContext context) {
    return HexChip(
      label: kAlpacaPaperLabel,
      color: alpacaAccent,
      variant: HexChipVariant.tinted,
      showDot: dot,
      fontSize: fontSize,
    );
  }
}
