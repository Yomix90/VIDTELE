"""
Test de l'étape 5 : API REST d'administration StreamAdmin.
"""
import asyncio
import httpx
import sys
sys.path.insert(0, ".")
from app.main import app


async def test():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Login admin
        login_res = await client.post("/api/auth/login", json={"username": "admin", "password": "AdminSecurePass2026!"})
        assert login_res.status_code == 200, login_res.text
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Genres
        genres_res = await client.get("/api/admin/genres", headers=headers)
        assert genres_res.status_code == 200
        print(f"[OK] 1. Genres listes : {len(genres_res.json())}")

        # 3. Home rows
        hr_res = await client.get("/api/admin/home-rows", headers=headers)
        assert hr_res.status_code == 200
        print(f"[OK] 2. Home rows listees : {len(hr_res.json())}")

        # 4. Créer une Série
        s_payload = {
            "title_fr": "Peaky Blinders",
            "title_ar": "بيكي بلايندرز",
            "synopsis_fr": "Une famille de criminels a Birmingham.",
            "year_start": 2013,
            "rating": 8.8,
            "status": "ended",
            "visibility": "draft",
        }
        create_s = await client.post("/api/admin/series", json=s_payload, headers=headers)
        assert create_s.status_code == 201, create_s.text
        s_data = create_s.json()
        series_id = s_data["id"]
        print(f"[OK] 3. Serie creee : '{s_data['title_fr']}' (ID: {series_id}, Saisons: {s_data['seasons_count']})")

        # 5. Détail Série
        det_res = await client.get(f"/api/admin/series/{series_id}", headers=headers)
        assert det_res.status_code == 200
        det_data = det_res.json()
        season_1_id = det_data["seasons"][0]["id"]
        print(f"[OK] 4. Detail serie recupere, Saison 1 ID: {season_1_id}")

        # 6. Ajouter un épisode dans Saison 1
        ep_payload = {
            "number": 1,
            "title_fr": "Episode 1",
            "synopsis_fr": "Thomas Shelby vole une cargaison d armes.",
        }
        create_ep = await client.post(f"/api/admin/seasons/{season_1_id}/episodes", json=ep_payload, headers=headers)
        assert create_ep.status_code == 201, create_ep.text
        print("[OK] 5. Episode 1 ajoute dans Saison 1")

        # 7. Créer un Film
        m_payload = {
            "title_fr": "Gladiator",
            "synopsis_fr": "Le general romain Maximus est trahi.",
            "year": 2000,
            "rating": 8.5,
            "visibility": "published",
        }
        create_m = await client.post("/api/admin/movies", json=m_payload, headers=headers)
        assert create_m.status_code == 201, create_m.text
        m_data = create_m.json()
        print(f"[OK] 6. Film cree : '{m_data['title_fr']}' (ID: {m_data['id']})")

        # 8. Liste des films
        movies_res = await client.get("/api/admin/movies", headers=headers)
        assert movies_res.status_code == 200
        print(f"[OK] 7. Films listes : {len(movies_res.json())}")

        print("\n============================================================")
        print("TOUS LES ENDPOINTS REST DE L ETAPE 5 SONT OPERATIONNELS !")
        print("============================================================")


if __name__ == "__main__":
    asyncio.run(test())
