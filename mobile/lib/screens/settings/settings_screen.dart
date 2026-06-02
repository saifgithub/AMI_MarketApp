/// Settings — currently just the Mandate editor.
///
/// Every editable field maps to a server-side mandate field. Save triggers
/// a PATCH /v1/mandate/{user_id}, which bumps the version and writes a
/// mandate_edit journal entry. The change is reflected the next time any
/// agent prompt is composed (1-on-1, Coach, Room, Sim).
library;

import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/i18n/locale_provider.dart';
import 'package:ami_trade/state/theme_provider.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/auth/sign_in_screen.dart';
import 'package:ami_trade/screens/coach/ai_coach_screen.dart';
import 'package:ami_trade/screens/feedback/bug_report_sheet.dart';
import 'package:ami_trade/state/feedback_providers.dart';
import 'package:ami_trade/services/api/backend_modes.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/backend_mode_provider.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/screens/settings/alpaca_connect_screen.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

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
                  const _ThemeSection(),
                  const SizedBox(height: AmiSpacing.l),
                  const _HelpSection(),
                  const SizedBox(height: AmiSpacing.l),
                  const _WalkthroughSection(),
                  const SizedBox(height: AmiSpacing.l),
                  const _AlpacaSection(),
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
                label: Text('$o%'),
                labelStyle: AmiTypography.labelMono.copyWith(
                  fontSize: 11,
                  color: o == value ? AmiColors.hexAmber : AmiColors.textMed,
                ),
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


/// Plain-English explanations for each compliance flag. Surfaced by
/// tapping the label in _ComplianceToggles (separate from flipping the
/// switch). User-filed bug: people wanted to know what "Halal screen"
/// actually means before turning it on.
const Map<String, _ComplianceExplanation> _complianceExplanations = {
  'halal': _ComplianceExplanation(
    title: 'Halal screen',
    body: 'Filters out tickers that fail standard Shariah screens: '
        'conventional financials (interest-based banking, insurance), '
        'alcohol, pork, tobacco, gambling, adult entertainment, and '
        'weapons. Also flags companies whose debt-to-equity ratio '
        'crosses common AAOIFI thresholds.',
  ),
  'esgLite': _ComplianceExplanation(
    title: 'ESG-lite',
    body: 'A light-touch screen for the most-controversial categories: '
        'thermal coal, oil sands, controversial weapons, and severe '
        'governance flags. Not a full ESG rating — just a floor.',
  ),
  'tag': _ComplianceExplanation(
    title: 'No tobacco / alcohol / gambling',
    body: 'Filters out tickers whose primary revenue comes from '
        'tobacco, alcohol, or gambling operations. Pure-play exclusions '
        'only; diversified conglomerates with a small exposure are not '
        'caught.',
  ),
  'fossil': _ComplianceExplanation(
    title: 'No fossil fuels',
    body: 'Filters out oil, gas, and coal producers, plus the pipelines '
        'and services companies whose revenue depends on them. Utilities '
        'with a transition plan are not auto-excluded.',
  ),
  'longOnly': _ComplianceExplanation(
    title: 'Long-only',
    body: 'No short selling, no inverse ETFs, no put options used as '
        'standalone bets. You can still hedge with protective puts '
        'against a long position you already hold.',
  ),
  'liquidOnly': _ComplianceExplanation(
    title: 'Liquid-only',
    body: 'Only tickers with sufficient average daily volume to enter '
        'and exit cleanly. Filters out micro-caps and thinly-traded '
        'names where a market order can move the price against you.',
  ),
};


