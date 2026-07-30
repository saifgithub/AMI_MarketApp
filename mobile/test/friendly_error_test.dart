/// DEF148 — never show a user an exception.
///
/// A lesson that failed to load printed the raw `DioException` to the screen:
/// stack text, `RequestOptions.validateStatus`, an MDN link, and the advice to
/// "fix your request code or fix the server code". It was the **second**
/// occurrence — DEF073 was the first, and the friendly handling it produced
/// was adopted by exactly one call site out of forty.
///
/// So the fix is not the call site, and neither is the test. The first group
/// checks that [friendlyError] says something a person can act on; the second
/// is the guard proper — it reads every provider and screen and fails if any
/// of them interpolates a caught object into user-facing text again. That is
/// the check the defect asked for, "applied across every provider at once".
library;

import 'dart:io';

import 'package:ami_trade/services/api/api_exceptions.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

DioException _dio(DioExceptionType type, {int? status}) => DioException(
      requestOptions: RequestOptions(path: '/v1/lessons/x'),
      type: type,
      response: status == null
          ? null
          : Response<void>(
              requestOptions: RequestOptions(path: '/v1/lessons/x'),
              statusCode: status,
            ),
    );

/// `catch (e)` binds the object; `'$e'` inside a literal is the leak.
///
/// Two details, one of which is load-bearing and one of which is belt:
///
/// - **The lookahead, not a closing `'`** — load-bearing. `$e` is almost always
///   the last thing before the quote, and an earlier version that required a
///   trailing `'` matched *none* of the real lines. It is also what keeps the
///   guard from crying wolf at `$entryId` and `$evaluated`, and a guard that
///   cries wolf gets deleted by the next person who trips over it.
/// - **`(?:[^'\\\n]|\\.)*` rather than `[^'\n]*`** — belt only, and measured
///   as such: swapping it back for the naive class leaves every assertion in
///   this file green, because in `'Couldn\'t reach the agent: $e'` the escaped
///   apostrophe simply re-opens as a literal and the naive pattern matches
///   from there. It is kept because it is the correct description of a Dart
///   string literal, not because a test can tell the difference today.
final _leak = RegExp(r"""'(?:[^'\\\n]|\\.)*\$e(?![a-zA-Z0-9_{])""");

/// The caught object's own `.toString()`, passed on with no
/// `friendlyError(...)` in between. `\be\.toString\(\)` — the word boundary
/// is what stops this from matching `locale.toString()`.
final _rawToString = RegExp(r'\be\.toString\(\)');

/// The strings that were on screen in the bug report, plus the shapes any
/// other leak would take.
const _tells = [
  'Exception',
  'DioException',
  'RequestOptions',
  'validateStatus',
  'http://',
  'https://',
  'status code',
  '#0 ',
];

