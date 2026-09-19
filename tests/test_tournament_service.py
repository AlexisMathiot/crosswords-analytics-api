"""Tests for the pure helpers of the tournament statistics service."""

from datetime import datetime

import pandas as pd

from app.services.statistics_service import extract_grid_number
from app.services.tournament_service import (
    classify_entrant,
    is_premium_now,
    label_round,
    played_rounds_count,
    summarize_slots,
    summarize_submissions,
)

NOW = datetime(2026, 9, 18, 12, 0)


# --- grid version -----------------------------------------------------------


def test_tournament_version_is_parsed():
    assert extract_grid_number("1-tournament-3.0") == 3


# --- premium / entrant classification --------------------------------------


def test_active_subscription_is_premium():
    assert is_premium_now("active", None, [], NOW)


def test_past_due_subscription_is_premium():
    assert is_premium_now("past_due", None, ["ROLE_USER"], NOW)


def test_canceled_with_future_end_is_premium():
    assert is_premium_now("canceled", datetime(2026, 10, 1), [], NOW)


def test_canceled_with_past_end_is_not_premium():
    assert not is_premium_now("canceled", datetime(2026, 9, 1), [], NOW)


def test_premium_grant_role_is_premium():
    assert is_premium_now(None, None, ["ROLE_USER", "ROLE_PREMIUM_GRANT"], NOW)


def test_no_subscription_is_not_premium():
    assert not is_premium_now(None, None, ["ROLE_USER"], NOW)
    assert not is_premium_now(None, None, None, NOW)


def test_ticket_wins_over_premium():
    assert classify_entrant(True, "active", None, [], NOW) == "ticket"


def test_premium_without_ticket():
    assert classify_entrant(False, "active", None, [], NOW) == "premium"


def test_expired_premium_without_ticket_is_other():
    assert classify_entrant(False, "canceled", datetime(2026, 1, 1), [], NOW) == "other"


# --- rounds ------------------------------------------------------------------


def test_played_rounds_count():
    assert played_rounds_count(16) == 4
    assert played_rounds_count(32) == 5
    assert played_rounds_count(64) == 6
    assert played_rounds_count(None) is None


def test_qualifying_window_label():
    info = label_round(1, 64)
    assert info["roundNumber"] is None
    assert info["label"] == "1er tour"
    assert info["played"] is True


def test_round_labels_for_bracket_of_16():
    assert label_round(2, 16)["label"] == "Huitièmes de finale"
    assert label_round(3, 16)["label"] == "Quarts de finale"
    assert label_round(4, 16)["label"] == "Demi-finales"
    assert label_round(5, 16)["label"] == "La Grande Finale"
    assert label_round(5, 16)["roundNumber"] == 4
    assert label_round(5, 16)["players"] == 2


def test_round_labels_for_bracket_of_32():
    assert label_round(2, 32)["label"] == "2e tour"
    assert label_round(3, 32)["label"] == "Huitièmes de finale"
    assert label_round(6, 32)["label"] == "La Grande Finale"


def test_round_labels_for_bracket_of_64():
    assert [label_round(p, 64)["label"] for p in range(1, 8)] == [
        "1er tour",
        "2e tour",
        "3e tour",
        "Huitièmes de finale",
        "Quarts de finale",
        "Demi-finales",
        "La Grande Finale",
    ]


def test_unused_windows_are_bonus_grids_not_played():
    info = label_round(6, 16)  # window 6 = round 5, a bracket of 16 stops at round 4
    assert info["played"] is False
    assert info["roundNumber"] == 5
    assert info["label"] == "Grille bonus"
    assert info["players"] is None
    assert label_round(7, 32)["label"] == "Grille bonus"


def test_unknown_bracket_size_presumes_64_and_flags_rounds_not_played():
    info = label_round(2, None)
    assert info["played"] is False
    assert info["players"] is None
    assert info["label"] == "2e tour"
    assert label_round(4, None)["label"] == "Huitièmes de finale"
    assert label_round(7, None)["label"] == "La Grande Finale"


# --- submissions ---------------------------------------------------------------


def _submissions(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["status", "completion_time", "words_found", "total_words"]
    )


def test_summarize_empty_submissions():
    summary = summarize_submissions(_submissions([]))
    assert summary["total"] == 0
    assert summary["byStatus"] == {"in_progress": 0, "submitted": 0, "cancelled": 0}
    assert summary["completionTime"] is None
    assert summary["fullGridRate"] is None


def test_summarize_submissions_ignores_in_progress_for_metrics():
    df = _submissions(
        [
            {
                "status": "submitted",
                "completion_time": 100,
                "words_found": 10,
                "total_words": 10,
            },
            {
                "status": "submitted",
                "completion_time": 300,
                "words_found": 5,
                "total_words": 10,
            },
            {
                "status": "in_progress",
                "completion_time": None,
                "words_found": None,
                "total_words": None,
            },
            {
                "status": "cancelled",
                "completion_time": 50,
                "words_found": 10,
                "total_words": 10,
            },
        ]
    )
    summary = summarize_submissions(df)
    assert summary["total"] == 4
    assert summary["byStatus"] == {"in_progress": 1, "submitted": 2, "cancelled": 1}
    assert summary["completionTime"] == {
        "mean": 200.0,
        "median": 200.0,
        "min": 100,
        "max": 300,
    }
    assert summary["averageWordsFound"] == 7.5
    assert summary["averageCompletion"] == 75.0
    assert summary["fullGridRate"] == 50.0


# --- slots ----------------------------------------------------------------------


def _slots(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["participation_id", "vacancy_reason", "outcome"])


def test_summarize_empty_slots():
    summary = summarize_slots(_slots([]))
    assert summary["total"] == 0
    assert summary["occupied"] == 0
    assert summary["outcomes"] == {
        "victoire": 0,
        "elimine": 0,
        "walkover": 0,
        "exemption": 0,
    }


def test_summarize_slots_counts_occupancy_outcomes_and_pending():
    df = _slots(
        [
            {"participation_id": "p1", "vacancy_reason": None, "outcome": "victoire"},
            {"participation_id": "p2", "vacancy_reason": None, "outcome": "elimine"},
            {"participation_id": "p3", "vacancy_reason": None, "outcome": "exemption"},
            {
                "participation_id": None,
                "vacancy_reason": "adversaire_retire",
                "outcome": None,
            },
            {"participation_id": "p5", "vacancy_reason": None, "outcome": None},
            {
                "participation_id": None,
                "vacancy_reason": "double_absence",
                "outcome": None,
            },
        ]
    )
    summary = summarize_slots(df)
    assert summary["total"] == 6
    assert summary["occupied"] == 4
    assert summary["vacant"] == 2
    assert summary["vacancyReasons"] == {"adversaire_retire": 1, "double_absence": 1}
    assert summary["outcomes"] == {
        "victoire": 1,
        "elimine": 1,
        "walkover": 0,
        "exemption": 1,
    }
    assert summary["resolved"] == 3
    assert summary["pending"] == 1