class _ComplianceExplanation {
  const _ComplianceExplanation({required this.title, required this.body});
  final String title;
  final String body;
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
        _row(context, 'halal', l.settingsComplianceHalal, value.halal,
            (v) => onChanged(value.copyWith(halal: v))),
        _row(context, 'esgLite', l.settingsComplianceEsgLite, value.esgLite,
            (v) => onChanged(value.copyWith(esgLite: v))),
        _row(context, 'tag', l.settingsComplianceTAG, value.noTobaccoAlcoholGambling,
            (v) => onChanged(value.copyWith(noTobaccoAlcoholGambling: v))),
        _row(context, 'fossil', l.settingsComplianceFossil, value.noFossilFuels,
            (v) => onChanged(value.copyWith(noFossilFuels: v))),
        _row(context, 'longOnly', l.settingsComplianceLongOnly, value.longOnly,
            (v) => onChanged(value.copyWith(longOnly: v))),
        _row(context, 'liquidOnly', l.settingsComplianceLiquidOnly, value.liquidOnly,
            (v) => onChanged(value.copyWith(liquidOnly: v))),
      ],
    );
  }

  Widget _row(BuildContext context, String key, String label, bool v,
      ValueChanged<bool> onChanged) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          Expanded(
            child: InkWell(
              onTap: () => _showExplanation(context, key),
              borderRadius: BorderRadius.circular(4),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(
                  children: [
                    Flexible(child: Text(label, style: AmiTypography.body)),
                    const SizedBox(width: 6),
                    const Icon(
                      Icons.info_outline,
                      size: 14,
                      color: AmiColors.textLow,
                    ),
                  ],
                ),
              ),
            ),
          ),
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

  void _showExplanation(BuildContext context, String key) {
    final explain = _complianceExplanations[key];
    if (explain == null) return;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AmiColors.slate800,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(
            AmiSpacing.l, AmiSpacing.l, AmiSpacing.l, AmiSpacing.xl,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 36, height: 4,
                  decoration: BoxDecoration(
                    color: AmiColors.slate600,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: AmiSpacing.m),
              Text(explain.title, style: AmiTypography.h4),
              const SizedBox(height: AmiSpacing.s),
              Text(
                explain.body,
                style: AmiTypography.body.copyWith(color: AmiColors.textMed),
              ),
            ],
          ),
        );
      },
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
        if (claimed) ...[
          const SizedBox(height: AmiSpacing.s),
          SizedBox(
            height: 40,
            child: OutlinedButton(
              onPressed: ref.read(authNotifierProvider).loading
                  ? null
                  : () async {
                      await ref
                          .read(authNotifierProvider.notifier)
                          .signOut();
                      if (!context.mounted) return;
                      Navigator.of(context).push(MaterialPageRoute(
                        builder: (_) =>
                            const SignInScreen(showSignedOutBanner: true),
                      ));
                    },
              style: OutlinedButton.styleFrom(
                foregroundColor: AmiColors.hexRed,
                side: const BorderSide(color: AmiColors.hexRed),
              ),
              child: const Text('Sign out'),
            ),
          ),
        ],
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


// ── Theme (alpha is dark-only) ────────────────────────────────────────────
//
// The full light theme exists at the MaterialApp level (amiLightTheme), but
// the alpha screens hard-code AmiColors.slate900 / slate800 backgrounds in
// 37 places — so flipping the system toggle has no visible effect. Rather
// than ship a broken control, this section is informational only until the
// screens are migrated to theme-aware colors (tracked as A29 in the plan).
// Force the persisted mode back to dark so a previously stored "light"
// setting can't make any subsequent screen look half-themed.


class _ThemeSection extends ConsumerWidget {
  const _ThemeSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final current = ref.watch(themeModeProvider);
    if (current != ThemeMode.dark) {
      // Coerce on first render; safe no-op if already dark.
      Future.microtask(
        () => ref.read(themeModeProvider.notifier).setMode(ThemeMode.dark),
      );
    }
    return _Section(
      title: 'APPEARANCE',
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.dark_mode, color: AmiColors.hexBlue, size: 20),
              const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Dark theme', style: AmiTypography.body),
                    const SizedBox(height: 2),
                    Text(
                      'Alpha is dark-only. Light + Follow System land in v1.0.',
                      style: AmiTypography.caption,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
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


class _WalkthroughSection extends ConsumerWidget {
  const _WalkthroughSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    return _Section(
      title: l.tourSettingsSectionTitle,
      children: [
        InkWell(
          onTap: () async {
            await ref.read(tourServiceProvider).resetAll();
            if (!context.mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(
              content: Text(l.tourSettingsResetDone),
              behavior: SnackBarBehavior.floating,
            ));
          },
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Row(
              children: [
                const Icon(Icons.explore_outlined,
                    color: AmiColors.hexCyan, size: 18),
                const SizedBox(width: AmiSpacing.s),
                Expanded(
                  child: Text(l.tourSettingsRestart, style: AmiTypography.body),
                ),
                const Icon(Icons.refresh, color: AmiColors.textLow, size: 18),
              ],
            ),
          ),
        ),
      ],
    );
  }
}


