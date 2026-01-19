"""
API Routers Package
"""

from .skills import router as skills_router
from .companies import router as companies_router
from .salary import router as salary_router
from .career import router as career_router
from .stats import router as stats_router

__all__ = [
    "skills_router",
    "companies_router", 
    "salary_router",
    "career_router",
    "stats_router"
]