void main() {
  group('DEF148 — friendlyError never leaks the exception', () {
    final cases = <String, Object>{
      'the reported 404': _dio(DioExceptionType.badResponse, status: 404),
      'a 500': _dio(DioExceptionType.badResponse, status: 500),
      'a 401': _dio(DioExceptionType.badResponse, status: 401),
      'a 429': _dio(DioExceptionType.badResponse, status: 429),
      'a 418 nobody planned for': _dio(DioExceptionType.badResponse, status: 418),
      'a badResponse with no response': _dio(DioExceptionType.badResponse),
      'offline': _dio(DioExceptionType.connectionError),
      'a timeout': _dio(DioExceptionType.receiveTimeout),
      'a cancel': _dio(DioExceptionType.cancel),
      'a bad certificate': _dio(DioExceptionType.badCertificate),
      'unknown': _dio(DioExceptionType.unknown),
      'DEF073\'s 502': const ServerUnavailableException(502),
      'the credit wall': const InsufficientCreditsException(
          balance: 0, cost: 1, plan: 'floor_pass'),
      'a bare Exception': Exception('boom'),
      'a StateError': StateError('bad state'),
      'a plain string': 'kaboom',
    };

    cases.forEach((name, error) {
      test('$name reads as English, not as diagnostics', () {
        final msg = friendlyError(error, action: 'open this lesson');
        for (final tell in _tells) {
          expect(msg.contains(tell), isFalse,
              reason: '$name leaked "$tell" into user copy: $msg');
        }
        expect(msg, contains('open this lesson'),
            reason: 'the user must be told WHAT failed, not just that '
                'something did');
        expect(msg.trim(), isNotEmpty);
        expect(msg.endsWith('.'), isTrue, reason: 'it is a sentence');
      });
    });

    test('the distinctions that change what the user should do survive', () {
      // Collapsing everything into one message would pass every assertion
      // above and still be the bug: a timeout means check your connection, a
      // 404 means stop tapping retry. DEF151 is what happens when a permanent
      // rejection is dressed as a transient one.
      final offline = friendlyError(_dio(DioExceptionType.connectionError),
          action: 'open this lesson');
      final gone = friendlyError(_dio(DioExceptionType.badResponse, status: 404),
          action: 'open this lesson');
      final unauthed = friendlyError(
          _dio(DioExceptionType.badResponse, status: 401),
          action: 'open this lesson');
      expect({offline, gone, unauthed}.length, 3,
          reason: 'these three need three different actions from the user');
      expect(offline.toLowerCase(), contains('connection'));
      expect(unauthed.toLowerCase(), contains('sign in'));
    });

    test('the action phrase is the caller\'s and is used verbatim', () {
      expect(friendlyError(Exception('x'), action: 'save your note'),
          contains('save your note'));
    });

    test('DEF164: the copy never offers a retry isRetryable() refuses', () {
      // Table-driven over every badResponse status code both functions
      // handle, so the next status either function grows a special case for
      // fails the build instead of shipping a second silent divergence.
      const statuses = [401, 403, 404, 418, 422, 429, 500, 502, 503];
      for (final status in statuses) {
        final err = _dio(DioExceptionType.badResponse, status: status);
        final retryable = isRetryable(err);
        final msg = friendlyError(err, action: 'load this').toLowerCase();
        final offersRetry = msg.contains('try again');
        expect(offersRetry, retryable,
            reason: 'status $status: isRetryable()=$retryable but copy '
                '${offersRetry ? 'offers' : 'does not offer'} a retry — '
                '"$msg"');
      }
    });
  });

  group('DEF148 — the guard: no call site may bypass it', () {
    /// Every file that can put text in front of a user.
    ///
    /// DEF164b: this used to be four hand-picked directories, and
    /// `lib/services/billing/revenuecat_purchase_service.dart` sat just
    /// outside them — a live counterexample the guard could not see. The
    /// whole of `lib/` is the accurate boundary: anything under `lib/` can
    /// end up on screen, `lib/generated/` is the one exception (l10n
    /// scaffolding, not hand-written call sites).
    List<File> userFacingSources() => Directory('lib')
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'))
        .where((f) => !f.path.contains('${Platform.pathSeparator}generated${Platform.pathSeparator}'))
        .toList();

    test('the sweep actually reaches the file the bug was reported against',
        () {
      // Vacuity guard. A glob that silently matches nothing would make every
      // assertion below pass forever.
      final paths = userFacingSources().map((f) => f.path).toList();
      expect(paths, isNotEmpty);
      expect(paths.any((p) => p.endsWith('lib/state/lessons_providers.dart')),
          isTrue, reason: 'DEF148 was reported against this exact file');
      expect(paths.length, greaterThan(40),
          reason: 'the sweep collapsed to a handful of files — re-point it');
    });

    test('no caught object is interpolated into a user-facing string', () {
      // Deliberately a source check rather than a runtime one: the failure is
      // a shape a developer writes, and it must go red in review, not on a
      // user's screen six days later.
      final offenders = <String>[];

      for (final file in userFacingSources()) {
        final lines = file.readAsLinesSync();
        for (var i = 0; i < lines.length; i++) {
          final line = lines[i];
          if (line.trimLeft().startsWith('//')) continue;
          if (line.contains('debugPrint')) continue; // logs, not screens
          final leaksInterpolated = _leak.hasMatch(line) || line.contains(r"'$e'");
          // DEF164b: e.toString() passed straight into a value is the same
          // leak with no string interpolation to catch it with — the
          // shape revenuecat_purchase_service.dart used.
          final leaksToString =
              _rawToString.hasMatch(line) && !line.contains('friendlyError(');
          if (leaksInterpolated || leaksToString) {
            offenders.add('${file.path}:${i + 1}  ${line.trim()}');
          }
        }
      }

      expect(offenders, isEmpty,
          reason: 'DEF148: pass the caught object to friendlyError(e, '
              'action: ...) instead of interpolating it. What the user gets '
              'otherwise is a stack trace and an MDN link.\n'
              '${offenders.join('\n')}');
    });

    test('the leak pattern would actually catch the lines that were there', () {
      // Pins the regex against the real DEF148 source, so a future edit cannot
      // loosen it into a check that matches nothing. Both of these were live
      // in this codebase an hour before this test existed.
      expect(_leak.hasMatch("error: 'Lesson load failed: \$e'"), isTrue,
          reason: 'the reported line');
      expect(_leak.hasMatch("content: 'Couldn\\'t reach the agent: \$e',"),
          isTrue,
          reason: 'the escaped-apostrophe variant — a naive [^\'] class stops '
              'at the \\\' and misses this entirely');
      expect(_leak.hasMatch("state.copyWith(error: 'Save failed: \$e');"),
          isTrue);
      // …and must not fire on legitimate interpolation of other identifiers,
      // or the guard gets disabled by whoever it cries wolf at.
      expect(_leak.hasMatch("error: 'Could not load \$entryId'"), isFalse);
      expect(_leak.hasMatch("label: 'Balance: \$entries left'"), isFalse);
      expect(_leak.hasMatch("Text('\$evaluated of \$total')"), isFalse);
    });
  });
}
