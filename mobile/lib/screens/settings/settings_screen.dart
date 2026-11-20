/// Settings — currently just the Mandate editor.
///
/// Every editable field maps to a server-side mandate field. Save triggers
/// a PATCH /v1/mandate/{user_id}, which bumps the version and writes a
/// mandate_edit journal entry. The change is reflected the next time any
/// agent prompt is composed (1-on-1, Coach, Room, Sim).
library;

import 'package:ami_trade/features/beta/beta_build.dart';
import 'package:ami_trade/features/build_identity.dart';
import 'package:ami_trade/features/games/games_gate.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/i18n/locale_provider.dart';
import 'package:ami_trade/i18n/plan_names.dart';
import 'package:ami_trade/models/account.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/settings/profile_fields_section.dart';
import 'package:ami_trade/screens/settings/street_comparison_setting.dart';
import 'package:ami_trade/screens/settings/ticker_rules_section.dart';
import 'package:ami_trade/screens/auth/sign_in_screen.dart';
import 'package:ami_trade/screens/coach/ai_coach_screen.dart';
import 'package:ami_trade/screens/feedback/bug_report_sheet.dart';
import 'package:ami_trade/state/feedback_providers.dart';
import 'package:ami_trade/services/ads/admob_config.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/state/ads_providers.dart';
import 'package:ami_trade/services/api/backend_modes.dart';
import 'package:ami_trade/state/account_providers.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/backend_mode_provider.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/screens/settings/alpaca_connect_screen.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:ami_trade/screens/settings/day_trader_disclosure_dialog.dart';
import 'package:ami_trade/screens/settings/risk_limits_section.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/me_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/screens/you/you_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/ads/ad_slot.dart';
import 'package:ami_trade/widgets/confirm_restart_onboarding.dart';
import 'package:ami_trade/widgets/credits_line.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:ami_trade/widgets/paywall/upgrade_paywall.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ami_trade/screens/settings/legal_screen.dart';
import 'package:ami_trade/widgets/alpaca/alpaca_badge.dart' show kAlpacaPaperLabel;
import 'package:ami_trade/qa/semantics_ids.dart';

/// DEF481 item 3 — a section a caller can ask Settings to scroll to on open.
/// The trade ticket's OPEN MY MANDATE uses it so a blocked trade lands on the
/// rule that blocked it instead of the top of a thirteen-section list.
enum SettingsAnchor {
  /// The risk-limit rows (concentration caps, cooldown, position/trade counts,
  /// open risk).
  riskLimits,

  /// The compliance toggles (halal, long-only, liquid-only, ...).
  compliance,

  /// The ticker allow/block list.
  tickerRules,
}

