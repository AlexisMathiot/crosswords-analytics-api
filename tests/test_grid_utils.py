"""Tests for grid version parsing."""

from app.services.statistics_service import extract_grid_number


def test_weekly_version():
    assert extract_grid_number("1-grid-13.0") == 13


def test_weekly_revision_version():
    assert extract_grid_number("1-grid-13.2") == 13


def test_izipizi_version():
    assert extract_grid_number("1-izipizi-4.0") == 4


def test_duel_version():
    assert extract_grid_number("1-duel-2.1") == 2


def test_none_version():
    assert extract_grid_number(None) is None


def test_unrecognized_version():
    assert extract_grid_number("something-else") is None
