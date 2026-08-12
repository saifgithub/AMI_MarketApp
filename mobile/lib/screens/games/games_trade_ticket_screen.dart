/// CR109 slice 2 — the game's 3-tap trade ticket (design §5.4, Amendment D).
///
/// TAP 1 — a ticker chip. TAP 2 — a size chip; 25% renders as the visually
/// -default choice (§5.4: "not a rule and not a block — choice
/// architecture... it costs a border colour"). TAP 3 — the confirm card:
/// shares, est. fee, book-percentage, fetched with ONE network call
/// ([GamesTicketNotifier.fetchQuote]) fired on arrival at this step — the
/// size chips themselves priced locally with zero round trips. Reached
/// only from the State-B run card's "Trade" action
/// (`games_home_screen.dart`) — the sole place this ticket is reachable
/// this slice.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/games/games_queue_note.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:ami_trade/widgets/sheet_insets.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// §5.4's size-chip row — a percentage of the run's current cash.
const List<double> kGamesTicketSizeChipPcts = [10, 25, 50, 100];

/// §5.4: "The 25% chip renders as the visually-default choice." Choice
/// architecture, not a rule — every chip stays fully selectable.
const double kGamesTicketDefaultSizePct = 25;

class GamesTradeTicketScreen extends ConsumerStatefulWidget {
  const GamesTradeTicketScreen({
    super.key,
    required this.runId,
    this.sellTicker,
    this.heldQuantity,
    this.coverTicker,
    this.coverQuantity,
  });

  final String runId;

  /// Non-null opens the ticket straight into SELL mode on that position:
  /// ticker pre-picked, size chips meaning "percent of the position", and no
  /// ticker input at all — you cannot sell something you do not hold, so
  /// offering a free-text field there would only be a way to get an error.
  final String? sellTicker;

  /// Shares currently held of [sellTicker]. The sell sizes against this, not
  /// against cash: "50%" means half the shares, and 100% closes the position.
  final double? heldQuantity;

  /// Non-null opens the ticket straight into COVER mode on an open short —
  /// CR109 Amendment G. There is no size step: the backend accepts a cover
  /// of the whole position or nothing, so a percentage here would be a
  /// choice the server refuses.
  final String? coverTicker;

  /// Shares short in [coverTicker] — the exact quantity the cover buys back.
  final double? coverQuantity;

  static Future<void> show(
    BuildContext context, {
    required String runId,
    String? sellTicker,
    double? heldQuantity,
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
      builder: (_) => GamesTradeTicketScreen(
        runId: runId,
        sellTicker: sellTicker,
        heldQuantity: heldQuantity,
        coverTicker: coverTicker,
        coverQuantity: coverQuantity,
      ),
    );
  }

  @override
  ConsumerState<GamesTradeTicketScreen> createState() =>
      _GamesTradeTicketScreenState();
}