/// DEF481 item 3 — which Settings section holds the rule that blocked an
/// order, from the server's `blocked_by` slug. Anything unrecognised
/// (`compliance`, `long_only`, `locale`, absent) lands on the compliance
/// toggles — the section a mandate refusal most often comes from.
SettingsAnchor settingsAnchorForBlockedBy(String? blockedBy) {
  switch (blockedBy) {
    case 'allowlist':
    case 'blocklist':
      return SettingsAnchor.tickerRules;
    case 'concentration':
    case 'cooldown':
    case 'max_open_positions':
    case 'over_trading':
    case 'open_risk':
      return SettingsAnchor.riskLimits;
    default:
      return SettingsAnchor.compliance;
  }
}

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key, this.embedded = false, this.anchor});

  /// Section to scroll into view after the first frame. Null = stay at the top.
  final SettingsAnchor? anchor;

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

  // CR220 — the identity/goal fields. Same shadow-copy shape as the three
  // above: null means "untouched this session", so the diff in `_save()` can
  // tell "not edited" apart from "edited back to the stored value".
  String? _localPrimaryGoal;
  String? _localHorizon;
  String? _localPath;
  String? _localLearningStyle;
  String? _localDisplayName;
  String? _localTimezone;
  List<String>? _localRiskQuotes;

  // CR101-MOBILE — the seven risk-limit fields. `containsKey` marks a field
  // touched this session; the (possibly null) value is what gets PATCHed.
  // Cleared after a successful save so the NEXT build reads straight off
  // the server's returned mandate (acceptance 2's round-trip contract).
  final Map<String, dynamic> _pendingRiskLimits = {};
  bool _riskLimitsExpanded = false;
  int _discardGeneration = 0;

  // DEF481 item 3 — one key per scroll target. The list is lazy, so a target
  // far down has no context until it has been scrolled near; see
  // `_scrollToAnchor`.
  final ScrollController _scroll = ScrollController();
  final Map<SettingsAnchor, GlobalKey> _anchorKeys = {
    for (final a in SettingsAnchor.values) a: GlobalKey(),
  };

  @override
  void initState() {
    super.initState();
    if (widget.anchor != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToAnchor());
    }
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _scrollToAnchor() async {
    final anchor = widget.anchor;
    if (anchor == null) return;
    final key = _anchorKeys[anchor]!;
    // The settings list builds lazily: a section well below the fold has no
    // element yet, so walk the list down until the target exists.
    for (var i = 0; i < 40; i++) {
      if (!mounted) return;
      if (key.currentContext != null) break;
      if (!_scroll.hasClients) return;
      final pos = _scroll.position;
      if (pos.pixels >= pos.maxScrollExtent) return;
      _scroll.jumpTo((pos.pixels + 400).clamp(0.0, pos.maxScrollExtent));
      await WidgetsBinding.instance.endOfFrame;
    }
    final ctx = key.currentContext;
    if (ctx == null || !mounted) return;
    await Scrollable.ensureVisible(
      ctx,
      alignment: 0.05,
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOut,
    );
  }

  void _initFrom(UserMandate m) {
    _localRiskScore ??= m.riskScore;
    _localMaxDD ??= m.maxDrawdownPct;
    _localCompliance ??= m.compliance;
    _localPrimaryGoal ??= m.primaryGoal;
    _localHorizon ??= m.horizon;
    _localPath ??= m.path;
    _localLearningStyle ??= m.learningStyle;
    _localDisplayName ??= m.displayName;
    _localTimezone ??= m.timezone;
    _localRiskQuotes ??= m.riskQuotes;
  }

  /// CR220 — one setter for every scalar identity/goal field, so a new field
  /// is a line in `_save()`'s diff table rather than another near-identical
  /// handler.
  /// List equality for the risk quotes — Dart's `==` on `List` is identity,
  /// so without this every build would look dirty and PATCH on every save.
  static bool _sameStrings(List<String> a, List<String> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }

  void _setLocal(void Function() apply) {
    setState(() {
      apply();
      _dirty = true;
    });
  }

  void _onRiskLimitChanged(LimitFieldConfig cfg, num? value) {
    setState(() => _pendingRiskLimits[cfg.key] = value);
  }

  /// Acceptance 3, post-CR129: the backend derives ALL seven limits from the
  /// risk profile, so an explicit override on ANY of them reads as Custom.
  bool _isCustomRiskProfile(UserMandate m) =>
      hasExplicitRiskLimitOverride(m, _pendingRiskLimits);

  /// L1: choosing a risk-profile score re-asserts "follow the profile
  /// preset" for all seven limits (CR129 — every one of them is
  /// profile-derived now), so the dial always writes a coherent, non-Custom
  /// state.
  void _onRiskScoreChanged(int v) {
    setState(() {
      _localRiskScore = v;
      _dirty = true;
      for (final cfg in kRiskLimitFields) {
        _pendingRiskLimits[cfg.key] = null;
      }
    });
  }

  /// CR129 items 2-3: Day Trader is disclosure-gated — the dialog renders the
  /// SERVER's text and must be confirmed before anything is staged (inform,
  /// don't block). On confirm the served override values are staged VERBATIM
  /// into the pending map; the user's existing Save then PATCHes them, which
  /// is exactly the payload the backend's `is_day_trader_preset()` recognises
  /// (the CR131 cohort marker keys off that round-trip). Nothing is saved
  /// here — disclosure therefore provably precedes the save.
  Future<void> _onDayTraderTapped(UserMandate m) async {
    final preset = m.dayTraderPreset;
    if (preset == null) return;
    // DEF481 item 6 — tapping the chip while it is selected deselects it: the
    // seven limits go back to "follow my risk profile" (null, as the dial
    // does). Risk score, horizon, path and drawdown stay as they now are, and
    // there is no dialog — this only ever tightens. The user still presses Save.
    if (matchesDayTraderPreset(m, _pendingRiskLimits)) {
      setState(() {
        for (final cfg in kRiskLimitFields) {
          _pendingRiskLimits[cfg.key] = null;
        }
      });
      return;
    }
    final ok = await DayTraderDisclosureDialog.show(context, preset.disclosure);
    if (ok != true || !mounted) return;
    setState(() {
      for (final cfg in kRiskLimitFields) {
        _pendingRiskLimits[cfg.key] = preset.overrides[cfg.key];
      }
      // DEF481 item 6 — the profile half, staged straight into the pending
      // fields (NOT via `_onRiskScoreChanged`, which would null the limits
      // just staged). Values are the server's; an older server sends none.
      final p = preset.profile;
      final score = p['risk_score'];
      if (score is num) _localRiskScore = score.toInt();
      final dd = p['max_drawdown_pct'];
      if (dd is num) _localMaxDD = dd.toInt();
      final horizon = p['horizon'];
      if (horizon is String) _localHorizon = horizon;
      final path = p['path'];
      if (path is String) _localPath = path;
      if (p.isNotEmpty) _dirty = true;
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
    // CR220: only send compliance when it actually CHANGED. It used to be sent
    // on every save (harmless while the payload was six bools the server would
    // merge back to themselves) — but `toPatchJson` now always carries
    // `ticker_allowlist`, including a null one, so an untouched save would
    // clear a user's allowlist. Comparing against the server's object is what
    // keeps "I edited my risk score" from silently rewriting a safety control.
    if (_localCompliance != null && _localCompliance != m.compliance) {
      updates['compliance'] = _localCompliance!.toPatchJson();
    }
    // CR220 — the identity/goal fields. Each key here MUST match the backend
    // `Mandate` field name exactly: the store deep-merges by key and the API
    // ignores what it does not recognise, so a typo would 200 and silently
    // drop the change (the DEF195 failure the user cannot see). Pinned by
    // `test/screens/settings/cr220_profile_fields_test.dart`.
    for (final entry in <String, List<Object?>>{
      'primary_goal': [_localPrimaryGoal, m.primaryGoal],
      'horizon': [_localHorizon, m.horizon],
      'path': [_localPath, m.path],
      'learning_style': [_localLearningStyle, m.learningStyle],
      'timezone': [_localTimezone, m.timezone],
    }.entries) {
      final local = entry.value[0];
      if (local != null && local != entry.value[1]) updates[entry.key] = local;
    }
    // Guarded separately: an empty display name would erase the only thing the
    // analysts have to call the user by, and the server has no default to fall
    // back to on a PATCH (unlike onboarding, which stamps "Trader").
    final name = _localDisplayName?.trim();
    if (name != null && name.isNotEmpty && name != m.displayName) {
      updates['display_name'] = name;
    }
    if (_localRiskQuotes != null && !_sameStrings(_localRiskQuotes!, m.riskQuotes)) {
      updates['risk_quotes'] = _localRiskQuotes;
    }
    final touchedRiskLimits = Map<String, dynamic>.from(_pendingRiskLimits);
    updates.addAll(touchedRiskLimits);
    if (updates.isEmpty) return;
    await ref.read(mandateNotifierProvider.notifier).patch(updates);
    setState(() {
      _dirty = false;
      _pendingRiskLimits.clear();
      // CR220: drop the shadow copies so the next build re-reads the server's
      // returned mandate — the same round-trip contract the risk limits keep.
      _localPrimaryGoal = null;
      _localHorizon = null;
      _localPath = null;
      _localLearningStyle = null;
      _localDisplayName = null;
      _localTimezone = null;
      _localRiskQuotes = null;
      _localCompliance = null;
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

  /// DEF470 — the YOU "discard changes" choice. Drops every pending edit and
  /// re-keys the list so text fields rebuild from the stored mandate (their
  /// controllers are seeded once and would otherwise keep the typed text).
  void _discardEdits() {
    setState(() {
      _localRiskScore = null;
      _localMaxDD = null;
      _localCompliance = null;
      _localPrimaryGoal = null;
      _localHorizon = null;
      _localPath = null;
      _localLearningStyle = null;
      _localDisplayName = null;
      _localTimezone = null;
      _localRiskQuotes = null;
      _dirty = false;
      _pendingRiskLimits.clear();
      _discardGeneration++;
    });
  }

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
      ref.listen<int>(settingsDiscardRequestProvider, (_, __) {
        _discardEdits();
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
                controller: _scroll,
                key: ValueKey(_discardGeneration),
                padding: const EdgeInsets.all(AmiSpacing.m),
                children: [
                  _Section(title: l.settingsSectionMandate, children: [
                    _RiskSlider(
                      value: _localRiskScore ?? m.riskScore,
                      onChanged: _onRiskScoreChanged,
                    ),
                    // CR129 item 2: the Day Trader half of the preset picker
                    // (the slider IS the five-profile half). Offered only
                    // when the server serves the full preset — an older
                    // backend simply has no entry, never an approximation.
                    if (dayTraderPresetOfferable(m)) ...[
                      const SizedBox(height: 4),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: Semantics(
                          identifier: SettingsIds.dayTraderPreset,
                          child: ChoiceChip(
                          key: const Key('riskPresetDayTrader'),
                          label: Text(l.settingsRiskPresetDayTrader),
                          labelStyle: AmiTypography.labelMono.copyWith(
                            fontSize: 11,
                            color: matchesDayTraderPreset(m, _pendingRiskLimits)
                                ? AmiColors.hexAmber
                                : AmiColors.textMed,
                          ),
                          selected: matchesDayTraderPreset(m, _pendingRiskLimits),
                          onSelected: (_) => _onDayTraderTapped(m),
                          selectedColor: AmiColors.hexAmber.withValues(alpha: 0.2),
                          backgroundColor: AmiColors.slate900,
                          side: BorderSide(
                            color: matchesDayTraderPreset(m, _pendingRiskLimits)
                                ? AmiColors.hexAmber
                                : AmiColors.slate700,
                          ),
                        )),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        l.settingsRiskPresetDayTraderExplain,
                        style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
                      ),
                    ],
                    const SizedBox(height: 4),
                    // Three states, checked in this order: Day Trader also
                    // trips hasExplicitRiskLimitOverride, so it must win
                    // before the Custom label is considered.
                    Text(
                      matchesDayTraderPreset(m, _pendingRiskLimits)
                          ? l.settingsRiskPresetDayTraderActive
                          : _isCustomRiskProfile(m)
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
                  _Section(
                      key: _anchorKeys[SettingsAnchor.riskLimits],
                      title: l.settingsSectionRiskLimits,
                      children: [
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
                  _Section(
                      key: _anchorKeys[SettingsAnchor.compliance],
                      title: l.settingsSectionCompliance,
                      children: [
                    _ComplianceToggles(
                      value: _localCompliance ?? m.compliance,
                      onChanged: (next) => setState(() {
                        _localCompliance = next;
                        _dirty = true;
                      }),
                    ),
                  ]),
                  const SizedBox(height: AmiSpacing.l),
                  // CR220 — the identity/goal half of the mandate, now
                  // editable. Plan and Credits stay read-only: they are
                  // entitlement state resolved server-side and stripped from
                  // any PATCH by CLIENT_UNWRITABLE_MANDATE_FIELDS (DEF179).
                  // Locale stays read-only here too — it is changed by the
                  // LANGUAGE section below, and offering two controls for one
                  // value is how they drift apart.
                  _Section(title: l.settingsSectionProfile, children: [
                    Text(
                      l.settingsProfileEditHint,
                      style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
                    ),
                    const SizedBox(height: AmiSpacing.s),
                    _ReadOnlyRow(
                        label: l.settingsProfilePlan,
                        value: planDisplayName(l, m.plan)),
                    _ReadOnlyRow(
                      label: l.settingsProfileCredits,
                      value: _creditsRowValue(l, m),
                    ),
                    _ReadOnlyRow(label: l.settingsProfileLocale, value: m.locale),
                    const SizedBox(height: AmiSpacing.s),
                    MandateTextRow(
                      fieldKey: 'displayNameField',
                      label: l.settingsProfileDisplayName,
                      hint: l.settingsProfileDisplayNameHint,
                      value: _localDisplayName ?? m.displayName,
                      onChanged: (v) => _setLocal(() => _localDisplayName = v),
                    ),
                    const SizedBox(height: AmiSpacing.m),
                    MandateChoiceRow(
                      fieldKey: 'primaryGoal',
                      label: l.settingsProfilePrimaryGoal,
                      options: primaryGoalOptions(l),
                      value: _localPrimaryGoal ?? m.primaryGoal,
                      onChanged: (v) => _setLocal(() => _localPrimaryGoal = v),
                    ),
                    const SizedBox(height: AmiSpacing.m),
                    MandateChoiceRow(
                      fieldKey: 'horizon',
                      label: l.settingsProfileHorizon,
                      options: horizonOptions(l),
                      value: _localHorizon ?? m.horizon,
                      onChanged: (v) => _setLocal(() => _localHorizon = v),
                    ),
                    const SizedBox(height: AmiSpacing.m),
                    MandateChoiceRow(
                      fieldKey: 'path',
                      label: l.settingsProfilePath,
                      options: pathOptions(l),
                      value: _localPath ?? m.path,
                      explain: l.settingsPathExplain,
                      onChanged: (v) => _setLocal(() => _localPath = v),
                    ),
                    const SizedBox(height: AmiSpacing.m),
                    MandateChoiceRow(
                      fieldKey: 'learningStyle',
                      label: l.settingsProfileLearningStyle,
                      options: learningStyleOptions(l),
                      value: _localLearningStyle ?? m.learningStyle,
                      onChanged: (v) => _setLocal(() => _localLearningStyle = v),
                    ),
                    const SizedBox(height: AmiSpacing.m),
                    _TimezoneRow(
                      value: _localTimezone ?? m.timezone,
                      onChanged: (v) => _setLocal(() => _localTimezone = v),
                    ),
                  ]),
                  const SizedBox(height: AmiSpacing.l),
                  _Section(
                      key: _anchorKeys[SettingsAnchor.tickerRules],
                      title: l.settingsSectionTickerRules,
                      children: [
                    TickerRulesSection(
                      compliance: _localCompliance ?? m.compliance,
                      validate: (t) => ref.read(apiClientProvider).validateTicker(t),
                      onChanged: (next) => _setLocal(() => _localCompliance = next),
                    ),
                  ]),
                  const SizedBox(height: AmiSpacing.l),
                  _Section(title: l.settingsSectionRiskQuotes, children: [
                    RiskQuotesSection(
                      quotes: _localRiskQuotes ?? m.riskQuotes,
                      onChanged: (next) => _setLocal(() => _localRiskQuotes = next),
                    ),
                  ]),
                  const SizedBox(height: AmiSpacing.l),
                  _MembershipSection(mandate: m),
                  // CR122 — Wallet & Plan is an approved, upsell-only ad
                  // placement (ads.md:44). Self-gating slot.
                  const AdSlot(placement: AdPlacement.walletAndPlan),
                  const SizedBox(height: AmiSpacing.l),
                  const _HandleSection(),
                  const SizedBox(height: AmiSpacing.l),
                  // CR278 (WP-36): the Beta build is English only - no switch.
                  if (!ref.watch(betaEnglishOnlyProvider)) ...const [
                    _LanguageSection(),
                    SizedBox(height: AmiSpacing.l),
                  ],
                  const _ThemeSection(),
                  const SizedBox(height: AmiSpacing.l),
                  const _HelpSection(),
                  // CR122-COMPLIANCE — ad-privacy controls exist ONLY in an
                  // AdMob-enabled build; offering a CCPA/consent control for
                  // an SDK that is not in play would be a false claim (the
                  // DEF085 class).
                  if (AdMobConfig.isConfigured) ...[
                    const SizedBox(height: AmiSpacing.l),
                    const _AdsPrivacySection(),
                  ],
                  const SizedBox(height: AmiSpacing.l),
                  const _WalkthroughSection(),
                  const SizedBox(height: AmiSpacing.l),
                  const _AlpacaSection(),
                  const SizedBox(height: AmiSpacing.l),
                  // CR260 / CR267 WP-21b — show or hide the Street-rating card
                  // under a Room verdict.
                  _Section(title: l.settingsSectionStreetRating, children: const [
                    StreetComparisonSetting(),
                  ]),
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

    return Semantics(identifier: ScreenIds.settingsScreen, container: true, explicitChildNodes: true, child: widget.embedded
        ? body
        : Scaffold(
            backgroundColor: AmiColors.slate900,
            body: SafeArea(child: body),
          ));
  }
}



class _Section extends StatelessWidget {
  const _Section({super.key, required this.title, required this.children});
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
            // DEF435 — `Expanded` + ellipsis so a label that outgrows the Row
            // at a large text scale shrinks instead of overflowing it; the
            // value stays a fixed-width sibling since it's short by
            // construction and the more important of the two to keep intact.
            Expanded(
              child: Text(l.settingsRiskScore,
                  style: AmiTypography.body, overflow: TextOverflow.ellipsis),
            ),
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
    // DEF428 round 2: `max_drawdown_pct` is any whole 1-100 now (was a fixed
    // 5-value Literal), so a mandate hydrated from a typed onboarding answer
    // (e.g. "45%") no longer matches any of the five chips below. Rather
    // than silently deselecting every chip (looks broken) or snapping to
    // the nearest one (loses the exact value the user typed, the same
    // fabrication class DEF428 exists to remove), an extra chip is shown
    // for the off-grid value, labelled with its exact number and selected.
    final isCustom = !_options.contains(value);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            // DEF435 — same fix as `_RiskSlider`'s label/value row above.
            Expanded(
              child: Text(l.settingsMaxDrawdown,
                  style: AmiTypography.body, overflow: TextOverflow.ellipsis),
            ),
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
            if (isCustom)
              ChoiceChip(
                key: const Key('drawdownCustomChip'),
                label: Text(l.settingsMaxDrawdownCustom(value.toString())),
                labelStyle: AmiTypography.labelMono.copyWith(
                  fontSize: 11,
                  color: AmiColors.hexAmber,
                ),
                selected: true,
                // No-op: this chip mirrors the current (already-selected)
                // custom value, it does not offer a new one to pick.
                onSelected: (_) {},
                selectedColor: AmiColors.hexAmber.withValues(alpha: 0.2),
                backgroundColor: AmiColors.slate900,
                side: const BorderSide(color: AmiColors.hexAmber),
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


// Plain-English explanations for each compliance flag live in the ARB
// (`settingsCompliance*Explain*`), surfaced by tapping the label in
// _ComplianceToggles (separate from flipping the switch). User-filed bug:
// people wanted to know what "Halal screen" actually means before turning it
// on. DEF494: the last four were hard-coded English in a const map here, so
// Arabic and Malay readers got English; the map is gone and so is the hole.


/// CR122-COMPLIANCE — CCPA "Do Not Sell" toggle (`ads.md:108`) and the UMP
/// re-consent entry point (`ads.md:107`). Rendered only when AdMob is
/// configured (see the build-site guard above). The toggle is read per ad
/// request downstream, so a flip applies to the next ad without a restart;
/// a failed write reverts the switch and says so — a privacy election is
/// never silently dropped.
class _AdsPrivacySection extends ConsumerStatefulWidget {
  const _AdsPrivacySection();

  @override
  ConsumerState<_AdsPrivacySection> createState() => _AdsPrivacySectionState();
}

class _AdsPrivacySectionState extends ConsumerState<_AdsPrivacySection> {
  bool? _doNotSell;
  bool _consentRowRequired = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final prefs = ref.read(adPrivacyPrefsProvider);
    final consent = ref.read(adMobUmpConsentProvider);
    final doNotSell = await prefs.doNotSell();
    var consentRequired = false;
    if (consent != null) {
      try {
        consentRequired = await consent.isPrivacyOptionsRequired();
      } catch (e) {
        debugPrint('CR122 UMP privacy-options requirement check failed — '
            'hiding the re-consent row: $e');
      }
    }
    if (!mounted) return;
    setState(() {
      _doNotSell = doNotSell;
      _consentRowRequired = consentRequired;
    });
  }

  Future<void> _setDoNotSell(bool value) async {
    final previous = _doNotSell;
    setState(() => _doNotSell = value);
    try {
      await ref.read(adPrivacyPrefsProvider).setDoNotSell(value);
    } catch (e) {
      debugPrint('CR122 CCPA toggle write failed — reverting: $e');
      if (!mounted) return;
      setState(() => _doNotSell = previous);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(
              AppLocalizations.of(context).settingsAdsDoNotSellSaveFailed)));
    }
  }

  Future<void> _openConsentForm() async {
    final consent = ref.read(adMobUmpConsentProvider);
    if (consent == null) return;
    try {
      await consent.showPrivacyOptionsForm();
    } catch (e) {
      debugPrint('CR122 UMP privacy-options form failed: $e');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content:
              Text(AppLocalizations.of(context).settingsAdsConsentFailed)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return _Section(
      title: l.settingsSectionAdPrivacy,
      children: [
        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l.settingsAdsDoNotSell, style: AmiTypography.body),
                  const SizedBox(height: 2),
                  Text(
                    l.settingsAdsDoNotSellSubtitle,
                    style:
                        AmiTypography.caption.copyWith(color: AmiColors.textLow),
                  ),
                ],
              ),
            ),
            Switch(
              value: _doNotSell ?? false,
              onChanged: _doNotSell == null ? null : _setDoNotSell,
              activeThumbColor: AmiColors.hexGreen,
              inactiveThumbColor: AmiColors.slate600,
            ),
          ],
        ),
        if (_consentRowRequired)
          InkWell(
            onTap: _openConsentForm,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 10),
              child: Row(
                children: [
                  const Icon(Icons.privacy_tip_outlined,
                      color: AmiColors.hexBlue, size: 18),
                  const SizedBox(width: AmiSpacing.s),
                  Expanded(
                      child:
                          Text(l.settingsAdsConsentRow, style: AmiTypography.body)),
                  const Icon(Icons.chevron_right, color: AmiColors.textLow),
                ],
              ),
            ),
          ),
      ],
    );
  }
}


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

  /// Every explanation resolves from the ARB, so each reader gets their own
  /// language. `halal` (CR069 Phase 1b) and `esgLite` (DEF339) are the
  /// values-sensitive ones; the other four moved with DEF494.
  _ComplianceExplanation? _explanationFor(BuildContext context, String key) {
    final l = AppLocalizations.of(context);
    switch (key) {
      case 'halal':
        return _ComplianceExplanation(
          title: l.settingsComplianceHalalExplainTitle,
          body: l.settingsComplianceHalalExplainBody,
        );
      case 'esgLite':
        return _ComplianceExplanation(
          title: l.settingsComplianceEsgLiteExplainTitle,
          body: l.settingsComplianceEsgLiteExplainBody,
        );
      case 'tag':
        return _ComplianceExplanation(
          title: l.settingsComplianceTAG,
          body: l.settingsComplianceTagExplainBody,
        );
      case 'fossil':
        return _ComplianceExplanation(
          title: l.settingsComplianceFossil,
          body: l.settingsComplianceFossilExplainBody,
        );
      case 'longOnly':
        return _ComplianceExplanation(
          title: l.settingsComplianceLongOnly,
          body: l.settingsComplianceLongOnlyExplainBody,
        );
      case 'liquidOnly':
        return _ComplianceExplanation(
          title: l.settingsComplianceLiquidOnly,
          body: l.settingsComplianceLiquidOnlyExplainBody,
        );
    }
    return null;
  }

  void _showExplanation(BuildContext context, String key) {
    final explain = _explanationFor(context, key);
    if (explain == null) return;
    showModalBottomSheet<void>(
      context: context,
      useRootNavigator: false,
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


/// CR236/DEF437 — the Profile → Credits row value: "63 · resets 1 Oct" once
/// the reset date is known, else just "63". A null balance (unknown, never
/// the old fabricated `75`) renders `settingsProfileCreditsUnknown` ("—")
/// instead of inventing a number.
String _creditsRowValue(AppLocalizations l, UserMandate m) {
  final balance = m.creditBalance;
  if (balance == null) return l.settingsProfileCreditsUnknown;
  final reset = m.creditsResetAt;
  if (reset == null) return balance.toString();
  return l.settingsProfileCreditsWithReset(
      balance.toString(), creditsResetDateLabel(reset));
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
          // DEF435 — the label already gave way via `Expanded`, but a long
          // VALUE (e.g. "Guest (anonymous)" for account status) had no flex
          // at all, so it alone could still outgrow the Row at a 1.3x text
          // scale once the label had shrunk to its minimum. `Flexible` +
          // ellipsis lets the value give way too, as the last resort rather
          // than the first: `Expanded`'s own default flex keeps the label
          // taking only its fair share, so in practice the value still gets
          // whatever room the label doesn't need.
          Flexible(
            child: Text(value,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.right,
                style: AmiTypography.labelMono.copyWith(color: AmiColors.textHigh)),
          ),
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

  String _resetDateStr() => _creditsResetLabel(mandate);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    return _Section(
      title: l.settingsSectionMembership,
      children: [
        _ReadOnlyRow(
            label: l.settingsProfilePlan,
            value: planDisplayName(l, mandate.plan)),
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


String _creditsResetLabel(UserMandate? mandate) {
  final r = mandate?.creditsResetAt;
  if (r == null) return 'the 1st';
  return '${r.year}-${r.month.toString().padLeft(2, '0')}-'
      '${r.day.toString().padLeft(2, '0')}';
}

/// DEF479 — one confirm for every irreversible Settings action (regenerate
/// handle, sign out, Alpaca disconnect, Alpaca relink). Cancel comes first so
/// the destructive choice is not the one under the thumb; dismissing the
/// dialog any other way counts as cancel.
Future<bool> _confirmDestructive(
  BuildContext context, {
  required String title,
  required String body,
  required String confirmLabel,
}) async {
  final l = AppLocalizations.of(context);
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: AmiColors.slate800,
      title: Text(title,
          style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber)),
      content: Text(body, style: AmiTypography.body),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(false),
          child: Text(l.actionCancel, style: AmiTypography.body),
        ),
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(true),
          child: Text(confirmLabel,
              style: AmiTypography.body.copyWith(color: AmiColors.hexRed)),
        ),
      ],
    ),
  );
  return ok == true;
}

/// CR011 (C3), narrowed by CR109 slice 7 — the pseudonymous handle and its
/// one-shot regenerate. The reputation total that sat beside it is gone with
/// the league Amendment A retired; the handle stayed, because it is the name
/// the games board renders and sorts the field by.
class _HandleSection extends ConsumerWidget {
  const _HandleSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final handle = ref.watch(myHandleProvider).valueOrNull;
    if (handle == null) return const SizedBox.shrink();
    return _Section(
      title: l.settingsSectionIdentity,
      children: [
        _ReadOnlyRow(label: l.leagueHandle, value: handle),
        const SizedBox(height: AmiSpacing.s),
        SizedBox(
          height: 40,
          child: OutlinedButton.icon(
            icon: const Icon(Icons.refresh, size: 16),
            onPressed: () async {
              final ok = await _confirmDestructive(
                context,
                title: l.settingsConfirmRegenTitle,
                body: l.settingsConfirmRegenBody,
                confirmLabel: l.settingsConfirmRegenConfirm,
              );
              if (!ok || !context.mounted) return;
              await _regenerate(context, ref, l);
            },
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
      ref.invalidate(myHandleProvider);
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


/// "ACCOUNT" — surfaces the current auth state; guests go to SignInScreen, a
/// signed-in user's MANAGE ACCOUNT opens the subscription tier picker.
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
          child: Semantics(
            identifier: SettingsIds.accountPrimary,
            child: OutlinedButton(
            key: const Key('accountPrimaryButton'),
            onPressed: () {
              // DEF481 item 7 — a signed-in user managing the account is
              // choosing a subscription tier (Saiful: "should allow user to
              // select the subscription tier level"), so MANAGE ACCOUNT opens
              // the plan picker; guests still go to sign-in.
              if (claimed) {
                showUpgradeSheet(
                  context,
                  resetDateLabel: _creditsResetLabel(
                      ref.read(mandateNotifierProvider).mandate),
                  onPurchased: () =>
                      ref.read(mandateNotifierProvider.notifier).refresh(),
                );
                return;
              }
              Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => const SignInScreen(),
              ));
            },
            child: Text(claimed ? l.settingsManageAccount : l.settingsSignIn),
          )),
        ),
        if (claimed) ...[
          const SizedBox(height: AmiSpacing.s),
          SizedBox(
            height: 40,
            child: OutlinedButton(
              onPressed: ref.read(authNotifierProvider).loading
                  ? null
                  : () async {
                      final ok = await _confirmDestructive(
                        context,
                        title: l.settingsConfirmSignOutTitle,
                        body: l.settingsConfirmSignOutBody,
                        confirmLabel: l.settingsConfirmSignOutConfirm,
                      );
                      if (!ok || !context.mounted) return;
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
              child: Text(l.settingsSignOut),
            ),
          ),
        ],
        const SizedBox(height: AmiSpacing.s),
        _AccountDataActions(guest: !claimed),
      ],
    );
  }
}

