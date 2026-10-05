"""Admin API - kimlik dogrulama, panel verileri, galeri, ZIP, QR.

Admin endpointleri public upload akisindan tamamen ayri bir guvenlik
katmanina sahiptir: opak DB session cookie + CSRF double-submit +
brute-force korumasi (spec #23).
"""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import AdminSession, utcnow
from ..security import hash_token, new_token, verify_password
from .public import client_ip, require_api_header

logger = logging.getLogger("wedding")

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_COOKIE = "wm_admin"
ADMIN_SESSION_HOURS = 12


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


def get_admin_session(request: Request, db: Session = Depends(get_db)) -> AdminSession:
    token = request.cookies.get(ADMIN_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Oturumunuz sona erdi. Lütfen tekrar giriş yapın.")
    session = db.get(AdminSession, hash_token(token))
    if session is None or session.expires_at < utcnow():
        raise HTTPException(status_code=401, detail="Oturumunuz sona erdi. Lütfen tekrar giriş yapın.")
    return session


def require_csrf(request: Request, admin: AdminSession = Depends(get_admin_session)) -> AdminSession:
    """Mutating admin isteklerinde X-CSRF-Token zorunludur.

    Cookie SameSite=Strict oldugu icin cross-site CSRF zaten engellenir;
    bu katman ayni origin'deki XSS disi senaryolara karsi ek savunmadir.
    """
    if request.headers.get("x-csrf-token") != admin.csrf_token:
        raise HTTPException(status_code=403, detail="Güvenlik doğrulaması başarısız. Sayfayı yenileyin.")
    return admin


def _admin_login_key(request: Request) -> str:
    return f"login-fail:{client_ip(request)}"


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    require_api_header(request)
    settings = get_settings()

    if not settings.admin_password_hash:
        logger.error("Admin login attempted but ADMIN_PASSWORD_HASH is not configured")
        raise HTTPException(
            status_code=503,
            detail="Yönetici hesabı yapılandırılmamış. Kurulum talimatları için sunucu loglarına bakın.",
        )

    limiter = request.app.state.login_failure_limiter
    key = _admin_login_key(request)
    if limiter.is_limited(key):
        raise HTTPException(
            status_code=429,
            detail="Çok fazla hatalı deneme yaptınız. Lütfen 15 dakika sonra tekrar deneyin.",
        )

    username_ok = body.username == settings.admin_username
    password_ok = verify_password(body.password, settings.admin_password_hash)
    if not (username_ok and password_ok):
        limiter.record(key)
        logger.warning("Admin login failed from %s", client_ip(request))
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı.")

    limiter.clear(key)
    db.execute(delete(AdminSession).where(AdminSession.expires_at < utcnow()))

    token = new_token()
    csrf_token = new_token()
    db.add(
        AdminSession(
            token_hash=hash_token(token),
            username=body.username,
            csrf_token=csrf_token,
            expires_at=utcnow() + timedelta(hours=ADMIN_SESSION_HOURS),
        )
    )
    db.commit()
    logger.info("Admin login ok from %s", client_ip(request))

    response.set_cookie(
        ADMIN_COOKIE,
        token,
        max_age=ADMIN_SESSION_HOURS * 3600,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/",
    )
    return {"username": body.username, "csrf_token": csrf_token}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    admin: AdminSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    db.delete(admin)
    db.commit()
    response.delete_cookie(ADMIN_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(admin: AdminSession = Depends(get_admin_session)):
    return {"username": admin.username}
