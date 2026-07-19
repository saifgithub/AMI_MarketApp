/// CR043 — the reference the user is shown must be the same string the
/// server and `/fix-bugs` use, or quoting it back is useless.
library;

import 'package:ami_trade/state/feedback_providers.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('shortId matches the server-side LEFT(id::text, 8)', () {
    // Real id from bug_reports; psql renders LEFT(id::text, 8) as
    // 'a52455ad', and /fix-bugs uses the same 8 chars in commit subjects.
    const state = FeedbackState(
      reportId: 'a52455ad-9362-4c8c-98b6-01a4effe2088',
    );
    expect(state.shortId, 'a52455ad');
  });

  test('shortId is null before a successful submit', () {
    expect(const FeedbackState().shortId, isNull);
  });

  test('copyWith carries the report id', () {
    final next = const FeedbackState()
        .copyWith(submitted: true, reportId: '788b80c0-ffc2-4b28-a197-37b');
    expect(next.submitted, isTrue);
    expect(next.shortId, '788b80c0');
  });
}
