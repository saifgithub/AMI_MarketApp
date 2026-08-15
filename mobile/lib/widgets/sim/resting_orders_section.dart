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

/// CR186 — what kind of order this is, on the card.
///
/// A buy limit at $190 and a buy stop at $190 are opposite orders: one waits for
/// a fall, the other for a rise. The book used to render them as the identical
/// card, so the single fact that distinguishes them was stated once in the
/// ticket at placement and never again.
String restingOrderTypeLabel(AppLocalizations l, SimOrderType t) => switch (t) {
      SimOrderType.limit => l.restingOrderTypeLimit,
      SimOrderType.stop => l.restingOrderTypeStop,
      SimOrderType.stopLimit => l.restingOrderTypeStopLimit,
      // MARKET never rests, so it never reaches the book. If one ever does, it
      // is as unrecognised as a type from a newer server — say nothing specific
      // rather than name a type the order does not have.
      _ => l.restingOrderTypeUnknown,
    };

/// The clause after the type tag: what this order is waiting for, in the
/// direction it actually waits.
///
/// Deliberately does NOT repeat the ticker or the quantity — both are on the
/// line above — and deliberately reuses `restsBelow`, the same pure predicate
/// the ticket's live hint runs on, so the book cannot describe an order
/// differently from the sheet that placed it.
String? restingOrderIntentLine(AppLocalizations l, SimRestingOrder o) {
  if (!o.isLive) return null;
  final named = o.namedPrice;
  if (named == null) return null;

  // A triggered stop-limit has stopped waiting for its trigger. Describing it
  // as still waiting for a price it already reached is the one sentence on this
  // card that would be actively false.
  if (o.state == RestingOrderState.triggered && o.limitPrice != null) {
    return l.restingOrderTriggeredNowLimit(o.limitPrice!.toStringAsFixed(2));
  }

  final waits = restsBelow(side: o.side, orderType: o.orderType)
      ? l.restingOrderWaitsForFall(named.toStringAsFixed(2))
      : l.restingOrderWaitsForRise(named.toStringAsFixed(2));

  if (o.orderType == SimOrderType.stopLimit && o.limitPrice != null) {
    return '$waits, ${l.restingOrderThenLimit(o.limitPrice!.toStringAsFixed(2))}';
  }
  return waits;
}

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
    final intent = restingOrderIntentLine(l, order);

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
          // CR186 — the type, and what this order is actually waiting for.
          // Without the first the book cannot tell a buy limit from a buy stop;
          // without the second a stop-limit's limit price — the number that
          // decides whether it ever fills — appears nowhere in the app after
          // the ticket closes.
          const SizedBox(height: 6),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                restingOrderTypeLabel(l, order.orderType),
                style: AmiTypography.labelMono
                    .copyWith(fontSize: 10, color: AmiColors.textMed),
              ),
              if (intent != null) ...[
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    intent,
                    style: AmiTypography.caption
                        .copyWith(color: AmiColors.textMed),
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Expanded(
                child: Text(
                  _subtitle(context, l),
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

  String _subtitle(BuildContext context, AppLocalizations l) {
    if (!order.isLive) {
      final head = order.state == RestingOrderState.filled &&
              order.fillPrice != null
          ? '${restingOrderStateLabel(l, order.state)} @ '
              '\$${order.fillPrice!.toStringAsFixed(2)}'
          : restingOrderStateLabel(l, order.state);
      // CR186 — when it ended. A closed order with no date is a fact with no
      // place in time, and this group is headed RECENTLY CLOSED.
      final ago = _retiredAgo(l);
      return ago == null ? head : '$head · $ago';
    }
    // Null before the first sweep — say so rather than render a zero distance,
    // which would read as "about to fill".
    final head = order.lastSeenPrice == null || order.distancePct == null
        ? l.restingOrderWaitingFirstCheck
        : l.restingOrderAway(order.distancePct!.abs().toStringAsFixed(1));
    final expiry = _expiry(context, l);
    return expiry == null ? head : '$head · $expiry';
  }

  /// CR186 — when this order dies.
  ///
  /// `expiresAt` and `tif` were both parsed into the model from the day it
  /// landed and neither reached a pixel, so a DAY order dying at the next
  /// session close looked exactly like a 90-day order. The server anchors every
  /// expiry to a **market session** close, never to local midnight, so the
  /// same-day case shows the clock time rather than the word "today" alone —
  /// for a user outside the US the two are routinely different days.
  String? _expiry(BuildContext context, AppLocalizations l) {
    final at = order.expiresAt;
    if (at == null) return null;
    final left = at.difference(DateTime.now());
    if (left.isNegative) return null;
    if (left.inHours < 24) {
      return l.restingOrderExpiresToday(
        TimeOfDay.fromDateTime(at).format(context),
      );
    }
    return l.restingOrderExpiresInDays('${left.inDays}');
  }

  /// CR186 — how long ago a closed order left the book, off DEF309's
  /// `retired_at`. Null on a build talking to a server that predates it, which
  /// renders as no date rather than as a wrong one.
  String? _retiredAgo(AppLocalizations l) {
    final at = order.retiredAt;
    if (at == null) return null;
    final d = DateTime.now().difference(at);
    if (d.isNegative || d.inMinutes < 1) return l.restingOrderRetiredJustNow;
    if (d.inMinutes < 60) return l.restingOrderRetiredMinutesAgo('${d.inMinutes}');
    if (d.inHours < 24) return l.restingOrderRetiredHoursAgo('${d.inHours}');
    return l.restingOrderRetiredDaysAgo('${d.inDays}');
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
