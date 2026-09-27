/// CR244 — Riverpod state for the Company Review screen.
///
/// Two independent fetches, both family-keyed by ticker and `autoDispose`
/// (the screen is a leaf, not persistent app state): the main profile
/// (overview/financials/filings/ownership, backs 5 of the 6 tabs) and the
/// insider feed (Form 3/4/5, backs the Insider tab). Kept separate rather
/// than joined into one future because the insider endpoint is the slow one
/// (CR244.md: up to 25 Form 4 XML fetches under SEC rate etiquette) — tying
/// its latency to the other four tabs would make Overview wait on Insider
/// for no reason.
library;

import 'package:ami_trade/models/company_profile.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final companyProfileProvider =
    FutureProvider.autoDispose.family<CompanyProfile, String>(
        (ref, ticker) async {
  final api = ref.watch(apiClientProvider);
  return api.companyProfile(ticker);
});

final insiderActivityProvider =
    FutureProvider.autoDispose.family<InsiderActivity, String>(
        (ref, ticker) async {
  final api = ref.watch(apiClientProvider);
  return api.insiderActivity(ticker);
});
