"""
Vérifications de santé.

- GET /api/health        : « le processus répond » (healthcheck Docker/Dokploy). Ne touche à
                           rien d'externe pour ne jamais redémarrer le conteneur à tort.
- GET /api/health/ready  : état détaillé (base, Telegram, disque) pour la surveillance.
                           200 si le service peut servir des vidéos (éventuellement dégradé),
                           503 si un composant indispensable est en panne.
"""
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_data_dir, settings
from app.database import AsyncSessionLocal
from app.telegram_client import telegram_manager

logger = logging.getLogger("vidtele.sante")

router = APIRouter(prefix="/api/health", tags=["Système"])

GIO = 1024**3


@router.get("")
async def vivant():
    """Le processus répond (aucune dépendance externe vérifiée)."""
    return {
        "status": "ok",
        "app": "Atlas Play",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _verifier_base() -> dict:
    debut = time.perf_counter()
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok", "latence_ms": round((time.perf_counter() - debut) * 1000, 1)}
    except Exception as exc:  # la cause exacte part dans les journaux, pas dans la réponse
        logger.error("Base de données indisponible : %s", exc)
        return {"status": "ko"}


def _verifier_telegram() -> dict:
    # Lecture de l'état local uniquement : aucun appel réseau vers Telegram
    if not telegram_manager.is_configured():
        return {"status": "non_configure"}
    client = telegram_manager.client
    connecte = bool(client and client.is_connected())
    return {"status": "ok" if connecte else "deconnecte"}


def _verifier_disque(chemin: Path) -> dict:
    try:
        usage = shutil.disk_usage(chemin)
    except OSError:
        return {"status": "ko"}
    libre_gio = usage.free / GIO
    if libre_gio < settings.DISK_MIN_FREE_GB:
        status = "ko"
    elif libre_gio < settings.DISK_MIN_FREE_GB * 2:
        status = "alerte"
    else:
        status = "ok"
    return {
        "status": status,
        "libre_gio": round(libre_gio, 2),
        "total_gio": round(usage.total / GIO, 2),
    }


@router.get("/ready")
async def pret():
    """État détaillé des composants. Statut global : ok, degrade ou ko."""
    composants = {
        "base": await _verifier_base(),
        "telegram": _verifier_telegram(),
        "disque_cache": _verifier_disque(Path(settings.CACHE_DIR)),
        "disque_donnees": _verifier_disque(get_data_dir()),
    }

    # Indispensables : la base et l'espace disque. Telegram absent = vidéos en cache seulement.
    if any(composants[c]["status"] == "ko" for c in ("base", "disque_cache", "disque_donnees")):
        global_ = "ko"
    elif composants["telegram"]["status"] != "ok" or any(
        composants[c]["status"] == "alerte" for c in ("disque_cache", "disque_donnees")
    ):
        global_ = "degrade"
    else:
        global_ = "ok"

    corps = {
        "status": global_,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "composants": composants,
    }
    return JSONResponse(status_code=503 if global_ == "ko" else 200, content=corps)
