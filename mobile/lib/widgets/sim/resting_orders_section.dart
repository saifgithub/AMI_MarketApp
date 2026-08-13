/// CR170 §9 — the book, on the Portfolio screen.
///
/// **Above holdings**, because a working order is the most time-sensitive thing
/// on the screen: a holding can be looked at tomorrow, an order that is about to
/// fill cannot.
///
/// Terminal rows from the last 24h render in their own group rather than
/// disappearing. That is the games lane's lesson stated as a rule — its own
/// `list_queued_orders` docstring records the cost of the alternative: *"from
/// the player's side the order simply VANISHED overnight."* A refused order the
/// user never sees is a refusal that teaches nothing and reads as a bug.
///
/// **Renders nothing at all when the backend has no book** (see
/// `SimState.restingOrdersSupported`). That is a deliberate absence, not a
/// broken thing: the alternative is an empty "waiting orders" heading on every
/// portfolio in the app, which is the placeholder CR040 forbids.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim_resting_order.dart';
import 'package:ami_trade/features/sim/order_pricing.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

String restingOrderStateLabel(AppLocalizations l, RestingOrderState s) =>
    switch (s) {
      RestingOrderState.working => l.restingOrderStateWorking,
      RestingOrderState.triggered => l.restingOrderStateTriggered,
      RestingOrderState.filling => l.restingOrderStateFilling,
      RestingOrderState.filled => l.restingOrderStateFilled,
      RestingOrderState.cancelled => l.restingOrderStateCancelled,
      RestingOrderState.expired => l.restingOrderStateExpired,
      RestingOrderState.rejected => l.restingOrderStateRejected,
      RestingOrderState.unknown => l.restingOrderStateUnknown,
    };

Color restingOrderStateColor(RestingOrderState s) => switch (s) {
      RestingOrderState.working => AmiColors.hexCyan,
      RestingOrderState.triggered => AmiColors.hexAmber,
      RestingOrderState.filling => AmiColors.hexAmber,
      RestingOrderState.filled => AmiColors.hexGreen,
      RestingOrderState.cancelled => AmiColors.textLow,
      RestingOrderState.expired => AmiColors.textLow,
      RestingOrderState.rejected => AmiColors.hexRed,
      RestingOrderState.unknown => AmiColors.hexPurple,
    };

class RestingOrdersSection extends ConsumerWidget {
  const RestingOrdersSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(simNotifierProvider);
    if (!state.restingOrdersSupported) return const SizedBox.shrink();
    final live = state.liveRestingOrders;
    final settled = state.settledRestingOrders;
    if (live.isEmpty && settled.isEmpty) return const SizedBox.shrink();
    final l = AppLocalizations.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (live.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
            child: Text(l.restingOrdersHeading, style: AmiTypography.labelMono),
          ),
          for (final o in live) _RestingOrderCard(order: o),
        ],
        if (settled.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
            child: Text(
              l.restingOrdersRecentHeading,
              style:
                  AmiTypography.labelMono.copyWith(color: AmiColors.textLow),
            ),
          ),
          for (final o in settled) _RestingOrderCard(order: o),
        ],
      ],
    );
  }
}

class _RestingOrderCard extends ConsumerWidget {
  const _RestingOrderCard({required this.order});
  final SimRestingOrder order;

  Future<void> _cancel(BuildContext context, WidgetRef ref) async {
    final l = AppLocalizations.of(context);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AmiColors.slate800,
        title: Text(l.restingOrderCancelTitle, style: AmiTypography.h4),
        content: Text(
          l.restingOrderCancelBody(
            order.side.toUpperCase(),
            order.quantity.toStringAsFixed(0),
            order.ticker,
            (order.namedPrice ?? 0).toStringAsFixed(2),
          ),
          style: AmiTypography.body,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l.restingOrderKeep,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.textMed)),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(l.restingOrderCancelConfirm,
                style:
                    AmiTypography.labelMono.copyWith(color: AmiColors.hexRed)),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;

