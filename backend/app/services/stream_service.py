"""
Service de streaming vidéo haute performance avec support des requêtes HTTP Range (206 Partial Content).
Téléchargement par morceaux via Telethon MTProto, verrous de concurrence et streaming sans surcharge RAM.
"""
import asyncio
import logging
import time
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional, Set, Tuple
import aiofiles
from fastapi import HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon.errors import FloodWaitError

from app.config import settings
from app.models import Video
from app.services.cache_service import cache_service
from app.telegram_client import telegram_manager

logger = logging.getLogger("vidtele.stream")

class PlageInsatisfiable(Exception):
    """Plage demandée au-delà de la fin du fichier : réponse 416."""

    def __init__(self, taille: int):
        super().__init__(f"plage insatisfiable (taille {taille})")
        self.taille = taille


CHUNK_SIZE = int(settings.STREAM_CHUNK_SIZE_KB * 1024)  # 256 Ko par paquet pour un débit optimal et latence minimale


class StreamService:
    """Moteur de streaming vidéo gérant la mise en cache, FastStart, préchauffage et requêtes Range."""

    def __init__(self):
        # Dictionnaire de verrous pour éviter le téléchargement simultané d'une même vidéo
        self._video_locks: Dict[int, asyncio.Lock] = {}
        self._master_lock = asyncio.Lock()
        # Ensemble des identifiants vidéos actuellement en cours de préchauffage
        self._prewarming_ids: Set[int] = set()

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
                    # Application du remuxage FastStart pour première image instantanée
                    if settings.AUTO_FASTSTART:
                        try:
                            await cache_service.apply_faststart(cached_path)
                        except Exception as ex_fs:
                            logger.warning(f"FastStart ignoré pour {cached_path.name}: {ex_fs}")
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
                    # Le détail technique reste dans les journaux (exc_info ci-dessus), pas chez le client
                    detail="Impossible de récupérer la vidéo depuis Telegram pour le moment. Réessayez.",
                )

    def parse_range_header(self, range_header: Optional[str], file_size: int) -> Optional[Tuple[int, int, int]]:
        """
        Analyse « Range: bytes=debut-fin » selon la RFC 9110.

        Retourne (debut, fin, longueur), ou None si l'en-tête est absent, mal formé ou
        multi-plages (on sert alors le fichier entier en 200, ce que la norme autorise).
        Lève PlageInsatisfiable si la plage commence au-delà de la fin du fichier (416).
        """
        if not range_header:
            return None
        valeur = range_header.strip()
        if not valeur.lower().startswith("bytes=") or "," in valeur:
            return None
        debut_txt, _, fin_txt = valeur[6:].strip().partition("-")
        try:
            if debut_txt:
                debut = int(debut_txt)
                fin = int(fin_txt) if fin_txt else file_size - 1
                if debut < 0 or (fin_txt and fin < debut):
                    return None
            elif fin_txt:
                suffixe = int(fin_txt)  # « bytes=-500 » : les 500 derniers octets
                if suffixe <= 0:
                    raise PlageInsatisfiable(file_size)
                debut, fin = max(0, file_size - suffixe), file_size - 1
            else:
                return None
        except ValueError:
            return None
        if debut >= file_size:
            raise PlageInsatisfiable(file_size)
        fin = min(fin, file_size - 1)
        return debut, fin, fin - debut + 1

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
        # Assurer la présence de la vidéo dans le cache local (mesure du temps d'attente)
        en_cache = cache_service.is_cached(video.telegram_message_id)
        chrono = time.perf_counter()
        file_path = await self.ensure_video_in_cache(video)
        attente_ms = round((time.perf_counter() - chrono) * 1000)
        file_size = file_path.stat().st_size

        try:
            plage = self.parse_range_header(range_header, file_size)
        except PlageInsatisfiable:
            logger.info("Flux vidéo %s : plage insatisfiable %r (taille %s)", video.id, range_header, file_size)
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{file_size}", "Accept-Ranges": "bytes"},
            )
        if plage is None:
            start, end, content_length = 0, file_size - 1, file_size
        else:
            start, end, content_length = plage

        logger.info(
            "Flux vidéo %s : cache=%s attente=%s ms plage=%s-%s/%s",
            video.id,
            "oui" if en_cache else "non",
            attente_ms,
            start,
            end,
            file_size,
        )

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
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": content_type,
            "Cache-Control": "public, max-age=86400, no-transform",
            "X-Content-Type-Options": "nosniff",
        }

        # 206 + Content-Range pour une plage valide ; 200 (fichier entier) sinon
        if plage is not None:
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            status_code = status.HTTP_206_PARTIAL_CONTENT
        else:
            status_code = status.HTTP_200_OK

        return StreamingResponse(
            self.stream_file_range(file_path, start, content_length),
            status_code=status_code,
            headers=headers,
            media_type=content_type,
        )

    async def prewarm_video(self, video: Video) -> bool:
        """
        Télécharge et optimise (FastStart) un épisode en arrière-plan sans bloquer le client.
        Évite tout téléchargement redondant si la vidéo est déjà en cache ou en cours.
        """
        if cache_service.is_cached(video.telegram_message_id):
            return True

        if video.id in self._prewarming_ids:
            return False

        self._prewarming_ids.add(video.id)
        try:
            logger.info(f"[Prewarm] Démarrage du préchauffage en tâche de fond pour '{video.title}' (ID {video.id})...")
            await self.ensure_video_in_cache(video)
            logger.info(f"[Prewarm] Vidéo {video.id} préchauffée avec succès dans le cache !")
            return True
        except Exception as e:
            logger.warning(f"[Prewarm] Échec du préchauffage pour la vidéo {video.id}: {e}")
            return False
        finally:
            self._prewarming_ids.discard(video.id)

    def enqueue_prewarm(self, video: Video) -> None:
        """Planifie le préchauffage en tâche de fond asynchrone non-bloquante."""
        if cache_service.is_cached(video.telegram_message_id) or video.id in self._prewarming_ids:
            return
        asyncio.create_task(self.prewarm_video(video))

    async def prewarm_next_episodes_in_series(
        self,
        current_video: Video,
        db: Optional[AsyncSession] = None,
        count: int = 2,
    ) -> None:
        """
        Détecte les épisodes suivants de la même série et préchauffe en avance leur cache.
        Permet un passage instantané (< 0.5 s) lors du swipe vertical.
        Gère de manière autonome sa propre session de base de données si aucune n'est fournie.
        """
        try:
            from app.database import AsyncSessionLocal
            from app.models import Episode

            async def _find_and_enqueue(session: AsyncSession) -> None:
                # Trouver l'épisode actuel
                stmt = select(Episode).where(Episode.telegram_video_id == current_video.id)
                current_ep = (await session.execute(stmt)).scalar_one_or_none()
                if not current_ep or not current_ep.season_id:
                    return

                # Trouver les épisodes suivants dans la même saison
                stmt_next = (
                    select(Video)
                    .join(Episode, Episode.telegram_video_id == Video.id)
                    .where(
                        Episode.season_id == current_ep.season_id,
                        Episode.number > current_ep.number,
                        Video.is_published == True,
                    )
                    .order_by(Episode.number.asc())
                    .limit(count)
                )
                next_videos = (await session.execute(stmt_next)).scalars().all()
                for nxt in next_videos:
                    self.enqueue_prewarm(nxt)

            if db is not None:
                await _find_and_enqueue(db)
            else:
                async with AsyncSessionLocal() as session:
                    await _find_and_enqueue(session)
        except Exception as e:
            logger.debug(f"[Prewarm] Erreur lors de la recherche des épisodes suivants: {e}")


# Instance unique (Singleton)
stream_service = StreamService()
