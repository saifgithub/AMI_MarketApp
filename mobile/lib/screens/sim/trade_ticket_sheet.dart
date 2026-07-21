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
import 'package:ami_trade/screens/room/convene_sheet.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/sheet_insets.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class TradeTicketSheet extends ConsumerStatefulWidget {
  const TradeTicketSheet({
    super.key,
    this.prefill,
    this.verdictRef,
    this.tickerPrefill,
  });

  /// Optional Room verdict to pre-fill from.
  final RoomVerdict? prefill;
  final String? verdictRef;
  final String? tickerPrefill;

  @override
  ConsumerState<TradeTicketSheet> createState() => _TradeTicketSheetState();

  static Future<void> show(
    BuildContext context, {
    RoomVerdict? prefill,
    String? verdictRef,
    String? tickerPrefill,
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
  Timer? _quoteDebounce;

  @override
  void initState() {
    super.initState();
    _ticker = TextEditingController(text: widget.tickerPrefill ?? '');
    _qty = TextEditingController(text: '1');
    _stop = TextEditingController();
    _target = TextEditingController();
    _horizon = TextEditingController();
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
    // If a ticker is prefilled (verdict path), fetch its quote immediately
    // so the price chip lands without the user having to retype.
    if (_ticker.text.trim().isNotEmpty) {
      _scheduleQuoteFetch();
    }
    _ticker.addListener(_onTickerChanged);
  }

  @override
  void dispose() {
    _quoteDebounce?.cancel();
    _ticker.removeListener(_onTickerChanged);
    _ticker.dispose();
    _qty.dispose();
    _stop.dispose();
    _target.dispose();
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
    _scheduleQuoteFetch();
  }

  void _scheduleQuoteFetch() {
    _quoteDebounce?.cancel();
    final t = _ticker.text.trim().toUpperCase();
    if (t.isEmpty) return;
    _quoteDebounce = Timer(const Duration(milliseconds: 450), () {
      _fetchQuote(t);
    });
  }

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
      // Anchor TP/SL off the live price when the user hasn't set them —
      // matches the Convene the Room trader template (-6% / +13%) so the
      // suggestion is consistent across both flows. User can override.
      if (_stop.text.trim().isEmpty) {
        _stop.text = (q.price * 0.94).toStringAsFixed(2);
      }
      if (_target.text.trim().isEmpty) {
        _target.text = (q.price * 1.13).toStringAsFixed(2);
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _quote = null;
        _quoteTicker = null;
        _quoteLoading = false;
      });
    }
  }

  void _convene() {
    final ticker = _ticker.text.trim().toUpperCase();
    Navigator.of(context).pop();
    if (ticker.isNotEmpty) {
      Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => RoomScreen(ticker: ticker),
      ));
    } else {
      ConveneSheet.show(context);
    }
  }

  Future<void> _submit() async {
    final ticker = _ticker.text.trim().toUpperCase();
    final qty = double.tryParse(_qty.text.trim());
    if (ticker.isEmpty || qty == null || qty <= 0) return;
    final result = await ref.read(simNotifierProvider.notifier).submit(
      ticker: ticker,
      side: _side,
      quantity: qty,
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
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          duration: const Duration(seconds: 5),
          backgroundColor: AmiColors.hexGreen,
          behavior: SnackBarBehavior.floating,
          content: Row(
            children: [
              const Icon(Icons.check_circle, color: AmiColors.slate900, size: 24),
              const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: Text(
                  AppLocalizations.of(context).tradeTicketFilled(
                    result.trade!.side.toUpperCase(),
                    result.trade!.quantity.toStringAsFixed(0),
                    result.trade!.ticker,
                    result.trade!.entryPrice.toStringAsFixed(2),
                  ),
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
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(simNotifierProvider);
    final refusal = state.lastSubmit != null && !state.lastSubmit!.ok;
    final l = AppLocalizations.of(context);
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
                    for (final v in state.lastSubmit!.violations)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text('• $v', style: AmiTypography.caption),
                      ),
                    const SizedBox(height: 4),
                    Text(
                      l.tradeTicketChangeMandate,
                      style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
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
                  onChange: (v) => setState(() => _side = v),
                ),
              ],
            ),
            // Live price anchor for setting TP / SL when no verdict has
            // been convened. Source pill (LIVE / MOCK) reflects what the
            // backend actually returned for this ticker — yfinance leaf
            // shows LIVE, mock_walk fallback shows MOCK.
            if (_quote != null || _quoteLoading) ...[
              const SizedBox(height: AmiSpacing.xs),
              _QuoteChip(
                quote: _quote,
                loading: _quoteLoading,
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
            const SizedBox(height: AmiSpacing.l),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: _side == 'buy' ? AmiColors.hexGreen : AmiColors.hexRed,
                  foregroundColor: AmiColors.slate900,
                  padding: const EdgeInsets.symmetric(vertical: AmiSpacing.m),
                ),
                icon: Icon(_side == 'buy' ? Icons.add : Icons.remove),
                label: Text(state.submitting
                    ? l.tradeTicketSubmitting
                    : l.tradeTicketSubmit),
                onPressed: state.submitting ? null : _submit,
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
