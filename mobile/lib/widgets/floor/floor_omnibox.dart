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
///
/// **CR283 — the market chip and name resolution.** Passing [market] is what
/// turns Bursa on for this widget: a US / MY chip appears in the field and a
/// typed word is resolved against both markets through [resolve] before it is
/// routed (see `lookupName`). With [market] null — every Bursa-off build — none
/// of that exists: no chip, no lookup, today's routing exactly.
library;

import 'dart:async';

import 'package:ami_trade/features/floor/omnibox_router.dart';
import 'package:ami_trade/features/markets/market.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
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
    this.onReview,
    this.market,
    this.onMarketChanged,
    this.resolve,
    this.fieldKey,
    this.ctaKey,
    this.reviewKey,
  }) : assert(market == null || resolve != null,
            'a Bursa-on omnibox needs a name resolver');

  /// CR283 — the active market, or null when this build has no Bursa.
  final AppMarket? market;

  /// CR283 — the chip's tap: the market to switch to.
  final ValueChanged<AppMarket>? onMarketChanged;

  /// CR283 — name -> candidates for one market (backend `/v1/tickers/resolve`).
  final TickerResolver? resolve;

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

  /// CR244 — opens Company Review for the ticker currently in the box. Null
  /// or disabled by the same gate CONVENE uses (ticker-shaped, validated) —
  /// see `_reviewTicker` below. Optional so tests that don't care about
  /// Review can omit it.
  final ValueChanged<String>? onReview;

  final Key? fieldKey;
  final Key? ctaKey;
  final Key? reviewKey;

  @override
  State<FloorOmnibox> createState() => _FloorOmniboxState();
}

/// CR283 — what the box would do with the current text.
enum _Mode {
  /// Today's rule ([routeOmnibox]) decides. Always the case with Bursa off.
  rule,

  /// A name is being looked up; the CTA stays generic until it answers.
  resolving,

  /// The lookup found exactly one listing: [_Eff.ticker] / [_Eff.label].
  resolved,

  /// The word is listed in both markets: [_Eff.choices] is shown, nothing
  /// convenes until the user taps one.
  choose,

  /// MY mode and the lookup is down: say so, convene nothing.
  blocked,
}

class _Eff {
  const _Eff(this.mode,
      {this.decision, this.ticker, this.label, this.choices = const []});

  final _Mode mode;
  final OmniboxDecision? decision;
  final String? ticker;
  final String? label;
  final List<ResolvedTicker> choices;

  /// The ticker CONVENE / Review would act on right now, or null.
  String? get conveneTicker => switch (mode) {
        _Mode.rule => decision!.route == OmniboxRoute.convene
            ? decision!.ticker
            : null,
        _Mode.resolved => ticker,
        _ => null,
      };
}

class _FloorOmniboxState extends State<FloorOmnibox> {
  final _ctrl = TextEditingController();
  late final TickerFieldValidator _validator;

  static const _lookupDebounce = Duration(milliseconds: 400);
  Timer? _lookupTimer;
  int _lookupSeq = 0;
  NameLookup? _lookup;
  String _lookupText = '';

  bool get _bursa => widget.market != null;
  String get _typed => _ctrl.text.trim();
  bool get _nameMode => _bursa && isNameQuery(_ctrl.text);

  OmniboxDecision _rule() => _bursa
      ? routeOmnibox(_ctrl.text, bursaEnabled: true)
      : routeOmnibox(_ctrl.text);

  _Eff _eff() {
    final rule = _Eff(_Mode.rule, decision: _rule());
    if (!_nameMode) return rule;
    final lookup = _lookupText == _typed ? _lookup : null;
    if (lookup == null) return const _Eff(_Mode.resolving);
    switch (lookup.kind) {
      case NameLookupKind.single:
        final c = lookup.candidates.first;
        return _Eff(_Mode.resolved,
            ticker: c.ticker.toUpperCase(), label: resolvedLabel(c));
      case NameLookupKind.choice:
        return _Eff(_Mode.choose, choices: lookup.candidates);
      case NameLookupKind.none:
        return rule;
      case NameLookupKind.down:
        return widget.market == AppMarket.my ? const _Eff(_Mode.blocked) : rule;
    }
  }

  void _feedValidator() {
    _validator.onTextChanged(_eff().conveneTicker ?? '');
  }

  Future<void> _runLookup() async {
    final q = _typed;
    final seq = ++_lookupSeq;
    final result = await lookupName(q,
        active: widget.market!, resolve: widget.resolve!);
    if (!mounted || seq != _lookupSeq) return;
    setState(() {
      _lookup = result;
      _lookupText = q;
    });
    _feedValidator();
  }

