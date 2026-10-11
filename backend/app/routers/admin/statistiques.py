"""
Administration — Statistiques globales du tableau de bord.

Code déplacé tel quel depuis l'ancien routers/admin.py (Phase 1).
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import InviteCode, User, Video
from app.schemas import (
    AdminStatsResponse,
    CacheStats,
    StreamStats,
)
from app.security import get_current_admin
from app.services.cache_service import cache_service
from app.services.stream_manager import stream_manager

router = APIRouter()

# -------------------------------------------------------------
# 1. Statistiques Globales du Système
# -------------------------------------------------------------

@router.get("/stats", response_model=AdminStatsResponse)
async def get_system_stats(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Retourne l'ensemble des métriques d'exploitation :
    Vidéos, vues, utilisateurs actifs, quotas de streaming et espace cache disque.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    thirty_days_ago = now - timedelta(days=30)

    # Statistiques Vidéos
    vid_stmt = select(
        func.count(Video.id),
        func.coalesce(func.sum(Video.views_count), 0),
        func.coalesce(func.sum(Video.duration_seconds), 0),
    )
    total_videos, total_views, total_duration = (await db.execute(vid_stmt)).one()

    # Statistiques Utilisateurs
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_users = (
        await db.execute(select(func.count(User.id)).where(User.last_login_at >= thirty_days_ago))
    ).scalar_one()

    # Statistiques Invitations
    total_invites = (await db.execute(select(func.count(InviteCode.id)))).scalar_one()
    used_invites = (
        await db.execute(select(func.count(InviteCode.id)).where(InviteCode.is_used == True))
    ).scalar_one()
    active_invites = total_invites - used_invites

    # Statistiques Cache Disque
    cache_info = cache_service.get_cache_stats()

    # Statistiques Streaming Actif
    stream_info = await stream_manager.get_active_stream_counts(db)

    return AdminStatsResponse(
        total_videos=total_videos,
        total_views=total_views,
        total_duration_seconds=total_duration,
        total_users=total_users,
        active_users=active_users,
        total_invites=total_invites,
        active_invites=active_invites,
        used_invites=used_invites,
        cache=CacheStats(**cache_info),
        streams=StreamStats(**stream_info),
    )