/// CR276 (CR267 WP-30) — "Export my data" and "Delete account".
///
/// Apple 5.1.1(v) and Play both require deletion to be reachable in-app, for
/// guests as much as for signed-in users (a guest account is an account). The
/// wording follows the server's policy: "Delete account" in Beta, "Close
/// account" only if the server runs archive mode with counsel's approval. The
/// dialog states what is deleted, what is kept and for how long, and the
/// restore window; it goes through [_confirmDestructive] like every other
/// irreversible Settings action (DEF479).
class _AccountDataActions extends ConsumerWidget {
  const _AccountDataActions({required this.guest});

  final bool guest;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final policy =
        ref.watch(accountPolicyProvider).valueOrNull ?? AccountPolicy.fallback;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          height: 40,
          child: OutlinedButton(
            onPressed: () => _export(context, ref, l),
            child: Text(l.settingsAccountExport),
          ),
        ),
        const SizedBox(height: AmiSpacing.xs),
        Text(l.settingsAccountExportHint, style: AmiTypography.caption),
        const SizedBox(height: AmiSpacing.s),
        SizedBox(
          height: 40,
          child: OutlinedButton(
            onPressed: () => _delete(context, ref, l, policy),
            style: OutlinedButton.styleFrom(
              foregroundColor: AmiColors.hexRed,
              side: const BorderSide(color: AmiColors.hexRed),
            ),
            child: Text(policy.isClose
                ? l.settingsAccountClose
                : l.settingsAccountDelete),
          ),
        ),
      ],
    );
  }

  Future<void> _export(
      BuildContext context, WidgetRef ref, AppLocalizations l) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final bytes = await ref.read(apiClientProvider).exportAccountData();
      final d = DateTime.now().toUtc();
      final stamp =
          '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
      await ref.read(accountExportSinkProvider)(
          bytes, 'ami-data-export-$stamp.json');
    } catch (_) {
      messenger
          .showSnackBar(SnackBar(content: Text(l.settingsAccountExportFailed)));
    }
  }

  Future<void> _delete(BuildContext context, WidgetRef ref, AppLocalizations l,
      AccountPolicy policy) async {
    final close = policy.isClose;
    final body = close
        ? l.settingsConfirmCloseBody(policy.graceDays)
        : l.settingsConfirmDeleteBody(policy.graceDays);
    final ok = await _confirmDestructive(
      context,
      title: close
          ? l.settingsConfirmCloseTitle
          : l.settingsConfirmDeleteTitle,
      body: guest ? '$body\n\n${l.settingsConfirmDeleteGuestNote}' : body,
      confirmLabel: close
          ? l.settingsConfirmCloseConfirm
          : l.settingsConfirmDeleteConfirm,
    );
    if (!ok || !context.mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    final nav = Navigator.of(context);
    final date = MaterialLocalizations.of(context);
    final AccountClosure closure;
    try {
      closure = await ref.read(apiClientProvider).closeAccount();
    } catch (_) {
      messenger
          .showSnackBar(SnackBar(content: Text(l.settingsAccountDeleteFailed)));
      return;
    }
    // The bearer died with the close; clear the device and mint a fresh guest.
    await ref.read(authNotifierProvider.notifier).signOut();
    nav.popUntil((r) => r.isFirst);
    messenger.showSnackBar(SnackBar(
      content: Text(l.settingsAccountDeleteScheduled(
          date.formatMediumDate(closure.restorableUntil.toLocal()))),
    ));
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
            primary: _primaryName(l, opt),
            secondary: _secondaryName(l, opt),
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

  // DEF494 — the System row and the second name come from the ARB, so the
  // picker reads in the language it is showing; the native names (English,
  // Arabic, Bahasa Melayu) stay in their own script on purpose.
  String _primaryName(AppLocalizations l, LocaleOption opt) =>
      opt.locale == null ? l.settingsLanguageSystem : opt.nativeName;

  String _secondaryName(AppLocalizations l, LocaleOption opt) {
    switch (opt.locale?.languageCode) {
      case null:
        return l.settingsLanguageFollowSystem;
      case 'en':
        return l.settingsLanguageEnglish;
      case 'ar':
        return l.settingsLanguageNameArabic;
      case 'ms':
        return l.settingsLanguageNameMalay;
      default:
        return opt.nativeName;
    }
  }

  bool _matches(Locale? a, Locale? b) {
    if (a == null && b == null) return true;
    if (a == null || b == null) return false;
    return a.languageCode == b.languageCode;
  }
}


class _LanguageRow extends StatelessWidget {
  const _LanguageRow({
    required this.primary,
    required this.secondary,
    required this.selected,
    required this.onTap,
  });
  final String primary;
  final String secondary;
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
            // DEF435 — surfaced by the same overflow class as
            // `_RiskSlider`/`_DrawdownPicker`: at a 1.3x text scale the
            // native + English name pair can outgrow the Row. `Flexible`
            // (not `Expanded`) on the native name lets it take only what it
            // needs when short, still ellipsizing if it can't; the English
            // name is dropped from the layout (not just visually clipped)
            // when there's truly no room, via a second `Flexible` with
            // `FlexFit.loose` sized last.
            Flexible(
              child: Text(primary,
                  style: AmiTypography.body, overflow: TextOverflow.ellipsis),
            ),
            if (primary != secondary) ...[
              const SizedBox(width: AmiSpacing.s),
              Flexible(
                child: Text(
                  '· $secondary',
                  style: AmiTypography.caption,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
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
      title: l.settingsSectionAppearance,
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
    final l = AppLocalizations.of(context);
    return _Section(
      title: l.settingsSectionHelp,
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
                  child: Text(l.settingsHelpQaLibrary,
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
        _LegalRow(
            label: AppLocalizations.of(context).settingsTermsOfService,
            url: 'https://www.agenticmarketintel.ai/terms/'),
        _LegalRow(
            label: AppLocalizations.of(context).settingsPrivacyPolicy,
            url: 'https://www.agenticmarketintel.ai/privacy/'),
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

    final linkedAsync = ref.watch(alpacaLinkedProvider);
    final l = AppLocalizations.of(context);

    return _Section(
      title: l.settingsSectionConnectedAccounts,
      children: [
        linkedAsync.when(
          loading: () => const SizedBox(
            height: 48,
            child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
          ),
          error: (_, __) => _AlpacaRow(linked: false, ref: ref),
          data: (linked) {
            // DEF439 — `alpacaLinkedProvider` now means "linked to a
            // confirmed PAPER account". When it is false, a credential may
            // still be sitting on the device from before this fix — check
            // `alpacaStoredNonPaperProvider` so that case reads as "relink",
            // not as "you were never connected".
            final storedNonPaper = !linked &&
                (ref.watch(alpacaStoredNonPaperProvider).valueOrNull ??
                    false);
            return _AlpacaRow(
              linked: linked,
              storedNonPaper: storedNonPaper,
              ref: ref,
            );
          },
        ),
      ],
    );
  }
}

class _AlpacaRow extends StatelessWidget {
  const _AlpacaRow({
    required this.linked,
    required this.ref,
    this.storedNonPaper = false,
  });

  final bool linked;
  final bool storedNonPaper;
  final WidgetRef ref;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Row(
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: linked
                ? AmiColors.hexGreen
                : (storedNonPaper ? AmiColors.hexAmber : AmiColors.slate600),
          ),
        ),
        const SizedBox(width: AmiSpacing.s),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                kAlpacaPaperLabel,
                style: AmiTypography.labelMono.copyWith(color: AmiColors.textHigh),
              ),
              Text(
                // DEF439 — a stored non-paper credential gets its own line:
                // "Not connected" alone would read as "never linked", which
                // is false and drops the reason a relink is needed.
                linked
                    ? l.settingsAlpacaConnected
                    : (storedNonPaper
                        ? l.settingsAlpacaRelinkNeeded
                        : l.settingsAlpacaNotConnected),
                style: AmiTypography.caption.copyWith(
                  color: linked
                      ? AmiColors.hexGreen
                      : (storedNonPaper
                          ? AmiColors.hexAmber
                          : AmiColors.slate500),
                ),
              ),
            ],
          ),
        ),
        TextButton(
          onPressed: () => _onPressed(context),
          child: Text(
            linked
                ? l.settingsAlpacaDisconnect
                : (storedNonPaper
                    ? l.settingsAlpacaRelink
                    : l.settingsAlpacaConnect),
            style: AmiTypography.labelMono.copyWith(
              color: linked ? AmiColors.hexRed : AmiColors.hexBlue,
            ),
          ),
        ),
      ],
    );
  }

  /// DEF479 — Disconnect wipes the credential at once, and Relink wipes the
  /// stale one before the connect screen opens (so backing out leaves the user
  /// unlinked). Both are irreversible, so both ask first; a plain Connect
  /// (nothing stored) does not.
  Future<void> _onPressed(BuildContext context) async {
    if (!linked && !storedNonPaper) {
      await _connect(context, false);
      return;
    }
    final l = AppLocalizations.of(context);
    final ok = await _confirmDestructive(
      context,
      title: linked
          ? l.settingsConfirmAlpacaDisconnectTitle
          : l.settingsConfirmAlpacaRelinkTitle,
      body: linked
          ? l.settingsConfirmAlpacaDisconnectBody
          : l.settingsConfirmAlpacaRelinkBody,
      confirmLabel: linked
          ? l.settingsConfirmAlpacaDisconnectConfirm
          : l.settingsConfirmAlpacaRelinkConfirm,
    );
    if (!ok || !context.mounted) return;
    if (linked) {
      await _disconnect(context);
    } else {
      await _connect(context, true);
    }
  }

  Future<void> _connect(BuildContext context, bool storedNonPaper) async {
    // DEF439 — a stale non-paper credential is cleared before the connect
    // screen opens, the same local-wipe-first order `_disconnect` uses, so
    // the new link cannot be read as "on top of" the old one.
    if (storedNonPaper) {
      await AlpacaCredentialStore.clear();
    }
    if (!context.mounted) return;
    final result = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => const AlpacaConnectScreen()),
    );
    if (result == true || storedNonPaper) {
      ref.read(alpacaSnapshotCacheProvider).invalidate();
      ref.invalidate(alpacaLinkedProvider);
      ref.invalidate(alpacaStoredNonPaperProvider);
      ref.invalidate(alpacaPortfolioProvider);
      ref.invalidate(alpacaPositionsProvider);
    }
  }

  /// CR202: disconnecting is purely local — the key only ever lived on this
  /// device, so the credential is gone the moment the store is cleared.
  ///
  /// CR203 adds one server call, and the ORDER matters: the local wipe happens
  /// FIRST and unconditionally, so a failed report can only ever leave the
  /// backend over-reporting a link that no longer exists — never leave a
  /// credential on the device after the user asked for it gone.
  Future<void> _disconnect(BuildContext context) async {
    await AlpacaCredentialStore.clear();
    try {
      await ref.read(apiClientProvider).alpacaReportLinkState(false);
    } catch (_) {}
    ref.read(alpacaSnapshotCacheProvider).invalidate();
    ref.invalidate(alpacaLinkedProvider);
    ref.invalidate(alpacaStoredNonPaperProvider);
    ref.invalidate(alpacaPortfolioProvider);
    ref.invalidate(alpacaPositionsProvider);
  }
}


