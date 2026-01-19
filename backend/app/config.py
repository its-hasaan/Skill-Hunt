"""
Configuration management using Pydantic Settings.
Loads from environment variables or .env file.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "Skill Hunt API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Database - Supabase PostgreSQL
    supabase_url: str  # Connection string
    supabase_anon_key: Optional[str] = None  # For future Supabase client features
    
    # CORS - Frontend URLs
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    
    # Cache settings
    cache_ttl_seconds: int = 3600  # 1 hour default
    
    # API settings
    api_prefix: str = "/api/v1"
    
    # Rate limiting (for future)
    rate_limit_per_minute: int = 100
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
