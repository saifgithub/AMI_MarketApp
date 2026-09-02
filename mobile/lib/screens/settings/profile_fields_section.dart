/// CR220 — the identity/goal half of the mandate, made editable.
///
/// The Concierge interview sets `primary_goal`, `horizon`, `path`,
/// `display_name`, `timezone` and `learning_style`, and Settings rendered every
/// one of them as a read-only row. The backend has always accepted them on
/// `PATCH /v1/mandate/{user_id}` — none is in `CLIENT_UNWRITABLE_MANDATE_FIELDS`
/// — so the gap was purely that nothing offered the control.
///
/// The option VALUES are the mandate schema's own enums and are hard-coded here
/// deliberately: they are a fixed contract (`PrimaryGoal`, `Horizon`, `Path`,
/// `LearningStyle` in `backend/app/schemas/mandate.py`), not a derived or
/// preset-backed number. That is a different thing from CR129's "server-sourced
/// only" fence, which exists because a resolved CAP is computed from risk_score
/// and a client copy would drift from what the safety floor enforces. Nothing
/// is computed here — a wrong value would 422 at the schema, loudly.
///
/// `_labelFor` maps value → localised label and falls back to the raw value for
/// anything it does not recognise, so a server that grows a new enum member
/// renders it as itself instead of blank.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

/// One selectable option: the wire value plus how to label it.
class MandateOption {
  const MandateOption(this.value, this.label);
  final String value;
  final String label;
}

List<MandateOption> primaryGoalOptions(AppLocalizations l) => [
      MandateOption('retirement', l.settingsGoalRetirement),
      MandateOption('long_term_wealth', l.settingsGoalLongTermWealth),
      MandateOption('income_now', l.settingsGoalIncomeNow),
      MandateOption('specific_goal', l.settingsGoalSpecificGoal),
      MandateOption('learning_to_trade', l.settingsGoalLearningToTrade),
      MandateOption('exploring', l.settingsGoalExploring),
    ];

/// Wording mirrors the backend's own `_horizon_label()` so the label the user
/// picks is the one the agents are told about.
List<MandateOption> horizonOptions(AppLocalizations l) => [
      MandateOption('short', l.settingsHorizonShort),
      MandateOption('medium', l.settingsHorizonMedium),
      MandateOption('long', l.settingsHorizonLong),
      MandateOption('very_long', l.settingsHorizonVeryLong),
    ];

/// `both` is offered because CR220 wired its three `overlay_generator`
/// branches. Before that it fell through to the LONG_HORIZON prompt, so
/// offering it would have been a control that silently meant something else.
List<MandateOption> pathOptions(AppLocalizations l) => [
      MandateOption('active', l.settingsPathActive),
      MandateOption('long_horizon', l.settingsPathLongHorizon),
      MandateOption('both', l.settingsPathBoth),
    ];

List<MandateOption> learningStyleOptions(AppLocalizations l) => [
      MandateOption('quick', l.settingsLearningQuick),
      MandateOption('story', l.settingsLearningStory),
      MandateOption('visual', l.settingsLearningVisual),
      MandateOption('hands_on', l.settingsLearningHandsOn),
    ];

String labelFor(List<MandateOption> options, String value) {
  for (final o in options) {
    if (o.value == value) return o.label;
  }
  return value;
}

/// A labelled row of ChoiceChips over a fixed option set — the enum
/// generalisation of `_DrawdownPicker`, which is the shape already established
/// in this screen.
class MandateChoiceRow extends StatelessWidget {
  const MandateChoiceRow({
    super.key,
    required this.label,
    required this.options,
    required this.value,
    required this.onChanged,
    this.explain,
    this.fieldKey,
  });

