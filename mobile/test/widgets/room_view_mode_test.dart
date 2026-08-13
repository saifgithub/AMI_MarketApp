/// CR106 acceptance #9 and #15 — when `ami_room_view_mode` may be written.
///
/// Two rules, and both are about the *absence* of a write:
///
///  - **#9** A fresh install lands on BOARD and **nothing is persisted** until
///    the user picks. Eagerly writing the default the first time the screen
///    renders would freeze today's choice into every existing install, and a
///    later change of default would silently never reach any of them. Copied
///    from `theme_provider.dart`, which gets this right and is the reason to
///    copy it rather than invent.
///  - **#15** `READ THE FULL DEBATE` in the peek sheet switches the mode **for
///    that screen only**. One curious tap on a 26pt mark must not rewrite what
///    every future Room opens as (T-MODESIDE).
library;

import 'package:ami_trade/state/room_view_mode_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

Future<String?> _stored() async =>
    (await SharedPreferences.getInstance()).getString(roomViewModePrefsKey);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('acceptance #9 — a fresh install lands on BOARD', () async {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer();
    addTearDown(container.dispose);
    expect(container.read(roomViewModeProvider), RoomViewMode.board,
        reason: 'the complaint is "too much to read"; the default has to be '
            'the thing that answers it');
  });

  test('acceptance #9 — reading the default persists nothing', () async {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer();
    addTearDown(container.dispose);
    container.read(roomViewModeProvider);
    await Future<void>.delayed(Duration.zero); // let _hydrate run
    expect(await _stored(), isNull,
        reason: 'a persisted default freezes it for every existing install');
  });

  test('a stored preference wins over the default', () async {
    SharedPreferences.setMockInitialValues(
        {roomViewModePrefsKey: 'transcript'});
    final container = ProviderContainer();
    addTearDown(container.dispose);
    // Hydration is async — the notifier starts on the default and settles.
    expect(container.read(roomViewModeProvider), RoomViewMode.board);
    await Future<void>.delayed(Duration.zero);
    expect(container.read(roomViewModeProvider), RoomViewMode.transcript);
  });

  test('an unrecognised stored value falls back rather than throwing',
      () async {
    SharedPreferences.setMockInitialValues({roomViewModePrefsKey: 'comb'});
    final container = ProviderContainer();
    addTearDown(container.dispose);
    await Future<void>.delayed(Duration.zero);
    expect(container.read(roomViewModeProvider), RoomViewMode.board);
  });

  test('setMode is the only thing that writes', () async {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final notifier = container.read(roomViewModeProvider.notifier);
    await Future<void>.delayed(Duration.zero);
    expect(await _stored(), isNull);

    await notifier.setMode(RoomViewMode.transcript);
    expect(await _stored(), 'transcript');
    expect(container.read(roomViewModeProvider), RoomViewMode.transcript);

    await notifier.setMode(RoomViewMode.board);
    expect(await _stored(), 'board');
  });

  testWidgets(
      'acceptance #15 — a per-screen mode switch leaves the stored value alone',
      (t) async {
    // The peek sheet's `READ THE FULL DEBATE` is modelled as local widget
    // state, deliberately not as a provider write. This asserts the shape that
    // makes that true: a widget can flip what it renders without the notifier
    // ever being asked to change.
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer();
    addTearDown(container.dispose);

    RoomViewMode? sessionMode;
    late StateSetter setLocal;

    await t.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: StatefulBuilder(builder: (context, setState) {
            setLocal = setState;
            return Consumer(builder: (context, ref, _) {
              final stored = ref.watch(roomViewModeProvider);
              final effective = sessionMode ?? stored;
              return Text(
                effective == RoomViewMode.board ? 'BOARD' : 'TRANSCRIPT',
                textDirection: TextDirection.ltr,
              );
            });
          }),
        ),
      ),
    );
    await t.pump();
    expect(find.text('BOARD'), findsOneWidget);

    // The jump: what the sheet's action does.
    setLocal(() => sessionMode = RoomViewMode.transcript);
    await t.pump();
    expect(find.text('TRANSCRIPT'), findsOneWidget);

    // And the stored preference is untouched — the next Room still opens on
    // the board.
    expect(await _stored(), isNull);
    expect(container.read(roomViewModeProvider), RoomViewMode.board);
  });

  group('CR173 — the third value', () {
    test('floor round-trips through the stored string', () async {
      SharedPreferences.setMockInitialValues({});
      final container = ProviderContainer();
      addTearDown(container.dispose);
      await container
          .read(roomViewModeProvider.notifier)
          .setMode(RoomViewMode.floor);
      expect(await _stored(), 'floor');

      // A fresh container reads it back — the persistence §5.7 calls
      // load-bearing is a round trip, not a write.
      final reopened = ProviderContainer();
      addTearDown(reopened.dispose);
      reopened.read(roomViewModeProvider);
      await Future<void>.delayed(Duration.zero);
      expect(reopened.read(roomViewModeProvider), RoomViewMode.floor);
    });

    test('each surface reads the one dial its own way', () {
      // Amendment B. The two readings live on the enum so a caller cannot
      // invent a third interpretation — `mode == RoomViewMode.board` was a
      // correct settled test while there were two values and silently became
      // a wrong one when there were three.
      expect(RoomViewMode.board.showsLiveFloor, isFalse);
      expect(RoomViewMode.transcript.showsLiveFloor, isFalse);
      expect(RoomViewMode.floor.showsLiveFloor, isTrue);

      expect(RoomViewMode.board.showsTranscript, isFalse);
      expect(RoomViewMode.transcript.showsTranscript, isTrue);
      expect(RoomViewMode.floor.showsTranscript, isFalse,
          reason: 'a floor user settles to the Board — one tap on WATCH THE '
              'FLOOR must not replace the settled screen they have always seen');
    });

    test('a value written by a newer build does not become transcript',
        () async {
      // DEF210 — the stored string outlives the build that wrote it. An
      // unrecognised value must land on the shipped default, visibly, rather
      // than in whichever bucket the comparison happens to fall through to.
      SharedPreferences.setMockInitialValues({roomViewModePrefsKey: 'comb'});
      final container = ProviderContainer();
      addTearDown(container.dispose);
      await Future<void>.delayed(Duration.zero);
      expect(container.read(roomViewModeProvider), RoomViewMode.board);
    });
  });
}
