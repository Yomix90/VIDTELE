"""
Script de test pour les fonctionnalités d'administration, limites et suivi (Étape 5).
"""
import asyncio
from datetime import datetime, timezone
import httpx
from sqlalchemy import select

from app.database import AsyncSessionLocal, init_db
from app.main import app, bootstrap_admin_and_invites
from app.models import User, Video


async def run_tests():
    print("=" * 60)
    print("DEMARRAGE DU TEST ADMIN, LIMITES & SUIVI (ETAPE 5)")
    print("=" * 60)

    # 1. Initialiser la base
    await init_db()
    await bootstrap_admin_and_invites()

    # Création d'une vidéo de test si absente
    async with AsyncSessionLocal() as db:
        v = (await db.execute(select(Video))).scalars().first()
        if not v:
            v = Video(
                telegram_message_id=555,
                title="Vidéo Test Suivi",
                duration_seconds=300,
                file_size_bytes=10_000_000,
                telegram_date=datetime.now(timezone.utc).replace(tzinfo=None),
                is_published=True,
            )
            db.add(v)
            await db.commit()
            await db.refresh(v)
        else:
            v.is_published = True
            await db.commit()
        test_video_id = v.id

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Connexion Admin
        login_res = await client.post("/api/auth/login", json={"username": "admin", "password": "AdminSecurePass2026!"})
        admin_token = login_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Test Enregistrement de la progression de lecture (PUT /api/videos/{id}/progress)
        res = await client.put(
            f"/api/videos/{test_video_id}/progress",
            headers=auth_headers,
            json={"position_seconds": 45.5, "completed": False},
        )
        assert res.status_code == 200
        print("[OK] 1. Progression de lecture enregistrée (45.5s)")

        # 3. Test Récupération de l'historique (GET /api/history)
        res = await client.get("/api/history", headers=auth_headers)
        assert res.status_code == 200
        history = res.json()
        assert len(history) >= 1
        assert history[0]["video_id"] == test_video_id
        assert history[0]["position_seconds"] == 45.5
        print(f"[OK] 2. Historique de visionnage validé ({len(history)} entrée(s))")

        # 4. Test Ajout aux favoris (POST /api/favorites/{id})
        res = await client.post(f"/api/favorites/{test_video_id}", headers=auth_headers)
        assert res.status_code in (200, 201)
        print("[OK] 3. Vidéo ajoutée aux favoris")

        # 5. Test Récupération des favoris (GET /api/favorites)
        res = await client.get("/api/favorites", headers=auth_headers)
        assert res.status_code == 200
        favs = res.json()
        assert any(f["video_id"] == test_video_id for f in favs)
        print(f"[OK] 4. Liste des favoris validée ({len(favs)} favori(s))")

        # 6. Test Suppression des favoris (DELETE /api/favorites/{id})
        res = await client.delete(f"/api/favorites/{test_video_id}", headers=auth_headers)
        assert res.status_code == 200
        print("[OK] 5. Vidéo retirée des favoris")

        # 7. Test Statistiques Admin globales (GET /api/admin/stats)
        res = await client.get("/api/admin/stats", headers=auth_headers)
        assert res.status_code == 200
        stats = res.json()
        assert "total_videos" in stats
        assert "cache" in stats
        assert "streams" in stats
        print(f"[OK] 6. Statistiques globales : {stats['total_videos']} vidéos, {stats['total_users']} utilisateurs")

        # 8. Test Création et Gestion Utilisateur Admin (POST, PUT, DELETE /api/admin/users)
        # Création
        res = await client.post(
            "/api/admin/users",
            headers=auth_headers,
            json={
                "username": "user_demo",
                "password": "Password123!",
                "role": "user",
                "max_concurrent_streams": 3,
            },
        )
        assert res.status_code == 201
        created_user = res.json()
        user_demo_id = created_user["id"]
        print(f"[OK] 7. Création utilisateur admin : '{created_user['username']}' (ID: {user_demo_id})")

        # Modification
        res = await client.put(
            f"/api/admin/users/{user_demo_id}",
            headers=auth_headers,
            json={"is_active": False, "max_concurrent_streams": 1},
        )
        assert res.status_code == 200
        assert res.json()["is_active"] is False
        assert res.json()["max_concurrent_streams"] == 1
        print("[OK] 8. Modification utilisateur (désactivation + quota flux) : Validée")

        # Suppression
        res = await client.delete(f"/api/admin/users/{user_demo_id}", headers=auth_headers)
        assert res.status_code == 200
        print("[OK] 9. Suppression utilisateur : Validée")

        # 9. Test Création de Code d'Invitation (POST /api/admin/invites)
        res = await client.post(
            "/api/admin/invites",
            headers=auth_headers,
            json={"expires_in_days": 14},
        )
        assert res.status_code == 201
        new_inv = res.json()
        assert new_inv["code"].startswith("INV-")
        print(f"[OK] 10. Code d'invitation généré : '{new_inv['code']}'")

        # Suppression de l'invitation
        res = await client.delete(f"/api/admin/invites/{new_inv['id']}", headers=auth_headers)
        assert res.status_code == 200
        print("[OK] 11. Révocation de l'invitation : Validée")

        # 10. Test Rendu de l'Interface Web Admin (GET /admin)
        res = await client.get("/admin")
        assert res.status_code == 200
        assert "VidTele Admin" in res.text
        assert "Tableau de Bord" in res.text
        print("[OK] 12. Interface Web Admin (HTML + Bootstrap 5 + RTL/LTR) : Rendue avec succès (200 OK)")

    print("=" * 60)
    print("TOUS LES TESTS DE L'ETAPE 5 ONT REUSSI AVEC SUCCES !")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
