"""Bursa device cases that need an AMI_BURSA=true build (UAT-SIM-037, UAT-ROOM-034,
UAT-WATCH-017, UAT-JRNL-012, and CR283's UAT-FLOOR-013 / UAT-FLOOR-014).

Alpha's backend has had MARKET_BURSA_ENABLED on since 2026-11-24, but store builds
keep AMI_BURSA off; only internal build 0.1.0+130 and later (TestFlight internal,
Play internal) has it on. There is no Appium journey for these yet, so each
test below SKIPS with its reason: a skip is recorded as skipped and never counts as
evidence, so the cases read "not passing" until someone runs the case's steps from
qa/uat/UAT_SCRIPT.md on build 130 and records the result (`ledger.py record`), or
until a real driver replaces the skip. They exist so the catalogue guard can see
that every active device case has an executor of record, not to pretend coverage.
"""

import pytest

_WHY = (
    "no Appium journey yet: run {case} by hand on build 0.1.0+130 or later "
    "(AMI_BURSA on) against Alpha (Bursa on) and record the result"
)


@pytest.mark.uat("UAT-SIM-037")
def test_bursa_board_lot_fill_in_the_myr_book():
    pytest.skip(_WHY.format(case="UAT-SIM-037"))


@pytest.mark.uat("UAT-ROOM-034")
@pytest.mark.llm
def test_bursa_room_reads_rm_and_names_unavailable_inputs():
    pytest.skip(_WHY.format(case="UAT-ROOM-034"))


@pytest.mark.uat("UAT-WATCH-017")
def test_bursa_price_alert_takes_its_price_in_rm():
    pytest.skip(_WHY.format(case="UAT-WATCH-017"))


@pytest.mark.uat("UAT-JRNL-012")
def test_bursa_closed_trade_journal_entry_reads_in_rm():
    pytest.skip(_WHY.format(case="UAT-JRNL-012"))


@pytest.mark.uat("UAT-FLOOR-013")
def test_bursa_floor_chip_and_name_resolves_to_the_active_market():
    pytest.skip(_WHY.format(case="UAT-FLOOR-013"))


@pytest.mark.uat("UAT-FLOOR-014")
def test_bursa_floor_word_in_both_markets_shows_the_chooser():
    pytest.skip(_WHY.format(case="UAT-FLOOR-014"))
