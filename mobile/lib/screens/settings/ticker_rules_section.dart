/// CR220 — the ticker allow/blocklist editors.
///
/// Both lists are ENFORCED in `backend/app/agents/safety_floor.py`, but nothing
/// ever wrote them: the Concierge hard-codes `[]` / `null`, so the enforcement
/// has never once fired for a real user. These editors are the first way to
/// populate them.
///
/// Two rules the design turns on, both CR040 "degrade loudly":
///
/// 1. **A symbol is validated before it can be added.** An unresolvable ticker
///    in an enforced list is a safety control that silently matches nothing.
///    Validation reuses `ApiClient.validateTicker` (`GET /v1/tickers/validate`,
///    CR128) — the same call the convene sheet, trade ticket, portfolio and
///    Floor already make, so there is no second notion of "is this a ticker".
///
/// 2. **A non-empty allowlist is the sharpest control in the app** — it refuses
///    everything outside itself — so it carries a standing warning rather than
///    a one-time confirm. An EMPTY allowlist is never sent: the API refuses it
///    (it would mean "nothing is tradable"), and clearing the last row sends
///    `null`, which means "no allowlist". `ComplianceFlags.copyWith` has a
///    dedicated `clearAllowlist` flag for exactly that distinction.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

typedef TickerValidator = Future<TickerValidation> Function(String ticker);

class TickerRulesSection extends StatelessWidget {
  const TickerRulesSection({
    super.key,
    required this.compliance,
    required this.onChanged,
    required this.validate,
  });

  final ComplianceFlags compliance;
  final ValueChanged<ComplianceFlags> onChanged;
  final TickerValidator validate;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final allowlist = compliance.tickerAllowlist ?? const <String>[];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _TickerList(
          key: const Key('tickerBlocklist'),
          fieldKey: 'blocklist',
          label: l.settingsTickerBlocklist,
          emptyText: l.settingsTickerBlocklistEmpty,
          tickers: compliance.tickerBlocklist,
          validate: validate,
          onChanged: (next) =>
              onChanged(compliance.copyWith(tickerBlocklist: next)),
        ),
        const SizedBox(height: AmiSpacing.l),
        _TickerList(
          key: const Key('tickerAllowlist'),
          fieldKey: 'allowlist',
          label: l.settingsTickerAllowlist,
          emptyText: l.settingsTickerAllowlistEmpty,
          tickers: allowlist,
          validate: validate,
          // An empty result clears the allowlist entirely rather than sending
          // `[]`, which would mean "nothing is tradable".
          onChanged: (next) => onChanged(
            next.isEmpty
                ? compliance.copyWith(clearAllowlist: true)
                : compliance.copyWith(tickerAllowlist: next),
          ),
        ),
        if (allowlist.isNotEmpty) ...[
          const SizedBox(height: 6),
          Container(
            padding: const EdgeInsets.all(AmiSpacing.s),
            decoration: BoxDecoration(
              color: AmiColors.hexAmber.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(AmiRadii.card),
              border: Border.all(color: AmiColors.hexAmber),
            ),
            child: Text(
              l.settingsTickerAllowlistWarning,
              key: const Key('allowlistWarning'),
              style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber),
            ),
          ),
        ],
      ],
    );
  }
}

class _TickerList extends StatefulWidget {
  const _TickerList({
    super.key,
    required this.fieldKey,
    required this.label,
    required this.emptyText,
    required this.tickers,
    required this.onChanged,
    required this.validate,
  });

  final String fieldKey;
  final String label;
  final String emptyText;
  final List<String> tickers;
  final ValueChanged<List<String>> onChanged;
  final TickerValidator validate;

  @override
  State<_TickerList> createState() => _TickerListState();
}

class _TickerListState extends State<_TickerList> {
  final _controller = TextEditingController();
  String? _error;
  bool _checking = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _add() async {
    final raw = _controller.text.trim().toUpperCase();
    if (raw.isEmpty) return;
    final l = AppLocalizations.of(context);

    if (widget.tickers.contains(raw)) {
      setState(() => _error = l.settingsTickerDuplicate);
      return;
    }

    setState(() {
      _checking = true;
      _error = null;
    });
    try {
      final result = await widget.validate(raw);
      if (!mounted) return;
      if (!result.exists) {
        // Deliberately does NOT auto-substitute the server's suggestion: this
        // list decides what may be traded, so silently adding a ticker the
        // user did not type is the wrong kind of helpful.
        setState(() {
          _checking = false;
          _error = result.suggestion != null
              ? '${l.settingsTickerUnknown} (${result.suggestion!.ticker}?)'
              : l.settingsTickerUnknown;
        });
        return;
      }
      setState(() {
        _checking = false;
        _error = null;
        _controller.clear();
      });
      widget.onChanged([...widget.tickers, result.ticker]);
    } catch (_) {
      if (!mounted) return;
      // Offline or the endpoint is unreachable: refuse rather than accept
      // unvalidated. An unchecked symbol in an enforced list is the silent
      // no-op this whole section exists to prevent.
      setState(() {
        _checking = false;
        _error = l.settingsTickerUnknown;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(widget.label, style: AmiTypography.body),
        const SizedBox(height: 6),
        if (widget.tickers.isEmpty)
          Text(
            widget.emptyText,
            style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
          )
        else
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final t in widget.tickers)
                InputChip(
                  key: Key('${widget.fieldKey}_chip_$t'),
                  label: Text(t),
                  labelStyle: AmiTypography.labelMono.copyWith(
                    fontSize: 11,
                    color: AmiColors.hexAmber,
                  ),
                  backgroundColor: AmiColors.slate900,
                  side: const BorderSide(color: AmiColors.hexAmber),
                  deleteIconColor: AmiColors.textMed,
                  // Explicit rather than the theme default: the delete affordance
                  // is how a user removes an enforced rule, so it should not
                  // change shape with a Material version bump.
                  deleteIcon: const Icon(Icons.close, size: 16),
                  tooltip: l.settingsTickerRemove,
                  onDeleted: () => widget.onChanged(
                    widget.tickers.where((x) => x != t).toList(),
                  ),
                ),
            ],
          ),
        const SizedBox(height: 6),
        Row(
          children: [
            Expanded(
              child: TextField(
                key: Key('${widget.fieldKey}_input'),
                controller: _controller,
                textCapitalization: TextCapitalization.characters,
                style: AmiTypography.labelMono.copyWith(color: AmiColors.textHigh),
                decoration: InputDecoration(
                  isDense: true,
                  hintText: l.settingsTickerAdd,
                  hintStyle: AmiTypography.caption.copyWith(color: AmiColors.textLow),
                  border: const UnderlineInputBorder(),
                  errorText: _error,
                  errorStyle: AmiTypography.caption.copyWith(color: AmiColors.hexRed),
                ),
                onSubmitted: (_) => _add(),
              ),
            ),
            const SizedBox(width: AmiSpacing.s),
            _checking
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : IconButton(
                    key: Key('${widget.fieldKey}_add'),
                    icon: const Icon(Icons.add, color: AmiColors.hexCyan),
                    onPressed: _add,
                  ),
          ],
        ),
      ],
    );
  }
}
