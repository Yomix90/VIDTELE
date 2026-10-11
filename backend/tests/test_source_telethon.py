"""
Adaptateur SourceTelethon face à un faux client Telethon qui applique les règles de l'API
upload.getFile : décalage multiple de 4 Ko, requête ne traversant pas une frontière de 1 Mo.
"""
import asyncio
from types import SimpleNamespace

import pytest
from telethon.errors import FileReferenceExpiredError, FloodWaitError

from app.services.stream_service import SourceTelethon

KO = 1024
MO = 1024 * KO


class FauxClientTelethon:
    def __init__(self, contenu: bytes, panne=None):
        self.contenu = contenu
        self.panne = panne  # exception à lever une fois, au premier appel
        self.appels = []

    async def iter_download(self, media, offset, request_size, chunk_size, file_size):
        assert offset % (4 * KO) == 0, "Telegram exige un décalage multiple de 4 Ko"
        assert MO % request_size == 0, "la taille de requête doit diviser 1 Mo"
        assert offset // MO == (offset + request_size - 1) // MO, "une requête ne doit pas traverser 1 Mo"
        self.appels.append((media, offset))
        if self.panne is not None:
            panne, self.panne = self.panne, None
            raise panne
        position = offset
        while position < file_size:
            yield self.contenu[position : position + request_size]
            position += request_size


def _message(taille, media="media-1"):
    return SimpleNamespace(media=media, file=SimpleNamespace(size=taille))


def _contenu(taille):
    return bytes((i * 13) % 256 for i in range(taille))


async def _lire(source, debut, nombre):
    resultat = b""
    async for morceau in source.iterer(debut):
        resultat += morceau
        if len(resultat) >= nombre:
            break
    return resultat[:nombre]


@pytest.mark.parametrize("debut", [0, 1, 4095, 512 * KO, 512 * KO + 7, 3 * MO - 100])
async def test_lecture_a_toute_position(debut):
    contenu = _contenu(3 * MO)
    client = FauxClientTelethon(contenu)
    source = SourceTelethon(client, _message(len(contenu)), recharger=None)
    assert source.taille == len(contenu)
    assert await _lire(source, debut, 100_000) == contenu[debut : debut + 100_000]


async def test_reference_expiree_rechargee():
    contenu = _contenu(1 * MO)
    client = FauxClientTelethon(contenu, panne=FileReferenceExpiredError(request=None))
    recharges = []

    async def recharger():
        recharges.append(1)
        return _message(len(contenu), media="media-2")

    source = SourceTelethon(client, _message(len(contenu)), recharger)
    assert await _lire(source, 600 * KO, 50_000) == contenu[600 * KO : 600 * KO + 50_000]
    assert recharges == [1]
    assert client.appels[-1][0] == "media-2", "nouvelle référence utilisée après rechargement"


async def test_floodwait_court_respecte(monkeypatch):
    pauses = []

    async def fausse_pause(secondes):
        pauses.append(secondes)

    monkeypatch.setattr(asyncio, "sleep", fausse_pause)
    contenu = _contenu(1 * MO)
    client = FauxClientTelethon(contenu, panne=FloodWaitError(request=None, capture=3))
    source = SourceTelethon(client, _message(len(contenu)), recharger=None)
    assert await _lire(source, 0, 1000) == contenu[:1000]
    assert pauses == [3]


async def test_floodwait_long_transmis():
    client = FauxClientTelethon(_contenu(MO), panne=FloodWaitError(request=None, capture=600))
    source = SourceTelethon(client, _message(MO), recharger=None)
    with pytest.raises(FloodWaitError):
        await _lire(source, 0, 10)
