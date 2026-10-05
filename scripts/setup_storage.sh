#!/bin/bash
# Raspberry Pi uzerinde USB depolamayi uygulama icin hazirlar.
# Docker container'i (uid 1000) klasore yazabilmeli ve uygulama
# marker dosyasini gormeli; boylece USB takili degilken upload
# edilmesi engellenir.
#
# Kullanim (sudo ile):
#   sudo bash scripts/setup_storage.sh [mount-noktasi]
#
# Varsayilan mount noktasi: /mnt/usb

set -e

MOUNT_POINT="${1:-/mnt/usb}"
UPLOAD_DIR="$MOUNT_POINT/wedding-uploads"

if ! mountpoint -q "$MOUNT_POINT"; then
    echo "HATA: $MOUNT_POINT mount edilmemis!" >&2
    echo "" >&2
    echo "USB diskizi once mount edin. Ornek:" >&2
    echo "  sudo mkdir -p $MOUNT_POINT" >&2
    echo "  sudo mount /dev/sda1 $MOUNT_POINT" >&2
    echo "" >&2
    echo "Kalici mount icin /etc/fstab'e ekleyin (bkz. README)." >&2
    exit 1
fi

mkdir -p "$UPLOAD_DIR"
touch "$UPLOAD_DIR/.wedding-storage"
chown -R 1000:1000 "$UPLOAD_DIR"

echo "OK: $UPLOAD_DIR hazir."
echo "    - marker dosyasi olusturuldu (.wedding-storage)"
echo "    - izinler container kullanicisina (uid 1000) verildi"
