"""Verify the proposed numeric provenance boundary with ISS003-style cases."""

from __future__ import annotations

import unittest

from provenance_demo import (
    AtomPart,
    PublishRejected,
    TextPart,
    example_registry,
    publish,
)


class PublishTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = example_registry()

    def test_sheet_value_is_rendered_by_server_without_an_ami_correction(self):
        result = publish(
            [
                TextPart("The cash position is "),
                AtomPart("sheet.fcf_ttm"),
                TextPart("."),
            ],
            self.registry,
        )
        self.assertEqual(
            result.text,
            "The cash position is TTM FCF: -RM15,433M.",
        )
        self.assertEqual(result.spans[0].atom_id, "sheet.fcf_ttm")
        self.assertNotIn("AMI checked", result.text)

    def test_round_three_values_can_be_published_from_each_source_class(self):
        cases = {
            "mandate.single_name_cap": "The limit is single-name cap: 1.0%.",
            "derived.atr_stop": "The exit uses ATR stop distance: 1.0x ATR(14), RM0.145.",
            "debate.bear.cap_quote": "The Bear cited quoted single-name cap: 1.0%.",
        }
        for atom_id, expected in cases.items():
            with self.subTest(atom_id=atom_id):
                result = publish(
                    [TextPart("The limit is " if "cap" in atom_id else "The exit uses "),
                     AtomPart(atom_id),
                     TextPart(".")],
                    self.registry,
                )
                self.assertEqual(
                    result.text,
                    expected if atom_id != "debate.bear.cap_quote"
                    else "The limit is quoted single-name cap: 1.0%.",
                )

    def test_fabricated_or_altered_raw_figure_is_rejected(self):
        invalid = (
            "TTM FCF is RM5,273M.",
            "1.0% is the mandate cap.",
            "The stop is 2.0x ATR(14), RM0.290.",
            "FCF yield is -12.6%.",
            "FY2024 FCF was RM27,986M.",
        )
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(PublishRejected):
                publish([TextPart(text)], self.registry)

    def test_word_spelled_and_unicode_numerals_are_rejected(self):
        invalid = (
            "The cap is one percent.",
            "Use twelve point five times earnings.",
            "The cap is ١.٠ percent.",
            "The position has Ⅻ units.",
        )
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(PublishRejected):
                publish([TextPart(text)], self.registry)

    def test_unknown_or_market_missing_atom_is_rejected(self):
        with self.assertRaisesRegex(PublishRejected, "not available"):
            publish([AtomPart("sheet.us_filings.quarter")], self.registry)

    def test_non_numeric_unseen_phrasing_reaches_the_renderer(self):
        result = publish(
            [
                TextPart("A fresh phrasing still delegates the fact to "),
                AtomPart("sheet.fcf_yield"),
                TextPart(", so wording cannot rewrite the source value."),
            ],
            self.registry,
        )
        self.assertIn("FCF yield: -12.6%", result.text)


if __name__ == "__main__":
    unittest.main()

