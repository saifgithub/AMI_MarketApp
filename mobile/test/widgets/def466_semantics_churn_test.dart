/// DEF466 — on a real iPhone the accessibility tree "goes dark" (Appium/WDA
/// page source collapses to the Application skeleton, element lookups 404
/// while the UI keeps painting), first on Journal, then Portfolio Health and
/// the Settings risk-limits accordion, and it stays dark across tabs.
///
/// What those screens share is not a widget but the chrome under every one of
/// them: `HomeShell` mounts the scrolling [TickerTape] below the bottom nav on
/// every tab. The tape moves a row of tappable, labelled items with a
/// `Transform.translate` driven by a repeating controller. Each frame that
/// moves a semantics node's transform dirties the semantics tree, so the
/// engine ships a semantics update to the platform EVERY frame, forever, on
/// every screen (measured: 60 updates in 60 frames) — and nodes scroll in and
/// out of the clip so ids and rects keep changing. iOS's accessibility bridge
/// rebuilds its UIAccessibility elements on each update; a WDA snapshot taken
/// against a tree that is replaced 60 times a second comes back empty or
/// stale (the 404). Android's bridge tolerates it, which is why only iPhone
/// saw it.
///
/// The guard asserts the property directly: with semantics on, an idle screen
/// with the tape mounted produces no semantics updates. The tape is a moving
/// marquee, not content; it is excluded from semantics (it was never in the
/// tree on the Simulator runs that predate the tape, nor in the QA harness's
/// locators, which address the YOU/Journal/Settings panes by identifier).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/screens/you/insights_data.dart';
import 'package:ami_trade/screens/you/insights_providers.dart';
import 'package:ami_trade/screens/you/you_providers.dart';
import 'package:ami_trade/screens/you/you_screen.dart';
import 'package:ami_trade/services/yahoo_finance_service.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/ticker_tape_provider.dart';
import 'package:ami_trade/widgets/ticker_tape.dart';
import 'package:ami_trade/models/portfolio_health.dart';
import 'package:ami_trade/services/billing/purchase_models.dart';
import 'package:ami_trade/services/billing/purchase_service.dart';
import 'package:ami_trade/state/portfolio_health_providers.dart';
import 'package:ami_trade/state/purchase_providers.dart';
import 'package:ami_trade/widgets/portfolio_health/health_card.dart';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/portfolio_health_fixtures.dart';

class _FixedTapeNotifier extends TickerTapeNotifier {
  @override
  Future<TickerTapeData> build() async => TickerTapeData(
        quotes: List.generate(
          20,
          (i) => TickerQuote(
            symbol: 'SYM$i',
            price: 100.0 + i,
            changePercent: i.isEven ? 1.2 : -0.8,
            marketState: 'REGULAR',
          ),
        ),
      );
}

class _NoOfferingService implements PurchaseService {
  @override
  bool get isConfigured => false;
  @override
  Future<PaywallOffering?> fetchOffering() async => null;
  @override
  Future<PurchaseOutcome> purchase(PaywallPackage pkg) async =>
      PurchaseOutcome.notConfigured;
  @override
  Future<PurchaseOutcome> restore() async => PurchaseOutcome.notConfigured;
}

class _QuietMandateNotifier extends MandateNotifier {
  _QuietMandateNotifier(super.ref);
  @override
  Future<void> refresh() async {}
}

class _FixedMandateNotifier extends MandateNotifier {
  _FixedMandateNotifier(super.ref, MandateState fixed) {
    state = fixed;
  }
}

class _FixedJournalNotifier extends JournalNotifier {
  _FixedJournalNotifier(super.ref, JournalState fixed) {
    state = fixed;
  }
}

UserMandate _mandate() => const UserMandate(
      userId: 'u1',
      version: 7,
      displayName: 'Trader',
      locale: 'en',
      timezone: 'UTC',
      primaryGoal: 'long_term_wealth',
      horizon: 'long',
      path: 'long_horizon',
      riskScore: 3,
      riskComponents: RiskComponents(
        drawdownResponse: 3,
        regretAsymmetry: 0,
        concentrationTolerance: 3,
      ),
      maxDrawdownPct: 30,
      learningStyle: 'quick',
      compliance: ComplianceFlags(),
      plan: 'trial_trader',
      creditBalance: 75,
    );

