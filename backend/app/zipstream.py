"""Sikistirmasiz (STORE) streaming ZIP uretici.

Foto ve videolar zaten sikistirilmis formatlarda oldugundan ZIP
sikistirmasi Raspberry Pi'de gereksiz CPU/RAM tuketirdi. STORE metod +
data descriptor ile dosyalar chunk chunk stream edilir; bellek kullanimi
sabit kalir, temp dosya olusmaz (spec #18).

Dogrulama testleri ciktiyi stdlib zipfile ile acar.
"""

import struct
import time
import zlib
from pathlib import Path
from typing import Iterable, Iterator

_LOCAL_SIG = 0x04034B50
_CENTRAL_SIG = 0x02014B50
_EOCD_SIG = 0x06054B50
_EOCD_SIG_ALT = 0x08074B50  # data descriptor imzasi
_UTF8_FLAG = 0x0800
_DATA_DESCRIPTOR_FLAG = 0x0008

CHUNK = 1024 * 1024


def _dos_time(mtime: float) -> tuple[int, int]:
    lt = time.localtime(mtime)
    year = max(1980, lt[0])
    date = ((year - 1980) << 9) | (lt[1] << 5) | lt[2]
    tim = (lt[3] << 11) | (lt[4] << 5) | (lt[5] // 2)
    return tim, date


def stream_zip(entries: Iterable[tuple[Path, str]]) -> Iterator[bytes]:
    """(dosya_yolu, zip_ici_isim) listesini ZIP byte akisina cevirir."""
    central = bytearray()
    offset = 0
    count = 0
    flags = _UTF8_FLAG | _DATA_DESCRIPTOR_FLAG

    for path, arcname in entries:
        name_bytes = arcname.encode("utf-8")
        stat = path.stat()
        size = stat.st_size
        tim, date = _dos_time(stat.st_mtime)

        header = struct.pack(
            "<IHHHHHIIIHH",
            _LOCAL_SIG, 20, flags, 0, tim, date,
            0, 0, 0,  # crc ve boyutlar data descriptor'da
            len(name_bytes), 0,
        ) + name_bytes
        header_offset = offset
        yield header
        offset += len(header)

        crc = 0
        with open(path, "rb") as f:
            while True:
                chunk = f.read(CHUNK)
                if not chunk:
                    break
                crc = zlib.crc32(chunk, crc)
                yield chunk
                offset += len(chunk)

        yield struct.pack("<IIII", _EOCD_SIG_ALT, crc, size, size)
        offset += 16

        central += struct.pack(
            "<IHHHHHHIIIHHHHHII",
            _CENTRAL_SIG,
            20, 20, flags, 0, tim, date,
            crc, size, size,
            len(name_bytes), 0, 0, 0, 0,
            (0o644 << 16),
            header_offset,
        ) + name_bytes
        count += 1

    cd_offset = offset
    eocd = struct.pack(
        "<IHHHHIIH",
        _EOCD_SIG, 0, 0, count, count, len(central), cd_offset, 0,
    )
    yield bytes(central) + eocd
