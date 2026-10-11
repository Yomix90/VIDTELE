"""
Point d'entrée principal de l'application VidTele (FastAPI).
"""
import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import (
    PUBLIC_DEFAULT_ADMIN_PASSWORDS,
    SECRET_KEY_SOURCE,
    get_data_dir,
    settings,
    write_private_file,
)
from app.core.erreurs import installer_gestionnaires_erreurs
from app.core.journalisation import configurer_journalisation
from app.core.requetes import MiddlewareContexteRequete
from app.core.version_minimale import MiddlewareVersionMinimale
from app.database import AsyncSessionLocal, init_db
from app.models import InviteCode, User
from app.routers import (
    admin,
    admin_web,
    ads,
    alias,
    analytique_lecture,
    application_mobile,
    auth,
    library,
    sante,
    videos,
)
from app.security import hash_password, verify_password
from app.services.prechauffage import boucle_prechauffage
from app.services.sync_service import sync_service
from app.services.telechargement_progressif import nettoyer_fichiers_incomplets
from app.telegram_client import telegram_manager

# Configuration des logs
configurer_journalisation(settings.LOG_LEVEL, settings.LOG_FORMAT)
logger = logging.getLogger("vidtele")


async def bootstrap_admin_and_invites():
    """Crée le compte admin et un code d'invitation initial si la base est neuve."""
    async with AsyncSessionLocal() as db:
        # 1. Vérifier si un compte admin existe
        stmt_admin = select(User).where(User.role == "admin")
        result_admin = await db.execute(stmt_admin)
        admin = result_admin.scalar_one_or_none()

        env_password = (settings.ADMIN_DEFAULT_PASSWORD or "").strip()
        env_password_is_public = env_password in PUBLIC_DEFAULT_ADMIN_PASSWORDS

        if not admin:
            logger.info("Aucun compte administrateur trouvé. Création de l'administrateur initial...")
            if env_password_is_public:
                # Jamais de mot de passe public : on en génère un, écrit dans un fichier privé (pas dans les logs)
                initial_password = secrets.token_urlsafe(18)
                password_file = get_data_dir() / "admin_initial_password.txt"
                write_private_file(password_file, initial_password + "\n")
                logger.warning(
                    f"ADMIN_DEFAULT_PASSWORD absent ou public : mot de passe généré dans {password_file} "
                    "(à changer puis supprimer le fichier)."
                )
            else:
                initial_password = env_password
            admin = User(
                username=settings.ADMIN_DEFAULT_USERNAME,
                hashed_password=hash_password(initial_password),
                role="admin",
                is_active=True,
                max_concurrent_streams=5,
            )
            db.add(admin)
            await db.flush()
            logger.info(f"==> Administrateur créé: '{settings.ADMIN_DEFAULT_USERNAME}'")
        elif settings.ADMIN_RESET_PASSWORD:
            # Procédure de secours explicite : réinitialisation depuis la variable d'environnement
            if env_password_is_public:
                logger.error("ADMIN_RESET_PASSWORD=true ignoré : ADMIN_DEFAULT_PASSWORD est vide ou public.")
            else:
                admin.hashed_password = hash_password(env_password)
                admin.is_active = True
                logger.warning(
                    f"==> Mot de passe de '{admin.username}' réinitialisé (ADMIN_RESET_PASSWORD=true). "
                    "Retirez cette variable puis redémarrez."
                )
        # Sinon : le mot de passe en base est conservé (les changements faits depuis l'admin persistent)

        # Alerte si un compte admin utilise encore un mot de passe publié dans le dépôt
        res_admins = await db.execute(select(User).where(User.role == "admin"))
        for adm in res_admins.scalars().all():
            if any(verify_password(p, adm.hashed_password) for p in PUBLIC_DEFAULT_ADMIN_PASSWORDS if p):
                logger.critical(
                    f"Le compte admin '{adm.username}' utilise un mot de passe PUBLIC (présent dans le dépôt). "
                    "Changez-le immédiatement."
                )


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
    if SECRET_KEY_SOURCE == "generated":
        logger.critical("SECRET_KEY non définie (ou publique) : clé générée et stockée dans le dossier de données.")
    # Fichiers vidéo .tmp laissés par un arrêt brutal pendant un téléchargement
    nettoyes = nettoyer_fichiers_incomplets()
    if nettoyes:
        logger.info(f"{nettoyes} fichier(s) vidéo incomplet(s) supprimé(s) du cache")
    # Initialisation de la base SQLite
    await init_db()
    # Amorçage admin et invitations
    await bootstrap_admin_and_invites()
    logger.info("Base de données et tables initialisées avec succès.")

    # Restauration des paramètres dynamiques depuis la base (ex: TELEGRAM_CHANNEL_ID et TelegramAccount actif)
    from app.models import SystemSetting, TelegramAccount
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(SystemSetting).where(SystemSetting.key == "TELEGRAM_CHANNEL_ID"))
        setting = res.scalar_one_or_none()
        if setting and setting.value:
            try:
                settings.TELEGRAM_CHANNEL_ID = int(setting.value)
                logger.info(f"Canal Telegram restauré depuis la base de données : {settings.TELEGRAM_CHANNEL_ID}")
            except ValueError:
                pass

        # Restauration des limites de streaming dynamiques
        res_global = await db.execute(select(SystemSetting).where(SystemSetting.key == "MAX_CONCURRENT_STREAMS_GLOBAL"))
        setting_global = res_global.scalar_one_or_none()
        if setting_global and setting_global.value:
            try:
                settings.MAX_CONCURRENT_STREAMS_GLOBAL = int(setting_global.value)
                logger.info(f"Limite globale de flux simultanés restaurée : {settings.MAX_CONCURRENT_STREAMS_GLOBAL}")
            except ValueError:
                pass

        res_user = await db.execute(select(SystemSetting).where(SystemSetting.key == "MAX_CONCURRENT_STREAMS_PER_USER"))
        setting_user = res_user.scalar_one_or_none()
        if setting_user and setting_user.value:
            try:
                settings.MAX_CONCURRENT_STREAMS_PER_USER = int(setting_user.value)
                logger.info(f"Limite de flux par utilisateur restaurée : {settings.MAX_CONCURRENT_STREAMS_PER_USER}")
            except ValueError:
                pass


        # Vérifier si un compte Telegram actif est enregistré dans la table telegram_accounts
        res_acc = await db.execute(select(TelegramAccount).where(TelegramAccount.is_active == True))
        active_acc = res_acc.scalar_one_or_none()
        if active_acc and active_acc.string_session:
            settings.TELEGRAM_STRING_SESSION = active_acc.string_session
            if active_acc.api_id:
                settings.TELEGRAM_API_ID = active_acc.api_id
            if active_acc.api_hash:
                settings.TELEGRAM_API_HASH = active_acc.api_hash
            logger.info(f"Session Telegram active restaurée depuis la base de données : '{active_acc.name}'")

    # Démarrage du client Telegram MTProto
    periodic_task = None
    prechauffage_task = None
    telegram_started = await telegram_manager.start()
    if telegram_started:
        sync_service.register_realtime_listener()
        periodic_task = asyncio.create_task(sync_service.start_periodic_sync())
        prechauffage_task = asyncio.create_task(boucle_prechauffage())
        logger.info("Service de synchronisation Telegram activé (temps réel + périodique).")
    else:
        logger.info("L'application démarre sans connexion Telegram active (mode local / en attente de configuration).")

    yield

    # Arrêt propre
    if periodic_task:
        periodic_task.cancel()
    if prechauffage_task:
        prechauffage_task.cancel()
    await telegram_manager.stop()
    logger.info("Arrêt de l'application VidTele.")


