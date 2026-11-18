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
library;

import 'dart:io';

import 'package:ami_trade/models/account.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
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
