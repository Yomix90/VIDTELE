"""
Contrat de l'API utilisée par les applications mobiles DÉJÀ INSTALLÉES (non-régression).

Principe : un catalogue réaliste est créé, chaque endpoint appelé par l'app est interrogé
et la « forme » de la réponse (clés + types, récursivement) est comparée à un instantané
enregistré dans tests/contrat/formes_api.json.

- Une clé ajoutée est acceptée (les anciennes apps l'ignorent).
- Une clé supprimée ou un type changé fait échouer le test (les anciennes apps casseraient).

Régénérer l'instantané (uniquement pour un changement volontaire et compatible) :
    MAJ_CONTRAT=1 pytest tests/test_contrat_api.py
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.database import AsyncSessionLocal
from app.models import Episode, Movie, Season, Series, Video

FICHIER_CONTRAT = Path(__file__).parent / "contrat" / "formes_api.json"


def _maintenant():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def forme(valeur):
    """Réduit une valeur JSON à sa structure : clés et types (les valeurs sont ignorées)."""
    if isinstance(valeur, dict):
        return {k: forme(v) for k, v in sorted(valeur.items())}
    if isinstance(valeur, list):
        fusion = None
        for element in valeur:
            fusion = _fusionner(fusion, forme(element))
        return [fusion] if fusion is not None else []
    if isinstance(valeur, bool):
        return "bool"
    if isinstance(valeur, (int, float)):
        return "nombre"
    if isinstance(valeur, str):
        return "texte"
    return "null"


def _fusionner(a, b):
    """Fusionne les formes des éléments d'une liste (union des clés)."""
    if a is None or a == "null":
        return b
    if b == "null":
        return a
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: _fusionner(a.get(k), b.get(k)) for k in sorted(set(a) | set(b))}
    if isinstance(a, list) and isinstance(b, list):
        if not a or not b:
            return a or b
        return [_fusionner(a[0], b[0])]
    return a


def ecarts(attendu, actuel, chemin="$"):
    """Liste les incompatibilités : clé disparue ou type différent."""
    if attendu == "null" or attendu == []:
        return []  # aucune contrainte connue
    if actuel == "null":
        # Une valeur nulle là où l'app attendait un objet/une liste peut la faire planter
        return [f"{chemin}: {attendu if isinstance(attendu, str) else type(attendu).__name__} devenu null"] if not isinstance(attendu, str) else []
    if isinstance(attendu, dict):
        if not isinstance(actuel, dict):
            return [f"{chemin}: objet attendu"]
        out = []
        for cle, sous in attendu.items():
            if cle not in actuel:
                out.append(f"{chemin}.{cle}: clé supprimée")
            else:
                out += ecarts(sous, actuel[cle], f"{chemin}.{cle}")
        return out
    if isinstance(attendu, list):
        if not isinstance(actuel, list):
            return [f"{chemin}: liste attendue"]
        if not actuel:
            return []
        return ecarts(attendu[0], actuel[0], f"{chemin}[]")
    if attendu != actuel:
        return [f"{chemin}: type {attendu} devenu {actuel}"]
    return []


@pytest.fixture(scope="module")
async def catalogue(client):
    """Catalogue de démonstration : 2 séries publiées (2 saisons), 1 film, favoris et historique."""
    async with AsyncSessionLocal() as db:
        videos = []
        for i in range(6):
            v = Video(
                telegram_message_id=7001 + i,
                title=f"Vidéo {i}",
                caption="Légende",
                category="drame",
                duration_seconds=90 + i,
                file_size_bytes=1_000_000,
                telegram_date=_maintenant() - timedelta(days=i),
                is_published=True,
                file_name=f"v{i}.mp4",
                views_count=10 * i,
            )
            db.add(v)
            videos.append(v)
        await db.flush()

        series_ids = []
        for s_idx in range(2):
            serie = Series(
                slug=f"serie-test-{s_idx}",
                title_fr=f"Série {s_idx}",
                title_ar=f"مسلسل {s_idx}",
                synopsis_fr="Synopsis",
                year_start=2026,
                rating=8.5,
                status="ongoing",
                poster_path="/static/uploads/poster.jpg",
                banner_path="/static/uploads/banner.jpg",
                is_featured=True,
                visibility="published",
            )
            db.add(serie)
            await db.flush()
            series_ids.append(serie.id)
            for n in (1, 2):
                saison = Season(series_id=serie.id, number=n, title_fr=f"Saison {n}")
                db.add(saison)
                await db.flush()
                video = videos[s_idx * 2 + (n - 1)]
                db.add(Episode(season_id=saison.id, telegram_video_id=video.id, number=1, title_fr="Épisode 1", duration_sec=90))

        film = Movie(
            slug="film-test",
            title_fr="Film test",
            telegram_video_id=videos[5].id,
            year=2026,
            duration_sec=5400,
            visibility="published",
            is_featured=True,
        )
        db.add(film)
        await db.commit()

    return {"video_ids": [v.id for v in videos], "series_ids": series_ids}


