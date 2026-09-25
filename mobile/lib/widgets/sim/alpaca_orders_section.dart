/// CR234 — the Alpaca half of Portfolio's Orders/History sections.
///
/// Saiful: *"I am not seeing orders from alpaca in the orders section after
/// putting a limit buy."* The order genuinely reached Alpaca and was
/// resting there (confirmed via the CR230 audit table), but
/// `AlpacaClient` had `account()`/`positions()`/`submitOrder()` and no way
/// to list or cancel — CR233 made resting Alpaca orders possible with no
/// way to ever see or act on one again. This file is the read/cancel half.
///
/// **Only rendered when an Alpaca paper account is linked**
/// (`alpacaLinkedProvider`) — same gating `_AlpacaPortfolioSection` already
/// uses, so a user who never linked an account sees nothing extra on either
/// tab.
///
/// **Degrade loudly (CR040).** An Alpaca fetch failure renders a visible
/// "couldn't load" row, never an empty list — an empty list here would read
/// exactly like "no orders", which is the false-negative this feature
/// exists to prevent Saiful's own report from recurring as.
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart' show apiClientProvider;
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/alpaca/alpaca_badge.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
// `intl` exports its own `TextDirection` (LTR/RTL, no `.ltr` getter) that
// collides with `dart:ui`'s — hidden so `Directionality`'s parameter below
// resolves to the Flutter one, matching `resting_orders_section.dart`'s
// unqualified usage (that file doesn't import `intl` so never hits this).
import 'package:intl/intl.dart' hide TextDirection;

/// Wraps the two Alpaca sections (Orders tab's open list, History tab's
/// closed list) so both gate on the same link check without duplicating the
/// `.when` branch. `child` is built only once linked; unlinked or still
/// resolving renders nothing, matching `_AlpacaPortfolioSection`'s posture.
class _AlpacaGate extends ConsumerWidget {
  const _AlpacaGate({required this.builder});
  final WidgetBuilder builder;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final linkedAsync = ref.watch(alpacaLinkedProvider);
    return linkedAsync.when(
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
      data: (linked) => linked ? builder(context) : const SizedBox.shrink(),
    );
  }
}

/// Portfolio Orders tab — Alpaca's OPEN orders, alongside AMI's own resting
/// book (`RestingOrdersSection`, rendered above this in `_OrdersTab`).
class AlpacaOpenOrdersSection extends StatelessWidget {
  const AlpacaOpenOrdersSection({super.key});

  @override
  Widget build(BuildContext context) {
    return _AlpacaGate(builder: (context) => const _AlpacaOpenOrdersList());
  }
}

class _AlpacaOpenOrdersList extends ConsumerWidget {
  const _AlpacaOpenOrdersList();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final ordersAsync = ref.watch(alpacaOpenOrdersProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.symmetric(vertical: AmiSpacing.s),
          child: AlpacaBadge(),
        ),
        ordersAsync.when(
          loading: () => const LinearProgressIndicator(
            backgroundColor: AmiColors.slate800,
            color: AmiColors.hexCyan,
          ),
          // CR040 — a visible error row, never an empty list. Alpaca being
          // unreachable must not read as "you have no orders".
          error: (_, __) => Text(
            l.alpacaOrdersLoadError,
            style: AmiTypography.caption.copyWith(color: AmiColors.hexRed),
          ),
          data: (orders) {
            if (orders.isEmpty) {
              return Text(
                l.alpacaOrdersNone,
                style:
                    AmiTypography.caption.copyWith(color: AmiColors.textLow),
              );
            }
            return Column(
              children: [
                for (final o in orders) _AlpacaOrderCard(order: o),
              ],
            );
          },
        ),
      ],
    );
  }
}

/// Portfolio History tab — Alpaca's recently CLOSED orders (filled /
/// cancelled / expired / rejected). Rendered as its own sliver-friendly
/// widget so `_HistoryTab` can splice it in alongside the AMI transaction
/// log, same shape `_watchlistSlivers` uses for the watchlist splice.
class AlpacaHistorySection extends StatelessWidget {
  const AlpacaHistorySection({super.key});

  @override
  Widget build(BuildContext context) {
    return _AlpacaGate(builder: (context) => const _AlpacaHistoryList());
  }
}

