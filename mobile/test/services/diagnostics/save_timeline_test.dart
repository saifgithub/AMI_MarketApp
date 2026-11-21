/// DEF521 — the SAVE-path breadcrumb buffer keeps only the newest lines and
/// leaves the bug-report steps untouched when nothing was recorded.
library;

import 'package:ami_trade/services/diagnostics/save_timeline.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  setUp(SaveTimeline.reset);

  test('nothing recorded leaves the steps unchanged', () {
    expect(SaveTimeline.summary(), isNull);
    expect(SaveTimeline.appendTo('steps'), 'steps');
    expect(SaveTimeline.appendTo(null), isNull);
  });

  test('ring buffer keeps the newest 24 and appends to the steps', () {
    for (var i = 0; i < 30; i++) {
      SaveTimeline.mark('step$i');
    }
    final s = SaveTimeline.summary()!;
    expect(s.contains('step0'), isFalse);
    expect(s.contains('step29'), isTrue);
    expect(';'.allMatches(s).length, 23);
    expect(SaveTimeline.appendTo('my steps'), startsWith('my steps\n[diag] save['));
  });
}
