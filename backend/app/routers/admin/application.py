"""
Administration — Mise à jour de l'application mobile (version minimale, APK).

Code déplacé tel quel depuis l'ancien routers/admin.py (Phase 1).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import SystemSetting, User
from app.schemas import (
    AppUpdateConfig,
    MessageResponse,
)
from app.security import get_current_admin

from app.services.version_app import invalider_cache

router = APIRouter()

# =============================================================
# 11. Gestion des Mises à Jour de l'Application Mobile (Atlas Play)
# =============================================================

@router.get("/app-update")
async def get_app_update_settings(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Récupère la configuration actuelle des mises à jour mobile."""
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

    return {
        "latest_version": settings_dict.get("app_latest_version", "1.0.0"),
        "min_version": settings_dict.get("app_min_version", "1.0.0"),
        "download_url": settings_dict.get("app_update_url", ""),
        "title": settings_dict.get("app_update_title", "Mise à jour disponible"),
        "release_notes": settings_dict.get("app_update_notes", ""),
        "force_update": settings_dict.get("app_update_force", "false").lower() == "true",
    }


@router.post("/app-update", response_model=MessageResponse)
async def update_app_update_settings(
    data: AppUpdateConfig,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enregistre la configuration de mise à jour déployée pour l'application mobile."""
    configs = {
        "app_latest_version": data.latest_version.strip(),
        "app_min_version": data.min_version.strip(),
        "app_update_url": data.download_url.strip() if data.download_url else "",
        "app_update_title": data.title.strip() if data.title else "Mise à jour disponible",
        "app_update_notes": data.release_notes.strip() if data.release_notes else "",
        "app_update_force": "true" if data.force_update else "false",
    }

    for key, val in configs.items():
        res = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = res.scalar_one_or_none()
        if setting:
            setting.value = val
        else:
            db.add(SystemSetting(key=key, value=val))

    await db.commit()
    invalider_cache()  # prise en compte immédiate par /api/app/version et le contrôle X-App-Version
    return MessageResponse(message="Configuration de mise à jour mobile enregistrée avec succès.")


