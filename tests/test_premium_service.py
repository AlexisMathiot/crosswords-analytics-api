"""Tests for the refund-estimation heuristic."""

from datetime import datetime

from app.services.premium_service import classify_probable_refund

ANCHOR = datetime(2026, 1, 15, 10, 30)


def test_exact_one_month_end_is_natural():
    assert (
        classify_probable_refund(datetime(2026, 2, 15, 10, 30), ANCHOR)
        == "natural_end"
    )


def test_one_month_end_within_tolerance_is_natural():
    assert (
        classify_probable_refund(datetime(2026, 2, 17, 8, 0), ANCHOR) == "natural_end"
    )


def test_mid_period_end_is_probable_refund():
    # Cancelled 10 days in: far from any monthly boundary
    assert (
        classify_probable_refund(datetime(2026, 1, 25, 12, 0), ANCHOR)
        == "probable_refund"
    )


def test_twelve_month_end_is_natural():
    # Annual plan ends on the 12-month boundary
    assert (
        classify_probable_refund(datetime(2027, 1, 15, 10, 30), ANCHOR)
        == "natural_end"
    )


def test_missing_anchor_is_unknown():
    assert classify_probable_refund(datetime(2026, 2, 15), None) == "unknown"


def test_missing_end_date_is_unknown():
    assert classify_probable_refund(None, ANCHOR) == "unknown"


def test_end_before_anchor_is_unknown():
    assert classify_probable_refund(datetime(2025, 12, 1), ANCHOR) == "unknown"


def test_end_before_first_month_boundary_is_probable_refund():
    # 20 days in: before the first possible natural boundary
    assert (
        classify_probable_refund(datetime(2026, 2, 4), ANCHOR) == "probable_refund"
    )
