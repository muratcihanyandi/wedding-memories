"""/album API testleri - tum anilar galerisi."""

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


def _admin_login(client):
    res = client.post(
        "/api/admin/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        headers=HEADERS,
    )
    assert res.status_code == 200
    return {"x-requested-with": "XMLHttpRequest", "x-csrf-token": res.json()["csrf_token"]}


def _create_user_with_uploads(client, name, files):
    res = client.post("/api/session", json={"name": name}, headers=HEADERS)
    assert res.status_code == 200
    for filename, data, ctype in files:
        res = client.post(
            "/api/uploads",
            files={"files": (filename, data, ctype)},
            headers=HEADERS,
        )
        assert res.status_code == 200


def test_album_requires_admin(client):
    res = client.get("/api/album/files")
    assert res.status_code == 401
    res = client.get("/api/album/zip")
    assert res.status_code == 401


def test_album_files_lists_all_uploaders(client):
    admin_headers = _admin_login(client)
    _create_user_with_uploads(client, "Erhan", [
        ("a.jpg", _png_bytes(), "image/png"),
        ("b.jpg", _png_bytes((255, 255, 255)), "image/png"),
    ])
    _create_user_with_uploads(client, "Ayse", [
        ("v.mp4", MP4_BYTES, "video/mp4"),
    ])

    res = client.get("/api/album/files", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    uploaders = {f["uploader"] for f in data["files"]}
    assert uploaders == {"Erhan", "Ayse"}
    video = next(f for f in data["files"] if f["media_type"] == "video")
    assert video["folder_name"] == "Ayse"
    assert video["original_filename"] == "v.mp4"


def test_album_files_empty(client):
    admin_headers = _admin_login(client)
    res = client.get("/api/album/files", headers=admin_headers)
    assert res.status_code == 200
    assert res.json() == {"total": 0, "files": []}


def test_album_zip_contains_all_users(client):
    admin_headers = _admin_login(client)
    _create_user_with_uploads(client, "Erhan", [("a.jpg", _png_bytes(), "image/png")])
    _create_user_with_uploads(client, "Ayse", [("v.mp4", MP4_BYTES, "video/mp4")])

    res = client.get("/api/album/zip", headers=admin_headers)
    assert res.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(res.content))
    names = archive.namelist()
    assert sorted(names) == ["Ayse/v.mp4", "Erhan/a.jpg"]
    assert archive.read("Erhan/a.jpg") == _png_bytes()
    assert archive.testzip() is None


def test_album_zip_empty_404(client):
    admin_headers = _admin_login(client)
    res = client.get("/api/album/zip", headers=admin_headers)
    assert res.status_code == 404
