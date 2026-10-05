#!/bin/sh
# Wedding Memories container giris noktasi.
# DB klasorunu hazirlar ve uvicorn'u tek worker ile baslatir
# (tek worker; rate limit state'i process icinde tutulur).

set -e

mkdir -p /app/data/db

exec uvicorn app.main:create_app \
    --factory \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --timeout-keep-alive 65 \
    --no-access-log
