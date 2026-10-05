"""Admin API - kimlik dogrulama, panel verileri, galeri, ZIP, QR.

Admin endpointleri public upload akisindan tamamen ayri bir guvenlik
katmanina sahiptir: opak DB session cookie + CSRF double-submit +
brute-force korumasi (spec #23).
"""

import io
import logging
import shutil
import sqlite3
import time
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Optional

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from ..config import get_settings
from ..db import get_db
from ..models import AdminSession, Setting, Upload, User, utcnow
from ..security import hash_token, new_token, verify_password
from ..settings_service import DEFAULTS, get_setting, set_setting
from ..storage import check_storage, safe_join
from ..zipstream import stream_zip
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


# ---------- panel verileri ----------


def _safe_upload_path(settings, record: Upload) -> Optional[Path]:
    """DB'deki storage_path'i guvenli sekilde gercek yola cevirir."""
    try:
        return safe_join(settings.upload_root, *record.storage_path.split("/"))
    except ValueError:
        logger.error("Invalid storage_path in DB: %s", record.storage_path)
        return None


def _file_dict(settings, record: Upload) -> dict:
    path = _safe_upload_path(settings, record)
    return {
        "id": record.id,
        "original_filename": record.original_filename,
        "stored_filename": record.stored_filename,
        "media_type": record.media_type,
        "mime_type": record.mime_type,
        "size": record.size,
        "has_thumbnail": record.has_thumbnail,
        "created_at": record.created_at.isoformat(),
        "exists_on_disk": path is not None and path.is_file(),
    }


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    return user


@router.get("/stats")
def stats(admin: AdminSession = Depends(get_admin_session), db: Session = Depends(get_db)):
    settings = get_settings()
    total_users = db.query(func.count(User.id)).scalar() or 0

    media_rows = db.query(
        Upload.media_type, func.count(Upload.id), func.coalesce(func.sum(Upload.size), 0)
    ).group_by(Upload.media_type).all()
    by_media = {row[0]: {"count": row[1], "size": row[2]} for row in media_rows}
    photos = by_media.get("image", {"count": 0, "size": 0})
    videos = by_media.get("video", {"count": 0, "size": 0})
    total_files = photos["count"] + videos["count"]
    total_size = photos["size"] + videos["size"]

    storage = check_storage(settings.upload_root, settings.require_storage_marker)
    used_percent = 0
    if storage.total_bytes > 0:
        used_percent = round(100 * (storage.total_bytes - storage.free_bytes) / storage.total_bytes, 1)

    return {
        "users": total_users,
        "photos": photos["count"],
        "videos": videos["count"],
        "files": total_files,
        "total_size": total_size,
        "storage": {
            "ok": storage.ok,
            "message": storage.message,
            "total_bytes": storage.total_bytes,
            "free_bytes": storage.free_bytes,
            "used_percent": used_percent,
            "warning": used_percent >= 90,
        },
    }


@router.get("/users")
def list_users(admin: AdminSession = Depends(get_admin_session), db: Session = Depends(get_db)):
    rows = (
        db.query(User, func.count(Upload.id), func.coalesce(func.sum(Upload.size), 0))
        .outerjoin(Upload, Upload.user_id == User.id)
        .group_by(User.id)
        .order_by(User.created_at.desc())
        .all()
    )
    return {
        "users": [
            {
                "id": user.id,
                "display_name": user.display_name,
                "folder_name": user.folder_name,
                "file_count": count,
                "total_size": size,
                "created_at": user.created_at.isoformat(),
            }
            for user, count, size in rows
        ]
    }


@router.get("/users/{user_id}")
def user_detail(user_id: int, admin: AdminSession = Depends(get_admin_session), db: Session = Depends(get_db)):
    settings = get_settings()
    user = _get_user_or_404(db, user_id)
    records = (
        db.query(Upload).filter(Upload.user_id == user.id).order_by(Upload.created_at.desc()).all()
    )
    return {
        "id": user.id,
        "display_name": user.display_name,
        "folder_name": user.folder_name,
        "created_at": user.created_at.isoformat(),
        "files": [_file_dict(settings, r) for r in records],
    }


