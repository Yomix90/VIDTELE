"""
Streaming progressif depuis Telegram (Phase 2), avec une source Telegram simulée.

Avant : la première requête d'une vidéo non en cache attendait le téléchargement complet.
"""
import asyncio
import time
from datetime import datetime, timezone

import pytest

from app.database import AsyncSessionLocal
from app.models import Video
from app.services import telechargement_progressif as tp
from app.services.cache_service import cache_service
from app.services.stream_service import stream_service

MO = 1024 * 1024


class SourceSimulee:
    """Fichier servi par morceaux avec un délai, comme Telegram ; peut échouer une fois."""

    def __init__(self, contenu: bytes, morceau: int = 64 * 1024, delai: float = 0.01, panne_apres: int | None = None):
        self.contenu = contenu
        self.taille = len(contenu)
        self.morceau = morceau
        self.delai = delai
        self.panne_apres = panne_apres
        self.departs: list[int] = []  # positions demandées à chaque itération

    async def iterer(self, debut: int):
        self.departs.append(debut)
        position = debut
        while position < self.taille:
            if self.panne_apres is not None and position >= self.panne_apres:
                self.panne_apres = None  # une seule panne
                raise ConnectionError("coupure réseau simulée")
            await asyncio.sleep(self.delai)
            fin = min(position + self.morceau, self.taille)
            yield self.contenu[position:fin]
            position = fin


def _contenu(taille: int) -> bytes:
    return bytes((i * 7) % 256 for i in range(taille))


async def _video(msg_id: int, taille: int) -> Video:
    async with AsyncSessionLocal() as db:
        v = Video(
            telegram_message_id=msg_id,
            title=f"Progressif {msg_id}",
            file_size_bytes=taille,
            telegram_date=datetime.now(timezone.utc).replace(tzinfo=None),
            is_published=True,
            file_name=f"p{msg_id}.mp4",
        )
        db.add(v)
        await db.commit()
        return v


@pytest.fixture
def sources(monkeypatch):
    """Remplace l'ouverture Telegram par des sources simulées, en comptant les ouvertures."""
    table: dict[int, SourceSimulee] = {}
    ouvertures: dict[int, int] = {}

    async def ouvrir(video):
        ouvertures[video.telegram_message_id] = ouvertures.get(video.telegram_message_id, 0) + 1
        return table[video.telegram_message_id]

    monkeypatch.setattr(stream_service, "_ouvrir_source", ouvrir)
    monkeypatch.setattr(tp, "TENTATIVES_REPRISE", 3)
    return table, ouvertures


async def _attendre_cache(msg_id: int, delai: float = 10.0):
    fin = time.monotonic() + delai
    while not cache_service.is_cached(msg_id):
        assert time.monotonic() < fin, "le téléchargement aurait dû se terminer"
        await asyncio.sleep(0.02)


async def test_premiers_octets_avant_la_fin_du_telechargement(client, admin_token, sources):
    table, _ = sources
    contenu = _contenu(2 * MO)  # 32 morceaux de 64 Ko à 10 ms ≈ 0,35 s minimum au total
    video = await _video(8901, len(contenu))
    table[8901] = SourceSimulee(contenu, delai=0.01)

    debut = time.perf_counter()
    res = await client.get(
        f"/api/videos/{video.id}/stream", params={"token": admin_token}, headers={"Range": "bytes=0-65535"}
    )
    duree = time.perf_counter() - debut
    assert res.status_code == 206
    assert res.headers["content-range"] == f"bytes 0-65535/{len(contenu)}"
    assert res.content == contenu[:65536]
    assert not cache_service.is_cached(8901), "réponse servie pendant le téléchargement"
    assert duree < 0.3, f"premier morceau en {duree:.2f} s (doit précéder la fin du téléchargement)"

    # Le téléchargement continue seul puis la vidéo passe en cache, intacte
    await _attendre_cache(8901)
    assert cache_service.get_video_path(8901).read_bytes() == contenu


