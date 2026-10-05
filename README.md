# Wedding Memories 🤍

Düğünlerde QR kodu ile çalışan, misafirlerin fotoğraf ve videolarını yalnızca **adını yazarak** paylaştığı; çiftin bu anıları güvenli bir admin panelinden görüntülediği, indirdiği ve arşivlediği hafif web uygulaması.

**Raspberry Pi 5 (8 GB) + Docker + USB disk** üzerinde, internet bağlantısı gerektirmeden yerel ağ üzerinden çalışacak şekilde tasarlanmıştır.

---

## İçindekiler

1. [Nasıl Çalışır](#nasıl-çalışır)
2. [Mimari ve Teknoloji Seçimi](#mimari-ve-teknoloji-seçimi)
3. [Gereksinimler](#gereksinimler)
4. [Hızlı Kurulum (Raspberry Pi)](#hızlı-kurulum-raspberry-pi)
5. [CasaOS Kurulumu (ghcr.io)](#casaos-kurulumu-ghcrio)
6. [USB Depolama Kurulumu](#usb-depolama-kurulumu)
7. [.env Ayarları](#env-ayarları)
8. [Admin Hesabı Oluşturma](#admin-hesabı-oluşturma)
9. [Başlatma / Durdurma / Loglar](#başlatma--durdurma--loglar)
10. [QR Kod Kullanımı](#qr-kod-kullanımı)
11. [Yerel Ağ ve İnternetsiz Kullanım](#yerel-ağ-ve-internetsiz-kullanım)
12. [Domain Bağlama ve HTTPS](#domain-bağlama-ve-https)
13. [Backup](#backup)
14. [Güncelleme](#güncelleme)
15. [Geliştirme Ortamı](#geliştirme-ortamı)
16. [Testler](#testler)
17. [Sorun Giderme](#sorun-giderme)

---

## Nasıl Çalışır

```
Misafir (telefon)                    Çift / Admin
────────────────                     ─────────────
QR kodu okut                         /admin
   ↓                                    ↓
"Adın nedir?" → Elif                  Giriş (kullanıcı adı + şifre)
   ↓                                    ↓
"Merhaba Elif! 🤍"                    Dashboard (istatistik + depolama)
   ↓                                    ↓
Fotoğraf/videoları seç                Katılımcılar → Galeri
   ↓                                    ↓
Yükleme (progress bar)                Görüntüle · İndir · ZIP · Sil
   ↓
"Anıların kaydedildi 🤍"
```

- Misafirlerden yalnızca **isim** istenir; kayıt, e-posta, şifre yoktur.
- Aynı isim girilirse "aynı kişiyim / farklı bir kişiyim" seçeneği sunulur; farklı kişiler `Elif-2` şeklinde ayrı klasör alır.
- Dosyalar **hiçbir zaman RAM'e tam alınmadan**, 1 MB'lık parçalarla diske akıtılır (streaming). 1 GB+ düğün videoları güvenle yüklenebilir.
- Yükleme yarıda kesilirse geçici dosya temizlenir, veritabanına kayıt oluşmaz.

## Mimari ve Teknoloji Seçimi

```
docker compose
└── app  (tek container, ARM64)
    ├── FastAPI  → /api/*   (upload, oturum, admin)
    ├── Statik React arayüzü (frontend/dist → /app/static)
    ├── SQLite (WAL) → named volume  /app/data/db
    └── Upload'lar   → bind mount     /mnt/usb/wedding-uploads
```

| Katman | Seçim | Neden |
|---|---|---|
| Backend | **FastAPI (Python)** | Async streaming upload ile 1 GB+ dosyalarda RAM güvenli; `python-multipart` dosyaları 1 MB sonrası otomatik diske taşır; Pillow/qrcode ARM64 wheel'leri hazırdur; SQLAlchemy sayesinde PostgreSQL'e geçiş tek env değişkeni |
| Frontend | **Vite + React (SPA)** | Derleme sonrası saf statik dosya → Pi'de çalışma maliyeti sıfır; XHR ile gerçek yükleme yüzdesi |
| Veritabanı | **SQLite + WAL** | Tek dosya, bakımsız, Pi için yeterli; `DATABASE_URL` ile PostgreSQL'e geçilebilir |
| ZIP | **Streaming STORE ZIP** | Foto/video zaten sıkıştırılmıştır; sıkıştırmasız akış RAM'i sabit tutar, geçici dosya oluşmaz |
| Şifre | **PBKDF2-HMAC-SHA256 (600k iterasyon)** | ARM64'te native derleme gerektirmez, güçlü ve bağımlılıksız |

Opsiyonel **nginx TLS proxy** profili içeride mevcuttur (aşağıda).

## Gereksinimler

- Raspberry Pi 5 (8 GB) — Raspberry Pi OS (64-bit)
- Docker + Docker Compose v2
- USB disk (SSD önerilir; harici HDD için aktif güçlü USB hub)
- Düğün alanında telefonların bağlanabileceği bir Wi-Fi ağı (Pi aynı ağda)

## Hızlı Kurulum (Raspberry Pi)

```bash
# 1) Docker kurulu değilse
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # çıkış yapıp tekrar girin

# 2) Sistem açılışında Docker otomatik başlasın
sudo systemctl enable docker

# 3) Projeyi alın
git clone <proje-adresi> wedding-memories
cd wedding-memories

# 4) USB depolamayı hazırlayın (aşağıya bakın)
sudo bash scripts/setup_storage.sh /mnt/usb

# 5) Ayar dosyasını oluşturun
cp .env.example .env

# 6) Admin şifrenizin hash'ini üretin ve .env'e koyun
python3 scripts/generate_admin_hash.py
#    çıktıyı .env içindeki ADMIN_PASSWORD_HASH= satırına yapıştırın

# 7) Rastgele SESSION_SECRET üretin
python3 -c "import secrets; print(secrets.token_hex(32))"
#    çıktıyı .env içindeki SESSION_SECRET= satırına yapıştırın

# 8) Başlatın
docker compose up -d --build
```

Uygulama hazır: `http://<pi-ip-adresi>` (varsayılan port 80).

> İlk kurulumda `.env` dosyası olmadan da container ayağa kalkar, ancak **admin girişi kapalıdır** ve loglarda kurulum uyarısı görünür.

## CasaOS Kurulumu (ghcr.io)

Pi'nizde **CasaOS** varsa derleme yapmadan hazır imajı çekebilirsiniz. İmaj GitHub Actions ile otomatik olarak `ghcr.io/muratcihanyandi/wedding-memories` adresine yayınlanır (linux/arm64).

1. **USB diskizi CasaOS'ta mount edin** (CasaOS → Storage). Mount yolunu not alın (örn. `/mnt/usb` veya `/media/...`).

2. Mount edilen diskte uygulama klasörünü hazırlayın (Pi'ye SSH ile):

   ```bash
   sudo mkdir -p /mnt/usb/wedding-uploads
   sudo touch /mnt/usb/wedding-uploads/.wedding-storage
   sudo chown -R 1000:1000 /mnt/usb/wedding-uploads
   ```

3. [docker-compose.casaos.yml](docker-compose.casaos.yml) dosyasını açın ve `DEGISTIR` etiketli değerleri doldurun:
   - `ADMIN_PASSWORD_HASH`: repo'yu klonlayıp `python3 scripts/generate_admin_hash.py` çalıştırın, çıkan `pbkdf2_sha256$...` değerini koyun
   - `SESSION_SECRET`: rastgele uzun metin (`python3 -c "import secrets;print(secrets.token_hex(32))"`)
   - `PUBLIC_URL`: Pi'nin IP'si (örn. `http://192.168.1.50`)
   - volumes bölümündeki USB yolu

4. CasaOS → **App Store → sağ üst "+" → Install from Docker-compose** (veya Docker Compose) seçeneğine düzenlediğiniz içeriği yapıştırıp kurun.

5. Kurulum bitince `http://<pi-ip>` adresinden uygulamayı açın.

**Güncelleme (CasaOS):** Yeni imaj çıktığında container'ı silip aynı compose ile yeniden kurun (volumes sayesinde veriler korunur), veya SSH ile:

```bash
docker pull ghcr.io/muratcihanyandi/wedding-memories:latest
docker rm -f wedding-app   # CasaOS tekrar kuracak / compose up -d
```

> İmaj gizli (private) yapılırsa CasaOS çekemez; public kalması önerilir. Uygulama sırları imajın içinde değil, compose içindeki env değerlerindedir.

## USB Depolama Kurulumu

Upload'lar container'ın **dışındaki** USB diskte tutulur; container silinse/restart olsa bile dosyalar korunur.

1. Diski takın ve mount edin:

```bash
sudo mkdir -p /mnt/usb
sudo mount /dev/sda1 /mnt/usb        # disk adınızı lsblk ile doğrulayın
```

2. Kalıcı (açılışta otomatik) mount için `/etc/fstab`'e ekleyin:

```
/dev/sda1  /mnt/usb  ext4  defaults,nofail  0  2
```

> `nofail` önemlidir: disk takılı değilken Pi'nin açılışta takılı kalmasını engeller.

3. Uygulama klasörünü hazırlayın:

```bash
sudo bash scripts/setup_storage.sh /mnt/usb
```

Bu betik mount kontrolü yapar, `wedding-uploads` klasörünü açar, **`.wedding-storage` marker dosyasını** oluşturur ve izinleri container kullanıcısına verir.

> ⚠️ **Kritik:** `REQUIRE_STORAGE_MARKER=true` (üretim varsayılanı) iken uygulama marker dosyasını göremezse **upload'leri durdurur** ve admin panelinde "Depolama cihazı bağlı değil" uyarısı gösterir. Bu, USB takılı değilken Docker'ın boş klasörü root filesystem üzerinde açıp dosyaları yanlış yere yazmasını engeller (spec gereği).

## .env Ayarları

| Değişken | Açıklama | Varsayılan |
|---|---|---|
| `APP_ENV` | `production` / `development` | `production` |
| `DATABASE_URL` | SQLite yolu; PostgreSQL için `postgresql+psycopg://...` | container içi SQLite |
| `UPLOAD_ROOT_HOST` | Pi üzerindeki upload klasörü (bind mount kaynağı) | `/mnt/usb/wedding-uploads` |
| `MAX_UPLOAD_SIZE_MB` | Dosya başına üst sınır | `2048` (2 GB) |
| `ADMIN_USERNAME` | Admin kullanıcı adı | `admin` |
| `ADMIN_PASSWORD_HASH` | `scripts/generate_admin_hash.py` çıktısı | (boş = admin kapalı) |
| `SESSION_SECRET` | Rastgele uzun gizli anahtar | — |
| `PUBLIC_URL` | QR kodun işaret edeceği adres (`http://192.168.x.x` veya `https://site.com`) | boş |
| `COOKIE_SECURE` | HTTPS kullanırken `true` yapın | `false` |
| `TRUST_PROXY` | nginx profili arkasında `true` yapın | `false` |
| `REQUIRE_STORAGE_MARKER` | USB mount kontrolü (üretimde `true` kalsın) | `true` |
| `LOGIN_MAX_FAILURES` | 15 dakikada izin verilen hatalı admin girişi | `5` |
| `UPLOAD_MAX_PER_HOUR` | IP başına saatlik dosya limiti | `120` |
| `APP_PORT` | Uygulamanın yayınlanacağı host portu | `80` |

Secret içeren `.env` dosyası `.gitignore`'dadır; **asla commit etmeyin**.

## Admin Hesabı Oluşturma

```bash
python3 scripts/generate_admin_hash.py
```

- Şifre en az 8 karakter olmalı, iki kez doğrulanır.
- Çıktıdaki `pbkdf2_sha256$...` değerini `.env` içinde `ADMIN_PASSWORD_HASH=` satırına yazın.
- Varsayılan/hazır şifre **yoktur**; hash tanımlı değilse admin girişi 503 döner.
- Değişiklik sonrası: `docker compose up -d` (env yeniden yüklenir).

## Başlatma / Durdurma / Loglar

```bash
docker compose up -d --build     # başlat / güncelle
docker compose stop              # durdur (veriler korunur)
docker compose down              # container'ları kaldır (upload'lar ve DB kalır)
docker compose logs -f app       # uygulama logları
docker compose ps                # sağlık durumu (healthy olmalı)
```

Loglar okunabilir düzendedir:

```
[INFO] Storage ready: /app/data/uploads
[INFO] POST /api/session -> 200 (24 ms)
[INFO] Upload started user=Erhan file=IMG_1234.JPG
[INFO] Upload completed user=Erhan file=IMG_1234.JPG size=4213812 thumb=True
[WARNING] Upload rejected user=Erhan file=virus.exe: Bu dosya türü desteklenmiyor...
[ERROR] Storage unavailable: Depolama cihazı bağlı değil.
```

## QR Kod Kullanımı

1. `.env` içinde `PUBLIC_URL`'i ayarlayın (örn. `http://192.168.1.50`) ve `docker compose up -d` ile yeniden yükleyin — **veya** admin panelinden *Ayarlar → QR Kod Adresi* alanını güncelleyin (yeniden başlatma gerekmez).
2. Admin panelinde **Ayarlar → QR Kod** bölümünden kodu görüntüleyin.
3. **"Yüksek Çözünürlüklü PNG İndir"** ile baskıya uygun (2048px) dosyayı alın.
4. Davetiye/kart/tablet standı üzerine bastırın. Düğün adı QR'ın yanında yer alacak şekilde tasarlanabilir.

## Yerel Ağ ve İnternetsiz Kullanım

- Sistem tamamen yereldir; internet gerektirmez.
- Pi'yi düğün Wi-Fi'ına bağlayın, IP'sini öğrenin: `hostname -I`
- Misafirler `http://<pi-ip>` adresine girer (QR bunu otomatik yapar).
- Fontlar dâhil tüm kaynaklar uygulama içinde barındırılır (self-host) — internet olmasa da arayüz eksiksiz açılır.

## Domain Bağlama ve HTTPS

Yerel ağ kullanımı için HTTPS zorunlu değildir. Domain + HTTPS isterseniz:

1. `.env` içinde `APP_PORT`'u çakışmayan bir porta alın (örn. `8080`) ve `TRUST_PROXY=true`, `COOKIE_SECURE=true` yapın.
2. Sertifika dosyalarını `nginx/certs/` altına koyun (`fullchain.pem`, `privkey.pem`).
3. `nginx/nginx.conf` içindeki yorumlu HTTPS sunucu bloğunu aktifleştirin.
4. Başlatın:

```bash
docker compose --profile proxy up -d
```

Let's Encrypt için: Pi'ye `certbot` kurup standalone modda sertifika alın, dosyaları `nginx/certs/`e kopyalayın (yenilemeyi cron'a bağlayın). Yük dengeleme/CDN gerekseydi aynı yapı korunur — reverse proxy katmanı uygulama kodundan tamamen bağımsızdır.

## Backup

- **Veritabanı (metadata):** Admin paneli → *Ayarlar → Bakım → Veritabanı Yedeğini İndir*. Tutarlı (online-backup API'li) bir kopya indirir.
- **Medya dosyaları:** USB diski düzenli olarak başka bir diske kopyalayın:

```bash
sudo rsync -a --info=progress2 /mnt/usb/wedding-uploads/ /mnt/backup-disk/wedding-backup/
```

- Mimari yedeklenebilirlik için hazırdır: DB ve dosyalar birbirinden bağımsız dizinlerde tutulur; ileride otomatik senkron jobs eklenebilir.
- Bozulmuş kayıt/dosya tutarsızlıklarında: *Ayarlar → Bakım → Tutarlılık Kontrolü* (eksik dosya kayıtlarını temizler, yetim dosyaları raporlar — **silmez**).

## Güncelleme

```bash
cd wedding-memories
git pull
docker compose up -d --build
```

Veriler (upload'lar + DB) volume'larda olduğu için güncelleme onlara dokunmaz.

## Geliştirme Ortamı

```bash
# Backend (Python 3.11+)
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt        # Windows
# source .venv/bin/activate && pip install -r requirements-dev.txt  # Linux/macOS

# Testleri çalıştır
.venv/Scripts/python -m pytest tests/ -v

# Sunucuyu başlat (frontend/dist yoksa arayüz 503 döner — normal)
.venv/Scripts/uvicorn app.main:create_app --factory --reload --port 8000

# Frontend (Node 20+)
cd frontend
npm install
npm run dev        # http://localhost:5173 (/api -> localhost:8000 proxy'lenir)
npm run build      # dist/ üretir; backend otomatik sunar
```

## Testler

`backend/tests/` altında **119 otomatik test** vardır (`pytest`). Kapsanan başlıca senaryolar:

- İsim akışı: Türkçe isim, boş isim, çok uzun isim, özel karakterli isim, aynı isim (reuse/new), büyük/küçük harf eşleşmesi
- Güvenlik: path traversal (`../../`), executable/php yükleme, sahte uzantı (magic byte), boyut limiti, oturumsuz upload
- Upload: çoklu dosya, isim çakışması (`IMG_1234_2.jpg`), boş dosya, depolama kapalıyken 503, DB-disk tutarlılığı
- Admin: doğru/yanlış giriş, brute-force kilidi (5 hata → 429), CSRF'siz mutasyon reddi, çıkış
- Panel: istatistikler, kullanıcı/dosya silme, ZIP arşiv bütünlüğü (stdlib zipfile ile doğrulama), QR PNG, ayar okuma/yazma, cleanup, DB yedeği

**Deploy sonrası elle test edilmesi önerilenler** (donanım gerektirir): gerçek telefonlardan iOS Safari / Android Chrome upload, 1 GB+ gerçek video, USB kablo çekme testi, Pi restart sonrası otomatik toparlanma, gerçek Wi-Fi altında eşzamanlı kullanıcılar.

## Sorun Giderme

| Belirti | Neden / Çözüm |
|---|---|
| Admin panelinde "Depolama cihazı bağlı değil" | USB mount edilmemiş. `mountpoint /mnt/usb` kontrol edin; disk takılıp `sudo bash scripts/setup_storage.sh /mnt/usb` çalıştırın, sonra `docker compose restart app` |
| Upload'da "Bu dosya çok büyük" | `MAX_UPLOAD_SIZE_MB` sınırı. Gerekirse `.env`'de yükseltip `docker compose up -d` |
| Admin girişi 503 "yapılandırılmamış" | `ADMIN_PASSWORD_HASH` boş. `python3 scripts/generate_admin_hash.py` çalıştırıp `.env`'e koyun |
| Admin girişi 429 | Brute-force koruması (15 dk). Bekleyin veya container'ı restart edin |
| `docker compose ps` → unhealthy | `/api/health` başarısız: storage veya DB sorunu. `docker compose logs app` kontrol edin |
| Sayfa 503 "Arayüz derlenmemiş" | İmajdaki statik dosya eksik (imajı `--build` ile yeniden oluşturun) |
| Telefon siteyi açmıyor | Pi ve telefon aynı Wi-Fi ağında mı? `hostname -I` ile IP doğrulayın; port 80 kullanılıyorsa `.env`'de `APP_PORT` değiştirin |
| Video oynatıcı seek etmiyor | Tarayıcı Range destekliyor olmalı; modern tarayıcıda sorun çıkmaz. Eski cihazda dosyayı indirin |
| Pi restart sonrası site yok | `restart: unless-stopped` + `systemctl enable docker` sayesinde otomatik açılır. Açılmıyorsa: `docker compose ps`, `systemctl status docker` |

---

**Proje yapısı**

```
wedding-memories/
├── backend/          FastAPI uygulaması + testler
│   ├── app/
│   │   ├── main.py         uygulama fabrikası, middleware, SPA
│   │   ├── config.py       ortam değişkenleri
│   │   ├── db.py           SQLAlchemy engine (WAL)
│   │   ├── models.py       tablolar
│   │   ├── security.py     pbkdf2 + token
│   │   ├── storage.py      dosya güvenlik katmanı
│   │   ├── thumbnails.py   Pillow (best-effort)
│   │   ├── zipstream.py    streaming ZIP
│   │   ├── rate_limit.py   sliding window limiter
│   │   └── routes/         public.py + admin.py
│   └── tests/        119 pytest
├── frontend/         Vite + React SPA (pastel tasarım sistemi)
├── nginx/            opsiyonel TLS proxy yapılandırması
├── scripts/          admin hash üretici + USB hazırlık betiği
├── Dockerfile        multi-stage (node build → python runtime)
├── docker-compose.yml
└── .env.example
```
