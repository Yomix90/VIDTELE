"""File de préchauffage : une vidéo à la fois, sans doublon, candidats par priorité."""
import asyncio
from datetime import datetime, timedelta, timezone

from app.database import AsyncSessionLocal
from app.models import Episode, Season, Series, Video
from app.services import prechauffage
from app.services.cache_service import cache_service
from app.services.prechauffage import FilePrechauffage, candidats_prechauffage
from app.services.stream_service import stream_service


def _maintenant():
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def test_une_video_a_la_fois_et_sans_doublon(monkeypatch):
    en_cours, maximum, traitees = 0, 0, []

    async def faux_prechauffage(video):
        nonlocal en_cours, maximum
        en_cours += 1
        maximum = max(maximum, en_cours)
        await asyncio.sleep(0.01)
        traitees.append(video.id)
        en_cours -= 1
        return True

    monkeypatch.setattr(stream_service, "prewarm_video", faux_prechauffage)
    file = FilePrechauffage()
    videos = [Video(id=i, telegram_message_id=990_000 + i) for i in range(1, 6)]
    for v in videos + videos[:2]:  # les deux premières demandées deux fois
        file.ajouter(v)
    await file.vider()

    assert traitees == [1, 2, 3, 4, 5], "ordre conservé, aucun doublon"
    assert maximum == 1, "une seule vidéo préchauffée à la fois (pas de rafale vers Telegram)"


async def test_echec_n_arrete_pas_la_file(monkeypatch):
    traitees = []

    async def faux_prechauffage(video):
        traitees.append(video.id)
        if video.id == 1:
            raise RuntimeError("Telegram indisponible")
        return True

    monkeypatch.setattr(stream_service, "prewarm_video", faux_prechauffage)
    file = FilePrechauffage()
    for i in (1, 2):
        file.ajouter(Video(id=i, telegram_message_id=991_000 + i))
    await file.vider()
    assert traitees == [1, 2]


async def test_candidats_par_priorite(client, monkeypatch):
    async with AsyncSessionLocal() as db:
        def video(msg, vues=0):
            return Video(
                telegram_message_id=msg, title=f"P{msg}", telegram_date=_maintenant(), is_published=True, views_count=vues
            )

        ancienne = Series(slug="prechauffe-ancienne", title_fr="Ancienne", visibility="published",
                          created_at=_maintenant() - timedelta(days=10))
        recente = Series(slug="prechauffe-recente", title_fr="Récente", visibility="published", created_at=_maintenant())
        brouillon = Series(slug="prechauffe-brouillon", title_fr="Brouillon", visibility="draft")
        db.add_all([ancienne, recente, brouillon])
        await db.flush()

        episodes = {}
        for serie, base in ((ancienne, 9500), (recente, 9600), (brouillon, 9700)):
            saison = Season(series_id=serie.id, number=1)
            db.add(saison)
            await db.flush()
            for n in range(1, 6):
                v = video(base + n)
                db.add(v)
                await db.flush()
                db.add(Episode(season_id=saison.id, telegram_video_id=v.id, number=n))
                episodes[(serie.slug, n)] = v
        populaire = video(9801, vues=10_000_000)
        db.add(populaire)
        await db.commit()

    # L'épisode 1 de la série récente est déjà en cache : il doit être sauté
    cache_service.get_video_path(9601).write_bytes(b"x")

    candidats = await candidats_prechauffage(limite=50)
    # D'autres tests créent aussi des séries : on ne regarde que les vidéos de ce test
    ids = [c.telegram_message_id for c in candidats if 9500 < c.telegram_message_id < 9900]

    assert ids[:2] == [9602, 9603], "série la plus récente d'abord, épisodes 2-3 (le 1 est en cache)"
    assert ids[2:5] == [9501, 9502, 9503], "puis les 3 premiers épisodes de la série plus ancienne"
    assert 9801 in ids, "puis les vidéos les plus vues"
    assert not any(9700 < i < 9800 for i in ids), "jamais une série en brouillon"
    assert all(i not in (9504, 9505, 9604, 9605) for i in ids), "seulement les 3 premiers épisodes"


async def test_cycle_desactivable(monkeypatch):
    monkeypatch.setattr(prechauffage.settings, "PREWARM_POPULAR_COUNT", 0)
    assert await prechauffage.cycle_prechauffage() == 0
