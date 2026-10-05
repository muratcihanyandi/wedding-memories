"""Public API - isim akisi, oturum ve dosya yukleme.

Public kullanicilar birbirlerinin dosyalarini GOREMEZ; klasor adi
tahmin edilerek baskasina upload yapilamaz - upload yalnizca gecerli
oturum token'ina bagli user icin calisir.
"""

import logging
import os
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..db import get_db
from ..models import PublicSession, Upload, User, utcnow
from ..security import hash_token, new_token
from ..settings_service import get_public_config
from ..storage import (
    check_storage,
    ensure_user_tree,
    media_type_for_extension,
    relative_posix,
    sanitize_display_name,
    sanitize_filename,
    sniff_media_type,
    unique_filename,
    unique_folder_name,
)
from ..thumbnails import make_thumbnail

logger = logging.getLogger("wedding")

router = APIRouter(prefix="/api", tags=["public"])

SESSION_COOKIE = "wm_session"
SESSION_DAYS = 7

MAX_FILES_PER_REQUEST = 20
CHUNK_SIZE = 1024 * 1024  # 1 MB - dosyalar asla tamamen RAM'e alinmaz


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


# ---------- dosya yukleme ----------


class UploadRejected(Exception):
    """Dosya bazli red - Turkce mesaj ve HTTP status icerir."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _file_error(filename: str, status_code: int, message: str) -> dict:
    return {
        "filename": filename,
        "status": "error",
        "code": status_code,
        "error": message,
    }


async def _store_single(
    upload_file: UploadFile,
    user: User,
    folders: dict,
    settings,
    db: Session,
) -> dict:
    original_name = upload_file.filename or "dosya"
    ext = os.path.splitext(original_name)[1].lower()
    expected_media = media_type_for_extension(ext)
    if expected_media is None:
        raise UploadRejected(415, "Bu dosya türü desteklenmiyor. Lütfen fotoğraf veya video seçin.")

    # MIME header'i yalnizca ilk eleme icin kullanilir; asil dogrulama
    # magic byte ile yapilir (spec #10).
    content_type = (upload_file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type != "application/octet-stream" and not (
        content_type.startswith("image/") or content_type.startswith("video/")
    ):
        raise UploadRejected(415, "Bu dosya türü desteklenmiyor. Lütfen fotoğraf veya video seçin.")

    tmp_path = folders["tmp"] / f"{uuid.uuid4().hex}.part"
    logger.info("Upload started user=%s file=%s", user.folder_name, original_name)
    try:
        size = 0
        with open(tmp_path, "wb") as out:
            while True:
                chunk = await upload_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_size_bytes:
                    raise UploadRejected(413, "Bu dosya çok büyük. Lütfen daha küçük bir dosya seçin.")
                out.write(chunk)

        if size == 0:
            raise UploadRejected(422, "Bu dosya boş görünüyor.")

        sniffed = sniff_media_type(tmp_path)
        if sniffed is None or sniffed[0] != expected_media:
            raise UploadRejected(415, "Bu dosya türü desteklenmiyor. Lütfen fotoğraf veya video seçin.")
        media_type, mime = sniffed

        safe_name = sanitize_filename(original_name)
        existing = {p.name for p in folders["original"].iterdir()}
        final_name = unique_filename(safe_name, existing)
        final_path = folders["original"] / final_name
        os.replace(tmp_path, final_path)  # ayni dosya sisteminde atomik
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    has_thumbnail = False
    if media_type == "image":
        thumb_path = folders["thumbs"] / f"{Path(final_name).stem}.webp"
        has_thumbnail = await run_in_threadpool(make_thumbnail, final_path, thumb_path)

    record = Upload(
        user_id=user.id,
        original_filename=original_name[:255],
        stored_filename=final_name,
        media_type=media_type,
        mime_type=mime,
        size=size,
        storage_path=relative_posix(settings.upload_root, final_path),
        has_thumbnail=has_thumbnail,
    )
    db.add(record)
    db.flush()
    logger.info(
        "Upload completed user=%s file=%s size=%d thumb=%s",
        user.folder_name, final_name, size, has_thumbnail,
    )
    return {
        "id": record.id,
        "stored_filename": final_name,
        "size": size,
        "media_type": media_type,
        "has_thumbnail": has_thumbnail,
    }


@router.post("/uploads")
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_api_header(request)
    if not files:
        raise HTTPException(status_code=422, detail="Dosya seçilmedi.")
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=422,
            detail=f"Bir seferde en fazla {MAX_FILES_PER_REQUEST} dosya yükleyebilirsiniz.",
        )

    settings = get_settings()
    storage = check_storage(settings.upload_root, settings.require_storage_marker)
    if not storage.ok:
        logger.error("Storage unavailable: %s", storage.message)
        raise HTTPException(status_code=503, detail=storage.message or "Depolama cihazı bağlı değil.")

    folders = ensure_user_tree(settings.upload_root, user.folder_name)

    results = []
    for upload_file in files:
        if not request.app.state.upload_limiter.allow(f"upload:{client_ip(request)}"):
            results.append(
                _file_error(upload_file.filename, 429, "Çok fazla yükleme yaptınız. Lütfen birazdan tekrar deneyin.")
            )
            continue
        try:
            record = await _store_single(upload_file, user, folders, settings, db)
            results.append({"filename": upload_file.filename, "status": "ok", **record})
        except UploadRejected as exc:
            logger.warning("Upload rejected user=%s file=%s: %s", user.folder_name, upload_file.filename, exc.message)
            results.append(_file_error(upload_file.filename, exc.status_code, exc.message))
        except OSError as exc:
            logger.error("Upload failed user=%s file=%s: %s", user.folder_name, upload_file.filename, exc)
            results.append(_file_error(upload_file.filename, 500, "Dosya kaydedilemedi. Lütfen tekrar deneyin."))

    db.commit()

    # Tek dosyalik isteklerde hatanin status kodu dogrudan donsun;
    # coklu isteklerde dosya bazli sonuclar 200 ile doner.
    if len(files) == 1 and results[0]["status"] != "ok":
        raise HTTPException(status_code=results[0]["code"], detail=results[0]["error"])
    return {"results": results}
