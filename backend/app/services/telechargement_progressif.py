"""
Téléchargement progressif depuis Telegram (Phase 2).

Avant : la première requête d'une vidéo non en cache attendait le téléchargement COMPLET
du fichier (puis un remuxage ffmpeg) avant d'envoyer le premier octet.

Maintenant :
- un seul téléchargement par vidéo, écrit au fil de l'eau dans `video_<id>.tmp` ;
- chaque lecteur reçoit les octets dès qu'ils sont sur le disque ;
- une plage demandée loin devant (déplacement, index MP4 en fin de fichier) est lue
  directement chez Telegram à cette position, sans attendre ;
- en fin de téléchargement, `.tmp` devient `video_<id>.<ext>` : les lectures suivantes
  viennent du disque.

L'accès à Telegram passe par l'interface `SourceVideo` : les tests la simulent.
"""
import asyncio
import logging
import os
import time
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable, Dict, Optional, Protocol

from app.services.cache_service import cache_service

logger = logging.getLogger("vidtele.telechargement")

TAILLE_MORCEAU_LECTURE = 256 * 1024
# Au-delà de cet écart devant le téléchargement, on lit directement chez Telegram
SEUIL_LECTURE_DIRECTE = 2 * 1024 * 1024
# Délai maximal d'attente de nouveaux octets avant de déclarer le téléchargement bloqué
DELAI_ATTENTE_SECONDES = 30.0
TENTATIVES_REPRISE = 4


class SourceVideo(Protocol):
    """Accès en lecture au fichier d'origine (Telegram en production, simulé en test)."""

    taille: int

    def iterer(self, debut: int) -> AsyncIterator[bytes]:
        """Octets du fichier à partir de `debut`, dans l'ordre, jusqu'à la fin."""
        ...


FabriqueSource = Callable[[], Awaitable[SourceVideo]]
# Réécriture du fichier temporaire (faststart) avant sa mise à disposition
Remuxeur = Callable[[Path], Awaitable[None]]


class TelechargementInterrompu(RuntimeError):
    """Le téléchargement a échoué : les lecteurs en attente reçoivent cette erreur."""


