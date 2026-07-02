"""
Supabase Storage utilities for resume file uploads.
Requires SUPABASE_PROJECT_URL and SUPABASE_SERVICE_KEY env vars.
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import Optional, Tuple

from .config import get_settings

logger = logging.getLogger(__name__)

BUCKET_NAME = "resumes"

# MIME type map
MIME_TYPES = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc":  "application/msword",
    ".txt":  "text/plain",
    ".md":   "text/markdown",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

# Module-level singleton
_supabase_client = None


def _get_client():
    """Lazy-initialise the sync Supabase client (called inside a thread)."""
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client
        settings = get_settings()
        if not settings.supabase_project_url or not settings.supabase_service_key:
            raise ValueError(
                "SUPABASE_PROJECT_URL and SUPABASE_SERVICE_KEY must be set to enable file storage."
            )
        _supabase_client = create_client(
            settings.supabase_project_url,
            settings.supabase_service_key,
        )
    return _supabase_client


def _do_upload(file_bytes: bytes, storage_path: str, content_type: str) -> str:
    """Blocking upload — always run via asyncio.to_thread."""
    client = _get_client()
    # file_options values become HTTP headers, so they must be strings
    # ("upsert": False would raise inside the header encoder).
    client.storage.from_(BUCKET_NAME).upload(
        storage_path,
        file_bytes,
        {"content-type": content_type, "upsert": "false"},
    )
    return client.storage.from_(BUCKET_NAME).get_public_url(storage_path)


async def upload_resume_file(
    file_bytes: bytes,
    original_filename: str,
) -> Tuple[str, str]:
    """
    Upload resume to Supabase Storage.
    Returns (storage_path, public_url).
    """
    from pathlib import Path
    ext = Path(original_filename).suffix.lower()
    content_type = MIME_TYPES.get(ext, "application/octet-stream")

    date_prefix = datetime.utcnow().strftime("%Y/%m")
    unique_name = f"{uuid.uuid4()}_{original_filename}"
    storage_path = f"{date_prefix}/{unique_name}"

    public_url = await asyncio.to_thread(_do_upload, file_bytes, storage_path, content_type)
    return storage_path, public_url


def is_storage_configured() -> bool:
    """Return True if both Supabase Storage credentials are present."""
    settings = get_settings()
    return bool(settings.supabase_project_url and settings.supabase_service_key)
