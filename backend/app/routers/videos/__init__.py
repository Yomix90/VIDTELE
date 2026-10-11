"""
API vidéo publique (/api/videos), découpée en deux domaines :
- catalogue : ce que l'application affiche (accueil, feed, séries, top) ;
- lecture   : accès au flux vidéo (jetons, streaming Range, miniatures).

Les fonctions du catalogue sont réexportées pour les alias racine (/api/home, /api/feed...).
"""
from fastapi import APIRouter

from app.routers.videos import catalogue, lecture
from app.routers.videos.catalogue import (  # noqa: F401  (réexport pour les alias)
    get_home_content,
    get_public_series_detail,
    get_top_series,
    get_vertical_feed,
    toggle_series_favorite,
)

router = APIRouter()
router.include_router(catalogue.router)
router.include_router(lecture.router)
