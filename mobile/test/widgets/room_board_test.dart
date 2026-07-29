/// CR106 — what the Verdict Board must and must not draw.
///
/// The board makes every unsupported claim louder than prose does, so most of
/// what is pinned here is a **refusal**: no ribbon without provenance, no bands
/// without recorded stances, no glyph inside a NO_VERDICT hex, no trade ticket
/// on a record. A test suite that only checked the happy render would pass on a
/// board that confidently invents.
///
/// It also re-asserts CR098's `NO_VERDICT` invariants against the hero tile.
/// `room_no_verdict_test.dart` pins them on `_VerdictCard` (transcript mode);
/// they are pinned here on the board because the two surfaces diverging
/// silently is precisely what `DEF143` was.
library;

import 'dart:math' as math;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/room.dart' show LevelSource;
import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/room/room_board.dart';
import 'package:ami_trade/widgets/room/room_transcript_rows.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

RoomVoice _voice(
  String agentId, {
  String? stance = 'for',
  String? conviction = 'high',
  String? headline,
  String content = 'A thesis with a **6.2% FCF yield** behind it.',
  bool recorded = true,
  bool withheld = false,
}) =>
    RoomVoice(
      agentId: agentId,
      content: content,
      stance: stance,
      conviction: conviction,
      headline: headline,
      stanceRecorded: recorded,
      withheld: withheld,
    );

RoomBoardData _board({
  VerdictOutcome outcome = VerdictOutcome.approve,
  String actionToken = 'APPROVE',
  Map<String, LevelSource>? provenance = const {
    'entry': LevelSource.pm,
    'stop': LevelSource.amiDefault,
    'target': LevelSource.pm,
  },
  List<RoomVoice>? voices,
  List<String> violations = const [],
  bool overridden = false,
  List<String> withheld = const [],
  bool isRecord = false,
  bool recordedStances = true,
  double? sizePct = 3.0,
}) =>
    RoomBoardData(
      ticker: 'AAPL',
      outcome: outcome,
      actionToken: actionToken,
      reason: 'Synthesis defended; the mandate clears at this size.',
      sizePct: sizePct,
      entry: 150,
      stop: 141,
      target: 172,
      horizonDays: 42,
      violations: violations,
      overriddenFromLlm: overridden,
      opinionsNotIncluded: withheld,
      levelProvenance: provenance,
      isRecord: isRecord,
      recordedAt: isRecord ? DateTime.utc(2026, 6, 2) : null,
      voices: voices ??
          [
            for (final a in kCombVoices)
              _voice(a.id, recorded: recordedStances),
          ],
    );

Future<void> _pump(WidgetTester t, RoomBoardData data) async {
  await t.pumpWidget(
    MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: SingleChildScrollView(child: RoomBoard(data: data)),
      ),
    ),
  );
  await t.pumpAndSettle();
}

List<String> _texts(WidgetTester t) => t
    .widgetList<Text>(find.byType(Text))
    .map((w) => w.data ?? '')
    .where((s) => s.isNotEmpty)
    .toList();

