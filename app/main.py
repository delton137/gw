"""genewizard.net — FastAPI application."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from contextlib import asynccontextmanager

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Disable docs in production
docs_kwargs = {}
if settings.environment == "production":
    docs_kwargs = {"docs_url": None, "redoc_url": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Shutdown: cancel all background analysis tasks so uvicorn can exit cleanly
    from app.routes.upload import _background_tasks
    if _background_tasks:
        log.info("Cancelling %d background task(s)...", len(_background_tasks))
        for task in _background_tasks:
            task.cancel()


app = FastAPI(title="genewizard.net", version="0.1.0", lifespan=lifespan, **docs_kwargs)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ---------------------------------------------------------------------------
# Request ID middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ---------------------------------------------------------------------------
# Timing middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - t0
    rid = getattr(request.state, "request_id", "?")
    log.info("[%s] %s %s → %d (%.3fs)", rid, request.method, request.url.path, response.status_code, elapsed)
    return response


# ---------------------------------------------------------------------------
# Global exception handler — generic messages for users, full details in logs
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", "unknown")
    log.error("[%s] Unhandled error: %s", rid, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please try again later.",
            "request_id": rid,
        },
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

from app.routes.health import router as health_router  # noqa: E402
from app.routes.upload import router as upload_router  # noqa: E402
from app.routes.results import router as results_router  # noqa: E402
from app.routes.snp import router as snp_router  # noqa: E402
from app.routes.gene import router as gene_router  # noqa: E402
from app.routes.account import router as account_router  # noqa: E402
from app.routes.newsletter import router as newsletter_router  # noqa: E402
from app.routes.sitemap import router as sitemap_router  # noqa: E402

app.include_router(health_router)
app.include_router(upload_router, prefix="/api/v1")
app.include_router(results_router, prefix="/api/v1")
app.include_router(snp_router, prefix="/api/v1")
app.include_router(gene_router, prefix="/api/v1")
app.include_router(account_router, prefix="/api/v1")
app.include_router(newsletter_router, prefix="/api/v1")
app.include_router(sitemap_router, prefix="/api/v1")
