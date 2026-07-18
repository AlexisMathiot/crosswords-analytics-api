"""Statistics router with analytics endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import duel_service, premium_service, statistics_service

router = APIRouter()


@router.get("/grids")
async def get_available_grids(type: str | None = None, db: Session = Depends(get_db)):
    """Get list of available grids.

    Returns only one grid per family (parent + revisions).
    When a grid has revisions, only the most recent (revision) is shown.

    Args:
        type: Optional grid type filter ("weekly", "izipizi", "duel")
        db: Database session

    Returns:
        list: List of grids with id, gridNumber, version, type, activatedAt,
            publishedAt
    """
    if type is not None and type not in ("weekly", "izipizi", "duel"):
        raise HTTPException(
            status_code=400,
            detail="Invalid type. Must be 'weekly', 'izipizi' or 'duel'",
        )
    return statistics_service.get_available_grids(db, grid_type=type)


@router.get("/grid/{grid_id}")
async def get_grid_statistics(grid_id: int, db: Session = Depends(get_db)):
    """Get comprehensive statistics for a specific grid.

    Args:
        grid_id: Grid identifier
        db: Database session

    Returns:
        dict: Grid statistics including:
            - totalPlayers: Number of unique players who submitted
            - totalSubmissions: Total number of submissions
            - completionRate: Percentage of completions
            - scores: Score distribution (min, max, avg, median, percentiles)
            - timing: Completion time statistics
            - jokerUsage: Joker usage statistics
            - wordsAnalysis: Word-level success rates
    """
    try:
        stats = statistics_service.calculate_grid_stats(db, grid_id)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating statistics: {str(e)}"
        )


@router.get("/grid/{grid_id}/leaderboard")
async def get_grid_leaderboard(
    grid_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get leaderboard for a specific grid.

    Args:
        grid_id: Grid identifier
        limit: Maximum number of results (default: 100, max: 1000)
        db: Database session

    Returns:
        list: Leaderboard entries with rank, pseudo, score, time, etc.
    """
    if limit > 1000:
        limit = 1000

    try:
        leaderboard = statistics_service.get_leaderboard(db, grid_id, limit)
        return leaderboard
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching leaderboard: {str(e)}"
        )


@router.get("/grid/{grid_id}/distribution")
async def get_score_distribution(grid_id: int, db: Session = Depends(get_db)):
    """Get score distribution for visualization (histogram data).

    Args:
        grid_id: Grid identifier
        db: Database session

    Returns:
        dict: Score distribution with bins for histogram
    """
    try:
        distribution = statistics_service.get_score_distribution(db, grid_id)
        return distribution
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating distribution: {str(e)}"
        )


@router.get("/grid/{grid_id}/completion-time-distribution")
async def get_completion_time_distribution(
    grid_id: int,
    max_minutes: int | None = None,
    db: Session = Depends(get_db),
):
    """Get completion time distribution for visualization (histogram data).

    Args:
        grid_id: Grid identifier
        max_minutes: Optional upper bound in minutes to filter outliers
        db: Database session

    Returns:
        dict: Completion time distribution with bins for histogram.
            Includes totalSubmissions and filteredSubmissions counts.
    """
    try:
        max_seconds = max_minutes * 60 if max_minutes is not None else None
        distribution = statistics_service.get_completion_time_distribution(
            db, grid_id, max_seconds=max_seconds
        )
        return distribution
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating completion time distribution: {str(e)}",
        )


@router.get("/grid/{grid_id}/temporal")
async def get_temporal_statistics(grid_id: int, db: Session = Depends(get_db)):
    """Get temporal statistics for a specific grid (submission times analysis).

    Args:
        grid_id: Grid identifier
        db: Database session

    Returns:
        dict: Temporal statistics including:
            - submissionsByHour: Count of submissions for each hour (0-23)
            - submissionsByDayOfWeek: Count of submissions for each day (Monday-Sunday)
            - peakHours: Top 3 hours with most submissions
            - dailyTimeline: Daily submission counts over time
            - firstSubmission: Timestamp of first submission
            - lastSubmission: Timestamp of last submission
            - averageSubmissionsPerDay: Average number of submissions per day
    """
    try:
        stats = statistics_service.calculate_temporal_stats(db, grid_id)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating temporal statistics: {str(e)}"
        )


@router.get("/users/registrations")
async def get_new_users_registrations(
    granularity: str = "month",
    db: Session = Depends(get_db),
):
    """Get the number of new user registrations per period.

    Args:
        granularity: Grouping period - "week" or "month" (default: "month")
        db: Database session

    Returns:
        list: Registration counts per period, sorted chronologically
    """
    if granularity not in ("week", "month"):
        raise HTTPException(
            status_code=400, detail="granularity must be 'week' or 'month'"
        )
    try:
        return statistics_service.get_new_users_per_period(db, granularity)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching user registrations: {str(e)}"
        )


