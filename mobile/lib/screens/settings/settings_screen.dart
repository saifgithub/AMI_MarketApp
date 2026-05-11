/// Settings — currently just the Mandate editor.
///
/// Every editable field maps to a server-side mandate field. Save triggers
/// a PATCH /v1/mandate/{user_id}, which bumps the version and writes a
/// mandate_edit journal entry. The change is reflected the next time any
/// agent prompt is composed (1-on-1, Coach, Room, Sim).
library;

import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  int? _localRiskScore;
  int? _localMaxDD;
  ComplianceFlags? _localCompliance;
  bool _dirty = false;

  void _initFrom(UserMandate m) {
    _localRiskScore ??= m.riskScore;
    _localMaxDD ??= m.maxDrawdownPct;
    _localCompliance ??= m.compliance;
  }

  Future<void> _save() async {
    final updates = <String, dynamic>{};
    final m = ref.read(mandateNotifierProvider).mandate;
    if (m == null) return;
    if (_localRiskScore != null && _localRiskScore != m.riskScore) {
      updates['risk_score'] = _localRiskScore;
    }
    if (_localMaxDD != null && _localMaxDD != m.maxDrawdownPct) {
      updates['max_drawdown_pct'] = _localMaxDD;
    }
    if (_localCompliance != null) {
      updates['compliance'] = _localCompliance!.toPatchJson();
    }
    if (updates.isEmpty) return;
    await ref.read(mandateNotifierProvider.notifier).patch(updates);
    setState(() => _dirty = false);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Mandate updated.')),
    );
    // Sim portfolio's compliance evaluation depends on the mandate —
    // refresh so any newly-rejectable holdings show up correctly.
    await ref.read(simNotifierProvider.notifier).refresh();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(mandateNotifierProvider);
    final m = state.mandate;
    if (m == null) {
      return const Scaffold(
        backgroundColor: AmiColors.slate900,
        body: Center(child: CircularProgressIndicator()),
      );
    }
    _initFrom(m);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            _Header(version: m.version, saving: state.saving, dirty: _dirty, onSave: _save),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(AmiSpacing.m),
                children: [
                  _Section(title: 'MY MANDATE', children: [
                    _RiskSlider(
                      value: _localRiskScore ?? m.riskScore,
                      onChanged: (v) => setState(() {
                        _localRiskScore = v;
                        _dirty = true;
                      }),
                    ),
                    const SizedBox(height: AmiSpacing.l),
                    _DrawdownPicker(
                      value: _localMaxDD ?? m.maxDrawdownPct,
                      onChanged: (v) => setState(() {
                        _localMaxDD = v;
                        _dirty = true;
                      }),
                    ),
                  ]),
                  const SizedBox(height: AmiSpacing.l),
                  _Section(title: 'COMPLIANCE', children: [
                    _ComplianceToggles(
                      value: _localCompliance ?? m.compliance,
                      onChanged: (next) => setState(() {
                        _localCompliance = next;
                        _dirty = true;
                      }),
                    ),
                  ]),
                  const SizedBox(height: AmiSpacing.l),
                  _Section(title: 'PROFILE', children: [
                    _ReadOnlyRow(label: 'Plan', value: m.plan),
                    _ReadOnlyRow(label: 'Locale', value: m.locale),
                    _ReadOnlyRow(label: 'Timezone', value: m.timezone),
                    _ReadOnlyRow(label: 'Path', value: m.path),
                    _ReadOnlyRow(label: 'Horizon', value: m.horizon),
                    _ReadOnlyRow(label: 'Primary goal', value: m.primaryGoal),
                    _ReadOnlyRow(label: 'Credits', value: '${m.creditBalance}'),
                  ]),
                  const SizedBox(height: AmiSpacing.xxl),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}


class _Header extends StatelessWidget {
  const _Header({
    required this.version,
    required this.saving,
    required this.dirty,
    required this.onSave,
  });

  final int version;
  final bool saving;
  final bool dirty;
  final VoidCallback onSave;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 64,
      padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
      decoration: const BoxDecoration(
        color: AmiColors.glassChrome,
        border: Border(bottom: BorderSide(color: AmiColors.slate700)),
      ),
      child: Row(
        children: [
          Text('SETTINGS',
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexBlue)),
          const SizedBox(width: AmiSpacing.s),
          Text('mandate v$version', style: AmiTypography.caption),
          const Spacer(),
          if (dirty)
            TextButton(
              onPressed: saving ? null : onSave,
              child: Text(saving ? 'SAVING…' : 'SAVE',
                  style: AmiTypography.labelMono.copyWith(color: AmiColors.hexBlue)),
            ),
        ],
      ),
    );
  }
}


