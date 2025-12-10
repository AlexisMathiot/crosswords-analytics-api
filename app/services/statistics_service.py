"""Statistics calculation service using Pandas for high performance."""

import math

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Grid, Submission, User
import re


def extract_grid_number(version: str | None) -> int | None:
    """Extract the grid number from a version string.

    Args:
        version: Version string like "1-grid-13.0" or "1-grid-13.2"

    Returns:
        int: The grid number (e.g., 13) or None if not found
    """
    if not version:
        return None
    match = re.search(r"-grid-(\d+)", version)
    return int(match.group(1)) if match else None


def calculate_grid_stats(db: Session, grid_id: int) -> dict:
    """Calculate comprehensive statistics for a grid using Pandas.

    Args:
        db: Database session
        grid_id: Grid identifier

    Returns:
        dict: Comprehensive grid statistics

    Raises:
        ValueError: If grid not found
    """
    # Verify grid exists
    grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not grid:
        raise ValueError(f"Grid {grid_id} not found")

    # Fetch all submissions for this grid
    submissions_query = (
        db.query(
            Submission.id,
            Submission.final_score,
            Submission.base_score,
            Submission.time_bonus,
            Submission.joker_penalty,
            Submission.correct_cells,
            Submission.completion_time_seconds,
            Submission.words_found,
            Submission.total_words,
            Submission.joker_used,
            Submission.submitted_at,
            User.pseudo,
        )
        .join(User, Submission.user_id == User.id)
        .filter(Submission.grid_id == grid_id)
    )

    # Convert to pandas DataFrame for fast analysis
    df = pd.read_sql(submissions_query.statement, db.bind)

    if df.empty:
        return {
            "gridId": grid_id,
            "gridNumber": extract_grid_number(grid.version),
            "gridVersion": grid.version,
            "totalPlayers": 0,
            "totalSubmissions": 0,
            "message": "No submissions yet for this grid",
        }

    total_submissions = len(df)
    total_players = total_submissions  # One submission per user per grid

    # Calculate completion metrics
    df["completion_percentage"] = (df["words_found"] / df["total_words"]) * 100
    completion_rate = (df["completion_percentage"] == 100).mean() * 100

    # Score statistics
    std_value = df["final_score"].std()
    scores = {
        "min": float(df["final_score"].min()),
        "max": float(df["final_score"].max()),
        "mean": float(df["final_score"].mean()),
        "median": float(df["final_score"].median()),
        "std": 0.0 if math.isnan(std_value) else float(std_value),
        "percentiles": {
            "p1": float(df["final_score"].quantile(0.01)),
            "p5": float(df["final_score"].quantile(0.05)),
            "p10": float(df["final_score"].quantile(0.10)),
            "p25": float(df["final_score"].quantile(0.25)),
            "p50": float(df["final_score"].quantile(0.50)),
            "p75": float(df["final_score"].quantile(0.75)),
            "p90": float(df["final_score"].quantile(0.90)),
            "p95": float(df["final_score"].quantile(0.95)),
            "p99": float(df["final_score"].quantile(0.99)),
        },
    }

    # Time statistics (in seconds)
    timing = {
        "min": int(df["completion_time_seconds"].min()),
        "max": int(df["completion_time_seconds"].max()),
        "mean": float(df["completion_time_seconds"].mean()),
        "median": float(df["completion_time_seconds"].median()),
        "percentiles": {
            "p25": int(df["completion_time_seconds"].quantile(0.25)),
            "p50": int(df["completion_time_seconds"].quantile(0.50)),
            "p75": int(df["completion_time_seconds"].quantile(0.75)),
        },
    }

    # Joker usage statistics
    joker_used_count = int(df["joker_used"].sum())
    with_joker = df[df["joker_used"]]
    without_joker = df[df["joker_used"]]

    avg_with_joker = with_joker["final_score"].mean() if len(with_joker) > 0 else None
    avg_without_joker = (
        without_joker["final_score"].mean() if len(without_joker) > 0 else None
    )

    joker_usage = {
        "totalUsed": joker_used_count,
        "usageRate": float((df["joker_used"].mean() * 100)),
        "averageScoreWithJoker": None
        if avg_with_joker is None or math.isnan(avg_with_joker)
        else float(avg_with_joker),
        "averageScoreWithoutJoker": None
        if avg_without_joker is None or math.isnan(avg_without_joker)
        else float(avg_without_joker),
    }

    # Words found statistics
    words_stats = {
        "averageFound": float(df["words_found"].mean()),
        "medianFound": float(df["words_found"].median()),
        "totalWords": int(df["total_words"].iloc[0]),
        "distribution": df["words_found"].value_counts().to_dict(),
    }

    return {
        "gridId": grid_id,
        "gridNumber": extract_grid_number(grid.version),
        "gridVersion": grid.version,
        "totalPlayers": total_players,
        "totalSubmissions": total_submissions,
        "completionRate": round(completion_rate, 2),
        "scores": scores,
        "timing": timing,
        "jokerUsage": joker_usage,
        "wordsStats": words_stats,
    }


