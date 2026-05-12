/// A11 — locale state.
///
/// `localeNotifierProvider` exposes the current `Locale?` for MaterialApp.
/// `null` means "follow the system locale" — that's the default; users
/// pick an override from Settings → Language and we persist it via
/// SharedPreferences so the choice survives restarts.
library;

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Locales the app ships strings for at Alpha. English is the only one
/// with a populated ARB today; AR + MS load through the framework but
/// fall back to English for missing keys, so users selecting them today
/// see mostly English text. Translators drop in proper ARBs later.
const supportedLocales = <Locale>[
  Locale('en'),
  Locale('ar'),
  Locale('ms'),
];

const _prefsKey = 'ami_locale_override';


class LocaleNotifier extends StateNotifier<Locale?> {
  LocaleNotifier() : super(null) {
    _hydrate();
  }

  Future<void> _hydrate() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final code = prefs.getString(_prefsKey);
      if (code == null || code.isEmpty) return;
      // Tolerate stored values from older builds that included a country.
      final parts = code.split('_');
      final locale = Locale(parts[0], parts.length > 1 ? parts[1] : null);
      if (supportedLocales.any((l) => l.languageCode == locale.languageCode)) {
        state = locale;
      }
    } catch (_) {
      // Shared prefs is best-effort; fall back to system locale.
    }
  }

  Future<void> setLocale(Locale? locale) async {
    state = locale;
    try {
      final prefs = await SharedPreferences.getInstance();
      if (locale == null) {
        await prefs.remove(_prefsKey);
      } else {
        await prefs.setString(_prefsKey, locale.languageCode);
      }
    } catch (_) {
      // Best-effort persistence.
    }
  }
}


final localeNotifierProvider =
    StateNotifierProvider<LocaleNotifier, Locale?>((ref) {
  return LocaleNotifier();
});


/// Convenience — Flutter's `Locale` doesn't need this on its own, but our
/// Settings screen uses it to label the active choice.
@immutable
class LocaleOption {
  const LocaleOption({
    required this.locale,
    required this.nativeName,
    required this.englishName,
  });
  final Locale? locale; // null → "Follow system"
  final String nativeName;
  final String englishName;
}

const localeOptions = <LocaleOption>[
  LocaleOption(locale: null, nativeName: 'System', englishName: 'Follow system'),
  LocaleOption(locale: Locale('en'), nativeName: 'English', englishName: 'English'),
  LocaleOption(locale: Locale('ar'), nativeName: 'العربية', englishName: 'Arabic'),
  LocaleOption(locale: Locale('ms'), nativeName: 'Bahasa Melayu', englishName: 'Malay'),
];
