# ============================================================
# Wedding Memories - multi-stage Docker image
# Asama 1: React arayuzu derlenir (node:22-alpine)
# Asama 2: FastAPI backend + statik arayuz (python:3.12-slim)
# Raspberry Pi 5 (ARM64) ile uyumludur; tum bagimliliklarin
# ARM64 wheel'i bulunur.
# ============================================================

# ---------- Asama 1: frontend ----------
FROM node:22-alpine AS frontend-build
WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit

COPY frontend/ ./
RUN npm run build

# ---------- Asama 2: backend ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY backend/docker-entrypoint.sh /docker-entrypoint.sh
COPY --from=frontend-build /build/dist ./static

# Root olmayan kullanici ile calisir
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data/db \
    && chmod +x /docker-entrypoint.sh \
    && chown -R appuser:appuser /app

USER appuser

# 33464 = telefon tuslarinda WEDDING (933464) - bilinen hicbir servis
# bu portu kullanmaz; 80/8000 gibi yaygin port cakismalarinin onune gecer.
EXPOSE 33464

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:33464/api/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/docker-entrypoint.sh"]
