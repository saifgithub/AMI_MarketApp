/// CR101-MOBILE — the seven settable risk-limit fields the backend
/// (CR101-BE1 + CR101-BE2) shipped and Settings never surfaced.
///
/// Three layers, per the assign (`orchestration/dispatch/lanes/CR101-MOBILE.assign.md`):
///   L1 — the risk-profile dial (`_RiskSlider` in settings_screen.dart) writes
///        `risk_score` and clears `sector_cap_pct`/`single_name_cap_pct` so
///        those two follow the new profile's preset.
///   L2 — this section: every field in its own units, editable.
///   L3 — no client-side ceiling on any value; a looser-than-current edit
///        discloses its consequence inline, at set-time.
///
/// CR046 shown-equals-enforced, applied literally: every number rendered
/// here is `mandate.<field>` (or a value this screen is about to PATCH) —
/// never a client-side constant. `sector_cap_pct` / `single_name_cap_pct`
/// unset do NOT mean "off": the CR101-BE1 bridge measured that an unset
/// value still enforces via a server-side preset this API never returns a
/// number for (`trading_math.sizing.risk_tier_cap`, keyed off
/// `risk_score`/`concentration_tolerance` — no endpoint exposes the resolved
/// figure). So this screen cannot show what an unset cap currently enforces
/// to, and it does not guess: it renders "Following your risk profile", not
/// a number, and not "OFF". The five CR101-BE2 fields have no such preset —
/// `null` there really is OFF (unenforced), exactly as the assign's field
/// table describes. This split is disclosed in the CR101-MOBILE bridge as a
/// deliberate deviation from the assign's literal "None means OFF for all
/// seven" framing, because the literal framing is false for two of the
/// seven per BE1's own measurement.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

enum LimitKind { percent, count, hours }

/// One settable limit's shape — key names and directionality only, never a
/// numeric cap value (that would be exactly the client-side literal CR046's
/// mobile-side guard test exists to catch).
class LimitFieldConfig {
  const LimitFieldConfig({
    required this.key,
    required this.kind,
    required this.presetLinked,
    required this.higherIsLooser,
  });

  /// The exact backend PATCH key (`Mandate` field name).
  final String key;
  final LimitKind kind;

  /// True for the two CR101-BE1 fields whose unset state follows a
  /// risk-profile preset rather than meaning "off".
  final bool presetLinked;

  /// Direction convention for the loosen/tighten disclosure: true when a
  /// numerically larger value is the looser (less-protective) one. False
  /// for `post_loss_cooldown_hours`, where a SHORTER wait is looser.
  final bool higherIsLooser;
}

const List<LimitFieldConfig> kRiskLimitFields = [
  LimitFieldConfig(key: 'sector_cap_pct', kind: LimitKind.percent, presetLinked: true, higherIsLooser: true),
  LimitFieldConfig(key: 'single_name_cap_pct', kind: LimitKind.percent, presetLinked: true, higherIsLooser: true),
  LimitFieldConfig(key: 'post_loss_cooldown_hours', kind: LimitKind.hours, presetLinked: false, higherIsLooser: false),
  LimitFieldConfig(key: 'max_open_positions', kind: LimitKind.count, presetLinked: false, higherIsLooser: true),
  LimitFieldConfig(key: 'max_trades_per_day', kind: LimitKind.count, presetLinked: false, higherIsLooser: true),
  LimitFieldConfig(key: 'max_trades_per_week', kind: LimitKind.count, presetLinked: false, higherIsLooser: true),
  LimitFieldConfig(key: 'max_open_risk_pct', kind: LimitKind.percent, presetLinked: false, higherIsLooser: true),
];

/// Disclosure classes a pending edit can fall into. `none` renders nothing.
enum LimitDisclosure { none, unknownDirection, looser, off, hundredPercent }

/// Pure — comparing an already-in-effect value against a candidate new
/// value using only the field's declared directionality, never a
/// hardcoded threshold beyond the mathematical percent ceiling (100).
LimitDisclosure classifyLimitEdit(
  LimitFieldConfig cfg, {
  required num? oldValue,
  required num? newValue,
}) {
  if (oldValue == newValue) return LimitDisclosure.none;
  if (cfg.kind == LimitKind.percent && newValue == 100) {
    return LimitDisclosure.hundredPercent;
  }
  if (oldValue == null && newValue != null) {
    return cfg.presetLinked ? LimitDisclosure.unknownDirection : LimitDisclosure.none;
  }
  if (oldValue != null && newValue == null) {
    return LimitDisclosure.off;
  }
  if (oldValue == null || newValue == null) return LimitDisclosure.none;
  final looser = cfg.higherIsLooser ? newValue > oldValue : newValue < oldValue;
  return looser ? LimitDisclosure.looser : LimitDisclosure.none;
}

