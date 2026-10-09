"""
Point d'entrée principal de l'application VidTele (FastAPI).
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.models import InviteCode, User
from app.routers import admin, admin_web, auth, library, videos
from app.security import hash_password
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
            logger.info(f"==> Administrateur créé: '{settings.ADMIN_DEFAULT_USERNAME}' / '{settings.ADMIN_DEFAULT_PASSWORD}'")

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

# Inclusion des routeurs
app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(library.router)
app.include_router(admin.router)
app.include_router(admin_web.router)


@app.get("/api/health", tags=["Système"])
async def health_check():
    """Vérification de santé de l'API."""
    return {
        "status": "ok",
        "app": "VidTele",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
