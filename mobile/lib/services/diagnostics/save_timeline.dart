/// DEF521 — a release-safe ring buffer of timed breadcrumbs for the Settings
/// SAVE path (PATCH, journal re-read, dirty-clear, audit, portfolio refresh).
///
/// A device run (AMI-DL-13) saw ~17 s with no server request between the
/// mandate PATCH and the retro-tightening audit. The server log can only say
/// "nothing arrived"; what the phone was waiting on is invisible from there.
/// Each awaited step now leaves a `+<ms since first mark> <label>` line, kept
/// to the last [_max] and appended to the in-app bug report beside the
/// `SemanticsHealth` line — the same user-initiated, no-PII channel (labels are
/// fixed strings and durations, never user data). Nothing is sent on its own.
library;

import 'package:flutter/foundation.dart';

class SaveTimeline {
  SaveTimeline._();

  static const _max = 24;
  static final Stopwatch _clock = Stopwatch();
  static final List<String> _lines = <String>[];

  /// Record [label]. Also `debugPrint`ed so a tethered run shows it live.
  static void mark(String label) {
    if (!_clock.isRunning) _clock.start();
    final line = '+${_clock.elapsedMilliseconds}ms $label';
    if (_lines.length >= _max) _lines.removeAt(0);
    _lines.add(line);
    debugPrint('save-timeline $line');
  }

  /// One block for the bug report, or `null` when nothing was recorded.
  static String? summary() =>
      _lines.isEmpty ? null : 'save[${_lines.join(';')}]';

  /// [steps] with [summary] on a trailing line, or [steps] unchanged.
  static String? appendTo(String? steps) {
    final s = summary();
    if (s == null) return steps;
    final base = steps?.trim() ?? '';
    return base.isEmpty ? '[diag] $s' : '$base\n[diag] $s';
  }

  @visibleForTesting
  static void reset() {
    _lines.clear();
    _clock
      ..stop()
      ..reset();
  }
}