# Création de l'application FastAPI
app = FastAPI(
    title="VidTele Backend API",
    description="API de streaming vidéo privé depuis Telegram pour application mobile Flutter.",
    version="1.0.0",
    lifespan=lifespan,
)

# Version minimale de l'app (en-tête X-App-Version) : ajouté avant CORS pour que
# la réponse 426 reçoive aussi les en-têtes CORS et le request_id
app.add_middleware(MiddlewareVersionMinimale)

# Configuration CORS pour autoriser l'app Flutter (Web/Mobile/Émulateur)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, peut être restreint au domaine
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Contexte de requête (request_id + journal d'accès) : ajouté en dernier = exécuté en premier
app.add_middleware(MiddlewareContexteRequete)

# Format d'erreur uniforme {"detail", "code", "request_id"} sur /api
installer_gestionnaires_erreurs(app)

# Fichiers statiques et uploads persistants
from pathlib import Path
from fastapi.staticfiles import StaticFiles

# Dossier d'uploads persistant (dans le volume Docker /app/data/uploads ou local static/uploads)
persistent_uploads = Path("/app/data/uploads") if Path("/app/data").is_dir() else (Path(__file__).resolve().parent / "static" / "uploads")
persistent_uploads.mkdir(parents=True, exist_ok=True)
(persistent_uploads / "apk").mkdir(parents=True, exist_ok=True)

static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
(static_dir / "uploads").mkdir(parents=True, exist_ok=True)

# 1. Monter prioritairement /static/uploads vers le stockage persistant
app.mount("/static/uploads", StaticFiles(directory=str(persistent_uploads)), name="static_uploads")
# 2. Monter le reste des fichiers statiques (CSS, JS, Jinja assets)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Inclusion des routeurs
app.include_router(sante.router)
app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(library.router)
app.include_router(admin.router)
app.include_router(admin_web.router)
app.include_router(ads.router)
app.include_router(alias.router)
app.include_router(application_mobile.router)
app.include_router(analytique_lecture.router)