  final String label;
  final List<MandateOption> options;
  final String value;
  final ValueChanged<String> onChanged;
  final String? explain;
  final String? fieldKey;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(label, style: AmiTypography.body),
            const Spacer(),
            Flexible(
              child: Text(
                labelFor(options, value),
                textAlign: TextAlign.right,
                style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber),
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: [
            for (final o in options)
              ChoiceChip(
                key: fieldKey == null ? null : Key('${fieldKey}_${o.value}'),
                label: Text(o.label),
                labelStyle: AmiTypography.labelMono.copyWith(
                  fontSize: 11,
                  color: o.value == value ? AmiColors.hexAmber : AmiColors.textMed,
                ),
                selected: o.value == value,
                onSelected: (_) => onChanged(o.value),
                selectedColor: AmiColors.hexAmber.withValues(alpha: 0.2),
                backgroundColor: AmiColors.slate900,
                side: BorderSide(
                  color: o.value == value ? AmiColors.hexAmber : AmiColors.slate700,
                ),
              ),
          ],
        ),
        if (explain != null) ...[
          const SizedBox(height: 4),
          Text(
            explain!,
            style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
          ),
        ],
      ],
    );
  }
}

/// A free-text mandate field (display name). Kept as its own widget so the
/// controller lifecycle is not the screen's problem.
class MandateTextRow extends StatefulWidget {
  const MandateTextRow({
    super.key,
    required this.label,
    required this.value,
    required this.onChanged,
    this.hint,
    this.maxLength = 40,
    this.fieldKey,
  });

  final String label;
  final String value;
  final ValueChanged<String> onChanged;
  final String? hint;
  final int maxLength;
  final String? fieldKey;

  @override
  State<MandateTextRow> createState() => _MandateTextRowState();
}

class _MandateTextRowState extends State<MandateTextRow> {
  late final TextEditingController _c = TextEditingController(text: widget.value);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(child: Text(widget.label, style: AmiTypography.body)),
          SizedBox(
            width: 170,
            child: TextField(
              key: widget.fieldKey == null ? null : Key(widget.fieldKey!),
              controller: _c,
              textAlign: TextAlign.right,
              maxLength: widget.maxLength,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber),
              decoration: InputDecoration(
                isDense: true,
                counterText: '',
                hintText: widget.hint,
                hintStyle: AmiTypography.caption.copyWith(color: AmiColors.textLow),
                border: const UnderlineInputBorder(),
              ),
              // Trimmed on the way out: a trailing space is invisible in the
              // field but is a real difference to the diff that decides whether
              // a PATCH is sent at all.
              onChanged: (v) => widget.onChanged(v.trim()),
            ),
          ),
        ],
      ),
    );
  }
}

/// The three verbatim interview answers. Editable so the user can correct what
/// the Concierge recorded them as saying; deliberately NOT injected into any
/// agent prompt (CR220 D5), which the explain line states plainly rather than
/// leaving the user to assume the analysts read them.
class RiskQuotesSection extends StatelessWidget {
  const RiskQuotesSection({
    super.key,
    required this.quotes,
    required this.onChanged,
  });

  final List<String> quotes;
  final ValueChanged<List<String>> onChanged;

  static const _labelKeys = 3;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final labels = [
      l.settingsRiskQuoteDrawdown,
      l.settingsRiskQuoteRegret,
      l.settingsRiskQuoteConcentration,
    ];
    // A mandate written before a quote existed can carry fewer than three.
    final padded = [
      for (var i = 0; i < _labelKeys; i++) i < quotes.length ? quotes[i] : '',
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          l.settingsRiskQuotesExplain,
          style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
        ),
        const SizedBox(height: AmiSpacing.s),
        for (var i = 0; i < _labelKeys; i++)
          MandateTextRow(
            key: Key('riskQuote_$i'),
            fieldKey: 'riskQuoteField_$i',
            label: labels[i],
            value: padded[i],
            maxLength: 140,
            onChanged: (v) {
              final next = [...padded];
              next[i] = v;
              onChanged(next);
            },
          ),
      ],
    );
  }
}
