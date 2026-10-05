"""Public API - isim akisi, oturum ve (Task 6'da) upload.

Public kullanicilar birbirlerinin dosyalarini GOREMEZ; klasor adi
tahmin edilerek baskasina upload yapilamaz - upload yalnizca gecerli
oturum token'ina bagli user icin calisir.
"""

from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import PublicSession, User, utcnow
from ..security import hash_token, new_token
from ..settings_service import get_public_config
from ..storage import ensure_user_tree, sanitize_display_name, unique_folder_name

router = APIRouter(prefix="/api", tags=["public"])

SESSION_COOKIE = "wm_session"
SESSION_DAYS = 7


class SessionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    if_exists: Optional[Literal["reuse", "new"]] = None


def client_ip(request: Request) -> str:
    settings = get_settings()
    forwarded = request.headers.get("x-forwarded-for")
    if settings.trust_proxy and forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_api_header(request: Request) -> None:
    """Cross-origin form POST'larini engelleyen basit CSRF savunmasi
    (ozel header'i cross-origin form gonderemez)."""
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        raise HTTPException(status_code=403, detail="Geçersiz istek.")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Önce adınızı yazın.")
    session = db.get(PublicSession, hash_token(token))
    if session is None or session.expires_at < utcnow():
        raise HTTPException(status_code=401, detail="Oturumunuz sona erdi. Lütfen tekrar adınızı yazın.")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Oturumunuz sona erdi. Lütfen tekrar adınızı yazın.")
    return user


@router.get("/config")
def read_config(db: Session = Depends(get_db)):
    settings = get_settings()
    return get_public_config(db, settings.max_upload_size_mb)


@router.get("/health")
def health(db: Session = Depends(get_db)):
    settings = get_settings()
    from ..storage import check_storage

    storage = check_storage(settings.upload_root, settings.require_storage_marker)
    db_ok = db.execute(select(1)).scalar() == 1
    status_code = 200 if (db_ok and storage.ok) else 503
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if status_code == 200 else "degraded",
            "db_ok": db_ok,
            "storage_ok": storage.ok,
            "storage_message": storage.message,
        },
    )


def _purge_expired_sessions(db: Session) -> None:
    db.execute(delete(PublicSession).where(PublicSession.expires_at < utcnow()))


@router.post("/session")
def create_session(
    body: SessionRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    require_api_header(request)
    if not request.app.state.session_limiter.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail="Çok fazla deneme yaptınız. Lütfen birazdan tekrar deneyin.")

    settings = get_settings()
    display_name = " ".join(body.name.split())
    if not display_name:
        raise HTTPException(status_code=422, detail="Lütfen adınızı yazın.")

    folder_base = sanitize_display_name(display_name)
    _purge_expired_sessions(db)

    # Buyuk/kucuk harf farki ayni kisiyi yakalamali (Erhan ~ erhan).
    existing = {
        u for u in db.scalars(select(User.folder_name)).all()
    }
    match = next((f for f in existing if f.casefold() == folder_base.casefold()), None)

    if match is not None and body.if_exists is None:
        return _name_exists_response(match)

    if match is not None and body.if_exists == "reuse":
        user = db.scalars(select(User).where(User.folder_name == match)).one()
    else:
        folder_name = (
            folder_base
            if match is None
            else unique_folder_name(folder_base, existing)
        )
        user = User(display_name=display_name, folder_name=folder_name)
        db.add(user)
        db.flush()
        ensure_user_tree(settings.upload_root, folder_name)

    token = new_token()
    db.add(
        PublicSession(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=SESSION_DAYS),
        )
    )
    db.commit()

    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return {"user": _user_dict(user), "existed": match is not None}


def _name_exists_response(folder_name: str):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=409,
        content={
            "detail": "Bu isim daha önce kullanılmış.",
            "existed": True,
            "folder_name": folder_name,
        },
    )


def _user_dict(user: User) -> dict:
    return {"id": user.id, "display_name": user.display_name, "folder_name": user.folder_name}


@router.get("/me")
def read_me(user: User = Depends(get_current_user)):
    return {"user": _user_dict(user)}