class _GamesTradeTicketScreenState
    extends ConsumerState<GamesTradeTicketScreen> {
  final _manualTicker = TextEditingController();

  bool get _isSell => widget.sellTicker != null;
  bool get _isCover => widget.coverTicker != null;

  /// The share count the size picker divides. Null in the opening modes,
  /// where the denominator is cash rather than a position.
  double? get _positionQuantity =>
      _isCover ? widget.coverQuantity : widget.heldQuantity;

  @override
  void initState() {
    super.initState();
    final target = widget.coverTicker ?? widget.sellTicker;
    if (target == null) return;
    final mode = _isCover ? 'cover' : 'sell';
    // Same Riverpod constraint the confirm card documents: a provider's state
    // cannot be written synchronously inside a life-cycle method. Side FIRST,
    // then ticker — `pickSide` rebuilds the state keeping the ticker and
    // `pickTicker` rebuilds it keeping the side, so the other order would
    // work too, but this one reads as what it is: choose the direction, then
    // name the instrument.
    Future.microtask(() {
      if (!mounted) return;
      final notifier = ref.read(gamesTicketProvider(widget.runId).notifier);
      notifier.pickMode(mode);
      notifier.pickTicker(target);
    });
  }

  @override
  void dispose() {
    _manualTicker.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final ticket = ref.watch(gamesTicketProvider(widget.runId));
    final notifier = ref.read(gamesTicketProvider(widget.runId).notifier);
    // `.valueOrNull`, NOT `.asData?.value`. Every placed order and every
    // cancel calls `ref.invalidate(gamesRunDetailProvider)`, and during the
    // refetch that follows, an `AsyncLoading` carrying the previous value
    // still answers `asData` with NULL. The `?? 0` below then sized the next
    // order against zero cash and the API — correctly — refused it with a
    // 422, which the player read as "suddenly this does not work". It worked
    // until the first order, then broke for every one after it.
    //
    // `valueOrNull` returns the value a refresh is carrying forward, so the
    // ticket keeps showing the cash it last knew about instead of pretending
    // there is none.
    final runDetail = ref.watch(gamesRunDetailProvider(widget.runId)).valueOrNull;
    final watchlist = ref.watch(watchlistNotifierProvider).items;

    return Padding(
      padding: EdgeInsets.fromLTRB(
        AmiSpacing.l,
        AmiSpacing.l,
        AmiSpacing.l,
        AmiSpacing.l + sheetBottomInset(MediaQuery.of(context)),
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // The queue-first rule used to print as a three-line paragraph
            // here AND again on the confirm card — twice on one ticket.
            // Standing copy that never changes stops being read, so it is now
            // one tap away behind the ⓘ rather than permanently occupying the
            // top of the sheet. Same string, same widget file: one source of
            // copy, two presentations, so they cannot drift.
            if (_isSell) ...[
              Text(
                l.gamesSellTitle(widget.sellTicker!),
                style: AmiTypography.h4.copyWith(color: AmiColors.textHigh),
              ),
              const SizedBox(height: AmiSpacing.xs),
              if (widget.heldQuantity != null)
                // The denominator, made visible. A percentage with no stated
                // base is the same defect as the slider that said 25% while
                // the confirm card said 11.9% — two numbers, two bases, one
                // screen.
                Text(
                  l.gamesSellHeld(widget.heldQuantity!.toStringAsFixed(4)),
                  style: AmiTypography.caption,
                ),
              const SizedBox(height: AmiSpacing.xs),
              // Stated here rather than discovered as a rejected order: the
              // fill path refuses a sell beyond the held quantity, so one
              // order can never close this and open a short in its place.
              // Since Amendment F shorting DOES exist — the note now points
              // at how to do it instead of saying it cannot be done.
              Text(l.gamesSellClosesOnlyNote, style: AmiTypography.caption),
              const SizedBox(height: AmiSpacing.s),
            ],
            if (_isCover) ...[
              Text(
                l.gamesCoverTitle(widget.coverTicker!),
                style: AmiTypography.h4.copyWith(color: AmiColors.textHigh),
              ),
              const SizedBox(height: AmiSpacing.xs),
              if (widget.coverQuantity != null)
                Text(
                  l.gamesCoverShortOf(
                      widget.coverQuantity!.toStringAsFixed(4)),
                  style: AmiTypography.caption,
                ),
              const SizedBox(height: AmiSpacing.xs),
              // Why there is no size picker below. Without this the missing
              // step reads as a bug rather than as the rule it is.
              Text(l.gamesCoverWholeOnlyNote, style: AmiTypography.caption),
              const SizedBox(height: AmiSpacing.s),
            ],
            Row(
              children: [
                Text(
                  (_isSell || _isCover) ? '' : l.gamesTicketHeading,
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.hexGreen),
                ),
                const SizedBox(width: AmiSpacing.xs),
                const GamesQueueInfoIcon(),
              ],
            ),
            const SizedBox(height: AmiSpacing.l),

            // What you are sizing AGAINST, before you size anything. This
            // figure used to appear only on the step-3 confirm card, so a
            // player had to commit to a percentage to discover what the
            // percentage was of.
            _CashHeader(detail: runDetail),
            const SizedBox(height: AmiSpacing.l),

            // TAP 0 — direction. Not a step in the §5.4 sense (it has a
            // default and never blocks progress), but it must sit ABOVE the
            // ticker: which way you are going changes what the size chips
            // mean, and a control that retroactively reinterprets a number
            // the player already chose is the defect this ordering avoids.
            if (!_isSell && !_isCover) ...[
              Text(l.gamesTicketStepDirection, style: AmiTypography.caption),
              const SizedBox(height: AmiSpacing.xs),
              Row(
                children: [
                  _pickerChip(
                    label: l.gamesDirectionLong,
                    selected: ticket.mode == 'buy',
                    onTap: () => notifier.pickMode('buy'),
                  ),
                  const SizedBox(width: AmiSpacing.s),
                  _pickerChip(
                    label: l.gamesDirectionShort,
                    selected: ticket.mode == 'short',
                    onTap: () => notifier.pickMode('short'),
                  ),
                ],
              ),
              if (ticket.mode == 'short') ...[
                const SizedBox(height: AmiSpacing.xs),
                // The cost, before the size is picked rather than on the
                // confirm card alone. 0.3% is three times the ordinary fee,
                // and a player who discovers that at the confirm step has
                // already decided.
                Text(l.gamesShortFeeNote, style: AmiTypography.caption),
                const SizedBox(height: AmiSpacing.xs),
                // A short posts its FULL value — the sentence that explains
                // why the slider below divides cash exactly as a buy's does,
                // which is the thing Saiful read as the ticket behaving "as
                // if I am buying" (DEF272). It is not a bug, it is the
                // no-leverage rule, and it was nowhere on this screen.
                Text(l.gamesShortCollateralNote, style: AmiTypography.caption),
                const SizedBox(height: AmiSpacing.xs),
                // The one thing about a short that is not true of anything
                // else in this app. Said plainly, once.
                //
                // REWRITTEN for Amendment I. It used to read "A short can
                // lose more than it ties up. There is no floor." — which the
                // forced buy-in made FALSE the day it shipped. That is the
                // same trap `gamesNoShortingNote` fell into: copy asserting a
                // rule as a fact, left behind by the amendment that changed
                // the rule. There is a floor now; it is stated with the gap
                // that can still jump it, because promising a hard cap we do
                // not have would be the worse error of the two.
                Text(
                  l.gamesShortRiskNote,
                  style: AmiTypography.caption
                      .copyWith(color: AmiColors.hexRed),
                ),
              ],
              const SizedBox(height: AmiSpacing.l),
            ],

            // TAP 1 — ticker.
            Text(l.gamesTicketStepTicker, style: AmiTypography.caption),
            const SizedBox(height: AmiSpacing.xs),
            Wrap(
              spacing: AmiSpacing.s,
              runSpacing: AmiSpacing.s,
              children: [
                for (final w in watchlist.take(6))
                  _pickerChip(
                    label: w.ticker,
                    selected: ticket.ticker == w.ticker,
                    onTap: () => notifier.pickTicker(w.ticker),
                  ),
                SizedBox(
                  width: 100,
                  child: TextField(
                    controller: _manualTicker,
                    textCapitalization: TextCapitalization.characters,
                    style: AmiTypography.bodySm,
                    decoration: InputDecoration(
                      isDense: true,
                      hintText: l.gamesTicketTickerHint,
                      hintStyle: AmiTypography.caption,
                      filled: true,
                      fillColor: AmiColors.slate900,
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 10),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(AmiRadii.card),
                        borderSide:
                            const BorderSide(color: AmiColors.slate700),
                      ),
                    ),
                    onSubmitted: notifier.pickTicker,
                  ),
                ),
              ],
            ),

            // NOTHING LEFT TO DEPLOY. Distinct from "cash is still loading":
            // `runDetail` is non-null here, so this figure is known, and it is
            // zero. Every step past ticker-picking is meaningless — there is
            // no size to pick and no quote to fetch.
            //
            // Saiful hit the earlier version of this: he had 10,003.29
            // committed to 8 queued orders, 0.00 available, and the confirm
            // card sat spinning. That spinner came from THIS MORNING's fix,
            // which taught `fetchQuote` to stay in the loading state rather
            // than fire a request that must 422 — correct while cash is
            // ARRIVING, and a lie once it has arrived and is zero. The two
            // cases look identical to a function that only receives a double,
            // which is why the screen now decides and the notifier takes a
            // nullable value.
            // A SELL is never blocked by an empty cash balance — that is
            // precisely the state a player most needs to close a position
            // from, and gating it behind cash is what made the book one-way.
            //
            // A SHORT is gated the same way a buy is: it ties up the full
            // notional (no leverage — see the backend's
            // `trading_math/shorts.py`), so an empty balance means it cannot
            // be opened either. A COVER never is, for the same reason a sell
            // never is: the cash to buy back was posted when the short was
            // opened, and a player with an unbounded-loss position open must
            // always be able to close it.
            if (!_isSell &&
                !_isCover &&
                runDetail != null &&
                runDetail.cashAvailable <= 0)
              _NoCashPanel(detail: runDetail)
            else if (_isCover)
              const SizedBox.shrink()
            else if (ticket.ticker != null) ...[
              const SizedBox(height: AmiSpacing.l),
              // TAP 2 — size, % of current cash (§5.4: priced locally,
              // zero round trips). The chips are quick presets; the slider
              // is the real control, because 10/25/50/100 could not express
              // "a bit" — the smallest possible order was a tenth of the
              // book.
              Text(
                _isSell
                    ? l.gamesTicketStepSizeSell
                    : (ticket.mode == 'short'
                        ? l.gamesTicketStepSizeShort
                        : l.gamesTicketStepSize),
                style: AmiTypography.caption,
              ),
              const SizedBox(height: AmiSpacing.xs),
              _SizePicker(
                sizePct: ticket.sizePct ?? kGamesTicketDefaultSizePct,
                cashAvailable: runDetail?.cashAvailable ?? 0,
                // Only a SELL divides a position. A short divides cash, like
                // a buy — passing the held quantity here would size it
                // against a position that does not exist yet.
                heldQuantity: _isSell ? widget.heldQuantity : null,
                // DEF272 — the readout said "{pct}% · {amount} AMI Cash" for
                // a short, which reads as money SPENT. Nothing is spent: the
                // amount is posted as collateral and comes back on the cover.
                // Same number, and the wrong noun for it.
                isShort: ticket.mode == 'short',
                onChanged: notifier.pickSize,
              ),
            ],

            if (ticket.step == 3) ...[
              const SizedBox(height: AmiSpacing.l),
              // TAP 3 — confirm.
              Text(l.gamesTicketStepConfirm, style: AmiTypography.caption),
              const SizedBox(height: AmiSpacing.s),
              _ConfirmCard(
                ticket: ticket,
                notifier: notifier,
                cashAvailable: runDetail?.cashAvailable,
                heldQuantity: _positionQuantity,
              ),
            ],

            if (ticket.error != null) ...[
              const SizedBox(height: AmiSpacing.s),
              Text(
                ticket.error!,
                style:
                    AmiTypography.caption.copyWith(color: AmiColors.hexRed),
              ),
            ],

            if (ticket.result != null) ...[
              const SizedBox(height: AmiSpacing.m),
              _ResultBanner(result: ticket.result!),
            ],
          ],
        ),
      ),
    );
  }

}

