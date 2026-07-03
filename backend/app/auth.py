"""
Supabase Auth integration for FastAPI.

The frontend authenticates with Supabase (email/password or Google OAuth via
supabase-js) and sends the resulting access token as `Authorization: Bearer`.
This module verifies that token and exposes two dependencies:

    get_current_user   -> AuthUser (401 if missing/invalid)
    get_optional_user  -> AuthUser | None (never raises; for endpoints that
                          work anonymously but personalize when logged in)

Verification strategy (in order):
 1. Local HS256 verification with SUPABASE_JWT_SECRET (fast, no network).
    Find the secret in Supabase: Project Settings -> API -> "JWT Secret".
 2. Remote verification against Supabase Auth (`GET /auth/v1/user`) using
    SUPABASE_PROJECT_URL + SUPABASE_ANON_KEY. Slightly slower but works with
    any signing algorithm (including the newer asymmetric keys).

If neither is configured, protected endpoints return 503 with instructions.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

logger = logging.getLogger(__name__)

# auto_error=False so missing credentials yield None (we raise ourselves,
# which lets get_optional_user share the same scheme without 403s).
_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthUser:
    id: str
    email: Optional[str] = None


# Tiny in-process cache for remote verification: token -> (user, expiry).
# Keeps repeated requests from the same session off the Auth API.
_remote_cache: dict = {}
_REMOTE_CACHE_TTL = 300  # seconds
_REMOTE_CACHE_MAX = 1000


def _verify_local(token: str, secret: str) -> Optional[AuthUser]:
    """Verify an HS256 Supabase JWT locally. Returns None if invalid."""
    try:
        import jwt  # PyJWT
    except ImportError:
        logger.error("PyJWT not installed — run: pip install PyJWT")
        return None
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
        return AuthUser(id=payload["sub"], email=payload.get("email"))
    except jwt.PyJWTError as e:
        logger.debug(f"Local JWT verification failed: {e}")
        return None


async def _verify_remote(token: str, project_url: str, anon_key: str) -> Optional[AuthUser]:
    """Verify by asking Supabase Auth who the token belongs to."""
    now = time.time()
    cached = _remote_cache.get(token)
    if cached and cached[1] > now:
        return cached[0]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{project_url.rstrip('/')}/auth/v1/user",
                headers={"apikey": anon_key, "Authorization": f"Bearer {token}"},
            )
        if resp.status_code != 200:
            return None
        data = resp.json()
        user = AuthUser(id=data["id"], email=data.get("email"))
        if len(_remote_cache) > _REMOTE_CACHE_MAX:
            _remote_cache.clear()
        _remote_cache[token] = (user, now + _REMOTE_CACHE_TTL)
        return user
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.warning(f"Remote token verification error: {e}")
        return None


async def _authenticate(token: str) -> Optional[AuthUser]:
    settings = get_settings()

    if settings.supabase_jwt_secret:
        return _verify_local(token, settings.supabase_jwt_secret)

    if settings.supabase_project_url and settings.supabase_anon_key:
        return await _verify_remote(
            token, settings.supabase_project_url, settings.supabase_anon_key
        )

    return None


def _auth_configured() -> bool:
    s = get_settings()
    return bool(s.supabase_jwt_secret or (s.supabase_project_url and s.supabase_anon_key))


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthUser:
    """Require a valid Supabase session. 401 when absent/invalid."""
    if not _auth_configured():
        raise HTTPException(
            status_code=503,
            detail="Auth is not configured on the server. Set SUPABASE_JWT_SECRET "
                   "(or SUPABASE_PROJECT_URL + SUPABASE_ANON_KEY).",
        )
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await _authenticate(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[AuthUser]:
    """Return the user when a valid token is present, else None. Never raises —
    used by endpoints that work anonymously but attach data to accounts."""
    if credentials is None or not _auth_configured():
        return None
    return await _authenticate(credentials.credentials)
