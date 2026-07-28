// DEF137 — every locale's ARB must carry exactly the template's key set.
//
// Flutter's delegate falls back to the template locale *per key*, so a missing
// translation renders English mid-paragraph instead of failing. That is the
// silent degrade CR040 exists to prevent, and it is why 24 keys accumulated
// across five separate CRs before anyone counted. Nothing in the build compared
// key sets — `flutter gen-l10n` is happy with a short file by design.
//
// The translation half of DEF137 is already delivered (7751ff5). This is the
// other half: without it, translating today's set only resets the counter.
//
// Locales are DISCOVERED by globbing `lib/l10n/app_*.arb`, not listed here. A
// hard-coded list is the allowlist-instead-of-invariant shape that has produced
// repeated findings in this codebase — it would pass happily the day someone
// adds `app_fr.arb`, which is exactly when the guard needs to bite.

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

const _arbDir = 'lib/l10n';
const _templateFile = 'app_en.arb';

/// ARB reserves the `@` prefix for metadata (`@@locale`, `@keyName`).
/// Only the unprefixed entries are user-visible strings.
Set<String> _messageKeys(Map<String, dynamic> arb) =>
    arb.keys.where((k) => !k.startsWith('@')).toSet();

/// The placeholder names the TEMPLATE declares for `key`, from its `@key`
/// metadata.
///
/// Read from the declaration rather than scraped out of the string with a
/// regex: an ICU plural body (`{days, plural, =1{1 day} other{{days} days}}`)
/// contains braces that are branch selectors, not placeholders, and a scraper
/// reports `1` as a missing argument. `test_every_braced_string_declares_its_
/// placeholders` below keeps this source authoritative.
Set<String> _declaredPlaceholders(Map<String, dynamic> arb, String key) {
  final meta = arb['@$key'];
  if (meta is! Map) return const {};
  final ph = meta['placeholders'];
  if (ph is! Map) return const {};
  return ph.keys.map((k) => k.toString()).toSet();
}

/// Does `value` actually reference `name` as an ICU argument?
/// Matches `{name}` and `{name,` (the plural/select form), and deliberately
/// does not match a bare `name` in prose.
bool _references(String value, String name) =>
    RegExp('\\{\\s*${RegExp.escape(name)}\\s*[,}]').hasMatch(value);

Map<String, dynamic> _load(File f) =>
    jsonDecode(f.readAsStringSync()) as Map<String, dynamic>;

List<File> _localeFiles() {
  final dir = Directory(_arbDir);
  // Not `expect` — this runs at load time, outside any test body.
  if (!dir.existsSync()) {
    throw StateError('ARB directory $_arbDir not found — run from mobile/');
  }
  return dir
      .listSync()
      .whereType<File>()
      .where((f) => RegExp(r'app_\w+\.arb$').hasMatch(f.path))
      .where((f) => !f.path.endsWith(_templateFile))
      .toList()
    ..sort((a, b) => a.path.compareTo(b.path));
}

void main() {
  final template = _load(File('$_arbDir/$_templateFile'));
  final templateKeys = _messageKeys(template);
  final localeFiles = _localeFiles();

  test('the guard has locales to check and a non-trivial template', () {
    // A parity test over an empty set is green for the wrong reason.
    expect(localeFiles, isNotEmpty,
        reason: 'no non-template ARB files found — the parity checks below '
            'would pass vacuously');
    expect(templateKeys.length, greaterThan(400),
        reason: 'template has only ${templateKeys.length} keys; if the template '
            'shrank, parity below is trivially satisfiable');
  });

  test('every braced template string declares its placeholders', () {
    // The placeholder check above reads the `@key` declaration. If a new
    // string interpolates without declaring, that check silently skips it —
    // the guard narrows without anyone noticing. Measured at 72 declaring
    // keys and 0 undeclared when this was written.
    final undeclared = <String>[];
    for (final key in templateKeys) {
      final value = template[key];
      if (value is! String || !value.contains('{')) continue;
      if (_declaredPlaceholders(template, key).isEmpty) undeclared.add(key);
    }
    expect(undeclared, isEmpty,
        reason: '${undeclared.length} template string(s) interpolate but '
            'declare no placeholders in their @key metadata, so the parity '
            'check below cannot see them: $undeclared');
  });

  for (final file in localeFiles) {
    final name = file.uri.pathSegments.last;
    final arb = _load(file);
    final keys = _messageKeys(arb);

    test('$name has no keys missing against $_templateFile', () {
      final missing = templateKeys.difference(keys).toList()..sort();
      expect(missing, isEmpty,
          reason: '${missing.length} key(s) exist only in $_templateFile, so '
              'this locale renders English for them inside an otherwise '
              'translated screen (DEF137). Add them to $name — or, if a string '
              'genuinely must not be translated, remove it from the template '
              'too. Missing: $missing');
    });

    test('$name has no keys the template does not define', () {
      final extra = keys.difference(templateKeys).toList()..sort();
      expect(extra, isEmpty,
          reason: '${extra.length} key(s) in $name are absent from '
              '$_templateFile — dead strings, or a key renamed on one side '
              'only. Extra: $extra');
    });

    test('$name preserves every placeholder its template string declares', () {
      // A translation that drops `{sector}` compiles and then renders a
      // literal brace or throws at runtime. DEF137 named this risk directly:
      // `portfolioSectorBreach` interpolates three placeholders whose order is
      // not safe to assume under RTL.
      final broken = <String>[];
      for (final key in templateKeys.intersection(keys)) {
        final en = template[key];
        final tr = arb[key];
        if (en is! String || tr is! String) continue;
        for (final p in _declaredPlaceholders(template, key)) {
          if (_references(en, p) && !_references(tr, p)) {
            broken.add('$key: template uses {$p}, translation does not');
          }
        }
      }
      expect(broken, isEmpty,
          reason: 'placeholder loss in $name — the string will render a '
              'literal brace or fail at runtime:\n${broken.join('\n')}');
    });

    test('$name keeps the ICU plural form where the template has one', () {
      // Arabic has six plural categories against English's two, so a
      // translator handed only the rendered English cannot reconstruct this.
      // Assert the form survived, not which categories were used.
      final flattened = <String>[];
      for (final key in templateKeys.intersection(keys)) {
        final en = template[key];
        final tr = arb[key];
        if (en is! String || tr is! String) continue;
        if (en.contains(', plural,') && !tr.contains(', plural,')) {
          flattened.add(key);
        }
      }
      expect(flattened, isEmpty,
          reason: 'plural form lost in $name for $flattened — the string will '
              'read wrong for at least one count. Arabic needs six categories '
              '(zero/one/two/few/many/other), not the =1/other shortcut.');
    });
  }
}