class Telechargement:
    """Téléchargement d'une vidéo, partagé par tous ses lecteurs."""

    def __init__(self, cle: int, extension: str, source: SourceVideo, remuxeur: Optional[Remuxeur] = None):
        self.cle = cle
        self.remuxeur = remuxeur
        self.remux_en_cours = False
        self.source = source
        self.taille = source.taille
        self.chemin_temporaire = cache_service.cache_dir / f"video_{cle}.tmp"
        self.chemin_final = cache_service.cache_dir / f"video_{cle}.{extension}"
        self.ecrits = 0
        self.termine = False
        self.erreur: Optional[BaseException] = None
        self.lecteurs_servis = 0  # si > 0, le fichier ne doit plus être réécrit (faststart)
        self._condition = asyncio.Condition()
        self._tache: Optional[asyncio.Task] = None
        self.debut = time.perf_counter()

    # ------------------------------------------------------------------ écriture
    def demarrer(self, semaphore: asyncio.Semaphore) -> None:
        self._tache = asyncio.create_task(self._executer(semaphore))

    async def attendre_fin(self) -> None:
        if self._tache:
            await asyncio.shield(self._tache)

    async def _executer(self, semaphore: asyncio.Semaphore) -> None:
        try:
            async with semaphore:
                await self._telecharger()
            # Faststart uniquement si AUCUN lecteur n'a lu le fichier : un lecteur qui a déjà
            # lu l'index MP4 serait corrompu si la disposition du fichier changeait ensuite.
            # Vérification et drapeau sans « await » entre les deux : atomique en asyncio.
            if self.remuxeur is not None and self.lecteurs_servis == 0:
                self.remux_en_cours = True
                try:
                    await self.remuxeur(self.chemin_temporaire)
                except Exception as exc:
                    logger.warning("Faststart ignoré pour la vidéo %s : %s", self.cle, exc)
                finally:
                    self.remux_en_cours = False
                self.taille = self.chemin_temporaire.stat().st_size
                self.ecrits = self.taille
            await asyncio.to_thread(self._finaliser)
            logger.info(
                "Téléchargement terminé : vidéo %s (%.1f Mo en %.1f s)",
                self.cle,
                self.taille / 1024**2,
                time.perf_counter() - self.debut,
            )
        except BaseException as exc:  # noqa: BLE001 - transmis aux lecteurs
            self.erreur = exc
            logger.error("Téléchargement interrompu : vidéo %s à %s/%s octets : %s", self.cle, self.ecrits, self.taille, exc)
            self.chemin_temporaire.unlink(missing_ok=True)
        finally:
            async with self._condition:
                self._condition.notify_all()

    async def _telecharger(self) -> None:
        self.chemin_temporaire.parent.mkdir(parents=True, exist_ok=True)
        with open(self.chemin_temporaire, "wb"):
            pass
        tentatives = 0
        while self.ecrits < self.taille:
            try:
                async for morceau in self.source.iterer(self.ecrits):
                    if not morceau:
                        continue
                    morceau = morceau[: self.taille - self.ecrits]
                    await asyncio.to_thread(self._ajouter, morceau)
                    self.ecrits += len(morceau)
                    tentatives = 0
                    async with self._condition:
                        self._condition.notify_all()
                    if self.ecrits >= self.taille:
                        break
                else:
                    if self.ecrits < self.taille:
                        raise TelechargementInterrompu("la source s'est arrêtée avant la fin du fichier")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                tentatives += 1
                if tentatives > TENTATIVES_REPRISE:
                    raise
                pause = min(2**tentatives, 15)
                logger.warning("Vidéo %s : reprise du téléchargement à %s octets dans %s s (%s)", self.cle, self.ecrits, pause, exc)
                await asyncio.sleep(pause)

    def _ajouter(self, morceau: bytes) -> None:
        with open(self.chemin_temporaire, "ab") as f:
            f.write(morceau)

    def _finaliser(self) -> None:
        # Sous Windows (tests), un lecteur peut tenir le fichier ouvert un instant : on réessaie
        for essai in range(20):
            try:
                os.replace(self.chemin_temporaire, self.chemin_final)
                break
            except PermissionError:
                time.sleep(0.05 * (essai + 1))
        else:
            os.replace(self.chemin_temporaire, self.chemin_final)
        cache_service.touch(self.cle)
        self.termine = True

    # ------------------------------------------------------------------ lecture
    def _lire_disque(self, position: int, nombre: int) -> bytes:
        for essai in range(10):
            chemin = self.chemin_final if self.termine else self.chemin_temporaire
            try:
                with open(chemin, "rb") as f:
                    f.seek(position)
                    return f.read(nombre)
            except (FileNotFoundError, PermissionError):
                # Renommage .tmp -> final en cours (PermissionError : spécifique à Windows) :
                # on relit avec le bon chemin après une courte pause
                time.sleep(0.01 * (essai + 1))
        with open(self.chemin_final, "rb") as f:
            f.seek(position)
            return f.read(nombre)

    async def lire(self, debut: int, fin: int) -> AsyncIterator[bytes]:
        """Octets [debut, fin] (inclus), dès qu'ils sont disponibles."""
        self.lecteurs_servis += 1
        # Un remuxage faststart est en cours : attendre le fichier définitif
        while self.remux_en_cours:
            async with self._condition:
                await asyncio.wait_for(self._condition.wait(), timeout=DELAI_ATTENTE_SECONDES)
        position = debut
        while position <= fin:
            if self.erreur is not None:
                raise TelechargementInterrompu(str(self.erreur))

            if position < self.ecrits or self.termine:
                nombre = min(TAILLE_MORCEAU_LECTURE, self.ecrits - position, fin - position + 1)
                morceau = await asyncio.to_thread(self._lire_disque, position, nombre)
                if not morceau:
                    raise TelechargementInterrompu("fichier en cache plus court que prévu")
                position += len(morceau)
                yield morceau
                continue

            if position - self.ecrits > SEUIL_LECTURE_DIRECTE:
                # Loin devant le téléchargement : lecture directe à la bonne position
                async for morceau in self._lire_directement(position, fin):
                    yield morceau
                return

            async with self._condition:
                if position >= self.ecrits and not self.termine and self.erreur is None:
                    try:
                        await asyncio.wait_for(self._condition.wait(), timeout=DELAI_ATTENTE_SECONDES)
                    except asyncio.TimeoutError:
                        raise TelechargementInterrompu("aucune donnée reçue de Telegram depuis 30 s") from None

    async def _lire_directement(self, debut: int, fin: int) -> AsyncIterator[bytes]:
        restant = fin - debut + 1
        iterateur = self.source.iterer(debut)
        try:
            async for morceau in iterateur:
                morceau = morceau[:restant]
                restant -= len(morceau)
                yield morceau
                if restant <= 0:
                    break
        finally:
            fermer = getattr(iterateur, "aclose", None)
            if fermer:
                await fermer()


