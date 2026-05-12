/// TermRegistry — resolves `<Term id="…"/>` references against a bundled
/// glossary asset. Loaded once from `assets/glossary/terms.<locale>.json`
/// at first lookup, then served synchronously from memory.
///
/// V1 reads bundled assets only — the backend `/v1/glossary/{locale}`
/// route exists for the catalogue screen and future hot-swaps but the
/// inline tooltip path stays offline-first so a lesson page is never
/// blocked on a network roundtrip per inline term.
///
/// Locale fallback: requested → en → null. The Term widget renders the
/// id as plain bold text when the registry returns null so a typo or
/// not-yet-translated id never crashes the reader.
library;

import 'dart:convert';

import 'package:ami_trade/models/glossary.dart';
import 'package:flutter/services.dart' show rootBundle;

class TermRegistry {
  TermRegistry._();

  static final TermRegistry instance = TermRegistry._();

  final Map<String, Map<String, GlossaryEntry>> _byLocale = {};
  final Map<String, Future<void>> _loading = {};

  /// Eager-load a locale. Safe to call multiple times; second and later
  /// calls return the in-flight or completed future.
  Future<void> load({String locale = 'en'}) {
    final cached = _loading[locale];
    if (cached != null) return cached;
    final fut = _loadLocale(locale);
    _loading[locale] = fut;
    return fut;
  }

  Future<void> _loadLocale(String locale) async {
    try {
      final raw = await rootBundle
          .loadString('assets/glossary/terms.$locale.json');
      final List<dynamic> list = json.decode(raw) as List<dynamic>;
      final map = <String, GlossaryEntry>{};
      for (final item in list) {
        final entry = GlossaryEntry.fromJson(item as Map<String, dynamic>);
        map[entry.id] = entry;
      }
      _byLocale[locale] = map;
    } catch (_) {
      _byLocale[locale] = const {};
    }
  }

  /// Synchronous lookup. Returns null when no asset for the locale is
  /// loaded yet OR when the id is unknown in both the requested locale
  /// and the English fallback. Callers should treat null as "render
  /// plain text" — never as an error.
  GlossaryEntry? get(String id, {String locale = 'en'}) {
    final bucket = _byLocale[locale];
    final hit = bucket?[id];
    if (hit != null) return hit;
    if (locale != 'en') {
      final fallback = _byLocale['en'];
      final fhit = fallback?[id];
      if (fhit != null) return fhit;
    }
    return null;
  }

  /// True once the requested locale (or English fallback) has been
  /// loaded into memory. Useful for widgets that want to defer a tap
  /// handler until the registry is ready, though in practice the EN
  /// asset loads in <50ms on a cold start.
  bool isReady({String locale = 'en'}) =>
      _byLocale.containsKey(locale) || _byLocale.containsKey('en');
}
