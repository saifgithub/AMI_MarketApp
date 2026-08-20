/// CR122 test doubles for the ad-cap store seam.
library;

import 'package:ami_trade/services/ads/ad_frequency_caps.dart';

class MemoryCapStore implements AdCapStore {
  MemoryCapStore([Map<String, String>? seed]) : map = {...?seed};
  final Map<String, String> map;

  @override
  Future<String?> read(String key) async => map[key];

  @override
  Future<void> write(String key, String value) async => map[key] = value;
}

class ThrowingCapStore implements AdCapStore {
  @override
  Future<String?> read(String key) async => throw StateError('disk gone');

  @override
  Future<void> write(String key, String value) async =>
      throw StateError('disk gone');
}
