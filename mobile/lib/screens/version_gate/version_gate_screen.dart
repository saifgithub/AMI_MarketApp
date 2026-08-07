/// CR121 — the client version-gate UI.
///
/// [VersionGateBlockScreen] is a non-dismissible full-screen route: no back
/// gesture, no system-back (`PopScope(canPop: false)`), one primary CTA to
/// the store, and a secondary "check again" for a user who already updated
/// but whose session hasn't re-checked yet. [showVersionGateNagSheet] is
/// the softer counterpart — a dismissible bottom sheet, shown at most once
/// per app session (enforced by `VersionGateController`, not by this file).
///
/// Both render the server's per-raise `headline`/`body` verbatim (CR121:
/// that copy is authored at raise time, not shipped ARB content) under a
/// static chrome title/CTA that IS shipped, translated copy.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/release_floor.dart';
import 'package:ami_trade/state/version_gate_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

Future<void> _openStore(String? url) async {
  if (url == null || url.isEmpty) return;
  final uri = Uri.tryParse(url);
  if (uri == null) return;
  await launchUrl(uri, mode: LaunchMode.externalApplication);
}

class VersionGateBlockScreen extends ConsumerStatefulWidget {
  const VersionGateBlockScreen({super.key, required this.floor});

  final ReleaseFloorResponse floor;

  @override
  ConsumerState<VersionGateBlockScreen> createState() =>
      _VersionGateBlockScreenState();
}

class _VersionGateBlockScreenState
    extends ConsumerState<VersionGateBlockScreen> {
  bool _rechecking = false;

  Future<void> _recheck() async {
    setState(() => _rechecking = true);
    // Fail-open lives in the controller itself — an unreachable server on
    // retry just leaves this screen showing the last-known block, never
    // throws here.
    await ref.read(versionGateControllerProvider.notifier).check();
    if (mounted) setState(() => _rechecking = false);
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final floor = widget.floor;
    return PopScope(
      // Non-dismissible: no back gesture, no system-back. The only ways
      // off this screen are updating (which re-launches the app) or the
      // gate itself re-resolving to "ok"/"nag" on recheck.
      canPop: false,
      child: Scaffold(
        backgroundColor: AmiColors.slate900,
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(AmiSpacing.l),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Icon(Icons.system_update_alt_rounded,
                      color: AmiColors.hexAmber, size: 48),
                  const SizedBox(height: AmiSpacing.m),
                  Text(
                    l.versionGateScreenTitle,
                    textAlign: TextAlign.center,
                    style: AmiTypography.labelMono
                        .copyWith(color: AmiColors.hexAmber),
                  ),
                  const SizedBox(height: AmiSpacing.s),
                  Text(
                    floor.headline ?? l.versionGateScreenTitle,
                    textAlign: TextAlign.center,
                    style: AmiTypography.h2,
                  ),
                  const SizedBox(height: AmiSpacing.s),
                  if (floor.body != null)
                    Text(
                      floor.body!,
                      textAlign: TextAlign.center,
                      style: AmiTypography.bodyLg,
                    ),
                  const SizedBox(height: AmiSpacing.xl),
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AmiColors.hexCyan,
                      foregroundColor: AmiColors.slate900,
                      padding:
                          const EdgeInsets.symmetric(vertical: AmiSpacing.m),
                    ),
                    onPressed: () => _openStore(floor.storeUrl),
                    child: Text(l.versionGateUpdateCta,
                        style: AmiTypography.labelMono
                            .copyWith(color: AmiColors.slate900)),
                  ),
                  const SizedBox(height: AmiSpacing.m),
                  TextButton(
                    onPressed: _rechecking ? null : _recheck,
                    child: _rechecking
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : Text(l.versionGateRetryCta,
                            style: AmiTypography.caption
                                .copyWith(color: AmiColors.textMed)),
                  ),
                  const SizedBox(height: AmiSpacing.s),
                  Text(
                    l.versionGateOfflineRetryHint,
                    textAlign: TextAlign.center,
                    style: AmiTypography.caption
                        .copyWith(color: AmiColors.textLow),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// The softer "nag" band (`min_build <= build < recommended_build`) — a
/// dismissible bottom sheet. Dismissing (either button) marks the session
/// so it doesn't reappear on the next resume this session.
Future<void> showVersionGateNagSheet(
  BuildContext context,
  WidgetRef ref,
  ReleaseFloorResponse floor,
) {
  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: AmiColors.slate800,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
    ),
    builder: (sheetContext) {
      final l = AppLocalizations.of(sheetContext);
      return Padding(
        padding: EdgeInsets.fromLTRB(
          AmiSpacing.l,
          AmiSpacing.l,
          AmiSpacing.l,
          AmiSpacing.xl + MediaQuery.of(sheetContext).viewInsets.bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              floor.headline ?? l.versionGateScreenTitle,
              style: AmiTypography.h3,
            ),
            if (floor.body != null) ...[
              const SizedBox(height: AmiSpacing.s),
              Text(floor.body!, style: AmiTypography.body),
            ],
            const SizedBox(height: AmiSpacing.l),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AmiColors.hexCyan,
                foregroundColor: AmiColors.slate900,
              ),
              onPressed: () => _openStore(floor.storeUrl),
              child: Text(l.versionGateUpdateCta,
                  style:
                      AmiTypography.labelMono.copyWith(color: AmiColors.slate900)),
            ),
            const SizedBox(height: AmiSpacing.s),
            Center(
              child: TextButton(
                onPressed: () {
                  ref.read(versionGateControllerProvider.notifier).dismissNag();
                  Navigator.of(sheetContext).pop();
                },
                child: Text(l.versionGateNagDismissCta,
                    style:
                        AmiTypography.labelMono.copyWith(color: AmiColors.textMed)),
              ),
            ),
          ],
        ),
      );
    },
  );
}
