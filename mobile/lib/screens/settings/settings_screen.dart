/// Settings — currently just the Mandate editor.
///
/// Every editable field maps to a server-side mandate field. Save triggers
/// a PATCH /v1/mandate/{user_id}, which bumps the version and writes a
/// mandate_edit journal entry. The change is reflected the next time any
/// agent prompt is composed (1-on-1, Coach, Room, Sim).
library;

import 'package:ami_trade/features/build_identity.dart';
import 'package:ami_trade/features/games/games_gate.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/i18n/locale_provider.dart';
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
import 'package:ami_trade/screens/settings/risk_limits_section.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/league_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/screens/you/you_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/confirm_restart_onboarding.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:ami_trade/widgets/paywall/upgrade_paywall.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ami_trade/screens/settings/legal_screen.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key, this.embedded = false});

  /// Rendered as a segment of `YOU` rather than as a screen of its own
  /// (CR133 §4). Embedded, it draws no `Scaffold`, no `SafeArea` and no header:
  /// `YouScreen` owns all three, and the header it owns has to carry the Save
  /// button, so this State publishes what that header needs to
  /// [settingsHeaderProvider] instead of rendering it.
  ///
  /// Kept as a flag rather than a second widget because everything below the
  /// header — thirteen sections, the mandate editor, the dirty tracking — is
  /// identical either way, and two copies of that is the DEF098 class.
  final bool embedded;

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  int? _localRiskScore;
  int? _localMaxDD;
  ComplianceFlags? _localCompliance;
  bool _dirty = false;

  // CR101-MOBILE — the seven risk-limit fields. `containsKey` marks a field
  // touched this session; the (possibly null) value is what gets PATCHed.
  // Cleared after a successful save so the NEXT build reads straight off
  // the server's returned mandate (acceptance 2's round-trip contract).
  final Map<String, dynamic> _pendingRiskLimits = {};
  bool _riskLimitsExpanded = false;

  void _initFrom(UserMandate m) {
    _localRiskScore ??= m.riskScore;
    _localMaxDD ??= m.maxDrawdownPct;
    _localCompliance ??= m.compliance;
  }

  void _onRiskLimitChanged(LimitFieldConfig cfg, num? value) {
    setState(() => _pendingRiskLimits[cfg.key] = value);
  }

  /// Acceptance 3: an explicit override on EITHER CR101-BE1 cap moves the
  /// dial to Custom — those two are the only fields the backend defines a
  /// risk-profile preset relationship for (see file header).
  bool _isCustomRiskProfile(UserMandate m) {
    final sector = _pendingRiskLimits.containsKey('sector_cap_pct')
        ? _pendingRiskLimits['sector_cap_pct'] as num?
        : m.sectorCapPct;
    final singleName = _pendingRiskLimits.containsKey('single_name_cap_pct')
        ? _pendingRiskLimits['single_name_cap_pct'] as num?
        : m.singleNameCapPct;
    return sector != null || singleName != null;
  }

  /// L1: choosing a risk-profile score re-asserts "follow the profile
  /// preset" for the two CR101-BE1 caps, so the dial always writes a
  /// coherent, non-Custom state — matching the assign's "L1 writes all
  /// caps coherently from a preset". The five CR101-BE2 fields have no
  /// backend-defined preset relationship to risk_score (disclosed in the
  /// hand-off), so L1 does not touch them.
  void _onRiskScoreChanged(int v) {
    setState(() {
      _localRiskScore = v;
      _dirty = true;
      _pendingRiskLimits['sector_cap_pct'] = null;
      _pendingRiskLimits['single_name_cap_pct'] = null;
    });
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
    final touchedRiskLimits = Map<String, dynamic>.from(_pendingRiskLimits);
    updates.addAll(touchedRiskLimits);
    if (updates.isEmpty) return;
    await ref.read(mandateNotifierProvider.notifier).patch(updates);
    setState(() {
      _dirty = false;
      _pendingRiskLimits.clear();
    });
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(AppLocalizations.of(context).settingsMandateUpdated)),
    );
    // Sim portfolio's compliance evaluation depends on the mandate —
    // refresh so any newly-rejectable holdings show up correctly.
    await ref.read(simNotifierProvider.notifier).refresh();
    // CR101-MOBILE retro-tightening (assign §3): only `max_open_positions`
    // and `max_open_risk_pct` have a portfolio-state dimension at all. No
    // preview endpoint exists (BL12's audit reads the CURRENTLY PERSISTED
    // mandate), so this necessarily runs immediately after the save, not
    // before it — disclosed in the bridge.
    final touchedRetroFields = touchedRiskLimits.keys
        .where((k) => k == 'max_open_positions' || k == 'max_open_risk_pct');
    if (touchedRetroFields.isEmpty || !mounted) return;
    try {
      final audit = await ref.read(apiClientProvider).auditMandateHoldings(m.userId);
      if (!audit.anyRetroBreach || !mounted) return;
      await RetroTighteningDialog.show(context, audit.violationTickers);
    } catch (_) {
      // DEF194 — the swallow itself stays (a failed audit read must not
      // block or misrepresent a save that already succeeded), but silence
      // on this path used to be indistinguishable from "nothing is in
      // breach": the user tightened a limit specifically to find out
      // whether it bites, and got the same nothing either way. This is
      // NOT an error dialog — the save DID succeed, and presenting it as a
      // failure would be the opposite misrepresentation — just the third,
      // honest state: "we could not check", visible rather than logged.
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content:
                Text(AppLocalizations.of(context).settingsRetroAuditFailed)),
      );
    }
  }

  bool get _hasUnsavedEdits => _dirty || _pendingRiskLimits.isNotEmpty;

  /// Publish what `YOU`'s header renders on this screen's behalf (CR133 §4.2).
  ///
  /// Derived in `build` and pushed after the frame rather than written at each
  /// of the four mutation sites: a mutation site added later cannot forget to
  /// call this, and forgetting would leave the Save button absent while edits
  /// were pending — the failure would be invisible until someone lost an edit.
  void _publishHeaderState(int version, bool saving) {
    if (!widget.embedded) return;
    final next = SettingsHeaderState(
      version: version,
      dirty: _hasUnsavedEdits,
      saving: saving,
    );
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final notifier = ref.read(settingsHeaderProvider.notifier);
      if (notifier.state != next) notifier.state = next;
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(mandateNotifierProvider);
    final m = state.mandate;
    if (m == null) {
      const loading = Center(child: CircularProgressIndicator());
      return widget.embedded
          ? loading
          : const Scaffold(
              backgroundColor: AmiColors.slate900, body: loading);
    }
    _initFrom(m);
    _publishHeaderState(m.version, state.saving);
    // `YOU` owns the header while this pane is embedded, so its Save button
    // asks here rather than holding a closure over this State (CR133 §4.2).
    if (widget.embedded) {
      ref.listen<int>(settingsSaveRequestProvider, (_, __) {
        if (!state.saving) _save();
      });
    }
    final l = AppLocalizations.of(context);
    final body = Column(
          children: [
            if (!widget.embedded)
              AmiScreenHeader(
                title: l.settingsHeading,
                titleColor: AmiColors.hexBlue,
                subtitle: l.settingsMandateVersion(m.version),
                showBack: Navigator.of(context).canPop(),
                actions: [
                  if (_hasUnsavedEdits)
                    TextButton(
                      onPressed: state.saving ? null : _save,
                      child: Text(
                          state.saving ? l.settingsSaving : l.settingsSave,
                          style: AmiTypography.labelMono
                              .copyWith(color: AmiColors.hexBlue)),
                    ),
                ],
              ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(AmiSpacing.m),
                children: [
                  _Section(title: l.settingsSectionMandate, children: [
                    _RiskSlider(
                      value: _localRiskScore ?? m.riskScore,
                      onChanged: _onRiskScoreChanged,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _isCustomRiskProfile(m)
                          ? l.settingsRiskLimitsProfileCustom
                          : l.settingsRiskLimitsProfileFollowing,
                      style: AmiTypography.caption.copyWith(color: AmiColors.hexCyan),
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
                  _Section(title: l.settingsSectionRiskLimits, children: [
                    RiskLimitsSection(
                      mandate: m,
                      pending: _pendingRiskLimits,
                      onFieldChanged: _onRiskLimitChanged,
                      expanded: _riskLimitsExpanded,
                      onToggleExpanded: () =>
                          setState(() => _riskLimitsExpanded = !_riskLimitsExpanded),
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
                  _MembershipSection(mandate: m),
                  const SizedBox(height: AmiSpacing.l),
                  const _LeagueSection(),
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
        );

    return widget.embedded
        ? body
        : Scaffold(
            backgroundColor: AmiColors.slate900,
            body: SafeArea(child: body),
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
///
/// CR069 Phase 1b: the `halal` entry is NOT in this map. Its copy is
/// observance-sensitive and must be translatable, so it is resolved from the
/// ARB in `_explanationFor` instead of hardcoded English here. The DEF084 body
/// that used to sit here ("a curated demonstration universe, not a Sharia
/// screen") described the 7-ticker allowlist and is now false in the other
/// direction — the flag enforces a real sourced AAOIFI screen.
const Map<String, _ComplianceExplanation> _complianceExplanations = {
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
            (v) => onChanged(value.copyWith(halal: v)),
            subtitle: l.settingsComplianceHalalSubtitle),
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
      ValueChanged<bool> onChanged, {String? subtitle}) {
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
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
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
                    if (subtitle != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        subtitle,
                        style: AmiTypography.caption
                            .copyWith(color: AmiColors.textLow),
                      ),
                    ],
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

  /// Localized override first, then the hardcoded map. Only `halal` is
  /// localized (CR069 Phase 1b) — it is the observance-sensitive one, and its
  /// copy has to be able to differ per locale rather than shipping EN to every
  /// reader.
  _ComplianceExplanation? _explanationFor(BuildContext context, String key) {
    if (key == 'halal') {
      final l = AppLocalizations.of(context);
      return _ComplianceExplanation(
        title: l.settingsComplianceHalalExplainTitle,
        body: l.settingsComplianceHalalExplainBody,
      );
    }
    return _complianceExplanations[key];
  }

  void _showExplanation(BuildContext context, String key) {
    final explain = _explanationFor(context, key);
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


/// CR084 — "MEMBERSHIP": the second upgrade entry point (the Room 402 wall is
/// the primary). Opens the live RC paywall as a bottom sheet. On a successful
/// purchase the paywall refreshes entitlement from the backend; we invalidate
/// the mandate view so the plan/credit rows above reflect it immediately.
class _MembershipSection extends ConsumerWidget {
  const _MembershipSection({required this.mandate});
  final UserMandate mandate;

  String _resetDateStr() {
    final r = mandate.creditsResetAt;
    if (r == null) return 'the 1st';
    return '${r.year}-${r.month.toString().padLeft(2, '0')}-'
        '${r.day.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    return _Section(
      title: l.settingsSectionMembership,
      children: [
        _ReadOnlyRow(label: l.settingsProfilePlan, value: mandate.plan),
        const SizedBox(height: AmiSpacing.s),
        SizedBox(
          height: 40,
          child: OutlinedButton.icon(
            icon: const Icon(Icons.workspace_premium_outlined, size: 18),
            style: OutlinedButton.styleFrom(
              foregroundColor: AmiColors.hexCyan,
              side: const BorderSide(color: AmiColors.hexCyan),
            ),
            onPressed: () => showUpgradeSheet(
              context,
              resetDateLabel: _resetDateStr(),
              onPurchased: () =>
                  ref.read(mandateNotifierProvider.notifier).refresh(),
            ),
            label: Text(l.settingsMembershipUpgrade),
          ),
        ),
      ],
    );
  }
}


/// CR011 (C3) — "LEAGUE": pseudonymous handle + reputation total + a one-shot
/// handle regenerate. (The "show my real name" toggle is deferred — no backend
/// route to persist `show_display_name` yet; tracked as a follow-up.)
class _LeagueSection extends ConsumerWidget {
  const _LeagueSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final me = ref.watch(leagueMeProvider).valueOrNull;
    if (me == null) return const SizedBox.shrink();
    return _Section(
      title: l.settingsSectionLeague,
      children: [
        _ReadOnlyRow(label: l.leagueHandle, value: me.handle),
        _ReadOnlyRow(label: l.leagueReputation, value: '${me.reputation}'),
        const SizedBox(height: AmiSpacing.s),
        SizedBox(
          height: 40,
          child: OutlinedButton.icon(
            icon: const Icon(Icons.refresh, size: 16),
            onPressed: () => _regenerate(context, ref, l),
            label: Text(l.leagueRegenerate),
          ),
        ),
      ],
    );
  }

  Future<void> _regenerate(
      BuildContext context, WidgetRef ref, AppLocalizations l) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final handle = await ref.read(apiClientProvider).regenerateHandle();
      ref.invalidate(leagueMeProvider);
      messenger
          .showSnackBar(SnackBar(content: Text('${l.leagueHandle}: $handle')));
    } catch (_) {
      // 409 already_regenerated, or a transient failure — one message covers
      // both (the backend allows only one regeneration).
      messenger
          .showSnackBar(SnackBar(content: Text(l.leagueRegenerateFailed)));
    }
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


// D-062 / D4: dark is pinned at the app level (see app.dart) — no more
// render-time coercion of the theme provider. This is a static status row.
class _ThemeSection extends StatelessWidget {
  const _ThemeSection();

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
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
                    Text(l.settingsAppearanceValue, style: AmiTypography.body),
                    const SizedBox(height: 2),
                    Text(l.settingsAppearanceBody, style: AmiTypography.caption),
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
// (see docs/initial_specs/08_tech/backend_modes.md). The whole subtree is gated by
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
        // CR173 slice 2 — `restart onboarding` moved here from the Floor.
        //
        // Frame A′ has no room for it and the capability map puts it "with the
        // rest of Settings", which since CR133 means inside YOU. It was the
        // app's ONLY route back into the interview, so leaving it behind on a
        // rebuilt Floor would have deleted the capability rather than moved it.
        //
        // DEF152 still governs the tap: this destroys the most expensive
        // artefact the user produces, and it used to sit one scroll under the
        // Convene CTA styled as a caption-sized link, where a tester hit it by
        // accident. The dialog names what is lost. It sits below the tour reset
        // deliberately — the destructive one is not the first thing under the
        // thumb.
        InkWell(
          onTap: () => _restartOnboarding(context, ref),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Row(
              children: [
                const Icon(Icons.restart_alt,
                    color: AmiColors.hexAmber, size: 18),
                const SizedBox(width: AmiSpacing.s),
                Expanded(
                  child: Text(l.floorRestartOnboarding,
                      style: AmiTypography.body),
                ),
                const Icon(Icons.chevron_right,
                    color: AmiColors.textLow, size: 18),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _restartOnboarding(BuildContext context, WidgetRef ref) async {
    if (!await confirmRestartOnboarding(context)) return;
    if (!context.mounted) return;
    // DEF160 (mobile half): this IS the restart path — the only place
    // `isRestart: true` should ever be set. See OnboardingNotifier.reset.
    await ref.read(onboardingNotifierProvider.notifier).reset(isRestart: true);
    if (!context.mounted) return;
    Navigator.of(context).pushReplacementNamed('/onboarding');
  }
}


class _HelpSection extends ConsumerWidget {
  const _HelpSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
        // CR133 §6 — the labelled bug-report door.
        //
        // Until this existed the only way to file a report was to scroll past
        // thirteen sections and **long-press an unlabelled grey version
        // string**, while `bug_report_sheet.dart` documents "call this from
        // anywhere" and had exactly one caller. That was already a defect;
        // CR133 demoting Settings a level deeper made it worse at the exact
        // moment we are trying to get reports out of alpha testers. The chip's
        // long-press stays — it costs nothing and some muscle memory exists —
        // but it is no longer the only door.
        InkWell(
          onTap: () => showBugReportSheet(context, ref),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Row(
              children: [
                const Icon(Icons.bug_report_outlined,
                    color: AmiColors.hexAmber, size: 18),
                const SizedBox(width: AmiSpacing.s),
                Expanded(
                  child: Text(AppLocalizations.of(context).settingsReportProblem,
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
      onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => LegalScreen(title: label, url: url),
      )),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(
          children: [
            const Icon(Icons.description_outlined, color: AmiColors.hexBlue, size: 18),
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
            // DEF306 — the version alone does not identify the binary: two
            // artifacts called `0.1.0+94` differed by a whole tab. The gates
            // ride along so `adb` is never the tool of first resort again.
            buildIdentityLabel(version, gamesEnabled: kGamesEnabled),
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
