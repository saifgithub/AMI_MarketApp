/// DEF466 round 3 - is the Settings semantics tree too deep or too big for
/// the iOS automation layer once PROFILE scrolls into view?
///
/// The device runs (AMI-DL-2, AMI-DL-8) showed the iOS accessibility tree going
/// dark when Settings > PROFILE enters the viewport while Flutter itself kept
/// the tree healthy (`nodes=33`, `updates` rising, `semErrors=0`). The one
/// app-side mechanism that could do that is size: WebDriverAgent snapshots the
/// element tree with `snapshotMaxDepth` (default 50) and returns a skeleton
/// when a snapshot cannot be completed.
///
/// This test walks the real Settings screen top to bottom with semantics on,
/// in 400 px steps, and records the semantics tree depth and node count at
/// every step, split into "PROFILE not yet in the tree" (above) and "PROFILE in
/// the tree" (at and below). Measured on the build this test was written
/// against: depth 9 above and below, nodes 25 to 38 everywhere. iOS adds a
/// handful of UIKit wrapper levels (Application, Window, FlutterView, scroll
/// view, containers; budgeted here as 15), so the budget below keeps
/// flutter depth + 15 under 50 with room to spare. A change that nests Settings
/// semantics deeper or balloons the node count fails here instead of on a
/// device run.
///
/// It does NOT prove the dark-tree cause: depth and size are ruled out, which
/// is the finding. See DEF466 in the defect register for the open lead.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/auth.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/me_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// WebDriverAgent's default `snapshotMaxDepth`.
const int _wdaSnapshotMaxDepth = 50;

/// UIKit levels iOS stacks above the Flutter semantics root (Application,
/// Window, root view controller views, FlutterView, semantics scroll view and
/// containers), rounded up.
const int _iosWrapperLevels = 15;

/// Largest Flutter semantics depth allowed: 20 + [_iosWrapperLevels] = 35,
/// 15 levels short of [_wdaSnapshotMaxDepth]. Measured depth is 9.
const int _maxDepth = 20;

/// Measured 25 to 38 on the real screen; roughly 3x headroom.
const int _maxNodes = 120;

class _Api extends ApiClient {
  _Api() : super(baseUrl: 'test://localhost');

  @override
  Future<void> alpacaReportLinkState(bool linked) async {}
}

class _Auth extends AuthNotifier {
  _Auth(super.ref) {
    state = AuthState(
      user: AuthUser(
        id: 'u1',
        email: 'trader@example.com',
        isAnonymous: false,
        createdAt: DateTime.utc(2026, 1, 1),
      ),
      token: 'tok',
    );
  }

  @override
  Future<void> bootstrap() async {}
}

class _NoopSim extends SimNotifier {
  _NoopSim(super.ref);
  @override
  Future<void> refresh() async {}
}

class _Mandate extends MandateNotifier {
  _Mandate(super.ref) {
    state = MandateState(
      mandate: UserMandate.fromJson({
        'user_id': 'u1',
        'plan': 'trial_trader',
        'display_name': 'Trader',
      }),
    );
  }

  @override
  Future<void> refresh() async {}
}

({int depth, int nodes, int textFields}) _measure(SemanticsNode root) {
  var maxDepth = 0;
  var nodes = 0;
  var textFields = 0;
  void walk(SemanticsNode n, int depth) {
    nodes++;
    if (depth > maxDepth) maxDepth = depth;
    if (n.getSemanticsData().flagsCollection.isTextField) textFields++;
    n.visitChildren((c) {
      walk(c, depth + 1);
      return true;
    });
  }

  walk(root, 1);
  return (depth: maxDepth, nodes: nodes, textFields: textFields);
}

void main() {
  testWidgets(
      'DEF466 - Settings semantics tree stays shallow and small above AND '
      'below PROFILE (iOS WDA snapshotMaxDepth is 50)', (t) async {
    final handle = t.ensureSemantics();
    t.view.physicalSize = const Size(390 * 3, 844 * 3);
    t.view.devicePixelRatio = 3.0;
    addTearDown(t.view.reset);

    await t.pumpWidget(ProviderScope(
      overrides: [
        mandateNotifierProvider.overrideWith((ref) => _Mandate(ref)),
        simNotifierProvider.overrideWith((ref) => _NoopSim(ref)),
        authNotifierProvider.overrideWith((ref) => _Auth(ref)),
        myHandleProvider.overrideWith((ref) async => 'HANDLE'),
        apiClientProvider.overrideWithValue(_Api()),
      ],
      child: const MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: SettingsScreen(),
      ),
    ));
    await t.pump();
    await t.pump();

    final l = AppLocalizations.of(t.element(find.byType(SettingsScreen)));
    // ignore: deprecated_member_use
    final owner = t.binding.pipelineOwner.semanticsOwner!;

    var aboveDepth = 0, aboveNodes = 0, belowDepth = 0, belowNodes = 0;
    var sawProfile = false;
    var steps = 0;
    var lastOffset = -1.0;
    final scrollable = find.byType(Scrollable).first;
    while (steps < 60) {
      final m = _measure(owner.rootSemanticsNode!);
      final profileInTree = find.text(l.settingsSectionProfile).evaluate().isNotEmpty;
      if (profileInTree) {
        sawProfile = true;
        if (m.depth > belowDepth) belowDepth = m.depth;
        if (m.nodes > belowNodes) belowNodes = m.nodes;
      } else if (!sawProfile) {
        if (m.depth > aboveDepth) aboveDepth = m.depth;
        if (m.nodes > aboveNodes) aboveNodes = m.nodes;
      }
      final offset = t.state<ScrollableState>(scrollable).position.pixels;
      if (offset == lastOffset) break;
      lastOffset = offset;
      await t.drag(scrollable, const Offset(0, -400));
      await t.pump();
      await t.pump(const Duration(milliseconds: 100));
      steps++;
    }

    expect(sawProfile, isTrue, reason: 'the walk never brought PROFILE into view');
    // ignore: avoid_print
    print('DEF466 settings semantics: above PROFILE depth=$aboveDepth '
        'nodes<=$aboveNodes; PROFILE and below depth=$belowDepth '
        'nodes<=$belowNodes (WDA snapshotMaxDepth $_wdaSnapshotMaxDepth, '
        'budget depth<=$_maxDepth nodes<=$_maxNodes)');
    expect(aboveDepth, lessThanOrEqualTo(_maxDepth));
    expect(belowDepth, lessThanOrEqualTo(_maxDepth),
        reason: 'DEF466: Settings semantics below PROFILE is $belowDepth '
            'deep; with ~$_iosWrapperLevels UIKit wrapper levels that '
            'approaches WDA snapshotMaxDepth $_wdaSnapshotMaxDepth. '
            'Flatten the nesting under PROFILE.');
    expect(aboveNodes, lessThanOrEqualTo(_maxNodes));
    expect(belowNodes, lessThanOrEqualTo(_maxNodes),
        reason: 'DEF466: $belowNodes semantics nodes in one frame below PROFILE.');
    handle.dispose();
  });
}
