"""Tests S1/S2 : clé JWT publique refusée, mot de passe admin non réécrit, porte dérobée supprimée."""
from app import config
from app.config import settings
from app.main import bootstrap_admin_and_invites
from tests.conftest import ADMIN_PASSWORD


def test_cle_publique_remplacee_par_cle_persistante():
    original = settings.SECRET_KEY
    try:
        settings.SECRET_KEY = "change_me_super_secret_jwt_key_at_least_32_chars_vidtele_2026"
        config._resolve_secret_key()
        generated = settings.SECRET_KEY
        assert generated not in config.PUBLIC_DEFAULT_SECRET_KEYS
        assert len(generated) == 64
        assert (config.get_data_dir() / ".jwt_secret").read_text().strip() == generated

        # Au redémarrage suivant, la même clé est relue (les sessions restent valides)
        settings.SECRET_KEY = ""
        config._resolve_secret_key()
        assert settings.SECRET_KEY == generated
    finally:
        settings.SECRET_KEY = original


def test_cle_fournie_conservee():
    original = settings.SECRET_KEY
    try:
        settings.SECRET_KEY = "x" * 64
        config._resolve_secret_key()
        assert settings.SECRET_KEY == "x" * 64
    finally:
        settings.SECRET_KEY = original


async def test_mots_de_passe_maitres_refuses(client):
    for pwd in ("AdminSecurePass2026!", "VotreMotDePasseSecurise2026!"):
        res = await client.post("/api/auth/login", json={"username": "admin", "password": pwd})
        assert res.status_code == 401, pwd
        res = await client.post(
            "/admin/login", data={"username": "admin", "password": pwd}, follow_redirects=False
        )
        assert res.status_code in (400, 429), pwd


async def test_mot_de_passe_admin_conserve_au_redemarrage(client, auth):
    nouveau = "NouveauMotDePasse456!"
    res = await client.post(
        "/api/auth/change-password",
        json={"old_password": ADMIN_PASSWORD, "new_password": nouveau},
        headers=auth,
    )
    assert res.status_code == 200, res.text
    try:
        # Simule un redémarrage : avant correctif, le mot de passe repassait à ADMIN_DEFAULT_PASSWORD
        await bootstrap_admin_and_invites()
        res = await client.post("/api/auth/login", json={"username": "admin", "password": nouveau})
        assert res.status_code == 200
    finally:
        await client.post(
            "/api/auth/change-password",
            json={"old_password": nouveau, "new_password": ADMIN_PASSWORD},
            headers=auth,
        )


async def test_reinitialisation_de_secours(client, auth):
    nouveau = "AutreMotDePasse789!"
    await client.post(
        "/api/auth/change-password",
        json={"old_password": ADMIN_PASSWORD, "new_password": nouveau},
        headers=auth,
    )
    settings.ADMIN_RESET_PASSWORD = True
    try:
        await bootstrap_admin_and_invites()
    finally:
        settings.ADMIN_RESET_PASSWORD = False
    res = await client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert res.status_code == 200
