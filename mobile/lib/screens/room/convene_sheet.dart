/// Convene the Room — ticker picker sheet.
///
/// Tiny modal that gathers the ticker before launching the streaming
/// console. Pre-fills with a curated alpha watchlist (AAPL, MSFT, NVDA,
/// GOOGL, META, TSLA, AMZN) so the user can convene with one tap.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/sheet_insets.dart';
import 'package:flutter/material.dart';

const _suggestedTickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMZN'];

class ConveneSheet extends StatefulWidget {
  const ConveneSheet({super.key});

  @override
  State<ConveneSheet> createState() => _ConveneSheetState();

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      backgroundColor: AmiColors.slate800,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => const ConveneSheet(),
    );
  }
}

class _ConveneSheetState extends State<ConveneSheet> {
  final _ctrl = TextEditingController();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  void _go(String t) {
    final ticker = t.trim().toUpperCase();
    if (ticker.isEmpty) return;
    Navigator.of(context).pop();
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => RoomScreen(ticker: ticker),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Padding(
      padding: EdgeInsets.fromLTRB(
        AmiSpacing.l, AmiSpacing.l, AmiSpacing.l,
        // DEF075 — clear keyboard AND nav bar, not just the keyboard.
        AmiSpacing.l + sheetBottomInset(MediaQuery.of(context)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.bolt, color: AmiColors.hexGreen, size: 20),
              const SizedBox(width: AmiSpacing.s),
              Text(l.conveneHeading,
                  style: AmiTypography.labelMono.copyWith(color: AmiColors.hexGreen)),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(
            l.convenePickTicker,
            style: AmiTypography.body,
          ),
          const SizedBox(height: AmiSpacing.l),
          TextField(
            controller: _ctrl,
            autofocus: true,
            textCapitalization: TextCapitalization.characters,
            style: AmiTypography.statMid,
            onSubmitted: _go,
            decoration: InputDecoration(
              hintText: l.conveneTickerHint,
              hintStyle: AmiTypography.statMid.copyWith(color: AmiColors.textLow),
              filled: true,
              fillColor: AmiColors.slate900,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AmiRadii.card),
                borderSide: const BorderSide(color: AmiColors.slate700),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AmiRadii.card),
                borderSide: const BorderSide(color: AmiColors.hexGreen),
              ),
            ),
          ),
          const SizedBox(height: AmiSpacing.m),
          Text(l.conveneOrPickOne,
              style: AmiTypography.labelMono.copyWith(fontSize: 11)),
          const SizedBox(height: AmiSpacing.s),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final t in _suggestedTickers)
                ActionChip(
                  label: Text(t,
                      style: AmiTypography.labelMono.copyWith(
                          color: AmiColors.textHigh)),
                  backgroundColor: AmiColors.slate900,
                  side: const BorderSide(color: AmiColors.slate700),
                  onPressed: () => _go(t),
                ),
            ],
          ),
          const SizedBox(height: AmiSpacing.l),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: AmiColors.hexGreen,
                foregroundColor: AmiColors.slate900,
                padding: const EdgeInsets.symmetric(vertical: AmiSpacing.m),
              ),
              icon: const Icon(Icons.bolt),
              label: Text(l.conveneCta),
              onPressed: () => _go(_ctrl.text),
            ),
          ),
        ],
      ),
    );
  }
}
