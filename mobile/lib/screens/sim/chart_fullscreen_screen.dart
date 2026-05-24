/// Fullscreen landscape chart for a single ticker.
///
/// Bundle 3 of the TickerDetail surface (AT:R41). The app is globally
/// portrait-locked in main.dart; this is the ONE route that unlocks
/// orientation, and it does so only while it's the active route — on
/// dispose, the lock is re-applied. Two ways to land here:
///
///   1. User taps the expand IconButton on the portrait chart.
///   2. User rotates the device while on TickerDetail — the parent
///      OrientationBuilder catches the rotation and pushes this route.
///
/// Either way, rotating back to portrait pops the route (the OS rotates
/// the underlying portrait-locked TickerDetail back into view).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/ticker_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class ChartFullscreenScreen extends StatefulWidget {
  const ChartFullscreenScreen({super.key, required this.ticker});

  final String ticker;

  @override
  State<ChartFullscreenScreen> createState() => _ChartFullscreenScreenState();
}

class _ChartFullscreenScreenState extends State<ChartFullscreenScreen> {
  @override
  void initState() {
    super.initState();
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  }

  @override
  void dispose() {
    SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            const topBarH = 40.0;
            // TickerChart = Wrap (period chips ≈ 32) + 4 spacer + chart.
            const chartChromeH = 40.0;
            final chartH =
                (constraints.maxHeight - topBarH - chartChromeH).clamp(120.0, 9999.0);
            return Column(
              children: [
                SizedBox(
                  height: topBarH,
                  child: Row(
                    children: [
                      const SizedBox(width: 8),
                      Tooltip(
                        message: l.tickerDetailChartClose,
                        child: IconButton(
                          icon: const Icon(Icons.close, color: AmiColors.hexCyan),
                          onPressed: () => Navigator.of(context).pop(),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        widget.ticker,
                        style: AmiTypography.labelMono.copyWith(
                          color: AmiColors.hexCyan,
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
                  child: TickerChart(
                    ticker: widget.ticker,
                    height: chartH,
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}
