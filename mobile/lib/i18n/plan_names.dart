/// DEF494 — the display name of a plan id, so Settings never shows the raw
/// backend id (`floor_pass`) as a value. Known ids resolve through the ARB; an
/// id this build does not know is title-cased rather than shown raw, so a new
/// plan degrades to a readable name instead of a snake_case token.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';

String planDisplayName(AppLocalizations l, String planId) {
  switch (planId) {
    case 'floor_pass':
      return l.planNameFloorPass;
    case 'trial_trader':
      return l.planNameTrialTrader;
    case 'trader':
      return l.upgradePlanTrader;
    case 'floor_manager':
      return l.upgradePlanFloorManager;
  }
  return planId
      .split('_')
      .where((w) => w.isNotEmpty)
      .map((w) => '${w[0].toUpperCase()}${w.substring(1)}')
      .join(' ');
}
