"""Duel statistics service using Pandas for high performance."""

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import DuelMatch, DuelSubmission, EloRating, Grid, User
from app.services.statistics_service import extract_grid_number

# Mirror of EloRating::LEADERBOARD_ELIGIBILITY_THRESHOLD in the Symfony API
ELO_LEADERBOARD_MIN_DUELS = 5


def get_duel_overview(db: Session) -> dict:
    """Get platform-wide duel statistics.

    Args:
        db: Database session

    Returns:
        dict: Duel overview (submissions, matches, outcomes, timings, Elo)
    """
    submissions_query = db.query(
        DuelSubmission.user_id,
        DuelSubmission.grid_id,
        DuelSubmission.status,
        DuelSubmission.completion_time,
        DuelSubmission.words_found,
        DuelSubmission.total_words,
        DuelSubmission.started_at,
    )
    df_sub = pd.read_sql(submissions_query.statement, db.connection())

    matches_query = db.query(
        DuelMatch.grid_id, DuelMatch.outcome, DuelMatch.resolved_at
    )
    df_match = pd.read_sql(matches_query.statement, db.connection())

    overview = {
        "totalDuelSubmissions": int(len(df_sub)),
        "uniquePlayers": 0,
        "totalMatches": int(len(df_match)),
        "outcomes": {
            "player1Wins": 0,
            "player2Wins": 0,
            "draws": 0,
            "drawRate": 0.0,
        },
        "submissionsByStatus": {
            "in_progress": 0,
            "submitted": 0,
            "matched": 0,
            "expired": 0,
        },
        "expiredRate": 0.0,
        "completionTime": None,
        "averageWordsFound": None,
        "averageCompletion": None,
        "participationTimeline": [],
        "perGrid": [],
        "elo": _get_elo_summary(db),
    }

    if not df_sub.empty:
        overview["uniquePlayers"] = int(
            df_sub["user_id"].dropna().astype(str).nunique()
        )

        status_counts = df_sub["status"].value_counts().to_dict()
        for status in overview["submissionsByStatus"]:
            overview["submissionsByStatus"][status] = int(status_counts.get(status, 0))
        overview["expiredRate"] = float(
            round(overview["submissionsByStatus"]["expired"] / len(df_sub) * 100, 1)
        )

        times = df_sub["completion_time"].dropna()
        if len(times) > 0:
            overview["completionTime"] = {
                "mean": float(round(times.mean(), 1)),
                "median": float(times.median()),
                "min": int(times.min()),
                "max": int(times.max()),
            }

        played = df_sub[df_sub["words_found"].notna() & df_sub["total_words"].notna()]
        if len(played) > 0:
            overview["averageWordsFound"] = float(
                round(played["words_found"].mean(), 1)
            )
            valid = played[played["total_words"] > 0]
            if len(valid) > 0:
                overview["averageCompletion"] = float(
                    round((valid["words_found"] / valid["total_words"]).mean() * 100, 1)
                )

    if not df_match.empty:
        outcome_counts = df_match["outcome"].value_counts().to_dict()
        player1_wins = int(outcome_counts.get("submission1", 0))
        player2_wins = int(outcome_counts.get("submission2", 0))
        draws = int(outcome_counts.get("draw", 0))
        overview["outcomes"] = {
            "player1Wins": player1_wins,
            "player2Wins": player2_wins,
            "draws": draws,
            "drawRate": float(round(draws / len(df_match) * 100, 1)),
        }

    overview["participationTimeline"] = _build_participation_timeline(df_sub, df_match)
    overview["perGrid"] = _build_per_grid_stats(db, df_sub, df_match)

    return overview


def _build_per_grid_stats(
    db: Session, df_sub: pd.DataFrame, df_match: pd.DataFrame
) -> list[dict]:
    """Build per-duel-grid statistics (published grids only), most recent first."""
    duel_grids = (
        db.query(Grid.id, Grid.version, Grid.activated_at, Grid.published_at)
        .filter(Grid.type == "duel", Grid.published_at.isnot(None))
        .all()
    )
    if not duel_grids:
        return []

    matches_per_grid: dict = (
        df_match.groupby("grid_id").size().to_dict() if not df_match.empty else {}
    )

    per_grid = []
    for grid in duel_grids:
        stats = {
            "gridId": grid.id,
            "gridNumber": extract_grid_number(grid.version),
            "version": grid.version,
            "submissions": 0,
            "matches": int(matches_per_grid.get(grid.id, 0)),
            "uniquePlayers": 0,
            "expiredCount": 0,
            "medianCompletionTime": None,
            "completionRate": None,
        }

        if not df_sub.empty:
            grid_subs = df_sub[df_sub["grid_id"] == grid.id]
            played = grid_subs[grid_subs["status"].isin(["submitted", "matched"])]
            stats["submissions"] = int(len(played))
            stats["uniquePlayers"] = int(
                grid_subs["user_id"].dropna().astype(str).nunique()
            )
            stats["expiredCount"] = int((grid_subs["status"] == "expired").sum())
            times = played["completion_time"].dropna()
            if len(times) > 0:
                stats["medianCompletionTime"] = int(times.median())
            completed = (
                played["words_found"].notna()
                & played["total_words"].notna()
                & (played["words_found"] == played["total_words"])
            )
            if len(played) > 0:
                stats["completionRate"] = float(
                    round(completed.sum() / len(played) * 100, 1)
                )

        per_grid.append(stats)

    # Most recent grid first (grids without data still listed, at their place)
    per_grid.sort(key=lambda g: (g["gridNumber"] or 0, g["gridId"]), reverse=True)
    return per_grid