/// The fee as a percentage of this order's own notional, or null when it is
/// close enough to the headline rate to be unremarkable — DEF274.
///
/// The threshold is **1%**, ten times the ordinary 0.1%. Below it the fee is
/// behaving like the rate the ticket already states and a second line saying
/// so is noise; at or above it, `FEE_MIN`'s floor is what the player is
/// actually paying and the stated rate has stopped describing their trade.
///
/// Null-safe on a zero notional: a quote that priced nothing has no drag to
/// report, and 0/0 would render as `NaN%` — a number that means nothing on a
/// card whose whole job is to be checkable.
double? _feeDragPct(GameTradeQuote q) {
  if (q.notional <= 0) return null;
  final pct = (q.estFee / q.notional) * 100;
  return pct >= 1.0 ? pct : null;
}

/// Shared by the ticker row and the size presets — both are the same
/// hex-chip affordance, and CR134 requires hex geometry for controls.
Widget _pickerChip({
  required String label,
  required bool selected,
  required VoidCallback onTap,
}) {
  return GestureDetector(
    onTap: onTap,
    child: HexChip(
      label: label,
      color: selected ? AmiColors.hexGreen : AmiColors.slate600,
      variant: selected ? HexChipVariant.filled : HexChipVariant.outlined,
    ),
  );
}

