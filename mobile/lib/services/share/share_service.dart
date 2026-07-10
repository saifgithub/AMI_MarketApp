/// CR012 (C4) — ShareService: rasterise a [ShareCard] offscreen and hand the
/// PNG to the OS share sheet.
///
/// The card is inserted into the root [Overlay] far off-screen (so nothing
/// flashes on the visible route), given a frame to lay out + paint, captured
/// via its [RepaintBoundary], written to a temp file, and shared through
/// `share_plus`. All four entry points (verdict / streak / unlock / promotion)
/// resolve their l10n strings here and pass fully-formed [ShareCardData] to the
/// context-free card.
library;

import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/share/share_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

abstract final class ShareService {
  /// The Room's verdict (ticker + stance + reasoning; no prices/P&L).
  static Future<void> shareVerdict(
    BuildContext context, {
    required String ticker,
    required String stanceLabel,
    required bool isApprove,
    required String reason,
  }) async {
    final l = AppLocalizations.of(context);
    await _capture(
      context,
      VerdictShareData(
        kicker: l.shareCardVerdictKicker,
        accent: isApprove ? AmiColors.hexGreen : AmiColors.hexAmber,
        ticker: ticker,
        stanceLabel: stanceLabel,
        reason: reason,
      ),
      'verdict',
    );
  }

  /// A streak milestone (day count).
  static Future<void> shareStreak(
    BuildContext context, {
    required int days,
    required Color accent,
  }) async {
    final l = AppLocalizations.of(context);
    await _capture(
      context,
      StreakShareData(
        kicker: l.shareCardStreakUnit,
        accent: accent,
        days: days,
        unit: l.shareCardStreakUnit,
      ),
      'streak',
    );
  }

  /// An agent unlock (hex + name).
  static Future<void> shareUnlock(
    BuildContext context, {
    required String agentName,
    required String abbreviation,
    required Color accent,
  }) async {
    final l = AppLocalizations.of(context);
    await _capture(
      context,
      UnlockShareData(
        kicker: l.shareCardUnlockKicker,
        accent: accent,
        agentName: agentName,
        abbreviation: abbreviation,
      ),
      'unlock',
    );
  }

  /// A league standing / promotion (tier + rank + week).
  static Future<void> sharePromotion(
    BuildContext context, {
    required String tierLabel,
    required Color tierColor,
    required String week,
    required int rank,
    String? outcomeLabel,
  }) async {
    final l = AppLocalizations.of(context);
    await _capture(
      context,
      PromotionShareData(
        kicker: l.shareCardPromotedKicker,
        accent: tierColor,
        tierLabel: tierLabel,
        week: week,
        rank: rank,
        outcomeLabel: outcomeLabel,
      ),
      'promotion',
    );
  }

  static Future<void> _capture(
    BuildContext context,
    ShareCardData data,
    String name,
  ) async {
    final l = AppLocalizations.of(context);
    // Anchor the iPad/macOS share popover to the tapped widget (ignored on
    // phones). Read the box BEFORE any await — the context may unmount after.
    final box = context.findRenderObject() as RenderBox?;
    final origin = (box != null && box.hasSize)
        ? box.localToGlobal(Offset.zero) & box.size
        : null;

    final bytes = await _rasterize(
      context,
      ShareCard(data: data, disclaimer: l.disclaimerShort),
    );
    if (bytes == null) return;

    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/ami_share_$name.png');
    await file.writeAsBytes(bytes);

    await Share.shareXFiles(
      [XFile(file.path, mimeType: 'image/png')],
      text: l.shareCaption,
      sharePositionOrigin: origin,
    );
  }

  static Future<Uint8List?> _rasterize(
    BuildContext context,
    Widget card,
  ) async {
    final overlay = Overlay.maybeOf(context, rootOverlay: true);
    if (overlay == null) return null;
    final mq = MediaQuery.of(context);
    // Follow the app's locale direction (O1) so the card lays out correctly
    // when AR (RTL) ships; falls back to LTR outside a Directionality scope.
    final dir = Directionality.maybeOf(context) ?? TextDirection.ltr;
    final key = GlobalKey();

    final entry = OverlayEntry(
      builder: (_) => Positioned(
        // Fully off the visible surface; a Stack/Overlay paints it anyway
        // (no viewport culling), so toImage still captures the layer.
        left: -kShareCardSize.width - 200,
        top: -kShareCardSize.height - 200,
        child: RepaintBoundary(
          key: key,
          child: MediaQuery(
            data: mq.copyWith(textScaler: const TextScaler.linear(1)),
            child: Directionality(
              textDirection: dir,
              child: card,
            ),
          ),
        ),
      ),
    );

    overlay.insert(entry);
    try {
      // One pipeline frame + a short settle so the hex-mesh SVG and Plex fonts
      // are painted into the boundary before we rasterise.
      await WidgetsBinding.instance.endOfFrame;
      await Future<void>.delayed(const Duration(milliseconds: 60));
      final boundary =
          key.currentContext?.findRenderObject() as RenderRepaintBoundary?;
      if (boundary == null) return null;
      final image = await boundary.toImage(pixelRatio: 1);
      final data = await image.toByteData(format: ui.ImageByteFormat.png);
      image.dispose();
      return data?.buffer.asUint8List();
    } finally {
      entry.remove();
    }
  }
}
