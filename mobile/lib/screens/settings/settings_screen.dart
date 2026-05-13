/// Settings — currently just the Mandate editor.
///
/// Every editable field maps to a server-side mandate field. Save triggers
/// a PATCH /v1/mandate/{user_id}, which bumps the version and writes a
/// mandate_edit journal entry. The change is reflected the next time any
/// agent prompt is composed (1-on-1, Coach, Room, Sim).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/i18n/locale_provider.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/auth/sign_in_screen.dart';
import 'package:ami_trade/screens/feedback/bug_report_sheet.dart';
import 'package:ami_trade/state/feedback_providers.dart';
import 'package:ami_trade/services/api/backend_modes.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/backend_mode_provider.dart';
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
      SnackBar(content: Text(AppLocalizations.of(context).settingsMandateUpdated)),
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
    final l = AppLocalizations.of(context);
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
                  _Section(title: l.settingsSectionMandate, children: [
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
                  _Section(title: l.settingsSectionCompliance, children: [
                    _ComplianceToggles(
                      value: _localCompliance ?? m.compliance,
                      onChanged: (next) => setState(() {
                        _localCompliance = next;
                        _dirty = true;
                      }),
                    ),
                  ]),
                  const SizedBox(height: AmiSpacing.l),
                  _Section(title: l.settingsSectionProfile, children: [
                    _ReadOnlyRow(label: l.settingsProfilePlan, value: m.plan),
                    _ReadOnlyRow(label: l.settingsProfileLocale, value: m.locale),
                    _ReadOnlyRow(label: l.settingsProfileTimezone, value: m.timezone),
                    _ReadOnlyRow(label: l.settingsProfilePath, value: m.path),
                    _ReadOnlyRow(label: l.settingsProfileHorizon, value: m.horizon),
                    _ReadOnlyRow(label: l.settingsProfilePrimaryGoal, value: m.primaryGoal),
                    _ReadOnlyRow(label: l.settingsProfileCredits, value: '${m.creditBalance}'),
                  ]),
                  const SizedBox(height: AmiSpacing.l),
                  const _LanguageSection(),
                  const SizedBox(height: AmiSpacing.l),
                  const _AccountSection(),
                  if (kAllowBackendSwitch) ...[
                    const SizedBox(height: AmiSpacing.l),
                    const _DeveloperSection(),
                  ],
                  const SizedBox(height: AmiSpacing.l),
                  _AppVersionChip(onLongPress: () => showBugReportSheet(context, ref)),
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
    final l = AppLocalizations.of(context);
    return Container(
      height: 64,
      padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
      decoration: const BoxDecoration(
        color: AmiColors.glassChrome,
        border: Border(bottom: BorderSide(color: AmiColors.slate700)),
      ),
      child: Row(
        children: [
          Text(l.settingsHeading,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexBlue)),
          const SizedBox(width: AmiSpacing.s),
          Text(l.settingsMandateVersion(version), style: AmiTypography.caption),
          const Spacer(),
          if (dirty)
            TextButton(
              onPressed: saving ? null : onSave,
              child: Text(saving ? l.settingsSaving : l.settingsSave,
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
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(l.settingsRiskScore, style: AmiTypography.body),
            const Spacer(),
            Text(l.settingsRiskScoreValue(value),
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
          _riskLabel(l, value),
          style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
        ),
      ],
    );
  }

  String _riskLabel(AppLocalizations l, int v) {
    switch (v) {
      case 1:
        return l.settingsRiskLabel1;
      case 2:
        return l.settingsRiskLabel2;
      case 3:
        return l.settingsRiskLabel3;
      case 4:
        return l.settingsRiskLabel4;
      case 5:
        return l.settingsRiskLabel5;
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
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(l.settingsMaxDrawdown, style: AmiTypography.body),
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
          l.settingsMaxDrawdownExplain,
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
    final l = AppLocalizations.of(context);
    return Column(
      children: [
        _row(l.settingsComplianceHalal, value.halal,
            (v) => onChanged(value.copyWith(halal: v))),
        _row(l.settingsComplianceEsgLite, value.esgLite,
            (v) => onChanged(value.copyWith(esgLite: v))),
        _row(l.settingsComplianceTAG, value.noTobaccoAlcoholGambling,
            (v) => onChanged(value.copyWith(noTobaccoAlcoholGambling: v))),
        _row(l.settingsComplianceFossil, value.noFossilFuels,
            (v) => onChanged(value.copyWith(noFossilFuels: v))),
        _row(l.settingsComplianceLongOnly, value.longOnly,
            (v) => onChanged(value.copyWith(longOnly: v))),
        _row(l.settingsComplianceLiquidOnly, value.liquidOnly,
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


/// "ACCOUNT" — surfaces the current auth state and routes to SignInScreen.
class _AccountSection extends ConsumerWidget {
  const _AccountSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authNotifierProvider).user;
    final claimed = user != null && !user.isAnonymous;
    final l = AppLocalizations.of(context);
    return _Section(
      title: l.settingsSectionAccount,
      children: [
        _ReadOnlyRow(
          label: l.settingsAccountStatus,
          value: claimed ? l.settingsAccountSignedIn : l.settingsAccountGuest,
        ),
        if (claimed)
          _ReadOnlyRow(label: l.settingsAccountHandle, value: user.displayHandle),
        const SizedBox(height: AmiSpacing.s),
        if (!claimed)
          Text(
            l.settingsAccountGuestNote,
            style: AmiTypography.caption,
          ),
        const SizedBox(height: AmiSpacing.s),
        SizedBox(
          height: 40,
          child: OutlinedButton(
            onPressed: () {
              Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => const SignInScreen(),
              ));
            },
            child: Text(claimed ? l.settingsManageAccount : l.settingsSignIn),
          ),
        ),
      ],
    );
  }
}


// ── Language picker (A11) ───────────────────────────────────────────────


class _LanguageSection extends ConsumerWidget {
  const _LanguageSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final current = ref.watch(localeNotifierProvider);
    final l = AppLocalizations.of(context);
    return _Section(
      title: l.settingsSectionLanguageUpper,
      children: [
        for (final opt in localeOptions)
          _LanguageRow(
            option: opt,
            selected: _matches(opt.locale, current),
            onTap: () => ref
                .read(localeNotifierProvider.notifier)
                .setLocale(opt.locale),
          ),
        const SizedBox(height: AmiSpacing.xs),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.s),
          child: Text(
            l.settingsLanguagePlaceholderNote,
            style: AmiTypography.caption,
          ),
        ),
      ],
    );
  }

  bool _matches(Locale? a, Locale? b) {
    if (a == null && b == null) return true;
    if (a == null || b == null) return false;
    return a.languageCode == b.languageCode;
  }
}


class _LanguageRow extends StatelessWidget {
  const _LanguageRow({
    required this.option,
    required this.selected,
    required this.onTap,
  });
  final LocaleOption option;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(
          children: [
            Icon(
              selected ? Icons.radio_button_checked : Icons.radio_button_off,
              color: selected ? AmiColors.hexBlue : AmiColors.textLow,
              size: 20,
            ),
            const SizedBox(width: AmiSpacing.s),
            Text(option.nativeName, style: AmiTypography.body),
            const SizedBox(width: AmiSpacing.s),
            if (option.nativeName != option.englishName)
              Text(
                '· ${option.englishName}',
                style: AmiTypography.caption,
              ),
          ],
        ),
      ),
    );
  }
}