@router.get("/users/monthly")
async def get_new_users_per_month(db: Session = Depends(get_db)):
    """Get the number of new user registrations per month.

    Deprecated: Use /users/registrations?granularity=month instead.

    Returns:
        list: Monthly counts sorted chronologically
    """
    try:
        return statistics_service.get_new_users_per_period(db, "month")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching monthly users: {str(e)}"
        )


@router.get("/users/activity")
async def get_user_activity(
    months_lookback: int = 6,
    min_active_months: int = 2,
    db: Session = Depends(get_db),
):
    """Get user activity and retention statistics.

    Tracks active users per month based on game activity (submissions and
    progressions). A user is considered "active" in a month if they submitted
    or saved progress on at least one grid.

    Args:
        months_lookback: Number of months to analyze (1-24, default: 6)
        min_active_months: Minimum months active to be "regular" (default: 2)
        db: Database session

    Returns:
        dict: Activity timeline, regular user stats, retention rates,
              and activity frequency distribution
    """
    if months_lookback < 1 or months_lookback > 24:
        raise HTTPException(
            status_code=400, detail="months_lookback must be between 1 and 24"
        )
    if min_active_months < 1 or min_active_months > months_lookback:
        raise HTTPException(
            status_code=400,
            detail="min_active_months must be between 1 and months_lookback",
        )
    try:
        return statistics_service.get_user_activity_stats(
            db, months_lookback, min_active_months
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating user activity: {str(e)}"
        )


@router.get("/global")
async def get_global_statistics(
    db: Session = Depends(get_db),
    start_date: str | None = None,
    end_date: str | None = None,
    period: str | None = None,
):
    """Get global platform statistics across all grids.

    Args:
        db: Database session
        start_date: Optional start date filter (ISO format: YYYY-MM-DD)
        end_date: Optional end date filter (ISO format: YYYY-MM-DD)
        period: Optional preset period (week, month, year, all)

    Returns:
        dict: Global statistics including total users, grids, submissions, etc.
    """
    from datetime import datetime, timedelta

    # Handle preset periods
    if period:
        today = datetime.now().date()
        if period == "week":
            start_date = (today - timedelta(days=7)).isoformat()
            end_date = today.isoformat()
        elif period == "month":
            start_date = (today - timedelta(days=30)).isoformat()
            end_date = today.isoformat()
        elif period == "year":
            start_date = (today - timedelta(days=365)).isoformat()
            end_date = today.isoformat()
        elif period == "all":
            start_date = None
            end_date = None

    try:
        stats = statistics_service.calculate_global_stats(db, start_date, end_date)
        # Add period info to response
        stats["period"] = {
            "type": period or "custom" if (start_date or end_date) else "all",
            "startDate": start_date,
            "endDate": end_date,
        }
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating global statistics: {str(e)}"
        )


@router.get("/types")
async def get_type_statistics(db: Session = Depends(get_db)):
    """Get aggregate statistics per grid type (weekly, izipizi, duel).

    Weekly/izipizi metrics come from classic submissions; duel metrics come
    from the duel tables (score and joker metrics are null for duels).

    Args:
        db: Database session

    Returns:
        dict: {"types": [per-type stats, always all three types]}
    """
    try:
        return statistics_service.calculate_type_stats(db)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating type statistics: {str(e)}"
        )


@router.get("/duels/overview")
async def get_duel_overview(db: Session = Depends(get_db)):
    """Get platform-wide duel statistics.

    Args:
        db: Database session

    Returns:
        dict: Duel submissions/matches counts, outcomes, completion times,
            monthly participation timeline and Elo summary
    """
    try:
        return duel_service.get_duel_overview(db)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating duel statistics: {str(e)}"
        )


@router.get("/duels/leaderboard")
async def get_duel_leaderboard(limit: int = 50, db: Session = Depends(get_db)):
    """Get the Elo leaderboard.

    Only players with at least 5 duels played are ranked (same eligibility
    threshold as the main application).

    Args:
        limit: Maximum number of results (default: 50, max: 1000)
        db: Database session

    Returns:
        list: Leaderboard entries with rank, pseudo, rating, win stats
    """
    if limit > 1000:
        limit = 1000

    try:
        return duel_service.get_elo_leaderboard(db, limit)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching Elo leaderboard: {str(e)}"
        )


@router.get("/premium")
async def get_premium_statistics(db: Session = Depends(get_db)):
    """Get premium subscription statistics.

    Refund counts are an estimate: refunds are not persisted in the database,
    they are inferred from cancellation dates falling outside natural billing
    period boundaries.

    Args:
        db: Database session

    Returns:
        dict: Subscription status breakdown, premium count, pending
            cancellations, launch promo usage, estimated refunds and a
            monthly subscription timeline
    """
    try:
        return premium_service.get_premium_stats(db)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating premium statistics: {str(e)}"
        )
