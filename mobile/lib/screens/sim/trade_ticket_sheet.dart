/// Sim Trade ticket — the form that submits a trade.
///
/// Used standalone (from the Portfolio screen) and as the "Open trade
/// ticket" CTA from a Room verdict (with the verdict's size/entry/stop/
/// target pre-filled). On submit, PM safety floor runs server-side; any
/// rejection is surfaced as an amber banner with the specific violations.
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/features/sim/order_pricing.dart';
import 'package:ami_trade/features/sim/short_rules.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/room/convene_sheet.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/sharia_verdict_banner.dart';
import 'package:ami_trade/widgets/sheet_insets.dart';
import 'package:ami_trade/widgets/ticker_not_found_panel.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class TradeTicketSheet extends ConsumerStatefulWidget {
  const TradeTicketSheet({
    super.key,
    this.prefill,
    this.verdictRef,
    this.tickerPrefill,
    this.coverTicker,
    this.coverQuantity,
  });

  /// Optional Room verdict to pre-fill from.
  final RoomVerdict? prefill;
  final String? verdictRef;
  final String? tickerPrefill;

  /// CR171 — opened to cover a standing short. Fixes the side to BUY and the
  /// quantity to the whole position, because the server takes a cover whole or
  /// not at all (§1's sell-never-crosses-zero, seen from the other end). Left
  /// editable would be a field whose only other value is a refusal.
  final String? coverTicker;
  final double? coverQuantity;

  @override
  ConsumerState<TradeTicketSheet> createState() => _TradeTicketSheetState();

  static Future<void> show(
    BuildContext context, {
    RoomVerdict? prefill,
    String? verdictRef,
    String? tickerPrefill,
    String? coverTicker,
    double? coverQuantity,
  }) {
    return showModalBottomSheet<void>(
      context: context,
      backgroundColor: AmiColors.slate800,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => TradeTicketSheet(
        prefill: prefill,
        verdictRef: verdictRef,
        tickerPrefill: tickerPrefill,
        coverTicker: coverTicker,
        coverQuantity: coverQuantity,
      ),
    );
  }
}

class _TradeTicketSheetState extends ConsumerState<TradeTicketSheet> {
  late final TextEditingController _ticker;
  late final TextEditingController _qty;
  late final TextEditingController _stop;
  late final TextEditingController _target;
  late final TextEditingController _horizon;
  // CR170 — the resting-order half. Two more price fields, shown only for the
  // order types that need them, and only against a backend that has the book.
  late final TextEditingController _limit;
  late final TextEditingController _trigger;
  SimOrderType _orderType = SimOrderType.market;
  SimOrderTif _tif = SimOrderTif.day;
  String _side = 'buy';
  // Bug d5717660: when a trade has no AI verdict, suggest convening first.
  // The user can dismiss the advisory and proceed — the trade is recorded
  // with verdict_ref=null, which the journal renders as "Without AI advice".
  bool _advisoryDismissed = false;

  // Live quote for the entered ticker. Fetched on a debounce so the user
  // has a price anchor when setting TP/SL manually. Source string is the
  // leaf provider (yfinance | mock_walk) so the user knows what they're
  // looking at.
  ({double price, double changePct, String source, String marketState})? _quote;
  String? _quoteTicker; // ticker that _quote belongs to
  bool _quoteLoading = false;

  /// CR128 existence check, DEF207's on-the-same-debounce-as-the-quote
  /// timing, and DEF208's shared not-found panel — all of it lives in the
  /// validator now, which owns the debounce this sheet used to run itself.
  /// The quote fetch chains off [TickerFieldValidator]'s `onExists`, so a
  /// price can only ever be requested for a ticker the reference table
  /// confirmed.
  late final TickerFieldValidator _validator;

  @override
  void initState() {
    super.initState();
    _ticker =
        TextEditingController(text: widget.coverTicker ?? widget.tickerPrefill ?? '');
    _qty = TextEditingController(
      text: widget.coverQuantity?.toStringAsFixed(0) ?? '1',
    );
    if (widget.coverTicker != null) _side = 'buy';
    _stop = TextEditingController();
    _target = TextEditingController();
    _horizon = TextEditingController();
    _limit = TextEditingController();
    _trigger = TextEditingController();
    // CR170/CR171 — the live hint and the two refusals are computed in `build`
    // from what is typed, so every field they read has to rebuild the sheet.
    // Found by a test: the quantity field had no `onChanged`, so a sell of ten
    // against a holding of four typed cleanly and the refusal never appeared.
    // Listeners rather than per-field `onChanged` because the set will grow and
    // the one that gets forgotten is the one that matters.
    for (final c in [_ticker, _qty, _stop, _target, _limit, _trigger]) {
      c.addListener(_rebuildOnInput);
    }
    final v = widget.prefill;
    if (v != null && v.isApprove) {
      if (v.stop != null) _stop.text = v.stop!.toStringAsFixed(2);
      if (v.target != null) _target.text = v.target!.toStringAsFixed(2);
      if (v.timeHorizonDays != null) _horizon.text = '${v.timeHorizonDays}';
      // Suggested qty: use the verdict's size%, $10k starting capital,
      // ~$entry price → quantity = size * 100 / entry. Conservative round.
      if (v.entry != null && v.entry! > 0 && v.sizePct != null) {
        final qty = ((10000 * v.sizePct! / 100) / v.entry!).floor();
        _qty.text = qty <= 0 ? '1' : '$qty';
      }
    }
    _validator = TickerFieldValidator(
      validate: (t) => ref.read(apiClientProvider).validateTicker(t),
      onChanged: () {
        if (mounted) setState(() {});
      },
      onExists: _fetchQuote,
    );
    // If a ticker is prefilled (verdict path), check + fetch its quote
    // immediately so the price chip lands without the user having to retype.
    if (_ticker.text.trim().isNotEmpty) {
      _validator.onTextChanged(_ticker.text);
    }
    _ticker.addListener(_onTickerChanged);
  }

