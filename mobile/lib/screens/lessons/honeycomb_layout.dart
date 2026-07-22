/// Honeycomb packing for the Lessons landing cluster (DEF082).
///
/// The old cluster hardcoded seven `Offset`s and *iterated that map*, using the
/// API response only as a filter — so every backend track without a hardcoded
/// position was silently dropped. 64 lessons across 5 tracks were dark for
/// months. This file exists so the layout is a function of *how many tracks the
/// API served*, never of a literal written months ago.
///
/// Shape: three columns of flat-top hexes, the centre column one taller than
/// the sides — 4/5/4 = 13 at today's corpus, the same comb the marketing site
/// uses for the 13 agents. Slots are filled in a fixed order (left column top
/// to bottom, then centre, then right), so a track that is registered but
/// unauthored empties the *last* slot instead of holing the middle.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/painting.dart' show Offset;

/// Canonical slot order. Position is deliberately stable per track: the palette
/// is only distinct *at the seams* (see `_trackColor` in `lessons_screen.dart`),
/// so re-sorting by lesson count or alphabetically would let near-identical
/// colours land adjacent and silently undo the separation. `decision_evaluation`
/// is last because it is registered with zero lessons until CR062 lands.
const honeycombTrackOrder = [
  'technical_analysis',
  'sentiment_behaviour',
  'news_macro',
  'ethics_integrity',
  'risk_portfolio',
  'economics_macro',
  'foundations',
  'islamic_finance',
  'quant_methods',
  'fundamentals_analysis',
  'asset_classes',
  'edge_process',
  'decision_evaluation',
];

/// One colour per track, solved together with [honeycombTrackOrder]: the
/// objective was to maximise the *minimum* OKLab distance over the comb's 26
/// adjacent pairs, so the colour reads as the boundary between cells. Every
/// seam clears 0.32, against 0.18 for the shipped palette's own closest pair
/// (hexPink/hexRed). Order and colour must therefore change together — re-sort
/// the list alone and near-identical colours can land adjacent.
const honeycombTrackColor = {
  'foundations': AmiColors.hexBlue,
  'fundamentals_analysis': AmiColors.hexCyan,
  'technical_analysis': AmiColors.hexPurple,
  'news_macro': AmiColors.hexAmber,
  'sentiment_behaviour': AmiColors.hexPink,
  'risk_portfolio': AmiColors.hexRed,
  'edge_process': AmiColors.hexGreen,
  'asset_classes': AmiColors.hexOrange500,
  'economics_macro': AmiColors.hexLime400,
  'quant_methods': AmiColors.hexGreen400,
  'ethics_integrity': AmiColors.hexIndigo600,
  'islamic_finance': AmiColors.hexFuchsia500,
  'decision_evaluation': AmiColors.hexRose400,
};

const honeycombTrackLabel = {
  'foundations': 'FOUNDATIONS',
  'fundamentals_analysis': 'FUNDAMENTALS',
  'technical_analysis': 'TECHNICAL',
  'news_macro': 'NEWS & MACRO',
  'sentiment_behaviour': 'SENTIMENT',
  'risk_portfolio': 'RISK',
  'edge_process': 'EDGE',
  'asset_classes': 'ASSET CLASSES',
  'economics_macro': 'ECONOMICS',
  'quant_methods': 'QUANT',
  'ethics_integrity': 'ETHICS',
  'islamic_finance': 'ISLAMIC FINANCE',
  'decision_evaluation': 'EVALUATION',
};

/// Fallback for a track this build has never heard of. Cycled by slot so two
/// unknown tracks never come out the same colour, and never transparent — a new
/// backend taxonomy must arrive *loudly* rather than vanish, which is the
/// entire lesson of DEF082.
const honeycombFallbackColors = [
  AmiColors.hexBlue,
  AmiColors.hexAmber,
  AmiColors.hexGreen,
  AmiColors.hexPink,
];

/// Height of the centre column for [n] cells. Sides hold one fewer each, so the
/// comb holds `3 * centre - 2` slots — the smallest that fits [n].
int honeycombCentreCount(int n) {
  if (n <= 0) return 0;
  final c = ((n + 2) / 3).ceil();
  return c < 2 ? 2 : c;
}

/// Top-left origins for the first [n] slots, in fill order, for a hex of
/// [hexW] x [hexH]. Columns sit at x = 0, ¾W, 1½W; side columns are offset half
/// a hex down so every neighbour shares a full edge.
List<Offset> honeycombSlots(int n, double hexW, double hexH) {
  final centre = honeycombCentreCount(n);
  final sides = centre - 1;
  final out = <Offset>[];
  for (var r = 0; r < sides; r++) {
    out.add(Offset(0, (0.5 + r) * hexH));
  }
  for (var r = 0; r < centre; r++) {
    out.add(Offset(hexW * 0.75, r * hexH));
  }
  for (var r = 0; r < sides; r++) {
    out.add(Offset(hexW * 1.5, (0.5 + r) * hexH));
  }
  return out.take(n).toList();
}

/// Cluster width is always 2.5 hexes (three columns overlapping by a quarter).
const honeycombWidthInHexes = 2.5;

/// Hex width as a fraction of the available width. The 7-hex flower used 0.4
/// (2.5 hexes filling the row edge to edge); at five rows that reads far too
/// heavy and overruns the viewport, so the comb is scaled down and centred.
/// 0.30 puts the whole 13-facet cluster on one screen with no scroll. This is
/// the single number to turn if the cells want to be smaller still.
const honeycombHexWidthFraction = 0.30;

/// Total height for [n] cells, in hexes — the centre column's span.
int honeycombHeightInHexes(int n) => honeycombCentreCount(n);

/// Served track ids in slot order: the known taxonomy first, in
/// [honeycombTrackOrder], then anything the backend added that this build has
/// never heard of, alphabetically. Every served id comes back exactly once —
/// that total is what the DEF082 guard asserts against.
List<String> orderTracksForHoneycomb(Iterable<String> served) {
  final remaining = served.toSet();
  final out = <String>[];
  for (final id in honeycombTrackOrder) {
    if (remaining.remove(id)) out.add(id);
  }
  final rest = remaining.toList()..sort();
  return [...out, ...rest];
}