/// What this ticket may actually spend, at the TOP of the ticket.
///
/// Two defects landed here in two builds. On build 71 the figure existed
/// only on the step-3 confirm card, so you had to commit to a size before
/// you could see what you were sizing against — Saiful: *"I have no idea how
/// much funds i have."* On build 74 the figure was there but it was
/// `current_cash`, which queued orders never touch, so a second order was
/// still offered the whole 10,000 the first one had already spoken for.
///
/// It now shows `cash_available` — cash minus everything committed to orders
/// waiting on the open — and, when they differ, says why in the line below.
/// Both numbers, or the difference is just an unexplained shortfall.
class _CashHeader extends StatelessWidget {
  const _CashHeader({required this.detail});

  final GameRunDetail? detail;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final d = detail;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(l.gamesTicketCashAvailable, style: AmiTypography.caption),
            Text(
              d == null ? '—' : _money(d.cashAvailable),
              style:
                  AmiTypography.labelMono.copyWith(color: AmiColors.textHigh),
            ),
          ],
        ),
        if (d != null && d.cashCommitted > 0) ...[
          const SizedBox(height: 2),
          Text(
            l.gamesTicketCashCommitted(
              _money(d.cashCommitted),
              d.queuedOrderCount,
            ),
            style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber),
          ),
        ],
      ],
    );
  }
}

