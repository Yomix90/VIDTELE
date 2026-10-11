"""
Service de streaming vidéo : requêtes HTTP Range (RFC 9110) servies depuis le cache disque
ou, pour une vidéo pas encore en cache, au fil de son téléchargement depuis Telegram
(voir telechargement_progressif.py).
"""
import asyncio
import logging
import time
from pathlib import Path
from typing import AsyncGenerator, AsyncIterator, Callable, Optional, Set, Tuple

import aiofiles
from fastapi import HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon.errors import FileReferenceExpiredError, FloodWaitError

from app.config import settings
from app.models import Video
from app.services.cache_service import cache_service
from app.services.telechargement_progressif import (
    TelechargementInterrompu,
    gestionnaire_telechargements,
)
from app.telegram_client import telegram_manager

logger = logging.getLogger("vidtele.stream")


class PlageInsatisfiable(Exception):
    """Plage demandée au-delà de la fin du fichier : réponse 416."""

    def __init__(self, taille: int):
        super().__init__(f"plage insatisfiable (taille {taille})")
        self.taille = taille


CHUNK_SIZE = int(settings.STREAM_CHUNK_SIZE_KB * 1024)


def extension_video(video: Video) -> str:
    """Extension du fichier en cache, d'après le nom d'origine ou le type MIME."""
    if video.file_name and "." in video.file_name:
        return video.file_name.rsplit(".", 1)[1].lower()
    mime = video.mime_type or ""
    if "mp2t" in mime:
        return "ts"
    if "matroska" in mime:
        return "mkv"
    if "webm" in mime:
        return "webm"
    return "mp4"


def type_contenu(video: Video, extension: str) -> str:
    return {
        "ts": "video/mp2t",
        "m2ts": "video/mp2t",
        "mkv": "video/x-matroska",
        "webm": "video/webm",
    }.get(extension, video.mime_type or "video/mp4")


class SourceTelethon:
    """Lecture d'un fichier Telegram à partir de n'importe quelle position (MTProto)."""

    # 512 Ko : taille de requête maximale de Telegram ; 1 Mo en est un multiple, donc une
    # requête alignée ne traverse jamais une frontière de 1 Mo (règle de l'API upload.getFile).
    TAILLE_REQUETE = 512 * 1024

    def __init__(self, client, message, recharger: Callable):
        self._client = client
        self._message = message
        self._recharger = recharger
        self.taille = int(message.file.size)

    async def iterer(self, debut: int) -> AsyncIterator[bytes]:
        position = debut
        while position < self.taille:
            base = position - position % self.TAILLE_REQUETE
            saut = position - base
            try:
                async for morceau in self._client.iter_download(
                    self._message.media,
                    offset=base,
                    request_size=self.TAILLE_REQUETE,
                    chunk_size=self.TAILLE_REQUETE,
                    file_size=self.taille,
                ):
                    if saut:
                        if len(morceau) <= saut:
                            saut -= len(morceau)
                            continue
                        morceau = morceau[saut:]
                        saut = 0
                    position += len(morceau)
                    yield bytes(morceau)
                return
            except FileReferenceExpiredError:
                # La référence du fichier expire au bout de quelques heures : on relit le message
                logger.info("Référence Telegram expirée, rechargement du message")
                self._message = await self._recharger()
            except FloodWaitError as exc:
                if exc.seconds > 120:
                    raise
                logger.warning("FloodWait Telegram : pause de %s s", exc.seconds)
                await asyncio.sleep(exc.seconds)


