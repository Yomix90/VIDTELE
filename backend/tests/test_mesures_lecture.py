"""Tests des mesures de lecture (POST /api/analytics/playback, GET /api/admin/stats/playback)."""


async def test_envoi_et_statistiques(client, auth):
    evenements = [{"type": "demarrage", "ttff_ms": t, "precharge": True, "reseau": "wifi"} for t in (300, 500, 700, 900)]
    evenements += [{"type": "demarrage", "ttff_ms": t, "precharge": False, "reseau": "mobile"} for t in (2000, 2600)]
    evenements += [
        {"type": "blocage", "stall_ms": 1200, "position_s": 12.5},
        {"type": "erreur", "code_erreur": "source_401"},
        {"type": "erreur", "code_erreur": "source_401"},
    ]
    res = await client.post(
        "/api/analytics/playback",
        json={"evenements": evenements},
        headers={**auth, "X-App-Version": "1.3.0"},
    )
    assert res.status_code == 202, res.text
    assert res.json() == {"enregistres": 9}

    stats = (await client.get("/api/admin/stats/playback", headers=auth)).json()
    assert stats["ttff_ms"]["precharge"]["nombre"] == 4
    assert stats["ttff_ms"]["precharge"]["p50"] in (500, 700)
    assert stats["ttff_ms"]["non_precharge"]["p90"] == 2600
    assert stats["blocages"]["nombre"] == 1
    assert stats["erreurs"] == {"source_401": 2}


async def test_validation_stricte(client, auth):
    # Type inconnu, valeurs aberrantes, lot vide ou trop gros : refusés
    for corps in (
        {"evenements": [{"type": "piratage"}]},
        {"evenements": [{"type": "demarrage", "ttff_ms": -5}]},
        {"evenements": []},
        {"evenements": [{"type": "fin"}] * 51},
    ):
        res = await client.post("/api/analytics/playback", json=corps, headers=auth)
        assert res.status_code == 422, corps


async def test_authentification_requise(client):
    res = await client.post("/api/analytics/playback", json={"evenements": [{"type": "fin"}]})
    assert res.status_code == 401
    res = await client.get("/api/admin/stats/playback")
    assert res.status_code == 401
