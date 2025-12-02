# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based analytics API for a crosswords application. It provides high-performance statistical calculations using Pandas/NumPy on data from a PostgreSQL database shared with a Symfony API. The service is read-only and does not modify the database schema.

## Development Commands

### Environment Setup

This project uses **Devbox** for reproducible development environments:

```bash
# Enter development environment (installs Python 3.14, PostgreSQL 18.1, Redis 8.2.2)
devbox shell

# Run development server with auto-reload
devbox run dev
# or manually: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Without Devbox:**
```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

### Testing and Code Quality

```bash
# Run tests
devbox run test
# or: pytest -v

# Lint code with Ruff
devbox run lint
# or: ruff check .

# Format code with Ruff
devbox run format
# or: ruff format .
```

### Configuration

- Copy `.env.example` to `.env` and configure environment variables
- Database connection defaults to `postgresql://crossword:crosswords_password@localhost:5432/crossword_db`
- Redis cache TTL defaults to 600 seconds (10 minutes)

## Architecture

### Application Structure

```
app/
├── main.py                   # FastAPI app initialization, CORS, health check
├── config.py                 # Pydantic Settings for environment variables
├── database.py               # SQLAlchemy engine, session management, connection pooling
├── models.py                 # SQLAlchemy ORM models (read-only, maps to Symfony schema)
├── routers/
│   └── statistics.py         # API endpoints for statistics
└── services/
    └── statistics_service.py # Core analytics logic using Pandas/NumPy
```

### Key Design Patterns

**Database Layer:**
- SQLAlchemy models map to existing Symfony database tables (no migrations needed)
- Connection pooling configured: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`
- Dependency injection via `get_db()` for database sessions
- Read-only access - this service never modifies data

**Service Layer (app/services/statistics_service.py):**
- All statistical calculations use **Pandas DataFrames** for vectorized operations (10-50x faster than Python loops)
- Pattern: Query SQLAlchemy → Convert to DataFrame with `pd.read_sql()` → Perform Pandas/NumPy calculations → Return serializable dict
- Functions raise `ValueError` for missing resources (caught in routers as 404 errors)

**Router Layer (app/routers/statistics.py):**
- Async endpoints for better concurrency
- Consistent error handling: `ValueError` → 404, other exceptions → 500
- Query parameter validation (e.g., limit max 1000 for leaderboard)

### Database Schema Reference

The API reads from these tables (managed by Symfony):

- `users` - User accounts (UUID primary key, pseudo, email, roles)
- `grids` - Crossword grids (integer ID, version, dimensions, publication status)
- `submission` - Completed submissions (UUID, user_id, grid_id, scores, times, joker usage)
- `progression` - In-progress games (UUID, user_id, grid_id, cells JSON, timestamps)
- `clues` - Grid clues (position references)
- `words` - Individual words in clues (encrypted answers, positions, directions)

**Critical relationships:**
- One submission per user per grid (enforced by Symfony)
- Submissions join to users for pseudo in leaderboards
- Grid validation happens before all statistics queries

## API Endpoints

All endpoints are prefixed with `/api/v1/statistics`:

- `GET /grids` - List all available grids
- `GET /grid/{grid_id}` - Comprehensive grid statistics (scores, timing, completion rate, joker usage)
- `GET /grid/{grid_id}/leaderboard?limit=100` - Top players ranked by score and time
- `GET /grid/{grid_id}/distribution` - Score distribution bins for histogram visualization
- `GET /grid/{grid_id}/temporal` - Temporal analysis (submissions by hour/day, peak times, daily timeline)
- `GET /global` - Platform-wide statistics (total users, grids, submissions)

**Documentation available at:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

## Performance Considerations

1. **Pandas/NumPy vectorization** - All statistics use DataFrame operations instead of Python loops
2. **Redis caching** - Planned but not yet implemented (see roadmap in README.md)
3. **Connection pooling** - Reuses database connections across requests
4. **Async endpoints** - FastAPI handles concurrent requests efficiently

**Estimated benchmarks:**
- Grid statistics (2000 submissions): 50-100ms
- Leaderboard (1000 entries): 20-30ms
- Score distribution: 10-20ms

## Common Issues and Solutions

**Bug in statistics_service.py:107** - Logic error when filtering joker usage:
- Line 107 incorrectly uses `df[df["joker_used"]]` for `without_joker`
- Should be `df[~df["joker_used"]]` (note the `~` for negation)
- This causes incorrect `averageScoreWithoutJoker` calculations

**When adding new statistics functions:**
1. Always verify resource exists (grid/user) and raise `ValueError` if not found
2. Handle empty DataFrames (return appropriate empty response)
3. Use `.to_dict()` or explicit type conversions (float, int) for JSON serialization
4. Handle NaN values from Pandas (check with `math.isnan()` before serializing)

**Database queries:**
- Always filter by grid_id/user_id to avoid full table scans
- Use `.join()` for related data (e.g., User.pseudo in leaderboards)
- Query only needed columns to reduce data transfer

## Testing

Currently no tests exist (see roadmap). When adding tests:
- Use `pytest` and `pytest-asyncio`
- Test database queries with test fixtures or mocked data
- Validate Pandas calculations with known sample data
- Test error cases (missing grids, empty submissions)
