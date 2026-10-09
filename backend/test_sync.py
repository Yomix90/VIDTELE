"""
Script de test pour la gestion des vidéos et la synchronisation (Étape 3).
"""
import asyncio
from datetime import datetime, timezone
import httpx
from sqlalchemy import select

from app.database import AsyncSessionLocal, init_db
from app.main import app, bootstrap_admin_and_invites
from app.models import Video
from app.services.sync_service import sync_service


async def run_tests():
    print("=" * 60)
    print("DEMARRAGE DU TEST DE GESTION DES VIDEOS & SYNC (ETAPE 3)")
    print("=" * 60)

    # 1. Initialiser la base
    await init_db()
    await bootstrap_admin_and_invites()

    # 2. Test unitaire de l'extraction de titres et catégories (hashtags)
    title, cat, caption = sync_service._extract_category_and_title(
        "Introduction au Python moderne\nVoici un tutoriel complet #formation #dev",
        "default.mp4"
    )
    assert title == "Introduction au Python moderne"
    assert cat == "Formation"
    print(f"[OK] 1. Extraction regex hashtag : Titre='{title}', Catégorie='{cat}'")

    title_ar, cat_ar, _ = sync_service._extract_category_and_title(
        "مقدمة في البرمجة\nشرح مبسط للمبتدئين #تعليم",
        "default.mp4"
    )
    assert title_ar == "مقدمة في البرمجة"
    assert cat_ar == "تعليم"
    print("[OK] 2. Support hashtag multilingue (Arabe) : OK")

    # 3. Insertion de données vidéo de test en base
    async with AsyncSessionLocal() as db:
        # Nettoyage
        existing = (await db.execute(select(Video))).scalars().all()
        for v in existing:
            await db.delete(v)
        await db.commit()

        # Insertion de vidéos simulées
        v1 = Video(
            telegram_message_id=101,
            title="Clip Nature 4K",
            caption="Superbe paysage de montagne #nature",
            category="Nature",
            duration_seconds=120,
            file_size_bytes=15_000_000,
            mime_type="video/mp4",
            telegram_date=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        v2 = Video(
            telegram_message_id=102,
            title="Tutoriel Flutter Mobile",
            caption="Créer une application de streaming #tutoriel",
            category="Tutoriel",
            duration_seconds=300,
            file_size_bytes=45_000_000,
            mime_type="video/mp4",
            telegram_date=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        v3 = Video(
            telegram_message_id=103,
            title="Clip Cascade Sauvage",
            caption="Vue aérienne par drone #nature",
            category="Nature",
            duration_seconds=60,
            file_size_bytes=10_000_000,
            mime_type="video/mp4",
            telegram_date=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add_all([v1, v2, v3])
        await db.commit()
    print("[OK] 3. Données de test insérées en base (3 vidéos, 2 catégories)")

    # 4. Tests des endpoints via HTTP
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Connexion admin pour récupérer le token
        login_res = await client.post("/api/auth/login", json={"username": "admin", "password": "AdminSecurePass2026!"})
        admin_token = login_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {admin_token}"}

        # 4.1 Liste des vidéos (GET /api/videos)
        res = await client.get("/api/videos", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        print(f"[OK] 4.1 GET /api/videos : {data['total']} vidéos retournées avec pagination")

        # 4.2 Filtrage par catégorie
        res = await client.get("/api/videos?category=Nature", headers=auth_headers)
        assert res.status_code == 200
        nat_data = res.json()
        assert nat_data["total"] == 2
        print(f"[OK] 4.2 Filtre par catégorie 'Nature' : {nat_data['total']} vidéos retournées")

        # 4.3 Recherche par mot-clé (q)
        res = await client.get("/api/videos?q=Flutter", headers=auth_headers)
        assert res.status_code == 200
        search_data = res.json()
        assert search_data["total"] == 1
        assert search_data["items"][0]["title"] == "Tutoriel Flutter Mobile"
        print("[OK] 4.3 Recherche textuelle 'Flutter' : 1 résultat exact")

        # 4.4 Liste des catégories agrégées (GET /api/videos/categories)
        res = await client.get("/api/videos/categories", headers=auth_headers)
        assert res.status_code == 200
        cats = res.json()
        assert len(cats) == 2
        print(f"[OK] 4.4 GET /api/videos/categories : {cats}")

        # 4.5 Détail d'une vidéo (GET /api/videos/{id})
        vid_id = data["items"][0]["id"]
        res = await client.get(f"/api/videos/{vid_id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["id"] == vid_id
        print(f"[OK] 4.5 GET /api/videos/{vid_id} : Détails récupérés avec succès")

        # 4.6 Récupération de la miniature (placeholder SVG si non présente sur disque)
        res = await client.get(f"/api/videos/{vid_id}/thumbnail")
        assert res.status_code == 200
        assert "svg" in res.headers.get("content-type", "") or "jpeg" in res.headers.get("content-type", "")
        print("[OK] 4.6 GET /api/videos/{id}/thumbnail : Image / Placeholder retourné")

        # 4.7 Vérification de la sécurité de /api/admin/sync sans token admin
        res = await client.post("/api/admin/sync")
        assert res.status_code == 401
        print("[OK] 4.7 Protection de /api/admin/sync (Rejet sans token 401) : OK")

    print("=" * 60)
    print("TOUS LES TESTS DE L'ÉTAPE 3 ONT RÉUSSI AVEC SUCCÈS !")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
