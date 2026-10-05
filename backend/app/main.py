"""FastAPI uygulama fabrikasi.

uvicorn app.main:create_app --factory seklinde calisir.
Module-level app YOKTUR - testler her seferinde kendi ortamlariyla
yeni uygulama olusturur.

Katmanlar:
  SecurityHeadersMiddleware  - CSP, clickjacking, MIME sniffing korumasi
  AccessLogMiddleware        - API istekleri icin formatli log (spec #35)
  /api/* routers             - public + admin API
  /assets + SPA fallback     - derlenmis React arayuzu (frontend/dist)
"""

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from .config import get_settings
from .db import create_all, init_engine
from .rate_limit import SlidingWindowLimiter
from .routes import admin, public
from .storage import check_storage, safe_join

logger = logging.getLogger("wedding")

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)

# Script/style fontlar self-host; React inline style attribute'lari icin
# style-src 'unsafe-inline' gerekir (script-src kesinlikle kapali kalir).
CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' blob: data:; "
    "media-src 'self' blob:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware:
    """Tum yanitlara HTTP guvenlik header'lari ekler (spec #23)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["x-content-type-options"] = "nosniff"
                headers["x-frame-options"] = "DENY"
                headers["referrer-policy"] = "strict-origin-when-cross-origin"
                headers["content-security-policy"] = CSP
            await send(message)

        await self.app(scope, receive, send_with_headers)


class AccessLogMiddleware:
    """API isteklerini loglar; /api/health (healthcheck) ve statik
    dosyalar loglanmaz."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        skip = not path.startswith("/api") or path == "/api/health"
        if skip:
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        status_holder = {"code": 0}

        async def send_logged(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_logged)
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "%s %s -> %d (%.0f ms)",
                scope.get("method", "?"), path, status_holder["code"], duration_ms,
            )


def _find_frontend_dist() -> Path | None:
    """Derlenmis arayuzu arar.

    FRONTEND_DIST acikca verildiyse o yol esas alinir (yoksa arayuz
    derlenmemis sayilir); verilmemisse repo frontend/dist ve Docker
    /app/static yollari denenir.
    """
    settings = get_settings()
    if settings.frontend_dist:
        if (settings.frontend_dist / "index.html").is_file():
            return settings.frontend_dist
        return None
    for candidate in (
        Path(__file__).resolve().parents[2] / "frontend" / "dist",
        Path("/app/static"),
    ):
        if (candidate / "index.html").is_file():
            return candidate
    return None


def _is_api_path(full_path: str) -> bool:
    return full_path == "api" or full_path.startswith("api/")


def create_app() -> FastAPI:
    settings = get_settings()

    init_engine(settings.database_url)
    create_all()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        storage = check_storage(settings.upload_root, settings.require_storage_marker)
        if storage.ok:
            logger.info("Storage ready: %s", settings.upload_root)
        else:
            logger.warning("Storage NOT ready: %s (%s)", settings.upload_root, storage.message)
        if not settings.admin_password_hash:
            logger.warning(
                "ADMIN_PASSWORD_HASH tanimli degil - admin girisi kapali. "
                "Kurulum icin: python scripts/generate_admin_hash.py"
            )
        yield

    app = FastAPI(
        title="Wedding Memories",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.session_limiter = SlidingWindowLimiter(60, 3600)
    app.state.upload_limiter = SlidingWindowLimiter(settings.upload_max_per_hour, 3600)
    app.state.login_failure_limiter = SlidingWindowLimiter(
        settings.login_max_failures, settings.login_window_minutes * 60
    )

    app.include_router(public.router)
    app.include_router(admin.router)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request, exc):
        return JSONResponse(
            status_code=422,
            content={"detail": "Geçersiz istek. Lütfen girdiğiniz bilgileri kontrol edin."},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request, exc):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Bir hata oluştu. Lütfen tekrar deneyin."},
        )

    # ---------- arayuz (SPA) ----------

    dist = _find_frontend_dist()
    if dist is not None:
        assets_dir = dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            if _is_api_path(full_path):
                raise HTTPException(status_code=404, detail="Sayfa bulunamadı.")
            if full_path:
                try:
                    candidate = safe_join(dist, *full_path.split("/"))
                except ValueError:
                    candidate = None
                if candidate is not None and candidate.is_file():
                    return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    else:

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_not_built(full_path: str):
            if _is_api_path(full_path):
                raise HTTPException(status_code=404, detail="Sayfa bulunamadı.")
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Arayüz henüz derlenmemiş. frontend klasöründe 'npm run build' çalıştırın."
                },
            )

    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    return app
