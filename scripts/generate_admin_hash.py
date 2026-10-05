#!/usr/bin/env python3
"""Admin sifresi icin guvenli pbkdf2 hash uretir.

Kullanim (proje kokunde):
    python scripts/generate_admin_hash.py

Cikan degeri .env dosyasinda ADMIN_PASSWORD_HASH alanina yapistirin.
Sifre asla source code'a veya .env'e duz metin olarak yazilmaz.
"""

import getpass
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.security import hash_password  # noqa: E402


def main() -> None:
    print("Wedding Memories - Admin Sifre Hash Uretici")
    print("-" * 44)
    print("Sifrenizi iki kez girin. Girdikleriniz ekranda gorunmez.\n")

    password = getpass.getpass("Sifre: ")
    if len(password) < 8:
        print("\nHATA: Sifre en az 8 karakter olmali.")
        sys.exit(1)
    if any(ch.isspace() for ch in password):
        print("\nHATA: Sifrede bosluk karakteri kullanilmamali.")
        sys.exit(1)

    confirm = getpass.getpass("Sifre (tekrar): ")
    if password != confirm:
        print("\nHATA: Sifreler eslesmiyor.")
        sys.exit(1)

    print("\nAsagidaki degeri .env dosyasinda ADMIN_PASSWORD_HASH'e kopyalayin:")
    print()
    print(hash_password(password))
    print()


if __name__ == "__main__":
    main()
