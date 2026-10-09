"""
Script de test pour le moteur de streaming HTTP Range 206 et le cache disque LRU (Étape 4).
"""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import httpx
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.main import app, bootstrap_admin_and_invites
from app.models import Video
from app.services.cache_service import cache_service
from app.services.stream_service import stream_service


async def run_tests():
    print("=" * 60)
    print("DEMARRAGE DU TEST DE STREAMING RANGE & CACHE (ETAPE 4)")
    print("=" * 60)

    # 1. Initialiser la base
    await init_db()
    await bootstrap_admin_and_invites()

    # 2. Test unitaire du parser d'en-tête HTTP Range
    file_size = 10_000_000  # 10 Mo
    s, e, l = stream_service.parse_range_header("bytes=0-1023", file_size)
    assert (s, e, l) == (0, 1023, 1024)
    print("[OK] 1. Range 'bytes=0-1023' : start=0, end=1023, length=1024")

    s, e, l = stream_service.parse_range_header("bytes=1048576-", file_size)
    assert (s, e, l) == (1048576, file_size - 1, file_size - 1048576)
    print("[OK] 2. Range 'bytes=1048576-' (seek forward) : OK")

    s, e, l = stream_service.parse_range_header("bytes=-500", file_size)
    assert (s, e, l) == (file_size - 500, file_size - 1, 500)
    print("[OK] 3. Range 'bytes=-500' (suffix/fin de fichier) : OK")

    # 3. Test du service de cache disque
    test_msg_id = 999
    test_cache_file = cache_service.get_video_path(test_msg_id)
    # Créer un faux fichier vidéo de exactement 2 Mo (2097152 octets)
    dummy_data = b"V" * (2 * 1024 * 1024)
    test_cache_file.write_bytes(dummy_data)
    dummy_size = len(dummy_data)

    assert cache_service.is_cached(test_msg_id)
    cache_service.touch(test_msg_id)
    stats = cache_service.get_cache_stats()
    assert stats["file_count"] >= 1
    print(f"[OK] 4. Cache disque actif : {stats['file_count']} fichiers, {stats['total_mb']} Mo")

    # 4. Insertion de la vidéo correspondante en base
    async with AsyncSessionLocal() as db:
        # Nettoyer et insérer
        stmt = select(Video).where(Video.telegram_message_id == test_msg_id)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if not existing:
            test_video = Video(
                telegram_message_id=test_msg_id,
                title="Vidéo Test Streaming Range",
                caption="Test de streaming HTTP 206 #test",
                category="Test",
                duration_seconds=60,
                file_size_bytes=dummy_size,
                mime_type="video/mp4",
                telegram_date=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.add(test_video)
            await db.commit()
            await db.refresh(test_video)
            video_id = test_video.id
        else:
            video_id = existing.id

    # 5. Tests HTTP avec HTTPX
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Récupérer token admin
        login_res = await client.post("/api/auth/login", json={"username": "admin", "password": "AdminSecurePass2026!"})
        admin_token = login_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {admin_token}"}

        # 5.1 Génération d'un stream token signé
        res = await client.get(f"/api/videos/{video_id}/stream-token", headers=auth_headers)
        assert res.status_code == 200
        stream_data = res.json()
        signed_stream_token = stream_data["stream_token"]
        print(f"[OK] 5. Stream token signé généré avec succès")

        # 5.2 Tentative de stream sans aucun token (doit être rejeté avec 401)
        res = await client.get(f"/api/videos/{video_id}/stream")
        assert res.status_code == 401
        print("[OK] 6. Protection streaming (Rejet 401 sans token) : OK")

        # 5.3 Requête normale complète (sans en-tête Range)
        res = await client.get(f"/api/videos/{video_id}/stream?token={signed_stream_token}")
        assert res.status_code == 200
        assert res.headers["Accept-Ranges"] == "bytes"
        assert int(res.headers["Content-Length"]) == dummy_size
        assert len(res.content) == dummy_size
        print(f"[OK] 7. Stream complet (HTTP 200) : {len(res.content)} octets reçus")

        # 5.4 Requête Range initiale (bytes=0-1023)
        range_headers = {"Range": "bytes=0-1023"}
        res = await client.get(
            f"/api/videos/{video_id}/stream?token={signed_stream_token}",
            headers=range_headers,
        )
        assert res.status_code == 206, f"Attendu 206, reçu: {res.status_code}"
        assert res.headers["Content-Range"] == f"bytes 0-1023/{dummy_size}"
        assert res.headers["Content-Length"] == "1024"
        assert res.content == dummy_data[0:1024]
        print("[OK] 8. Requête HTTP 206 (bytes=0-1023) : Plage exacte validée")

        # 5.5 Requête d'avance rapide (Seek forward : bytes=1048576-2097151)
        seek_headers = {"Range": "bytes=1048576-2097151"}
        res = await client.get(
            f"/api/videos/{video_id}/stream?token={signed_stream_token}",
            headers=seek_headers,
        )
        assert res.status_code == 206
        assert res.headers["Content-Range"] == f"bytes 1048576-2097151/{dummy_size}"
        assert res.headers["Content-Length"] == str(2097151 - 1048576 + 1)
        assert res.content == dummy_data[1048576:2097152]
        print("[OK] 9. Avance rapide Seek (HTTP 206) : Déplacement instantané validé")

    # Nettoyage du fichier de test
    test_cache_file.unlink(missing_ok=True)
    print("[OK] 10. Fichier temporaire de test nettoyé")

    print("=" * 60)
    print("TOUS LES TESTS DU MOTEUR DE STREAMING RANGE ONT REUSSI !")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