List<JournalEntry> _entries() => [
      for (var i = 0; i < 12; i++)
        JournalEntry(
          id: 'e$i',
          userId: 'u1',
          entryType: JournalEntryType.roomRun,
          title: 'Room on MSFT $i',
          summary: 'The Room passed - no position.',
          ticker: 'MSFT',
          createdAt: DateTime.utc(2026, 11, 19),
          agentsInvolved: const [],
          tags: const [],
        ),
    ];

/// YOU with the real shell chrome under it: the tape in the bottom bar, as in
/// `HomeShell`.
Future<ProviderContainer> _pumpYouWithTape(WidgetTester t) async {
  t.view.physicalSize = const Size(390, 1400);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);

  final container = ProviderContainer(overrides: [
    mandateNotifierProvider.overrideWith(
        (ref) => _FixedMandateNotifier(ref, MandateState(mandate: _mandate()))),
    journalNotifierProvider.overrideWith((ref) =>
        _FixedJournalNotifier(ref, JournalState(entries: _entries()))),
    insightsProvider
        .overrideWith((ref) async => const InsightsData(entryCount: 0)),
    tickerTapeProvider.overrideWith(_FixedTapeNotifier.new),
  ]);
  addTearDown(container.dispose);

  await t.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: YouScreen(),
        bottomNavigationBar: TickerTape(),
      ),
    ),
  ));
  await t.pump();
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
  return container;
}

/// Semantics updates the engine would ship over [frames] idle frames.
Future<int> _updatesOverIdleFrames(WidgetTester t, {int frames = 60}) async {
  // ignore: deprecated_member_use
  final owner = t.binding.pipelineOwner.semanticsOwner!;
  var updates = 0;
  void onUpdate() => updates++;
  owner.addListener(onUpdate);
  for (var i = 0; i < frames; i++) {
    await t.pump(const Duration(milliseconds: 16));
  }
  owner.removeListener(onUpdate);
  return updates;
}

/// Every node in the tree, with its rect expressed in screen coordinates.
List<({SemanticsNode node, Rect rect})> _allNodes(WidgetTester t) {
  final out = <({SemanticsNode node, Rect rect})>[];
  void walk(SemanticsNode n, Matrix4 parent) {
    final m = parent.clone();
    if (n.transform != null) m.multiply(n.transform!);
    out.add((node: n, rect: MatrixUtils.transformRect(m, n.rect)));
    n.visitChildren((c) {
      walk(c, m);
      return true;
    });
  }

  // ignore: deprecated_member_use
  walk(t.binding.pipelineOwner.semanticsOwner!.rootSemanticsNode!, Matrix4.identity());
  return out;
}

void _expectFiniteTree(WidgetTester t) {
  final nodes = _allNodes(t);
  expect(nodes.length, greaterThan(3));
  for (final n in nodes) {
    final r = n.rect;
    expect(r.left.isFinite && r.top.isFinite && r.right.isFinite && r.bottom.isFinite,
        isTrue,
        reason: 'non-finite semantics rect on ${n.node.id} (${n.node.label}): $r');
    expect(r.width.abs() < 1e5 && r.height.abs() < 1e5, isTrue,
        reason: 'implausibly huge semantics rect on ${n.node.id}: $r');
  }
}