    final result =
        await ref.read(simNotifierProvider.notifier).cancelRestingOrder(order.id);
    if (!context.mounted || result == null) return;
    // The SERVER's verdict, not ours. A cancel can lose a race with the sweep,
    // and the games lane shipped `status ?? 'filled'` once already.
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      behavior: SnackBarBehavior.floating,
      backgroundColor:
          result.cancelled ? AmiColors.slate800 : AmiColors.hexAmber,
      content: Text(
        result.cancelled
            ? l.restingOrderCancelled
            : l.restingOrderCancelRaced(
                restingOrderStateLabel(l, result.state)),
        style: TextStyle(
          color: result.cancelled ? AmiColors.textHigh : AmiColors.slate900,
        ),
      ),
    ));
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final accent = restingOrderStateColor(order.state);
    final buy = order.side == 'buy';
    final named = order.namedPrice;

    return Container(
      margin: const EdgeInsets.only(bottom: AmiSpacing.s),
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: accent.withValues(alpha: 0.6)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(buy ? Icons.arrow_downward : Icons.arrow_upward,
                  size: 16, color: buy ? AmiColors.hexGreen : AmiColors.hexRed),
              const SizedBox(width: 6),
              Expanded(
                child: Directionality(
                  textDirection: TextDirection.ltr,
                  child: Text(
                    '${order.side.toUpperCase()} ${order.quantity.toStringAsFixed(0)} '
                    '${order.ticker}'
                    '${named == null ? '' : ' @ \$${named.toStringAsFixed(2)}'}',
                    style: AmiTypography.labelMono,
                  ),
                ),
              ),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: accent),
                ),
                child: Text(
                  restingOrderStateLabel(l, order.state).toUpperCase(),
                  style: AmiTypography.labelMono
                      .copyWith(fontSize: 9, color: accent),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Expanded(
                child: Text(
                  _subtitle(l),
                  style: AmiTypography.caption
                      .copyWith(color: AmiColors.textLow),
                ),
              ),
              if (order.isCancellable)
                TextButton(
                  onPressed: () => _cancel(context, ref),
                  style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                  ),
                  child: Text(l.restingOrderCancelConfirm,
                      style: AmiTypography.labelMono
                          .copyWith(fontSize: 10, color: AmiColors.hexRed)),
                ),
            ],
          ),
          // Non-null cancel_reason always means the SYSTEM refused. That
          // distinction is load-bearing for the copy, so the sentence is shown
          // verbatim rather than replaced by a state label.
          if (order.cancelReason != null) ...[
            const SizedBox(height: 6),
            Text(order.cancelReason!,
                style:
                    AmiTypography.caption.copyWith(color: AmiColors.hexRed)),
          ],
        ],
      ),
    );
  }

  String _subtitle(AppLocalizations l) {
    if (order.state == RestingOrderState.filled && order.fillPrice != null) {
      return '${restingOrderStateLabel(l, order.state)} @ '
          '\$${order.fillPrice!.toStringAsFixed(2)}';
    }
    if (!order.isLive) return restingOrderStateLabel(l, order.state);
    // Null before the first sweep — say so rather than render a zero distance,
    // which would read as "about to fill".
    if (order.lastSeenPrice == null || order.distancePct == null) {
      return l.restingOrderWaitingFirstCheck;
    }
    return l.restingOrderAway(order.distancePct!.abs().toStringAsFixed(1));
  }
}

/// Whether the ticket's controls and this section have anything to show.
/// Exported so `_NewTraderHint` cannot tell a user with a resting order that
/// they have not traded yet.
bool hasAnyRestingOrders(SimState state) =>
    state.restingOrdersSupported && state.restingOrders.isNotEmpty;

/// Re-exported so callers do not have to import `order_pricing.dart` just to
/// name an order type in a test.
typedef RestingOrderType = SimOrderType;
