"""App assembly testleri - middleware, SPA fallback, hata handler'lari."""

HEADERS = {"x-requested-with": "XMLHttpRequest"}


def _make_dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><html><head><title>Wedding</title></head><body><div id=root></div></body></html>",
        encoding="utf-8",
    )
    (dist / "assets" / "app.js").write_text("console.log('app')", encoding="utf-8")
    (dist / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
    return dist


def test_security_headers_present(client):
    res = client.get("/api/config")
    assert res.status_code == 200
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in res.headers["content-security-policy"]
    assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_spa_not_built_returns_503(client_factory, tmp_path):
    # FRONTEND_DIST gecersemeyen bir yola isaret ederse arayuz derlenmemis
    # sayilir (repo'daki gercek frontend/dist'ten etkilenmemek icin).
    client = client_factory(FRONTEND_DIST=str(tmp_path / "yok"))
    res = client.get("/")
    assert res.status_code == 503
    assert "derlenmemiş" in res.json()["detail"]


def test_spa_serves_index_for_frontend_routes(client_factory, tmp_path):
    dist = _make_dist(tmp_path)
    client = client_factory(FRONTEND_DIST=str(dist))

    for path in ["/", "/upload", "/success", "/admin", "/admin/users", "/admin/users/5"]:
        res = client.get(path)
        assert res.status_code == 200, path
        assert "text/html" in res.headers["content-type"]
        assert "id=root" in res.text


def test_spa_serves_static_assets(client_factory, tmp_path):
    dist = _make_dist(tmp_path)
    client = client_factory(FRONTEND_DIST=str(dist))

    res = client.get("/assets/app.js")
    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"]

    res = client.get("/favicon.ico")
    assert res.status_code == 200


def test_spa_traversal_blocked(client_factory, tmp_path):
    dist = _make_dist(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("gizli", encoding="utf-8")
    client = client_factory(FRONTEND_DIST=str(dist))

    res = client.get("/../secret.txt")
    assert res.status_code in (200, 404)
    if res.status_code == 200:
        assert "gizli" not in res.text


def test_api_routes_take_precedence_over_spa(client_factory, tmp_path):
    dist = _make_dist(tmp_path)
    client = client_factory(FRONTEND_DIST=str(dist))

    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res = client.get("/api/yok-boyle")
    assert res.status_code == 404
    assert res.json()["detail"] == "Sayfa bulunamadı."


def test_validation_error_returns_turkish(client):
    res = client.post(
        "/api/session",
        json={"name": ""},
        headers=HEADERS,
    )
    assert res.status_code == 422
    assert "Geçersiz istek" in res.json()["detail"]
