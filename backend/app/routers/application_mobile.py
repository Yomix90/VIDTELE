"""
Application mobile : vérification de version au lancement (mise à jour conseillée
ou obligatoire). Code déplacé tel quel depuis main.py (Phase 1).
"""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import SystemSetting

router = APIRouter()


@router.get("/api/app/version", tags=["Application Mobile"])
async def check_app_version(
    current_version: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint public consulté au lancement de l'application mobile Atlas Play.
    Vérifie si une mise à jour est disponible ou obligatoire.
    """
    def parse_semver(v: str) -> tuple:
        parts = []
        for x in str(v).strip().split("."):
            try:
                parts.append(int(x))
            except ValueError:
                parts.append(0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])

    # Récupérer les paramètres système de mise à jour
    settings_keys = [
        "app_latest_version",
        "app_min_version",
        "app_update_url",
        "app_update_title",
        "app_update_notes",
        "app_update_force",
    ]
    res = await db.execute(select(SystemSetting).where(SystemSetting.key.in_(settings_keys)))
    settings_dict = {row.key: row.value for row in res.scalars().all()}

    apk_fallback = Path(__file__).resolve().parent.parent / "static" / "uploads" / "apk" / "atlas-play.apk"
    fallback_url = "/static/uploads/apk/atlas-play.apk" if apk_fallback.exists() else ""

    latest_ver = settings_dict.get("app_latest_version", "1.2.0")
    min_ver = settings_dict.get("app_min_version", "1.0.0")
    download_url = settings_dict.get("app_update_url") or fallback_url
    title = settings_dict.get("app_update_title", "Nouvelle version Atlas Play disponible")
    notes = settings_dict.get("app_update_notes", "Améliorations des posters, zapping TikTok, enchaînement automatique des épisodes et veille d'écran.")
    force_update = settings_dict.get("app_update_force", "false").lower() == "true"

    has_update = False
    is_forced = force_update

    if current_version:
        try:
            cur_v = parse_semver(current_version)
            lat_v = parse_semver(latest_ver)
            min_v = parse_semver(min_ver)
            has_update = cur_v < lat_v
            if cur_v < min_v:
                is_forced = True
        except Exception:
            has_update = current_version != latest_ver

    return {
        "latest_version": latest_ver,
        "min_version": min_ver,
        "download_url": download_url,
        "title": title,
        "release_notes": notes,
        "force_update": is_forced,
        "has_update": has_update,
    }
