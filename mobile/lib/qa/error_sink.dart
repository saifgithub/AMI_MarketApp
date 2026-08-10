/// CR163 — QA-only error sink: the app records its own failures where an
/// automated crawler can read them.
///
/// Why this exists rather than reading the device log: **Flutter's Dart output
/// does not reach iOS `os_log`.** Measured 2026-08-10 — a `log stream` capture
/// of a running Runner process returned 5,685 lines and not one Dart-origin
/// entry, while the app was actively calling `debugPrint`. Dart stdout/stderr
/// goes to the process's own stdout, which `simctl spawn log stream` never
/// sees. `flutter run` shows those lines because it holds the pipe; a harness
/// that attaches to an already-running app does not.
///
/// So the app writes them down instead. Same mechanism on both platforms, no
/// log-transport differences to reason about, and it survives the crawler
/// crashing.
///
/// **Off unless `--dart-define=AMI_QA_SEMANTICS=1`.** No file is created, no
/// handler is installed, and `runApp` is untouched in a build a user receives.
///
/// This only sees what Flutter *reports*. In a release build Flutter compiles
/// most framework assertions out, which is why the crawler drives a debug
/// build — see `docs/forward_planning/CR163_autonomous_bug_crawler/`.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

/// Filename inside the app's documents directory. The crawler resolves the
/// container with `xcrun simctl get_app_container <udid> <bundle> data`.
const qaErrorSinkFilename = 'ami_qa_errors.jsonl';

/// Cap so a single error looping every frame cannot fill the disk — the exact
/// scenario this is built to catch (a RenderFlex overflow re-reports on every
/// frame, thousands of times a minute).
const _maxRecords = 500;

class QaErrorSink {
  QaErrorSink._();

  static final QaErrorSink instance = QaErrorSink._();

  File? _file;
  int _written = 0;
  final Set<String> _seen = <String>{};

  /// Install the handlers and truncate any previous run's file. Safe to call
  /// once, from main(), behind the QA flag.
  Future<void> install() async {
    try {
      final dir = await getApplicationDocumentsDirectory();
      _file = File('${dir.path}/$qaErrorSinkFilename');
      await _file!.writeAsString('');
    } catch (_) {
      // No sink means the crawler reports zero errors, which would read as "the
      // app is clean". Say so on stdout so a `flutter run` session shows it;
      // the crawler separately treats a missing file as a hard failure rather
      // than as an empty result.
      debugPrint('QA ERROR SINK UNAVAILABLE — crawl results will be incomplete');
      return;
    }

    final previousOnError = FlutterError.onError;
    FlutterError.onError = (FlutterErrorDetails details) {
      _record(
        kind: 'flutter_error',
        library: details.library ?? 'unknown',
        message: details.exceptionAsString(),
        stack: details.stack?.toString(),
      );
      previousOnError?.call(details);
    };

    // Errors that escape the framework entirely — an unawaited future that
    // throws, a platform-channel failure. FlutterError.onError never sees these.
    PlatformDispatcher.instance.onError = (Object error, StackTrace stack) {
      _record(
        kind: 'uncaught',
        library: 'zone',
        message: error.toString(),
        stack: stack.toString(),
      );
      return false; // false = still report it normally; we are observing, not swallowing
    };
  }

  void _record({
    required String kind,
    required String library,
    required String message,
    String? stack,
  }) {
    final file = _file;
    if (file == null || _written >= _maxRecords) return;

    // Deduplicate on kind+library+first line. The same overflow fires every
    // frame; writing each one buries the second, different defect under
    // thousands of copies of the first.
    final firstLine = message.split('\n').first.trim();
    final key = '$kind|$library|$firstLine';
    if (!_seen.add(key)) return;

    _written++;
    try {
      file.writeAsStringSync(
        '${jsonEncode({
          'kind': kind,
          'library': library,
          'message': firstLine,
          'full': message.length > 2000 ? message.substring(0, 2000) : message,
          'stack': stack == null
              ? null
              : (stack.length > 2000 ? stack.substring(0, 2000) : stack),
        })}\n',
        mode: FileMode.append,
        flush: true, // the crawler may read mid-run, and the app may die next frame
      );
    } catch (_) {
      // Never let the act of recording an error throw a second one.
    }
  }
}
