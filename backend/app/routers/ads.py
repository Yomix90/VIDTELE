"""
Routeur FastAPI pour la monétisation et la configuration des annonces AdMob avec récompense.
Fournit :
1. GET /api/config/ads : configuration dynamique des quotas et statut d'exemption de l'utilisateur.
2. POST /api/analytics/ads : remontée des métriques d'impression, d'interruption et de récompense.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import SystemSetting, User
from app.schemas import AdAnalyticsEvent, AdsConfigResponse, MessageResponse
from app.security import get_optional_current_user

logger = logging.getLogger("vidtele.ads")

router = APIRouter(prefix="/api", tags=["Monétisation & Publicités"])


@router.get("/config/ads", response_model=AdsConfigResponse)
async def get_ads_configuration(
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère la configuration dynamique des annonces vidéo avec récompense.
    Désactive automatiquement les annonces si l'utilisateur connecté est Administrateur
    ou bénéficie du statut 'ads_free: True'.
    """
    # 1. Vérification de l'exemption utilisateur
    is_exempt = False
    if current_user:
        is_exempt = current_user.role in ("admin", "super_admin") or getattr(current_user, "ads_free", False)

    # 2. Lecture des réglages dynamiques potentiels depuis la table SystemSetting
    settings_keys = [
        "ads_enabled",
        "ads_min_videos_per_cycle",
        "ads_max_videos_per_cycle",
        "ads_watch_completion_threshold",
    ]
    stmt = select(SystemSetting).where(SystemSetting.key.in_(settings_keys))
    res = await db.execute(stmt)
    db_settings = {s.key: s.value for s in res.scalars().all()}

    global_enabled = db_settings.get("ads_enabled", "true").lower() == "true"
    min_videos = int(db_settings.get("ads_min_videos_per_cycle", "4"))
    max_videos = int(db_settings.get("ads_max_videos_per_cycle", "5"))
    threshold = float(db_settings.get("ads_watch_completion_threshold", "0.70"))

    # Si l'utilisateur est exempté, enabled = False pour son flux
    user_enabled = global_enabled and not is_exempt

    return AdsConfigResponse(
        enabled=user_enabled,
        min_videos_per_cycle=min_videos,
        max_videos_per_cycle=max_videos,
        watch_completion_threshold=threshold,
        reward_amount=1,
        fallback_bypass_enabled=True,
    )


@router.post("/analytics/ads", response_model=MessageResponse)
async def record_ad_analytics(
    event: AdAnalyticsEvent,
    request: Request,
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Enregistre les événements de télémétrie publicitaire (affichages, récompenses, refus, échecs).
    Permet le monitoring de l'inventaire publicitaire sans ralentir l'expérience utilisateur.
    """
    user_id = current_user.id if current_user else "anonymous"
    username = current_user.username if current_user else "anonymous"

    logger.info(
        f"[AdMob Analytics] Event='{event.event_type}' | User={username} (ID: {user_id}) | "
        f"VideoID={event.video_id} | WatchedCount={event.cycle_watched_count} | "
        f"Error='{event.error_message or 'None'}'"
    )

    return MessageResponse(
        message=f"Événement publicitaire '{event.event_type}' enregistré avec succès"
    )
