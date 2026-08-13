/// CR173 slice 2 — YOUR TEAM'S CALLS, opened.
///
/// Carousel card 2 shows two rows; this is the rest of them. Same rows, same
/// renderer ([TeamCallRow]) — the list only adds the PM's reason and the
/// disclosure that a PASS named no level to measure against.
///
/// Each row reopens its own settled Verdict Board through the Journal's
/// existing detail screen, so the destination is CR106's shipped surface rather
/// than a second rendering of a verdict (T-TWICE).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/floor/floor_cards.dart';
import 'package:ami_trade/screens/floor/floor_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class TeamCallsScreen extends ConsumerWidget {
  const TeamCallsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final async = ref.watch(teamCallsProvider);

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            AmiScreenHeader(
              title: l.floorCardCalls,
              titleColor: AmiColors.hexCyan,
              // Every aggregate names its window (CR178's rule): a list capped
              // at 50 that presents itself as "all of them" is wrong by an
              // amount the reader cannot see.
              subtitle: l.floorCallsWindow(kCallsWindow),
              showBack: true,
            ),
            Expanded(
              child: async.when(
                loading: () => const Center(
                    child: CircularProgressIndicator(strokeWidth: 2)),
                // DEF148 — what reaches the user goes through `friendlyError`,
                // never an interpolated exception.
                error: (e, _) => Padding(
                  padding: const EdgeInsets.all(AmiSpacing.l),
                  child: Text(
                    friendlyError(e, action: "read your team's calls"),
                    style: AmiTypography.body,
                  ),
                ),
                data: (calls) => calls.isEmpty
                    ? Padding(
                        padding: const EdgeInsets.all(AmiSpacing.l),
                        child: Text(l.floorCardCallsEmpty,
                            style: AmiTypography.body
                                .copyWith(color: AmiColors.textMed)),
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.all(AmiSpacing.m),
                        itemCount: calls.length,
                        separatorBuilder: (_, __) => const Divider(
                            height: 1, color: AmiColors.slate700),
                        itemBuilder: (_, i) => TeamCallRow(call: calls[i]),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