String _money(double v) {
  final fixed = v.toStringAsFixed(2);
  final parts = fixed.split('.');
  final digits = parts[0];
  final buf = StringBuffer();
  for (var i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 == 0) buf.write(',');
    buf.write(digits[i]);
  }
  return '${buf.toString()}.${parts[1]}';
}

/// TAP 2 — position size.
///
/// A slider from 1% to 100%, plus the original chips as quick presets.
/// Saiful, on build 71: *"I can't buy less then 10%"* and *"The steps are too
/// large."* The four chips (10/25/50/ALL-IN) made a tenth of the book the
/// SMALLEST expressible order, which is a large first position and no way to
/// dip a toe.
///
/// The percentage is applied to cash locally, with no round trip (§5.4), so
/// the money readout tracks the drag immediately. The quote is only fetched
/// once the drag ENDS — dragging would otherwise fire a request per frame.
class _SizePicker extends StatefulWidget {
  const _SizePicker({
    required this.sizePct,
    required this.cashAvailable,
    required this.onChanged,
    this.heldQuantity,
    this.isShort = false,
  });

  final double sizePct;
  final double cashAvailable;

  /// Changes the READOUT only, never the arithmetic. A short divides cash
  /// exactly as a buy does (no leverage — it posts its full notional), so
  /// the number is identical; what differs is that the cash is posted as
  /// collateral rather than spent, and calling it the same thing as a buy is
  /// what made the ticket read as "behaving as if I am buying" (DEF272).
  final bool isShort;
  /// Non-null puts the picker in SELL mode: the percentage divides the
  /// POSITION rather than the cash, and the readout is shares rather than
  /// AMI Cash. Showing a dollar figure here would be actively misleading —
  /// the proceeds depend on the fill price, which for a queued order is not
  /// known until the next open.
  final double? heldQuantity;
  final ValueChanged<double> onChanged;

