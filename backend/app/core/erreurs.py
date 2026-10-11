"""
Format d'erreur uniforme de l'API.

Toutes les erreurs /api renvoient :
    {"detail": <message ou liste>, "code": "<code_stable>", "request_id": "<id>"}

`detail` est conservé tel quel : les applications installées l'affichent directement.
`code` et `request_id` sont des AJOUTS (ignorés par les anciennes versions).
Les erreurs inattendues ne divulguent jamais le détail interne au client.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.journalisation import request_id_var

logger = logging.getLogger("vidtele.erreurs")

CODES_HTTP = {
    400: "requete_invalide",
    401: "non_authentifie",
    403: "acces_refuse",
    404: "introuvable",
    405: "methode_non_autorisee",
    409: "conflit",
    413: "trop_volumineux",
    416: "plage_invalide",
    422: "validation",
    426: "mise_a_jour_requise",
    429: "trop_de_requetes",
    500: "erreur_interne",
    502: "service_externe_indisponible",
    503: "service_indisponible",
}


def _est_api(request: Request) -> bool:
    return request.url.path.startswith("/api/")


def corps_erreur(detail, statut: int) -> dict:
    """Corps JSON d'erreur standard."""
    return {
        "detail": detail,
        "code": CODES_HTTP.get(statut, f"http_{statut}"),
        "request_id": request_id_var.get(),
    }


def installer_gestionnaires_erreurs(app: FastAPI) -> None:
    """Enregistre les gestionnaires d'erreurs uniformes sur l'application."""

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        # Les pages de l'admin web gardent le comportement standard (HTML, redirections)
        if not _est_api(request):
            return await http_exception_handler(request, exc)
        return JSONResponse(
            status_code=exc.status_code,
            content=corps_erreur(exc.detail, exc.status_code),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        if not _est_api(request):
            return await request_validation_exception_handler(request, exc)
        # Même liste `detail` que FastAPI par défaut (sans recopier les valeurs reçues)
        detail = [{k: v for k, v in err.items() if k in ("type", "loc", "msg")} for err in exc.errors()]
        return JSONResponse(status_code=422, content=corps_erreur(detail, 422))

    @app.exception_handler(Exception)
    async def _inattendue(request: Request, exc: Exception):
        logger.error("Erreur non gérée sur %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=corps_erreur("Erreur interne du serveur. Réessayez plus tard.", 500),
        )
