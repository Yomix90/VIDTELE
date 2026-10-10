"""Tests S4 et arrêts spontanés : jeton de flux lié à la vidéo, tolérance d'expiration bornée."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Video
from app.services.cache_service import cache_service

CONTENU = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 40


@pytest.fixture(scope="module")
async def videos(client):
    """Deux vidéos publiées, déjà présentes dans le cache disque (aucun appel Telegram)."""
    ids = []
    async with AsyncSessionLocal() as db:
        for msg_id in (9001, 9002):
            v = Video(
                telegram_message_id=msg_id,
                title=f"Test {msg_id}",
                file_size_bytes=len(CONTENU),
                telegram_date=datetime.now(timezone.utc).replace(tzinfo=None),
                is_published=True,
                file_name=f"test_{msg_id}.mp4",
            )
            db.add(v)
            await db.flush()
            ids.append(v.id)
            cache_service.get_video_path(msg_id).write_bytes(CONTENU)
        await db.commit()
    return ids


async def _user_id(client, auth):
    return (await client.get("/api/auth/me", headers=auth)).json()["id"]


def _jeton(user_id, type_, delta, vid=None):
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "type": type_, "exp": now + delta, "iat": now}
    if vid is not None:
        payload["vid"] = vid
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def _stream(client, video_id, token):
    return await client.get(
        f"/api/videos/{video_id}/stream",
        params={"token": token},
        headers={"Range": "bytes=0-99"},
    )


async def test_jeton_de_flux_valide(client, auth, videos):
    res = await client.post(f"/api/videos/{videos[0]}/stream-token", headers=auth)
    res = await _stream(client, videos[0], res.json()["stream_token"])
    assert res.status_code == 206
    assert res.headers["content-range"] == f"bytes 0-99/{len(CONTENU)}"
    assert res.content == CONTENU[:100]


async def test_jeton_de_flux_refuse_pour_une_autre_video(client, auth, videos):
    # Avant correctif : un jeton émis pour la vidéo A ouvrait toutes les vidéos
    res = await client.post(f"/api/videos/{videos[0]}/stream-token", headers=auth)
    res = await _stream(client, videos[1], res.json()["stream_token"])
    assert res.status_code == 403


async def test_jeton_acces_toujours_accepte(client, auth, videos, admin_token):
    # Compatibilité : les versions installées mettent le jeton d'accès dans l'URL
    res = await _stream(client, videos[1], admin_token)
    assert res.status_code == 206


async def test_jeton_expire_tolere_pendant_la_lecture(client, auth, videos):
    uid = await _user_id(client, auth)
    # Expiré depuis 30 min : la lecture en cours continue (avant : 401 => arrêt spontané)
    res = await _stream(client, videos[0], _jeton(uid, "access", timedelta(minutes=-30)))
    assert res.status_code == 206
    res = await _stream(client, videos[0], _jeton(uid, "stream", timedelta(minutes=-30), vid=videos[0]))
    assert res.status_code == 206


async def test_jeton_expire_au_dela_de_la_tolerance(client, auth, videos):
    uid = await _user_id(client, auth)
    trop_vieux = timedelta(minutes=-(settings.STREAM_TOKEN_GRACE_MINUTES + 1))
    res = await _stream(client, videos[0], _jeton(uid, "access", trop_vieux))
    assert res.status_code == 401


async def test_tolerance_limitee_au_flux(client, auth):
    # Un jeton d'accès expiré reste refusé partout ailleurs dans l'API
    uid = await _user_id(client, auth)
    expire = _jeton(uid, "access", timedelta(minutes=-5))
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {expire}"})
    assert res.status_code == 401


async def test_jetons_refuses(client, videos):
    uid = 1
    # Jeton de rafraîchissement, signature invalide, jeton sans expiration
    refresh = _jeton(uid, "refresh", timedelta(days=1))
    faux = jwt.encode({"sub": "1", "type": "access", "exp": 9999999999}, "autre_cle_" * 4, algorithm="HS256")
    sans_exp = jwt.encode({"sub": "1", "type": "access"}, settings.SECRET_KEY, algorithm="HS256")
    for tok in (refresh, faux, sans_exp, "n'importe quoi"):
        res = await _stream(client, videos[0], tok)
        assert res.status_code == 401, tok