  @override
  State<_SizePicker> createState() => _SizePickerState();
}

class _SizePickerState extends State<_SizePicker> {
  double? _dragging;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final pct = _dragging ?? widget.sizePct;
    final held = widget.heldQuantity;
    final amount = widget.cashAvailable * (pct / 100.0);
    final shares = held == null ? null : held * (pct / 100.0);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: AmiSpacing.s,
          children: [
            for (final preset in kGamesTicketSizeChipPcts)
              _pickerChip(
                label: preset == 100
                    ? (held == null
                        ? l.gamesTicketSizeAllIn
                        : l.gamesTicketSizeCloseAll)
                    : '${preset.toInt()}%',
                selected: pct == preset,
                onTap: () {
                  setState(() => _dragging = null);
                  widget.onChanged(preset);
                },
              ),
          ],
        ),
        SliderTheme(
          data: SliderTheme.of(context).copyWith(
            activeTrackColor: AmiColors.hexGreen,
            inactiveTrackColor: AmiColors.slate600,
            thumbColor: AmiColors.hexGreen,
            overlayColor: AmiColors.hexGreen.withValues(alpha: 0.15),
            valueIndicatorColor: AmiColors.slate600,
          ),
          child: Slider(
            value: pct.clamp(1, 100),
            min: 1,
            max: 100,
            // 1% granularity: 99 steps between 1 and 100.
            divisions: 99,
            label: '${pct.round()}%',
            onChanged: (v) => setState(() => _dragging = v),
            onChangeEnd: (v) {
              setState(() => _dragging = null);
              widget.onChanged(v.roundToDouble());
            },
          ),
        ),
        Text(
          shares != null
              ? l.gamesTicketSizeShares(
                  pct.round().toString(),
                  shares.toStringAsFixed(4),
                )
              : (widget.isShort
                  ? l.gamesTicketSizeCollateral(
                      pct.round().toString(), _money(amount))
                  : l.gamesTicketSizeAmount(
                      pct.round().toString(), _money(amount))),
          style: AmiTypography.caption.copyWith(color: AmiColors.textHigh),
        ),
      ],
    );
  }
}

class _ConfirmCard extends ConsumerStatefulWidget {
  const _ConfirmCard({
    required this.ticket,
    required this.notifier,
    required this.cashAvailable,
    this.heldQuantity,
  });

  final GamesTicketState ticket;
  final GamesTicketNotifier notifier;
  /// Shares held, on a sell. The notifier sizes the order from this.
  final double? heldQuantity;
  /// Null means the run detail has not arrived yet — NOT that cash is zero.
  /// The difference decides between a spinner and a refusal.
  final double? cashAvailable;

  @override
  ConsumerState<_ConfirmCard> createState() => _ConfirmCardState();
}

class _ConfirmCardState extends ConsumerState<_ConfirmCard> {
  @override
  void initState() {
    super.initState();
    if (widget.ticket.quote == null && !widget.ticket.quoting) {
      // Riverpod forbids writing a provider's state synchronously inside a
      // widget life-cycle method (initState/build/dispose/...) — even
      // though fetchQuote is `async`, its first line runs before the first
      // `await`, which lands inside THIS call frame. `Future.microtask`
      // defers it to after the frame finishes building, per Riverpod's own
      // fix for this exact error.
      Future.microtask(
        () => widget.notifier.fetchQuote(
          cashAvailable: widget.cashAvailable,
          heldQuantity: widget.heldQuantity,
        ),
      );
    }
  }

