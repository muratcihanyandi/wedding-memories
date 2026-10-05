"""FastAPI uygulama fabrikasi.

uvicorn app.main:create_app --factory seklinde calisir.
Module-level app YOKTUR - testler her seferinde kendi ortamlariyla
yeni uygulama olusturur.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .db import create_all, init_engine
from .rate_limit import SlidingWindowLimiter
from .routes import admin, public
from .storage import check_storage

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger("wedding")


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

    return app
