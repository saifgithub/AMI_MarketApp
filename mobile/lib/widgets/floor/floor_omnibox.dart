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
///
/// **DEF298 — the shape test is not the gate.** `routeOmnibox` decides where the
/// text goes; it deliberately does not know which symbols exist, so `HI` and
/// `ZZZZZ` arm CONVENE. Slice 2 mitigated that by renaming the CTA and trusting
/// the user to read it, which is CR038's own finding pointed at a person: an
/// instruction the reader is expected to notice is not a control. Convening on a
/// symbol that does not exist costs a credit and runs twelve agents over a price
/// the mock provider invented. So the same [TickerFieldValidator] the Convene
/// sheet and the trade ticket already use runs here too, inline under the field
/// as you type (DEF208), and `_go` will not convene until it has said yes. One
/// gate, three fields — not a fourth opinion about what a ticker is.
///
/// The validator arrives as a callback rather than through `ref` so this widget
/// stays a plain [StatefulWidget]: a test can hand it a fake and assert the gate
/// without standing up a provider container.
library;

import 'package:ami_trade/features/floor/omnibox_router.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/ticker_not_found_panel.dart';
import 'package:flutter/material.dart';

class FloorOmnibox extends StatefulWidget {
  const FloorOmnibox({
    super.key,
    required this.onConvene,
    required this.onAsk,
    required this.onPick,
    required this.validate,
    this.fieldKey,
    this.ctaKey,
  });

  /// The CR128 existence check — the same one behind the Convene sheet and the
  /// trade ticket. Injected, not read from a provider, so the gate is visible in
  /// this widget's own signature.
  final Future<TickerValidation> Function(String ticker) validate;

  /// A ticker-shaped entry, already upper-cased **and confirmed to exist**.
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
  late final TickerFieldValidator _validator;

  @override
  void initState() {
    super.initState();
    _validator = TickerFieldValidator(
      validate: widget.validate,
      onChanged: () {
        if (mounted) setState(() {});
      },
    );
    // The CTA's label is a function of the text, so it has to rebuild on every
    // keystroke — that is the whole "visible before it is taken" property.
    _ctrl.addListener(_onTextChanged);
  }

  @override
  void dispose() {
    _ctrl.removeListener(_onTextChanged);
    _validator.dispose();
    _ctrl.dispose();
    super.dispose();
  }

  void _onTextChanged() {
    setState(() {});
    // Only ticker-shaped text is worth an existence check; a sentence bound for
    // the Concierge is not a symbol and must not spend a request saying so.
    final decision = routeOmnibox(_ctrl.text);
    _validator.onTextChanged(
      decision.route == OmniboxRoute.convene ? decision.ticker! : '',
    );
  }

  Future<void> _go() async {
    final decision = routeOmnibox(_ctrl.text);
    switch (decision.route) {
      case OmniboxRoute.convene:
        // DEF298 — the gate, not the label. A symbol the reference table does
        // not know never reaches the Room, so it can never cost a credit.
        if (_validator.checking) return;
        if (!await _validator.check(decision.ticker!)) return;
        if (!mounted) return;
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
          // The box is the screen's primary entry point and now has the room to
          // look like it: the Floor's footer lost its hidden long-press
          // (CR182), so this is no longer competing for vertical space with
          // anything. A 56pt-tall target also clears the 48pt minimum a
          // one-handed thumb needs, which the old `vertical: 2` did not.
          constraints: const BoxConstraints(minHeight: 56),
          padding: const EdgeInsets.symmetric(
              horizontal: AmiSpacing.s, vertical: AmiSpacing.xs),
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
                  size: 32),
              const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: TextField(
                  controller: _ctrl,
                  textInputAction: TextInputAction.go,
                  onSubmitted: (_) => _go(),
                  // DEF297 — Flutter's default `onTapOutside` unfocuses on
                  // desktop and does NOTHING on iOS/Android, so without this
                  // the keyboard has no way down: the Floor offers nothing else
                  // to focus, and the only other exit (`go`) leaves the screen.
                  onTapOutside: (_) => FocusScope.of(context).unfocus(),
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
        // DEF298/DEF208 — the answer arrives under the field as you type, in
        // the same panel the other two ticker fields use, rather than as a
        // modal after you have already committed.
        if (_validator.unknownTicker != null) ...[
          const SizedBox(height: AmiSpacing.s),
          TickerNotFoundPanel(
            typed: _validator.unknownTicker!,
            suggestion: _validator.suggestion,
            onAccept: (t) {
              _ctrl.text = t;
              _ctrl.selection = TextSelection.collapsed(offset: t.length);
            },
          ),
        ],
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
