# Wedding Memories - Dugun QR Fotograf/Video Paylasim Sistemi Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Raspberry Pi 5 uzerinde Docker ile calisan, QR ile giris yapilan, sadece isim isteyen, mobil-first, pastel dugun temali foto/video yukleme platformu; admin paneli, galeri, ZIP indirme, QR uretimi ve storage saglik kontrolu ile birlikte.

**Architecture:** Tek uygulama container'i: FastAPI (async, streaming upload, SQLite+SQLAlchemy, WAL) hem REST API'yi hem build edilmis React SPA'sini servis eder. Medya dosyalari hicbir zaman RAM'e tam alinmaz; multipart parcalari disk uzerinde gecici dosyaya yazilir, dogrulanir, ayni dosya sisteminde atomik `os.replace` ile finalize edilir, DB kaydi sonda olusur. Upload klasoru bind mount ile `/mnt/usb` uzerindedir; DB ayri named volume'dadir. Opsiyonel nginx profili (TLS termination) uygulama kodundan bagimsizdir.

**Tech Stack:**
- Backend: Python 3.12 (Docker) / 3.11 (dev), FastAPI, Uvicorn, SQLAlchemy 2.0 (SQLite), Pillow (+ pillow-heif opsiyonel), qrcode, python-multipart, pytest + httpx
- Frontend: Vite + React 18 + react-router-dom, ozel CSS design system (UI kutuphanesi YOK), XHR ile gercek upload progress, @fontsource (self-host fontlar - internet olmayan dugun WiFi'i icin)
- Deploy: multi-stage Dockerfile (node:22-alpine build -> python:3.12-slim run), docker-compose (restart: unless-stopped, healthcheck, bind mount + named volume), opsiyonel nginx profile

**Gerekceler (spec #40):**
- FastAPI secildi cunku: async streaming request body (1GB+ dosyalar icin RAM guvenli), python-multipart dosya parcalarini 1MB sonrasi otomatik diske spill eder, Pillow'un ARM64 wheel'i hazir (thumbnail), SQLAlchemy ile PostgreSQL gecisi tek env degiskeni (DATABASE_URL), tek process dusuk RAM. Node+sharp ARM64 native build derdi tasir; Next.js SSR Pi icin gereksiz yuk.
- React SPA secildi cunku: build sonrasi saf statik dosya (Pi'de calisma zamani maliyeti sifir), kucuk dependency seti, XHR progress event ile gercek yuzde gosterimi.

---

## Kritik Tasarim Kararlari

1. **Klasor duzeni:** `UPLOAD_ROOT/<UserFolder>/original/...` + `UPLOAD_ROOT/<UserFolder>/thumbs/...` + `UPLOAD_ROOT/<UserFolder>/tmp/<uuid>` (ayni FS'te atomik rename icin). Orijinal dosya asla bozulmaz.
2. **DB:** `admin_users`, `admin_sessions`, `users`, `public_sessions`, `uploads`, `settings`. `uploads` kaydi yalnizca dosya finalize olduktan sonra insert edilir. DB kaydi olup dosya eksikse admin paneli hata vermez, "eksik" olarak isaretler; admin "Tutarlilik Kontrolu" ile orphan kayitlari temizler.
3. **Public session:** Isim girince 256-bit opaque token uretilir, DB'de sha256 hash'i tutulur, HttpOnly cookie (`wm_session`, SameSite=Lax, 7 gun). Baska kullanicinin klasorune erisim imkansizdir (klasor adi tahmin edilerek upload yapilamaz).
4. **Isim cakismasi (spec #29):** `POST /api/session {name, if_exists?}` - isim varsa ve `if_exists` yoksa 409 + `{"existed": true}` doner; frontend "Ayrı kişiysen yeni klasör oluştur / Aynı kişiyim devam et" diyalogu gosterir. `new` secilirse `Erhan-2` klasoru olusur. UX basit tutuldu.
5. **Sifre hashing:** stdlib `hashlib.pbkdf2_hmac("sha256", pwd, salt, 600_000)` - format: `pbkdf2_sha256$600000$<salt_hex>$<hash_hex>`. ARM64 native derleme gerektiren bcrypt yerine guvenli ve bagsiz cozum. Hash `.env`'de: `ADMIN_PASSWORD_HASH`. `scripts/generate_admin_hash.py` ile uretilir. Default sifre YOK; hash yoksa admin girisi acikca reddeder ve logda kurulum talimati gosterir.
6. **Upload dogrulama:** uzanti whitelist (jpg jpeg png webp heic heif | mp4 mov webm m4v) + MIME eslesmesi + magic byte kontrolu (JPEG FFD8FF, PNG 89504E47, WEBP RIFF/WEBP, MP4/MOV/M4V `ftyp` offset 4, HEIC ftyp heic/heix/mif1/msf1, WEBM EBML 1A45DFA3). Boyut stream sirasinda sayilir, limit asilirsa temp silinir ve Turkce hata doner. Dosya adi hicbir zaman dogrudan filesystem'e yazilmaz; `sanitize_filename` + `resolve()` + `is_relative_to(root)` guard.
7. **ZIP:** STORE (sikistirmasiz) metod ile gercek streaming ZIP generator'u - foto/video zaten sikistirilmis oldugundan compression CPU/RAM israfi olurdu. CRC32 chunk chunk hesaplanir, memory O(1), temp dosya yok.
8. **Storage sagligi (spec #48):** Kurulumda host tarafinda `UPLOAD_ROOT/.wedding-storage` marker dosyasi olusturulur (`scripts/setup_storage.sh`). Uygulama `REQUIRE_STORAGE_MARKER=true` ise (production compose default'u) marker yoksa/yazilamiyorsa upload'leri DURDURUR, admin'e "Depolama cihazı bağlı değil" gosterir. Boylece USB takilmadan Docker'in root fs'te klasor yaratmasi durumu engellenir. Dev'de flag false'dur.
9. **Rate limit + brute force:** in-memory sliding window (tek uvicorn worker). Login: IP basina 15 dakikada 5 hatali deneme -> 429 + Turkce mesaj. Upload: IP basina saatte 120 dosya. Statik/API GET'ler limitsiz.
10. **CSRF:** Admin cookie SameSite=Strict + mutating admin endpoint'lerinde `X-CSRF-Token` double-submit (login'de verilen token). Public POST'ler SameSite=Lax cookie + `X-Requested-With` header zorunluluğu.
11. **Video thumbnail YOK** (spec #13: Pi'yi zorlamamak icin FFmpeg kullanilmaz); admin galerisinde `<video preload="metadata">` ile tarayici poster'i. Foto thumbnail: Pillow, maks 512px WebP, hata durumunda sessizce atlanir (orijinal korunur).
12. **Fontlar self-host:** internetsiz dugun WiFi'i icin @fontsource ile bundle edilir (Cormorant Garamond + Nunito Sans, latin-ext).
13. **HTTP Range:** Admin medya servisi `<video>` seek icin Range destekler (Starlette FileResponse destekliyorsa kullanilir, degilse manuel).

## API Sozlesmesi

Public:
- `GET  /api/config` → wedding_title, couple, welcome_title, welcome_text, max_upload_mb
- `POST /api/session` `{name, if_exists?: "reuse"|"new"}` → 200 user + cookie | 409 existed
- `GET  /api/me` → user | 401
- `POST /api/uploads` (multipart `files`, cookie) → dosya bazli sonuclar
- `GET  /api/health` → `{status, db_ok, storage_ok}` (compose healthcheck)

Admin (hepsi `wm_admin` cookie; mutating olanlar + `X-CSRF-Token`):
- `POST /api/admin/login|logout`, `GET /api/admin/me`
- `GET /api/admin/stats` → kisiler/foto/video/dosya sayisi, kullanilan alan, disk toplam/bos
- `GET /api/admin/users`, `GET/DELETE /api/admin/users/{id}`
- `DELETE /api/admin/files/{id}`, `POST /api/admin/files/delete-batch`
- `GET /api/admin/files/{id}/download`, `GET /api/admin/thumbs/{id}`
- `GET /api/admin/users/{id}/zip`
- `GET /api/admin/qr.png?size=1024`
- `GET/PUT /api/admin/settings`
- `POST /api/admin/cleanup` (DB<->dosya tutarliligi)
- `GET /api/admin/backup.sqlite`

## Proje Yapisi

```
.
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app, middleware, static, SPA fallback, hata handler'lari
│   │   ├── config.py        # env ayarlari (pydantic-settings yok, os.environ + dataclass)
│   │   ├── db.py            # engine/session, WAL pragma
│   │   ├── models.py        # SQLAlchemy modelleri
│   │   ├── security.py      # pbkdf2, token, cookie yardimcilari
│   │   ├── rate_limit.py    # sliding window limiter
│   │   ├── storage.py       # sanitize, path guard, magic bytes, atomic finalize, disk usage, health
│   │   ├── thumbnails.py    # Pillow thumbnail (best-effort)
│   │   ├── zipstream.py     # STORE metodlu streaming ZIP
│   │   └── routes/
│   │       ├── public.py
│   │       └── admin.py
│   ├── tests/               # pytest (conftest tmp storage + TestClient)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.jsx, App.jsx
│   │   ├── styles.css       # pastel design system
│   │   ├── lib/api.js       # fetch wrapper + XHR upload
│   │   ├── texts.js         # tum Turkce UI metinleri (tek yerden yonetim)
│   │   ├── pages/           # Home, Upload, Success
│   │   └── admin/           # Login, Dashboard, Users, UserDetail, Settings + components
│   ├── index.html, vite.config.js, package.json
├── nginx/nginx.conf         # opsiyonel TLS proxy profili
├── scripts/
│   ├── generate_admin_hash.py
│   └── setup_storage.sh     # Pi uzerinde /mnt/usb hazirlama + marker
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .gitignore
├── README.md
└── docs/
```

---

### Task 1: Repo init

**Files:** `.gitignore`, `.env.example`, klasor yapisi
**Steps:**
1. `git init`, `.gitignore` (node_modules, dist, __pycache__, .env, data/, *.db, venv)
2. `.env.example` — spec #55'teki tum degiskenler + aciklama yorumlari
3. Commit: `chore: project scaffold`

### Task 2: Backend skeleton (config + db + models)

**Files:** `backend/requirements.txt`, `backend/app/{__init__,config,db,models}.py`, `backend/tests/conftest.py`
**Steps:**
1. venv olustur, `pip install -r requirements.txt`
2. `config.py`: Settings dataclass, env okuma (APP_ENV, DATABASE_URL, UPLOAD_ROOT, MAX_UPLOAD_SIZE_MB, ADMIN_USERNAME, ADMIN_PASSWORD_HASH, PUBLIC_URL, SESSION_SECRET, REQUIRE_STORAGE_MARKER, COOKIE_SECURE, rate limit degerleri)
3. `models.py`: 6 tablo (yukarida), index'ler (uploads.user_id, expires_at)
4. `db.py`: engine factory, `PRAGMA journal_mode=WAL; synchronous=NORMAL; foreign_keys=ON`
5. Test: tablo olusumu + temel CRUD (tmp sqlite)
6. Commit: `feat(backend): config, db, models`

### Task 3: Security utils

**Files:** `backend/app/security.py`, `backend/tests/test_security.py`
**Steps:**
1. Failing test: `hash_password`/`verify_password` roundtrip, yanlis sifre, format bozuk hash
2. Failing test: `new_token` 43 char urlsafe, `hash_token` deterministik
3. Implement (pbkdf2 600k, secrets.token_urlsafe(32), sha256)
4. Testler gec → Commit: `feat(backend): password + token security utils`

### Task 4: Storage layer (kritik guvenlik)

**Files:** `backend/app/storage.py`, `backend/tests/test_storage.py`
**Steps:**
1. Failing test'ler:
   - `sanitize_display_name`: Turkce transliterasyon ("Ümit Şahin" → "Umit Sahin"), bosluk collapse, max 40, sadece harf/rakam/bosluk/-/_, bos → "Misafir", path traversal girdileri ("../../evil", "a/b", "..") temizlenir
   - `unique_folder_name`: cakisma → "Erhan-2", "Erhan-3"...
   - `sanitize_filename`: basename al, ".." kaldir, izinli karakter disini "_", max 100, cakisma → "IMG_1234_2.jpg"
   - `safe_join(root, ...)`: `resolve` + `is_relative_to` guard; disari cikan path ValueError
   - `sniff_media_type`: gecerli jpg/png/webp/mp4/mov/heic/webm imzalar; exe/php/zip → None
   - `storage_health`: marker yok + REQUIRE_STORAGE_MARKER → unhealthy
2. Implement
3. Gec → Commit: `feat(backend): storage safety layer`

### Task 5: Public session API (isim akisi)

**Files:** `backend/app/routes/public.py`, `backend/tests/test_session.py`
**Steps:**
1. Failing test: gecerli isim → 200, users tablosuna kayit, klasor olusur (`<root>/Erhan/original`), cookie set
2. Failing test: ayni isim tekrar, `if_exists` yok → 409 `existed:true`; `if_exists:"reuse"` → 200 ayni user; `"new"` → yeni klasor "Erhan-2"
3. Failing test: bos isim / 100+ karakter / sadece ozel karakter → 422 Turkce mesaj
4. Failing test: `GET /api/me` cookie'siz → 401; cookie'li → user
5. Implement (rate limit dahil)
6. Gec → Commit: `feat(backend): name flow + public sessions`

### Task 6: Upload API

**Files:** `routes/public.py` (upload endpoint), `backend/app/thumbnails.py`, `backend/tests/test_upload.py`
**Steps:**
1. Failing test: gecerli kucuk PNG → 200, `original/` altinda dosya, DB kaydi, `has_thumbnail` true, thumbs/ altinda webp
2. Failing test: 3 dosya ayni anda → hepsi kayit
3. Failing test: `.exe` / `.php` / sahte uzanti (icinde exe olan .jpg) → 415/400 Turkce hata, temp temizlenmis, DB'de kayit YOK
4. Failing test: limit ustu dosya → 413 "Bu dosya çok büyük...", temp silinmis
5. Failing test: session yok → 401; baskasinin klasorune erisim imkani yok (token user'a bagli)
6. Failing test: storage unhealthy → 503 "Depolama cihazı bağlı değil"
7. Implement: chunk'li kopya (1MB), boyut sayaci, magic check, atomic rename, DB insert, thumbnail best-effort
8. Gec → Commit: `feat(backend): streaming upload pipeline`

### Task 7: Admin auth API

**Files:** `routes/admin.py` (auth kismi), `backend/tests/test_admin_auth.py`
**Steps:**
1. Failing test: dogru kullanici/sifre → 200 + cookie + csrf; yanlis → 401 genel mesaj
2. Failing test: ADMIN_PASSWORD_HASH tanimli degilse → 503 "kurulum tamamlanmamis"
3. Failing test: 6. hatali deneme → 429
4. Failing test: csrf'siz DELETE → 403; csrf'li → calisir; logout → cookie gecersiz
5. Implement + security headers middleware testi (X-Frame-Options vs.)
6. Gec → Commit: `feat(backend): admin auth with brute-force protection`

### Task 8: Admin data API

**Files:** `routes/admin.py` (devam), `backend/app/zipstream.py`, `backend/tests/test_admin_api.py`
**Steps:**
1. Failing test: stats (kisi/foto/video/dosya/toplam boyut + disk usage)
2. Failing test: users listesi (dosya sayisi + boyut), user detail (dosya metadata)
3. Failing test: dosya sil (diskten + DB), kullanici sil (klasor + kayitlar), batch sil
4. Failing test: zip stream — STORE zip imzasi (PK\x03\x04), icerik dosyalari dogru, memory O(1) (generator)
5. Failing test: QR endpoint gecerli PNG doner, PUBLIC_URL icerir
6. Failing test: settings GET/PUT (wedding_title vs.), `/api/config` yansir
7. Failing test: cleanup — DB'de olup diskte olmayan kayit silinir, diskte olup DB'de olmayan dosya raporlanir
8. Implement
9. Gec → Commit: `feat(backend): admin dashboard APIs, streaming zip, qr`

### Task 9: App assembly

**Files:** `backend/app/main.py`
**Steps:**
1. Middleware'ler: guvenlik header'lari, rate limit, request log (INFO/WARN/ERROR formatli, spec #35)
2. Hata handler'lari: 413/415/500 → Turkce JSON `{detail}`
3. Static serving + SPA fallback (`/admin/*` dahil) — frontend `dist/` yoksa 503 net mesaj
4. Startup: DB init (create_all), admin hash kontrol logu, storage health logu
5. Smoke test: TestClient ile `/api/health`, `/` (dist yokken davranis)
6. Commit: `feat(backend): app assembly, middleware, error handling`

### Task 10: Frontend scaffold + design system

**Files:** `frontend/*` (package.json, vite.config, index.html, main.jsx, App.jsx, styles.css, texts.js, lib/api.js)
**Steps:**
1. `npm create vite` manuel kurulum (react, react-router-dom, @fontsource x2)
2. `styles.css`: pastel design tokens (krem #FBF7F4, blush #F6E7E4, pudra #F2D9D6, peach #FBE5DC, champagne #EAD9C2, gold #C6A15B, metin #5B5450), serif (Cormorant Garamond) + sans (Nunito Sans) rolleri, yumusak radius/golge, buton/input/badge/kart bilesenleri, focus-visible, `prefers-reduced-motion`
3. `api.js`: fetch wrapper (hatalari Turkce mesaja cevirir), `uploadFile` XHR progress callback'li, `jsonFetch`
4. `vite.config.js`: dev proxy `/api` → localhost:8000
5. `npm run build` gecer → Commit: `feat(frontend): scaffold + pastel design system`

### Task 11: Public sayfalar

**Files:** `frontend/src/pages/{Home,Upload,Success}.jsx`
**Steps:**
1. Home: config'ten basliklar, isim inputu (buyuk, mobil klavye-friendly), 409'da "ayni kisi / yeni kisi" diyalogu, hafif fade-in
2. Upload: "Merhaba X 🤍", buyuk "+ Fotoğraf veya Video Ekle" (accept="image/*,video/*", multiple, capture yok), dosya kartlari (client thumbnail blob:, dosya adi, boyut), XHR progress bar + %, hata → "Tekrar Dene", yukleme sirasinda beforeunload uyaris, 2 dosya eszamanli kuyruk, hepsi bitince /success
3. Success: "Anıların başarıyla kaydedildi! 🤍" + "Başka Anı Ekle"
4. Manuel test + build → Commit: `feat(frontend): public name-upload-success flow`

### Task 12: Admin sayfalari

**Files:** `frontend/src/admin/*`
**Steps:**
1. Login (brute-force mesaji dahil), korumali route wrapper'i
2. Dashboard: stat kartlari (kisi/foto/video/GB), storage bar (%90 uyarisi), son yuklemeler
3. Users listesi → UserDetail: masonry galeri (columns), lightbox (klavye navigasyonlu), video oynatici, coklu secim + sil (confirm: "Bu işlem geri alınamaz."), tek dosya indir, "Tümünü ZIP indir"
4. Settings: dugun adi/cift/mesaj/PUBLIC_URL, QR goster + PNG indir, tutarlilik kontrolu butonu, DB backup indir
5. Build → Commit: `feat(frontend): admin panel`

### Task 13: Docker

**Files:** `Dockerfile`, `docker-compose.yml`, `nginx/nginx.conf`, `backend/docker-entrypoint.sh`
**Steps:**
1. Multi-stage Dockerfile: node build → python:3.12-slim, non-root user, requirements install (ARM64 wheel'ler: pillow, pillow-heif), dist kopyala
2. compose: `app` servisi (restart unless-stopped, env_file, `${UPLOAD_ROOT_HOST:-/mnt/usb/wedding-uploads}:/app/data/uploads` bind + `db-data` named volume, healthcheck python ile /api/health), opsiyonel `proxy` profili nginx (client_max_body_size 0, 80/443, cert volume)
3. `docker compose config` gecerlilik kontrolu (bu makinede docker yok — YAML dogrulamasi python yaml ile)
4. Commit: `feat: docker deployment`

### Task 14: Scripts + README

**Files:** `scripts/generate_admin_hash.py`, `scripts/setup_storage.sh`, `README.md`
**Steps:**
1. Hash script'i (interaktif, stdout'e sadece hash)
2. setup_storage.sh: mount kontrolu, mkdir, marker, izinler
3. README: spec #53'teki tum basliklar (kurulum, .env, admin hesabi, backup, QR, domain/HTTPS, troubleshooting)
4. Commit: `docs: readme and scripts`

### Task 15: Son dogrulama

**Steps:**
1. `pytest` tamamen yesil
2. `npm run build` temiz
3. Uygulamayi yerelde calistir (uvicorn + dist), tarayici ile tam akis testi: isim → dosya sec → progress → basari → admin login → dashboard → galeri → indir/ZIP → silme → settings/QR
4. Spec #51 senaryo listesindeki otomatiklenebilir maddeleri isaretle, kalanlari README'de "deploy sonrasi test" listesi olarak birak
5. Commit: `test: end-to-end verification`

---

## Riskler / Notlar

- Bu makinede Docker YOK → tum test yerelde python/node ile; Docker dogrulamasi syntax-duzeyde. Pi uzerinde ilk calistirma README'de adim adim.
- Starlette FileResponse Range destegi surume bagli → implementasyon sirasinda dogrulanir, gerekirse manuel Range.
- HEIC thumbnail icin pillow-heif import'u try/except ile sarilir (wheel yoksa thumbnail'siz calisir).
- iOS Safari: `accept="image/*,video/*"` tek input'ta kamera+galeri menusu acar; `multiple` desteklenir. beforeunload iOS'ta garantili degil → ek olarak sayfa ici uyari metni.