void main() {
  testWidgets(
      'DEF466 — the ticker tape never makes an idle screen emit semantics '
      'updates (a per-frame update storm is what blanks the iOS tree)',
      (t) async {
    final h = t.ensureSemantics();
    await _pumpYouWithTape(t);

    expect(find.text('SYM0'), findsWidgets,
        reason: 'the tape must still be painted for sighted users');
    final updates = await _updatesOverIdleFrames(t);
    expect(updates, 0,
        reason: 'DEF466: $updates semantics updates in 60 idle frames. The '
            'tape is a moving marquee; its items must not live in the '
            'semantics tree or every screen churns it at frame rate.');
    h.dispose();
  });

  testWidgets(
      'DEF466 — Journal with entries stays a readable, finite tree while it '
      'sits open, and after moving on to Settings and back', (t) async {
    final h = t.ensureSemantics();
    final container = await _pumpYouWithTape(t);

    container.read(youSegmentProvider.notifier).state = YouSegment.journal;
    await t.pump();
    await t.pump(const Duration(milliseconds: 300));

    expect(find.bySemanticsIdentifier(ScreenIds.journalScreen), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp('Room on MSFT 0')), findsWidgets);
    _expectFiniteTree(t);

    // "~5-8 s after opening, no interaction": sit on it for 12 s of frames.
    for (var s = 0; s < 12; s++) {
      await t.pump(const Duration(seconds: 1));
    }
    expect(find.bySemanticsIdentifier(ScreenIds.journalScreen), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp('Room on MSFT 0')), findsWidgets);
    _expectFiniteTree(t);
    expect(await _updatesOverIdleFrames(t), 0);

    // "stayed dark on other tabs": the next segment must be as readable.
    container.read(youSegmentProvider.notifier).state = YouSegment.settings;
    await t.pump();
    await t.pump(const Duration(milliseconds: 300));
    expect(find.bySemanticsIdentifier(ScreenIds.settingsScreen), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp('Room on MSFT 0')), findsNothing,
        reason: 'the hidden Journal pane must not leak into the tree');
    _expectFiniteTree(t);
    expect(await _updatesOverIdleFrames(t), 0);

    container.read(youSegmentProvider.notifier).state = YouSegment.journal;
    await t.pump();
    await t.pump(const Duration(milliseconds: 300));
    expect(find.bySemanticsLabel(RegExp('Room on MSFT 0')), findsWidgets);
    h.dispose();
  });

  testWidgets(
      'DEF466 — Settings risk-limits accordion rows are exposed once open, '
      'and the tree stays quiet', (t) async {
    final h = t.ensureSemantics();
    await _pumpYouWithTape(t);

    final l = AppLocalizations.of(t.element(find.byType(YouScreen)));
    await t.tap(find.text(l.settingsRiskLimitsExpand));
    await t.pump();
    await t.pump(const Duration(milliseconds: 300));

    expect(find.bySemanticsLabel(RegExp(l.settingsRiskLimitsSectorCapLabel)),
        findsWidgets,
        reason: 'accordion rows must be in the semantics tree');
    expect(find.bySemanticsLabel(RegExp(l.settingsRiskLimitsCooldownLabel)),
        findsWidgets);
    _expectFiniteTree(t);
    expect(await _updatesOverIdleFrames(t), 0);
    h.dispose();
  });

  for (final loading in [true, false]) {
    testWidgets(
        'DEF466 — Portfolio Health card (${loading ? 'loading' : 'loaded'}) '
        'is a finite, quiet semantics tree on its own', (t) async {
      t.view.physicalSize = const Size(390, 844);
      t.view.devicePixelRatio = 1.0;
      addTearDown(t.view.reset);
      final h = t.ensureSemantics();
      await t.pumpWidget(ProviderScope(
        overrides: [
          purchaseServiceProvider.overrideWithValue(_NoOfferingService()),
          mandateNotifierProvider.overrideWith(_QuietMandateNotifier.new),
          portfolioHealthProvider.overrideWith((ref) => loading
              ? Completer<PortfolioHealth>().future
              : healthFixture()),
        ],
        child: const MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Scaffold(
            body: SingleChildScrollView(child: PortfolioHealthCard()),
          ),
        ),
      ));
      await t.pump();
      await t.pump(const Duration(seconds: 1));

      _expectFiniteTree(t);
      expect(await _updatesOverIdleFrames(t), 0,
          reason: 'the Health card must not churn semantics while it sits open');
      h.dispose();
    });
  }
}