class _HelpSection extends StatelessWidget {
  const _HelpSection();

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'HELP',
      children: [
        InkWell(
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute<void>(builder: (_) => const AICoachScreen()),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Row(
              children: [
                const Icon(Icons.help_outline, color: AmiColors.hexBlue, size: 18),
                const SizedBox(width: AmiSpacing.s),
                Expanded(
                  child: Text('AI Coach — Q&A library',
                      style: AmiTypography.body),
                ),
                const Icon(Icons.chevron_right, color: AmiColors.textLow),
              ],
            ),
          ),
        ),
        _LegalRow(label: 'Terms of Service', url: 'https://www.agenticmarketintel.ai/terms/'),
        _LegalRow(label: 'Privacy Policy', url: 'https://www.agenticmarketintel.ai/privacy/'),
      ],
    );
  }
}

class _LegalRow extends StatelessWidget {
  const _LegalRow({required this.label, required this.url});
  final String label;
  final String url;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () => launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(
          children: [
            const Icon(Icons.open_in_new, color: AmiColors.hexBlue, size: 18),
            const SizedBox(width: AmiSpacing.s),
            Expanded(child: Text(label, style: AmiTypography.body)),
            const Icon(Icons.chevron_right, color: AmiColors.textLow),
          ],
        ),
      ),
    );
  }
}


class _AppVersionChip extends ConsumerWidget {
  const _AppVersionChip({required this.onLongPress});
  final VoidCallback onLongPress;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final version = ref.watch(appVersionProvider).valueOrNull ?? '…';
    return Center(
      child: GestureDetector(
        onLongPress: onLongPress,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: AmiSpacing.xs),
          child: Text(
            'AMI Trade v$version',
            style: AmiTypography.caption.copyWith(color: AmiColors.slate600),
          ),
        ),
      ),
    );
  }
}


// ── Alpaca paper trading section (AT:R45) ──────────────────────────────


class _AlpacaSection extends ConsumerWidget {
  const _AlpacaSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authNotifierProvider).user;
    final claimed = user != null && !user.isAnonymous;
    if (!claimed) return const SizedBox.shrink();

    final statusAsync = ref.watch(alpacaStatusProvider);

    return _Section(
      title: 'CONNECTED ACCOUNTS',
      children: [
        statusAsync.when(
          loading: () => const SizedBox(
            height: 48,
            child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
          ),
          error: (_, __) => _AlpacaRow(linked: false, ref: ref),
          data: (status) => _AlpacaRow(linked: status.linked, ref: ref),
        ),
      ],
    );
  }
}

class _AlpacaRow extends StatelessWidget {
  const _AlpacaRow({required this.linked, required this.ref});

  final bool linked;
  final WidgetRef ref;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: linked ? AmiColors.hexGreen : AmiColors.slate600,
          ),
        ),
        const SizedBox(width: AmiSpacing.s),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'ALPACA PAPER',
                style: AmiTypography.labelMono.copyWith(color: AmiColors.textHigh),
              ),
              Text(
                linked ? 'Connected' : 'Not connected',
                style: AmiTypography.caption.copyWith(
                  color: linked ? AmiColors.hexGreen : AmiColors.slate500,
                ),
              ),
            ],
          ),
        ),
        TextButton(
          onPressed: () => linked ? _disconnect(context) : _connect(context),
          child: Text(
            linked ? 'Disconnect' : 'Connect',
            style: AmiTypography.labelMono.copyWith(
              color: linked ? AmiColors.hexRed : AmiColors.hexBlue,
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _connect(BuildContext context) async {
    final result = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => const AlpacaConnectScreen()),
    );
    if (result == true) {
      ref.invalidate(alpacaStatusProvider);
      ref.invalidate(alpacaPortfolioProvider);
      ref.invalidate(alpacaPositionsProvider);
    }
  }

  Future<void> _disconnect(BuildContext context) async {
    final api = ref.read(apiClientProvider);
    try {
      await api.alpacaUnlink();
    } catch (_) {}
    ref.invalidate(alpacaStatusProvider);
    ref.invalidate(alpacaPortfolioProvider);
    ref.invalidate(alpacaPositionsProvider);
  }
}
