/// CR109 slice 2 — the entry confirm sheet (design §4.2, §13.3).
///
/// Entry has no cost (§4.2 — a legal load-bearing choice, not a generosity
/// one: an entry fee is *consideration*, one of the three legs of the
/// gambling test, §15). This sheet shows the stake and — on a player's
/// first entry ever, full text; a chip on every entry after — the §7
/// no-rules disclosure, then a single confirm tap calls
/// `POST /v1/games/enter`.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/games/no_rules_disclosure.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/sheet_insets.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class GamesEntrySheet extends ConsumerStatefulWidget {
  const GamesEntrySheet({super.key, required this.cadence});

  final String cadence;

  static Future<void> show(BuildContext context, {required String cadence}) {
    return showModalBottomSheet<void>(
      context: context,
      backgroundColor: AmiColors.slate800,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => GamesEntrySheet(cadence: cadence),
    );
  }

  @override
  ConsumerState<GamesEntrySheet> createState() => _GamesEntrySheetState();
}

class _GamesEntrySheetState extends ConsumerState<GamesEntrySheet> {
  bool _loadingSeen = true;
  bool _seenBefore = false;
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    gamesDisclosureSeen().then((seen) {
      if (!mounted) return;
      setState(() {
        _seenBefore = seen;
        _loadingSeen = false;
      });
    });
  }

  Future<void> _confirm() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final api = ref.read(apiClientProvider);
      await api.gamesEnter(cadence: widget.cadence);
      await markGamesDisclosureSeen();
      ref.invalidate(gamesRunsProvider);
      ref.invalidate(gamesCadencesProvider);
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      Navigator.of(context).pop();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = friendlyError(e, action: 'enter this field');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Padding(
      padding: EdgeInsets.fromLTRB(
        AmiSpacing.l,
        AmiSpacing.l,
        AmiSpacing.l,
        AmiSpacing.l + sheetBottomInset(MediaQuery.of(context)),
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l.gamesEntrySheetHeading, style: AmiTypography.h3),
            const SizedBox(height: AmiSpacing.xs),
            Text(
              l.gamesEntryStakeLine,
              style: AmiTypography.body.copyWith(color: AmiColors.textLow),
            ),
            const SizedBox(height: AmiSpacing.m),
            if (_loadingSeen)
              const SizedBox(
                height: 24,
                child: Center(
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              )
            else if (_seenBefore)
              const NoRulesDisclosureChip()
            else
              const NoRulesDisclosurePanel(),
            const SizedBox(height: AmiSpacing.m),
            if (_error != null) ...[
              Text(
                _error!,
                style: AmiTypography.caption.copyWith(color: AmiColors.hexRed),
              ),
              const SizedBox(height: AmiSpacing.s),
            ],
            SizedBox(
              width: double.infinity,
              child: HexButton(
                label: (_submitting
                        ? l.gamesEntryConfirming
                        : l.gamesEntryConfirmCta)
                    .toUpperCase(),
                color: AmiColors.hexGreen,
                onPressed: (_submitting || _loadingSeen) ? null : _confirm,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
