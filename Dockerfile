# ==============================================================
# VidTele Backend - Production Dockerfile pour Dokploy & Docker
# ==============================================================

FROM python:3.11-slim

# Configuration des variables d'environnement Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Installation des paquets système (curl pour healthcheck, ffmpeg pour vidéo, sqlite3)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    sqlite3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Installation des dépendances Python
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copie du code backend
COPY backend/ /app/

# Création des répertoires de persistance et de cache
RUN mkdir -p /app/data /app/cache /app/thumbnails

# Exposition du port
EXPOSE 8000

# Contrôle de santé (Healthcheck) compatible Dokploy & Docker
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Lancement du serveur Uvicorn FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
