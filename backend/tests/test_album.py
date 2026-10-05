"""/album API testleri - herkese acik tum anilar galerisi.

/album giris gerektirmez; yonetim islemleri admin API'sinde korunur.
"""

import io
import zipfile

from PIL import Image

from tests.conftest import ADMIN_PASS, ADMIN_USER

HEADERS = {"x-requested-with": "XMLHttpRequest"}


def _png_bytes(color=(246, 231, 228)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buf, format="PNG")
    return buf.getvalue()


MP4_BYTES = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41" + b"\x00" * 64


def _create_user_with_uploads(client, name, files):
    res = client.post("/api/session", json={"name": name}, headers=HEADERS)
    assert res.status_code == 200
    user = res.json()["user"]
    for filename, data, ctype in files:
        res = client.post(
            "/api/uploads",
            files={"files": (filename, data, ctype)},
            headers=HEADERS,
        )
        assert res.status_code == 200
    return user


def _seed(client):
    """2 kullanici, 3 dosya olusturur."""
    erhan = _create_user_with_uploads(client, "Erhan", [
        ("a.jpg", _png_bytes(), "image/png"),
    ])
    ayse = _create_user_with_uploads(client, "Ayse", [
        ("a.jpg", _png_bytes((255, 255, 255)), "image/png"),
        ("v.mp4", MP4_BYTES, "video/mp4"),
    ])
    return erhan, ayse


def test_album_files_public_without_login(client):
    _seed(client)
    # HICBIR cookie yok - giris gerektirmemeli
    res = client.get("/api/album/files")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    uploaders = {f["uploader"] for f in data["files"]}
    assert uploaders == {"Erhan", "Ayse"}


def test_album_files_empty(client):
    res = client.get("/api/album/files")
    assert res.status_code == 200
    assert res.json() == {"total": 0, "files": []}


def test_album_zip_grouped_mode(client):
    _seed(client)
    res = client.get("/api/album/zip")  # varsayilan grouped
    assert res.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(res.content))
    names = archive.namelist()
    # her yukleyen kendi klasorunde (ayni isimli a.jpg'ler ayrismali)
    assert "Erhan/a.jpg" in names
    assert "Ayse/a.jpg" in names
    assert "Ayse/v.mp4" in names
    assert archive.testzip() is None


def test_album_zip_flat_mode(client):
    _seed(client)
    res = client.get("/api/album/zip?mode=flat")
    assert res.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(res.content))
    names = archive.namelist()
    assert "/" not in "".join(names), "flat modda klasor olmamali"
    # a.jpg iki kez yuklenmisti - ikincisi _2 ile ayristirilmali
    # (uygulama genelindeki convention: name_2.ext)
    assert sorted(n for n in names if n.startswith("a")) == ["a.jpg", "a_2.jpg"]
    assert "v.mp4" in names
    assert archive.read("a.jpg") == _png_bytes()


def test_album_zip_invalid_mode_falls_back_to_grouped(client):
    _seed(client)
    res = client.get("/api/album/zip?mode=bilinmeyen")
    assert res.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(res.content))
    assert any("/" in n for n in archive.namelist())


def test_album_zip_empty_404(client):
    res = client.get("/api/album/zip")
    assert res.status_code == 404


def test_album_thumb_public(client):
    erhan, _ = _seed(client)
    res = client.get("/api/album/files")
    photo = next(f for f in res.json()["files"] if f["media_type"] == "image")
    res = client.get(f"/api/album/thumbs/{photo['id']}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/webp"


def test_album_thumb_video_404(client):
    _seed(client)
    res = client.get("/api/album/files")
    video = next(f for f in res.json()["files"] if f["media_type"] == "video")
    res = client.get(f"/api/album/thumbs/{video['id']}")
    assert res.status_code == 404


def test_album_download_public(client):
    _seed(client)
    res = client.get("/api/album/files")
    video = next(f for f in res.json()["files"] if f["media_type"] == "video")
    res = client.get(f"/api/album/files/{video['id']}/download")
    assert res.status_code == 200
    assert res.content == MP4_BYTES


def test_album_download_range(client):
    _seed(client)
    res = client.get("/api/album/files")
    video = next(f for f in res.json()["files"] if f["media_type"] == "video")
    res = client.get(f"/api/album/files/{video['id']}/download", headers={"Range": "bytes=0-9"})
    assert res.status_code in (200, 206)
    if res.status_code == 206:
        assert res.content == MP4_BYTES[:10]


def test_admin_endpoints_still_protected(client):
    """Album public oldu ama yonetim API'si korumali kalmali."""
    res = client.get("/api/admin/stats")
    assert res.status_code == 401
    res = client.get("/api/admin/users")
    assert res.status_code == 401
    _seed(client)
    res = client.get("/api/album/files")
    file_id = res.json()["files"][0]["id"]
    res = client.delete(f"/api/admin/files/{file_id}", headers=HEADERS)
    assert res.status_code == 401, "silme islemi oturumsuz yapilamamali"


def test_admin_can_delete_from_album_listing(client):
    from tests.test_admin_auth import _login_ok  # admin cookie + csrf

    headers = _login_ok(client)
    _seed(client)
    res = client.get("/api/album/files")
    file_id = res.json()["files"][0]["id"]
    res = client.delete(f"/api/admin/files/{file_id}", headers=headers)
    assert res.status_code == 200
    res = client.get("/api/album/files")
    assert res.json()["total"] == 2
