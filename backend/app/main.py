"""
Point d'entrée principal de l'application VidTele (FastAPI).
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from typing import List, Optional
from app.config import settings
from app.database import AsyncSessionLocal, get_db, init_db
from app.models import InviteCode, User
from app.routers import admin, admin_web, ads, auth, library, videos
from app.schemas import FeedResponse, HomeScreenResponse, TopSeriesItem
from app.security import get_current_active_user, hash_password
from app.services.sync_service import sync_service
from app.telegram_client import telegram_manager

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vidtele")


async def bootstrap_admin_and_invites():
    """Crée le compte admin et un code d'invitation initial si la base est neuve."""
    async with AsyncSessionLocal() as db:
        # 1. Vérifier si un compte admin existe
        stmt_admin = select(User).where(User.role == "admin")
        result_admin = await db.execute(stmt_admin)
        admin = result_admin.scalar_one_or_none()

        if not admin:
            logger.info("Aucun compte administrateur trouvé. Création de l'administrateur par défaut...")
            admin = User(
                username=settings.ADMIN_DEFAULT_USERNAME,
                hashed_password=hash_password(settings.ADMIN_DEFAULT_PASSWORD),
                role="admin",
                is_active=True,
                max_concurrent_streams=5,
            )
            db.add(admin)
            await db.flush()
            logger.info(f"==> Administrateur créé: '{settings.ADMIN_DEFAULT_USERNAME}'")
        else:
            admin.hashed_password = hash_password(settings.ADMIN_DEFAULT_PASSWORD)
            admin.is_active = True
            logger.info(f"==> Mot de passe administrateur synchronisé pour '{admin.username}'")


        # 2. Vérifier si le code de bienvenue existe déjà (qu'il soit utilisé ou non)
        welcome_code = "BIENVENUE-2026"
        stmt_invite = select(InviteCode).where(InviteCode.code == welcome_code)
        result_invite = await db.execute(stmt_invite)
        existing_invite = result_invite.scalar_one_or_none()

        if not existing_invite:
            invite = InviteCode(
                code=welcome_code,
                created_by_id=admin.id,
                is_used=False,
            )
            db.add(invite)
            logger.info(f"==> Code d'invitation initial généré: '{welcome_code}'")

        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cycle de vie de l'application FastAPI."""
    logger.info("Démarrage de l'application VidTele...")
    # Initialisation de la base SQLite
    await init_db()
    # Amorçage admin et invitations
    await bootstrap_admin_and_invites()
    logger.info("Base de données et tables initialisées avec succès.")

    # Restauration des paramètres dynamiques depuis la base (ex: TELEGRAM_CHANNEL_ID)
    from app.models import SystemSetting
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(SystemSetting).where(SystemSetting.key == "TELEGRAM_CHANNEL_ID"))
        setting = res.scalar_one_or_none()
        if setting and setting.value:
            try:
                settings.TELEGRAM_CHANNEL_ID = int(setting.value)
                logger.info(f"Canal Telegram restauré depuis la base de données : {settings.TELEGRAM_CHANNEL_ID}")
            except ValueError:
                pass

    # Démarrage du client Telegram MTProto
    periodic_task = None
    telegram_started = await telegram_manager.start()
    if telegram_started:
        sync_service.register_realtime_listener()
        periodic_task = asyncio.create_task(sync_service.start_periodic_sync())
        logger.info("Service de synchronisation Telegram activé (temps réel + périodique).")
    else:
        logger.info("L'application démarre sans connexion Telegram active (mode local / en attente de configuration).")

    yield

    # Arrêt propre
    if periodic_task:
        periodic_task.cancel()
    await telegram_manager.stop()
    logger.info("Arrêt de l'application VidTele.")