String? disclosureText(AppLocalizations l, LimitDisclosure d) {
  switch (d) {
    case LimitDisclosure.none:
      return null;
    case LimitDisclosure.unknownDirection:
      return l.settingsRiskLimitsDisclosureFollowing;
    case LimitDisclosure.looser:
      return l.settingsRiskLimitsDisclosureLooser;
    case LimitDisclosure.off:
      return l.settingsRiskLimitsDisclosureOff;
    case LimitDisclosure.hundredPercent:
      return l.settingsRiskLimitsDisclosure100;
  }
}

class RiskLimitsSection extends StatelessWidget {
  const RiskLimitsSection({
    super.key,
    required this.mandate,
    required this.pending,
    required this.onFieldChanged,
    required this.expanded,
    required this.onToggleExpanded,
  });

  final UserMandate mandate;

  /// Patch-key → pending value. `containsKey(key)` means "touched this
  /// session"; the stored value (possibly `null`) is what will be PATCHed.
  final Map<String, dynamic> pending;
  final void Function(LimitFieldConfig cfg, num? value) onFieldChanged;
  final bool expanded;
  final VoidCallback onToggleExpanded;

  num? _serverValue(String key) {
    switch (key) {
      case 'sector_cap_pct':
        return mandate.sectorCapPct;
      case 'single_name_cap_pct':
        return mandate.singleNameCapPct;
      case 'post_loss_cooldown_hours':
        return mandate.postLossCooldownHours;
      case 'max_open_positions':
        return mandate.maxOpenPositions;
      case 'max_trades_per_day':
        return mandate.maxTradesPerDay;
      case 'max_trades_per_week':
        return mandate.maxTradesPerWeek;
      case 'max_open_risk_pct':
        return mandate.maxOpenRiskPct;
      default:
        return null;
    }
  }

  num? effectiveValue(String key) =>
      pending.containsKey(key) ? pending[key] as num? : _serverValue(key);

  bool get isCustomProfile =>
      effectiveValue('sector_cap_pct') != null || effectiveValue('single_name_cap_pct') != null;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: onToggleExpanded,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Row(
              children: [
                Expanded(
                  child: Text(l.settingsRiskLimitsExpand, style: AmiTypography.body),
                ),
                Icon(
                  expanded ? Icons.expand_less : Icons.expand_more,
                  color: AmiColors.textLow,
                ),
              ],
            ),
          ),
        ),
        if (expanded)
          for (final cfg in kRiskLimitFields) ...[
            _LimitFieldRow(
              config: cfg,
              label: _labelFor(l, cfg.key),
              explain: _explainFor(l, cfg.key),
              serverValue: _serverValue(cfg.key),
              effectiveValue: effectiveValue(cfg.key),
              onChanged: (v) => onFieldChanged(cfg, v),
            ),
            const SizedBox(height: AmiSpacing.s),
          ],
      ],
    );
  }

  static String _labelFor(AppLocalizations l, String key) {
    switch (key) {
      case 'sector_cap_pct':
        return l.settingsRiskLimitsSectorCapLabel;
      case 'single_name_cap_pct':
        return l.settingsRiskLimitsSingleNameCapLabel;
      case 'post_loss_cooldown_hours':
        return l.settingsRiskLimitsCooldownLabel;
      case 'max_open_positions':
        return l.settingsRiskLimitsMaxOpenPositionsLabel;
      case 'max_trades_per_day':
        return l.settingsRiskLimitsMaxTradesPerDayLabel;
      case 'max_trades_per_week':
        return l.settingsRiskLimitsMaxTradesPerWeekLabel;
      case 'max_open_risk_pct':
        return l.settingsRiskLimitsMaxOpenRiskLabel;
      default:
        return key;
    }
  }

  static String _explainFor(AppLocalizations l, String key) {
    switch (key) {
      case 'sector_cap_pct':
        return l.settingsRiskLimitsSectorCapExplain;
      case 'single_name_cap_pct':
        return l.settingsRiskLimitsSingleNameCapExplain;
      case 'post_loss_cooldown_hours':
        return l.settingsRiskLimitsCooldownExplain;
      case 'max_open_positions':
        return l.settingsRiskLimitsMaxOpenPositionsExplain;
      case 'max_trades_per_day':
        return l.settingsRiskLimitsMaxTradesPerDayExplain;
      case 'max_trades_per_week':
        return l.settingsRiskLimitsMaxTradesPerWeekExplain;
      case 'max_open_risk_pct':
        return l.settingsRiskLimitsMaxOpenRiskExplain;
      default:
        return '';
    }
  }
}

class _LimitFieldRow extends StatefulWidget {
  const _LimitFieldRow({
    required this.config,
    required this.label,
    required this.explain,
    required this.serverValue,
    required this.effectiveValue,
    required this.onChanged,
  });

  final LimitFieldConfig config;
  final String label;
  final String explain;
  final num? serverValue;
  final num? effectiveValue;
  final ValueChanged<num?> onChanged;

  @override
  State<_LimitFieldRow> createState() => _LimitFieldRowState();
}

