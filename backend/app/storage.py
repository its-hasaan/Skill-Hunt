"""
Supabase Storage utilities for resume file uploads.
Requires SUPABASE_PROJECT_URL and SUPABASE_SERVICE_KEY env vars.
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import Optional

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


def _do_upload(file_bytes: bytes, storage_path: str, content_type: str) -> None:
    """Blocking upload — always run via asyncio.to_thread."""
    client = _get_client()
    # file_options values become HTTP headers, so they must be strings
    # ("upsert": False would raise inside the header encoder).
    client.storage.from_(BUCKET_NAME).upload(
        storage_path,
        file_bytes,
        {"content-type": content_type, "upsert": "false"},
    )


async def upload_resume_file(file_bytes: bytes, original_filename: str) -> str:
    """
    Upload a resume to the PRIVATE `resumes` bucket and return its storage
    path. No URL is returned: public URLs don't work on a private bucket,
    and any future download must use a short-lived signed URL instead.
    """
    from pathlib import Path
    ext = Path(original_filename).suffix.lower()
    content_type = MIME_TYPES.get(ext, "application/octet-stream")

    date_prefix = datetime.utcnow().strftime("%Y/%m")
    storage_path = f"{date_prefix}/{uuid.uuid4()}_{original_filename}"

    await asyncio.to_thread(_do_upload, file_bytes, storage_path, content_type)
    return storage_path


def is_storage_configured() -> bool:
    """Return True if both Supabase Storage credentials are present."""
    settings = get_settings()
    return bool(settings.supabase_project_url and settings.supabase_service_key)