  @override
  void didUpdateWidget(covariant _ConfirmCard old) {
    super.didUpdateWidget(old);
    // The user backed up and tapped a different size chip while this card
    // stayed mounted — re-quote against the new pick rather than confirming
    // a stale one.
    if (old.ticket.sizePct != widget.ticket.sizePct &&
        widget.ticket.sizePct != null &&
        widget.ticket.quote == null &&
        !widget.ticket.quoting) {
      Future.microtask(
        () => widget.notifier.fetchQuote(
          cashAvailable: widget.cashAvailable,
          heldQuantity: widget.heldQuantity,
        ),
      );
    }
    // Cash has ARRIVED. The card can mount before the run detail resolves —
    // routinely so, because placing an order invalidates that provider — and
    // `fetchQuote` refuses to quote against zero rather than sending a request
    // the API must reject. Nothing is in flight in that state, so this is what
    // starts the real one.
    if (widget.heldQuantity == null &&
        (old.cashAvailable ?? 0) <= 0 &&
        (widget.cashAvailable ?? 0) > 0 &&
        widget.ticket.quote == null) {
      Future.microtask(
        () => widget.notifier.fetchQuote(
          cashAvailable: widget.cashAvailable,
          heldQuantity: widget.heldQuantity,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final t = widget.ticket;
    if (t.quoting) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: AmiSpacing.m),
        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    if (t.quote == null) {
      // No quote and nothing in flight. This used to fall into the spinner
      // above, so a FAILED quote left a progress indicator turning under the
      // error message for as long as the sheet stayed open — the app showing
      // work it was not doing, with no way to try again short of re-picking a
      // size. Saiful hit it when the Cloudflare tunnel dropped all four edge
      // connectors for ~70s and his phone got a 502.
      //
      // An error gets a retry. No error yet means the first fetch has not
      // reached its microtask, which is genuinely a moment of loading.
      if (t.error == null) {
        return const Padding(
          padding: EdgeInsets.symmetric(vertical: AmiSpacing.m),
          child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
        );
      }
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
        child: SizedBox(
          width: double.infinity,
          child: HexButton(
            label: l.gamesRetry.toUpperCase(),
            color: AmiColors.hexGreen,
            onPressed: () => widget.notifier
                .fetchQuote(cashAvailable: widget.cashAvailable),
          ),
        ),
      );
    }
    final q = t.quote!;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate900,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // A modeled-cost / book-% mirror surface (CR134 §21): colour-
          // neutral, no amber — measurement, never a scold.
          // Price per share leads. Saiful, on build 76: *"We need the price
          // per unit."* The card showed a share count and a total cost with
          // nothing to check either against — and it is the first number a
          // trader reads, because it is the only one that says whether the
          // trade is a good idea.
          _row(l.gamesTicketPricePerShare, '\$${_money(q.price)}'),
          _row(l.gamesTicketShares, q.shares.toStringAsFixed(4)),
          _row(l.gamesTicketEstFee, '\$${q.estFee.toStringAsFixed(2)}'),
          _row(l.gamesTicketBookPct, '${q.bookPercentage.toStringAsFixed(1)}%'),
          // DEF274 — what the fee actually costs THIS order, when the
          // minimum is doing the work.
          //
          // Saiful's run held 4.09 against a 10,000 book. The slider happily
          // offered 100% of it, and the ticket priced the trade at "est. fee
          // $1.00" — true, unremarkable next to a 10bps rate, and in fact
          // **24% of the trade**. `FEE_MIN` is a floor, so the smaller the
          // order the larger the bite, and the one number that says so was
          // the one number not on the card.
          //
          // Stated, NOT blocked. §7.1's frictions doctrine is explicit that
          // "nothing caps what a player may do" and Saiful took the
          // price-shaped escalator over a prohibition when he was asked
          // (Amendment D). A cap here would be the rule he rejected; this is
          // the price, made legible.
          if (_feeDragPct(q) != null) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(
              l.gamesTicketFeeDrag(_feeDragPct(q)!.toStringAsFixed(1)),
              style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber),
            ),
          ],
          // What that price IS. A quote on a queued order is the last live
          // price, not the price the order will get — and if the feed fell
          // through to the mock walk it is not even that. One line, and only
          // when there is something to say: a price that will fill at itself,
          // from a live feed, needs no caveat.
          if (!q.priceIsLive || q.mayQueue) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(
              q.priceIsLive
                  ? l.gamesTicketPriceAsOfLive
                  : l.gamesTicketPriceSimulated,
              style: AmiTypography.caption.copyWith(
                color: q.priceIsLive ? AmiColors.textLow : AmiColors.hexAmber,
              ),
            ),
          ],
          const SizedBox(height: AmiSpacing.m),
          SizedBox(
            width: double.infinity,
            child: HexButton(
              label: (t.submitting
                      ? l.gamesTicketPlacing
                      : l.gamesTicketConfirmCta)
                  .toUpperCase(),
              color: AmiColors.hexGreen,
              onPressed: t.submitting
                  ? null
                  : () async {
                      final result = await widget.notifier.confirm();
                      if (result != null && mounted) {
                        HapticFeedback.mediumImpact();
                      }
                    },
            ),
          ),
        ],
      ),
    );
  }

  Widget _row(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: AmiTypography.caption),
            Text(value, style: AmiTypography.dataMd),
          ],
        ),
      );
}