  @override
  void didUpdateWidget(FloorOmnibox old) {
    super.didUpdateWidget(old);
    if (old.market != widget.market && _bursa) {
      _lookup = null;
      _lookupTimer?.cancel();
      if (_nameMode) _lookupTimer = Timer(_lookupDebounce, _runLookup);
      _feedValidator();
    }
  }

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
    _lookupTimer?.cancel();
    _validator.dispose();
    _ctrl.dispose();
    super.dispose();
  }

  void _onTextChanged() {
    setState(() {});
    _lookupTimer?.cancel();
    if (_nameMode && _lookupText != _typed) {
      _lookupTimer = Timer(_lookupDebounce, _runLookup);
    }
    // Only ticker-shaped text is worth an existence check; a sentence bound for
    // the Concierge is not a symbol and must not spend a request saying so.
    _feedValidator();
  }

  Future<void> _conveneOn(String ticker) async {
    // DEF298 — the gate, not the label. A symbol the reference table does
    // not know never reaches the Room, so it can never cost a credit.
    if (_validator.checking) return;
    if (!await _validator.check(ticker)) return;
    if (!mounted) return;
    widget.onConvene(ticker);
  }

  Future<void> _go() async {
    var eff = _eff();
    if (eff.mode == _Mode.resolving) {
      _lookupTimer?.cancel();
      await _runLookup();
      if (!mounted) return;
      eff = _eff();
    }
    switch (eff.mode) {
      case _Mode.resolved:
        await _conveneOn(eff.ticker!);
      case _Mode.resolving || _Mode.choose || _Mode.blocked:
        return;
      case _Mode.rule:
        final decision = eff.decision!;
        switch (decision.route) {
          case OmniboxRoute.convene:
            await _conveneOn(decision.ticker!);
          case OmniboxRoute.concierge:
            widget.onAsk(decision.text!);
          case OmniboxRoute.picker:
            widget.onPick();
        }
    }
  }

  /// CR244 — the ticker Review would open, or null when the box isn't
  /// currently armed on a validated ticker. Same gate as CONVENE: ticker-shaped
  /// route, not mid-check, and not flagged unknown by the CR128 validator.
  String? get _reviewTicker {
    final ticker = _eff().conveneTicker;
    if (ticker == null) return null;
    if (_validator.checking) return null;
    if (_validator.unknownTicker != null) return null;
    return ticker;
  }

  /// L audit fix (CR244) — Review used to trust the button's enabled state
  /// alone (a snapshot of the validator's cached result at the last
  /// keystroke), unlike CONVENE's `_go`, which re-runs `_validator.check`
  /// synchronously in the tap handler before navigating. That gap meant a
  /// tap landing between "text changed" and "debounced check resolved"
  /// could open Review on a ticker never actually confirmed to exist. This
  /// mirrors `_go`'s gate exactly: await the check, bail if it fails.
  Future<void> _reviewTapped() async {
    final ticker = _eff().conveneTicker;
    if (ticker == null) return;
    if (_validator.checking) return;
    if (!await _validator.check(ticker)) return;
    if (!mounted) return;
    widget.onReview?.call(ticker);
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final eff = _eff();
    final concierge = kAllAgents.last;
    final reviewTicker = _reviewTicker;

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
              if (widget.market != null) ...[
                const SizedBox(width: AmiSpacing.xs),
                _MarketChip(
                  market: widget.market!,
                  onTap: widget.onMarketChanged == null
                      ? null
                      : () => widget.onMarketChanged!(
                          widget.market == AppMarket.my
                              ? AppMarket.us
                              : AppMarket.my),
                ),
              ],
            ],
          ),
        ),
        if (eff.mode == _Mode.blocked) ...[
          const SizedBox(height: AmiSpacing.s),
          Text(
            l.floorOmniboxLookupDown,
            key: const Key('omnibox-lookup-down'),
            style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber),
          ),
        ],
        if (eff.mode == _Mode.choose) ...[
          const SizedBox(height: AmiSpacing.s),
          _MarketChooser(
            choices: eff.choices,
            onPick: (c) => _conveneOn(c.ticker.toUpperCase()),
          ),
        ],
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
        // Acceptance #2 — CONVENE is still the only primary on the screen.
        // CR244 adds Review beside it as a 1/4-width split button (Saiful's
        // explicit mockup correction) — same row, never a second primary.
        IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                flex: 3,
                child: SizedBox(
                  key: widget.ctaKey,
                  child: HexButton(
                    label: switch (eff.mode) {
                      _Mode.resolved => l.floorConveneOn(eff.label!),
                      _Mode.resolving ||
                      _Mode.choose ||
                      _Mode.blocked =>
                        l.floorConveneCta,
                      _Mode.rule => switch (eff.decision!.route) {
                          OmniboxRoute.convene =>
                            l.floorConveneOn(eff.decision!.ticker!),
                          OmniboxRoute.concierge => l.floorAskAmi,
                          OmniboxRoute.picker => l.floorConveneCta,
                        },
                    },
                    color: AmiColors.hexGreen,
                    onPressed: _go,
                  ),
                ),
              ),
              const SizedBox(width: AmiSpacing.s),
              Expanded(
                flex: 1,
                child: _ReviewSplitButton(
                  key: widget.reviewKey,
                  onTap: reviewTicker == null || widget.onReview == null
                      ? null
                      : _reviewTapped,
                ),
              ),
            ],
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

