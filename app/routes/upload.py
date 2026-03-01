"""Upload endpoint — accepts genotype files, kicks off background analysis."""

from __future__ import annotations

import asyncio
import logging
import os
import stat

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.params import Form
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id_upload
from app.config import settings
from app.db import get_session, async_session_factory
from app.models.user import Analysis
from app.services.parser import ALLOWED_EXTENSIONS

log = logging.getLogger(__name__)

router = APIRouter()

# Ensure temp directory exists with restrictive permissions
os.makedirs(settings.temp_dir, mode=0o700, exist_ok=True)

# Magic bytes for format validation
_GZIP_MAGIC = b"\x1f\x8b"

# Strong references to background tasks — prevents garbage collection
_background_tasks: set[asyncio.Task] = set()


def _validate_magic_bytes(header: bytes) -> None:
    """Check that file is gzip or text, not a disguised executable."""
    if header[:2] == _GZIP_MAGIC:
        return
    try:
        header.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File does not appear to be a valid genotype file")


def _validate_extension(filename: str) -> None:
    """Check file extension."""
    name = filename.lower()
    if not any(name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )


async def _check_rate_limit(user_id: str, session: AsyncSession) -> None:
    """Check upload rate limit: max N uploads per user per hour."""
    result = await session.execute(
        text("""
            SELECT COUNT(*) FROM analyses
            WHERE user_id = :uid AND created_at > NOW() - INTERVAL '1 hour'
        """),
        {"uid": user_id},
    )
    count = result.scalar() or 0
    if count >= settings.upload_rate_limit:
        raise HTTPException(
            status_code=429,
            detail="Upload limit reached. Please wait before uploading again.",
        )


async def _run_analysis_in_background(analysis_id: str, user_id: str, tmp_path: str, ancestry_group: str) -> None:
    """Run unified analysis pipeline with its own database session."""
    from app.services.analysis import run_analysis_pipeline

    async with async_session_factory() as session:
        try:
            await run_analysis_pipeline(
                analysis_id=analysis_id,
                user_id=user_id,
                tmp_path=tmp_path,
                ancestry_group=ancestry_group,
                session=session,
            )
        except asyncio.CancelledError:
            log.info("Background analysis %s was cancelled", analysis_id)
        except Exception:
            log.exception("Background analysis failed for %s", analysis_id)


@router.post("/upload/")
async def upload_genotype_file(
    request: Request,
    file: UploadFile,
    ancestry_group: str = Form("EUR"),
    user_id: str = Depends(get_current_user_id_upload),
    session: AsyncSession = Depends(get_session),
):
    """Upload a genotype file and start background analysis.

    Streams the file to a temp file, validates it, creates an Analysis record,
    then kicks off the analysis pipeline as a background asyncio task.
    Returns immediately with the analysis ID for polling.
    """
    rid = getattr(request.state, "request_id", "?")

    _validate_extension(file.filename or "unknown")

    ancestry_group = ancestry_group.strip().upper()
    valid_ancestries = {"EUR", "AFR", "EAS", "SAS", "AMR"}
    if ancestry_group not in valid_ancestries:
        raise HTTPException(status_code=400, detail=f"Invalid ancestry group. Must be one of: {', '.join(sorted(valid_ancestries))}")

    await _check_rate_limit(user_id, session)

    tmp_path = None
    try:
        analysis = Analysis(user_id=user_id, status="pending", filename=file.filename)
        session.add(analysis)
        await session.commit()
        await session.refresh(analysis)

        tmp_path = os.path.join(settings.temp_dir, f"{analysis.id}.upload")
        total_size = 0
        first_chunk = True

        with open(tmp_path, "wb") as tmp_file:
            while True:
                chunk = await file.read(64 * 1024)  # 64KB chunks
                if not chunk:
                    break
                if first_chunk:
                    _validate_magic_bytes(chunk[:16])
                    first_chunk = False
                total_size += len(chunk)
                if total_size > settings.max_upload_size:
                    raise HTTPException(status_code=413, detail="File too large. Maximum size is 5GB.")
                tmp_file.write(chunk)

        if total_size == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)

        log.info("[%s] Created analysis %s for user %s (%d bytes)", rid, analysis.id, user_id, total_size)

        task = asyncio.create_task(
            _run_analysis_in_background(
                analysis_id=str(analysis.id),
                user_id=user_id,
                tmp_path=tmp_path,
                ancestry_group=ancestry_group,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        return {
            "id": str(analysis.id),
            "status": "pending",
            "created_at": analysis.created_at.isoformat(),
        }

    except Exception:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
        raise
