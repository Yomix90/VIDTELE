"""Tests de non-régression sur l'ordre des routes /api/videos/*."""


async def test_health(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


async def test_liste_series_accessible(client, auth):
    # Avant correctif : 422 car capturée par /api/videos/{video_id}
    res = await client.get("/api/videos/series", headers=auth)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


async def test_routes_statiques_videos_non_masquees(client, auth):
    for path in ("/api/videos/home", "/api/videos/feed", "/api/videos/series/top"):
        res = await client.get(path, headers=auth)
        assert res.status_code == 200, f"{path} -> {res.status_code}"


async def test_video_par_id_toujours_resolue(client, auth):
    # Un identifiant numérique inexistant doit renvoyer 404 (et non 422)
    res = await client.get("/api/videos/999999", headers=auth)
    assert res.status_code == 404
