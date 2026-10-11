# ==============================================================
# VidTele Backend - Image de production (Dokploy / Docker)
# Contexte de build : racine du dépôt (docker-compose.yml)
# ==============================================================

# Python 3.14 : même version que les tests (pytest) et que requirements.lock
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1     PIP_DISABLE_PIP_VERSION_CHECK=1     PORT=8000

WORKDIR /app

# Paquets système : curl (healthcheck), ffmpeg (remux faststart), sqlite3 (sauvegardes)
# Aucun compilateur : toutes les dépendances Python sont des roues précompilées.
RUN apt-get update && apt-get install -y --no-install-recommends     curl     ffmpeg     sqlite3     ca-certificates     && rm -rf /var/lib/apt/lists/*

# Dépendances Python figées et vérifiées par empreinte (reproductible)
COPY backend/requirements.lock /app/requirements.lock
RUN pip install --require-hashes -r /app/requirements.lock

# Code du serveur
COPY backend/ /app/

RUN mkdir -p /app/data /app/cache /app/thumbnails

EXPOSE 8000

# Vérification de vie (le conteneur répond). L'état détaillé est sur /api/health/ready.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3     CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
