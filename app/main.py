"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import statistics

# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    debug=settings.debug,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(statistics.router, prefix="/api/v1/statistics", tags=["statistics"])


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Status information
    """
    return {
        "status": "healthy",
        "service": "crosswords-analytics-api",
        "version": settings.api_version,
    }


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information.

    Returns:
        dict: Welcome message and documentation link
    """
    return {
        "message": "Crosswords Analytics API",
        "version": settings.api_version,
        "docs": "/docs",
        "health": "/health",
    }
