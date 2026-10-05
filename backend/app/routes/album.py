"""Public album API'si - /album sayfasi.

Bu endpointler GIRIS GEREKTIRMEZ: /album, misafirlerin paylastigi
anilarin herkese acik galerisidir (kullanici talebiyle public yapildi).
Linki bilen herkes fotoğraf/videolari gorebilir ve indirebilir.
Yonetim islemleri (silme, ayarlar, kullanicilar) admin API'sinde
korumali kalir. Dosyalar yine dogrudan diskten degil, bu API uzerinden
guvenli sekilde servis edilir.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Upload, User
from ..zipstream import stream_zip
from .admin import _file_dict, _safe_upload_path

logger = logging.getLogger("wedding")

router = APIRouter(prefix="/api/album", tags=["album"])


@router.get("/files")
def album_files(db: Session = Depends(get_db)):
    """Tum kullanicilarin tum dosyalari - yukleyen adiyla, en yeniden
    eskiye sirali."""
    settings = get_settings()
    rows = (
        db.query(Upload, User.display_name, User.folder_name)
        .join(User, Upload.user_id == User.id)
        .order_by(Upload.created_at.desc())
        .all()
    )
    return {
        "total": len(rows),
        "files": [
            {
                **_file_dict(settings, upload),
                "uploader": display_name,
                "folder_name": folder_name,
            }
            for upload, display_name, folder_name in rows
        ],
    }


def _build_zip_entries(settings, db: Session, mode: str) -> list:
    rows = (
        db.query(Upload, User.folder_name)
        .join(User, Upload.user_id == User.id)
        .order_by(Upload.user_id, Upload.id)
        .all()
    )

    entries = []
    used_names: set[str] = set()
    for record, folder_name in rows:
        path = _safe_upload_path(settings, record)
        if path is None or not path.is_file():
            continue
        base_name = record.original_filename or record.stored_filename
        # flat: tek klasor; grouped: her yukleyen kendi klasorunde
        arcname = base_name if mode == "flat" else f"{folder_name}/{base_name}"
        candidate = arcname
        i = 2
        while candidate in used_names:
            stem, dot, ext = arcname.rpartition(".")
            candidate = f"{stem}_{i}.{ext}" if dot else f"{arcname}_{i}"
            i += 1
        used_names.add(candidate)
        entries.append((path, candidate))
    return entries


@router.get("/zip")
def album_zip(mode: str = "grouped", db: Session = Depends(get_db)):
    """Tum anilar tek ZIP arsivinde (streaming, RAM dostu).

    mode=grouped (varsayilan): her yukleyen icin ayri klasor
        (Erhan/IMG_1234.jpg, Ayse/video.mp4)
    mode=flat: tum dosyalar tek klasorde; cakisan isimler _2, _3...
        ile ayristirilir
    """
    if mode not in ("grouped", "flat"):
        mode = "grouped"
    settings = get_settings()
    entries = _build_zip_entries(settings, db, mode)
    if not entries:
        raise HTTPException(status_code=404, detail="Henüz indirilecek dosya yok.")

    filename = "dugun-anilari.zip" if mode == "grouped" else "dugun-anilari-tek-klasor.zip"
    logger.info("Album zip requested mode=%s files=%d", mode, len(entries))
    return StreamingResponse(
        stream_zip(entries),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/thumbs/{file_id}")
def album_thumb(file_id: int, db: Session = Depends(get_db)):
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


@router.get("/files/{file_id}/download")
def album_download(file_id: int, db: Session = Depends(get_db)):
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