/// CR283 — the "US" / "MY" market chip inside the search box. Tapping it
/// switches the app-wide market; the label is the market the box is searching.
class _MarketChip extends StatelessWidget {
  const _MarketChip({required this.market, required this.onTap});

  final AppMarket market;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final code = market == AppMarket.my ? 'MY' : 'US';
    return MergeSemantics(
      child: Semantics(
        identifier: FloorIds.marketChip,
        button: true,
        label: l.floorMarketChipSemantics(code),
        child: GestureDetector(
          key: const Key('floor-market-chip'),
          onTap: onTap,
          behavior: HitTestBehavior.opaque,
          child: Container(
            constraints: const BoxConstraints(minHeight: 36, minWidth: 44),
            padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.s),
            decoration: BoxDecoration(
              color: AmiColors.hexBlue.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(AmiRadii.card),
              border:
                  Border.all(color: AmiColors.hexBlue.withValues(alpha: 0.5)),
            ),
            alignment: Alignment.center,
            child: ExcludeSemantics(
              child: Text(code,
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.hexBlue)),
            ),
          ),
        ),
      ),
    );
  }
}

/// CR283 — the two-line chooser: the typed word is listed in both markets, so
/// the user says which. One row per market, the active market first (the order
/// [lookupName] returns). Nothing convenes until a row is tapped.
class _MarketChooser extends StatelessWidget {
  const _MarketChooser({required this.choices, required this.onPick});

  final List<ResolvedTicker> choices;
  final ValueChanged<ResolvedTicker> onPick;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(l.floorOmniboxChooseMarket,
            style: AmiTypography.labelMono.copyWith(color: AmiColors.textLow)),
        const SizedBox(height: AmiSpacing.xs),
        for (final c in choices)
          Padding(
            padding: const EdgeInsets.only(bottom: AmiSpacing.xs),
            child: MergeSemantics(
              child: Semantics(
                identifier: '${FloorIds.marketChoicePrefix}${c.ticker}',
                button: true,
                child: GestureDetector(
                  key: Key('omnibox-choice-${c.ticker}'),
                  onTap: () => onPick(c),
                  behavior: HitTestBehavior.opaque,
                  child: Container(
                    constraints: const BoxConstraints(minHeight: 48),
                    padding: const EdgeInsets.symmetric(
                        horizontal: AmiSpacing.s, vertical: AmiSpacing.xs),
                    decoration: BoxDecoration(
                      color: AmiColors.slate800,
                      borderRadius: BorderRadius.circular(AmiRadii.card),
                      border: Border.all(color: AmiColors.slate700),
                    ),
                    child: Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(resolvedLabel(c),
                                  style: AmiTypography.labelMono.copyWith(
                                      color: AmiColors.textHigh)),
                              Text(c.longName,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: AmiTypography.caption
                                      .copyWith(color: AmiColors.textLow)),
                            ],
                          ),
                        ),
                        Text(c.market,
                            style: AmiTypography.labelMono
                                .copyWith(color: AmiColors.hexBlue)),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

/// CR244 — the 1/4-width Review split button beside CONVENE THE ROOM. Same
/// disabled treatment as [HexButton] (no ticker armed → dim, no tap): Review
/// is never a second primary, so it never gets its own error state, only an
/// on/off one that mirrors CONVENE's own gate.
class _ReviewSplitButton extends StatelessWidget {
  const _ReviewSplitButton({super.key, required this.onTap});

  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final enabled = onTap != null;
    final color = enabled ? AmiColors.hexBlue : AmiColors.textLow;
    // L6 audit fix — `floorReviewCta`'s own ARB description promises this
    // string doubles as the button's tooltip (no visible text label at this
    // width); previously only the Semantics label carried it, so a
    // pointer-hover user (or anyone relying on the tooltip affordance) never
    // saw it.
    return Tooltip(
      message: l.floorReviewCta,
      child: Semantics(
        button: true,
        enabled: enabled,
        label: l.floorReviewCta,
        child: GestureDetector(
          onTap: onTap,
          behavior: HitTestBehavior.opaque,
          child: Container(
            constraints: const BoxConstraints(minHeight: 44),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(AmiRadii.card),
              border: Border.all(color: color.withValues(alpha: 0.5)),
            ),
            alignment: Alignment.center,
            child: Icon(Icons.info_outline, color: color, size: 20),
          ),
        ),
      ),
    );
  }
}
