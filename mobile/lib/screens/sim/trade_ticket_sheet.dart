/// Sim Trade ticket — the form that submits a trade.
///
/// Used standalone (from the Portfolio screen) and as the "Open trade
/// ticket" CTA from a Room verdict (with the verdict's size/entry/stop/
/// target pre-filled). On submit, PM safety floor runs server-side; any
/// rejection is surfaced as an amber banner with the specific violations.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
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
  }

  @override
  void dispose() {
    _ticker.dispose();
    _qty.dispose();
    _stop.dispose();
    _target.dispose();
    _horizon.dispose();
    super.dispose();
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
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            AppLocalizations.of(context).tradeTicketFilled(
              result.trade!.side.toUpperCase(),
              result.trade!.quantity.toStringAsFixed(0),
              result.trade!.ticker,
              result.trade!.entryPrice.toStringAsFixed(2),
            ),
          ),
          backgroundColor: AmiColors.slate800,
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
        AmiSpacing.l + MediaQuery.of(context).viewInsets.bottom,
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