// ── Developer — active backend (Alpha / Beta / Prod) ────────────────────
//
// Rendered only when ALLOW_BACKEND_SWITCH=true was set at build time
// (see docs/08_tech/backend_modes.md). The whole subtree is gated by
// `if (kAllowBackendSwitch)` at the call site so prod builds compile
// the section out entirely under tree-shaking.


class _DeveloperSection extends ConsumerWidget {
  const _DeveloperSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final active = ref.watch(backendModeProvider);
    final activeUrl = ref.watch(activeBackendUrlProvider);
    final available = BackendUrls.availableModes;
    final l = AppLocalizations.of(context);
    return _Section(
      title: l.settingsSectionDeveloper,
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: AmiSpacing.s),
          child: Text(
            l.settingsDeveloperActive,
            style: AmiTypography.labelMono.copyWith(color: AmiColors.textHigh),
          ),
        ),
        for (final m in BackendMode.values)
          _BackendModeRow(
            mode: m,
            selected: m == active,
            disabled: !available.contains(m),
            onTap: () => ref.read(backendModeProvider.notifier).setMode(m),
          ),
        const SizedBox(height: AmiSpacing.s),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.xs),
          child: Text(
            activeUrl ?? l.settingsDeveloperNoUrl,
            style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
            maxLines: 2, overflow: TextOverflow.ellipsis,
          ),
        ),
        const SizedBox(height: AmiSpacing.xs),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.xs),
          child: Text(
            l.settingsDeveloperFootnote,
            style: AmiTypography.caption,
          ),
        ),
      ],
    );
  }
}


class _BackendModeRow extends StatelessWidget {
  const _BackendModeRow({
    required this.mode,
    required this.selected,
    required this.disabled,
    required this.onTap,
  });
  final BackendMode mode;
  final bool selected;
  final bool disabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = disabled
        ? AmiColors.textLow
        : (selected ? AmiColors.hexBlue : AmiColors.textHigh);
    return InkWell(
      onTap: disabled ? null : onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            Icon(
              selected ? Icons.radio_button_checked : Icons.radio_button_off,
              size: 20,
              color: disabled ? AmiColors.textLow : color,
            ),
            const SizedBox(width: AmiSpacing.s),
            Text(backendModeLabel(mode),
                style: AmiTypography.labelMono.copyWith(color: color)),
            if (disabled) ...[
              const SizedBox(width: AmiSpacing.s),
              Text(AppLocalizations.of(context).settingsDeveloperNotInBuild,
                  style: AmiTypography.caption.copyWith(color: AmiColors.textLow)),
            ],
          ],
        ),
      ),
    );
  }
}


class _AppVersionChip extends StatelessWidget {
  const _AppVersionChip({required this.onLongPress});
  final VoidCallback onLongPress;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: GestureDetector(
        onLongPress: onLongPress,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: AmiSpacing.xs),
          child: Text(
            'AMI Trade v$kAppVersion',
            style: AmiTypography.caption.copyWith(color: AmiColors.slate600),
          ),
        ),
      ),
    );
  }
}
