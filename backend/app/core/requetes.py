"""
Middleware ASGI de contexte de requête.

Écrit en ASGI pur (et non BaseHTTPMiddleware) pour ne pas perturber les réponses
en flux (vidéo) : aucune mise en mémoire tampon, aucune tâche supplémentaire.
"""
import logging
import re
import time
import uuid

from app.core.journalisation import masquer_secrets, request_id_var

logger = logging.getLogger("vidtele.http")

_ID_VALIDE = re.compile(r"^[A-Za-z0-9\-_.]{8,64}$")


class MiddlewareContexteRequete:
    """Attribue un request_id, l'expose dans l'en-tête X-Request-ID et journalise la requête."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Réutilise l'identifiant fourni par le client ou le proxy s'il est sain, sinon en crée un
        entetes = dict(scope.get("headers") or [])
        fourni = entetes.get(b"x-request-id", b"").decode("latin-1")
        request_id = fourni if _ID_VALIDE.match(fourni) else uuid.uuid4().hex[:16]
        jeton = request_id_var.set(request_id)

        debut = time.perf_counter()
        statut = 500

        async def envoyer(message):
            nonlocal statut
            if message["type"] == "http.response.start":
                statut = message["status"]
                message["headers"] = list(message.get("headers", [])) + [(b"x-request-id", request_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, envoyer)
        finally:
            duree_ms = round((time.perf_counter() - debut) * 1000, 1)
            chemin = scope.get("path", "")
            requete = scope.get("query_string", b"").decode("latin-1")
            if requete:
                chemin = f"{chemin}?{requete}"
            chemin = masquer_secrets(chemin)
            client = scope.get("client") or ("-", 0)
            niveau = logging.WARNING if statut >= 500 else logging.INFO
            # Le healthcheck Docker (toutes les 30 s) ne doit pas noyer les journaux
            if scope.get("path", "").startswith("/api/health") and statut < 400:
                niveau = logging.DEBUG
            logger.log(
                niveau,
                "%s %s -> %s (%s ms)",
                scope.get("method", "-"),
                chemin,
                statut,
                duree_ms,
                extra={
                    "methode": scope.get("method"),
                    "chemin": chemin,
                    "statut": statut,
                    "duree_ms": duree_ms,
                    "ip": client[0],
                },
            )
            request_id_var.reset(jeton)
