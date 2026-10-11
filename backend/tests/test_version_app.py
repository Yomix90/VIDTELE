"""Tests de la version minimale de l'application (fenêtre au lancement + contrôle X-App-Version)."""
import pytest

from app.database import AsyncSessionLocal
from app.models import SystemSetting
from app.services import version_app
from app.services.version_app import analyser_version


@pytest.mark.parametrize(
    "texte, attendu",
    [("1.2.0", (1, 2, 0)), ("1.3", (1, 3, 0)), ("v2.0.1+7", (2, 0, 1)), ("1.4.0-beta", (1, 4, 0)), ("", (0, 0, 0)), (None, (0, 0, 0))],
)
def test_analyser_version(texte, attendu):
    assert analyser_version(texte) == attendu


@pytest.fixture
async def version_minimale_130():
    """Règle la version minimale à 1.3.0 (comme depuis l'admin), puis restaure."""
    async with AsyncSessionLocal() as db:
        db.add(SystemSetting(key="app_min_version", value="1.3.0"))
        db.add(SystemSetting(key="app_latest_version", value="1.3.0"))
        await db.commit()
    version_app.invalider_cache()
    yield
    async with AsyncSessionLocal() as db:
        for cle in ("app_min_version", "app_latest_version"):
            ligne = await db.get(SystemSetting, cle)
            await db.delete(ligne)
        await db.commit()
    version_app.invalider_cache()


async def test_lancement_ancienne_version_obligatoire(client, version_minimale_130):
    # L'app 1.2.0 installée affiche alors la fenêtre bloquante (force_update)
    res = await client.get("/api/app/version", params={"current_version": "1.2.0"})
    corps = res.json()
    assert corps["force_update"] is True and corps["has_update"] is True
    res = await client.get("/api/app/version", params={"current_version": "1.3.0"})
    assert res.json()["force_update"] is False


async def test_entete_version_trop_ancienne_426(client, auth, version_minimale_130):
    res = await client.get("/api/home", headers={**auth, "X-App-Version": "1.2.9"})
    corps = res.json()
    assert res.status_code == 426
    assert corps["code"] == "mise_a_jour_requise" and corps["min_version"] == "1.3.0"
    assert "request_id" in corps


async def test_entete_version_suffisante(client, auth, version_minimale_130):
    res = await client.get("/api/home", headers={**auth, "X-App-Version": "1.3.0"})
    assert res.status_code == 200


async def test_sans_entete_apps_installees_non_bloquees(client, auth, version_minimale_130):
    res = await client.get("/api/home", headers=auth)
    assert res.status_code == 200


async def test_chemins_toujours_accessibles(client, version_minimale_130):
    for chemin in ("/api/health", "/api/health/ready", "/api/app/version"):
        res = await client.get(chemin, headers={"X-App-Version": "1.0.0"})
        assert res.status_code in (200, 503), chemin
