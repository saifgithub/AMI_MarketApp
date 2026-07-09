/// CR011 (C3) — shared league helpers: tier → colour + display label, and the
/// "Nd Nh" week-countdown formatter. There is no tier-colour helper in the
/// theme, so the mapping lives here for the card + screen to share.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

/// Tier ids come from the backend (`apprentice` → `floor_veteran`).
Color leagueTierColor(String tier) {
  switch (tier) {
    case 'analyst':
      return AmiColors.hexBlue;
    case 'trader':
      return AmiColors.hexCyan;
    case 'senior':
      return AmiColors.hexPurple;
    case 'floor_veteran':
      return AmiColors.hexAmber;
    case 'apprentice':
    default:
      return AmiColors.slate500;
  }
}

String leagueTierLabel(String tier) => tier.replaceAll('_', ' ').toUpperCase();

/// "2D 14H" until the given ISO 8601 instant; empty when past or unparseable.
String leagueRollsIn(String endsAtIso) {
  final ends = DateTime.tryParse(endsAtIso);
  if (ends == null) return '';
  final d = ends.toLocal().difference(DateTime.now());
  if (d.isNegative) return '';
  return '${d.inDays}D ${d.inHours % 24}H';
}
