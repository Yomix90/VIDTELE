"""
Gestionnaire et client asynchrone Telethon MTProto pour l'API VidTele.
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from app.config import settings

logger = logging.getLogger("vidtele.telegram")


class TelegramManager:
    """Gestionnaire centralisé de la connexion Telegram MTProto."""

    def __init__(self):
        self._client: Optional[TelegramClient] = None
        self._is_started: bool = False
        self._channel_entity = None
        self._session_path = Path(__file__).resolve().parent.parent / settings.TELEGRAM_SESSION_NAME

    @property
    def client(self) -> Optional[TelegramClient]:
        return self._client

    def is_configured(self) -> bool:
        """Vérifie si les paramètres Telegram sont renseignés."""
        return (
            bool(settings.TELEGRAM_API_ID)
            and settings.TELEGRAM_API_ID != 0
            and bool(settings.TELEGRAM_API_HASH)
            and settings.TELEGRAM_API_HASH != "none"
        )

    def session_exists(self) -> bool:
        """Vérifie si le fichier .session existe sur le disque."""
        session_file = Path(f"{self._session_path}.session")
        return session_file.exists()

    async def start(self) -> bool:
        """Initialise et démarre le client Telethon."""
        if not self.is_configured():
            logger.warning("Telegram n'est pas encore configuré dans le fichier .env (API_ID/API_HASH manquants).")
            return False

        if not self.session_exists():
            logger.warning(
                f"Fichier de session '{self._session_path}.session' introuvable. "
                "Exécutez 'python login_telegram.py' pour initialiser la session."
            )
            return False

        try:
            logger.info("Connexion au réseau Telegram MTProto...")
            self._client = TelegramClient(
                str(self._session_path),
                settings.TELEGRAM_API_ID,
                settings.TELEGRAM_API_HASH,
                # Optimisations de téléchargement par blocs
                flood_sleep_threshold=60,
                request_retries=5,
                connection_retries=5,
            )

            await self._client.connect()

            if not await self._client.is_user_authorized():
                logger.error("Session Telegram non autorisée ou expirée. Veuillez relancer 'login_telegram.py'.")
                return False

            me = await self._client.get_me()
            logger.info(f"Connecté avec succès à Telegram : {me.first_name} (ID: {me.id})")

            # Résolution de l'entité du canal si configuré
            if settings.TELEGRAM_CHANNEL_ID and settings.TELEGRAM_CHANNEL_ID != 0:
                try:
                    self._channel_entity = await self._client.get_entity(settings.TELEGRAM_CHANNEL_ID)
                    logger.info(f"Canal cible validé : '{getattr(self._channel_entity, 'title', 'Canal Privé')}'")
                except Exception as e:
                    logger.warning(f"Impossible de résoudre le canal {settings.TELEGRAM_CHANNEL_ID}: {e}")

            self._is_started = True
            return True

        except Exception as e:
            logger.error(f"Erreur lors du démarrage du client Telegram: {e}", exc_info=True)
            return False

    async def stop(self):
        """Déconnecte proprement le client Telethon."""
        if self._client and self._client.is_connected():
            logger.info("Déconnexion du client Telegram...")
            await self._client.disconnect()
        self._is_started = False

    async def get_channel_entity(self):
        """Récupère l'entité du canal configuré avec résolution intelligente de l'ID."""
        if not self._client or not settings.TELEGRAM_CHANNEL_ID:
            return None

        if self._channel_entity:
            return self._channel_entity

        raw_id = settings.TELEGRAM_CHANNEL_ID
        candidates = [raw_id]

        s_id = str(raw_id)
        if not s_id.startswith("-100"):
            clean = s_id.lstrip("-")
            candidates.append(int(f"-100{clean}"))
            candidates.append(int(clean))
        else:
            clean = s_id.replace("-100", "")
            candidates.append(int(f"-{clean}"))
            candidates.append(int(clean))

        for cid in candidates:
            try:
                entity = await self._client.get_entity(cid)
                if entity:
                    self._channel_entity = entity
                    title = getattr(entity, "title", "Canal")
                    logger.info(f"Canal Telegram résolu avec succès : '{title}' (ID utilisé: {cid})")
                    return self._channel_entity
            except Exception:
                continue

        logger.warning(f"Impossible de résoudre le canal avec les variantes d'ID : {candidates}")
        return None

    async def download_thumbnail(self, message, target_path: Path) -> Optional[str]:
        """
        Télécharge la miniature associée à un message vidéo.
        Gère automatiquement le FloodWait.
        """
        if not self._client or not self._is_started:
            return None

        retries = 3
        while retries > 0:
            try:
                # Telethon permet de télécharger directement la miniature (thumb=-1 pour la plus haute qualité)
                path = await self._client.download_media(
                    message,
                    file=str(target_path),
                    thumb=-1,
                )
                return path
            except FloodWaitError as e:
                logger.warning(f"Telegram FloodWait: attente de {e.seconds} secondes...")
                await asyncio.sleep(e.seconds)
                retries -= 1
            except Exception as e:
                logger.warning(f"Échec du téléchargement de la miniature pour le message {message.id}: {e}")
                return None
        return None


# Instance unique (Singleton)
telegram_manager = TelegramManager()
