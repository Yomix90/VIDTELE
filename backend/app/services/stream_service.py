"""
Service de streaming vidéo haute performance avec support des requêtes HTTP Range (206 Partial Content).
Téléchargement par morceaux via Telethon MTProto, verrous de concurrence et streaming sans surcharge RAM.
"""
import asyncio
import logging
import os
import re
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional, Tuple
import aiofiles
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from telethon.errors import FloodWaitError

from app.config import settings
from app.models import Video
from app.services.cache_service import cache_service
from app.telegram_client import telegram_manager

logger = logging.getLogger("vidtele.stream")

CHUNK_SIZE = 64 * 1024  # 64 Ko par paquet pour une latence minimale et RAM ultra faible


class StreamService:
    """Moteur de streaming vidéo gérant la mise en cache et les requêtes Range."""

    def __init__(self):
        # Dictionnaire de verrous pour éviter le téléchargement simultané d'une même vidéo
        self._video_locks: Dict[int, asyncio.Lock] = {}
        self._master_lock = asyncio.Lock()

    async def _get_video_lock(self, video_id: int) -> asyncio.Lock:
        """Récupère ou crée le verrou associé à une vidéo spécifique."""
        async with self._master_lock:
            if video_id not in self._video_locks:
                self._video_locks[video_id] = asyncio.Lock()
            return self._video_locks[video_id]

    async def ensure_video_in_cache(self, video: Video) -> Path:
        """
        Garantit que la vidéo est présente sur le disque local.
        Si absente, la télécharge depuis Telegram par morceaux avec gestion de concurrence.
        """
        ext = "mp4"
        if video.file_name and "." in video.file_name:
            ext = video.file_name.rsplit(".", 1)[1].lower()
        elif video.mime_type:
            if "mp2t" in video.mime_type:
                ext = "ts"
            elif "matroska" in video.mime_type:
                ext = "mkv"
            elif "webm" in video.mime_type:
                ext = "webm"

        cached_path = cache_service.get_video_path(video.telegram_message_id, extension=ext)

        # Si le fichier existe déjà et est complet, on met à jour son timestamp LRU
        if cache_service.is_cached(video.telegram_message_id):
            cache_service.touch(video.telegram_message_id)
            return cached_path

        # Acquisition du verrou spécifique à cette vidéo
        lock = await self._get_video_lock(video.telegram_message_id)
        async with lock:
            # Double vérification : un autre worker vient peut-être de terminer le téléchargement
            if cache_service.is_cached(video.telegram_message_id):
                cache_service.touch(video.telegram_message_id)
                return cached_path

            # Vérification et rétablissement automatique de l'état du client Telegram
            client = telegram_manager.client
            if not client or not client.is_connected():
                logger.info("Client Telegram non connecté lors de la demande de flux : tentative de démarrage automatique...")
                # Tenter de restaurer le compte actif depuis la base si disponible
                try:
                    from app.database import AsyncSessionLocal
                    from app.models import TelegramAccount
                    async with AsyncSessionLocal() as db_session:
                        stmt_acc = select(TelegramAccount).where(TelegramAccount.is_active == True)
                        active_acc = (await db_session.execute(stmt_acc)).scalar_one_or_none()
                        if active_acc and active_acc.string_session:
                            settings.TELEGRAM_STRING_SESSION = active_acc.string_session
                            if active_acc.api_id:
                                settings.TELEGRAM_API_ID = active_acc.api_id
                            if active_acc.api_hash:
                                settings.TELEGRAM_API_HASH = active_acc.api_hash
                except Exception as ex_db:
                    logger.debug(f"Impossible de vérifier le compte Telegram en base : {ex_db}")

                started = await telegram_manager.start()
                client = telegram_manager.client
                if not started or not client or not client.is_connected():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Le service Telegram MTProto n'est pas connecté sur le serveur. Rendez-vous dans 'Telegram MTProto' sur le panel d'administration pour connecter votre session.",
                    )

            channel = await telegram_manager.get_channel_entity()
            if not channel:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Canal Telegram inaccessible ou identifiant de canal invalide. Vérifiez TELEGRAM_CHANNEL_ID dans les paramètres.",
                )

            # Vérification du quota disque avant téléchargement
            await cache_service.ensure_capacity(needed_bytes=video.file_size_bytes)

            tmp_path = cache_service.cache_dir / f"video_{video.telegram_message_id}.tmp"

            try:
                logger.info(
                    f"Début du téléchargement Telegram pour '{video.title}' "
                    f"(Message ID: {video.telegram_message_id}, Taille: {round(video.file_size_bytes / 1024**2, 2)} Mo)..."
                )

                # Récupération du message Telegram source
                message = await client.get_messages(channel, ids=video.telegram_message_id)
                if not message or not message.media:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Le message vidéo source a été supprimé de Telegram",
                    )

                # Téléchargement par morceaux via Telethon directement dans le fichier temporaire
                # Telethon gère le streaming réseau MTProto par blocs sans charger le fichier en RAM
                retries = 3
                while retries > 0:
                    try:
                        await client.download_media(message, file=str(tmp_path))
                        break
                    except FloodWaitError as e:
                        logger.warning(f"Telegram FloodWait détecté: pause de {e.seconds} secondes...")
                        await asyncio.sleep(e.seconds)
                        retries -= 1
                        if retries == 0:
                            raise HTTPException(
                                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"Surcharge Telegram (FloodWait). Veuillez réessayer dans {e.seconds}s.",
                            )

                # Renommage atomique du fichier temporaire vers le fichier final
                if tmp_path.exists() and tmp_path.stat().st_size > 0:
                    tmp_path.replace(cached_path)
                    cache_service.touch(video.telegram_message_id)
                    logger.info(f"Vidéo '{video.title}' mise en cache avec succès ({cached_path.name})")
                    return cached_path
                else:
                    raise RuntimeError("Échec du téléchargement: fichier temporaire vide")

            except Exception as e:
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
                logger.error(f"Erreur lors de la mise en cache de la vidéo {video.id}: {e}", exc_info=True)
                if isinstance(e, HTTPException):
                    raise e
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Erreur lors du téléchargement de la vidéo depuis Telegram: {str(e)}",
                )

    def parse_range_header(self, range_header: Optional[str], file_size: int) -> Tuple[int, int, int]:
        """
        Analyse l'en-tête HTTP 'Range: bytes=start-end'.
        Retourne (start, end, content_length).
        """
        if not range_header or not range_header.startswith("bytes="):
            return 0, file_size - 1, file_size

        range_val = range_header.replace("bytes=", "").strip()
        parts = range_val.split("-")

        try:
            if parts[0] and parts[1]:
                # bytes=100-200
                start = int(parts[0])
                end = int(parts[1])
            elif parts[0] and not parts[1]:
                # bytes=100-
                start = int(parts[0])
                end = file_size - 1
            elif not parts[0] and parts[1]:
                # bytes=-100 (les 100 derniers octets)
                end = file_size - 1
                start = max(0, file_size - int(parts[1]))
            else:
                return 0, file_size - 1, file_size
        except ValueError:
            return 0, file_size - 1, file_size

        # Bornage
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        content_length = (end - start) + 1

        return start, end, content_length

    async def stream_file_range(
        self,
        file_path: Path,
        start: int,
        content_length: int,
    ) -> AsyncGenerator[bytes, None]:
        """
        Générateur asynchrone qui lit un segment précis du fichier par morceaux de 64 Ko.
        Ne charge jamais le fichier complet en mémoire.
        """
        bytes_sent = 0
        async with aiofiles.open(file_path, mode="rb") as f:
            await f.seek(start)
            while bytes_sent < content_length:
                to_read = min(CHUNK_SIZE, content_length - bytes_sent)
                chunk = await f.read(to_read)
                if not chunk:
                    break
                bytes_sent += len(chunk)
                yield chunk

    async def create_streaming_response(
        self,
        video: Video,
        range_header: Optional[str],
    ) -> StreamingResponse:
        """
        Prépare et renvoie une réponse HTTP 206 Partial Content (ou 200 OK)
        parfaitement compatible avec les lecteurs vidéo mobiles et web.
        """
        # Assurer la présence de la vidéo dans le cache local
        file_path = await self.ensure_video_in_cache(video)
        file_size = file_path.stat().st_size

        start, end, content_length = self.parse_range_header(range_header, file_size)

        # Déterminer le Content-Type le plus précis pour les lecteurs vidéo natifs (Android ExoPlayer / iOS AVPlayer)
        content_type = video.mime_type
        if file_path.suffix.lower() in [".ts", ".m2ts"]:
            content_type = "video/mp2t"
        elif file_path.suffix.lower() == ".mkv":
            content_type = "video/x-matroska"
        elif file_path.suffix.lower() == ".webm":
            content_type = "video/webm"
        elif not content_type:
            content_type = "video/mp4"

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": content_type,
            "Cache-Control": "no-cache",
        }

        # Status 206 si une plage spécifique a été demandée, 200 sinon
        status_code = status.HTTP_206_PARTIAL_CONTENT if range_header else status.HTTP_200_OK

        return StreamingResponse(
            self.stream_file_range(file_path, start, content_length),
            status_code=status_code,
            headers=headers,
            media_type=content_type,
        )


# Instance unique (Singleton)
stream_service = StreamService()
