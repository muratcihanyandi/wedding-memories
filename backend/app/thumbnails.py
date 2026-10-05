"""Fotoğraf thumbnail uretimi - best effort.

Orijinal dosya ASLA degistirilmez; thumbs/ klasorune en fazla 512px
WEBP kopyasi yazilir. HEIC destegi pillow-heif kuruluysa acilir.
Herhangi bir hata thumbnail'siz kalma seklinde atlanir - yukleme
basarisiz sayilmaz (spec #12: orijinal kalite korunmali).
"""

import logging
from pathlib import Path

logger = logging.getLogger("wedding")

try:  # HEIC destegi - paket yoksa sessizce devre disi kalir
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:  # pragma: no cover - import hatasi normal durum
    pass


def make_thumbnail(src: Path, dst: Path, max_size: int = 512) -> bool:
    try:
        from PIL import Image, ImageOps

        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail((max_size, max_size))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(dst, "WEBP", quality=80)
        return True
    except Exception as exc:  # bozuk gorsel, HEIF decoder yok, disk dolu...
        logger.warning("Thumbnail uretilemedi: %s (%s)", src.name, exc)
        return False
