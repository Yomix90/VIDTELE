"""
Préchauffage du cache vidéo (Phase 2).

Une seule file, traitée une vidéo à la fois : avant, chaque demande lançait sa propre tâche
et toutes interrogeaient Telegram en même temps (risque de FloodWait).

Sources :
- les épisodes suivants de celui qui vient d'être lancé (stream_service) ;
- un cycle périodique : premiers épisodes de chaque série publiée (les plus récentes
  d'abord), puis les vidéos les plus vues, dans la limite de PREWARM_POPULAR_COUNT par cycle.
"""
import asyncio
import logging
from typing import List, Optional, Set

from sqlalchemy import desc, select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Episode, Season, Series, Video
from app.services.cache_service import cache_service

logger = logging.getLogger("vidtele.prechauffage")

EPISODES_PAR_SERIE = 3
DELAI_PREMIER_CYCLE_SECONDES = 60


class FilePrechauffage:
    def __init__(self):
        self._file: Optional[asyncio.Queue] = None
        self._en_file: Set[int] = set()
        self._travailleur: Optional[asyncio.Task] = None

    def _demarrer_si_besoin(self) -> None:
        if self._file is None:
            self._file = asyncio.Queue()
        if self._travailleur is None or self._travailleur.done():
            self._travailleur = asyncio.create_task(self._travailler())

    def ajouter(self, video: Video) -> bool:
        """Ajoute une vidéo à la file (ignorée si déjà en cache ou déjà en attente)."""
        if cache_service.is_cached(video.telegram_message_id) or video.id in self._en_file:
            return False
        self._demarrer_si_besoin()
        self._en_file.add(video.id)
        self._file.put_nowait(video)
        return True

    @property
    def taille(self) -> int:
        return len(self._en_file)

    async def _travailler(self) -> None:
        from app.services.stream_service import stream_service

        while True:
            video = await self._file.get()
            try:
                await stream_service.prewarm_video(video)
            except Exception as exc:  # un échec ne doit jamais arrêter la file
                logger.warning("Préchauffage de la vidéo %s impossible : %s", video.id, exc)
            finally:
                self._en_file.discard(video.id)
                self._file.task_done()

    async def vider(self) -> None:
        """Attend la fin de la file (tests, arrêt propre)."""
        if self._file is not None:
            await self._file.join()


file_prechauffage = FilePrechauffage()


async def candidats_prechauffage(limite: int) -> List[Video]:
    """Vidéos publiées non encore en cache, par ordre de priorité."""
    choisis: List[Video] = []
    vus: Set[int] = set()

    def retenir(videos) -> bool:
        for v in videos:
            if v.id not in vus and not cache_service.is_cached(v.telegram_message_id):
                vus.add(v.id)
                choisis.append(v)
                if len(choisis) >= limite:
                    return True
        return False

    async with AsyncSessionLocal() as db:
        # 1. Premiers épisodes des séries publiées, les plus récentes d'abord
        series = (
            await db.execute(select(Series.id).where(Series.visibility == "published").order_by(desc(Series.created_at)))
        ).scalars().all()
        for serie_id in series:
            episodes = (
                await db.execute(
                    select(Video)
                    .join(Episode, Episode.telegram_video_id == Video.id)
                    .join(Season, Season.id == Episode.season_id)
                    .where(Season.series_id == serie_id, Video.is_published == True)  # noqa: E712
                    .order_by(Season.number, Episode.number)
                    .limit(EPISODES_PAR_SERIE)
                )
            ).scalars().all()
            if retenir(episodes):
                return choisis

        # 2. Vidéos publiées les plus vues (au moins une vue : inutile de précharger l'inconnu)
        populaires = (
            await db.execute(
                select(Video)
                .where(Video.is_published == True, Video.views_count > 0)  # noqa: E712
                .order_by(desc(Video.views_count))
                .limit(limite * 3)
            )
        ).scalars().all()
        retenir(populaires)
    return choisis


async def cycle_prechauffage() -> int:
    """Ajoute à la file les meilleurs candidats ; retourne le nombre ajouté."""
    limite = max(0, settings.PREWARM_POPULAR_COUNT)
    if limite == 0:
        return 0
    ajoutes = sum(file_prechauffage.ajouter(v) for v in await candidats_prechauffage(limite))
    if ajoutes:
        logger.info("Préchauffage : %s vidéo(s) ajoutée(s) à la file", ajoutes)
    return ajoutes


async def boucle_prechauffage() -> None:
    """Tâche de fond : un cycle peu après le démarrage, puis à chaque intervalle de synchronisation."""
    await asyncio.sleep(DELAI_PREMIER_CYCLE_SECONDES)
    while True:
        try:
            await cycle_prechauffage()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Cycle de préchauffage en erreur : %s", exc)
        await asyncio.sleep(max(1, settings.SYNC_INTERVAL_MINUTES) * 60)
