"""Statistics calculation service using Pandas for high performance."""

import math

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime
import re
from dateutil.relativedelta import relativedelta

from app.models import DuelMatch, DuelSubmission, Grid, Progression, Submission, User

GRID_TYPES = ("weekly", "izipizi", "duel")

TYPE_LABELS = {
    "weekly": "Grille de la semaine",
    "izipizi": "Izipizi",
    "duel": "Duel",
}


def extract_grid_number(version: str | None) -> int | None:
    """Extract the grid number from a version string.

    Args:
        version: Version string like "1-grid-13.0", "1-izipizi-4.0" or "1-duel-2.1"

    Returns:
        int: The grid number (e.g., 13) or None if not found
    """
    if not version:
        return None
    match = re.search(r"-(?:grid|izipizi|duel)-(\d+)", version)
    return int(match.group(1)) if match else None


def get_grid_family(db: Session, grid_id: int) -> tuple[Grid, list[int]]:
    """Get the grid family (parent + all revisions) for aggregated statistics.

    When a grid is a revision, we aggregate statistics from the parent and all its
    revisions. The most recent grid (revision) is returned as the representative grid.

    Args:
        db: Database session
        grid_id: Any grid ID (parent or revision)

    Returns:
        tuple: (representative_grid, list_of_all_grid_ids)
            - representative_grid: The most recent grid in the family (for display info)
            - list_of_all_grid_ids: All grid IDs whose submissions should be aggregated

    Raises:
        ValueError: If grid not found
    """
    grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not grid:
        raise ValueError(f"Grid {grid_id} not found")

    # Determine the root parent ID
    if grid.is_revision and grid.parent_grid_id:
        parent_id = grid.parent_grid_id
    else:
        parent_id = grid.id

    # Find all grids in this family (parent + all revisions)
    family_grids = (
        db.query(Grid)
        .filter((Grid.id == parent_id) | (Grid.parent_grid_id == parent_id))
        .all()
    )

    # Get all grid IDs
    family_ids = [g.id for g in family_grids]

    # Find the most recent grid (by published_at or created_at) for display
    # Revisions are more recent, so prefer them
    representative_grid = max(
        family_grids,
        key=lambda g: (g.is_revision, g.published_at or g.created_at or g.id),
    )

    return representative_grid, family_ids


def get_available_grids(db: Session, grid_type: str | None = None) -> list[dict]:
    """Get list of available grids, showing only one grid per family.

    When a grid has revisions, only the most recent (revision) is returned.
    Parent grids that have revisions are hidden from the list.

    Args:
        db: Database session
        grid_type: Optional filter on grid type ("weekly", "izipizi", "duel")

    Returns:
        list: List of grid info dicts with id, gridNumber, version, type,
            activatedAt, publishedAt
    """
    # Get all grids
    all_grids = db.query(Grid).order_by(Grid.id).all()

    # Group grids by family root
    families: dict[int, list[Grid]] = {}
    for grid in all_grids:
        # Determine family root
        if grid.is_revision and grid.parent_grid_id:
            root_id = grid.parent_grid_id
        else:
            root_id = grid.id

        if root_id not in families:
            families[root_id] = []
        families[root_id].append(grid)

    # For each family, pick the representative grid (most recent)
    result = []
    for family_grids in families.values():
        representative = max(
            family_grids,
            key=lambda g: (g.is_revision, g.published_at or g.created_at or g.id),
        )
        if grid_type and representative.type != grid_type:
            continue
        result.append(
            {
                "id": representative.id,
                "gridNumber": extract_grid_number(representative.version),
                "version": representative.version,
                "type": representative.type,
                "activatedAt": representative.activated_at.isoformat()
                if representative.activated_at
                else None,
                "publishedAt": representative.published_at.isoformat()
                if representative.published_at
                else None,
            }
        )

    # Sort by gridNumber then by id
    result.sort(key=lambda x: (x["gridNumber"] or 0, x["id"]))

    return result