class GestionnaireTelechargements:
    """Un téléchargement actif par vidéo ; priorité aux lectures sur le préchauffage."""

    def __init__(self, max_lectures: int = 4, max_prechauffage: int = 1):
        self._actifs: Dict[int, Telechargement] = {}
        self._ouvertures: Dict[int, asyncio.Lock] = {}
        self._max_lectures = max_lectures
        self._max_prechauffage = max_prechauffage
        self._sem_lecture: Optional[asyncio.Semaphore] = None
        self._sem_prechauffage: Optional[asyncio.Semaphore] = None

    def _semaphores(self):
        # Créés à la première utilisation (dans la boucle asyncio du serveur)
        if self._sem_lecture is None:
            self._sem_lecture = asyncio.Semaphore(self._max_lectures)
            self._sem_prechauffage = asyncio.Semaphore(self._max_prechauffage)
        return self._sem_lecture, self._sem_prechauffage

    def actif(self, cle: int) -> Optional[Telechargement]:
        t = self._actifs.get(cle)
        if t is not None and (t.termine or t.erreur is not None):
            del self._actifs[cle]
            return None
        return t

    async def obtenir(
        self,
        cle: int,
        extension: str,
        fabrique: FabriqueSource,
        prechauffage: bool = False,
        remuxeur: Optional[Remuxeur] = None,
    ) -> Telechargement:
        """Téléchargement en cours pour cette vidéo, ou démarrage d'un nouveau."""
        existant = self.actif(cle)
        if existant is not None:
            return existant
        verrou = self._ouvertures.setdefault(cle, asyncio.Lock())
        async with verrou:
            existant = self.actif(cle)
            if existant is not None:
                return existant
            source = await fabrique()
            await cache_service.ensure_capacity(needed_bytes=source.taille)
            telechargement = Telechargement(cle, extension, source, remuxeur if prechauffage else None)
            sem_lecture, sem_prechauffage = self._semaphores()
            telechargement.demarrer(sem_prechauffage if prechauffage else sem_lecture)
            self._actifs[cle] = telechargement
            logger.info(
                "Téléchargement démarré : vidéo %s (%.1f Mo, %s)",
                cle,
                source.taille / 1024**2,
                "préchauffage" if prechauffage else "lecture",
            )
            return telechargement


gestionnaire_telechargements = GestionnaireTelechargements()


def nettoyer_fichiers_incomplets() -> int:
    """Supprime les .tmp laissés par un arrêt brutal (appelé au démarrage)."""
    supprimes = 0
    for fichier in cache_service.cache_dir.glob("video_*.tmp"):
        try:
            fichier.unlink()
            supprimes += 1
        except OSError:
            pass
    return supprimes
