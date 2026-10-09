"""
Test complet de l'organisation des vidéos en Films et Séries (VidTele Catalogue Management).
Vérifie que :
1. Les vidéos brutes Telegram (non publiées) ne s'affichent PAS sur le catalogue mobile (/api/videos).
2. L'administrateur peut créer un Film et y associer une vidéo brute.
3. Lors de la publication du Film, la vidéo devient immédiatement accessible sur le mobile.
4. L'administrateur peut créer une Série avec plusieurs épisodes (S01E01, S01E02...).
5. La dépublication et la suppression fonctionnent sans perte des vidéos brutes Telegram.
"""
import asyncio
from datetime import datetime, timezone
import httpx
from sqlalchemy import select

from app.database import AsyncSessionLocal, init_db
from app.main import app, bootstrap_admin_and_invites
from app.models import MediaItem, Video


async def run_tests():
    print("=" * 65)
    print("TEST ORGANISATION DES VIDEOS (FILMS & SERIES) & MASQUAGE MOBILE")
    print("=" * 65)

    await init_db()
    await bootstrap_admin_and_invites()

    async with AsyncSessionLocal() as db:
        # Créer 2 vidéos brutes non publiées (simulant un upload Telegram)
        raw_vid1 = Video(
            telegram_message_id=9001,
            title="film_action_raw.mp4",
            duration_seconds=7200,
            file_size_bytes=1_500_000_000,
            telegram_date=datetime.now(timezone.utc).replace(tzinfo=None),
            is_published=False,  # BRUTE / NON PUBLIEE
        )
        raw_vid2 = Video(
            telegram_message_id=9002,
            title="episode_1_raw.mp4",
            duration_seconds=2700,
            file_size_bytes=450_000_000,
            telegram_date=datetime.now(timezone.utc).replace(tzinfo=None),
            is_published=False,  # BRUTE / NON PUBLIEE
        )
        db.add_all([raw_vid1, raw_vid2])
        await db.commit()
        await db.refresh(raw_vid1)
        await db.refresh(raw_vid2)
        v1_id = raw_vid1.id
        v2_id = raw_vid2.id

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Connexion Admin
        login_res = await client.post("/api/auth/login", json={"username": "admin", "password": "AdminSecurePass2026!"})
        admin_token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Vérification que les 2 vidéos brutes NE SONT PAS visibles sur l'API mobile publique /api/videos
        pub_res = await client.get("/api/videos", headers=headers)
        assert pub_res.status_code == 200
        pub_videos = pub_res.json()["items"]
        found_raw1 = any(v["id"] == v1_id for v in pub_videos)
        found_raw2 = any(v["id"] == v2_id for v in pub_videos)
        assert not found_raw1, "La vidéo brute 1 ne doit PAS apparaître sur mobile !"
        assert not found_raw2, "La vidéo brute 2 ne doit PAS apparaître sur mobile !"
        print("[OK] 1. Les vidéos brutes restent bien masquées du catalogue mobile.")

        # 3. Liste des vidéos brutes pour l'admin
        raw_res = await client.get("/api/admin/raw-videos?unassigned_only=true", headers=headers)
        assert raw_res.status_code == 200
        raw_list = raw_res.json()
        assert any(rv["id"] == v1_id for rv in raw_list)
        print(f"[OK] 2. Les vidéos brutes sont bien listées dans l'administration ({len(raw_list)} trouvées).")

        # 4. Création d'un Film (MediaItem) avec liaison directe de raw_vid1
        film_payload = {
            "title": "Interstellar",
            "media_type": "movie",
            "category": "Science-Fiction",
            "release_year": 2014,
            "rating": 8.7,
            "description": "Une équipe d'explorateurs voyage à travers un trou de ver.",
            "poster_url": "https://image.tmdb.org/t/p/w500/interstellar.jpg",
            "is_published": False,  # D'abord en brouillon
            "raw_video_id": v1_id,
        }
        create_res = await client.post("/api/admin/media-items", json=film_payload, headers=headers)
        assert create_res.status_code == 201, create_res.text
        film_data = create_res.json()
        film_id = film_data["id"]
        assert film_data["title"] == "Interstellar"
        assert film_data["video_count"] == 1
        print("[OK] 3. Film 'Interstellar' créé et vidéo brute associée.")

        # 5. Vérifier que tant que le film est brouillon (is_published=False), il n'apparaît toujours pas sur mobile
        pub_res = await client.get("/api/videos", headers=headers)
        pub_videos = pub_res.json()["items"]
        assert not any(v["id"] == v1_id for v in pub_videos)
        print("[OK] 4. Le Film en brouillon reste invisible sur mobile.")

        # 6. Publier le Film en 1 clic (toggle-publish)
        toggle_res = await client.post(f"/api/admin/media-items/{film_id}/toggle-publish", headers=headers)
        assert toggle_res.status_code == 200
        assert toggle_res.json()["is_published"] is True
        print("[OK] 5. Film publié avec succès.")

        # 7. Vérifier que la vidéo apparaît MAINTENANT sur l'API mobile avec les métadonnées du film
        pub_res = await client.get("/api/videos", headers=headers)
        pub_videos = pub_res.json()["items"]
        published_film_video = next((v for v in pub_videos if v["id"] == v1_id), None)
        assert published_film_video is not None, "La vidéo du film publié DOIT apparaître sur mobile !"
        assert published_film_video["title"] == "Interstellar"
        assert published_film_video["category"] == "Science-Fiction"
        print(f"[OK] 6. La vidéo apparaît sur mobile sous le titre '{published_film_video['title']}'.")

        # 8. Création d'une Série (MediaItem)
        series_payload = {
            "title": "Breaking Bad",
            "media_type": "series",
            "category": "Drame",
            "release_year": 2008,
            "rating": 9.5,
            "description": "Un professeur de chimie s'associe à un ancien élève.",
            "is_published": True,
        }
        series_res = await client.post("/api/admin/media-items", json=series_payload, headers=headers)
        assert series_res.status_code == 201
        series_id = series_res.json()["id"]

        # 9. Associer raw_vid2 comme Épisode 1 de la Saison 1
        ep_res = await client.post(
            f"/api/admin/media-items/{series_id}/episodes",
            json={
                "video_id": v2_id,
                "season_number": 1,
                "episode_number": 1,
                "episode_title": "Chute Libre",
            },
            headers=headers,
        )
        assert ep_res.status_code == 200
        print("[OK] 7. Épisode S01E01 rattaché à la série.")

        # 10. Vérifier que l'épisode est formaté et publié sur mobile
        pub_res = await client.get("/api/videos", headers=headers)
        pub_videos = pub_res.json()["items"]
        published_ep = next((v for v in pub_videos if v["id"] == v2_id), None)
        assert published_ep is not None
        assert "Breaking Bad - S01E01 : Chute Libre" in published_ep["title"]
        print(f"[OK] 8. Épisode de série publié : '{published_ep['title']}'.")

        # 11. Détacher l'épisode et vérifier qu'il retourne dans les vidéos brutes et disparaît du mobile
        detach_res = await client.delete(f"/api/admin/media-items/{series_id}/episodes/{v2_id}", headers=headers)
        assert detach_res.status_code == 200

        pub_res = await client.get("/api/videos", headers=headers)
        pub_videos = pub_res.json()["items"]
        assert not any(v["id"] == v2_id for v in pub_videos)
        print("[OK] 9. Vidéo détachée avec succès et retirée du catalogue mobile.")

        # 12. Supprimer le film et vérifier que la vidéo n'est pas effacée mais dépubliée
        del_res = await client.delete(f"/api/admin/media-items/{film_id}", headers=headers)
        assert del_res.status_code == 200
        async with AsyncSessionLocal() as db:
            v_check = (await db.execute(select(Video).where(Video.id == v1_id))).scalar_one_or_none()
            assert v_check is not None, "La vidéo ne doit pas être détruite !"
            assert v_check.is_published is False
            assert v_check.media_item_id is None
        print("[OK] 10. Suppression du Film : la vidéo brute Telegram est préservée et dépubliée.")

    print("=" * 65)
    print("TOUS LES TESTS D'ORGANISATION FILMS & SERIES ONT REUSSI (10/10) !")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_tests())
