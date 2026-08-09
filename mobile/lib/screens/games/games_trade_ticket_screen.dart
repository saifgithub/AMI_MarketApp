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
  const GamesTradeTicketScreen({super.key, required this.runId});

  final String runId;

  static Future<void> show(BuildContext context, {required String runId}) {
    return showModalBottomSheet<void>(
      context: context,
      backgroundColor: AmiColors.slate800,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => GamesTradeTicketScreen(runId: runId),
    );
  }

  @override
  ConsumerState<GamesTradeTicketScreen> createState() =>
      _GamesTradeTicketScreenState();
}

class _GamesTradeTicketScreenState
    extends ConsumerState<GamesTradeTicketScreen> {
  final _manualTicker = TextEditingController();

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
    final runDetail = ref.watch(gamesRunDetailProvider(widget.runId));
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
            Text(
              l.gamesTicketHeading,
              style: AmiTypography.labelMono
                  .copyWith(color: AmiColors.hexGreen),
            ),
            const SizedBox(height: AmiSpacing.m),
            const GamesQueueNote(),
            const SizedBox(height: AmiSpacing.l),

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

            if (ticket.ticker != null) ...[
              const SizedBox(height: AmiSpacing.l),
              // TAP 2 — size, % of current cash (§5.4: priced locally,
              // zero round trips).
              Text(l.gamesTicketStepSize, style: AmiTypography.caption),
              const SizedBox(height: AmiSpacing.xs),
              Wrap(
                spacing: AmiSpacing.s,
                children: [
                  for (final pct in kGamesTicketSizeChipPcts)
                    _pickerChip(
                      label: pct == 100
                          ? l.gamesTicketSizeAllIn
                          : '${pct.toInt()}%',
                      selected:
                          (ticket.sizePct ?? kGamesTicketDefaultSizePct) ==
                              pct,
                      onTap: () => notifier.pickSize(pct),
                    ),
                ],
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
                cashAvailable: runDetail.asData?.value.cash ?? 0,
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
}

class _ConfirmCard extends ConsumerStatefulWidget {
  const _ConfirmCard({
    required this.ticket,
    required this.notifier,
    required this.cashAvailable,
  });

  final GamesTicketState ticket;
  final GamesTicketNotifier notifier;
  final double cashAvailable;

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
        () => widget.notifier.fetchQuote(cashAvailable: widget.cashAvailable),
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
        () => widget.notifier.fetchQuote(cashAvailable: widget.cashAvailable),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final t = widget.ticket;
    if (t.quoting || t.quote == null) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: AmiSpacing.m),
        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
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
          _row(l.gamesTicketShares, q.shares.toStringAsFixed(4)),
          _row(l.gamesTicketEstFee, '\$${q.estFee.toStringAsFixed(2)}'),
          _row(l.gamesTicketBookPct, '${q.bookPercentage.toStringAsFixed(1)}%'),
          if (q.willQueue) ...[
            const SizedBox(height: AmiSpacing.s),
            const GamesQueueNote(),
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
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.hexGreen.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexGreen.withValues(alpha: 0.5)),
      ),
      child: Text(
        result.isQueued ? l.gamesTicketQueuedNote : l.gamesTicketFilledNote,
        style: AmiTypography.body,
      ),
    );
  }
}