@pytest.fixture(scope="module")
async def utilisateur(client, admin_token, catalogue):
    """Utilisateur standard inscrit avec un code d'invitation, comme dans l'app."""
    entetes_admin = {"Authorization": f"Bearer {admin_token}"}
    res = await client.post("/api/admin/invites", json={"code": "CONTRAT-2026", "max_uses": 5}, headers=entetes_admin)
    assert res.status_code == 201, res.text
    res = await client.post(
        "/api/auth/register",
        json={"username": "spectateur", "password": "MotDePasse123!", "invite_code": "CONTRAT-2026"},
    )
    assert res.status_code == 201, res.text
    jetons = res.json()
    entetes = {"Authorization": f"Bearer {jetons['access_token']}"}

    # Favoris, historique et reprise de lecture comme le ferait l'app.
    # Le favori de série bascule le favori de son 1er épisode : on le fait en premier,
    # puis on ajoute une vidéo autonome (vidéo 4, ni épisode ni film).
    assert (await client.post(f"/api/series/{catalogue['series_ids'][0]}/favorite", headers=entetes)).status_code == 200
    assert (await client.post(f"/api/favorites/{catalogue['video_ids'][4]}", headers=entetes)).status_code == 201
    vid = catalogue["video_ids"][0]
    res = await client.put(
        f"/api/videos/{vid}/progress",
        json={"position_seconds": 42.0, "progress_seconds": 42.0, "completed": False},
        headers=entetes,
    )
    assert res.status_code == 200, res.text
    return {"entetes": entetes, "jetons": jetons, "admin": entetes_admin}


def _appels(catalogue):
    """Appels effectués par l'application installée (version 1.2.0)."""
    vid = catalogue["video_ids"][0]
    sid = catalogue["series_ids"][0]
    return [
        ("GET", "/api/app/version", {"params": {"current_version": "1.2.0"}}, "public"),
        ("GET", "/api/auth/me", {}, "user"),
        ("GET", "/api/home", {}, "user"),
        ("GET", "/api/videos/home", {}, "user"),
        ("GET", "/api/series/top", {"params": {"period": "7d", "limit": 5}}, "user"),
        ("GET", "/api/feed", {"params": {"limit": 15}}, "user"),
        ("GET", "/api/feed", {"params": {"limit": 15, "series_id": sid}}, "user"),
        ("GET", "/api/videos", {"params": {"limit": 100, "exclude_episodes": True}}, "user"),
        ("GET", "/api/videos/series", {}, "user"),
        ("GET", "/api/videos/series/latest", {}, "user"),
        ("GET", f"/api/videos/series/{sid}", {}, "user"),
        ("GET", f"/api/series/{sid}", {}, "user"),
        ("GET", "/api/videos/categories", {}, "user"),
        ("GET", f"/api/videos/{vid}", {}, "user"),
        ("GET", f"/api/videos/{vid}/stream-token", {}, "user"),
        ("POST", f"/api/videos/{vid}/stream-token", {}, "user"),
        ("GET", "/api/history", {}, "user"),
        ("GET", "/api/favorites", {}, "user"),
        ("GET", "/api/admin/stats", {}, "admin"),
    ]


async def test_contrat_api_applications_installees(client, catalogue, utilisateur):
    formes = {}
    for methode, chemin, options, qui in _appels(catalogue):
        entetes = {"public": {}, "user": utilisateur["entetes"], "admin": utilisateur["admin"]}[qui]
        res = await client.request(methode, chemin, headers=entetes, **options)
        assert res.status_code == 200, f"{methode} {chemin} -> {res.status_code} {res.text[:200]}"
        cle = f"{methode} {chemin}" + (f"?{sorted(options['params'].items())}" if "params" in options else "")
        formes[_normaliser(cle, catalogue)] = forme(res.json())

    # Rafraîchissement du jeton (utilisé par l'intercepteur Dio)
    res = await client.post("/api/auth/refresh", json={"refresh_token": utilisateur["jetons"]["refresh_token"]})
    assert res.status_code == 200
    formes["POST /api/auth/refresh"] = forme(res.json())
    formes["POST /api/auth/register"] = forme(utilisateur["jetons"])

    if os.environ.get("MAJ_CONTRAT") == "1" or not FICHIER_CONTRAT.exists():
        FICHIER_CONTRAT.parent.mkdir(exist_ok=True)
        FICHIER_CONTRAT.write_text(json.dumps(formes, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        pytest.skip("Instantané du contrat (re)généré : relancer le test pour vérifier.")

    attendu = json.loads(FICHIER_CONTRAT.read_text(encoding="utf-8"))
    problemes = []
    for cle, forme_attendue in attendu.items():
        if cle not in formes:
            problemes.append(f"{cle}: endpoint non testé ou disparu")
            continue
        problemes += [f"{cle} -> {e}" for e in ecarts(forme_attendue, formes[cle])]
    assert not problemes, "Rupture de compatibilité :\n" + "\n".join(problemes)


def _normaliser(cle, catalogue):
    """Remplace les identifiants variables par des marqueurs stables dans les clés."""
    cle = re.sub(r"/api/series/\d+", "/api/series/{series_id}", cle)
    cle = re.sub(r"/api/videos/series/\d+", "/api/videos/series/{series_id}", cle)
    cle = re.sub(r"/api/videos/\d+", "/api/videos/{video_id}", cle)
    return re.sub(r"\('series_id', \d+\)", "('series_id', {series_id})", cle)


def test_outil_de_forme():
    # Vérifie l'outil lui-même : suppression de clé et changement de type détectés
    a = forme({"id": 1, "titre": "x", "liste": [{"n": 1}]})
    assert ecarts(a, forme({"id": 2, "titre": "y", "liste": [{"n": 3}], "nouveau": True})) == []
    assert ecarts(a, forme({"id": 2, "liste": []})) == ["$.titre: clé supprimée"]
    assert ecarts(a, forme({"id": "2", "titre": "y", "liste": []})) == ["$.id: type nombre devenu texte"]
