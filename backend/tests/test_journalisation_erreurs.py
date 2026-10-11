"""Tests de la journalisation structurée, du request_id et du format d'erreur uniforme."""
import json
import logging

import httpx

from app.core.journalisation import FiltreContexte, FormateurJson, masquer_secrets
from app.main import app


def test_masquage_des_secrets():
    jwt_ = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc-DEF_123"
    assert "abc-DEF" not in masquer_secrets(f"GET /api/videos/3/stream?token={jwt_}&x=1")
    assert masquer_secrets("GET /stream?token=secret123&x=1") == "GET /stream?token=***&x=1"
    assert masquer_secrets("Authorization: Bearer abc.def.ghi") == "Authorization: Bearer ***"
    assert "s3cret" not in masquer_secrets("{'username': 'a', 'password': 's3cret'}")
    assert "1BJWap" not in masquer_secrets('string_session="1BJWapABCDEF"')


def test_filtre_masque_les_arguments_et_ajoute_request_id():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "%s %s", ("GET", "/x?token=abc"), None)
    FiltreContexte().filter(record)
    assert record.getMessage() == "GET /x?token=***"
    assert record.request_id == "-"
    ligne = json.loads(FormateurJson().format(record))
    assert ligne["message"] == "GET /x?token=***" and ligne["niveau"] == "INFO"


async def test_request_id_genere_et_propage(client):
    res = await client.get("/api/health")
    assert len(res.headers["x-request-id"]) >= 8
    res = await client.get("/api/health", headers={"X-Request-ID": "app-1234-abcd"})
    assert res.headers["x-request-id"] == "app-1234-abcd"
    # Valeur malveillante ignorée (injection dans les journaux)
    res = await client.get("/api/health", headers={"X-Request-ID": "x\nfaux"})
    assert res.headers["x-request-id"] != "x\nfaux"


async def test_format_erreur_uniforme(client):
    res = await client.get("/api/auth/me")
    corps = res.json()
    assert res.status_code == 401
    assert corps["code"] == "non_authentifie"
    assert isinstance(corps["detail"], str)  # l'app installée affiche detail tel quel
    assert corps["request_id"] == res.headers["x-request-id"]

    res = await client.post("/api/auth/login", json={"username": "a"})
    corps = res.json()
    assert res.status_code == 422 and corps["code"] == "validation"
    assert isinstance(corps["detail"], list) and "loc" in corps["detail"][0]


async def test_admin_web_garde_ses_redirections(client):
    res = await client.get("/admin", follow_redirects=False)
    assert res.status_code in (302, 303, 307)


async def test_erreur_inattendue_sans_fuite(caplog):
    async def _boom():
        raise RuntimeError("chemin secret /app/data/vidtele.db")

    app.add_api_route("/api/_test_boom", _boom)
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            with caplog.at_level(logging.ERROR):
                res = await c.get("/api/_test_boom")
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/api/_test_boom"]
    assert res.status_code == 500
    assert res.json()["code"] == "erreur_interne"
    assert "secret" not in res.text
    assert any("Erreur non gérée" in r.getMessage() for r in caplog.records)