  @override
  void dispose() {
    _validator.dispose();
    _ticker.removeListener(_onTickerChanged);
    for (final c in [_ticker, _qty, _stop, _target, _limit, _trigger]) {
      c.removeListener(_rebuildOnInput);
      c.dispose();
    }
    _horizon.dispose();
    super.dispose();
  }

  void _onTickerChanged() {
    final t = _ticker.text.trim().toUpperCase();
    // Invalidate the chip if the user is editing — once they pause we'll
    // refetch. Avoids showing the wrong ticker's price during typing.
    if (t != _quoteTicker) {
      setState(() {
        _quote = null;
        _quoteTicker = null;
      });
    }
    _validator.onTextChanged(_ticker.text);
  }

  /// Only ever called by the validator, and only for a ticker it has just
  /// confirmed exists (DEF207): `simQuoteDetail` cannot answer the
  /// existence question itself — it falls through to the mock walk and
  /// fabricates a plausible price for any string, which is exactly how
  /// "NETFLIX" rendered as a confident $287.82 with nothing to say it is
  /// not a ticker (bug `ab1d5664`).
  Future<void> _fetchQuote(String ticker) async {
    if (!mounted) return;
    setState(() => _quoteLoading = true);
    try {
      final q = await ref.read(apiClientProvider).simQuoteDetail(ticker);
      if (!mounted) return;
      // If the user kept typing past us, drop the stale result.
      if (_ticker.text.trim().toUpperCase() != ticker) return;
      setState(() {
        _quote = q;
        _quoteTicker = ticker;
        _quoteLoading = false;
      });
      // CR171 — a cover carries no bracket: the server closes the whole
      // position at the fill and never reads stop/target on that path.
      // Anchoring them here would put two numbers in front of the user that
      // do nothing, on the one screen where a number that does nothing reads
      // as a control.
      if (_isCover) return;
      _anchorBracket(q.price);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _quote = null;
        _quoteTicker = null;
        _quoteLoading = false;
      });
    }
  }

  Future<void> _convene() async {
    final ticker = _ticker.text.trim().toUpperCase();
    if (ticker.isEmpty) {
      Navigator.of(context).pop();
      ConveneSheet.show(context);
      return;
    }
    // Convening burns credits + paid feed quota before a single agent
    // speaks, so this route out of the sheet gets the same gate as submit.
    if (_validator.checking) return;
    if (!await _validator.check(ticker)) return;
    if (!mounted) return;
    Navigator.of(context).pop();
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => RoomScreen(ticker: ticker),
    ));
  }

  void _rebuildOnInput() {
    if (mounted) setState(() {});
  }

  bool get _isCover => widget.coverTicker != null;

  /// Close the sheet and give the same confirmation the ordinary path gives.
  void _acknowledgeAdvisory() {
    final result = ref.read(simNotifierProvider).lastSubmit;
    final typed = _ticker.text.trim().toUpperCase();
    setState(() => _pendingAdvisories = const []);
    Navigator.of(context).pop();
    if (result != null && result.ok) _showOutcome(result, typed);
  }

  /// CR171 §6 — notices from the LAST submit, held so the sheet can show them
  /// before it closes.
  ///
  /// The trade already executed by the time these arrive, and the sheet's
  /// success path pops immediately — so an advisory rendered inline in `build`
  /// would be drawn onto a widget that is already leaving the tree. It would
  /// be on the wire, computed correctly, and seen by nobody, which is the exact
  /// shape of the failure Saiful's ruling exists to prevent: *"we will put a
  /// flag and notice to inform the user, but we let the trade through."*
  /// Holding the pop until the notice is acknowledged is what makes "inform"
  /// true (CR040).
  List<String> _pendingAdvisories = const [];

  /// CR171 §1/§5 — the two refusals the ticket owns, as **one** function that
  /// both the panel and the CTA's enabled-state read.
  ///
  /// One source, not two, on purpose: a disabled button with no sentence is a
  /// dead control, and a sentence over a live button is an instruction the user
  /// can ignore. The pair only stays consistent if there is nothing to keep
  /// consistent (DEF098).
  ///
  /// Null means "nothing to refuse", which includes every case where the input
  /// is too incomplete to judge. An unset field is not a violation, and warning
  /// about one teaches the user to read past the panel.
  /// Shares of the typed ticker currently held. 0 when nothing is typed yet.
  double _heldQty(SimState state, String ticker) =>
      state.portfolio?.holdings
          .where((h) => h.ticker.toUpperCase() == ticker)
          .fold<double>(0, (a, h) => a + h.quantity) ??
      0;

  /// CR188 — does this order OPEN a short? The same three-case rule the server
  /// applies, read here so the sheet can say so before the tap rather than in
  /// the snackbar after it.
  bool _opensShort(SimState state) {
    if (_side != 'sell') return false;
    final typed = _ticker.text.trim().toUpperCase();
    final qty = double.tryParse(_qty.text.trim());
    if (typed.isEmpty || qty == null || qty <= 0) return false;
    return classifySell(held: _heldQty(state, typed), quantity: qty) ==
        SellIntent.opensShort;
  }

  String? _localRefusal(AppLocalizations l, SimState state) {
    final typed = _ticker.text.trim().toUpperCase();
    final qty = double.tryParse(_qty.text.trim());
    if (typed.isEmpty || qty == null || qty <= 0) return null;

    final held = _heldQty(state, typed);
    var isShort = false;

    if (_side == 'sell') {
      final intent = classifySell(held: held, quantity: qty);
      if (intent == SellIntent.crossesZero) {
        return l.tradeTicketRefuseCrossZero(
          closeableQuantity(held).toStringAsFixed(0),
          typed,
          qty.toStringAsFixed(0),
        );
      }
      // A sell that CLOSES a long carries no bracket of its own — its levels
      // are meaningless, which is why the server does not judge them either.
      if (intent != SellIntent.opensShort) return null;
      isShort = true;
    }

    // CR188/DEF312 — the bracket rule runs for BOTH directions now.
    //
    // `stopIsWrongSide`/`targetIsWrongSide` have taken an `isShort` flag and
    // handled the long case correctly since CR171. They were called behind
    // `if (intent != SellIntent.opensShort) return null`, after this method had
    // already returned early on every buy — so the long branch existed, was
    // right, and was unreachable. That is P21, and the server had the identical
    // hole (`short_bracket_is_wrong_side` called only from `_open_short_fill`),
    // which is why reading either side made the rule look covered.
    //
    // The price the bracket is measured against: what the user named on a
    // resting order, otherwise the live mark. Null when neither is known — the
    // check simply does not run, rather than running against a zero.
    final entry = namedPriceFor(_orderType,
            triggerPrice: double.tryParse(_trigger.text.trim()),
            limitPrice: double.tryParse(_limit.text.trim())) ??
        _quote?.price;
    final stop = double.tryParse(_stop.text.trim());
    final target = double.tryParse(_target.text.trim());
    if (stopIsWrongSide(isShort: isShort, entry: entry, stop: stop) == true) {
      return isShort
          ? l.tradeTicketRefuseShortStop
          : l.tradeTicketRefuseLongStop(stop!.toStringAsFixed(2));
    }
    if (targetIsWrongSide(isShort: isShort, entry: entry, target: target) ==
        true) {
      return isShort
          ? l.tradeTicketRefuseShortTarget
          : l.tradeTicketRefuseLongTarget(target!.toStringAsFixed(2));
    }
    return null;
  }

  /// DEF314 — anchor TP/SL off the live price, **pointing the way this order
  /// actually points**.
  ///
  /// This wrote `price × 0.94` / `price × 1.13` unconditionally: a long bracket,
  /// on every order, including one that opens a SHORT. CR171 then refuses a
  /// short whose stop sits below entry — so the sheet filled in two numbers the
  /// user never typed and killed its own submit button over them, with a message
  /// naming a rule about fields it had just written itself.
  ///
  /// **It made shorting impossible through the ticket.** Type a ticker you do
  /// not hold, pick SELL, let the quote land, and the order is un-submittable
  /// unless you notice that the fix is to clear two optional fields. Measured on
  /// 2026-08-15: `sim_short_positions` held **zero rows, ever**, while 30 of 37
  /// current mandates permitted shorting. That gap was read as "nobody wants to
  /// short" until this was found.
  ///
  /// Reported by Saiful from a device — COST at $961.10 gave 903.43 / 1086.04,
  /// which is exactly `× 0.94` and `× 1.13`.
  ///
  /// A short inverts: the stop goes ABOVE, the target BELOW, at the same
  /// distances, so the suggestion stays the trader template either way.
  /// An ordinary sell that CLOSES a long gets nothing — an exit carries no
  /// bracket of its own, the same reason a cover returns above.
  void _anchorBracket(double price) {
    final state = ref.read(simNotifierProvider);
    if (_side == 'sell' && !_opensShort(state)) return;
    final short = _side == 'sell';
    if (_stop.text.trim().isEmpty) {
      _stop.text = (price * (short ? 1.06 : 0.94)).toStringAsFixed(2);
    }
    if (_target.text.trim().isEmpty) {
      _target.text = (price * (short ? 0.87 : 1.13)).toStringAsFixed(2);
    }
  }

  /// DEF314 — the bracket follows the side.
  ///
  /// Only ever discards values THIS SHEET wrote: a field the user edited is
  /// left exactly as typed, and the refusal panel then does its job on it. The
  /// alternative — leaving our own long bracket in place after a flip to SELL —
  /// is the dead end itself.
  void _rebracketForSide() {
    final q = _quote;
    if (q == null) return;
    for (final (c, longMul, shortMul) in [
      (_stop, 0.94, 1.06),
      (_target, 1.13, 0.87),
    ]) {
      final ours = {
        (q.price * longMul).toStringAsFixed(2),
        (q.price * shortMul).toStringAsFixed(2),
      };
      if (c.text.trim().isEmpty || ours.contains(c.text.trim())) c.text = '';
    }
    _anchorBracket(q.price);
  }

  /// CR188 — flipping to SELL fills the quantity with what you actually hold.
  ///
  /// It defaulted to `1`, which is the one quantity that is almost never the
  /// intent and never tells the user what they own. Only ever fills DOWN from a
  /// holding — a ticker with nothing held is left alone rather than being
  /// pre-loaded with a short the user did not ask for, and switching back to BUY
  /// does not touch the field at all.
  void _prefillSellQuantity(SimState state) {
    if (_side != 'sell') return;
    final typed = _ticker.text.trim().toUpperCase();
    if (typed.isEmpty) return;
    final held = _heldQty(state, typed);
    if (held <= 0) return;
    _qty.text = held.toStringAsFixed(0);
  }

  /// CR188 — what this SELL is about to do, stated before the tap.
  ///
  /// Informational, never a refusal: it renders alongside a live button. The
  /// ticket used to say nothing at all here, so a sell did one of three
  /// different things — reduce, refuse, or open a short with unbounded loss —
  /// decided by a number that appeared nowhere on the screen.
  String? _sellNotice(AppLocalizations l, SimState state) {
    if (_side != 'sell') return null;
    final typed = _ticker.text.trim().toUpperCase();
    final qty = double.tryParse(_qty.text.trim());
    if (typed.isEmpty || qty == null || qty <= 0) return null;
    final held = _heldQty(state, typed);
    return switch (classifySell(held: held, quantity: qty)) {
      SellIntent.closesLong => l.tradeTicketNoticeHolding(
          held.toStringAsFixed(0), typed, qty.toStringAsFixed(0)),
      SellIntent.opensShort => l.tradeTicketNoticeOpensShort(typed),
      // The refusal panel already carries this case, in stronger words.
      SellIntent.crossesZero => null,
    };
  }

  Future<void> _submit() async {
    final typed = _ticker.text.trim().toUpperCase();
    final qty = double.tryParse(_qty.text.trim());
    if (typed.isEmpty || qty == null || qty <= 0 || _validator.checking) return;
    // CR171 — refused here as well as in the disabled CTA, because the sheet
    // can reach this method from a keyboard submit action that never touches
    // the button.
    if (_localRefusal(AppLocalizations.of(context),
            ref.read(simNotifierProvider)) !=
        null) {
      return;
    }
    // DEF208: no modal here. A failed check leaves the shared panel under
    // the field explaining why, which is the same thing the user has been
    // looking at since they stopped typing.
    if (!await _validator.check(typed)) return;
    if (!mounted) return;
    final result = await ref.read(simNotifierProvider.notifier).submit(
      ticker: typed,
      side: _side,
      quantity: qty,
      orderType: _orderType,
      limitPrice: _orderType.needsLimitPrice
          ? double.tryParse(_limit.text.trim())
          : null,
      triggerPrice: _orderType.needsTriggerPrice
          ? double.tryParse(_trigger.text.trim())
          : null,
      tif: _tif,
      stop: double.tryParse(_stop.text.trim()),
      target: double.tryParse(_target.text.trim()),
      horizonDays: int.tryParse(_horizon.text.trim()),
      verdictRef: widget.verdictRef,
    );
    if (!mounted) return;
    if (result != null && result.ok) {
      // Strong success feedback (bug 9b3a6c2f): the previous slate800
      // snackbar was indistinguishable from the dark theme, leaving users
      // unsure whether the trade actually placed and tapping Buy again.
      // Now: haptic tick, green background, large checkmark, longer
      // duration so the success is unambiguous.
      HapticFeedback.mediumImpact();
      // CR171 §6 — hold the sheet open on an advisory. The trade is done
      // either way; this is the only moment at which the notice can be put in
      // front of the person it is about.
      if (result.advisories.isNotEmpty) {
        setState(() => _pendingAdvisories = result.advisories);
        return;
      }
      Navigator.of(context).pop();
      _showOutcome(result, typed);
    }
  }

  /// The one confirmation, whichever of the four things just happened.
  ///
  /// Extracted so the advisory path's "GOT IT" reaches exactly the same
  /// sentence the ordinary path does. A second copy of this would be a second
  /// place for the short branch to be forgotten (DEF098).
  void _showOutcome(SimSubmitResult result, String typed) {
    final l = AppLocalizations.of(context);
    // CR170/CR171 — FOUR outcomes now, and the copy must not claim the wrong
    // one. `resting` is read off the response, never inferred from
    // `trade == null`: the server states it on every branch. That inference
    // was already wrong once — a short writes no trade row by design (§3), so
    // `resting = result.resting || trade == null` reported every successful
    // short as an order waiting at $0.00.
    final short = result.shortAction;
    final filled = result.trade;
    final String message;
    final IconData icon;
    final Color background;
    if (short != null) {
      final qty = (result.shortQuantity ?? 0).toStringAsFixed(0);
      final ticker = result.shortTicker ?? typed;
      if (result.isShortCover) {
        final pnl = result.shortRealisedPnl ?? 0;
        message = l.tradeTicketShortCovered(
          qty,
          ticker,
          '${pnl >= 0 ? '+' : '−'}\$${pnl.abs().toStringAsFixed(2)}',
        );
        icon = Icons.check_circle;
        background = pnl >= 0 ? AmiColors.hexGreen : AmiColors.hexAmber;
      } else {
        message = l.tradeTicketShortOpened(
          qty, ticker, (_quote?.price ?? 0).toStringAsFixed(2),
        );
        icon = Icons.trending_down;
        background = AmiColors.hexRed;
      }
    } else if (filled == null) {
      message = l.tradeTicketResting(
        _side.toUpperCase(),
        typed,
        (result.order?.namedPrice ?? 0).toStringAsFixed(2),
      );
      icon = Icons.schedule;
      background = AmiColors.hexCyan;
    } else {
      message = l.tradeTicketFilled(
        filled.side.toUpperCase(),
        filled.quantity.toStringAsFixed(0),
        filled.ticker,
        filled.entryPrice.toStringAsFixed(2),
      );
      icon = Icons.check_circle;
      background = AmiColors.hexGreen;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        duration: const Duration(seconds: 5),
        backgroundColor: background,
        behavior: SnackBarBehavior.floating,
        content: Row(
          children: [
            Icon(icon, color: AmiColors.slate900, size: 24),
            const SizedBox(width: AmiSpacing.s),
            Expanded(
              child: Text(
                message,
                style: const TextStyle(
                  color: AmiColors.slate900,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Violations minus the backend's English Sharia sentence, when the same
  /// fact is about to be rendered from the ARB as a localized banner. See the
  /// call site for why the match is deliberately narrow.
  static List<String> _visibleViolations(SimSubmitResult r) {
    final v = r.shariaVerdict;
    if (v == null || !v.isBlocking) return r.violations;
    final ticker = v.ticker.toUpperCase();
    final standard = v.standard.toUpperCase();
    if (ticker.isEmpty || standard.isEmpty) return r.violations;
    return r.violations
        .where((s) =>
            !(s.toUpperCase().contains(ticker) &&
                s.toUpperCase().contains(standard)))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(simNotifierProvider);
    final refusal = state.lastSubmit != null && !state.lastSubmit!.ok;
    final l = AppLocalizations.of(context);
    // CR171 — the client-side refusals, distinct from `refusal` above, which is
    // the server's verdict on the LAST submit. This one is about the order the
    // user is still typing.
    final localRefusal = _localRefusal(l, state);
    // CR188 — what this order is about to do, and whether it opens a short.
    // Both are read once here so the notice, the CTA's label and the CTA's
    // colour cannot disagree about the same order (DEF098).
    final sellNotice = localRefusal == null ? _sellNotice(l, state) : null;
    final opensShort = _opensShort(state);
    // CR069 G3: the Sharia disclosure rides on BOTH outcomes. A screened-out
    // ticker is refused and its verdict sits inside the refusal panel below; a
    // pass or an unknown is PERMITTED, so its verdict has no refusal to ride on
    // and gets its own banner here. A permitted unknown that renders nothing is
    // a silent pass on an observance decision — this CR's failure class
    // pointing the other way.
    final permittedVerdict = state.lastSubmit != null && state.lastSubmit!.ok
        ? state.lastSubmit!.shariaVerdict
        : null;
    final blockingVerdict = refusal &&
            (state.lastSubmit!.shariaVerdict?.isBlocking ?? false)
        ? state.lastSubmit!.shariaVerdict
        : null;
    return Padding(
      padding: EdgeInsets.fromLTRB(
        AmiSpacing.l, AmiSpacing.l, AmiSpacing.l,
        // DEF075 — clear keyboard AND nav bar, not just the keyboard.
        AmiSpacing.l + sheetBottomInset(MediaQuery.of(context)),
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.bolt, color: AmiColors.hexCyan, size: 20),
                const SizedBox(width: AmiSpacing.s),
                Text(l.tradeTicketHeading,
                    style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
              ],
            ),
            const SizedBox(height: AmiSpacing.l),
            // No-verdict advisory (bug d5717660). Non-blocking: the user
            // can dismiss and submit anyway; the resulting trade has
            // verdict_ref=null so the journal labels it "Without AI advice".
            if (widget.verdictRef == null && !_advisoryDismissed) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(AmiSpacing.s),
                decoration: BoxDecoration(
                  color: AmiColors.hexBlue.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(AmiRadii.card),
                  border: Border.all(color: AmiColors.hexBlue.withValues(alpha: 0.5)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.lightbulb_outline,
                            color: AmiColors.hexBlue, size: 16),
                        const SizedBox(width: 4),
                        Text('NO AI VERDICT',
                            style: AmiTypography.labelMono.copyWith(
                                color: AmiColors.hexBlue, fontSize: 11)),
                        const Spacer(),
                        InkWell(
                          onTap: () => setState(() => _advisoryDismissed = true),
                          child: const Padding(
                            padding: EdgeInsets.all(4),
                            child: Icon(Icons.close,
                                color: AmiColors.textLow, size: 16),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Convene the Room first to get analysis from your 12 agents. '
                      'Or proceed — this trade will be marked "without advice".',
                      style: AmiTypography.body,
                    ),
                    const SizedBox(height: AmiSpacing.s),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            style: OutlinedButton.styleFrom(
                              foregroundColor: AmiColors.hexBlue,
                              side: const BorderSide(color: AmiColors.hexBlue),
                              padding: const EdgeInsets.symmetric(vertical: 8),
                            ),
                            icon: const Icon(Icons.bolt, size: 16),
                            label: const Text('Convene the Room'),
                            onPressed: _convene,
                          ),
                        ),
                        const SizedBox(width: AmiSpacing.s),
                        Expanded(
                          child: TextButton(
                            style: TextButton.styleFrom(
                              foregroundColor: AmiColors.textLow,
                              padding: const EdgeInsets.symmetric(vertical: 8),
                            ),
                            onPressed: () =>
                                setState(() => _advisoryDismissed = true),
                            child: const Text('Proceed without'),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AmiSpacing.m),
            ],
            // CR171 §6 — the notice on a trade that WENT THROUGH. Saiful's
            // ruling: *"our job is only to inform. The user can continue with
            // whatever trade they want to do."* So this is amber-bordered but
            // never says blocked, carries no way to undo, and the only control
            // on it acknowledges. Rendered ABOVE everything else in the sheet
            // because the sheet is only still open in order to show it.
            if (_pendingAdvisories.isNotEmpty) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(AmiSpacing.m),
                decoration: BoxDecoration(
                  color: AmiColors.hexAmber.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(AmiRadii.card),
                  border: Border.all(color: AmiColors.hexAmber),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.info_outline,
                            color: AmiColors.hexAmber, size: 16),
                        const SizedBox(width: 4),
                        Text(l.tradeTicketAdvisoryLabel,
                            style: AmiTypography.labelMono.copyWith(
                                color: AmiColors.hexAmber, fontSize: 11)),
                      ],
                    ),
                    const SizedBox(height: AmiSpacing.xs),
                    for (final a in _pendingAdvisories)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text(a, style: AmiTypography.body),
                      ),
                    const SizedBox(height: AmiSpacing.s),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AmiColors.hexAmber,
                          foregroundColor: AmiColors.slate900,
                        ),
                        onPressed: _acknowledgeAdvisory,
                        child: Text(l.tradeTicketAdvisoryAcknowledge,
                            style: AmiTypography.labelMono
                                .copyWith(color: AmiColors.slate900)),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AmiSpacing.m),
            ],
            if (permittedVerdict != null) ...[
              ShariaVerdictBanner(verdict: permittedVerdict),
              const SizedBox(height: AmiSpacing.m),
            ],
            // CR171 — why the quantity on a cover cannot be edited.
            if (_isCover) ...[
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.swap_vert,
                      size: 16, color: AmiColors.hexCyan),
                  const SizedBox(width: AmiSpacing.xs),
                  Expanded(
                    child: Text(
                      l.shortCoverTicketNote(
                        (widget.coverQuantity ?? 0).toStringAsFixed(0),
                        widget.coverTicker!,
                      ),
                      style: AmiTypography.caption
                          .copyWith(color: AmiColors.textMed),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AmiSpacing.m),
            ],
            if (refusal) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(AmiSpacing.s),
                decoration: BoxDecoration(
                  color: AmiColors.slate900,
                  borderRadius: BorderRadius.circular(AmiRadii.card),
                  border: Border.all(color: AmiColors.hexAmber),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.lock, color: AmiColors.hexAmber, size: 16),
                        const SizedBox(width: 4),
                        Text(l.tradeTicketSafetyFloorBlocked,
                            style: AmiTypography.labelMono.copyWith(
                                color: AmiColors.hexAmber, fontSize: 11)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    // The backend composes its violation sentences in English
                    // (they also feed the agent prompts). When a blocking
                    // Sharia verdict arrives structured, its localized banner
                    // is rendered below instead, so drop the English twin here
                    // rather than showing the same fact twice in two
                    // languages. The match is on the verdict's own ticker AND
                    // standard, so a violation from any other rule survives;
                    // if it ever fails to match, the user sees the English
                    // sentence as well — duplicated, never missing.
                    for (final v in _visibleViolations(state.lastSubmit!))
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text('• $v', style: AmiTypography.caption),
                      ),
                    if (blockingVerdict != null) ...[
                      const SizedBox(height: AmiSpacing.s),
                      ShariaVerdictBanner(verdict: blockingVerdict),
                    ],
                    const SizedBox(height: 4),
                    Text(
                      l.tradeTicketChangeMandate,
                      style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
                    ),
                    // CR133 §5 — this line used to end "…via Settings → My
                    // Mandate", which fired at the exact moment a compliance
                    // breach had just blocked the trade and then made the user
                    // walk the path themselves. CR133 moves that path (the
                    // mandate now sits YOU → SETTINGS), so the instruction was
                    // about to be both wrong AND a longer walk. Replaced with
                    // the control rather than renamed: a rename leaves the same
                    // trap armed for the next nav change. Same pattern the app
                    // already ships as `floorLockedGoToLessons` → "GO TO
                    // LESSONS".
                    const SizedBox(height: AmiSpacing.s),
                    Align(
                      alignment: AlignmentDirectional.centerStart,
                      child: TextButton(
                        style: TextButton.styleFrom(
                          padding: EdgeInsets.zero,
                          minimumSize: const Size(0, 32),
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        ),
                        onPressed: () => Navigator.of(context)
                            .push(MaterialPageRoute<void>(
                          builder: (_) => const SettingsScreen(),
                        )),
                        child: Text(
                          l.tradeTicketOpenMandate,
                          style: AmiTypography.labelMono
                              .copyWith(color: AmiColors.hexBlue),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AmiSpacing.m),
            ],
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _ticker,
                    autofocus: true,
                    textCapitalization: TextCapitalization.characters,
                    style: AmiTypography.statMid,
                    decoration: _decoration(
                        label: l.tradeTicketLabelTicker,
                        hint: l.tradeTicketHintTicker),
                  ),
                ),
                const SizedBox(width: AmiSpacing.s),
                _SideToggle(
                  value: _side,
                  onChange: (v) => setState(() {
                    _side = v;
                    _prefillSellQuantity(state);
                    _rebracketForSide();
                  }),
                ),
              ],
            ),
            // DEF207 — not-found takes the price chip's place entirely. A
            // price of ANY kind next to a string that isn't a ticker is the
            // fabrication this defect is about; the two are mutually
            // exclusive by construction, not by z-order.
            if (_validator.unknownTicker != null) ...[
              const SizedBox(height: AmiSpacing.xs),
              TickerNotFoundPanel(
                typed: _validator.unknownTicker!,
                suggestion: _validator.suggestion,
                onAccept: (t) {
                  _ticker.text = t;
                  _ticker.selection =
                      TextSelection.collapsed(offset: t.length);
                },
              ),
            ]
            // Live price anchor for setting TP / SL when no verdict has
            // been convened. Source pill (LIVE / MOCK) reflects what the
            // backend actually returned for this ticker — yfinance leaf
            // shows LIVE, mock_walk fallback shows MOCK.
            else if (_quote != null || _quoteLoading || _validator.checking) ...[
              const SizedBox(height: AmiSpacing.xs),
              _QuoteChip(
                quote: _quote,
                loading: _quoteLoading || _validator.checking,
              ),
            ],
            const SizedBox(height: AmiSpacing.m),
            TextField(
              controller: _qty,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [
                FilteringTextInputFormatter.allow(RegExp(r'[0-9.]')),
              ],
              style: AmiTypography.body,
              decoration: _decoration(
                  label: l.tradeTicketLabelQuantity, hint: l.tradeTicketHintQty),
            ),
            // CR170 — the order-type controls appear ONLY when this backend
            // actually has a resting-order book. Against a pre-CR170 server
            // `order_type=limit` is accepted and filled instantly at the price
            // typed, so offering the picker there would be a control that
            // quietly does something else with the user's money (CR040). See
            // `SimState.restingOrdersSupported`.
            if (state.restingOrdersSupported) ...[
              const SizedBox(height: AmiSpacing.m),
              _PillToggle<SimOrderType>(
                label: l.tradeTicketLabelOrderType,
                value: _orderType,
                accent: AmiColors.hexCyan,
                options: [
                  (SimOrderType.market, l.tradeTicketOrderMarket),
                  (SimOrderType.limit, l.tradeTicketOrderLimit),
                  (SimOrderType.stop, l.tradeTicketOrderStop),
                  (SimOrderType.stopLimit, l.tradeTicketOrderStopLimit),
                ],
                onChange: (v) => setState(() => _orderType = v),
              ),
              if (_orderType.needsTriggerPrice) ...[
                const SizedBox(height: AmiSpacing.m),
                TextField(
                  controller: _trigger,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  style: AmiTypography.body,
                  decoration: _decoration(
                      label: l.tradeTicketLabelTrigger,
                      hint: l.tradeTicketHintPrice),
                ),
              ],
              if (_orderType.needsLimitPrice) ...[
                const SizedBox(height: AmiSpacing.m),
                TextField(
                  controller: _limit,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  style: AmiTypography.body,
                  decoration: _decoration(
                      label: l.tradeTicketLabelLimit,
                      hint: l.tradeTicketHintPrice),
                ),
              ],
              if (_orderType.canRest) ...[
                const SizedBox(height: AmiSpacing.m),
                _PillToggle<SimOrderTif>(
                  label: l.tradeTicketLabelTif,
                  value: _tif,
                  accent: AmiColors.hexAmber,
                  options: [
                    (SimOrderTif.day, l.tradeTicketTifDay),
                    (SimOrderTif.gtd30, l.tradeTicketTif30),
                    (SimOrderTif.gtd90, l.tradeTicketTif90),
                  ],
                  onChange: (v) => setState(() => _tif = v),
                ),
              ],
              _OrderIntentHint(
                side: _side,
                ticker: _quoteTicker ?? _ticker.text.trim().toUpperCase(),
                orderType: _orderType,
                triggerPrice: double.tryParse(_trigger.text.trim()),
                limitPrice: double.tryParse(_limit.text.trim()),
                mark: _quote?.price,
              ),
            ],
            const SizedBox(height: AmiSpacing.m),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _stop,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    style: AmiTypography.body,
                    decoration: _decoration(
                        label: l.tradeTicketLabelStop,
                        hint: l.tradeTicketHintOptional),
                  ),
                ),
                const SizedBox(width: AmiSpacing.s),
                Expanded(
                  child: TextField(
                    controller: _target,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    style: AmiTypography.body,
                    decoration: _decoration(
                        label: l.tradeTicketLabelTarget,
                        hint: l.tradeTicketHintOptional),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AmiSpacing.m),
            TextField(
              controller: _horizon,
              keyboardType: TextInputType.number,
              style: AmiTypography.body,
              decoration: _decoration(
                  label: l.tradeTicketLabelHorizon, hint: l.tradeTicketHintOptional),
            ),
            // CR188 — informational, and deliberately in the refusal's slot
            // rather than beside it: the two are mutually exclusive, and the
            // last thing read before the button should be one sentence about
            // this order, never two competing ones.
            if (sellNotice != null) ...[
              const SizedBox(height: AmiSpacing.m),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    opensShort ? Icons.trending_down : Icons.info_outline,
                    size: 16,
                    color: opensShort ? AmiColors.hexAmber : AmiColors.textMed,
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      sellNotice,
                      style: AmiTypography.caption.copyWith(
                        color:
                            opensShort ? AmiColors.hexAmber : AmiColors.textMed,
                      ),
                    ),
                  ),
                ],
              ),
            ],
            if (localRefusal != null) ...[
              const SizedBox(height: AmiSpacing.m),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(AmiSpacing.m),
                decoration: BoxDecoration(
                  color: AmiColors.slate900,
                  borderRadius: BorderRadius.circular(AmiRadii.card),
                  border: Border.all(color: AmiColors.hexAmber),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.block, size: 18, color: AmiColors.hexAmber),
                    const SizedBox(width: AmiSpacing.s),
                    Expanded(
                      child: Text(localRefusal,
                          style: AmiTypography.caption
                              .copyWith(color: AmiColors.hexAmber)),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: AmiSpacing.l),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  // CR188 — a short is neither a buy nor an ordinary sell, and
                  // the control says so. CR171 already had the words for it and
                  // fired them AFTER the fill, which is right for the
                  // borrow-cost advisory and wrong for "this is a different
                  // kind of position than you think you are opening". A word on
                  // the control being pressed is structural; a sentence above it
                  // is an instruction, and instructions are not controls.
                  backgroundColor: opensShort
                      ? AmiColors.hexAmber
                      : (_side == 'buy'
                          ? AmiColors.hexGreen
                          : AmiColors.hexRed),
                  foregroundColor: AmiColors.slate900,
                  padding: const EdgeInsets.symmetric(vertical: AmiSpacing.m),
                ),
                icon: (state.submitting || _validator.checking)
                    ? const SizedBox(
                        width: 16, height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2, color: AmiColors.slate900,
                        ),
                      )
                    : Icon(opensShort
                        ? Icons.trending_down
                        : (_side == 'buy' ? Icons.add : Icons.remove)),
                // CR188 — the LABEL is the structural half, not the colour. A
                // user who reads nothing on this sheet still reads the word on
                // the button they are pressing, and "SUBMIT TRADE" over an
                // order that opens a borrowed position with uncapped loss is
                // the sheet's last chance to be honest.
                label: Text(state.submitting
                    ? l.tradeTicketSubmitting
                    : (opensShort
                        ? l.tradeTicketSubmitShort
                        : l.tradeTicketSubmit)),
                onPressed: (state.submitting ||
                        _validator.checking ||
                        localRefusal != null ||
                        // The trade this advisory belongs to has already
                        // executed. A live submit button under an unread
                        // notice is a second trade one tap away.
                        _pendingAdvisories.isNotEmpty)
                    ? null
                    : _submit,
              ),
            ),
            const SizedBox(height: AmiSpacing.xs),
            Text(
              l.tradeTicketFooterNote,
              style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
            ),
          ],
        ),
      ),
    );
  }

  InputDecoration _decoration({required String label, required String hint}) {
    return InputDecoration(
      labelText: label,
      labelStyle: AmiTypography.labelMono.copyWith(fontSize: 10),
      hintText: hint,
      hintStyle: AmiTypography.body.copyWith(color: AmiColors.textLow),
      filled: true,
      fillColor: AmiColors.slate900,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AmiRadii.card),
        borderSide: const BorderSide(color: AmiColors.slate700),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AmiRadii.card),
        borderSide: const BorderSide(color: AmiColors.hexCyan),
      ),
    );
  }
}


