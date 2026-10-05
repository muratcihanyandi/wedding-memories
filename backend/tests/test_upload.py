"""Upload API testleri - streaming, validasyon, thumbnail, DB tutarliligi."""

import io

from PIL import Image

from app import db as app_db
from app.models import Upload, User

HEADERS = {"x-requested-with": "XMLHttpRequest"}


def _png_bytes(color=(246, 231, 228)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (255, 220, 210)).save(buf, format="JPEG")
    return buf.getvalue()


MP4_BYTES = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41" + b"\x00" * 64
EXE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 32


def _login(client, name="Erhan"):
    res = client.post("/api/session", json={"name": name}, headers=HEADERS)
    assert res.status_code == 200
    return res.json()["user"]


def _upload(client, filename, data, content_type):
    return client.post(
        "/api/uploads",
        files={"files": (filename, data, content_type)},
        headers=HEADERS,
    )


def test_upload_image_stores_file_and_thumbnail(client):
    user = _login(client, "Erhan")
    res = _upload(client, "IMG_1234.JPG", _jpeg_bytes(), "image/jpeg")
    assert res.status_code == 200
    body = res.json()["results"][0]
    assert body["status"] == "ok"
    assert body["media_type"] == "image"
    assert body["has_thumbnail"] is True

    original = client.upload_root / "Erhan" / "original" / "IMG_1234.JPG"
    thumb = client.upload_root / "Erhan" / "thumbs" / "IMG_1234.webp"
    assert original.is_file()
    assert original.read_bytes() == _jpeg_bytes() or original.stat().st_size > 0
    assert thumb.is_file()

    with app_db._SessionLocal() as db:
        record = db.query(Upload).one()
        assert record.user_id == user["id"]
        assert record.original_filename == "IMG_1234.JPG"
        assert record.storage_path == "Erhan/original/IMG_1234.JPG"


def test_upload_multiple_files(client):
    _login(client, "Erhan")
    res = client.post(
        "/api/uploads",
        files=[
            ("files", ("a.png", _png_bytes(), "image/png")),
            ("files", ("b.png", _png_bytes((255, 255, 255)), "image/png")),
            ("files", ("video.mp4", MP4_BYTES, "video/mp4")),
        ],
        headers=HEADERS,
    )
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) == 3
    assert all(r["status"] == "ok" for r in results)
    with app_db._SessionLocal() as db:
        assert db.query(Upload).count() == 3


def test_upload_rejects_executable(client):
    _login(client, "Erhan")
    res = _upload(client, "virus.exe", EXE_BYTES, "application/x-msdownload")
    assert res.status_code == 415
    assert "desteklenmiyor" in res.json()["detail"]
    with app_db._SessionLocal() as db:
        assert db.query(Upload).count() == 0
    assert not any((client.upload_root / "Erhan" / "original").iterdir())


def test_upload_rejects_php_with_fake_extension(client):
    _login(client, "Erhan")
    php = b"<?php system($_GET['c']); ?>" + b"\x00" * 16
    res = _upload(client, "fotograf.jpg", php, "image/jpeg")
    assert res.status_code == 415
    with app_db._SessionLocal() as db:
        assert db.query(Upload).count() == 0


def test_upload_rejects_oversize(client_factory):
    client = client_factory(MAX_UPLOAD_SIZE_MB=1)
    _login(client, "Erhan")
    big = b"a" * (1024 * 1024 + 100)
    res = _upload(client, "buyuk.jpg", b"\xff\xd8\xff\xe0" + big, "image/jpeg")
    assert res.status_code == 413
    assert "çok büyük" in res.json()["detail"]
    with app_db._SessionLocal() as db:
        assert db.query(Upload).count() == 0
    tmp_dir = client.upload_root / "Erhan" / "tmp"
    assert not any(tmp_dir.iterdir()), "gecici dosya temizlenmeli"


def test_upload_rejects_empty_file(client):
    _login(client, "Erhan")
    res = _upload(client, "bos.jpg", b"", "image/jpeg")
    assert res.status_code == 422
    with app_db._SessionLocal() as db:
        assert db.query(Upload).count() == 0


def test_upload_requires_session(client):
    res = _upload(client, "foto.jpg", _jpeg_bytes(), "image/jpeg")
    assert res.status_code == 401


def test_upload_storage_unhealthy(client_factory):
    client = client_factory(REQUIRE_STORAGE_MARKER="true")
    _login(client, "Erhan")
    res = _upload(client, "foto.jpg", _jpeg_bytes(), "image/jpeg")
    assert res.status_code == 503
    assert res.json()["detail"] == "Depolama cihazı bağlı değil."


def test_upload_filename_collision(client):
    _login(client, "Erhan")
    _upload(client, "IMG_1234.jpg", _jpeg_bytes(), "image/jpeg")
    res = _upload(client, "IMG_1234.jpg", _jpeg_bytes(), "image/jpeg")
    assert res.status_code == 200
    assert res.json()["results"][0]["stored_filename"] == "IMG_1234_2.jpg"
    original_dir = client.upload_root / "Erhan" / "original"
    assert sorted(p.name for p in original_dir.iterdir()) == ["IMG_1234.jpg", "IMG_1234_2.jpg"]


def test_upload_filename_traversal_neutralized(client):
    _login(client, "Erhan")
    res = _upload(client, "..\\..\\evil.jpg", _jpeg_bytes(), "image/jpeg")
    assert res.status_code == 200
    original_dir = client.upload_root / "Erhan" / "original"
    names = [p.name for p in original_dir.iterdir()]
    assert names == ["evil.jpg"]
    assert (client.upload_root / "evil.jpg").exists() is False


def test_upload_video_no_thumbnail(client):
    _login(client, "Erhan")
    res = _upload(client, "video.mp4", MP4_BYTES, "video/mp4")
    assert res.status_code == 200
    body = res.json()["results"][0]
    assert body["media_type"] == "video"
    assert body["has_thumbnail"] is False
    assert (client.upload_root / "Erhan" / "original" / "video.mp4").is_file()


def test_upload_heic_accepted_without_thumbnail(client):
    _login(client, "Erhan")
    heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 32
    res = _upload(client, "foto.heic", heic, "image/heic")
    assert res.status_code == 200
    body = res.json()["results"][0]
    assert body["status"] == "ok"
    assert body["media_type"] == "image"
    assert (client.upload_root / "Erhan" / "original" / "foto.heic").is_file()


def test_upload_turkish_filename_transliterated(client):
    _login(client, "Erhan")
    res = _upload(client, "fotoğrafım.jpg", _jpeg_bytes(), "image/jpeg")
    assert res.status_code == 200
    assert res.json()["results"][0]["stored_filename"] == "fotografim.jpg"


def test_upload_binds_files_to_owning_user(client):
    erhan = _login(client, "Erhan")
    _upload(client, "foto.jpg", _jpeg_bytes(), "image/jpeg")
    with app_db._SessionLocal() as db:
        record = db.query(Upload).one()
        assert record.user_id == erhan["id"]
        owner = db.get(User, record.user_id)
        assert owner.folder_name == "Erhan"