def calculate_grid_stats(db: Session, grid_id: int) -> dict:
    """Calculate comprehensive statistics for a grid using Pandas.

    Statistics are aggregated across the grid family (parent + all revisions).

    Args:
        db: Database session
        grid_id: Grid identifier (can be parent or any revision)

    Returns:
        dict: Comprehensive grid statistics

    Raises:
        ValueError: If grid not found
    """
    # Get the grid family for aggregation
    grid, family_ids = get_grid_family(db, grid_id)

    # Fetch all submissions for the entire grid family
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
        .filter(Submission.grid_id.in_(family_ids))
    )

    # Convert to pandas DataFrame for fast analysis
    df = pd.read_sql(submissions_query.statement, db.bind)

    if df.empty:
        return {
            "gridId": grid.id,
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
    without_joker = df[~df["joker_used"]]

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
        "gridId": grid.id,
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

    Leaderboard is aggregated across the grid family (parent + all revisions).

    Args:
        db: Database session
        grid_id: Grid identifier (can be parent or any revision)
        limit: Maximum number of results

    Returns:
        list: Leaderboard entries

    Raises:
        ValueError: If grid not found
    """
    # Get the grid family for aggregation
    _grid, family_ids = get_grid_family(db, grid_id)

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
        .filter(Submission.grid_id.in_(family_ids))
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

    Distribution is aggregated across the grid family (parent + all revisions).

    Args:
        db: Database session
        grid_id: Grid identifier (can be parent or any revision)
        num_bins: Number of bins for histogram

    Returns:
        dict: Distribution data with bins

    Raises:
        ValueError: If grid not found
    """
    # Get the grid family for aggregation
    _grid, family_ids = get_grid_family(db, grid_id)

    # Fetch scores from all grids in the family
    scores = (
        db.query(Submission.final_score)
        .filter(Submission.grid_id.in_(family_ids))
        .all()
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
    db: Session, grid_id: int, num_bins: int = 20, max_seconds: int | None = None
) -> dict:
    """Get completion time distribution for histogram visualization.

    Distribution is aggregated across the grid family (parent + all revisions).

    Args:
        db: Database session
        grid_id: Grid identifier (can be parent or any revision)
        num_bins: Number of bins for histogram
        max_seconds: Optional upper bound in seconds to filter outliers

    Returns:
        dict: Distribution data with bins for completion times

    Raises:
        ValueError: If grid not found
    """
    # Get the grid family for aggregation
    _grid, family_ids = get_grid_family(db, grid_id)

    # Fetch completion times from all grids in the family
    times = (
        db.query(Submission.completion_time_seconds)
        .filter(Submission.grid_id.in_(family_ids))
        .all()
    )

    if not times:
        return {
            "bins": [],
            "counts": [],
            "totalSubmissions": 0,
            "filteredSubmissions": 0,
        }

    # Convert to numpy array
    times_array = np.array([t[0] for t in times])
    total_submissions = len(times_array)

    # Filter outliers if max_seconds is set
    if max_seconds is not None:
        times_array = times_array[times_array <= max_seconds]

    filtered_submissions = len(times_array)

    if filtered_submissions == 0:
        return {
            "bins": [],
            "totalSubmissions": total_submissions,
            "filteredSubmissions": 0,
        }

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
        "totalSubmissions": total_submissions,
        "filteredSubmissions": filtered_submissions,
    }


