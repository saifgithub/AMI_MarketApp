/// Providers behind Settings > Delete account / Export my data (CR276, CR267
/// WP-30).
///
/// `accountPolicyProvider` reads what the server does after the restore window
/// so the confirm dialog states it truthfully. If the call fails the dialog
/// uses [AccountPolicy.fallback] (Beta: delete, 30 days) and logs the failure,
/// because blocking an App-Store-mandated deletion button on a policy fetch
/// would be the worse failure.
///
/// `accountExportSinkProvider` is the "hand the file to the user" step —
/// written to the temp dir and given to the OS share sheet (save to Files,
/// Drive, mail). It is a provider so widget tests can replace it.
///
/// `accountExportSaverProvider` (DEF524) keeps the file ON the phone. On
/// Android it asks MainActivity to open the system Save dialog (Storage Access
/// Framework `ACTION_CREATE_DOCUMENT`) because a phone without a Files app
/// otherwise only offers share targets that send the file elsewhere. iOS has no
/// such gap — its share sheet offers Save to Files — so there the screen skips
/// the Save/Share choice and goes straight to the share sheet.
library;

import 'dart:io';

import 'package:ami_trade/models/account.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

final accountPolicyProvider = FutureProvider.autoDispose<AccountPolicy>((ref) async {
  try {
    return await ref.read(apiClientProvider).accountPolicy();
  } catch (e) {
    debugPrint('accountPolicy fetch failed, using Beta default: $e');
    return AccountPolicy.fallback;
  }
});

typedef AccountExportSink = Future<void> Function(Uint8List bytes, String filename);

Future<void> _shareExportFile(Uint8List bytes, String filename) async {
  final dir = await getTemporaryDirectory();
  final file = File('${dir.path}/$filename');
  await file.writeAsBytes(bytes, flush: true);
  await Share.shareXFiles(
    [XFile(file.path, mimeType: 'application/json')],
    subject: filename,
  );
}

final accountExportSinkProvider =
    Provider<AccountExportSink>((ref) => _shareExportFile);

const accountExportSaveChannel =
    MethodChannel('ai.agenticmarketintel.ami_trade/export_save');

/// Returns the saved file's display name, or null when the user cancelled the
/// Save dialog. Throws when the write failed.
typedef AccountExportSaver = Future<String?> Function(
    Uint8List bytes, String filename);

Future<String?> _saveExportFile(Uint8List bytes, String filename) {
  return accountExportSaveChannel.invokeMethod<String>('saveFile', {
    'name': filename,
    'mime': 'application/json',
    'bytes': bytes,
  });
}

final accountExportSaverProvider =
    Provider<AccountExportSaver>((ref) => _saveExportFile);

bool get accountExportOffersSave =>
    defaultTargetPlatform == TargetPlatform.android;
