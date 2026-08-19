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

  group('DEF253 — only a call that waits on AMI may blame AMI', () {
    // Saiful, on 4G, healthy backend, AMI not in the call path:
    // "Couldn't load your portfolio — AMI took too long to answer."
    // `docker logs` showed no `/v1/sim/portfolio/` request arriving at all, so
    // the sentence was wrong about which half of the system failed.
    DioException timeout(DioExceptionType type, {bool waitsOnModel = false}) =>
        DioException(
          requestOptions: RequestOptions(
            path: '/v1/sim/portfolio/u1',
            extra: waitsOnModel ? Map<String, dynamic>.from(kAmiWaitsOnModel) : {},
          ),
          type: type,
        );

    test('the reported case: a portfolio read never names AMI', () {
      final msg = friendlyError(timeout(DioExceptionType.receiveTimeout),
          action: 'load your portfolio');
      expect(msg.contains('AMI'), isFalse, reason: msg);
      expect(msg.toLowerCase(), contains('connection'),
          reason: 'the user is owed the thing they can act on — signal, not a '
              'claim about the model');
    });

    test('a call that really does wait on the model may still say so', () {
      final msg = friendlyError(
          timeout(DioExceptionType.receiveTimeout, waitsOnModel: true),
          action: 'get your Finding');
      expect(msg, contains('AMI took too long to answer'));
    });

    test('connect and send timeouts never name AMI, marker or not', () {
      // Nothing was ever asked, so nothing could have been slow to answer.
      // This is the half that must hold even on a model-backed route, and it
      // is why the marker is read only on receiveTimeout.
      for (final type in [
        DioExceptionType.connectionTimeout,
        DioExceptionType.sendTimeout,
      ]) {
        for (final waits in [false, true]) {
          final msg = friendlyError(timeout(type, waitsOnModel: waits),
              action: 'load your portfolio');
          expect(msg.contains('AMI'), isFalse,
              reason: '$type (waitsOnModel: $waits) → $msg');
        }
      }
    });

    test('the sibling branch stopped asserting AMI is down', () {
      for (final type in [
        DioExceptionType.connectionError,
        DioExceptionType.unknown,
      ]) {
        final msg =
            friendlyError(timeout(type), action: 'load your portfolio');
        expect(msg.contains('AMI'), isFalse, reason: '$type → $msg');
        expect(msg.toLowerCase(), contains('connection'));
      }
    });

    test('the marker reaches the two call sites that need it, and no others',
        () {
      // The caller-side half. `friendlyError` reading the marker correctly says
      // nothing about whether any request carries one — DEF190's lesson, and
      // the reason this asserts the client source rather than a fake options
      // map. Two routes: `/v1/brief/propose` (`brief_engine.propose` streams
      // from `self._llm`) and `/v1/portfolio/health/{id}/finding`
      // (`generate_and_persist_finding(gateway=get_llm_gateway())`). The Room,
      // Brief-message and 1-on-1 streams are absent because they do not use
      // Dio at all and can never raise a DioException.
      final src =
          File('lib/services/api/api_client.dart').readAsStringSync();
      expect(src, contains('kAmiWaitsOnModel'),
          reason: 'the client stopped marking anything — every model-backed '
              'timeout now under-explains');

      for (final route in const [
        "'/v1/brief/propose'",
        r"'/v1/portfolio/health/$userId/finding'",
      ]) {
        final i = src.indexOf(route);
        expect(i, greaterThan(-1), reason: 'route moved or was renamed: $route');
        final end = i + 500 < src.length ? i + 500 : src.length;
        expect(src.substring(i, end), contains('kAmiWaitsOnModel'),
            reason: '$route no longer carries the marker, so a receive '
                'timeout on it under-explains a genuinely slow model');
      }

      // Exactly two call sites plus the `show` on the import. A third would
      // mean something that does not wait on the model is claiming it does,
      // which is the defect running in the other direction.
      expect('kAmiWaitsOnModel'.allMatches(src).length, 3,
          reason: 'the marked set changed — verify server-side that the new '
              'route awaits the LLM gateway before widening it');

      // The route the defect was actually reported against must stay unmarked.
      final portfolio = src.indexOf(r"'/v1/sim/portfolio/$userId'");
      expect(portfolio, greaterThan(-1));
      final end =
          portfolio + 300 < src.length ? portfolio + 300 : src.length;
      expect(src.substring(portfolio, end).contains('kAmiWaitsOnModel'), isFalse,
          reason: 'the portfolio read is a database call — marking it would '
              'reinstate DEF253 verbatim');
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
        // DEF331 — `debugPrint` is exempt because it is a log, not a screen,
        // but the exemption used to be tested on the same physical line as the
        // match. A wrapped call puts the interpolation on a CONTINUATION line
        // that contains no `debugPrint` token, so a correctly-written log was
        // reported as a leak — `term_registry.dart:56` (DEF325), where the
        // string simply ran past 80 columns.
        //
        // A guard that fires on correct code is the failure this repo has paid
        // for repeatedly (DEF277; DEF329 was this exact line-vs-statement
        // mistake in the register generator). So the exemption now tracks the
        // whole call: once `debugPrint(` opens, every line stays exempt until
        // its parentheses balance.
        var debugPrintDepth = 0;
        for (var i = 0; i < lines.length; i++) {
          final line = lines[i];
          if (line.trimLeft().startsWith('//')) continue;

          final wasInsideDebugPrint = debugPrintDepth > 0;
          if (wasInsideDebugPrint || line.contains('debugPrint(')) {
            // Start at the '(' itself on the opening line, so the first
            // character read is the paren that opens the call. Starting at the
            // 'd' of `debugPrint` and breaking on "depth is 0" exits before
            // any paren is seen, which is how the first attempt at this fix
            // still reported term_registry.dart:56.
            final from = wasInsideDebugPrint
                ? 0
                : line.indexOf('debugPrint(') + 'debugPrint'.length;
            for (var c = from; c < line.length; c++) {
              if (line[c] == '(') {
                debugPrintDepth++;
              } else if (line[c] == ')') {
                debugPrintDepth--;
                if (debugPrintDepth <= 0) {
                  debugPrintDepth = 0;
                  break;
                }
              }
            }
            continue; // logs, not screens
          }
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

    test('DEF331 — a wrapped debugPrint is exempt, and only the debugPrint is',
        () {
      // The exemption is for logs, not screens. It used to be evaluated per
      // physical line, so a `debugPrint(` whose string ran onto a second line
      // left that continuation unexempted and a correct log was reported as a
      // leak. `term_registry.dart:56` (DEF325) is the real instance.
      //
      // This pins BOTH halves, because widening an exemption is the easy way
      // to make a guard quiet and useless:
      //   1. the real wrapped debugPrint is not reported;
      //   2. the leak regex still matches that exact text in isolation — so
      //      what silences it is the debugPrint exemption, NOT a weakened
      //      pattern. Without (2) this test would also pass if someone
      //      "fixed" the guard by making `_leak` match nothing.
      final registry = File('lib/widgets/lessons/term_registry.dart');
      expect(registry.existsSync(), isTrue,
          reason: 'DEF331 was found against this file');

      final continuation = registry
          .readAsLinesSync()
          .firstWhere((l) => l.contains(r'render as plain text: $e'),
              orElse: () => '');
      expect(continuation, isNotEmpty,
          reason: 'the wrapped debugPrint this test pins has been rewritten — '
              're-point it at another multi-line debugPrint, or drop it');
      expect(_leak.hasMatch(continuation), isTrue,
          reason: 'the pattern must still MATCH this text; the exemption is '
              'what makes it acceptable, not a hole in the regex');
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