class _SideToggle extends StatelessWidget {
  const _SideToggle({required this.value, required this.onChange});
  final String value;
  final ValueChanged<String> onChange;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      decoration: BoxDecoration(
        color: AmiColors.slate900,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Row(
        children: [
          _pill(l.tradeTicketSideBuy, AmiColors.hexGreen, value == 'buy',
              () => onChange('buy')),
          _pill(l.tradeTicketSideSell, AmiColors.hexRed, value == 'sell',
              () => onChange('sell')),
        ],
      ),
    );
  }

  Widget _pill(String label, Color color, bool active, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AmiRadii.card),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        decoration: BoxDecoration(
          color: active ? color.withValues(alpha: 0.2) : Colors.transparent,
          borderRadius: BorderRadius.circular(AmiRadii.card),
        ),
        child: Text(label,
            style: AmiTypography.labelMono.copyWith(
              color: active ? color : AmiColors.textLow,
            )),
      ),
    );
  }
}

/// CR170 §9 — the generalised pill row `_SideToggle` was the first instance of.
/// The order-type and time-in-force pickers are the second and third, and three
/// hand-copies of one control is how a design-system property (DEF146's single
/// clip, most recently) ends up true of only some of them.
class _PillToggle<T> extends StatelessWidget {
  const _PillToggle({
    required this.label,
    required this.value,
    required this.options,
    required this.accent,
    required this.onChange,
  });

