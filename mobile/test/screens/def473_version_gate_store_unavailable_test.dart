// DEF473 — the version-gate UPDATE button was a silent no-op when the
// release-floor response carried no store_url. On the hard-block screen
// (no back, no dismiss) that left the user with a dead button. It must now say
// so, in every locale, instead of doing nothing.

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/release_floor.dart';
import 'package:ami_trade/screens/version_gate/version_gate_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _app(Locale locale, ReleaseFloorResponse floor) => ProviderScope(
      child: MaterialApp(
        locale: locale,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: VersionGateBlockScreen(floor: floor),
      ),
    );

void main() {
  for (final storeUrl in <String?>[null, '']) {
    for (final code in ['en', 'ar', 'ms']) {
      testWidgets(
          'UPDATE with storeUrl=${storeUrl == null ? 'null' : "''"} says it '
          'cannot open the store ($code)', (tester) async {
        final l = await AppLocalizations.delegate.load(Locale(code));
        await tester.pumpWidget(_app(
          Locale(code),
          ReleaseFloorResponse(
              action: 'block', minBuild: 99, storeUrl: storeUrl),
        ));
        await tester.pump();

        await tester.tap(find.text(l.versionGateUpdateCta));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 300));

        expect(find.text(l.versionGateStoreUnavailable), findsOneWidget,
            reason: 'a dead UPDATE button on the block screen strands the user');
      });
    }
  }
}
