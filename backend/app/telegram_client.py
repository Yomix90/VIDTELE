"""
Gestionnaire et client asynchrone Telethon MTProto pour l'API VidTele.
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from app.config import settings

logger = logging.getLogger("vidtele.telegram")


class TelegramManager:
    """Gestionnaire centralisé de la connexion Telegram MTProto."""

    def __init__(self):
        self._client: Optional[TelegramClient] = None
        self._is_started: bool = False
        self._channel_entity = None
        session_name = settings.TELEGRAM_SESSION_NAME
        if Path(session_name).is_absolute():
            self._session_path = Path(session_name)
        else:
            self._session_path = Path(__file__).resolve().parent.parent / session_name
        self._session_path.parent.mkdir(parents=True, exist_ok=True)

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
        """Vérifie si une session est disponible (StringSession ou fichier .session)."""
        if bool(settings.TELEGRAM_STRING_SESSION):
            return True
        session_file = Path(f"{self._session_path}.session")
        return session_file.exists()

    async def start(self) -> bool:
        """Initialise et démarre le client Telethon."""
        if not self.is_configured():
            logger.warning("Telegram n'est pas encore configuré dans le fichier .env (API_ID/API_HASH manquants).")
            return False

        if not self.session_exists():
            logger.warning(
                f"Fichier de session '{self._session_path}.session' introuvable et TELEGRAM_STRING_SESSION non configuré. "
                "Exécutez 'python login_telegram.py' ou renseignez TELEGRAM_STRING_SESSION pour initialiser la session."
            )
            return False

        try:
            logger.info("Connexion au réseau Telegram MTProto...")
            if settings.TELEGRAM_STRING_SESSION:
                session = StringSession(settings.TELEGRAM_STRING_SESSION.strip())
                logger.info("Utilisation de la session en mémoire TELEGRAM_STRING_SESSION (Dokploy / Sans fichier).")
            else:
                session = str(self._session_path)
                logger.info(f"Utilisation du fichier de session sur disque : '{self._session_path}.session'")

            self._client = TelegramClient(
                session,
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

        # Fallback via iter_dialogs si get_entity ne résout pas directement le canal privé
        try:
            target_clean = "".join(filter(str.isdigit, str(raw_id)))
            async for dialog in self._client.iter_dialogs(limit=150):
                d_clean = "".join(filter(str.isdigit, str(dialog.id)))
                if dialog.id in candidates or (target_clean and target_clean in d_clean):
                    self._channel_entity = dialog.entity
                    title = getattr(dialog.entity, "title", getattr(dialog, "name", "Canal"))
                    logger.info(f"Canal Telegram résolu via la liste des dialogues : '{title}' (ID: {dialog.id})")
                    return self._channel_entity
        except Exception as e:
            logger.warning(f"Erreur lors de la recherche dans les dialogues : {e}")

        logger.warning(f"Impossible de résoudre le canal avec les variantes d'ID : {candidates}")
        return None

    async def get_connection_status(self) -> dict:
        """Retourne l'état détaillé de la connexion Telegram MTProto."""
        if (not self._client or not self._client.is_connected()) and self.is_configured() and self.session_exists():
            await self.start()

        is_conn = bool(self._client and self._client.is_connected())
        account_info = None
        if is_conn:
            try:
                me = await self._client.get_me()
                if me:
                    account_info = {
                        "id": me.id,
                        "first_name": getattr(me, "first_name", "") or "",
                        "username": getattr(me, "username", "") or "",
                        "phone": getattr(me, "phone", "") or "",
                    }
            except Exception:
                pass

        channel_title = None
        if self._channel_entity:
            channel_title = getattr(self._channel_entity, "title", str(self._channel_entity))
        elif is_conn and settings.TELEGRAM_CHANNEL_ID:
            entity = await self.get_channel_entity()
            if entity:
                channel_title = getattr(entity, "title", str(entity))

        return {
            "is_configured": self.is_configured(),
            "session_exists": self.session_exists(),
            "is_connected": is_conn,
            "account": account_info,
            "current_channel_id": settings.TELEGRAM_CHANNEL_ID,
            "current_channel_title": channel_title,
        }

    async def list_available_channels(self) -> list:
        """Liste les canaux et groupes auxquels le compte Telegram a accès."""
        if (not self._client or not self._client.is_connected()) and self.is_configured() and self.session_exists():
            await self.start()

        if not self._client or not self._client.is_connected():
            return []

        channels = []
        try:
            async for dialog in self._client.iter_dialogs(limit=100):
                if dialog.is_channel or dialog.is_group:
                    channels.append({
                        "id": dialog.id,
                        "title": dialog.name,
                        "is_channel": dialog.is_channel,
                        "is_group": dialog.is_group,
                        "username": getattr(dialog.entity, "username", None),
                    })
        except Exception as e:
            logger.warning(f"Erreur lors de la récupération des dialogues : {e}")

        return channels

    async def test_channel(self, channel_target: str | int) -> dict:
        """Teste l'accès à un canal ou groupe spécifique et retourne ses métadonnées."""
        if (not self._client or not self._client.is_connected()) and self.is_configured() and self.session_exists():
            await self.start()

        if not self._client or not self._client.is_connected():
            return {
                "success": False,
                "error": "Le client Telegram MTProto n'est pas connecté au serveur. Vérifiez vos identifiants API ou relancez login_telegram.py.",
            }

        target_str = str(channel_target).strip()
        candidates = []

        try:
            num = int(target_str)
            candidates.append(num)
            clean = str(abs(num))
            if not clean.startswith("100"):
                candidates.append(int(f"-100{clean}"))
                candidates.append(int(f"-{clean}"))
                candidates.append(int(clean))
            else:
                raw_c = clean[3:]
                candidates.append(int(f"-{raw_c}"))
                candidates.append(int(raw_c))
        except ValueError:
            cleaned = target_str.replace("https://t.me/", "").replace("http://t.me/", "").lstrip("@")
            candidates.append(f"@{cleaned}")
            candidates.append(cleaned)

        entity = None
        used_id = None
        last_error = None

        # 1. Essai direct
        for cand in candidates:
            try:
                e = await self._client.get_entity(cand)
                if e:
                    entity = e
                    used_id = cand
                    break
            except Exception as ex:
                last_error = ex
                continue

        # 2. Essai via les dialogues
        if not entity:
            try:
                target_clean_digits = "".join(filter(str.isdigit, target_str))
                async for dialog in self._client.iter_dialogs(limit=150):
                    d_clean_digits = "".join(filter(str.isdigit, str(dialog.id)))
                    if (
                        str(dialog.id) in [str(c) for c in candidates]
                        or (target_clean_digits and target_clean_digits in d_clean_digits)
                        or (isinstance(dialog.name, str) and dialog.name.lower() == target_str.lower())
                    ):
                        entity = dialog.entity
                        used_id = dialog.id
                        break
            except Exception as ex:
                last_error = ex

        if not entity:
            return {
                "success": False,
                "error": f"Canal introuvable ou accès refusé. Vérifiez que votre compte Telegram est bien membre ou administrateur. ({last_error})",
            }

        title = getattr(entity, "title", getattr(entity, "first_name", "Canal"))
        username = getattr(entity, "username", None)
        entity_id = getattr(entity, "id", used_id)
        formatted_id = entity_id
        if isinstance(entity_id, int) and entity_id > 0 and getattr(entity, "broadcast", False):
            formatted_id = int(f"-100{entity_id}")

        can_read = False
        message_count_test = 0
        try:
            messages = await self._client.get_messages(entity, limit=5)
            can_read = True
            message_count_test = len(messages)
        except Exception:
            can_read = False

        return {
            "success": True,
            "id": entity_id,
            "formatted_id": formatted_id,
            "title": title,
            "username": username,
            "is_channel": getattr(entity, "broadcast", True),
            "can_read_messages": can_read,
            "sample_messages_found": message_count_test,
        }

    async def set_active_channel(self, channel_id: int) -> dict:
        """Met à jour le canal actif en mémoire."""
        settings.TELEGRAM_CHANNEL_ID = channel_id
        self._channel_entity = None
        entity = await self.get_channel_entity()
        title = getattr(entity, "title", "Canal") if entity else None
        return {
            "success": True,
            "channel_id": channel_id,
            "title": title,
        }

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

