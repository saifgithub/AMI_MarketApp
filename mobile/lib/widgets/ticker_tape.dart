/// Scrolling stock ticker tape — displayed below the bottom nav bar.
///
/// Fetches quotes directly from Yahoo Finance (via tickerTapeProvider).
/// Scroll direction follows locale: right-to-left for LTR languages (EN),
/// left-to-right for RTL languages (AR, MS). Ticker symbols are always LTR.
/// Tapping any item pauses the tape for 2 s then opens the watchlist sheet.
library;

import 'dart:async';
import 'dart:ui' as ui;

import 'package:ami_trade/services/yahoo_finance_service.dart';
import 'package:ami_trade/state/ticker_tape_provider.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/watchlist_sheet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

const double _kItemWidth = 160.0;
const double _kTapeHeight = 28.0;

// ─────────────────────────────────────────────────────────────────────────────
// Public entry point
// ─────────────────────────────────────────────────────────────────────────────

class TickerTape extends ConsumerWidget {
  const TickerTape({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bottomInset = MediaQuery.of(context).padding.bottom;
    final async = ref.watch(tickerTapeProvider);

    // Keep showing last known data during silent background refreshes.
    final data = async.valueOrNull;
    final isFirstLoad = async.isLoading && data == null;
    final hasError = async.hasError && data == null;

    if (hasError) return const SizedBox.shrink();

    return _Shell(
      bottomInset: bottomInset,
      child: isFirstLoad
          ? const _LoadingBar()
          : (data == null || data.quotes.isEmpty)
              ? const SizedBox.shrink()
              : SizedBox(
                  height: _kTapeHeight,
                  child: Stack(
                    children: [
                      _ScrollingTape(data: data),
                      _StatusPill(data: data),
                    ],
                  ),
                ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Shell — background + border + bottom inset
// ─────────────────────────────────────────────────────────────────────────────

class _Shell extends StatelessWidget {
  const _Shell({required this.bottomInset, required this.child});

  final double bottomInset;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AmiColors.slate900,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(height: 0.5, color: AmiColors.slate700),
          child,
          SizedBox(height: bottomInset),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Loading bar — first fetch only
// ─────────────────────────────────────────────────────────────────────────────

class _LoadingBar extends StatelessWidget {
  const _LoadingBar();

  @override
  Widget build(BuildContext context) {
    return Container(height: _kTapeHeight, color: AmiColors.slate800);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Scrolling tape
// ─────────────────────────────────────────────────────────────────────────────

class _ScrollingTape extends ConsumerStatefulWidget {
  const _ScrollingTape({required this.data});

  final TickerTapeData data;

  @override
  ConsumerState<_ScrollingTape> createState() => _ScrollingTapeState();
}

class _ScrollingTapeState extends ConsumerState<_ScrollingTape>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  late AnimationController _ctrl;
  Timer? _pauseTimer;

  List<TickerQuote> get _doubled =>
      [...widget.data.quotes, ...widget.data.quotes];

  double get _halfWidth => widget.data.quotes.length * _kItemWidth;

  Duration get _duration =>
      Duration(milliseconds: (_halfWidth / 60 * 1000).round());

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _ctrl = AnimationController(vsync: this, duration: _duration)..repeat();
  }

  @override
  void didUpdateWidget(_ScrollingTape old) {
    super.didUpdateWidget(old);
    if (old.data.quotes.length != widget.data.quotes.length) {
      _ctrl.duration = _duration;
      if (_ctrl.isAnimating) _ctrl.repeat();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive) {
      _ctrl.stop();
    } else if (state == AppLifecycleState.resumed) {
      _ctrl.repeat();
    }
  }

  void _onItemTap(TickerQuote quote) {
    _ctrl.stop();
    _pauseTimer?.cancel();
    _pauseTimer = Timer(const Duration(seconds: 2), () {
      if (mounted) _ctrl.repeat();
    });
    showWatchlistSheet(context, ref, ticker: quote.symbol, price: quote.price);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _pauseTimer?.cancel();
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Explicit dart:ui prefix resolves TextDirection unambiguously — this import
    // combination causes the analyzer to shadow TextDirection with a non-enum.
    final isRtl = Directionality.of(context) == ui.TextDirection.rtl;

    return ClipRect(
      child: RepaintBoundary(
        child: AnimatedBuilder(
          animation: _ctrl,
          builder: (context, child) {
            final offset =
                isRtl ? _halfWidth * _ctrl.value : -_halfWidth * _ctrl.value;
            return Transform.translate(
              offset: Offset(offset, 0),
              child: child,
            );
          },
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: _doubled
                .map(
                  (q) => _TapeItem(
                    quote: q,
                    onTap: () => _onItemTap(q),
                  ),
                )
                .toList(),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Individual ticker item
// ─────────────────────────────────────────────────────────────────────────────

class _TapeItem extends StatelessWidget {
  const _TapeItem({required this.quote, required this.onTap});

  final TickerQuote quote;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final isUp = quote.changePercent > 0;
    final isDown = quote.changePercent < 0;
    final arrow = isUp ? '↑' : (isDown ? '↓' : '–');
    final arrowColor = isUp
        ? AmiColors.hexGreen
        : (isDown ? AmiColors.hexRed : AmiColors.textLow);
    final priceFmt = NumberFormat.simpleCurrency(decimalDigits: 2);
    final pctFmt = NumberFormat('0.0');

    return Directionality(
      // Explicit dart:ui prefix — see RTL comment above.
      textDirection: ui.TextDirection.ltr,
      child: GestureDetector(
        onTap: onTap,
        child: SizedBox(
          width: _kItemWidth,
          height: _kTapeHeight,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Text(
                  quote.symbol,
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.textMed, fontSize: 10),
                ),
                const SizedBox(width: 4),
                Text(
                  priceFmt.format(quote.price),
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.textHigh, fontSize: 10),
                ),
                const SizedBox(width: 3),
                Text(
                  '$arrow${pctFmt.format(quote.changePercent.abs())}%',
                  style: AmiTypography.labelMono
                      .copyWith(color: arrowColor, fontSize: 10),
                ),
                const SizedBox(width: 6),
                Text(
                  '·',
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.textLow, fontSize: 10),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Market state / stale pill — pinned to the leading edge
// ─────────────────────────────────────────────────────────────────────────────

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.data});

  final TickerTapeData data;

  @override
  Widget build(BuildContext context) {
    final String label;
    final Color color;

    if (data.isStale) {
      label = 'STALE';
      color = AmiColors.hexRed;
    } else {
      switch (data.marketState) {
        case 'PRE':
          label = 'PRE-MKT';
          color = AmiColors.hexAmber;
        case 'POST':
          label = 'AFTER-HRS';
          color = AmiColors.hexAmber;
        case 'CLOSED':
          label = 'CLOSED';
          color = AmiColors.textLow;
        default:
          return const SizedBox.shrink(); // REGULAR — no pill needed
      }
    }

    return Align(
      alignment: AlignmentDirectional.centerStart,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 6, vertical: 5),
        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
        decoration: BoxDecoration(
          color: AmiColors.slate900,
          border: Border.all(color: color, width: 0.5),
          borderRadius: BorderRadius.circular(3),
        ),
        child: Text(
          label,
          style: AmiTypography.labelMono.copyWith(
            color: color,
            fontSize: 8,
            letterSpacing: 0.8,
          ),
        ),
      ),
    );
  }
}
