"""
Script de test complet pour l'authentification VidTele (Étape 2).
"""
import asyncio
import httpx
from app.main import app, bootstrap_admin_and_invites
from app.database import init_db


async def run_tests():
    print("=" * 60)
    print("DEMARRAGE DU TEST D'AUTHENTIFICATION VIDTELE")
    print("=" * 60)

    # Initialisation de la base et amorçage pour le test
    await init_db()
    await bootstrap_admin_and_invites()

    # Nettoyage des données de test précédentes si elles existent
    from app.database import AsyncSessionLocal
    from app.models import User, InviteCode
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        old_u = (await db.execute(select(User).where(User.username == "youssef"))).scalar_one_or_none()
        if old_u:
            await db.delete(old_u)
        inv = (await db.execute(select(InviteCode).where(InviteCode.code == "BIENVENUE-2026"))).scalar_one_or_none()
        if inv:
            inv.is_used = False
            inv.used_by_id = None
        await db.commit()

    # Utilisation du transport ASGI httpx pour tester directement FastAPI sans port réseau
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Test du health check
        res = await client.get("/api/health")
        assert res.status_code == 200, f"Erreur health: {res.text}"
        print("[OK] 1. Endpoint /api/health operationnel")

        # 2. Test de connexion de l'administrateur par defaut
        login_data = {"username": "admin", "password": "AdminSecurePass2026!"}
        res = await client.post("/api/auth/login", json=login_data)
        assert res.status_code == 200, f"Erreur login admin: {res.text}"
        tokens = res.json()
        admin_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        print(f"[OK] 2. Connexion admin reussie (Token JWT recu, role={tokens['role']})")

        # 3. Test de recuperation du profil (/api/auth/me) avec le token Bearer
        headers = {"Authorization": f"Bearer {admin_token}"}
        res = await client.get("/api/auth/me", headers=headers)
        assert res.status_code == 200, f"Erreur /api/auth/me: {res.text}"
        profile = res.json()
        assert profile["username"] == "admin"
        assert profile["role"] == "admin"
        print(f"[OK] 3. Profil /api/auth/me valide pour l'utilisateur '{profile['username']}'")

        # 4. Test d'acces non autorise sans token
        res = await client.get("/api/auth/me")
        assert res.status_code == 401
        print("[OK] 4. Rejet 401 Unauthorized sans token : OK")

        # 5. Inscription d'un nouvel utilisateur avec le code d'invitation initial BIENVENUE-2026
        reg_data = {
            "username": "youssef",
            "password": "PasswordUser2026!",
            "invite_code": "BIENVENUE-2026",
        }
        res = await client.post("/api/auth/register", json=reg_data)
        assert res.status_code == 201, f"Erreur inscription: {res.text}"
        user_tokens = res.json()
        assert user_tokens["username"] == "youssef"
        assert user_tokens["role"] == "user"
        print("[OK] 5. Inscription avec code d'invitation 'BIENVENUE-2026' : Succes")

        # 6. Tentative de reutilisation du meme code (doit echouer)
        reg_duplicate = {
            "username": "autre_user",
            "password": "PasswordUser2026!",
            "invite_code": "BIENVENUE-2026",
        }
        res = await client.post("/api/auth/register", json=reg_duplicate)
        assert res.status_code == 400
        print("[OK] 6. Rejet de code d'invitation deja utilise (Code 400) : OK")

        # 7. Tentative avec un code d'invitation inexistant
        reg_fake = {
            "username": "autre_user",
            "password": "PasswordUser2026!",
            "invite_code": "CODE-INEXISTANT",
        }
        res = await client.post("/api/auth/register", json=reg_fake)
        assert res.status_code == 400
        print("[OK] 7. Rejet de faux code d'invitation : OK")

        # 8. Connexion avec le nouvel utilisateur cree
        res = await client.post("/api/auth/login", json={"username": "youssef", "password": "PasswordUser2026!"})
        assert res.status_code == 200
        print("[OK] 8. Connexion du nouvel utilisateur 'youssef' : Succes")

        # 9. Test de rafraichissement de jeton
        res = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert res.status_code == 200
        refreshed = res.json()
        assert "access_token" in refreshed
        print("[OK] 9. Rafraichissement de jeton /api/auth/refresh : Succes")

        # 10. Test anti brute-force : 5 mauvais mots de passe
        print("10. Test de limitation des tentatives de connexion (anti brute-force)...")
        for i in range(5):
            res = await client.post("/api/auth/login", json={"username": "admin", "password": "mauvais_mot_de_passe"})
            assert res.status_code == 401

        # La 6eme tentative doit declencher une erreur 429 Too Many Requests
        res = await client.post("/api/auth/login", json={"username": "admin", "password": "mauvais_mot_de_passe"})
        assert res.status_code == 429, f"Attendu 429, recu: {res.status_code}"
        print("[OK] 10. Protection Anti Brute-Force active (Code 429 recu apres echecs repetes)")

    print("=" * 60)
    print("TOUS LES TESTS DE L'ETAPE 2 ONT REUSSI AVEC SUCCES !")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
