"""
Contrôle de version minimale côté serveur (middleware ASGI).

Si la requête porte l'en-tête X-App-Version (envoyé par l'app à partir de la 1.3.0) et
que cette version est inférieure à la version minimale réglée dans l'admin, toute
requête /api reçoit :
    426 {"detail": "Mise à jour requise...", "code": "mise_a_jour_requise",
         "min_version": "...", "download_url": "...", "request_id": "..."}

Sans en-tête (applications déjà installées), rien ne change : elles restent gérées
par GET /api/app/version au lancement.
"""
import json
import logging

from app.core.erreurs import corps_erreur
from app.services.version_app import construire_parametres, est_trop_ancienne, lire_reglages_bruts

logger = logging.getLogger("vidtele.version")

# Toujours accessibles, même pour une version trop ancienne
CHEMINS_EXEMPTES = ("/api/health", "/api/app/version")


class MiddlewareVersionMinimale:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        chemin = scope.get("path", "")
        if not chemin.startswith("/api/") or chemin.startswith(CHEMINS_EXEMPTES):
            await self.app(scope, receive, send)
            return

        entetes = dict(scope.get("headers") or [])
        version = entetes.get(b"x-app-version", b"").decode("latin-1").strip()
        if not version:
            await self.app(scope, receive, send)
            return

        try:
            from app.routers.application_mobile import url_apk_secours

            parametres = construire_parametres(await lire_reglages_bruts(), url_apk_secours())
        except Exception:
            # La base est indisponible : on ne bloque personne pour autant
            logger.warning("Lecture de la version minimale impossible", exc_info=True)
            await self.app(scope, receive, send)
            return

        if not est_trop_ancienne(version, parametres.minimale):
            await self.app(scope, receive, send)
            return

        corps = corps_erreur(
            f"Mise à jour requise : la version {version} n'est plus prise en charge "
            f"(minimum {parametres.minimale}).",
            426,
        )
        corps["min_version"] = parametres.minimale
        corps["download_url"] = parametres.url
        donnees = json.dumps(corps, ensure_ascii=False).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 426,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(donnees)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": donnees})