/// CR220 — the timezone picker.
///
/// Onboarding sends `DateTime.now().timeZoneName`, which is an ABBREVIATION
/// ("GMT+8", "PST"), not the IANA identifier `mandate_schema.md` specifies. So
/// most users' stored value is something no library can parse. This row does
/// not try to repair that automatically — it offers the correct value and lets
/// the user pick, which is the self-correcting path CR220 chose over touching
/// the capture side.
///
/// The list is deliberately short and regional rather than the full ~600-zone
/// IANA database: the value is narration only today (every day/week boundary in
/// the safety floor is pinned to UTC by design, see `risk_limits.py`), so a
/// searchable 600-row picker would be a lot of surface for a field nothing
/// enforces. The user's current value is always offered even if it is not in
/// the list, so a picker refresh can never silently drop what they had.
class _TimezoneRow extends StatelessWidget {
  const _TimezoneRow({required this.value, required this.onChanged});

  final String value;
  final ValueChanged<String> onChanged;

  static const _zones = <String>[
    'UTC',
    'Asia/Riyadh',
    'Asia/Dubai',
    'Asia/Kuala_Lumpur',
    'Asia/Singapore',
    'Asia/Karachi',
    'Asia/Kolkata',
    'Asia/Jakarta',
    'Asia/Tokyo',
    'Europe/London',
    'Europe/Paris',
    'Europe/Istanbul',
    'America/New_York',
    'America/Chicago',
    'America/Los_Angeles',
    'Australia/Sydney',
  ];

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final options = [
      if (!_zones.contains(value)) value,
      ..._zones,
    ];
    return Row(
      children: [
        Flexible(
          child: Text(l.settingsProfileTimezone,
              style: AmiTypography.body, overflow: TextOverflow.ellipsis),
        ),
        const SizedBox(width: AmiSpacing.s),
        // DEF435-adjacent hardening: the longest IANA zone strings
        // ("America/Los_Angeles") could in principle outgrow the Row at a
        // 1.3x text scale. `selectedItemBuilder` renders a SEPARATE widget
        // for the closed state so it can ellipsize independently of the
        // popup's own item text (deliberately left unclipped there — the
        // open menu has the full screen width). `alignedDropdown: false`
        // drops `DropdownButton`'s built-in ~20px alignment padding, and the
        // icon is set explicitly smaller, both purely to give the closed
        // state more room to work with.
        Expanded(
          child: ButtonTheme(
            alignedDropdown: false,
            child: DropdownButton<String>(
              key: const Key('timezoneField'),
              value: value,
              isDense: true,
              isExpanded: true,
              iconSize: 18,
              dropdownColor: AmiColors.slate800,
              underline: const SizedBox.shrink(),
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber),
              selectedItemBuilder: (context) => [
                for (final z in options)
                  Text(z,
                      overflow: TextOverflow.ellipsis,
                      style: AmiTypography.labelMono
                          .copyWith(color: AmiColors.hexAmber)),
              ],
              items: [
                for (final z in options) DropdownMenuItem(value: z, child: Text(z)),
              ],
              onChanged: (v) {
                if (v != null) onChanged(v);
              },
            ),
          ),
        ),
      ],
    );
  }
}
