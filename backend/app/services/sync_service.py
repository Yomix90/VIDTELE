"""
Service de synchronisation des vidéos depuis le canal privé Telegram vers SQLite.
Supporte la synchronisation manuelle, périodique et l'écoute en direct (NewMessage events).
"""
import asyncio
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from sqlalchemy import select
from telethon import events
from telethon.tl.types import DocumentAttributeVideo

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Video
from app.telegram_client import telegram_manager

logger = logging.getLogger("vidtele.sync")


class SyncService:
    """Service gérant la découverte et l'indexation des vidéos Telegram."""

    def __init__(self):
        self._is_syncing: bool = False
        self._sync_task: Optional[asyncio.Task] = None
        self._listener_registered: bool = False

    def is_syncing(self) -> bool:
        return self._is_syncing

    def _extract_category_and_title(self, raw_caption: Optional[str], default_name: str) -> Tuple[str, str, Optional[str]]:
        """
        Extrait la catégorie (#hashtag), le titre et la légende propre.
        """
        if not raw_caption:
            return default_name, "Général", None

        clean_text = raw_caption.strip()

        # Recherche de hashtags (#serie1, #formation, #humour)
        hashtags = re.findall(r"#([a-zA-Z0-9_\u0600-\u06FF]+)", clean_text)
        category = hashtags[0].capitalize() if hashtags else "Général"

        # Le titre est la première ligne sans les hashtags isolés
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        if lines:
            first_line = lines[0]
            # Nettoyer les hashtags du titre
            title = re.sub(r"#[a-zA-Z0-9_\u0600-\u06FF]+", "", first_line).strip()
            if not title:
                title = default_name
        else:
            title = default_name

        return title, category, clean_text

    def _is_video_message(self, message) -> bool:
        """Vérifie si le message contient une vidéo valide."""
        if not message or not message.media:
            return False

        if getattr(message, "video", None):
            return True

        if getattr(message, "document", None):
            mime = getattr(message.document, "mime_type", "") or ""
            if mime.startswith("video/"):
                return True

        return False

    async def _process_video_message(self, message, db) -> Optional[Video]:
        """Traite un message Telegram individuel et met à jour la base de données."""
        if not self._is_video_message(message):
            return None

        # Durée et attributs
        duration = 0
        if getattr(message, "document", None) and hasattr(message.document, "attributes"):
            for attr in message.document.attributes:
                if isinstance(attr, DocumentAttributeVideo):
                    duration = int(attr.duration or 0)
                    break

        file_size = getattr(message.file, "size", 0) or 0
        mime_type = getattr(message.file, "mime_type", "video/mp4") or "video/mp4"
        file_name = getattr(message.file, "name", None)
        raw_caption = getattr(message, "message", "")

        default_name = file_name or f"Vidéo #{message.id}"
        title, category, caption = self._extract_category_and_title(raw_caption, default_name)

        # Date du message Telegram
        msg_date = message.date.replace(tzinfo=None) if message.date else datetime.now(timezone.utc).replace(tzinfo=None)

        # Recherche en base
        stmt = select(Video).where(Video.telegram_message_id == message.id)
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()

        thumbnail_filename = f"thumb_{message.id}.jpg"
        thumbnail_disk_path = Path(settings.THUMBNAILS_DIR) / thumbnail_filename

        # Téléchargement de la miniature si absente
        if not thumbnail_disk_path.exists():
            downloaded = await telegram_manager.download_thumbnail(message, thumbnail_disk_path)
            thumbnail_rel_path = f"/api/videos/{message.id}/thumbnail" if downloaded else None
        else:
            thumbnail_rel_path = f"/api/videos/{message.id}/thumbnail"

        if video:
            # Mise à jour
            video.title = title
            video.caption = caption
            video.category = category
            video.duration_seconds = duration
            video.file_size_bytes = file_size
            video.mime_type = mime_type
            video.thumbnail_path = thumbnail_rel_path
            video.file_name = file_name
        else:
            # Création
            video = Video(
                telegram_message_id=message.id,
                title=title,
                caption=caption,
                category=category,
                duration_seconds=duration,
                file_size_bytes=file_size,
                mime_type=mime_type,
                thumbnail_path=thumbnail_rel_path,
                file_name=file_name,
                telegram_date=msg_date,
            )
            db.add(video)

        return video

    async def sync_channel(self) -> Dict[str, int]:
        """
        Synchronise manuellement l'intégralité du canal Telegram configuré.
        Retourne des statistiques (ajoutées, mises à jour, total).
        """
        if self._is_syncing:
            logger.warning("Une synchronisation est déjà en cours.")
            return {"status": "already_running", "processed": 0}

        client = telegram_manager.client
        if not client or not telegram_manager.is_configured() or not telegram_manager.session_exists():
            logger.warning("Synchronisation impossible : client Telegram non connecté.")
            return {"status": "not_connected", "processed": 0}

        channel = await telegram_manager.get_channel_entity()
        if not channel:
            logger.warning("Canal Telegram introuvable ou inaccessible.")
            return {"status": "channel_not_found", "processed": 0}

        channel_title = getattr(channel, "title", getattr(channel, "first_name", "Canal"))
        logger.info(f"Canal cible résolu : '{channel_title}' (ID: {channel.id})")

        self._is_syncing = True
        stats = {"added": 0, "updated": 0, "total_messages": 0}

        try:
            logger.info(f"Début du parcours des messages dans '{channel_title}'...")
            async with AsyncSessionLocal() as db:
                # Parcours des messages du canal
                async for message in client.iter_messages(channel, limit=None):
                    stats["total_messages"] += 1
                    is_vid = self._is_video_message(message)
                    logger.info(f"Message ID {message.id} inspecté: est_vidéo={is_vid}, texte='{message.message[:30] if message.message else ''}'")
                    if is_vid:
                        # Vérifier si déjà présent
                        stmt = select(Video.id).where(Video.telegram_message_id == message.id)
                        exists = (await db.execute(stmt)).scalar_one_or_none() is not None

                        await self._process_video_message(message, db)
                        if exists:
                            stats["updated"] += 1
                        else:
                            stats["added"] += 1

                await db.commit()
            logger.info(f"Synchronisation terminée avec succès: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Erreur pendant la synchronisation du canal: {e}", exc_info=True)
            return {"status": "error", "error": str(e), **stats}
        finally:
            self._is_syncing = False

    def register_realtime_listener(self):
        """Enregistre un écouteur en temps réel pour synchroniser instantanément les nouvelles vidéos."""
        client = telegram_manager.client
        if not client or self._listener_registered:
            return

        channel_id = settings.TELEGRAM_CHANNEL_ID
        if not channel_id or channel_id == 0:
            return

        @client.on(events.NewMessage(chats=channel_id))
        async def handler(event):
            try:
                message = event.message
                if self._is_video_message(message):
                    logger.info(f"Nouvelle vidéo détectée dans le canal (ID message: {message.id}). Indexation...")
                    async with AsyncSessionLocal() as db:
                        await self._process_video_message(message, db)
                        await db.commit()
                    logger.info(f"Vidéo {message.id} indexée automatiquement avec succès.")
            except Exception as err:
                logger.error(f"Erreur lors de l'indexation de l'événement nouveau message: {err}")

        self._listener_registered = True
        logger.info("Écouteur d'événements en direct (NewMessage) activé sur le canal Telegram.")

    async def start_periodic_sync(self):
        """Boucle d'arrière-plan pour synchroniser régulièrement le canal."""
        while True:
            try:
                await asyncio.sleep(settings.SYNC_INTERVAL_MINUTES * 60)
                if telegram_manager.is_configured() and telegram_manager.session_exists():
                    logger.info("Déclenchement de la synchronisation périodique du canal...")
                    await self.sync_channel()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans la tâche périodique de synchronisation: {e}")


# Instance unique (Singleton)
sync_service = SyncService()
