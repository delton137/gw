"""Clerk JWT verification for FastAPI.

Validates JWTs from Clerk against their JWKS endpoint.
Extracts user_id (Clerk's 'sub' claim) from the verified token.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx
import jwt as pyjwt
from fastapi import Depends, HTTPException, Request

from app.config import settings

log = logging.getLogger(__name__)

_jwks_cache: dict | None = None
_jwks_cache_time: float = 0.0
_JWKS_CACHE_TTL = 3600  # Re-fetch JWKS every hour
_jwks_lock = asyncio.Lock()


async def _get_jwks() -> dict:
    """Fetch and cache Clerk's JWKS keys with TTL-based expiry."""
    global _jwks_cache, _jwks_cache_time

    # Fast path: return cached value without lock
    now = time.monotonic()
    if _jwks_cache is not None and (now - _jwks_cache_time) < _JWKS_CACHE_TTL:
        return _jwks_cache

    async with _jwks_lock:
        # Double-check after acquiring lock (another coroutine may have refreshed)
        now = time.monotonic()
        if _jwks_cache is not None and (now - _jwks_cache_time) < _JWKS_CACHE_TTL:
            return _jwks_cache

        async with httpx.AsyncClient() as client:
            headers = {}
            if settings.clerk_secret_key:
                headers["Authorization"] = f"Bearer {settings.clerk_secret_key}"
            resp = await client.get(
                settings.clerk_jwks_url,
                headers=headers,
                timeout=5.0,
            )
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_cache_time = now
            return _jwks_cache


async def _verify_clerk_token(request: Request, leeway: int = 60) -> str:
    """Verify a Clerk JWT and return the user_id (sub claim).

    Args:
        request: The incoming HTTP request.
        leeway: Seconds of tolerance for token expiration. Larger values
                accommodate slow uploads where the proxy buffers the full
                body before forwarding (token can expire during transfer).
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")

    token = auth_header[7:]

    if not settings.clerk_secret_key:
        raise HTTPException(
            status_code=503,
            detail="Authentication not configured",
        )

    try:
        jwks = await _get_jwks()
        from jwt.api_jwk import PyJWKSet

        jwk_set = PyJWKSet.from_dict(jwks)

        header = pyjwt.get_unverified_header(token)
        kid = header.get("kid")
        signing_key = None
        for key in jwk_set.keys:
            if key.key_id == kid:
                signing_key = key.key
                break

        if signing_key is None:
            # Key not found — maybe Clerk rotated keys. Clear cache and retry once.
            global _jwks_cache_time
            _jwks_cache_time = 0.0
            jwks = await _get_jwks()
            jwk_set = PyJWKSet.from_dict(jwks)
            for key in jwk_set.keys:
                if key.key_id == kid:
                    signing_key = key.key
                    break
            if signing_key is None:
                raise HTTPException(status_code=401, detail="Invalid token signing key")

        payload = pyjwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            leeway=leeway,
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing sub claim")
        return user_id

    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except pyjwt.InvalidTokenError as e:
        log.warning("Invalid JWT: %s", e)
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except httpx.HTTPError as e:
        log.error("Failed to fetch JWKS: %s", e)
        raise HTTPException(status_code=503, detail="Authentication service unavailable")


async def get_current_user_id(request: Request) -> str:
    """Standard auth — 60s leeway (for API reads, polling, etc.)."""
    return await _verify_clerk_token(request, leeway=60)


async def get_verified_user_id(
    user_id: str,
    auth_user_id: str = Depends(get_current_user_id),
) -> str:
    """Verify that the path parameter user_id matches the authenticated user."""
    if user_id != auth_user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return user_id


async def get_current_user_id_upload(request: Request) -> str:
    """Upload auth — 30 min leeway.

    Large file uploads (430MB+ WGS VCFs) can take 10-20+ minutes to transfer.
    Railway's reverse proxy buffers the entire request body before forwarding
    to uvicorn, so the JWT issued before upload started may be well past its
    ~60s Clerk expiry by the time FastAPI sees the request.
    """
    return await _verify_clerk_token(request, leeway=1800)
