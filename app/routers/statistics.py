"""Statistics router with analytics endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Grid
from app.services import statistics_service

router = APIRouter()


@router.get("/grids")
async def get_available_grids(db: Session = Depends(get_db)):
    """Get list of available grids.

    Args:
        db: Database session

    Returns:
        list: List of grids with id and version
    """
    grids = db.query(Grid.id, Grid.version).order_by(Grid.id).all()
    return [{"id": grid_id, "version": version} for grid_id, version in grids]


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
async def get_completion_time_distribution(grid_id: int, db: Session = Depends(get_db)):
    """Get completion time distribution for visualization (histogram data).

    Args:
        grid_id: Grid identifier
        db: Database session

    Returns:
        dict: Completion time distribution with bins for histogram
    """
    try:
        distribution = statistics_service.get_completion_time_distribution(db, grid_id)
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


@router.get("/global")
async def get_global_statistics(db: Session = Depends(get_db)):
    """Get global platform statistics across all grids.

    Args:
        db: Database session

    Returns:
        dict: Global statistics including total users, grids, submissions, etc.
    """
    try:
        stats = statistics_service.calculate_global_stats(db)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating global statistics: {str(e)}"
        )
