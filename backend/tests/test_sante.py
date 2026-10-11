"""Tests des vérifications de santé."""
from app.config import settings


async def test_vivant_inchange(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert set(res.json()) == {"status", "app", "timestamp"}


async def test_pret_sans_telegram_degrade(client):
    res = await client.get("/api/health/ready")
    corps = res.json()
    assert res.status_code == 200
    assert corps["composants"]["base"]["status"] == "ok"
    assert corps["composants"]["telegram"]["status"] == "non_configure"
    assert corps["status"] == "degrade"


async def test_pret_disque_plein(client, monkeypatch):
    monkeypatch.setattr(settings, "DISK_MIN_FREE_GB", 10**9)
    res = await client.get("/api/health/ready")
    assert res.status_code == 503
    assert res.json()["status"] == "ko"
