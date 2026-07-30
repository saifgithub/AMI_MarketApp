/// DEF189 — the PM's transcript row always read `NO RESPONSE` (a copy-paste
/// ternary with two identical branches at `room_transcript_rows.dart:253-257`
/// before this fix), and its expanded content rendered as unframed floating
/// text with no card and no attribution. Saiful ruled: keep the PM row in
/// `RoomTranscriptRows`, fix both bugs rather than excluding
/// `portfolio_manager` the way the 11-hex comb does.
///
/// Pinned here:
///   1. a PM voice with non-empty, non-quotable content (no headline, no
///      `**bold**` span, no entry/stop/target triple) must NOT collapse to
///      `NO RESPONSE` — this is the bug the tester actually saw;
///   2. `NO RESPONSE` must stay reachable and correct for a genuinely empty
///      voice — the other direction, so the fix isn't just a new false
///      positive;
///   3. the expanded PM content is carded and attributed, matching
///      `_ReasonBlock`'s treatment (`room_board.dart`), not floating text.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/room/room_transcript_rows.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

RoomVoice _pmVoice({
  String content =
      'The mandate clears at this size and the risk is acceptable given '
      'current sector volatility, so the position stands as proposed',
  bool withheld = false,
  String? headline,
}) =>
    RoomVoice(
      agentId: 'portfolio_manager',
      content: content,
      headline: headline,
      withheld: withheld,
    );

Future<void> _pump(WidgetTester t, RoomVoice voice,
    {bool expanded = false}) async {
  await t.pumpWidget(
    MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: TranscriptRow(
          voice: voice,
          expanded: expanded,
          onToggle: () {},
        ),
      ),
    ),
  );
  await t.pumpAndSettle();
}

void main() {
  late AppLocalizations l;
  setUpAll(() async {
    l = await AppLocalizations.delegate.load(const Locale('en'));
  });

  group('DEF189 — collapsed label', () {
    testWidgets(
        'a PM voice with prose content (no headline/bold/triple) does not '
        'render NO RESPONSE', (t) async {
      final voice = _pmVoice();
      await t.pumpWidget(
        MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Builder(builder: (context) {
            final l = AppLocalizations.of(context);
            return Scaffold(
              body: Column(children: [
                TranscriptRow(voice: voice, expanded: false, onToggle: () {}),
                Text('sentinel:${l.roomRowNoResponse}'),
              ]),
            );
          }),
        ),
      );
      await t.pumpAndSettle();
      final l = AppLocalizations.of(t.element(find.byType(TranscriptRow)));
      expect(find.text(l.roomRowNoResponse), findsNothing,
          reason: 'DEF189 — the PM said something; the row must say so');
    });

    testWidgets('gistFor still returns null for plain verdict prose',
        (t) async {
      // Documents bug (2) from the row file: none of the three analyst-style
      // extraction patterns match verdict prose. The fallback lives at the
      // call site (collapsedLabel), not inside gistFor — see its doc-comment.
      final voice = _pmVoice();
      expect(gistFor(voice), isNull);
    });

    testWidgets('collapsedLabel derives from content when gistFor is null',
        (t) async {
      final voice = _pmVoice();
      final label = collapsedLabel(l, voice);
      expect(label, isNot(l.roomRowNoResponse));
      expect(label, startsWith('The mandate clears at this size'));
    });

    testWidgets('a genuinely empty PM voice still reads NO RESPONSE',
        (t) async {
      final voice = _pmVoice(content: '');
      final label = collapsedLabel(l, voice);
      expect(label, l.roomRowNoResponse,
          reason: 'must not swap the false negative for a false positive');
      await _pump(t, voice);
      expect(find.text(l.roomRowNoResponse), findsOneWidget);
    });

    testWidgets('a withheld voice reads NOT HEARD, never NO RESPONSE',
        (t) async {
      final voice = _pmVoice(withheld: true, content: '');
      final label = collapsedLabel(l, voice);
      expect(label, l.roomRowNotHeard);
    });

    testWidgets('a headline still wins over the first-sentence fallback',
        (t) async {
      final voice = _pmVoice(headline: 'APPROVE at 3.0%');
      final label = collapsedLabel(l, voice);
      expect(label, 'APPROVE at 3.0%');
    });
  });

  group('DEF189 — expanded content is carded and attributed', () {
    testWidgets('the expanded PM row wraps content in a Container and names '
        'the Portfolio Manager', (t) async {
      final voice = _pmVoice();
      await _pump(t, voice, expanded: true);

      expect(find.byKey(const Key('pmVerdictCard')), findsOneWidget,
          reason: 'DEF189 — the PM narrative must render inside a card, not '
              'as floating text');
      final card = t.widget<Container>(find.byKey(const Key('pmVerdictCard')));
      expect((card.decoration as BoxDecoration).color, AmiColors.slate900);

      expect(find.textContaining('PORTFOLIO MANAGER'), findsOneWidget,
          reason: 'the card must clearly say this came from the PM agent');
    });

    testWidgets('a non-PM row is left unstyled (fence: do not restyle the '
        'rest of the transcript)', (t) async {
      final voice = RoomVoice(agentId: 'trader', content: 'Entry 150.');
      await _pump(t, voice, expanded: true);
      expect(find.byKey(const Key('pmVerdictCard')), findsNothing,
          reason: 'only the PM row gets the _ReasonBlock card treatment');
      expect(find.textContaining('TRADER'), findsNothing);
    });
  });
}