class _AlpacaHistoryList extends ConsumerWidget {
  const _AlpacaHistoryList();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final ordersAsync = ref.watch(alpacaClosedOrdersProvider);
    return ordersAsync.when(
      loading: () => const SizedBox.shrink(),
      // CR040 — a failed fetch is the one case worth a heading + row even
      // though there is nothing to list: silence here would be
      // indistinguishable from "no Alpaca history", which is the false
      // negative this section exists to prevent.
      error: (_, __) => Padding(
        padding: const EdgeInsets.only(top: AmiSpacing.m),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const AlpacaBadge(),
            const SizedBox(height: AmiSpacing.s),
            Text(
              l.alpacaHistoryLoadError,
              style: AmiTypography.caption.copyWith(color: AmiColors.hexRed),
            ),
          ],
        ),
      ),
      data: (orders) {
        // Empty here is a legitimate, quiet state — unlike Orders, History's
        // own AMI transaction log already renders its own "no trades yet"
        // empty state above/around this, so a heading over nothing would be
        // noise. Render nothing at all, heading included.
        if (orders.isEmpty) return const SizedBox.shrink();
        return Padding(
          padding: const EdgeInsets.only(top: AmiSpacing.m),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const AlpacaBadge(),
              const SizedBox(height: AmiSpacing.s),
              for (final o in orders) _AlpacaOrderCard(order: o, closed: true),
            ],
          ),
        );
      },
    );
  }
}

/// One Alpaca order, open or closed. Mirrors `_RestingOrderCard`'s shape
/// (ticker/side/qty/price row, type + status chip, bracket legs, cancel
/// action) so the two sections read as one family despite being sourced
/// from different systems — the ticket's own "AMI SIM" / "ALPACA PAPER"
/// destination labels are the literal, un-localized strings the trade
/// ticket already uses (`trade_ticket_sheet.dart`), reused here rather than
/// invented afresh.
class _AlpacaOrderCard extends ConsumerWidget {
  const _AlpacaOrderCard({required this.order, this.closed = false});
  final AlpacaOrder order;
  final bool closed;

  Color get _accent {
    final s = order.status.toLowerCase();
    if (s == 'filled') return AmiColors.hexGreen;
    if (s == 'rejected') return AmiColors.hexRed;
    if (s == 'canceled' || s == 'cancelled' || s == 'expired') {
      return AmiColors.textLow;
    }
    return AmiColors.hexCyan;
  }

  String _priceLabel() {
    final parts = <String>[];
    if (order.limitPrice != null) {
      parts.add('LMT \$${order.limitPrice!.toStringAsFixed(2)}');
    }
    if (order.stopPrice != null) {
      parts.add('STP \$${order.stopPrice!.toStringAsFixed(2)}');
    }
    if (parts.isEmpty) return order.type?.toUpperCase() ?? 'MARKET';
    return parts.join(' · ');
  }

  Future<void> _cancel(BuildContext context, WidgetRef ref) async {
    final l = AppLocalizations.of(context);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AmiColors.slate800,
        title: Text(l.alpacaOrderCancelTitle, style: AmiTypography.h4),
        content: Text(
          l.alpacaOrderCancelBody(
            order.side.toUpperCase(),
            order.qty.toStringAsFixed(0),
            order.symbol,
          ),
          style: AmiTypography.body,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l.alpacaOrderKeep,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.textMed)),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(l.alpacaOrderCancelConfirm,
                style:
                    AmiTypography.labelMono.copyWith(color: AmiColors.hexRed)),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;