def _build_participation_timeline(
    df_sub: pd.DataFrame, df_match: pd.DataFrame
) -> list[dict]:
    """Build a monthly timeline of duel submissions and resolved matches."""
    parts = []

    if not df_sub.empty:
        sub_periods = (
            pd.to_datetime(df_sub["started_at"])
            .dt.to_period("M")
            .value_counts()
            .sort_index()
        )
        parts.append(sub_periods.rename("submissions"))

    if not df_match.empty:
        match_periods = (
            pd.to_datetime(df_match["resolved_at"])
            .dt.to_period("M")
            .value_counts()
            .sort_index()
        )
        parts.append(match_periods.rename("matches"))

    if not parts:
        return []

    timeline = pd.concat(parts, axis=1).fillna(0).sort_index()
    for column in ("submissions", "matches"):
        if column not in timeline.columns:
            timeline[column] = 0

    return [
        {
            "period": str(period),
            "submissions": int(row["submissions"]),
            "matches": int(row["matches"]),
        }
        for period, row in timeline.iterrows()
    ]


def _get_elo_summary(db: Session) -> dict:
    """Get aggregate Elo rating statistics."""
    rated_players = db.query(func.count(EloRating.id)).scalar() or 0
    eligible_players = (
        db.query(func.count(EloRating.id))
        .filter(EloRating.duels_played >= ELO_LEADERBOARD_MIN_DUELS)
        .scalar()
        or 0
    )
    average_rating = db.query(func.avg(EloRating.rating)).scalar()
    max_rating = db.query(func.max(EloRating.rating)).scalar()

    return {
        "ratedPlayers": int(rated_players),
        "eligiblePlayers": int(eligible_players),
        "averageRating": float(round(average_rating, 1)) if average_rating else None,
        "maxRating": int(max_rating) if max_rating is not None else None,
    }


def get_elo_leaderboard(
    db: Session, limit: int = 50, min_duels: int = ELO_LEADERBOARD_MIN_DUELS
) -> list[dict]:
    """Get the Elo leaderboard.

    Only players having played at least `min_duels` duels are ranked
    (mirrors the eligibility threshold of the Symfony API).

    Args:
        db: Database session
        limit: Maximum number of results
        min_duels: Minimum duels played to appear on the leaderboard

    Returns:
        list: Leaderboard entries with rank, pseudo, rating, win stats
    """
    query = (
        db.query(
            EloRating.rating,
            EloRating.duels_played,
            EloRating.duels_won,
            EloRating.duels_lost,
            User.pseudo,
        )
        .join(User, EloRating.user_id == User.id)
        .filter(EloRating.duels_played >= min_duels)
        .order_by(EloRating.rating.desc())
        .limit(limit)
    )

    df = pd.read_sql(query.statement, db.connection())

    if df.empty:
        return []

    df["rank"] = range(1, len(df) + 1)

    leaderboard = df.to_dict(orient="records")

    for entry in leaderboard:
        entry["rank"] = int(entry["rank"])
        entry["rating"] = int(entry["rating"])
        entry["duelsPlayed"] = int(entry["duels_played"])
        entry["duelsWon"] = int(entry["duels_won"])
        entry["duelsLost"] = int(entry["duels_lost"])
        entry["draws"] = entry["duelsPlayed"] - entry["duelsWon"] - entry["duelsLost"]
        entry["winRate"] = (
            float(round(entry["duelsWon"] / entry["duelsPlayed"] * 100, 1))
            if entry["duelsPlayed"] > 0
            else 0.0
        )

        del entry["duels_played"]
        del entry["duels_won"]
        del entry["duels_lost"]

    return leaderboard