def _delete_upload_files(settings, record: Upload) -> None:
    """Orijinal dosya ve thumbnail'i diskten kaldirir."""
    path = _safe_upload_path(settings, record)
    if path is not None and path.is_file():
        path.unlink()
    thumb = path.parent.parent / "thumbs" / f"{path.stem}.webp" if path else None
    if thumb is not None and thumb.is_file():
        thumb.unlink()


@router.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    admin: AdminSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    record = db.get(Upload, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı.")
    _delete_upload_files(settings, record)
    db.delete(record)
    db.commit()
    logger.info("File deleted id=%s name=%s", file_id, record.stored_filename)
    return {"ok": True}


class BatchDeleteRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


@router.post("/files/delete-batch")
def delete_files_batch(
    body: BatchDeleteRequest,
    admin: AdminSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    deleted = 0
    for file_id in body.ids:
        record = db.get(Upload, file_id)
        if record is None:
            continue
        _delete_upload_files(settings, record)
        db.delete(record)
        deleted += 1
    db.commit()
    logger.info("Batch delete: %d files", deleted)
    return {"ok": True, "deleted": deleted}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin: AdminSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    user = _get_user_or_404(db, user_id)
    folder = safe_join(settings.upload_root, user.folder_name)
    db.delete(user)  # cascade: uploads + public_sessions
    db.commit()
    if folder.is_dir():
        shutil.rmtree(folder)
        logger.warning("User folder deleted: %s", user.folder_name)
    return {"ok": True}


@router.get("/files/{file_id}/download")
def download_file(
    file_id: int,
    admin: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    record = db.get(Upload, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı.")
    path = _safe_upload_path(settings, record)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Dosya diskte bulunamadı.")
    return FileResponse(
        path,
        media_type=record.mime_type,
        filename=record.original_filename,
    )


@router.get("/thumbs/{file_id}")
def download_thumb(
    file_id: int,
    admin: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    record = db.get(Upload, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı.")
    path = _safe_upload_path(settings, record)
    if path is None:
        raise HTTPException(status_code=404, detail="Önizleme bulunamadı.")
    thumb = path.parent.parent / "thumbs" / f"{path.stem}.webp"
    if not thumb.is_file():
        raise HTTPException(status_code=404, detail="Önizleme bulunamadı.")
    return FileResponse(thumb, media_type="image/webp")


@router.get("/users/{user_id}/zip")
def download_user_zip(
    user_id: int,
    admin: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    user = _get_user_or_404(db, user_id)
    records = db.query(Upload).filter(Upload.user_id == user.id).order_by(Upload.id).all()

    entries = []
    used_names: set[str] = set()
    for record in records:
        path = _safe_upload_path(settings, record)
        if path is None or not path.is_file():
            continue
        arcname = record.original_filename or record.stored_filename
        base = arcname
        i = 2
        while arcname in used_names:
            stem, dot, ext = base.rpartition(".")
            arcname = f"{stem}_{i}.{ext}" if dot else f"{base}_{i}"
            i += 1
        used_names.add(arcname)
        entries.append((path, arcname))

    if not entries:
        raise HTTPException(status_code=404, detail="Bu kullanıcı için indirilecek dosya yok.")

    zip_name = f"{user.folder_name}-anilari.zip"
    return StreamingResponse(
        stream_zip(entries),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )


@router.get("/qr.png")
def qr_code_png(
    request: Request,
    size: int = 1024,
    admin: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    size = max(256, min(2048, size))
    url = get_setting(db, "public_url") or get_settings().public_url
    if not url:
        url = str(request.base_url).rstrip("/")

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=max(2, size // 49),
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#5B5450", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


# ---------- ayarlar ----------


class SettingsUpdate(BaseModel):
    wedding_title: Optional[str] = Field(None, max_length=120)
    welcome_text: Optional[str] = Field(None, max_length=400)
    upload_welcome_text: Optional[str] = Field(None, max_length=400)
    success_text: Optional[str] = Field(None, max_length=400)
    public_url: Optional[str] = Field(None, max_length=300)


@router.get("/settings")
def read_settings(admin: AdminSession = Depends(get_admin_session), db: Session = Depends(get_db)):
    settings = get_settings()
    values = {key: get_setting(db, key) for key in DEFAULTS}
    return {
        **values,
        "public_url": get_setting(db, "public_url") or settings.public_url,
        "admin_username": settings.admin_username,
        "max_upload_mb": settings.max_upload_size_mb,
    }


@router.put("/settings")
def update_settings(
    body: SettingsUpdate,
    admin: AdminSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    updates = body.model_dump(exclude_none=True)
    if "public_url" in updates:
        url = updates["public_url"].strip()
        if url and not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(status_code=422, detail="URL http:// veya https:// ile başlamalı.")
        updates["public_url"] = url

    for key, value in updates.items():
        if key in DEFAULTS or key == "public_url":
            set_setting(db, key, value)
    db.commit()
    logger.info("Settings updated: %s", ", ".join(updates.keys()))
    return {"ok": True}


# ---------- bakim ----------


@router.post("/cleanup")
def cleanup(
    admin: AdminSession = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    """DB <-> dosya tutarliligi (spec #22).

    - Dosyasi diskte olmayan DB kayitlari silinir
    - DB'de kaydi olmayan disk dosyalari RAPORLANIR (silinmez - veri
      kaybi riski almamak icin)
    - 1 gunden eski yarim kalmis .part dosyalari temizlenir
    """
    settings = get_settings()
    removed_records = 0
    for record in db.query(Upload).all():
        path = _safe_upload_path(settings, record)
        if path is None or not path.is_file():
            db.delete(record)
            removed_records += 1
    db.commit()

    orphan_files = 0
    removed_temp = 0
    cutoff = time.time() - 24 * 3600
    for user in db.query(User).all():
        try:
            folder = safe_join(settings.upload_root, user.folder_name)
        except ValueError:
            continue
        original = folder / "original"
        if original.is_dir():
            known = {
                r.stored_filename for r in db.query(Upload).filter(Upload.user_id == user.id)
            }
            orphan_files += sum(1 for p in original.iterdir() if p.name not in known)
        tmp = folder / "tmp"
        if tmp.is_dir():
            for part in tmp.glob("*.part"):
                if part.stat().st_mtime < cutoff:
                    part.unlink(missing_ok=True)
                    removed_temp += 1

    logger.info("Cleanup done: removed_records=%d orphan_files=%d removed_temp=%d",
                removed_records, orphan_files, removed_temp)
    return {
        "ok": True,
        "removed_records": removed_records,
        "orphan_files": orphan_files,
        "removed_temp": removed_temp,
    }


@router.get("/backup.sqlite")
def backup_database(admin: AdminSession = Depends(get_admin_session)):
    settings = get_settings()
    if not settings.database_url.startswith("sqlite"):
        raise HTTPException(status_code=501, detail="Bu özellik yalnızca SQLite kurulumlarında kullanılabilir.")
    db_path = Path(settings.database_url.replace("sqlite:///", "", 1))
    if not db_path.is_file():
        raise HTTPException(status_code=503, detail="Veritabanı dosyası bulunamadı.")

    tmp_path = db_path.parent / f"backup-{uuid.uuid4().hex}.sqlite3"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(tmp_path)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

    def _remove():
        tmp_path.unlink(missing_ok=True)

    filename = f"wedding-backup-{utcnow().strftime('%Y%m%d-%H%M')}.sqlite3"
    return FileResponse(
        tmp_path,
        media_type="application/octet-stream",
        filename=filename,
        background=BackgroundTask(_remove),
    )
