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
    app_name: str = "Job Script API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Database - Supabase PostgreSQL
    supabase_url: str  # Connection string
    supabase_anon_key: Optional[str] = None  # For future Supabase client features

    # Supabase Storage (for resume file uploads)
    supabase_project_url: Optional[str] = None  # e.g. https://xxxx.supabase.co
    supabase_service_key: Optional[str] = None  # service_role key from Supabase dashboard

    # Supabase Auth (JWT verification for logged-in users)
    # Project Settings -> API -> "JWT Secret". If unset, the backend falls
    # back to verifying tokens remotely via supabase_project_url + anon key.
    supabase_jwt_secret: Optional[str] = None
    
    # CORS - Frontend URLs
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    
    # Cache settings
    cache_ttl_seconds: int = 3600  # 1 hour default
    
    # API settings
    api_prefix: str = "/api/v1"
    
    # Rate limiting (per client IP, sliding 60s window — see ratelimit.py)
    rate_limit_per_minute: int = 100
    # Lower budget for endpoints that parse uploads or run several queries
    # (/resume/*, /extension/*).
    rate_limit_expensive_per_minute: int = 10

    # Largest resume upload accepted, in bytes. Reads abort once this is
    # exceeded, so an oversized file never lands in memory.
    max_upload_bytes: int = 5 * 1024 * 1024  # 5 MB
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
