/// CR266 — the typed decision record and the next-convene delta, parsed where
/// they live (`room.dart`), with the project's one load-bearing rule pinned on
/// every field: **absence is absence, never a default** (T-BACKFILL). An old
/// verdict with no record must stay `null` end to end — the board must never
/// be able to read it as "not contested" — and a recorded value (including a
/// recorded `false`) must survive untouched.
library;

import 'package:ami_trade/models/room.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _verdictJson(Map<String, dynamic> extra) => {
      'action': 'APPROVE',
      'reason': 'Synthesis defended.',
      ...extra,
    };

void main() {
  group('DecisionRecord.fromJson', () {
    test('a full record parses every field', () {
      final r = DecisionRecord.fromJson({
        'score': 0.71,
        'threshold': 0.55,
        'allowed_actions': ['APPROVE', 'PASS'],
        'computed_size_pct': 3.4,
        'unresolved_objections': ['The split vote was overridden.'],
        'unresolved_objection_ids': ['bear_researcher'],
        'evidence_available': true,
        'evidence_source': 'claims_v3',
        'contested': true,
        'contested_reasons': ['split_vote', 'weak_evidence'],
      });
      expect(r.score, 0.71);
      expect(r.threshold, 0.55);
      expect(r.allowedActions, ['APPROVE', 'PASS']);
      expect(r.computedSizePct, 3.4);
      expect(r.unresolvedObjections, ['The split vote was overridden.']);
      expect(r.unresolvedObjectionIds, ['bear_researcher']);
      expect(r.evidenceAvailable, isTrue);
      expect(r.evidenceSource, 'claims_v3');
      expect(r.contested, isTrue);
      expect(r.contestedReasons, ['split_vote', 'weak_evidence']);
    });

    test('ints on the wire become doubles for the float fields', () {
      final r = DecisionRecord.fromJson({'score': 1, 'computed_size_pct': 2});
      expect(r.score, 1.0);
      expect(r.computedSizePct, 2.0);
    });

    test('an absent field stays null — contested is never inferred false', () {
      final r = DecisionRecord.fromJson(const {});
      expect(r.score, isNull);
      expect(r.contested, isNull);
      expect(r.evidenceAvailable, isNull);
      expect(r.allowedActions, isNull);
      expect(r.contestedReasons, isNull);
    });

    test('a recorded false survives — the opposite of absent', () {
      // The distinction the whole card gating rests on: only an explicit
      // `true` renders the contested card, and only an explicit `false`
      // certifies "recorded, not contested". Collapsing false into null (or
      // null into false) would let the board claim either fabrication.
      final r = DecisionRecord.fromJson({'contested': false});
      expect(r.contested, isFalse);
    });

    test('a non-bool on a bool field degrades to null, not a thrown cast', () {
      final r = DecisionRecord.fromJson({
        'contested': 'true',
        'evidence_available': 1,
      });
      expect(r.contested, isNull);
      expect(r.evidenceAvailable, isNull);
    });

    test('a present-but-empty list stays empty; a non-list stays null', () {
      final r = DecisionRecord.fromJson({
        'contested_reasons': <String>[],
        'unresolved_objections': 'not_a_list',
      });
      expect(r.contestedReasons, isEmpty);
      expect(r.unresolvedObjections, isNull);
    });

    test('one non-string element never throws inside build()', () {
      final r = DecisionRecord.fromJson({
        'contested_reasons': ['split_vote', 7, null, 'weak_evidence'],
      });
      expect(r.contestedReasons, ['split_vote', 'weak_evidence']);
    });
  });

  group('NextConveneDelta.fromJson', () {
    test('a full delta parses, transitions included', () {
      final d = NextConveneDelta.fromJson({
        'prior_date': '2026-10-20T14:30:00Z',
        'prior_action': 'PASS',
        'price_move_pct': 2.43,
        'changed_fields': [
          {
            'field': 'margin_trend',
            'from_state': 'LIVE',
            'to_state': 'UNAVAILABLE',
          },
          {
            'field': 'technicals',
            'from_state': 'LIVE',
            'to_state': 'WITHHELD_PAID',
          },
        ],
        'prior_kill_criterion': 'Gross margin compression below 38%.',
      });
      expect(d.priorDate, DateTime.utc(2026, 10, 20, 14, 30));
      expect(d.priorAction, 'PASS');
      expect(d.priceMovePct, 2.43);
      expect(d.changedFields.length, 2);
      expect(d.changedFields.first.field, 'margin_trend');
      expect(d.changedFields.first.fromState, 'LIVE');
      expect(d.changedFields.first.toState, 'UNAVAILABLE');
      expect(d.changedFields.last.toState, 'WITHHELD_PAID');
      expect(d.priorKillCriterion, 'Gross margin compression below 38%.');
    });

    test('the minimal delta — date and action only — parses clean', () {
      final d = NextConveneDelta.fromJson({
        'prior_date': '2026-10-20T14:30:00Z',
        'prior_action': 'APPROVE',
      });
      expect(d.priorDate, isNotNull);
      expect(d.priorAction, 'APPROVE');
      expect(d.priceMovePct, isNull);
      // `changed_fields` defaults to an empty list server-side; empty here
      // means "the prior predates sheet_state", never "nothing changed".
      expect(d.changedFields, isEmpty);
      expect(d.priorKillCriterion, isNull);
    });

    test('an unparseable date degrades to null, not a throw', () {
      final d = NextConveneDelta.fromJson({
        'prior_date': 'not-a-date',
        'prior_action': 'APPROVE',
      });
      expect(d.priorDate, isNull);
    });

    test('non-map entries inside changed_fields are skipped', () {
      final d = NextConveneDelta.fromJson({
        'prior_date': '2026-10-20T14:30:00Z',
        'prior_action': 'APPROVE',
        'changed_fields': [
          'garbage',
          {'field': 'news', 'from_state': 'LIVE', 'to_state': 'UNAVAILABLE'},
        ],
      });
      expect(d.changedFields.length, 1);
      expect(d.changedFields.single.field, 'news');
    });

    test('a non-list changed_fields degrades to empty, not a throw', () {
      final d = NextConveneDelta.fromJson({
        'prior_date': '2026-10-20T14:30:00Z',
        'prior_action': 'APPROVE',
        'changed_fields': 42,
      });
      expect(d.changedFields, isEmpty);
    });
  });

  group('RoomVerdict carries both through fromJson', () {
    test('verdict-level decision_record and next_convene_delta parse', () {
      final v = RoomVerdict.fromJson(_verdictJson({
        'decision_record': {'contested': true, 'score': 0.7},
        'next_convene_delta': {
          'prior_date': '2026-10-20T14:30:00Z',
          'prior_action': 'PASS',
        },
      }));
      expect(v.decisionRecord?.contested, isTrue);
      expect(v.decisionRecord?.score, 0.7);
      expect(v.nextConveneDelta?.priorAction, 'PASS');
    });

    test('an old-shape verdict has neither — and never a fabricated one',
        () {
      final v = RoomVerdict.fromJson(_verdictJson(const {}));
      expect(v.decisionRecord, isNull);
      expect(v.nextConveneDelta, isNull);
    });

    test('a non-map decision_record or delta degrades to null', () {
      final v = RoomVerdict.fromJson(_verdictJson({
        'decision_record': 'contested',
        'next_convene_delta': 3,
      }));
      expect(v.decisionRecord, isNull);
      expect(v.nextConveneDelta, isNull);
    });
  });
}
