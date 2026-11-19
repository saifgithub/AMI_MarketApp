/// CR278 (CR267 WP-36, D-076) - the compile-time marker of a Beta build.
///
/// A Beta build is English only: the locale is pinned to `en` and Settings
/// shows no language switch. It is a build-time define rather than a runtime
/// setting for the reason `AMI_GAMES` is (games_gate.dart): a store binary's
/// behaviour should not depend on something a caller can flip after the fact.
///
///     flutter build ios --release --dart-define=AMI_BETA=true
///     flutter build appbundle --release --dart-define=AMI_BETA=true
///
/// Default builds (no define) are unchanged: all three locales, the switch
/// shown. Read as a flexible truthy STRING, not `bool.fromEnvironment`, which
/// accepts only the literals 'true'/'false' and so reads `AMI_BETA=1` as false
/// without saying so (the `AMI_QA_SEMANTICS` lesson, main.dart).
///
/// [betaEnglishOnlyProvider] is the seam widgets read, so a test can override
/// it without recompiling with the define.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

const String _betaFlag = String.fromEnvironment('AMI_BETA');

/// True only when the build was made with `--dart-define=AMI_BETA=<truthy>`.
const bool kBetaBuild = _betaFlag == '1' ||
    _betaFlag == 'true' ||
    _betaFlag == 'yes' ||
    _betaFlag == 'on';

/// Whether this build locks the app to English and hides the language switch.
final betaEnglishOnlyProvider = Provider<bool>((ref) => kBetaBuild);
