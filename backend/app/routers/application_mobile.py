"""
Application mobile : vérification de version au lancement (mise à jour conseillée
ou obligatoire). Voir app/services/version_app.py.
"""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter

from app.services.version_app import (
    analyser_version,
    construire_parametres,
    est_trop_ancienne,
    lire_reglages_bruts,
)

router = APIRouter()

_APK_SECOURS = Path(__file__).resolve().parent.parent / "static" / "uploads" / "apk" / "atlas-play.apk"


def url_apk_secours() -> str:
    return "/static/uploads/apk/atlas-play.apk" if _APK_SECOURS.exists() else ""


@router.get("/api/app/version", tags=["Application Mobile"])
async def check_app_version(current_version: Optional[str] = None):
    """
    Consulté au lancement de l'application. Indique si une mise à jour est disponible
    (has_update) ou obligatoire (force_update : version < version minimale, ou mise à
    jour forcée pour tous depuis l'admin). Format de réponse inchangé depuis la 1.2.0.
    """
    p = construire_parametres(await lire_reglages_bruts(), url_apk_secours())
    a_jour_dispo = False
    obligatoire = p.forcer_tout_le_monde
    if current_version:
        a_jour_dispo = analyser_version(current_version) < analyser_version(p.derniere)
        obligatoire = obligatoire or est_trop_ancienne(current_version, p.minimale)

    return {
        "latest_version": p.derniere,
        "min_version": p.minimale,
        "download_url": p.url,
        "title": p.titre,
        "release_notes": p.notes,
        "force_update": obligatoire,
        "has_update": a_jour_dispo,
    }