# Création de l'application FastAPI
app = FastAPI(
    title="VidTele Backend API",
    description="API de streaming vidéo privé depuis Telegram pour application mobile Flutter.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configuration CORS pour autoriser l'app Flutter (Web/Mobile/Émulateur)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, peut être restreint au domaine
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fichiers statiques StreamAdmin (CSS, JS, images)
from pathlib import Path
from fastapi.staticfiles import StaticFiles
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Inclusion des routeurs
app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(library.router)
app.include_router(admin.router)
app.include_router(admin_web.router)
app.include_router(ads.router)


@app.get("/api/health", tags=["Système"])
async def health_check():
    """Vérification de santé de l'API."""
    return {
        "status": "ok",
        "app": "Atlas Play",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/home", response_model=HomeScreenResponse, tags=["Accueil"])
async def get_home_alias(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Alias racine pour le chargement complet de l'écran d'accueil."""
    return await videos.get_home_content(current_user=current_user, db=db)


@app.get("/api/series/top", response_model=List[TopSeriesItem], tags=["Séries"])
async def get_series_top_alias(
    period: str = "7d",
    limit: int = 5,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Alias racine pour le classement Top des séries."""
    return await videos.get_top_series(period=period, limit=limit, current_user=current_user, db=db)


@app.get("/api/feed", response_model=FeedResponse, tags=["Feed Vertical"])
async def get_feed_alias(
    cursor: Optional[int] = None,
    limit: int = 15,
    series_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Alias racine pour le flux vertical d'épisodes et de vidéos."""
    return await videos.get_vertical_feed(
        cursor=cursor,
        limit=limit,
        series_id=series_id,
        current_user=current_user,
        db=db,
    )


@app.get("/api/series/{series_id}", tags=["Séries"])
async def get_series_detail_alias(
    series_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Alias racine pour le détail d'une série avec épisodes et séries similaires."""
    return await videos.get_public_series_detail(series_id=series_id, current_user=current_user, db=db)


@app.post("/api/series/{series_id}/favorite", tags=["Séries"])
async def toggle_series_favorite_alias(
    series_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Alias racine pour basculer le statut favori d'une série."""
    return await videos.toggle_series_favorite(series_id=series_id, current_user=current_user, db=db)


@app.get("/api/app/version", tags=["Application Mobile"])
async def check_app_version(
    current_version: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint public consulté au lancement de l'application mobile Atlas Play.
    Vérifie si une mise à jour est disponible ou obligatoire.
    """
    from app.models import SystemSetting

    def parse_semver(v: str) -> tuple:
        parts = []
        for x in str(v).strip().split("."):
            try:
                parts.append(int(x))
            except ValueError:
                parts.append(0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])

    # Récupérer les paramètres système de mise à jour
    settings_keys = [
        "app_latest_version",
        "app_min_version",
        "app_update_url",
        "app_update_title",
        "app_update_notes",
        "app_update_force",
    ]
    res = await db.execute(select(SystemSetting).where(SystemSetting.key.in_(settings_keys)))
    settings_dict = {row.key: row.value for row in res.scalars().all()}

    apk_fallback = Path(__file__).resolve().parent / "static" / "uploads" / "apk" / "atlas-play.apk"
    fallback_url = "/static/uploads/apk/atlas-play.apk" if apk_fallback.exists() else ""

    latest_ver = settings_dict.get("app_latest_version", "1.2.0")
    min_ver = settings_dict.get("app_min_version", "1.0.0")
    download_url = settings_dict.get("app_update_url") or fallback_url
    title = settings_dict.get("app_update_title", "Nouvelle version Atlas Play disponible")
    notes = settings_dict.get("app_update_notes", "Améliorations des posters, zapping TikTok, enchaînement automatique des épisodes et veille d'écran.")
    force_update = settings_dict.get("app_update_force", "false").lower() == "true"

    has_update = False
    is_forced = force_update

    if current_version:
        try:
            cur_v = parse_semver(current_version)
            lat_v = parse_semver(latest_ver)
            min_v = parse_semver(min_ver)
            has_update = cur_v < lat_v
            if cur_v < min_v:
                is_forced = True
        except Exception:
            has_update = current_version != latest_ver

    return {
        "latest_version": latest_ver,
        "min_version": min_ver,
        "download_url": download_url,
        "title": title,
        "release_notes": notes,
        "force_update": is_forced,
        "has_update": has_update,
    }