class StreamService:
    """Streaming Range depuis le cache, ou progressif depuis Telegram, et préchauffage."""

    def __init__(self):
        # Vidéos en cours de préchauffage (évite les doublons)
        self._prewarming_ids: Set[int] = set()

    # ------------------------------------------------------------------ Telegram
    async def _client_telegram(self):
        """Client Telegram connecté (reconnexion automatique si nécessaire), sinon 503."""
        client = telegram_manager.client
        if client and client.is_connected():
            return client

        logger.info("Client Telegram non connecté lors d'une demande de flux : reconnexion...")
        try:
            from app.database import AsyncSessionLocal
            from app.models import TelegramAccount

            async with AsyncSessionLocal() as db_session:
                stmt_acc = select(TelegramAccount).where(TelegramAccount.is_active == True)  # noqa: E712
                active_acc = (await db_session.execute(stmt_acc)).scalar_one_or_none()
                if active_acc and active_acc.string_session:
                    settings.TELEGRAM_STRING_SESSION = active_acc.string_session
                    if active_acc.api_id:
                        settings.TELEGRAM_API_ID = active_acc.api_id
                    if active_acc.api_hash:
                        settings.TELEGRAM_API_HASH = active_acc.api_hash
        except Exception as ex_db:
            logger.debug("Impossible de vérifier le compte Telegram en base : %s", ex_db)

        started = await telegram_manager.start()
        client = telegram_manager.client
        if not started or not client or not client.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le service Telegram MTProto n'est pas connecté sur le serveur. Rendez-vous dans "
                "'Telegram MTProto' sur le panel d'administration pour connecter votre session.",
            )
        return client

    async def _ouvrir_source(self, video: Video) -> SourceTelethon:
        client = await self._client_telegram()
        channel = await telegram_manager.get_channel_entity()
        if not channel:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Canal Telegram inaccessible ou identifiant de canal invalide.",
            )

        async def charger_message():
            message = await client.get_messages(channel, ids=video.telegram_message_id)
            if not message or not message.media or not message.file:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Le message vidéo source a été supprimé de Telegram",
                )
            return message

        return SourceTelethon(client, await charger_message(), charger_message)

    # ------------------------------------------------------------------ HTTP
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

    async def stream_file_range(self, file_path: Path, start: int, content_length: int) -> AsyncGenerator[bytes, None]:
        """Lit un segment du fichier en cache par morceaux (jamais le fichier entier en mémoire)."""
        bytes_sent = 0
        async with aiofiles.open(file_path, mode="rb") as f:
            await f.seek(start)
            while bytes_sent < content_length:
                chunk = await f.read(min(CHUNK_SIZE, content_length - bytes_sent))
                if not chunk:
                    break
                bytes_sent += len(chunk)
                yield chunk

    async def _flux_progressif(self, video_id: int, iterateur: AsyncIterator[bytes]) -> AsyncGenerator[bytes, None]:
        try:
            async for morceau in iterateur:
                yield morceau
        except TelechargementInterrompu as exc:
            # Les en-têtes sont déjà partis : on coupe la réponse, le lecteur réessaiera
            logger.warning("Flux vidéo %s interrompu : %s", video_id, exc)
            raise

    async def create_streaming_response(self, video: Video, range_header: Optional[str]) -> Response:
        """Réponse 206/200/416 pour le lecteur, depuis le cache ou au fil du téléchargement."""
        cle = video.telegram_message_id
        extension = extension_video(video)
        chrono = time.perf_counter()

        if cache_service.is_cached(cle):
            chemin = cache_service.get_video_path(cle, extension=extension)
            cache_service.touch(cle)
            taille = chemin.stat().st_size
            origine = "cache"
            extension = chemin.suffix.lstrip(".") or extension

            def corps(debut: int, longueur: int):
                return self.stream_file_range(chemin, debut, longueur)
        else:
            try:
                telechargement = await gestionnaire_telechargements.obtenir(
                    cle, extension, lambda: self._ouvrir_source(video)
                )
            except HTTPException:
                raise
            except Exception as exc:
                logger.error("Ouverture de la vidéo %s impossible : %s", video.id, exc, exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Impossible de récupérer la vidéo depuis Telegram pour le moment. Réessayez.",
                ) from exc
            taille = telechargement.taille
            origine = f"telegram ({telechargement.ecrits * 100 // max(taille, 1)} % téléchargé)"

            def corps(debut: int, longueur: int):
                return self._flux_progressif(video.id, telechargement.lire(debut, debut + longueur - 1))

        attente_ms = round((time.perf_counter() - chrono) * 1000)
        try:
            plage = self.parse_range_header(range_header, taille)
        except PlageInsatisfiable:
            logger.info("Flux vidéo %s : plage insatisfiable %r (taille %s)", video.id, range_header, taille)
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{taille}", "Accept-Ranges": "bytes"},
            )
        debut, fin, longueur = plage if plage is not None else (0, taille - 1, taille)
        logger.info(
            "Flux vidéo %s : %s, attente=%s ms, plage=%s-%s/%s", video.id, origine, attente_ms, debut, fin, taille
        )

        contenu = type_contenu(video, extension)
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(longueur),
            "Content-Type": contenu,
            "Cache-Control": "public, max-age=86400, no-transform",
            "X-Content-Type-Options": "nosniff",
        }
        if plage is not None:
            headers["Content-Range"] = f"bytes {debut}-{fin}/{taille}"
        return StreamingResponse(
            corps(debut, longueur),
            status_code=status.HTTP_206_PARTIAL_CONTENT if plage is not None else status.HTTP_200_OK,
            headers=headers,
            media_type=contenu,
        )

    # ------------------------------------------------------------------ préchauffage
    async def prewarm_video(self, video: Video) -> bool:
        """
        Télécharge une vidéo en arrière-plan (priorité basse, un à la fois). Si aucun lecteur
        ne l'a lue entre-temps, applique le faststart avant de la mettre à disposition.
        """
        cle = video.telegram_message_id
        if cache_service.is_cached(cle):
            return True
        if video.id in self._prewarming_ids:
            return False
        self._prewarming_ids.add(video.id)
        try:
            extension = extension_video(video)
            remuxeur = cache_service.faststart_fichier if settings.AUTO_FASTSTART and extension == "mp4" else None
            telechargement = await gestionnaire_telechargements.obtenir(
                cle, extension, lambda: self._ouvrir_source(video), prechauffage=True, remuxeur=remuxeur
            )
            await telechargement.attendre_fin()
            if telechargement.erreur is not None:
                raise telechargement.erreur
            logger.info("[Préchauffage] Vidéo %s prête dans le cache", video.id)
            return True
        except Exception as exc:
            logger.warning("[Préchauffage] Échec pour la vidéo %s : %s", video.id, exc)
            return False
        finally:
            self._prewarming_ids.discard(video.id)

    def enqueue_prewarm(self, video: Video) -> None:
        """Planifie le préchauffage en tâche de fond (non bloquant)."""
        if cache_service.is_cached(video.telegram_message_id) or video.id in self._prewarming_ids:
            return
        asyncio.create_task(self.prewarm_video(video))

    async def prewarm_next_episodes_in_series(
        self,
        current_video: Video,
        db: Optional[AsyncSession] = None,
        count: int = 2,
    ) -> None:
        """Préchauffe les épisodes suivants de la même saison (passage quasi instantané au swipe)."""
        try:
            from app.database import AsyncSessionLocal
            from app.models import Episode

            async def _find_and_enqueue(session: AsyncSession) -> None:
                stmt = select(Episode).where(Episode.telegram_video_id == current_video.id)
                current_ep = (await session.execute(stmt)).scalar_one_or_none()
                if not current_ep or not current_ep.season_id:
                    return
                stmt_next = (
                    select(Video)
                    .join(Episode, Episode.telegram_video_id == Video.id)
                    .where(
                        Episode.season_id == current_ep.season_id,
                        Episode.number > current_ep.number,
                        Video.is_published == True,  # noqa: E712
                    )
                    .order_by(Episode.number.asc())
                    .limit(count)
                )
                for nxt in (await session.execute(stmt_next)).scalars().all():
                    self.enqueue_prewarm(nxt)

            if db is not None:
                await _find_and_enqueue(db)
            else:
                async with AsyncSessionLocal() as session:
                    await _find_and_enqueue(session)
        except Exception as e:
            logger.debug("[Préchauffage] Recherche des épisodes suivants impossible : %s", e)


# Instance unique (Singleton)
stream_service = StreamService()
