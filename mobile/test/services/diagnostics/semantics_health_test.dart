/// DEF466 round 2 — SemanticsHealth records what the semantics tree is doing
/// so a bug report filed while the iPhone tree is dark can say whether Flutter
/// stopped producing semantics or the iOS bridge stopped exposing them.
library;

import 'dart:ui' as ui;

import 'package:ami_trade/services/diagnostics/semantics_health.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late FlutterExceptionHandler? savedOnError;
  late VoidCallback? savedFeatures;

  setUp(() {
    savedOnError = FlutterError.onError;
    savedFeatures = ui.PlatformDispatcher.instance.onAccessibilityFeaturesChanged;
  });
  tearDown(() {
    FlutterError.onError = savedOnError;
    ui.PlatformDispatcher.instance.onAccessibilityFeaturesChanged = savedFeatures;
  });

  test('not installed: adds nothing to a report', () {
    final h = SemanticsHealth.forTest();
    expect(h.summary(), isNull);
    expect(h.appendTo('my steps'), 'my steps');
    expect(h.appendTo(null), isNull);
  });

  testWidgets('reports enabled state, update flow and node count',
      (t) async {
    final h = SemanticsHealth.forTest()..install();
    final handle = t.ensureSemantics();
    await t.pumpWidget(const MaterialApp(home: Scaffold(body: Text('hello'))));
    await t.pump();

    final s = h.summary()!;
    expect(s, contains('on=1'));
    expect(s, matches(RegExp(r'updates=[1-9]')));
    expect(s, matches(RegExp(r'nodes=[1-9]')));
    expect(s, contains('semErrors=0'));

    handle.dispose();
  });

  testWidgets('counts an error raised while building semantics, keeps no '
      'message text', (t) async {
    final h = SemanticsHealth.forTest()..install();
    final handle = t.ensureSemantics();
    await t.pumpWidget(const MaterialApp(home: Scaffold(body: Text('x'))));

    FlutterError.reportError(FlutterErrorDetails(
      exception: StateError('secret user@example.com'),
      library: 'semantics library',
      stack: StackTrace.fromString(
          '#0 PipelineOwner.flushSemantics (package:flutter/src/rendering/object.dart:1)'),
    ));
    expect(t.takeException(), isA<StateError>());

    final s = h.summary()!;
    expect(s, contains('semErrors=1'));
    expect(s, contains('first=StateError@semantics library'));
    expect(s, isNot(contains('secret')));
    expect(s, isNot(contains('example.com')));

    FlutterError.reportError(FlutterErrorDetails(
      exception: ArgumentError('unrelated'),
      library: 'widgets library',
      stack: StackTrace.fromString('#0 SomeWidget.build (x.dart:1)'),
    ));
    t.takeException();
    expect(h.summary(), allOf(contains('errors=2'), contains('semErrors=1')));
    handle.dispose();
  });

  testWidgets('appendTo puts the record on a trailing line of the user steps',
      (t) async {
    final h = SemanticsHealth.forTest()..install();
    expect(h.appendTo('open Journal'), startsWith('open Journal\n\n[diag] sem['));
    expect(h.appendTo(null), startsWith('[diag] sem['));
  });
}