class _ResultBanner extends StatelessWidget {
  const _ResultBanner({required this.result});
  final GameTradeResult result;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    // Queued is the NORMAL outcome for most of the target audience (§5.1) —
    // styled identically to a fill, never as a warning.
    //
    // THREE states, not two. This read `isQueued ? queued : filled`, so an
    // outcome the client could not identify rendered as "Filled." — a
    // positive claim about a position in a scored contest, asserted with no
    // evidence. An unknown outcome now says so, and says it in amber rather
    // than the confident green, because it is the one case where the player
    // must go and look.
    final unknown = !result.isQueued && !result.isFilled;
    final accent = unknown ? AmiColors.hexAmber : AmiColors.hexGreen;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: accent.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: accent.withValues(alpha: 0.5)),
      ),
      child: Text(
        unknown
            ? l.gamesTicketUnknownNote
            : result.isQueued
                ? l.gamesTicketQueuedNote
                : l.gamesTicketFilledNote,
        style: AmiTypography.body,
      ),
    );
  }
}

/// Every AMI Cash unit is spoken for. Not a loading state, not an error —
/// a fact about the book, with the one action that changes it.
///
/// Saiful, on build 78: *"I was trying to add a trade when I have no funds
/// left. I was waiting with a spinner for a while. I think this is an
/// unhandled error."* It was: the ticket could not tell "cash has not
/// arrived" from "cash is zero", so it waited for a number that had already
/// come. A zero balance is not a thing to wait for.
class _NoCashPanel extends StatelessWidget {
  const _NoCashPanel({required this.detail});

  final GameRunDetail detail;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate900,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexAmber.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l.gamesTicketNoCashHeading, style: AmiTypography.h4),
          const SizedBox(height: AmiSpacing.xs),
          // DEF272 — WHERE the money went is a question with two answers, and
          // this panel only ever gave one of them.
          //
          // Saiful hit the other: 4.09 free against a 10,000 book, every unit
          // of it in POSITIONS and not one queued order outstanding. The old
          // copy told him "0.00 is committed to 0 orders waiting on the next
          // open. Cancel one to free up cash" — a false statement pointing at
          // an empty list, on the screen where he had just been refused. The
          // count decides which sentence is true, so the count picks it.
          Text(
            detail.queuedOrderCount > 0
                ? l.gamesTicketNoCashBody(
                    _money(detail.cashCommitted),
                    detail.queuedOrderCount,
                  )
                : l.gamesTicketNoCashInPositionsBody,
            style: AmiTypography.body.copyWith(color: AmiColors.textLow),
          ),
          const SizedBox(height: AmiSpacing.m),
          SizedBox(
            width: double.infinity,
            child: HexButton(
              label: (detail.queuedOrderCount > 0
                      ? l.gamesTicketNoCashCta
                      : l.gamesTicketNoCashPositionsCta)
                  .toUpperCase(),
              color: AmiColors.hexAmber,
              // Both routes are the same gesture: the run screen underneath
              // carries the queued-order list AND the holdings, each with its
              // own close action. Closing IS the navigation.
              onPressed: () => Navigator.of(context).pop(),
            ),
          ),
        ],
      ),
    );
  }
}