    try {
      await ref.read(alpacaClientProvider).cancelOrder(order.id);
      // CR230 — every Alpaca order interaction is logged, cancels
      // included (CR234 widened the outcome enum). Best-effort: a failed
      // report costs a log row, never the cancel itself, matching
      // `_reportOrderLog`'s own posture in `trade_ticket_sheet.dart`.
      unawaited(_reportCancel(ref, outcome: 'cancelled'));
      if (!context.mounted) return;
      ref.invalidate(alpacaOpenOrdersProvider);
      ref.invalidate(alpacaClosedOrdersProvider);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        backgroundColor: AmiColors.slate800,
        content: Text(l.alpacaOrderCancelled,
            style: const TextStyle(color: AmiColors.textHigh)),
      ));
    } on AlpacaException catch (e) {
      unawaited(_reportCancel(ref, outcome: 'rejected_by_alpaca', detail: e.detail));
      if (!context.mounted) return;
      // A lost race (already filled/cancelled) still means the order is no
      // longer open — refresh regardless of whether the cancel itself
      // "succeeded", so the list reflects Alpaca's actual current state.
      ref.invalidate(alpacaOpenOrdersProvider);
      ref.invalidate(alpacaClosedOrdersProvider);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        backgroundColor: AmiColors.hexAmber,
        content: Text(l.alpacaOrderCancelFailed(e.detail),
            style: const TextStyle(color: AmiColors.slate900)),
      ));
    } on AlpacaOrderRejected catch (_) {
      // Structural refusal — the paper-host check in `cancelOrder()` fired
      // before any network call, so nothing was sent and nothing to log
      // (unlike the `AlpacaException` branch above, which reports an
      // attempt that Alpaca itself answered). This can only happen for a
      // credential stored before DEF439 (the connect screen no longer lets a
      // live link be saved) — still surface it rather than let it die as an
      // unhandled async error, which read as the Cancel button silently
      // doing nothing (CR040).
      //
      // CR234 round-2 MINOR-4 — this used to interpolate `e.message`, the
      // raw developer-facing string `cancelOrder()` throws ("refusing to
      // cancel an order against a non-paper Alpaca host: <url>"), straight
      // into user-facing copy. Fixed copy names the actual, user-actionable
      // fact instead.
      //
      // DEF439 round 2 (auditor u66 MINOR-3) — that fixed copy was still a
      // hard-coded English literal here, so AR/MS users got an English
      // clause inside an otherwise-translated sentence (half of MINOR-4's
      // original complaint). Now an ARB key (`alpacaOrderCancelNonPaperDetail`)
      // like every other piece of user-facing copy in this file.
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        backgroundColor: AmiColors.hexAmber,
        content: Text(
            l.alpacaOrderCancelFailed(l.alpacaOrderCancelNonPaperDetail),
            style: const TextStyle(color: AmiColors.slate900)),
      ));
    }
  }

  Future<void> _reportCancel(
    WidgetRef ref, {
    required String outcome,
    String? detail,
  }) async {
    try {
      await ref.read(apiClientProvider).alpacaReportOrderLog(
            symbol: order.symbol,
            side: order.side,
            qty: order.qty,
            destination: 'alpaca_only',
            outcome: outcome,
            detail: detail,
            alpacaOrderId: order.id,
            alpacaStatus: order.status,
          );
    } catch (_) {
      // Best-effort — see docstring above.
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final buy = order.side.toLowerCase() == 'buy';
    final fmt = NumberFormat('#,##0.00');
    final submitted = order.submittedAt;

    return Container(
      margin: const EdgeInsets.only(bottom: AmiSpacing.s),
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: _accent.withValues(alpha: 0.6)),
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
                    '${order.side.toUpperCase()} ${order.qty.toStringAsFixed(0)} '
                    '${order.symbol}',
                    style: AmiTypography.labelMono,
                  ),
                ),
              ),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: _accent),
                ),
                child: Text(
                  order.status.toUpperCase(),
                  style: AmiTypography.labelMono
                      .copyWith(fontSize: 9, color: _accent),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              // CR234 — the one shared identity badge, not a bespoke chip.
              const AlpacaBadge(fontSize: 9),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  _priceLabel(),
                  style: AmiTypography.caption
                      .copyWith(color: AmiColors.textMed),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (order.timeInForce != null)
                Text(
                  order.timeInForce!.toUpperCase(),
                  style: AmiTypography.caption
                      .copyWith(color: AmiColors.textLow, fontSize: 10),
                ),
            ],
          ),
          if (order.filledQty != null && order.filledQty! > 0) ...[
            const SizedBox(height: 4),
            Text(
              '${order.filledQty!.toStringAsFixed(0)} of '
              '${order.qty.toStringAsFixed(0)} filled'
              '${order.filledAvgPrice != null ? ' @ \$${fmt.format(order.filledAvgPrice)}' : ''}',
              style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
            ),
          ],
          // CR233's bracket legs, read back nested (this client requests
          // `nested=true`) — shown as the stop/target facts a user placed,
          // not as unexplained standalone orders.
          for (final leg in order.legs) _AlpacaBracketLegLine(leg: leg),
          if (submitted != null) ...[
            const SizedBox(height: 4),
            Text(
              DateFormat('d MMM, HH:mm').format(submitted.toLocal()),
              style: AmiTypography.caption
                  .copyWith(color: AmiColors.textLow, fontSize: 10),
            ),
          ],
          if (!closed && order.isCancellable) ...[
            const SizedBox(height: 6),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: () => _cancel(context, ref),
                style: TextButton.styleFrom(
                  visualDensity: VisualDensity.compact,
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                ),
                child: Text(
                  AppLocalizations.of(context).alpacaOrderCancelConfirm,
                  style: AmiTypography.labelMono
                      .copyWith(fontSize: 10, color: AmiColors.hexRed),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// One bracket leg (stop-loss or take-profit), read from `AlpacaOrder.legs`.
/// `type` on a leg is Alpaca's own `stop`/`limit` for that child order;
/// which one it is (protective stop vs. profit target) is read from
/// whichever price field is set, matching the same "server states it"
/// posture as the rest of this file — a stop-loss leg carries `stop_price`,
/// a take-profit leg carries `limit_price`, and Alpaca never sends both on
/// one bracket child.
class _AlpacaBracketLegLine extends StatelessWidget {
  const _AlpacaBracketLegLine({required this.leg});
  final AlpacaOrder leg;

  @override
  Widget build(BuildContext context) {
    final isStop = leg.stopPrice != null;
    final price = isStop ? leg.stopPrice : leg.limitPrice;
    if (price == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 2),
      child: Text(
        '${isStop ? 'Stop' : 'Target'} \$${price.toStringAsFixed(2)} '
        '(${leg.status})',
        style: AmiTypography.caption.copyWith(
          color: isStop ? AmiColors.hexAmber : AmiColors.hexGreen,
          fontSize: 10,
        ),
      ),
    );
  }
}