  final String label;
  final T value;
  final List<(T, String)> options;
  final Color accent;
  final ValueChanged<T> onChange;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: AmiTypography.labelMono
                .copyWith(fontSize: 10, color: AmiColors.textLow)),
        const SizedBox(height: 6),
        Container(
          decoration: BoxDecoration(
            color: AmiColors.slate900,
            borderRadius: BorderRadius.circular(AmiRadii.card),
            border: Border.all(color: AmiColors.slate700),
          ),
          child: Row(
            children: [
              for (final (v, text) in options)
                Expanded(
                  child: InkWell(
                    onTap: () => onChange(v),
                    borderRadius: BorderRadius.circular(AmiRadii.card),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: v == value
                            ? accent.withValues(alpha: 0.2)
                            : Colors.transparent,
                        borderRadius: BorderRadius.circular(AmiRadii.card),
                      ),
                      child: Text(
                        text,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AmiTypography.labelMono.copyWith(
                          fontSize: 10,
                          color: v == value ? accent : AmiColors.textLow,
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}


/// CR170 §9 calls this the highest-value element in the feature, and the reason
/// is behavioural rather than decorative: without it a resting order reads as a
/// **broken button**. The user taps BUY, nothing appears in their holdings, and
/// nothing on the screen said it would not.
///
/// It states what *this order* will do — order state — not how the simulator
/// works. Saiful, 2026-08-11: *"we do not need to explain the simulation rules
/// to the user. thats our internal decision."* So there is no note about polling
/// cadence, fill-in-full or the pricing rule here, and there must not be one.
///
/// It renders **nothing** until it can say something true: no typed price, no
/// quote, or an order type this build does not recognise all produce an empty
/// box rather than a guess.
class _OrderIntentHint extends StatelessWidget {
  const _OrderIntentHint({
    required this.side,
    required this.ticker,
    required this.orderType,
    required this.triggerPrice,
    required this.limitPrice,
    required this.mark,
  });

  final String side;
  final String ticker;
  final SimOrderType orderType;
  final double? triggerPrice;
  final double? limitPrice;
  final double? mark;

  @override
  Widget build(BuildContext context) {
    if (orderType == SimOrderType.market) return const SizedBox.shrink();
    final intent = predictIntent(
      side: side,
      orderType: orderType,
      triggerPrice: triggerPrice,
      limitPrice: limitPrice,
      mark: mark,
    );
    if (intent == null) return const SizedBox.shrink();
    final l = AppLocalizations.of(context);
    final named = namedPriceFor(orderType,
        triggerPrice: triggerPrice, limitPrice: limitPrice)!;
    final fillsNow = intent == OrderIntent.fillsNow;
    final accent = fillsNow ? AmiColors.hexGreen : AmiColors.hexCyan;
    final below = restsBelow(side: side, orderType: orderType);
    return Padding(
      padding: const EdgeInsets.only(top: AmiSpacing.s),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(fillsNow ? Icons.bolt : Icons.schedule, size: 16, color: accent),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              fillsNow
                  ? l.tradeTicketHintFillsNow
                  : (orderType == SimOrderType.stopLimit
                      ? l.tradeTicketHintRestsStopLimit(
                          ticker,
                          named.toStringAsFixed(2),
                          (limitPrice ?? 0).toStringAsFixed(2))
                      : (below
                          ? l.tradeTicketHintRestsBelow(
                              ticker, named.toStringAsFixed(2))
                          : l.tradeTicketHintRestsAbove(
                              ticker, named.toStringAsFixed(2)))),
              style: AmiTypography.caption.copyWith(color: accent),
            ),
          ),
        ],
      ),
    );
  }
}


/// Inline chip under the ticker field — shows the live price, day-change
/// %, and a LIVE / MOCK pill so the user has a price anchor when setting
/// TP / SL on a manual trade.
class _QuoteChip extends StatelessWidget {
  const _QuoteChip({required this.quote, required this.loading});

  final ({double price, double changePct, String source, String marketState})?
      quote;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    if (quote == null && loading) {
      return Padding(
        padding: const EdgeInsets.only(left: 4, top: 4),
        child: Row(
          children: [
            const SizedBox(
              width: 12,
              height: 12,
              child: CircularProgressIndicator(
                strokeWidth: 1.5,
                color: AmiColors.textLow,
              ),
            ),
            const SizedBox(width: 8),
            Text('fetching live price…',
                style: AmiTypography.caption.copyWith(color: AmiColors.textLow)),
          ],
        ),
      );
    }
    final q = quote;
    if (q == null) return const SizedBox.shrink();
    final isLive = q.source.toLowerCase().contains('yfinance') ||
        q.source.toLowerCase().contains('yahoo');
    final changeColor = q.changePct >= 0 ? AmiColors.hexGreen : AmiColors.hexAmber;
    final changeSign = q.changePct >= 0 ? '+' : '';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AmiColors.slate900,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Row(
        children: [
          Text('\$${q.price.toStringAsFixed(2)}',
              style: AmiTypography.statMid.copyWith(color: AmiColors.textHigh)),
          if (q.changePct != 0) ...[
            const SizedBox(width: 8),
            Text(
              '$changeSign${q.changePct.toStringAsFixed(2)}%',
              style: AmiTypography.labelMono.copyWith(
                color: changeColor,
                fontSize: 11,
              ),
            ),
          ],
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: (isLive ? AmiColors.hexGreen : AmiColors.hexAmber)
                  .withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              isLive ? 'LIVE' : 'MOCK',
              style: AmiTypography.labelMono.copyWith(
                color: isLive ? AmiColors.hexGreen : AmiColors.hexAmber,
                fontSize: 9,
              ),
            ),
          ),
          if (q.marketState.toUpperCase() == 'CLOSED') ...[
            const SizedBox(width: 4),
            Text(
              'CLOSED',
              style: AmiTypography.labelMono.copyWith(
                color: AmiColors.textLow,
                fontSize: 9,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
