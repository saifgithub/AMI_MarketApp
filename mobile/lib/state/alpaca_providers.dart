/// Riverpod state for the Alpaca paper trading link (AT:R45).
///
/// alpacaStatusProvider — whether the current user has a linked Alpaca account.
///   Re-fetched by invalidating this provider (e.g. after link or unlink).
///
/// alpacaPortfolioProvider / alpacaPositionsProvider — paper account data.
///   Only useful when alpacaStatusProvider resolves to linked==true.
library;

import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final alpacaStatusProvider = FutureProvider.autoDispose<AlpacaStatus>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.alpacaStatus();
});

final alpacaPortfolioProvider = FutureProvider.autoDispose<AlpacaPortfolio>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.alpacaPortfolio();
});

final alpacaPositionsProvider = FutureProvider.autoDispose<List<AlpacaPosition>>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.alpacaPositions();
});