def calculate_temporal_stats(db: Session, grid_id: int) -> dict:
    """Calculate temporal statistics for a grid (submission times analysis).

    Statistics are aggregated across the grid family (parent + all revisions).

    Args:
        db: Database session
        grid_id: Grid identifier (can be parent or any revision)

    Returns:
        dict: Temporal statistics including:
            - submissions by hour of day
            - submissions by day of week
            - peak submission times
            - daily submission timeline

    Raises:
        ValueError: If grid not found
    """
    # Get the grid family for aggregation
    grid, family_ids = get_grid_family(db, grid_id)

    # Fetch all submissions with timestamps from the grid family
    submissions_query = db.query(Submission.submitted_at).filter(
        Submission.grid_id.in_(family_ids)
    )

    # Convert to pandas DataFrame
    df = pd.read_sql(submissions_query.statement, db.bind)

    if df.empty:
        return {
            "gridId": grid.id,
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
        "gridId": grid.id,
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


def get_new_users_per_period(db: Session, granularity: str = "month") -> list[dict]:
    """Get the number of new users registered per period.

    Args:
        db: Database session
        granularity: "week" or "month"

    Returns:
        list: User registration counts per period, sorted chronologically
    """
    query = db.query(User.created_at)
    df = pd.read_sql(query.statement, db.bind)

    if df.empty:
        return []

    df["created_at"] = pd.to_datetime(df["created_at"])

    if granularity == "week":
        df["period"] = df["created_at"].dt.to_period("W")
    else:
        df["period"] = df["created_at"].dt.to_period("M")

    grouped = df.groupby("period").size().reset_index(name="count")
    grouped = grouped.sort_values("period")

    if granularity == "week":
        return [
            {
                "period": f"{row['period'].start_time.strftime('%Y-W%V')}",
                "startDate": row["period"].start_time.strftime("%Y-%m-%d"),
                "count": int(row["count"]),
            }
            for _, row in grouped.iterrows()
        ]
    else:
        return [
            {"period": str(row["period"]), "count": int(row["count"])}
            for _, row in grouped.iterrows()
        ]


def calculate_global_stats(
    db: Session,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Calculate global platform statistics with per-grid breakdown.

    Grids are grouped by family (parent + revisions). Only the most recent grid
    in each family is displayed, with aggregated statistics from all family members.

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

    # Count grid families (parent + revisions = 1 family)
    # A family root is either a non-revision grid, or the parent_grid_id of a revision
    all_grids = db.query(Grid).all()
    family_roots = set()
    published_family_roots = set()
    for grid in all_grids:
        root_id = (
            grid.parent_grid_id if grid.is_revision and grid.parent_grid_id else grid.id
        )
        family_roots.add(root_id)
        if grid.published_at is not None:
            published_family_roots.add(root_id)

    total_grids = len(family_roots)
    published_grids = len(published_family_roots)

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

    # Fetch per-grid statistics with parent_grid_id and is_revision for family grouping
    grids_query = (
        db.query(
            Grid.id,
            Grid.version,
            Grid.parent_grid_id,
            Grid.is_revision,
            Grid.published_at,
            Grid.created_at,
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
        # Determine the family root for each grid
        # If is_revision and has parent_grid_id, use parent_grid_id; otherwise use id
        df["family_root"] = df.apply(
            lambda row: row["parent_grid_id"]
            if row["is_revision"] and pd.notna(row["parent_grid_id"])
            else row["id"],
            axis=1,
        )

        # Get unique family roots
        family_roots = df["family_root"].unique()

        for family_root in family_roots:
            # Get all grids in this family
            family_df = df[df["family_root"] == family_root]

            # Find the representative grid (most recent: prefer revision, then by date)
            family_grids_info = family_df[
                ["id", "version", "is_revision", "published_at", "created_at"]
            ].drop_duplicates()
            representative = family_grids_info.sort_values(
                by=["is_revision", "published_at", "created_at", "id"],
                ascending=[False, False, False, False],
            ).iloc[0]

            # Get all submissions for the family
            family_submissions = family_df[family_df["grid_id"].notna()]

            if len(family_submissions) > 0:
                # Calculate completion rate
                completed = (
                    family_submissions["words_found"]
                    == family_submissions["total_words"]
                ).sum()
                completion_rate = (completed / len(family_submissions)) * 100

                # Calculate joker usage rate
                joker_used_count = family_submissions["joker_used"].sum()
                joker_rate = (joker_used_count / len(family_submissions)) * 100

                # Get total words for this grid (same for all submissions)
                total_words = int(family_submissions["total_words"].iloc[0])

                # Calculate average words found
                avg_words_found = family_submissions["words_found"].mean()

                # Calculate median completion time
                median_time = family_submissions["completion_time_seconds"].median()

                # Get grid version from representative
                grid_version = str(representative["version"])

                grids_stats.append(
                    {
                        "gridId": int(representative["id"]),
                        "gridNumber": extract_grid_number(grid_version),
                        "gridVersion": grid_version,
                        "totalPlayers": int(len(family_submissions)),
                        "completionRate": round(float(completion_rate), 1),
                        "jokerUsageRate": round(float(joker_rate), 1),
                        "totalWords": total_words,
                        "averageWordsFound": round(float(avg_words_found), 1),
                        "medianCompletionTime": int(median_time),
                    }
                )
            else:
                # Family without submissions - use representative grid info
                grid_version = str(representative["version"])
                grids_stats.append(
                    {
                        "gridId": int(representative["id"]),
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

    # Sort by gridNumber (grid families)
    grids_stats.sort(key=lambda x: (x["gridNumber"] or 0, x["gridId"]))

    # Count unique grid families (not individual grids)
    unique_families = len(grids_stats)

    return {
        "totalUsers": total_users,
        "totalGrids": total_grids,
        "publishedGrids": published_grids,
        "uniqueGridFamilies": unique_families,
        "totalSubmissions": total_submissions,
        "averageSubmissionsPerGrid": round(total_submissions / unique_families, 2)
        if unique_families > 0
        else 0,
        "gridStats": grids_stats,
    }


def _fetch_activity_data(db: Session, months_lookback: int) -> pd.DataFrame:
    """Fetch user activity from submissions and progressions.

    Returns a DataFrame with columns: user_id, activity_date, period.
    """
    cutoff = (datetime.now() - relativedelta(months=months_lookback)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    submissions_query = db.query(
        Submission.user_id,
        Submission.submitted_at.label("activity_date"),
    ).filter(Submission.submitted_at >= cutoff)

    df = pd.read_sql(submissions_query.statement, db.bind)

    try:
        progressions_query = db.query(
            Progression.user_id,
            Progression.last_saved_at.label("activity_date"),
        ).filter(Progression.last_saved_at >= cutoff)
        df_prog = pd.read_sql(progressions_query.statement, db.bind)
        df = pd.concat([df, df_prog], ignore_index=True)
    except Exception:
        pass  # progression table may not exist yet

    if df.empty:
        return df

    # Normalize UUIDs to strings so they can be matched against users.id
    df["user_id"] = df["user_id"].astype(str)
    df["activity_date"] = pd.to_datetime(df["activity_date"])
    df["period"] = df["activity_date"].dt.to_period("M")
    return df


def _build_active_users_timeline(
    users_by_period: dict[object, set], registration_map: dict
) -> list[dict]:
    """Build active users timeline with new vs returning breakdown."""
    periods = sorted(users_by_period.keys())
    timeline = []
    for period in periods:
        active = users_by_period[period]
        new_users = {uid for uid in active if registration_map.get(uid) == period}
        timeline.append(
            {
                "period": str(period),
                "activeUsers": len(active),
                "newUsers": len(new_users),
                "returningUsers": len(active - new_users),
            }
        )
    return timeline


def _calculate_regular_users(
    df: pd.DataFrame, min_active_months: int, months_lookback: int
) -> dict:
    """Calculate how many users meet the regular activity threshold."""
    user_month_counts = (
        df.groupby("user_id")["period"].nunique().reset_index(name="active_months")
    )
    regular_count = int((user_month_counts["active_months"] >= min_active_months).sum())
    total = len(user_month_counts)

    return {
        "count": regular_count,
        "totalUsers": total,
        "percentage": round((regular_count / total) * 100, 1) if total > 0 else 0.0,
        "minActiveMonths": min_active_months,
        "monthsAnalyzed": months_lookback,
    }


def _calculate_retention(users_by_period: dict[object, set]) -> list[dict]:
    """Calculate month-over-month retention rates."""
    periods = sorted(users_by_period.keys())
    retention = []
    for i in range(1, len(periods)):
        prev_users = users_by_period[periods[i - 1]]
        curr_users = users_by_period[periods[i]]
        retained = prev_users & curr_users
        retention.append(
            {
                "period": str(periods[i]),
                "retainedFromPrevious": len(retained),
                "previousTotal": len(prev_users),
                "retentionRate": round((len(retained) / len(prev_users)) * 100, 1)
                if len(prev_users) > 0
                else 0.0,
            }
        )
    return retention


def _build_activity_distribution(df: pd.DataFrame) -> list[dict]:
    """Build distribution of how many months each user was active (1, 2, 3+)."""
    user_month_counts = (
        df.groupby("user_id")["period"].nunique().reset_index(name="active_months")
    )
    distribution_counts = user_month_counts["active_months"].value_counts().sort_index()

    distribution = []
    bucket_3plus = 0
    for months_count, user_count in distribution_counts.items():
        if months_count >= 3:
            bucket_3plus += int(user_count)
        else:
            distribution.append(
                {"activeMonths": int(months_count), "userCount": int(user_count)}
            )
    if bucket_3plus > 0:
        distribution.append({"activeMonths": "3+", "userCount": bucket_3plus})

    return distribution


def get_user_activity_stats(
    db: Session, months_lookback: int = 6, min_active_months: int = 2
) -> dict:
    """Calculate user activity and retention statistics.

    Args:
        db: Database session
        months_lookback: Number of months to look back
        min_active_months: Minimum months active to be considered "regular"

    Returns:
        dict: Activity statistics with timeline, regular users, retention,
              and frequency distribution
    """
    empty_response = {
        "activeUsersTimeline": [],
        "regularUsers": {
            "count": 0,
            "totalUsers": 0,
            "percentage": 0.0,
            "minActiveMonths": min_active_months,
            "monthsAnalyzed": months_lookback,
        },
        "totalPlayedUsers": 0,
        "retention": [],
        "activityDistribution": [],
    }

    df = _fetch_activity_data(db, months_lookback)
    if df.empty:
        return empty_response

    # Build user sets per period (shared by timeline and retention)
    periods = sorted(df["period"].unique())
    users_by_period = {
        period: set(df[df["period"] == period]["user_id"].unique())
        for period in periods
    }

    # Registration dates for new vs returning classification
    users_query = db.query(User.id, User.created_at)
    df_users = pd.read_sql(users_query.statement, db.bind)
    df_users["id"] = df_users["id"].astype(str)
    df_users["created_at"] = pd.to_datetime(df_users["created_at"])
    df_users["registration_period"] = df_users["created_at"].dt.to_period("M")
    registration_map = dict(zip(df_users["id"], df_users["registration_period"]))

    # Total users who have played at least one grid (all time)
    all_user_ids = (
        db.query(Submission.user_id).union(db.query(Progression.user_id)).subquery()
    )
    total_played_users = db.query(func.count()).select_from(all_user_ids).scalar()

    return {
        "activeUsersTimeline": _build_active_users_timeline(
            users_by_period, registration_map
        ),
        "regularUsers": _calculate_regular_users(
            df, min_active_months, months_lookback
        ),
        "totalPlayedUsers": total_played_users,
        "retention": _calculate_retention(users_by_period),
        "activityDistribution": _build_activity_distribution(df),
    }


def calculate_type_stats(db: Session) -> dict:
    """Calculate aggregate statistics per grid type (weekly, izipizi, duel).

    Weekly and izipizi grids are played through the submission table; duel grids
    go through duel_submission/duel_match, which have no score or joker concept
    (those metrics are null for the duel type).

    Args:
        db: Database session

    Returns:
        dict: {"types": [stats per type, always all three types]}
    """
    # Count grid families per type (same family grouping as the grids list)
    all_grids = db.query(Grid).all()
    families: dict[int, list[Grid]] = {}
    for grid in all_grids:
        root_id = (
            grid.parent_grid_id if grid.is_revision and grid.parent_grid_id else grid.id
        )
        families.setdefault(root_id, []).append(grid)

    grids_per_type = {t: 0 for t in GRID_TYPES}
    published_per_type = {t: 0 for t in GRID_TYPES}
    for family_grids in families.values():
        representative = max(
            family_grids,
            key=lambda g: (g.is_revision, g.published_at or g.created_at or g.id),
        )
        if representative.type not in grids_per_type:
            continue
        grids_per_type[representative.type] += 1
        if any(g.published_at is not None for g in family_grids):
            published_per_type[representative.type] += 1

    # Classic submissions (weekly + izipizi) grouped by grid type
    submissions_query = db.query(
        Grid.type,
        Submission.user_id,
        Submission.final_score,
        Submission.completion_time_seconds,
        Submission.words_found,
        Submission.total_words,
        Submission.joker_used,
    ).join(Grid, Submission.grid_id == Grid.id)
    df_sub = pd.read_sql(submissions_query.statement, db.bind)
    if not df_sub.empty:
        df_sub["user_id"] = df_sub["user_id"].astype(str)

    # Duel data
    duel_query = db.query(
        DuelSubmission.user_id,
        DuelSubmission.status,
        DuelSubmission.completion_time,
        DuelSubmission.words_found,
        DuelSubmission.total_words,
    )
    df_duel = pd.read_sql(duel_query.statement, db.bind)
    total_matches = db.query(func.count(DuelMatch.id)).scalar()

    types = []
    for grid_type in GRID_TYPES:
        stats = {
            "type": grid_type,
            "label": TYPE_LABELS[grid_type],
            "totalGrids": grids_per_type[grid_type],
            "publishedGrids": published_per_type[grid_type],
            "totalPlayers": 0,
            "totalSubmissions": 0,
            "averageScore": None,
            "medianScore": None,
            "medianCompletionTime": None,
            "completionRate": None,
            "jokerUsageRate": None,
            "totalMatches": None,
        }

        if grid_type == "duel":
            stats["totalMatches"] = int(total_matches or 0)
            if not df_duel.empty:
                played = df_duel[df_duel["status"].isin(["submitted", "matched"])]
                stats["totalPlayers"] = int(
                    df_duel["user_id"].dropna().astype(str).nunique()
                )
                stats["totalSubmissions"] = int(len(played))
                times = played["completion_time"].dropna()
                if len(times) > 0:
                    stats["medianCompletionTime"] = int(times.median())
                completed_mask = (
                    played["words_found"].notna()
                    & played["total_words"].notna()
                    & (played["words_found"] == played["total_words"])
                )
                if len(played) > 0:
                    stats["completionRate"] = float(
                        round(completed_mask.sum() / len(played) * 100, 1)
                    )
        else:
            if not df_sub.empty:
                type_df = df_sub[df_sub["type"] == grid_type]
                if len(type_df) > 0:
                    stats["totalPlayers"] = int(type_df["user_id"].nunique())
                    stats["totalSubmissions"] = int(len(type_df))
                    stats["averageScore"] = float(
                        round(type_df["final_score"].mean(), 1)
                    )
                    stats["medianScore"] = float(
                        round(type_df["final_score"].median(), 1)
                    )
                    stats["medianCompletionTime"] = int(
                        type_df["completion_time_seconds"].median()
                    )
                    completed = (type_df["words_found"] == type_df["total_words"]).sum()
                    stats["completionRate"] = float(
                        round(completed / len(type_df) * 100, 1)
                    )
                    stats["jokerUsageRate"] = float(
                        round(type_df["joker_used"].sum() / len(type_df) * 100, 1)
                    )

        types.append(stats)

    return {"types": types}
