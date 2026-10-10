"""
Configuration commune des tests pytest.

Les variables d'environnement sont fixées AVANT l'import de l'application :
base SQLite jetable, cache temporaire et Telegram désactivé.
Aucun test ne touche la base locale ni la production.
"""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="vidtele_tests_"))
os.environ.update(
    {
        "DATABASE_URL": f"sqlite+aiosqlite:///{(_TMP / 'test.db').as_posix()}",
        "CACHE_DIR": str(_TMP / "cache"),
        "THUMBNAILS_DIR": str(_TMP / "thumbs"),
        "DATA_DIR": str(_TMP / "data"),
        "TELEGRAM_API_ID": "0",
        "TELEGRAM_API_HASH": "",
        "TELEGRAM_STRING_SESSION": "",
        "SECRET_KEY": "cle_de_test_tres_longue_0123456789abcdef0123456789",
        "ADMIN_DEFAULT_USERNAME": "admin",
        "ADMIN_DEFAULT_PASSWORD": "MotDePasseTest123!",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app, bootstrap_admin_and_invites  # noqa: E402

ADMIN_PASSWORD = os.environ["ADMIN_DEFAULT_PASSWORD"]


@pytest.fixture(scope="session")
async def client():
    """Client HTTP branché directement sur l'application ASGI (sans réseau)."""
    await init_db()
    await bootstrap_admin_and_invites()
    transport = httpx.ASGITransport(app=app, client=("203.0.113.10", 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(scope="session")
async def admin_token(client):
    """Jeton d'accès de l'administrateur de test."""
    res = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": ADMIN_PASSWORD},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
