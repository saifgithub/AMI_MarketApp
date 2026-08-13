/// CR173 slice 2 — one box where the Floor had two doors.
///
/// The shipped Floor asked the user to know, before typing anything, whether
/// their thought was a *ticker* (→ the CONVENE sheet) or a *question* (→ the
/// Concierge hex, 110pt, top of the screen). That is the app's filing system
/// presented as a choice. Here there is one box, and the routing is the app's
/// problem — decided by [routeOmnibox], deterministically, with no LLM in the
/// path (§4, CR038).
///
/// **The route is visible before it is taken.** Shape-matching cannot read
/// intent, so `HI` arms CONVENE. Rather than hide that, the CTA renames itself
/// to whatever is about to happen — `CONVENE THE ROOM · HI` is wrong on its
/// face and gets corrected before a credit is spent. A silent router would have
/// spent it.
///
/// **Tap-first** (§5): CONVENE on an empty box opens the picker. Typing is the
/// accelerant, never the toll — the pink Concierge mark inside the field is the
/// screen's one identity mark at rest (acceptance #1).
library;

import 'package:ami_trade/features/floor/omnibox_router.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:flutter/material.dart';

class FloorOmnibox extends StatefulWidget {
  const FloorOmnibox({
    super.key,
    required this.onConvene,
    required this.onAsk,
    required this.onPick,
    this.fieldKey,
    this.ctaKey,
  });

  /// A ticker-shaped entry, already upper-cased.
  final ValueChanged<String> onConvene;

  /// Anything else, trimmed — arrives in the Concierge chat as the first user
  /// message (§5). D-015 holds there: the Concierge routes analysis to the
  /// firm, it does not answer it.
  final ValueChanged<String> onAsk;

  /// The empty-box path.
  final VoidCallback onPick;

  final Key? fieldKey;
  final Key? ctaKey;

  @override
  State<FloorOmnibox> createState() => _FloorOmniboxState();
}

class _FloorOmniboxState extends State<FloorOmnibox> {
  final _ctrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    // The CTA's label is a function of the text, so it has to rebuild on every
    // keystroke — that is the whole "visible before it is taken" property.
    _ctrl.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  void _go() {
    final decision = routeOmnibox(_ctrl.text);
    switch (decision.route) {
      case OmniboxRoute.convene:
        widget.onConvene(decision.ticker!);
      case OmniboxRoute.concierge:
        widget.onAsk(decision.text!);
      case OmniboxRoute.picker:
        widget.onPick();
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final decision = routeOmnibox(_ctrl.text);
    final concierge = kAllAgents.last;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          key: widget.fieldKey,
          padding: const EdgeInsets.symmetric(
              horizontal: AmiSpacing.s, vertical: 2),
          decoration: BoxDecoration(
            color: AmiColors.slate800,
            borderRadius: BorderRadius.circular(AmiRadii.card),
            border: Border.all(color: AmiColors.slate700),
          ),
          child: Row(
            children: [
              HexAvatar(
                  label: concierge.abbreviation,
                  color: concierge.color,
                  size: 28),
              const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: TextField(
                  controller: _ctrl,
                  textInputAction: TextInputAction.go,
                  onSubmitted: (_) => _go(),
                  style: AmiTypography.body,
                  decoration: InputDecoration(
                    isDense: true,
                    border: InputBorder.none,
                    hintText: l.floorOmniboxHint,
                    hintStyle: AmiTypography.body
                        .copyWith(color: AmiColors.textLow),
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: AmiSpacing.s),
        // Acceptance #2 — the only primary on the screen. Everything else on
        // the Floor is a card, a row or a text button.
        SizedBox(
          key: widget.ctaKey,
          child: HexButton(
            label: switch (decision.route) {
              OmniboxRoute.convene =>
                l.floorConveneOn(decision.ticker!),
              OmniboxRoute.concierge => l.floorAskAmi,
              OmniboxRoute.picker => l.floorConveneCta,
            },
            color: AmiColors.hexGreen,
            onPressed: _go,
          ),
        ),
        const SizedBox(height: AmiSpacing.xs),
        Text(
          l.floorOmniboxCaption,
          textAlign: TextAlign.center,
          style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
        ),
      ],
    );
  }
}
