/// DEF466 round 2 — a release-safe record of what the Flutter semantics tree
/// is doing, so a bug report filed while the iPhone accessibility tree is
/// "dark" says WHY.
///
/// Two very different failures look identical from WDA (the page source is the
/// bare Application skeleton while the screen paints normally):
///
///  1. Flutter stopped producing semantics: an exception inside the semantics
///     flush, or the platform switched semantics off (`semanticsEnabled`
///     false). Release builds swallow both without a trace, and the store
///     build has no error sink (`qa/error_sink.dart` is QA-only).
///  2. Flutter is still producing semantics (updates keep flowing, nodes are
///     present) and the iOS accessibility bridge is not exposing them. That is
///     an engine/OS problem and no widget change will fix it.
///
/// This class keeps just enough to tell them apart: enable/disable flips,
/// whether updates are still flowing and how many nodes the tree holds now,
/// and the TYPE and library (never the message, which can carry user data) of
/// any framework error raised while building semantics.
///
/// It is read by the in-app bug report, which appends [summary] to the steps
/// the user submits — the same user-initiated, no-PII channel that already
/// carries the app version, platform and request trace ids. Nothing is sent on
/// its own, and there is no new endpoint.
library;

import 'dart:ui' as ui;

import 'package:flutter/foundation.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/scheduler.dart';

class SemanticsHealth {
  SemanticsHealth._();

  static final SemanticsHealth instance = SemanticsHealth._();

  /// A fresh, uninstalled instance for tests.
  @visibleForTesting
  SemanticsHealth.forTest();

  static const _maxEvents = 8;

  final Stopwatch _clock = Stopwatch();
  bool _installed = false;
  bool _enabled = false;
  bool _accessibleNavigation = false;
  int _flips = 0;
  int _updates = 0;
  int _errors = 0;
  int _semanticsErrors = 0;
  String? _firstSemanticsError;
  Duration? _lastUpdateAt;
  SemanticsOwner? _owner;
  final List<String> _events = <String>[];

  bool get installed => _installed;

  /// Hook the semantics-enabled flag, the semantics owner and
  /// [FlutterError.onError] (chained, never replaced). Idempotent. Call after
  /// `WidgetsFlutterBinding.ensureInitialized()` and before anything that
  /// installs its own handler, so theirs chains to this one.
  void install() {
    if (_installed) return;
    _installed = true;
    _clock.start();

    final binding = SemanticsBinding.instance;
    _enabled = binding.semanticsEnabled;
    _accessibleNavigation = _readAccessibleNavigation();
    _event('start on=$_enabled nav=$_accessibleNavigation');
    binding.addSemanticsEnabledListener(_onEnabledChanged);
    _attachOwner();
    // The owner is created and torn down by the renderer when semantics is
    // switched on/off; a per-frame identity check keeps the listener on the
    // live one whatever the order those callbacks ran in.
    SchedulerBinding.instance.addPersistentFrameCallback((_) => _attachOwner());

    final previous = FlutterError.onError;
    FlutterError.onError = (FlutterErrorDetails details) {
      try {
        _onFlutterError(details);
      } catch (_) {
        // Recording must never throw a second error.
      }
      previous?.call(details);
    };

    final previousFeatures = ui.PlatformDispatcher.instance.onAccessibilityFeaturesChanged;
    ui.PlatformDispatcher.instance.onAccessibilityFeaturesChanged = () {
      try {
        final now = _readAccessibleNavigation();
        if (now != _accessibleNavigation) {
          _accessibleNavigation = now;
          _event('nav=$now');
        }
      } catch (_) {}
      previousFeatures?.call();
    };
  }

  bool _readAccessibleNavigation() =>
      ui.PlatformDispatcher.instance.accessibilityFeatures.accessibleNavigation;

  void _onEnabledChanged() {
    final now = SemanticsBinding.instance.semanticsEnabled;
    if (now != _enabled) {
      _enabled = now;
      _flips++;
      _event('on=$now');
    }
    _attachOwner();
  }

  void _attachOwner() {
    SemanticsOwner? next;
    for (final view in RendererBinding.instance.renderViews) {
      next = view.owner?.semanticsOwner;
      if (next != null) break;
    }
    if (identical(next, _owner)) return;
    _owner?.removeListener(_onUpdate);
    _owner = next;
    next?.addListener(_onUpdate);
  }

  void _onUpdate() {
    _updates++;
    _lastUpdateAt = _clock.elapsed;
  }

  void _onFlutterError(FlutterErrorDetails details) {
    _errors++;
    final stack = details.stack?.toString() ?? '';
    final inSemantics = stack.contains('flushSemantics') ||
        stack.contains('SemanticsOwner') ||
        stack.contains('SemanticsNode') ||
        stack.contains('_getSemanticsForParent') ||
        stack.contains('describeSemanticsConfiguration') ||
        (details.library ?? '').contains('semantics');
    if (!inSemantics) return;
    _semanticsErrors++;
    _firstSemanticsError ??=
        '${details.exception.runtimeType}@${details.library ?? '?'}';
    _event('semErr ${details.exception.runtimeType}');
  }

  void _event(String what) {
    if (_events.length >= _maxEvents) _events.removeAt(0);
    _events.add('+${_clock.elapsed.inSeconds}s $what');
  }

  int _nodeCount() {
    final root = _owner?.rootSemanticsNode;
    if (root == null) return -1;
    var n = 0;
    void walk(SemanticsNode node) {
      n++;
      node.visitChildren((c) {
        walk(c);
        return true;
      });
    }

    walk(root);
    return n;
  }

  /// One line, no user data. `null` when [install] was never called (tests,
  /// and any build that did not opt in), so callers add nothing.
  String? summary() {
    if (!_installed) return null;
    final sinceUpdate = _lastUpdateAt == null
        ? 'never'
        : '${(_clock.elapsed - _lastUpdateAt!).inSeconds}s';
    final first = _firstSemanticsError;
    return 'sem[on=${SemanticsBinding.instance.semanticsEnabled ? 1 : 0}'
        ' flips=$_flips nav=${_accessibleNavigation ? 1 : 0}'
        ' updates=$_updates lastUpdateAgo=$sinceUpdate nodes=${_nodeCount()}'
        ' errors=$_errors semErrors=$_semanticsErrors'
        '${first == null ? '' : ' first=$first'}'
        ' up=${_clock.elapsed.inSeconds}s'
        ' events=${_events.join(';')}]';
  }

  /// [steps] with this build's [summary] on a trailing line, or [steps]
  /// unchanged when nothing is recorded.
  String? appendTo(String? steps) {
    final s = summary();
    if (s == null) return steps;
    final base = steps?.trim() ?? '';
    return base.isEmpty ? '[diag] $s' : '$base\n\n[diag] $s';
  }
}
