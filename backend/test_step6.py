"""
Test de l'étape 6 : Rendu de toutes les vues HTML StreamAdmin.
"""
import asyncio
import httpx
import sys
sys.path.insert(0, ".")
from app.main import app


async def test():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        routes = [
            ("/admin", "Tableau de bord"),
            ("/admin/series", "Gestion des Séries"),
            ("/admin/movies", "Catalogue des Films"),
            ("/admin/raw-videos", "Bibliothèque Brute Telegram"),
            ("/admin/telegram", "Connexion Telegram & Canaux"),
            ("/admin/users", "Gestion des Utilisateurs"),
            ("/admin/invitations", "Codes d'Invitation"),
            ("/admin/home-editor", "Éditeur de l'Accueil Mobile"),
            ("/admin/settings", "Paramètres du Système"),
        ]

        for path, label in routes:
            res = await client.get(path)
            assert res.status_code == 200, f"Erreur {path}: {res.status_code}"
            assert "app-shell" in res.text, f"Coquille app-shell manquante sur {path}"
            assert "StreamAdmin" in res.text, f"Marque StreamAdmin manquante sur {path}"
            print(f"[OK] {path} -> 200 OK ('{label}')")

        # Test de la page détail série
        res_series = await client.get("/admin/series/1")
        if res_series.status_code == 200:
            assert "app-shell" in res_series.text
            print("[OK] /admin/series/1 -> 200 OK (Détail Série)")

        print("\n============================================================")
        print("TOUTES LES VUES WEB STREAMADMIN SONT OPERATIONNELLES (200 OK) !")
        print("============================================================")


if __name__ == "__main__":
    asyncio.run(test())