async def test_lecteurs_simultanes_partagent_un_seul_telechargement(client, admin_token, sources):
    table, ouvertures = sources
    contenu = _contenu(1 * MO)
    video = await _video(8902, len(contenu))
    table[8902] = SourceSimulee(contenu, delai=0.005)

    url = f"/api/videos/{video.id}/stream"
    reponses = await asyncio.gather(
        *(client.get(url, params={"token": admin_token}, headers={"Range": f"bytes={d}-{d + 99_999}"}) for d in (0, 200_000, 500_000))
    )
    for d, res in zip((0, 200_000, 500_000), reponses):
        assert res.status_code == 206
        assert res.content == contenu[d : d + 100_000]
    assert ouvertures[8902] == 1, "une seule ouverture Telegram pour trois lecteurs"


async def test_plage_lointaine_lue_directement(client, admin_token, sources):
    table, _ = sources
    contenu = _contenu(8 * MO)
    video = await _video(8903, len(contenu))
    source = SourceSimulee(contenu, delai=0.02)  # téléchargement lent : ~2,6 s au total
    table[8903] = source

    # Comme ExoPlayer avec un index MP4 en fin de fichier : il demande la fin tout de suite
    debut_fin = len(contenu) - 300_000
    chrono = time.perf_counter()
    res = await client.get(
        f"/api/videos/{video.id}/stream", params={"token": admin_token}, headers={"Range": f"bytes={debut_fin}-"}
    )
    duree = time.perf_counter() - chrono
    assert res.status_code == 206
    assert res.content == contenu[debut_fin:]
    assert any(d >= debut_fin - 64 * 1024 for d in source.departs), "lecture directe à la position demandée"
    assert duree < 1.0, f"fin du fichier servie en {duree:.2f} s sans attendre le téléchargement"
    await _attendre_cache(8903)


async def test_reprise_apres_coupure_reseau(client, admin_token, sources):
    table, _ = sources
    contenu = _contenu(1 * MO)
    video = await _video(8904, len(contenu))
    source = SourceSimulee(contenu, delai=0.002, panne_apres=400_000)
    table[8904] = source

    res = await client.get(f"/api/videos/{video.id}/stream", params={"token": admin_token})
    assert res.status_code == 200
    assert res.content == contenu, "fichier complet malgré la coupure"
    await _attendre_cache(8904)
    # Reprise à l'endroit de la coupure (et non depuis le début)
    # (la panne survient à la première frontière de morceau après 400 000 octets)
    assert len(source.departs) == 2 and 400_000 <= source.departs[1] < len(contenu)


async def test_prechauffage_applique_le_faststart_sans_lecteur(client, sources, monkeypatch):
    table, _ = sources
    remuxes = []

    async def faux_faststart(chemin):
        remuxes.append(chemin.name)

    monkeypatch.setattr(cache_service, "faststart_fichier", faux_faststart)
    contenu = _contenu(512 * 1024)
    video = await _video(8905, len(contenu))
    table[8905] = SourceSimulee(contenu, delai=0.001)

    assert await stream_service.prewarm_video(video) is True
    assert remuxes == ["video_8905.tmp"], "remuxage du fichier temporaire, avant mise à disposition"
    assert cache_service.is_cached(8905)


async def test_pas_de_faststart_si_un_lecteur_a_deja_lu(client, admin_token, sources, monkeypatch):
    table, _ = sources
    remuxes = []

    async def faux_faststart(chemin):
        remuxes.append(chemin.name)

    monkeypatch.setattr(cache_service, "faststart_fichier", faux_faststart)
    contenu = _contenu(1 * MO)
    video = await _video(8906, len(contenu))
    table[8906] = SourceSimulee(contenu, delai=0.01)

    prechauffage = asyncio.create_task(stream_service.prewarm_video(video))
    await asyncio.sleep(0.05)
    res = await client.get(
        f"/api/videos/{video.id}/stream", params={"token": admin_token}, headers={"Range": "bytes=0-1023"}
    )
    assert res.status_code == 206
    assert await prechauffage is True
    assert remuxes == [], "un lecteur a lu l'index : le fichier ne doit plus changer"
