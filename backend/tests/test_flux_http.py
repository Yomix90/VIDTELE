"""Conformité HTTP du streaming (Range, 206/200/416) et chemin chaud sans écritures inutiles."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.models import ActiveStream, Video
from app.services.cache_service import cache_service
from app.services.stream_manager import stream_manager
from app.services.stream_service import PlageInsatisfiable, stream_service

TAILLE = 10_000
CONTENU = bytes(i % 251 for i in range(TAILLE))


@pytest.mark.parametrize(
    "entete, attendu",
    [
        ("bytes=0-1023", (0, 1023, 1024)),
        ("bytes=1000-", (1000, TAILLE - 1, TAILLE - 1000)),
        ("bytes=-500", (TAILLE - 500, TAILLE - 1, 500)),
        ("bytes=9000-999999", (9000, TAILLE - 1, 1000)),  # fin bornée à la taille
        ("bytes=0-0", (0, 0, 1)),
        (None, None),
        ("", None),
        ("octets=0-10", None),  # unité inconnue : ignorée
        ("bytes=0-10,20-30", None),  # multi-plages : fichier entier
        ("bytes=abc-", None),
        ("bytes=50-10", None),  # fin < début : invalide, ignorée
    ],
)
def test_analyse_plage(entete, attendu):
    assert stream_service.parse_range_header(entete, TAILLE) == attendu


@pytest.mark.parametrize("entete", ["bytes=10000-", "bytes=20000-30000", "bytes=-0"])
def test_plage_insatisfiable(entete):
    with pytest.raises(PlageInsatisfiable):
        stream_service.parse_range_header(entete, TAILLE)


@pytest.fixture(scope="module")
async def video_test(client):
    async with AsyncSessionLocal() as db:
        v = Video(
            telegram_message_id=8801,
            title="Flux HTTP",
            file_size_bytes=TAILLE,
            telegram_date=datetime.now(timezone.utc).replace(tzinfo=None),
            is_published=True,
            file_name="flux.mp4",
        )
        db.add(v)
        await db.commit()
        cache_service.get_video_path(8801).write_bytes(CONTENU)
        return v.id


async def test_reponses_http(client, admin_token, video_test):
    url = f"/api/videos/{video_test}/stream"
    params = {"token": admin_token}

    res = await client.get(url, params=params, headers={"Range": "bytes=100-199"})
    assert res.status_code == 206
    assert res.headers["content-range"] == f"bytes 100-199/{TAILLE}"
    assert res.headers["content-length"] == "100"
    assert res.content == CONTENU[100:200]

    # Sans Range : 200, fichier entier, pas de Content-Range
    res = await client.get(url, params=params)
    assert res.status_code == 200
    assert "content-range" not in res.headers
    assert res.headers["accept-ranges"] == "bytes"
    assert res.content == CONTENU

    # Au-delà de la fin : 416 + taille réelle
    res = await client.get(url, params=params, headers={"Range": f"bytes={TAILLE}-"})
    assert res.status_code == 416
    assert res.headers["content-range"] == f"bytes */{TAILLE}"

    # Jamais de compression sur la vidéo
    assert "content-encoding" not in res.headers


async def test_une_vue_par_lecture_et_pas_d_ecriture_par_requete(client, admin_token, video_test):
    async def vues():
        async with AsyncSessionLocal() as db:
            return (await db.execute(select(Video.views_count).where(Video.id == video_test))).scalar_one()

    async def heartbeat():
        async with AsyncSessionLocal() as db:
            return (await db.execute(select(func.max(ActiveStream.last_active_at)))).scalar_one()

    stream_manager._vues_recentes.clear()
    avant = await vues()
    url = f"/api/videos/{video_test}/stream"
    # Le lecteur enchaîne plusieurs requêtes Range, dont des reprises « bytes=0- »
    await client.get(url, params={"token": admin_token}, headers={"Range": "bytes=0-"})
    battement = await heartbeat()
    for entete in ("bytes=0-", "bytes=4000-", "bytes=0-", "bytes=8000-"):
        res = await client.get(url, params={"token": admin_token}, headers={"Range": entete})
        assert res.status_code == 206

    assert await vues() == avant + 1, "une seule vue pour une même lecture"
    assert await heartbeat() == battement, "aucune écriture de session dans les 30 s"
