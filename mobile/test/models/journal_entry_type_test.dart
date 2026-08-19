// CR136 M08 — wire mapping for portfolio_health_analysis + the DEF210 null-on-unknown contract.

import 'package:ami_trade/models/journal.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('portfolio_health_analysis maps to its enum member', () {
    expect(
      JournalEntryTypeJson.fromWire('portfolio_health_analysis'),
      JournalEntryType.portfolioHealthAnalysis,
    );
    expect(
      JournalEntryType.portfolioHealthAnalysis.wire,
      'portfolio_health_analysis',
    );
  });

  test('every member round-trips through its own wire value', () {
    // Swept rather than listed, so a future member is covered the day it is
    // added instead of the day someone remembers to extend this test.
    for (final type in JournalEntryType.values) {
      expect(JournalEntryTypeJson.fromWire(type.wire), type, reason: type.name);
    }
  });

  test('an unknown wire value stays null and is never coerced', () {
    // DEF210: the previous behaviour silently labelled unrecognised entries
    // "1-ON-1". A null routes to the honest UNKNOWN card instead.
    expect(JournalEntryTypeJson.fromWire('never_heard_of_it'), isNull);

    final entry = JournalEntry.fromJson(const {
      'id': '11111111-1111-1111-1111-111111111111',
      'user_id': '22222222-2222-2222-2222-222222222222',
      'entry_type': 'never_heard_of_it',
      'title': 'Something new',
      'created_at': '2026-08-02T09:00:00Z',
      'payload': <String, dynamic>{},
    });
    expect(entry.entryType, isNull);
  });

  test('compliance_block parses inert on a build that predates it', () {
    // CR177 acceptance 5, pinned on the LITERAL wire value: the backend ships
    // by rsync same-day while this client ships through store review, so
    // every installed build will receive `compliance_block` entries before it
    // can name them. They must take the DEF210 null → UNKNOWN-badge path —
    // never crash, never render as a result. The journal card's switch is
    // exhaustive over the nullable enum (an explicit `case null:` arm), so
    // the render half of that guarantee is compile-time; this pins the
    // parse half. When the client learns the type, this test flips to a
    // round-trip expectation like portfolio_health_analysis above.
    expect(JournalEntryTypeJson.fromWire('compliance_block'), isNull);

    final entry = JournalEntry.fromJson(const {
      'id': '33333333-3333-3333-3333-333333333333',
      'user_id': '22222222-2222-2222-2222-222222222222',
      'entry_type': 'compliance_block',
      'title': 'BLOCKED: BUY 5 AAPL',
      'created_at': '2026-08-19T09:00:00Z',
      'payload': <String, dynamic>{'blocked_by': 'single_name_cap'},
    });
    expect(entry.entryType, isNull);
    expect(entry.outcome, isNull, reason: 'a block must never read as a result');
  });
}