def get_leaderboard(db: Session, grid_id: int, limit: int = 100) -> list[dict]:
    """Get leaderboard for a grid.

    Args:
        db: Database session
        grid_id: Grid identifier
        limit: Maximum number of results

    Returns:
        list: Leaderboard entries

    Raises:
        ValueError: If grid not found
    """
    # Verify grid exists
    grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not grid:
        raise ValueError(f"Grid {grid_id} not found")

    # Fetch submissions ordered by score (desc) and time (asc)
    query = (
        db.query(
            Submission.final_score,
            Submission.completion_time_seconds,
            Submission.words_found,
            Submission.total_words,
            Submission.joker_used,
            Submission.submitted_at,
            User.pseudo,
        )
        .join(User, Submission.user_id == User.id)
        .filter(Submission.grid_id == grid_id)
        .order_by(
            Submission.final_score.desc(), Submission.completion_time_seconds.asc()
        )
        .limit(limit)
    )

    df = pd.read_sql(query.statement, db.bind)

    if df.empty:
        return []

    # Add rank
    df["rank"] = range(1, len(df) + 1)

    # Convert to list of dicts
    leaderboard = df.to_dict(orient="records")

    # Format for JSON
    for entry in leaderboard:
        entry["rank"] = int(entry["rank"])
        entry["finalScore"] = float(entry["final_score"])
        entry["completionTime"] = int(entry["completion_time_seconds"])
        entry["wordsFound"] = int(entry["words_found"])
        entry["totalWords"] = int(entry["total_words"])
        entry["isCompleted"] = bool(entry["words_found"] == entry["total_words"])
        entry["jokerUsed"] = bool(entry["joker_used"])
        entry["submittedAt"] = entry["submitted_at"].isoformat()

        # Remove original snake_case keys
        del entry["final_score"]
        del entry["completion_time_seconds"]
        del entry["words_found"]
        del entry["total_words"]
        del entry["joker_used"]
        del entry["submitted_at"]

    return leaderboard


def get_score_distribution(db: Session, grid_id: int, num_bins: int = 20) -> dict:
    """Get score distribution for histogram visualization.

    Args:
        db: Database session
        grid_id: Grid identifier
        num_bins: Number of bins for histogram

    Returns:
        dict: Distribution data with bins

    Raises:
        ValueError: If grid not found
    """
    # Verify grid exists
    grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not grid:
        raise ValueError(f"Grid {grid_id} not found")

    # Fetch scores
    scores = (
        db.query(Submission.final_score).filter(Submission.grid_id == grid_id).all()
    )

    if not scores:
        return {"bins": [], "counts": []}

    # Convert to numpy array
    scores_array = np.array([s[0] for s in scores])

    # Create histogram
    counts, bin_edges = np.histogram(scores_array, bins=num_bins)

    return {
        "bins": [
            {
                "start": float(bin_edges[i]),
                "end": float(bin_edges[i + 1]),
                "count": int(counts[i]),
            }
            for i in range(len(counts))
        ],
        "min": float(scores_array.min()),
        "max": float(scores_array.max()),
        "mean": float(scores_array.mean()),
    }


