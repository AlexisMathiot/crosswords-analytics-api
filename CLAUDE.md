# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based analytics API for a crosswords application (onsengrilleune.fr). It provides high-performance statistical calculations using Pandas/NumPy on data from the PostgreSQL database shared with the Symfony API v2 (`~/Projects/crosswords-api`). The service is read-only and does not modify the database schema.

## Development Commands

### Environment Setup

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The local database is the PostgreSQL container from the `crosswords-api` dev stack (`localhost:5432`, `crossword`/`password`, db `crossword_db`). Start it with `docker compose up -d postgres` in `~/Projects/crosswords-api`.

### Testing and Code Quality

```bash
pytest -v        # Run tests
ruff check .     # Lint
ruff format .    # Format
```

### Configuration

- Copy `.env.example` to `.env` and configure environment variables
- Database connection defaults to `postgresql+psycopg://crossword:password@localhost:5432/crossword_db`
- Redis cache TTL defaults to 600 seconds (10 minutes)

## Architecture

### Application Structure

```
app/
├── main.py                   # FastAPI app initialization, CORS, health check
├── config.py                 # Pydantic Settings for environment variables
├── database.py               # SQLAlchemy engine, session management, connection pooling
├── models.py                 # SQLAlchemy ORM models (read-only, maps to Symfony v2 Postgres schema)
├── routers/
│   └── statistics.py         # API endpoints for statistics
└── services/
    └── statistics_service.py # Core analytics logic using Pandas/NumPy
```

### Deployment (VPS OVH)

The app runs in Docker on the OVH VPS next to the `crosswords-api` prod stack:

- `Dockerfile` + `compose.prod.yaml` — the container joins two external Docker networks: `prod_internal` (reaches PostgreSQL at `prod_postgres:5432`; the database is never publicly exposed) and `web` (shared Caddy reverse proxy, serving `analytics.onsengrilleune.fr`)
- `deploy/deploy-prod.sh` — pull main + rebuild + restart on the VPS
- `deploy/DEPLOY.md` — first-time setup and DNS cutover from o2switch
- Real config (DATABASE_URL with prod password, CORS) lives in `.env.local` on the VPS (gitignored); `app/config.py` normalizes Symfony/Doctrine-style DATABASE_URL (forces `+psycopg`, strips `serverVersion`/`charset`)

### Key Design Patterns

**Database Layer:**
- SQLAlchemy models map to the existing Symfony v2 PostgreSQL tables (no migrations here — Doctrine owns the schema)
- UUIDs use `sqlalchemy.dialects.postgresql.UUID(as_uuid=True)`; JSON columns use generic `sqlalchemy.JSON`
- Connection pooling configured: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`
- Dependency injection via `get_db()` for database sessions
- Read-only access - this service never modifies data

**Service Layer (app/services/statistics_service.py):**
- All statistical calculations use **Pandas DataFrames** for vectorized operations (10-50x faster than Python loops)
- Pattern: Query SQLAlchemy → Convert to DataFrame with `pd.read_sql()` → Perform Pandas/NumPy calculations → Return serializable dict
- UUID columns coming back from `pd.read_sql()` are `uuid.UUID` objects — normalize with `.astype(str)` before joining/grouping across DataFrames
- Functions raise `ValueError` for missing resources (caught in routers as 404 errors)

**Router Layer (app/routers/statistics.py):**
- Async endpoints for better concurrency
- Consistent error handling: `ValueError` → 404, other exceptions → 500
- Query parameter validation (e.g., limit max 1000 for leaderboard)

### Database Schema Reference

The API reads from these tables (managed by Symfony v2 / Doctrine migrations):

- `users` - User accounts (UUID primary key, pseudo, email, roles JSON, Stripe subscription fields)
- `grids` - Crossword grids (integer ID, version, dimensions, publication status, `type`, `activated_at`)
- `submission` - Completed submissions (UUID, user_id, grid_id, scores, times, joker usage)
- `progression` - In-progress games (UUID, user_id, grid_id, cells JSON, cell_validations, timestamps)
- `clues` - Grid clues (position references)
- `words` - Individual words in clues (encrypted answers, positions, directions, alternate answers)

The v2 schema also has duel tables (`duel_match`, `duel_submission`, `elo_rating`) not yet mapped here — candidates for future statistics.

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
- `GET /grid/{grid_id}/completion-time-distribution?max_minutes=60` - Completion time histogram
- `GET /grid/{grid_id}/temporal` - Temporal analysis (submissions by hour/day, peak times, daily timeline)
- `GET /users/registrations?granularity=month` - New user registrations per week/month
- `GET /users/activity?months_lookback=6&min_active_months=2` - Active/regular users, retention, activity distribution
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

**When adding new statistics functions:**
1. Always verify resource exists (grid/user) and raise `ValueError` if not found
2. Handle empty DataFrames (return appropriate empty response)
3. Use `.to_dict()` or explicit type conversions (float, int) for JSON serialization
4. Handle NaN values from Pandas (check with `math.isnan()` before serializing)
5. Convert UUID columns to `str` before using them as dict keys or set members shared across queries

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
