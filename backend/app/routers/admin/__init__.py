"""
API d'administration (/api/admin), découpée par domaine.

Toutes les routes exigent un administrateur (dépendance get_current_admin sur chaque route).
L'ordre d'inclusion reproduit l'ordre de l'ancien fichier unique ; le test
tests/test_inventaire_routes.py vérifie qu'aucune route n'est masquée par une autre.
"""
from fastapi import APIRouter

from app.routers.admin import (
    application,
    films,
    ia,
    invitations,
    medias,
    referentiel,
    series,
    statistiques,
    streaming,
    synchronisation,
    telegram,
    televersements,
    utilisateurs,
)

router = APIRouter(prefix="/api/admin", tags=["Administration"])

router.include_router(statistiques.router)
router.include_router(utilisateurs.router)
router.include_router(invitations.router)
router.include_router(synchronisation.router)
router.include_router(telegram.router)
router.include_router(medias.router)
router.include_router(series.router)
router.include_router(films.router)
router.include_router(referentiel.router)
router.include_router(application.router)
router.include_router(televersements.router)
router.include_router(ia.router)
router.include_router(streaming.router)