def get_completion_time_distribution(
    db: Session, grid_id: int, num_bins: int = 20
) -> dict:
    """Get completion time distribution for histogram visualization.

    Args:
        db: Database session
        grid_id: Grid identifier
        num_bins: Number of bins for histogram

    Returns:
        dict: Distribution data with bins for completion times

    Raises:
        ValueError: If grid not found
    """
    # Verify grid exists
    grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not grid:
        raise ValueError(f"Grid {grid_id} not found")

    # Fetch completion times
    times = (
        db.query(Submission.completion_time_seconds)
        .filter(Submission.grid_id == grid_id)
        .all()
    )

    if not times:
        return {"bins": [], "counts": []}

    # Convert to numpy array
    times_array = np.array([t[0] for t in times])

    # Create histogram
    counts, bin_edges = np.histogram(times_array, bins=num_bins)

    return {
        "bins": [
            {
                "start": int(bin_edges[i]),
                "end": int(bin_edges[i + 1]),
                "count": int(counts[i]),
            }
            for i in range(len(counts))
        ],
        "min": int(times_array.min()),
        "max": int(times_array.max()),
        "mean": float(times_array.mean()),
        "median": float(np.median(times_array)),
    }


def calculate_temporal_stats(db: Session, grid_id: int) -> dict:
    """Calculate temporal statistics for a grid (submission times analysis).

    Args:
        db: Database session
        grid_id: Grid identifier

    Returns:
        dict: Temporal statistics including:
            - submissions by hour of day
            - submissions by day of week
            - peak submission times
            - daily submission timeline

    Raises:
        ValueError: If grid not found
    """
    # Verify grid exists
    grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not grid:
        raise ValueError(f"Grid {grid_id} not found")

    # Fetch all submissions with timestamps
    submissions_query = db.query(Submission.submitted_at).filter(
        Submission.grid_id == grid_id
    )

    # Convert to pandas DataFrame
    df = pd.read_sql(submissions_query.statement, db.bind)

    if df.empty:
        return {
            "gridId": grid_id,
            "gridNumber": extract_grid_number(grid.version),
            "gridVersion": grid.version,
            "totalSubmissions": 0,
            "message": "No submissions yet for this grid",
        }

    # Ensure submitted_at is datetime
    df["submitted_at"] = pd.to_datetime(df["submitted_at"])

    # Extract temporal components
    df["hour"] = df["submitted_at"].dt.hour
    df["day_of_week"] = df["submitted_at"].dt.dayofweek  # Monday=0, Sunday=6
    df["date"] = df["submitted_at"].dt.date

    # Submissions by hour of day (0-23)
    submissions_by_hour = df["hour"].value_counts().sort_index().to_dict()
    # Fill missing hours with 0
    submissions_by_hour_complete = {
        hour: submissions_by_hour.get(hour, 0) for hour in range(24)
    }

    # Submissions by day of week (0=Monday, 6=Sunday)
    submissions_by_day = df["day_of_week"].value_counts().sort_index().to_dict()
    # Fill missing days with 0
    day_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    submissions_by_day_complete = [
        {"day": day_names[i], "dayNumber": i, "count": submissions_by_day.get(i, 0)}
        for i in range(7)
    ]

    # Find peak submission hours (top 3)
    peak_hours = df["hour"].value_counts().head(3).to_dict()
    peak_hours_list = [
        {"hour": int(hour), "count": int(count)} for hour, count in peak_hours.items()
    ]

    # Daily submissions timeline
    daily_submissions = df.groupby("date").size()
    daily_submissions = daily_submissions.reset_index()
    daily_submissions.columns = ["date", "count"]
    daily_submissions["date"] = daily_submissions["date"].astype(str)
    daily_timeline = daily_submissions.to_dict(orient="records")

    # Calculate statistics
    total_submissions = len(df)
    first_submission = df["submitted_at"].min()
    last_submission = df["submitted_at"].max()

    # Average submissions per day (if multiple days)
    unique_dates = df["date"].nunique()
    avg_submissions_per_day = (
        total_submissions / unique_dates if unique_dates > 0 else 0
    )

    return {
        "gridId": grid_id,
        "gridNumber": extract_grid_number(grid.version),
        "gridVersion": grid.version,
        "totalSubmissions": total_submissions,
        "firstSubmission": first_submission.isoformat(),
        "lastSubmission": last_submission.isoformat(),
        "uniqueDays": int(unique_dates),
        "averageSubmissionsPerDay": round(avg_submissions_per_day, 2),
        "submissionsByHour": submissions_by_hour_complete,
        "submissionsByDayOfWeek": submissions_by_day_complete,
        "peakHours": peak_hours_list,
        "dailyTimeline": daily_timeline,
    }