class _Section extends StatelessWidget {
  const _Section({required this.title, required this.children});
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: AmiTypography.labelMono.copyWith(color: AmiColors.hexBlue)),
          const SizedBox(height: AmiSpacing.s),
          ...children,
        ],
      ),
    );
  }
}


class _RiskSlider extends StatelessWidget {
  const _RiskSlider({required this.value, required this.onChanged});
  final int value;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Text('Risk score', style: AmiTypography.body),
            const Spacer(),
            Text('$value / 5',
                style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
          ],
        ),
        Slider(
          value: value.toDouble(),
          min: 1,
          max: 5,
          divisions: 4,
          activeColor: AmiColors.hexCyan,
          inactiveColor: AmiColors.slate700,
          label: '$value',
          onChanged: (v) => onChanged(v.round()),
        ),
        Text(
          _riskLabel(value),
          style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
        ),
      ],
    );
  }

  String _riskLabel(int v) {
    switch (v) {
      case 1:
        return 'Capital preservation. Small sizes, tight stops.';
      case 2:
        return 'Cautious. Below-average position sizing.';
      case 3:
        return 'Balanced. Standard 3-5% positions.';
      case 4:
        return 'Aggressive. Larger sizes on high-conviction setups.';
      case 5:
        return 'Highest risk tolerance. Concentrated bets allowed.';
      default:
        return '';
    }
  }
}


class _DrawdownPicker extends StatelessWidget {
  const _DrawdownPicker({required this.value, required this.onChanged});
  final int value;
  final ValueChanged<int> onChanged;

  static const _options = [10, 20, 30, 50, 100];

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Text('Max drawdown', style: AmiTypography.body),
            const Spacer(),
            Text('$value%',
                style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber)),
          ],
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 6,
          children: [
            for (final o in _options)
              ChoiceChip(
                label: Text('$o%',
                    style: AmiTypography.labelMono.copyWith(fontSize: 11)),
                selected: o == value,
                onSelected: (_) => onChanged(o),
                selectedColor: AmiColors.hexAmber.withValues(alpha: 0.2),
                backgroundColor: AmiColors.slate900,
                side: BorderSide(
                  color: o == value ? AmiColors.hexAmber : AmiColors.slate700,
                ),
              ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          'Your PM refuses trades that would push the portfolio past this.',
          style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
        ),
      ],
    );
  }
}


class _ComplianceToggles extends StatelessWidget {
  const _ComplianceToggles({required this.value, required this.onChanged});
  final ComplianceFlags value;
  final ValueChanged<ComplianceFlags> onChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _row('Halal screen', value.halal, (v) => onChanged(value.copyWith(halal: v))),
        _row('ESG-lite', value.esgLite, (v) => onChanged(value.copyWith(esgLite: v))),
        _row('No tobacco / alcohol / gambling', value.noTobaccoAlcoholGambling,
            (v) => onChanged(value.copyWith(noTobaccoAlcoholGambling: v))),
        _row('No fossil fuels', value.noFossilFuels,
            (v) => onChanged(value.copyWith(noFossilFuels: v))),
        _row('Long-only', value.longOnly, (v) => onChanged(value.copyWith(longOnly: v))),
        _row('Liquid-only', value.liquidOnly,
            (v) => onChanged(value.copyWith(liquidOnly: v))),
      ],
    );
  }

  Widget _row(String label, bool v, ValueChanged<bool> onChanged) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          Expanded(child: Text(label, style: AmiTypography.body)),
          Switch(
            value: v,
            onChanged: onChanged,
            activeThumbColor: AmiColors.hexGreen,
            inactiveThumbColor: AmiColors.slate600,
          ),
        ],
      ),
    );
  }
}


class _ReadOnlyRow extends StatelessWidget {
  const _ReadOnlyRow({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(child: Text(label, style: AmiTypography.body)),
          Text(value,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.textHigh)),
        ],
      ),
    );
  }
}
