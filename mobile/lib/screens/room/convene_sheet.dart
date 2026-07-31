/// Convene the Room — ticker picker sheet.
///
/// Tiny modal that gathers the ticker before launching the streaming
/// console. Pre-fills with a curated alpha watchlist (AAPL, MSFT, NVDA,
/// GOOGL, META, TSLA, AMZN) so the user can convene with one tap.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/sheet_insets.dart';
import 'package:ami_trade/widgets/ticker_not_found_panel.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

const _suggestedTickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMZN'];

class ConveneSheet extends ConsumerStatefulWidget {
  const ConveneSheet({super.key});

  @override
  ConsumerState<ConveneSheet> createState() => _ConveneSheetState();

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

class _ConveneSheetState extends ConsumerState<ConveneSheet> {
  final _ctrl = TextEditingController();
  late final TickerFieldValidator _validator;

  @override
  void initState() {
    super.initState();
    _validator = TickerFieldValidator(
      validate: (t) => ref.read(apiClientProvider).validateTicker(t),
      onChanged: () {
        if (mounted) setState(() {});
      },
    );
    _ctrl.addListener(_onTickerChanged);
  }

  @override
  void dispose() {
    _ctrl.removeListener(_onTickerChanged);
    _validator.dispose();
    _ctrl.dispose();
    super.dispose();
  }

  void _onTickerChanged() => _validator.onTextChanged(_ctrl.text);

  // CR128: existence check before Convene the Room ever runs — a bad ticker
  // used to burn credits + feed quota on a full fake 12-agent debate before
  // anything noticed (bug ab1d5664). DEF208: the answer is the same inline
  // panel the trade ticket uses, shown under the field as you type, rather
  // than a modal that only fires once you've committed.
  Future<void> _go(String t) async {
    final typed = t.trim().toUpperCase();
    if (typed.isEmpty || _validator.checking) return;
    // A tapped chip is a known-good ticker from our own list; typed input
    // may not be. Both go through the same gate so there is one path.
    if (!await _validator.check(typed)) return;
    if (!mounted) return;
    Navigator.of(context).pop();
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => RoomScreen(ticker: typed),
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
          // DEF208 — the one not-found surface, same widget and same
          // placement (directly under the ticker field) as the trade ticket
          // and watchlist add.
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
                  onPressed: _validator.checking ? null : () => _go(t),
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
              icon: _validator.checking
                  ? const SizedBox(
                      width: 16, height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2, color: AmiColors.slate900,
                      ),
                    )
                  : const Icon(Icons.bolt),
              label: Text(l.conveneCta),
              onPressed: _validator.checking ? null : () => _go(_ctrl.text),
            ),
          ),
        ],
      ),
    );
  }
}