class _LimitFieldRowState extends State<_LimitFieldRow> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: _formatForEdit(widget.effectiveValue));
  }

  @override
  void didUpdateWidget(covariant _LimitFieldRow old) {
    super.didUpdateWidget(old);
    // Only resync the field text when the value changed from OUTSIDE this
    // row's own typing (e.g. L1's preset reset) — never fight the user's
    // cursor while they're mid-edit of the same value they just typed.
    if (old.effectiveValue != widget.effectiveValue &&
        _formatForEdit(widget.effectiveValue) != _controller.text) {
      _controller.text = _formatForEdit(widget.effectiveValue);
    }
  }

  String _formatForEdit(num? v) {
    if (v == null) return '';
    if (widget.config.kind == LimitKind.count) return v.toInt().toString();
    final d = v.toDouble();
    return d == d.roundToDouble() ? d.toInt().toString() : d.toString();
  }

  String _unitSuffix() {
    switch (widget.config.kind) {
      case LimitKind.percent:
        return '%';
      case LimitKind.hours:
        return 'h';
      case LimitKind.count:
        return '';
    }
  }

  void _setOff() {
    _controller.clear();
    widget.onChanged(null);
  }

  void _submit(String text) {
    final trimmed = text.trim();
    if (trimmed.isEmpty) {
      widget.onChanged(null);
      return;
    }
    final parsed = num.tryParse(trimmed);
    if (parsed == null) return;
    widget.onChanged(parsed);
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final isOff = widget.effectiveValue == null;
    final offLabel = widget.config.presetLinked
        ? l.settingsRiskLimitsProfileFollowing
        : l.settingsRiskLimitsOff;
    final disclosure = classifyLimitEdit(
      widget.config,
      oldValue: widget.serverValue,
      newValue: widget.effectiveValue,
    );
    final disclosureMsg = disclosureText(l, disclosure);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(widget.label, style: AmiTypography.body),
          const SizedBox(height: 2),
          Text(widget.explain, style: AmiTypography.caption.copyWith(color: AmiColors.textLow)),
          const SizedBox(height: 6),
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: AmiSpacing.s,
            runSpacing: 6,
            children: [
              ChoiceChip(
                key: Key('riskLimitOff_${widget.config.key}'),
                label: Text(offLabel),
                labelStyle: AmiTypography.labelMono.copyWith(
                  fontSize: 11,
                  color: isOff ? AmiColors.hexAmber : AmiColors.textMed,
                ),
                selected: isOff,
                onSelected: (_) => _setOff(),
                selectedColor: AmiColors.hexAmber.withValues(alpha: 0.2),
                backgroundColor: AmiColors.slate900,
                side: BorderSide(color: isOff ? AmiColors.hexAmber : AmiColors.slate700),
              ),
              SizedBox(
                width: 88,
                child: TextField(
                  key: Key('riskLimitField_${widget.config.key}'),
                  controller: _controller,
                  enabled: true,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
                  style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan),
                  decoration: InputDecoration(
                    isDense: true,
                    suffixText: _unitSuffix(),
                    hintText: '—',
                    contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(6),
                      borderSide: const BorderSide(color: AmiColors.slate700),
                    ),
                  ),
                  onChanged: _submit,
                ),
              ),
            ],
          ),
          if (widget.config.key == 'max_open_risk_pct') ...[
            const SizedBox(height: 4),
            Text(
              l.settingsRiskLimitsMaxOpenRiskPreviewNote,
              style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
            ),
          ],
          if (disclosureMsg != null) ...[
            const SizedBox(height: 4),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.warning_amber_rounded, size: 14, color: AmiColors.hexAmber),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    disclosureMsg,
                    style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}

/// Retro-tightening disclosure (assign §3): shown after a successful save
/// that made `GET /v1/mandate/{id}/audit` report a new portfolio-level
/// breach. There is no preview-the-candidate-mandate endpoint (BL12's own
/// docstring: "Designed to be called by mobile immediately after a
/// successful PATCH"), so this cannot fire strictly before the PATCH — it
/// fires immediately after, before the user can act on the save as if
/// nothing changed. Disclosed in the CR101-MOBILE bridge as a measured
/// deviation from the assign's "before saving" wording.
class RetroTighteningDialog extends StatelessWidget {
  const RetroTighteningDialog({super.key, required this.tickers});

  final List<String> tickers;

  static Future<void> show(BuildContext context, List<String> tickers) {
    return showDialog<void>(
      context: context,
      builder: (_) => RetroTighteningDialog(tickers: tickers),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return AlertDialog(
      backgroundColor: AmiColors.slate800,
      title: Text(l.settingsRiskLimitsRetroTitle, style: AmiTypography.h4),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l.settingsRiskLimitsRetroBody, style: AmiTypography.body),
          if (tickers.isNotEmpty) ...[
            const SizedBox(height: AmiSpacing.s),
            Text(
              l.settingsRiskLimitsRetroTickers(tickers.join(', ')),
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber),
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(l.settingsRiskLimitsRetroDismiss),
        ),
      ],
    );
  }
}