void main() {
  group('acceptance #2 — five hero states, none reading as a rejection', () {
    testWidgets('each state has its own heading and accent', (t) async {
      final seenHeadings = <String>{};
      final expected = {
        VerdictOutcome.approve: AmiColors.hexGreen,
        VerdictOutcome.pass: AmiColors.slate500,
        VerdictOutcome.reject: AmiColors.hexRed,
        VerdictOutcome.noVerdict: AmiColors.slate500,
        VerdictOutcome.noResult: AmiColors.hexRed,
      };
      for (final entry in expected.entries) {
        final data = _board(outcome: entry.key, violations: const ['x']);
        await _pump(t, data);
        expect(t.takeException(), isNull, reason: '${entry.key}');
        expect(accentForOutcome(entry.key), entry.value);
        final heading = headingForOutcome(
          AppLocalizations.of(t.element(find.byType(RoomBoard))),
          data,
        );
        expect(find.text(heading), findsOneWidget, reason: '${entry.key}');
        seenHeadings.add(heading);
      }
      // Five states, five distinct headings — not one heading reused.
      expect(seenHeadings.length, 5);
    });

    testWidgets('NO_VERDICT and NO RESULT carry no reject accent', (t) async {
      for (final o in [VerdictOutcome.noVerdict, VerdictOutcome.pass]) {
        expect(accentForOutcome(o), isNot(AmiColors.hexAmber),
            reason: 'amber tells the user their thesis was turned down');
        expect(accentForOutcome(o), AmiColors.slate500);
      }
    });

    testWidgets('the NO_VERDICT hex carries no glyph at all', (t) async {
      // An empty outline hex IS the statement; any mark inside it reads as a
      // decision.
      await _pump(t, _board(outcome: VerdictOutcome.noVerdict));
      final texts = _texts(t);
      for (final glyph in const ['✓', '✗', '—']) {
        expect(texts.contains(glyph), isFalse, reason: 'glyph $glyph leaked');
      }
    });

    testWidgets('the raw wire enum never reaches the user for a known action',
        (t) async {
      await _pump(t, _board(
          outcome: VerdictOutcome.noVerdict, actionToken: 'NO_VERDICT'));
      expect(_texts(t).where((s) => s.contains('NO_VERDICT')), isEmpty);
    });

    testWidgets('an action we have never shipped renders, neutrally', (t) async {
      // T-UNKNOWN's real concern: a new backend action must not silently become
      // a real outcome. It also must not become a fake failure — the run DID
      // produce a verdict.
      await _pump(t, _board(
        outcome: VerdictOutcome.unknown,
        actionToken: 'DEFERRED_PENDING_EARNINGS',
      ));
      expect(t.takeException(), isNull);
      expect(find.text('DEFERRED_PENDING_EARNINGS'), findsOneWidget);
      expect(accentForOutcome(VerdictOutcome.unknown), AmiColors.slate500);
    });

    testWidgets('T-UNIT — a bare percentage never stands alone', (t) async {
      await _pump(t, _board());
      expect(find.text('3.0%'), findsOneWidget);
      // Without the unit line the number reads as an expected return.
      expect(find.textContaining('OF PORTFOLIO'), findsOneWidget);
    });

    testWidgets('PASS says NO POSITION, never 0%', (t) async {
      await _pump(t, _board(outcome: VerdictOutcome.pass, sizePct: null));
      expect(find.text('NO POSITION'), findsOneWidget);
      final texts = _texts(t);
      expect(texts.where((s) => s == '0%' || s == '0.0%'), isEmpty);
    });
  });

  group('acceptance #3 — the ribbon is gated on provenance (T-PROV)', () {
    testWidgets('with provenance: ribbon, ratio, and a derived-level note',
        (t) async {
      await _pump(t, _board());
      expect(find.textContaining('RISK'), findsOneWidget);
      // (172 - 150) / (150 - 141) = 2.4
      expect(find.text('2.4 : 1'), findsOneWidget);
      // The minted stop is named, and named as AMI's — not the PM's.
      expect(find.textContaining('SET BY AMI, NOT THE PM'), findsOneWidget);
      expect(find.textContaining('STOP'), findsWidgets);
    });

    testWidgets('without provenance: the plain list, captioned, no ratio',
        (t) async {
      await _pump(t, _board(provenance: null));
      expect(find.textContaining('PROVENANCE UNAVAILABLE'), findsOneWidget);
      expect(find.textContaining('RISK'), findsNothing);
      final texts = _texts(t);
      expect(texts.where((s) => s.contains(' : 1')), isEmpty,
          reason: 'a ratio implies a geometry we cannot attribute');
      // The prices themselves are still shown — only the graphic is withheld.
      expect(find.text('\$150.00'), findsOneWidget);
    });

    testWidgets('an all-stated verdict names no derived level', (t) async {
      await _pump(t, _board(provenance: const {
        'entry': LevelSource.pm,
        'stop': LevelSource.pm,
        'target': LevelSource.pm,
      }));
      expect(find.textContaining('SET BY AMI'), findsNothing);
    });

    testWidgets('the ratio is locked LTR (T-BIDI)', (t) async {
      // Verified in the prototype: without this, "2.8 : 1" renders as
      // "1 : 2.8" under RTL — a WRONG NUMBER, not a layout nit.
      await t.pumpWidget(
        MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Directionality(
            textDirection: TextDirection.rtl,
            child: Scaffold(
              body: SingleChildScrollView(child: RoomBoard(data: _board())),
            ),
          ),
        ),
      );
      await t.pumpAndSettle();
      final ratio = t
          .widgetList<Text>(find.byType(Text))
          .firstWhere((w) => (w.data ?? '').contains(' : 1'));
      expect(ratio.textDirection, TextDirection.ltr);
    });

    testWidgets('no ribbon on a PASS — there is no geometry to draw',
        (t) async {
      await _pump(t, _board(outcome: VerdictOutcome.pass));
      expect(find.textContaining('RISK'), findsNothing);
    });
  });

  group('acceptance #4 — the comb', () {
    testWidgets('eleven hexes, the PM caption, counts over stated only',
        (t) async {
      final voices = [
        for (final a in kCombVoices)
          _voice(a.id, stance: a.id == 'news_analyst' ? null : 'for'),
      ];
      await _pump(t, _board(voices: voices));
      expect(find.byType(CombHex), findsNWidgets(11));
      expect(find.text('THE PM DECIDES — THIS IS NOT A VOTE'), findsOneWidget);
      expect(find.text('11 VOICES'), findsOneWidget);
      expect(find.text('10 STATED A VIEW'), findsOneWidget,
          reason: 'a count that always sums to 11 would state a consensus '
              'that never occurred (T-SUM11)');
      expect(find.text('NOT STATED'), findsOneWidget);
    });

    testWidgets('no recorded stances → one sentence, not empty bands',
        (t) async {
      await _pump(t, _board(recordedStances: false));
      expect(find.text('NOT RECORDED'), findsOneWidget);
      expect(find.textContaining('Open the transcript'), findsOneWidget);
      expect(find.byType(CombHex), findsNothing,
          reason: 'eleven hexes in a gutter would read as "nobody had a view"');
      expect(find.text('FOR'), findsNothing);
    });

    testWidgets('the PM is never one of the voices (T-VOTE)', (t) async {
      expect(
        kCombVoices.map((a) => a.id),
        isNot(contains('portfolio_manager')),
      );
      expect(kCombVoices.length, 11);
    });

    testWidgets('an unknown conviction draws no bar at all', (t) async {
      // Absence must not look like "low".
      await _pump(t, _board(voices: [
        for (final a in kCombVoices) _voice(a.id, conviction: null),
      ]));
      expect(t.takeException(), isNull);
    });
  });

  group('DEF142 — the comb does not inherit HexAvatar\'s unreadable ink', () {
    test('the label clears the canvas floor on every family', () {
      double luminance(Color c) {
        double ch(double v) {
          v = v / 255.0;
          return v <= 0.03928
              ? v / 12.92
              : math.pow((v + 0.055) / 1.055, 2.4).toDouble();
        }

        return 0.2126 * ch((c.r * 255).roundToDouble()) +
            0.7152 * ch((c.g * 255).roundToDouble()) +
            0.0722 * ch((c.b * 255).roundToDouble());
      }

      double ratio(Color a, Color b) {
        final la = luminance(a), lb = luminance(b);
        final hi = la > lb ? la : lb, lo = la > lb ? lb : la;
        return (hi + 0.05) / (lo + 0.05);
      }

      const fills = [
        AmiColors.hexCyan,
        AmiColors.hexAmber,
        AmiColors.hexGreen,
        AmiColors.hexPink,
        AmiColors.hexPurple,
      ];

      // Non-vacuity, and the DEF142 defect stated as a measurement: the shipped
      // `HexAvatar` ink (white on the saturated family fill) fails the 4.5:1
      // normal-text floor on every one of the five.
      for (final fill in fills) {
        expect(ratio(Colors.white, fill), lessThan(4.5),
            reason: 'white on $fill was supposed to be the defect');
      }

      // Nor is there a dark ink that rescues a solid fill: on `hexPurple`,
      // `slate900` measures 4.22 against white's 4.23 (a wash) and `textHigh`
      // is 3.85 — WORSE than white. That is why the comb changes the FILL.
      expect(ratio(AmiColors.slate900, AmiColors.hexPurple), lessThan(4.5));
      expect(ratio(AmiColors.textHigh, AmiColors.hexPurple), lessThan(4.5));

      // The shipped treatment: family colour on the canvas interior. Every
      // family clears the project's own accent-as-type floor, which was itself
      // set by the dimmest token here.
      for (final fill in fills) {
        expect(
          ratio(combInkFor(fill), AmiColors.slate900),
          greaterThanOrEqualTo(amiCanvasContrastFloor),
          reason: 'comb label fails the canvas floor on $fill',
        );
      }
      // Four of the five clear the full 4.5:1 normal-text floor outright.
      final clearing = [
        for (final f in fills)
          if (ratio(combInkFor(f), AmiColors.slate900) >= 4.5) f,
      ];
      expect(clearing.length, 4);

      // The palette has moved once already (`hexPurple` was `#A855F7`), so pin
      // the value the floor is calibrated against.
      expect(ratio(AmiColors.hexPurple, AmiColors.slate900),
          closeTo(4.22, 0.02));
    });

    test('comb labels fit and stay recognisable', () {
      for (final a in kCombVoices) {
        final label = combLabelFor(a.id);
        expect(label.length, lessThanOrEqualTo(4), reason: a.id);
        expect(label, isNotEmpty, reason: a.id);
      }
      // Only two differ from the shipped abbreviation — a truncation, not a
      // second naming scheme to learn.
      final differing = [
        for (final a in kCombVoices)
          if (combLabelFor(a.id) != a.abbreviation) a.id,
      ];
      expect(differing, ['research_manager', 'trader']);
    });
  });

  group('acceptance #6 — the mandate override is never collapsed', () {
    testWidgets('override renders its heading and every violation inline',
        (t) async {
      await _pump(t, _board(
        outcome: VerdictOutcome.pass,
        overridden: true,
        violations: const [
          'Position would take semiconductor exposure to 34.2%.',
          'Single-name cap is 25%.',
        ],
      ));
      expect(find.textContaining('MANDATE OVERRIDE'), findsOneWidget);
      expect(find.textContaining('semiconductor exposure'), findsOneWidget);
      expect(find.textContaining('Single-name cap'), findsOneWidget);
      // Without it the board contradicts itself — the comb shows a majority
      // in favour while the hero says PASS (T-OVERRIDE).
      expect(find.byType(ExpansionTile), findsNothing);
    });

    testWidgets('no override → no line', (t) async {
      await _pump(t, _board());
      expect(find.textContaining('MANDATE OVERRIDE'), findsNothing);
    });
  });

  group('the roster gap', () {
    testWidgets('names the withheld analysts and never mislabels one',
        (t) async {
      await _pump(t, _board(withheld: const ['social_media_analyst']));
      expect(find.text('THE ROSTER GAP'), findsOneWidget);
      expect(find.text('1 NOT HEARD'), findsOneWidget);
      expect(find.text('• Social Media Analyst'), findsOneWidget);
    });

    testWidgets('an unresolvable id renders as itself, never as a name',
        (t) async {
      // `agentById` falls back to the Concierge for an unknown id — in a
      // disclosure that would name the WRONG analyst as absent.
      await _pump(t, _board(withheld: const ['future_analyst']));
      expect(find.text('• future_analyst'), findsOneWidget);
      expect(find.textContaining('Concierge'), findsNothing);
    });

    testWidgets('survives a run that never reached a verdict', (t) async {
      // The CR098 round-1 audit finding, one layer up: on a dropped socket
      // there is no verdict to read `opinions_not_included` off, and the only
      // source is the `agent_withheld` events already in state.
      await _pump(t, _board(
        outcome: VerdictOutcome.noResult,
        withheld: const [],
        voices: [
          for (final a in kCombVoices)
            _voice(a.id, withheld: a.id == 'market_analyst'),
        ],
      ));
      expect(find.text('THE ROSTER GAP'), findsOneWidget);
      expect(find.text('• Market Analyst'), findsOneWidget);
    });

    testWidgets('a full roster shows no gap at all', (t) async {
      await _pump(t, _board());
      expect(find.text('THE ROSTER GAP'), findsNothing);
    });
  });

  group('acceptance #12 — a journal board is a record, not a setup', () {
    testWidgets('the geometry carries the run date', (t) async {
      await _pump(t, _board(isRecord: true));
      expect(find.textContaining('02 JUN 2026'), findsOneWidget);
      expect(find.textContaining('A RECORD, NOT A CURRENT SETUP'),
          findsOneWidget);
    });

    testWidgets('a live board carries no date caption', (t) async {
      await _pump(t, _board());
      expect(find.textContaining('A RECORD, NOT'), findsNothing);
    });
  });

  group('acceptance #5 — collapsed rows extract, never summarise', () {
    test('the headline wins when the agent stated one', () {
      expect(
        gistFor(_voice('trader', headline: 'FCF 6.2% vs 3.1%')),
        'FCF 6.2% vs 3.1%',
      );
    });

    test('otherwise the first bold span, verbatim', () {
      expect(
        gistFor(_voice('trader',
            content: 'Lead line. **\$30.8B · 4** is the number.')),
        '\$30.8B · 4',
      );
    });

    test('then the level triple, parsed not paraphrased', () {
      final gist = gistFor(_voice(
        'trader',
        headline: null,
        content: 'BUY 3% at entry \$178.40, stop \$168.90, target \$205.00.',
      ));
      expect(gist, '\$178.40 → \$205.00 stop \$168.90');
    });

    test('a partial triple yields nothing — two thirds is not a setup', () {
      expect(
        gistFor(_voice('trader',
            headline: null, content: 'Entry near \$178.40, stop unclear.')),
        isNull,
      );
    });

    test('no gist is ever a truncated sentence', () {
      // The Bull/Bear prompts ask for thesis + evidence + falsifier; cutting an
      // adversative sentence at 32 characters strands the negation and inverts
      // the meaning (the DEF059 class).
      final long = 'The bull case holds unless the buyback pace slows, which '
          'would remove the only support under the multiple.';
      expect(gistFor(_voice('bull_researcher', headline: null, content: long)),
          isNull);
    });

    test('the AMI annotation mark is a substring test on the content', () {
      expect(hasAmiAnnotation('plain prose'), isFalse);
      expect(
        hasAmiAnnotation('prose\n\n[AMI verified the trade geometry …]'),
        isTrue,
      );
      // DEF125's truncation mark rides the same channel, so a cut-off turn is
      // flagged in the collapsed transcript with no client change.
      expect(
        hasAmiAnnotation('half a sen\n\n[AMI: this contribution hit its '
            'length limit and stops mid-thought — it is incomplete.]'),
        isTrue,
      );
    });
  });
}