def calculate_global_stats(
    db: Session,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Calculate global platform statistics with per-grid breakdown.

    Args:
        db: Database session
        start_date: Optional start date filter (ISO format: YYYY-MM-DD)
        end_date: Optional end date filter (ISO format: YYYY-MM-DD)

    Returns:
        dict: Global statistics including per-grid data
    """
    from datetime import datetime, timedelta

    # Parse date filters
    date_filter_start = None
    date_filter_end = None
    if start_date:
        date_filter_start = datetime.fromisoformat(start_date)
    if end_date:
        date_filter_end = datetime.fromisoformat(end_date) + timedelta(days=1)

    total_users = db.query(func.count(User.id)).scalar()
    total_grids = db.query(func.count(Grid.id)).scalar()
    published_grids = (
        db.query(func.count(Grid.id)).filter(Grid.published_at.isnot(None)).scalar()
    )

    # Total submissions (with date filter if provided)
    submissions_count_query = db.query(func.count(Submission.id))
    if date_filter_start:
        submissions_count_query = submissions_count_query.filter(
            Submission.submitted_at >= date_filter_start
        )
    if date_filter_end:
        submissions_count_query = submissions_count_query.filter(
            Submission.submitted_at < date_filter_end
        )
    total_submissions = submissions_count_query.scalar()

    # Fetch per-grid statistics
    grids_query = (
        db.query(
            Grid.id,
            Grid.version,
            Submission.grid_id,
            Submission.words_found,
            Submission.total_words,
            Submission.joker_used,
            Submission.completion_time_seconds,
            Submission.submitted_at,
        )
        .outerjoin(Submission, Grid.id == Submission.grid_id)
        .filter(Grid.published_at.isnot(None))
    )

    # Apply date filters to submissions
    if date_filter_start:
        grids_query = grids_query.filter(
            (Submission.submitted_at >= date_filter_start)
            | (Submission.submitted_at.is_(None))
        )
    if date_filter_end:
        grids_query = grids_query.filter(
            (Submission.submitted_at < date_filter_end)
            | (Submission.submitted_at.is_(None))
        )

    # Convert to DataFrame for analysis
    df = pd.read_sql(grids_query.statement, db.bind)

    grids_stats = []
    if not df.empty and "grid_id" in df.columns:
        # Group by grid
        for grid_id in df["id"].unique():
            grid_df = df[df["id"] == grid_id]
            grid_submissions = grid_df[grid_df["grid_id"].notna()]

            if len(grid_submissions) > 0:
                # Calculate completion rate
                completed = (
                    grid_submissions["words_found"] == grid_submissions["total_words"]
                ).sum()
                completion_rate = (completed / len(grid_submissions)) * 100

                # Calculate joker usage rate
                joker_used_count = grid_submissions["joker_used"].sum()
                joker_rate = (joker_used_count / len(grid_submissions)) * 100

                # Get total words for this grid (same for all submissions)
                total_words = int(grid_submissions["total_words"].iloc[0])

                # Calculate average words found
                avg_words_found = grid_submissions["words_found"].mean()

                # Calculate median completion time
                median_time = grid_submissions["completion_time_seconds"].median()

                # Get grid version
                grid_version = str(grid_df["version"].iloc[0])

                grids_stats.append(
                    {
                        "gridId": int(grid_id),
                        "gridNumber": extract_grid_number(grid_version),
                        "gridVersion": grid_version,
                        "totalPlayers": int(len(grid_submissions)),
                        "completionRate": round(float(completion_rate), 1),
                        "jokerUsageRate": round(float(joker_rate), 1),
                        "totalWords": total_words,
                        "averageWordsFound": round(float(avg_words_found), 1),
                        "medianCompletionTime": int(median_time),
                    }
                )
            else:
                # Grid without submissions
                grid_version = str(grid_df["version"].iloc[0])
                grids_stats.append(
                    {
                        "gridId": int(grid_id),
                        "gridNumber": extract_grid_number(grid_version),
                        "gridVersion": grid_version,
                        "totalPlayers": 0,
                        "completionRate": 0.0,
                        "jokerUsageRate": 0.0,
                        "totalWords": 0,
                        "averageWordsFound": 0.0,
                        "medianCompletionTime": 0,
                    }
                )

    # Sort by gridId
    grids_stats.sort(key=lambda x: x["gridId"])

    return {
        "totalUsers": total_users,
        "totalGrids": total_grids,
        "publishedGrids": published_grids,
        "totalSubmissions": total_submissions,
        "averageSubmissionsPerGrid": round(total_submissions / total_grids, 2)
        if total_grids > 0
        else 0,
        "gridStats": grids_stats,
    }
