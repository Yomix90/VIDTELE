"""Tests S3 : IP réelle derrière Traefik et verrous anti brute-force."""
import httpx
import pytest
from starlette.requests import Request

from app.config import settings
from app.main import app
from app.security import get_client_ip

MAUVAIS = {"username": "admin", "password": "mauvais_mot_de_passe"}


def _req(peer: str, xff: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "client": (peer, 1234), "headers": headers})


@pytest.mark.parametrize(
    "peer, xff, attendu",
    [
        ("203.0.113.10", "1.2.3.4", "203.0.113.10"),  # client direct : en-tête ignoré
        ("172.18.0.5", "198.51.100.7", "198.51.100.7"),  # via Traefik
        ("172.18.0.5", "1.2.3.4, 198.51.100.7", "198.51.100.7"),  # valeur forgée à gauche ignorée
        ("172.18.0.5", "198.51.100.7, 10.0.0.3", "198.51.100.7"),  # proxys internes sautés
        ("172.18.0.5", None, "172.18.0.5"),
        ("172.18.0.5", "pas-une-ip", "172.18.0.5"),
    ],
)
def test_get_client_ip(peer, xff, attendu):
    assert get_client_ip(_req(peer, xff)) == attendu


async def test_xff_forge_ne_contourne_plus_le_verrou(client):
    # Avant correctif : 8 échecs avec X-Forwarded-For tournant => jamais bloqué
    codes = []
    for i in range(7):
        res = await client.post(
            "/api/auth/login", json=MAUVAIS, headers={"X-Forwarded-For": f"1.2.3.{i}"}
        )
        codes.append(res.status_code)
    assert codes[:5] == [401] * 5
    assert codes[5:] == [429, 429]


async def test_verrou_par_compte_toutes_ip(monkeypatch):
    # Même si l'attaquant contrôle réellement plusieurs IP, le compte se verrouille
    monkeypatch.setattr(settings, "MAX_LOGIN_ATTEMPTS_PER_ACCOUNT", 6)
    codes = []
    for i in range(8):
        transport = httpx.ASGITransport(app=app, client=(f"198.51.100.{i}", 4000))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            res = await c.post("/api/auth/login", json=MAUVAIS)
            codes.append(res.status_code)
    assert codes[:6] == [401] * 6
    assert codes[6:] == [429, 429]


async def test_admin_web_protege(client):
    codes = []
    for _ in range(7):
        res = await client.post(
            "/admin/login",
            data={"username": "admin", "password": "mauvais_mot_de_passe"},
            follow_redirects=False,
        )
        codes.append(res.status_code)
    assert codes[:5] == [400] * 5
    assert codes[5:] == [429, 429]


async def test_succes_reinitialise_les_compteurs(client):
    from tests.conftest import ADMIN_PASSWORD

    for _ in range(4):
        await client.post("/api/auth/login", json=MAUVAIS)
    ok = await client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert ok.status_code == 200
    for _ in range(4):
        res = await client.post("/api/auth/login", json=MAUVAIS)
        assert res.status_code == 401
