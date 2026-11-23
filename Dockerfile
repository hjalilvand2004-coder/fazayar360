# ── مرحله ۱: ساخت فرانت‌اند ──────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

# ── مرحله ۲: بک‌اند ──────────────────────────────────────────────────
FROM python:3.12-slim AS backend
WORKDIR /srv
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend /app/dist ./frontend/dist
RUN mkdir -p /srv/data/uploads
ENV FAZAYAR_UPLOAD_DIR=/srv/data/uploads \
    FAZAYAR_DIST_DIR=/srv/frontend/dist \
    PYTHONUNBUFFERED=1
EXPOSE 8095
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8095"]
