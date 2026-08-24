/// CR172 §9 (D5) — the four option limits as a Settings surface.
///
/// Two properties carry this file.
///
/// `they are hidden unless the mandate permits derivatives` is the one that
/// affects every user in the app today: `derivatives_allowed` is false on all
/// 42 live mandates, so four controls for a capability nobody has would be
/// noise added to the one screen where noise costs the most.
///
/// `an unset option limit means NO CAP, not "follow your profile"` is the one
/// that would be a lie if it were wrong. The seven CR129 limits are
/// preset-linked: leaving one blank still binds a real, server-resolved
/// number. These four are not — leaving one blank means nothing is enforcing
/// it — and rendering them with the CR129 copy would tell a user they are
/// protected by a limit that does not exist.
library;

import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/settings/risk_limits_section.dart';
import 'package:flutter_test/flutter_test.dart';

UserMandate _mandate({
  bool derivatives = false,
  double? premiumPct,
  double? notionalPct,
  double? assignmentPct,
  int? minDte,
}) =>
    UserMandate.fromJson({
      'user_id': 'u1',
      'version': 1,
      'display_name': 'Trader',
      'locale': 'en',
      'timezone': 'UTC',
      'primary_goal': 'long_term_wealth',
      'horizon': 'long',
      'path': 'long_horizon',
      'risk_score': 3,
      'risk_components': {
        'drawdown_response': 3,
        'regret_asymmetry': 0,
        'concentration_tolerance': 3,
      },
      'max_drawdown_pct': 30,
      'learning_style': 'quick',
      'plan': 'trader',
      'credit_balance': 75,
      'compliance': {'derivatives_allowed': derivatives},
      if (premiumPct != null) 'max_option_premium_pct': premiumPct,
      if (notionalPct != null) 'max_option_notional_pct': notionalPct,
      if (assignmentPct != null) 'max_assignment_exposure_pct': assignmentPct,
      if (minDte != null) 'min_days_to_expiry': minDte,
    });

void main() {
  group('the registry', () {
    test('the four option limits are declared apart from the CR129 seven', () {
      expect(kRiskLimitFields.length, 7);
      expect(kOptionLimitFields.map((c) => c.key), [
        'max_option_premium_pct',
        'max_option_notional_pct',
        'max_assignment_exposure_pct',
        'min_days_to_expiry',
      ]);
      // No overlap: folding them together would make every "Custom" and
      // preset-match computation over the seven answer a different question.
      final seven = kRiskLimitFields.map((c) => c.key).toSet();
      expect(kOptionLimitFields.any((c) => seven.contains(c.key)), isFalse);
    });

    test('an unset option limit means NO CAP, not "follow your profile"', () {
      // THE distinction. presetLinked drives the copy: true renders "following
      // your risk profile" — which for these would claim a protection that is
      // not there, because they deliberately do not resolve from risk_score.
      expect(kOptionLimitFields.every((c) => !c.presetLinked), isTrue);
      expect(kRiskLimitFields.every((c) => c.presetLinked), isTrue);
    });

    test('a SHORTER minimum expiry is the looser setting', () {
      final dte = kOptionLimitFields
          .firstWhere((c) => c.key == 'min_days_to_expiry');
      expect(dte.higherIsLooser, isFalse);
      expect(dte.kind, LimitKind.days);
      // Every other option limit runs the usual direction.
      expect(
        kOptionLimitFields
            .where((c) => c.key != 'min_days_to_expiry')
            .every((c) => c.higherIsLooser),
        isTrue,
      );
    });
  });

  group('reading the mandate', () {
    test('each option limit is read from its own server key', () {
      final m = _mandate(
        derivatives: true, premiumPct: 5.0, notionalPct: 120.0,
        assignmentPct: 25.0, minDte: 7,
      );
      expect(riskLimitServerValue(m, 'max_option_premium_pct'), 5.0);
      expect(riskLimitServerValue(m, 'max_option_notional_pct'), 120.0);
      expect(riskLimitServerValue(m, 'max_assignment_exposure_pct'), 25.0);
      expect(riskLimitServerValue(m, 'min_days_to_expiry'), 7);
    });

    test('an absent limit reads null, never zero', () {
      // A 0 would be a real, binding cap meaning "block everything" — the
      // opposite of "no cap set".
      final m = _mandate(derivatives: true);
      for (final c in kOptionLimitFields) {
        expect(riskLimitServerValue(m, c.key), isNull, reason: c.key);
      }
    });

    test('derivatives_allowed is read, and defaults to false', () {
      expect(_mandate().compliance.derivativesAllowed, isFalse);
      expect(_mandate(derivatives: true).compliance.derivativesAllowed, isTrue);
      // An older backend that sends no such key must not read as permitted.
      final legacy = ComplianceFlags.fromJson(const {});
      expect(legacy.derivativesAllowed, isFalse);
    });
  });

  group('the disclosure classifier', () {
    test('raising a premium cap is disclosed as looser', () {
      final cfg = kOptionLimitFields.first;
      expect(classifyLimitEdit(cfg, oldValue: 5, newValue: 10),
          LimitDisclosure.looser);
    });

    test('SHORTENING the minimum expiry is the looser direction', () {
      // The trap: numerically smaller, but it admits shorter-dated options.
      final cfg = kOptionLimitFields
          .firstWhere((c) => c.key == 'min_days_to_expiry');
      expect(classifyLimitEdit(cfg, oldValue: 30, newValue: 7),
          LimitDisclosure.looser);
      expect(classifyLimitEdit(cfg, oldValue: 7, newValue: 30),
          isNot(LimitDisclosure.looser));
    });

    test('clearing a non-preset limit reads as off, not back-to-profile', () {
      final cfg = kOptionLimitFields.first;
      expect(classifyLimitEdit(cfg, oldValue: 5, newValue: null),
          LimitDisclosure.off);
    });
  });
}
