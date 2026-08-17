/// DEF306 — the build says which build it is.
///
/// Tested as a pure function rather than through the widget, because
/// `kGamesEnabled` is `bool.fromEnvironment` and therefore const-folded: a
/// widget test can only ever observe the one value the test binary was compiled
/// with, so a test that rendered the chip would pin exactly half the behaviour
/// and look like it pinned all of it.
library;

import 'package:ami_trade/features/build_identity.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('a store binary carries no marker at all', () {
    // Not cosmetic: the marker must never appear in a binary that does not
    // have the feature, or it advertises to App Review (2.3.1) something the
    // app cannot show.
    expect(buildFeatureFlags(gamesEnabled: false), isEmpty);
    expect(buildIdentityLabel('0.1.0+94', gamesEnabled: false),
        'AMI Trade v0.1.0+94');
  });

  test('a games build says so, next to the version', () {
    expect(buildIdentityLabel('0.1.0+94', gamesEnabled: true),
        'AMI Trade v0.1.0+94 · GAMES');
  });

  test('the two builds of one version are distinguishable on screen', () {
    // The whole defect in one assertion: `0.1.0+94` existed as two different
    // Android apps and every human-readable surface called them the same
    // thing. Whatever the label format becomes, this must stay true.
    expect(
      buildIdentityLabel('0.1.0+94', gamesEnabled: true),
      isNot(buildIdentityLabel('0.1.0+94', gamesEnabled: false)),
    );
  });
}
