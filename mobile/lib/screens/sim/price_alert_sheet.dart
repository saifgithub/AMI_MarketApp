/// Price-alert creation sheet (CR027 §4) — the loop's only manual entry
/// point: creates the alert `price_alert_evaluator.py` fires on breach.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/state/price_alert_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/sheet_insets.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class PriceAlertSheet extends ConsumerStatefulWidget {
  const PriceAlertSheet({super.key, required this.ticker});

  final String ticker;

  @override
  ConsumerState<PriceAlertSheet> createState() => _PriceAlertSheetState();

  static Future<void> show(BuildContext context, {required String ticker}) {
    return showModalBottomSheet<void>(
      context: context,
      backgroundColor: AmiColors.slate800,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => PriceAlertSheet(ticker: ticker),
    );
  }
}

class _PriceAlertSheetState extends ConsumerState<PriceAlertSheet> {
  final _price = TextEditingController();
  String _thresholdType = 'stop';

  @override
  void dispose() {
    _price.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final price = double.tryParse(_price.text.trim());
    if (price == null || price <= 0) return;
    final ok = await ref.read(priceAlertControllerProvider.notifier).create(
          ticker: widget.ticker,
          thresholdType: _thresholdType,
          thresholdPrice: price,
        );
    if (ok && mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final controllerState = ref.watch(priceAlertControllerProvider);
    final price = double.tryParse(_price.text.trim());
    final canSubmit = !controllerState.busy && price != null && price > 0;

    return Padding(
      padding: EdgeInsets.fromLTRB(
        AmiSpacing.l, AmiSpacing.l, AmiSpacing.l,
        AmiSpacing.l + sheetBottomInset(MediaQuery.of(context)),
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.notifications_active_outlined,
                    color: AmiColors.hexBlue, size: 20),
                const SizedBox(width: AmiSpacing.s),
                Text(
                  l.priceAlertSheetTitle(widget.ticker),
                  style: AmiTypography.labelMono.copyWith(color: AmiColors.hexBlue),
                ),
              ],
            ),
            const SizedBox(height: AmiSpacing.l),
            Text(l.priceAlertSheetThresholdLabel, style: AmiTypography.caption),
            const SizedBox(height: AmiSpacing.xs),
            RadioGroup<String>(
              groupValue: _thresholdType,
              onChanged: (v) => setState(() => _thresholdType = v ?? _thresholdType),
              child: Column(
                children: [
                  _ThresholdRadio(value: 'stop', label: l.priceAlertTypeStop),
                  _ThresholdRadio(value: 'target', label: l.priceAlertTypeTarget),
                  _ThresholdRadio(value: 'manual_above', label: l.priceAlertTypeManualAbove),
                  _ThresholdRadio(value: 'manual_below', label: l.priceAlertTypeManualBelow),
                ],
              ),
            ),
            const SizedBox(height: AmiSpacing.m),
            TextField(
              controller: _price,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [
                FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d{0,2}')),
              ],
              onChanged: (_) => setState(() {}),
              style: AmiTypography.body.copyWith(color: AmiColors.textHigh),
              decoration: InputDecoration(
                labelText: l.priceAlertSheetPriceLabel,
                prefixText: '\$',
              ),
            ),
            if (controllerState.error != null) ...[
              const SizedBox(height: AmiSpacing.s),
              Text(
                controllerState.error!,
                style: AmiTypography.caption.copyWith(color: AmiColors.hexRed),
              ),
            ],
            const SizedBox(height: AmiSpacing.l),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: canSubmit ? _submit : null,
                child: controllerState.busy
                    ? const SizedBox(
                        width: 18, height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(l.priceAlertSheetCreate),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ThresholdRadio extends StatelessWidget {
  const _ThresholdRadio({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return RadioListTile<String>(
      value: value,
      title: Text(label, style: AmiTypography.body),
      dense: true,
      contentPadding: EdgeInsets.zero,
      activeColor: AmiColors.hexBlue,
    );
  }
}
