"""
Skill Hunt API - Main Application
=================================
FastAPI backend for the Skill Hunt job market analysis dashboard.

Run locally: uvicorn app.main:app --reload --port 8000
API docs: http://localhost:8000/docs
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time

from .config import get_settings
from .database import db
from .routers import (
    skills_router,
    companies_router,
    salary_router,
    career_router,
    stats_router
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    # Startup
    logger.info("Starting Skill Hunt API...")
    await db.connect()
    logger.info("Database connected")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Skill Hunt API...")
    await db.disconnect()
    logger.info("Database disconnected")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="""
    ## Skill Hunt API
    
    Backend API for the Skill Hunt job market analysis dashboard.
    
    ### Features
    - **Skills**: Get skill demand, co-occurrence, and network data
    - **Salary**: Analyze salary premiums by skill
    - **Companies**: View top hiring companies
    - **Career**: Explore role similarities and career transitions
    - **Stats**: Dashboard statistics and filter options
    
    ### Data Sources
    - Job postings from Adzuna API
    - Skills extracted using NLP and pattern matching
    - Data transformed using dbt
    """,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# CORS middleware
origins = settings.cors_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2)) + "ms"
    return response


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred"
        }
    )


# Include routers
app.include_router(skills_router, prefix=settings.api_prefix)
app.include_router(companies_router, prefix=settings.api_prefix)
app.include_router(salary_router, prefix=settings.api_prefix)
app.include_router(career_router, prefix=settings.api_prefix)
app.include_router(stats_router, prefix=settings.api_prefix)


# Root endpoints
@app.get("/", tags=["Root"])
async def root():
    """API root - basic info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["Root"])
async def health_check():
    """Health check endpoint."""
    try:
        # Test database connection
        result = await db.fetch_one("SELECT 1 as ok")
        db_status = "healthy" if result else "unhealthy"
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "version": settings.app_version,
        "database": db_status
    }


# Convenience endpoint for API version
@app.get(f"{settings.api_prefix}", tags=["Root"])
async def api_root():
    """API v1 root."""
    return {
        "version": "v1",
        "endpoints": {
            "skills": f"{settings.api_prefix}/skills",
            "companies": f"{settings.api_prefix}/companies",
            "salary": f"{settings.api_prefix}/salary",
            "career": f"{settings.api_prefix}/career",
            "stats": f"{settings.api_prefix}/stats"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
