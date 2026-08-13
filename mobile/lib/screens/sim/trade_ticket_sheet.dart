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
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/room/convene_sheet.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/sharia_verdict_banner.dart';
import 'package:ami_trade/widgets/sheet_insets.dart';
import 'package:ami_trade/widgets/ticker_not_found_panel.dart';
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

  /// CR128 existence check, DEF207's on-the-same-debounce-as-the-quote
  /// timing, and DEF208's shared not-found panel — all of it lives in the
  /// validator now, which owns the debounce this sheet used to run itself.
  /// The quote fetch chains off [TickerFieldValidator]'s `onExists`, so a
  /// price can only ever be requested for a ticker the reference table
  /// confirmed.
  late final TickerFieldValidator _validator;

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
    _validator = TickerFieldValidator(
      validate: (t) => ref.read(apiClientProvider).validateTicker(t),
      onChanged: () {
        if (mounted) setState(() {});
      },
      onExists: _fetchQuote,
    );
    // If a ticker is prefilled (verdict path), check + fetch its quote
    // immediately so the price chip lands without the user having to retype.
    if (_ticker.text.trim().isNotEmpty) {
      _validator.onTextChanged(_ticker.text);
    }
    _ticker.addListener(_onTickerChanged);
  }

  @override
  void dispose() {
    _validator.dispose();
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
    _validator.onTextChanged(_ticker.text);
  }

  /// Only ever called by the validator, and only for a ticker it has just
  /// confirmed exists (DEF207): `simQuoteDetail` cannot answer the
  /// existence question itself — it falls through to the mock walk and
  /// fabricates a plausible price for any string, which is exactly how
  /// "NETFLIX" rendered as a confident $287.82 with nothing to say it is
  /// not a ticker (bug `ab1d5664`).
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

  Future<void> _convene() async {
    final ticker = _ticker.text.trim().toUpperCase();
    if (ticker.isEmpty) {
      Navigator.of(context).pop();
      ConveneSheet.show(context);
      return;
    }
    // Convening burns credits + paid feed quota before a single agent
    // speaks, so this route out of the sheet gets the same gate as submit.
    if (_validator.checking) return;
    if (!await _validator.check(ticker)) return;
    if (!mounted) return;
    Navigator.of(context).pop();
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => RoomScreen(ticker: ticker),
    ));
  }

  Future<void> _submit() async {
    final typed = _ticker.text.trim().toUpperCase();
    final qty = double.tryParse(_qty.text.trim());
    if (typed.isEmpty || qty == null || qty <= 0 || _validator.checking) return;
    // DEF208: no modal here. A failed check leaves the shared panel under
    // the field explaining why, which is the same thing the user has been
    // looking at since they stopped typing.
    if (!await _validator.check(typed)) return;
    if (!mounted) return;
    final result = await ref.read(simNotifierProvider.notifier).submit(
      ticker: typed,
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

  /// Violations minus the backend's English Sharia sentence, when the same
  /// fact is about to be rendered from the ARB as a localized banner. See the
  /// call site for why the match is deliberately narrow.
  static List<String> _visibleViolations(SimSubmitResult r) {
    final v = r.shariaVerdict;
    if (v == null || !v.isBlocking) return r.violations;
    final ticker = v.ticker.toUpperCase();
    final standard = v.standard.toUpperCase();
    if (ticker.isEmpty || standard.isEmpty) return r.violations;
    return r.violations
        .where((s) =>
            !(s.toUpperCase().contains(ticker) &&
                s.toUpperCase().contains(standard)))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(simNotifierProvider);
    final refusal = state.lastSubmit != null && !state.lastSubmit!.ok;
    final l = AppLocalizations.of(context);
    // CR069 G3: the Sharia disclosure rides on BOTH outcomes. A screened-out
    // ticker is refused and its verdict sits inside the refusal panel below; a
    // pass or an unknown is PERMITTED, so its verdict has no refusal to ride on
    // and gets its own banner here. A permitted unknown that renders nothing is
    // a silent pass on an observance decision — this CR's failure class
    // pointing the other way.
    final permittedVerdict = state.lastSubmit != null && state.lastSubmit!.ok
        ? state.lastSubmit!.shariaVerdict
        : null;
    final blockingVerdict = refusal &&
            (state.lastSubmit!.shariaVerdict?.isBlocking ?? false)
        ? state.lastSubmit!.shariaVerdict
        : null;
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
            if (permittedVerdict != null) ...[
              ShariaVerdictBanner(verdict: permittedVerdict),
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
                    // The backend composes its violation sentences in English
                    // (they also feed the agent prompts). When a blocking
                    // Sharia verdict arrives structured, its localized banner
                    // is rendered below instead, so drop the English twin here
                    // rather than showing the same fact twice in two
                    // languages. The match is on the verdict's own ticker AND
                    // standard, so a violation from any other rule survives;
                    // if it ever fails to match, the user sees the English
                    // sentence as well — duplicated, never missing.
                    for (final v in _visibleViolations(state.lastSubmit!))
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text('• $v', style: AmiTypography.caption),
                      ),
                    if (blockingVerdict != null) ...[
                      const SizedBox(height: AmiSpacing.s),
                      ShariaVerdictBanner(verdict: blockingVerdict),
                    ],
                    const SizedBox(height: 4),
                    Text(
                      l.tradeTicketChangeMandate,
                      style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
                    ),
                    // CR133 §5 — this line used to end "…via Settings → My
                    // Mandate", which fired at the exact moment a compliance
                    // breach had just blocked the trade and then made the user
                    // walk the path themselves. CR133 moves that path (the
                    // mandate now sits YOU → SETTINGS), so the instruction was
                    // about to be both wrong AND a longer walk. Replaced with
                    // the control rather than renamed: a rename leaves the same
                    // trap armed for the next nav change. Same pattern the app
                    // already ships as `floorLockedGoToLessons` → "GO TO
                    // LESSONS".
                    const SizedBox(height: AmiSpacing.s),
                    Align(
                      alignment: AlignmentDirectional.centerStart,
                      child: TextButton(
                        style: TextButton.styleFrom(
                          padding: EdgeInsets.zero,
                          minimumSize: const Size(0, 32),
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        ),
                        onPressed: () => Navigator.of(context)
                            .push(MaterialPageRoute<void>(
                          builder: (_) => const SettingsScreen(),
                        )),
                        child: Text(
                          l.tradeTicketOpenMandate,
                          style: AmiTypography.labelMono
                              .copyWith(color: AmiColors.hexBlue),
                        ),
                      ),
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
            // DEF207 — not-found takes the price chip's place entirely. A
            // price of ANY kind next to a string that isn't a ticker is the
            // fabrication this defect is about; the two are mutually
            // exclusive by construction, not by z-order.
            if (_validator.unknownTicker != null) ...[
              const SizedBox(height: AmiSpacing.xs),
              TickerNotFoundPanel(
                typed: _validator.unknownTicker!,
                suggestion: _validator.suggestion,
                onAccept: (t) {
                  _ticker.text = t;
                  _ticker.selection =
                      TextSelection.collapsed(offset: t.length);
                },
              ),
            ]
            // Live price anchor for setting TP / SL when no verdict has
            // been convened. Source pill (LIVE / MOCK) reflects what the
            // backend actually returned for this ticker — yfinance leaf
            // shows LIVE, mock_walk fallback shows MOCK.
            else if (_quote != null || _quoteLoading || _validator.checking) ...[
              const SizedBox(height: AmiSpacing.xs),
              _QuoteChip(
                quote: _quote,
                loading: _quoteLoading || _validator.checking,
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
                icon: (state.submitting || _validator.checking)
                    ? const SizedBox(
                        width: 16, height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2, color: AmiColors.slate900,
                        ),
                      )
                    : Icon(_side == 'buy' ? Icons.add : Icons.remove),
                label: Text(state.submitting
                    ? l.tradeTicketSubmitting
                    : l.tradeTicketSubmit),
                onPressed: (state.submitting || _validator.checking) ? null : _submit,
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
