"""Newsletter email signup endpoint."""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db import get_session
from app.models.newsletter import EmailSubscriber

log = logging.getLogger(__name__)

router = APIRouter(tags=["newsletter"])

# ---------------------------------------------------------------------------
# IP-based rate limiting (in-memory, resets on restart — fine for this use case)
# ---------------------------------------------------------------------------
_subscribe_attempts: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 3600  # 1 hour
RATE_LIMIT_MAX = 5  # max 5 subscribe attempts per IP per hour

# Max email length per RFC 5321
MAX_EMAIL_LENGTH = 320

# Simple but strict email regex — no need for full RFC 5322 parser
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)


def _check_ip_rate_limit(client_ip: str) -> None:
    """Enforce per-IP rate limit on subscribe attempts."""
    now = time.monotonic()
    attempts = _subscribe_attempts[client_ip]
    # Prune old entries
    _subscribe_attempts[client_ip] = [t for t in attempts if now - t < RATE_LIMIT_WINDOW]
    if len(_subscribe_attempts[client_ip]) >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")
    _subscribe_attempts[client_ip].append(now)


class SubscribeRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) > MAX_EMAIL_LENGTH:
            raise ValueError("Invalid email address")
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        # Must have at least one dot in domain part
        domain = v.rsplit("@", 1)[1]
        if "." not in domain:
            raise ValueError("Invalid email address")
        return v


@router.post("/newsletter/subscribe")
async def subscribe(
    body: SubscribeRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    # Rate limit by IP
    client_ip = request.client.host if request.client else "unknown"
    _check_ip_rate_limit(client_ip)

    # Check if already subscribed — return success either way (no info leakage)
    existing = await session.execute(
        select(EmailSubscriber.id).where(EmailSubscriber.email == body.email)
    )
    if existing.scalar_one_or_none() is not None:
        return {"status": "ok"}

    subscriber = EmailSubscriber(email=body.email)
    session.add(subscriber)
    await session.commit()
    log.info("New email subscriber: %s", body.email[:3] + "***")
    return {"status": "ok"}
