"""
Routeur pour l'interface web d'administration (HTML + Bootstrap 5 + Jinja2).
"""
from pathlib import Path
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import InviteCode, MediaItem, User, Video
from app.services.cache_service import cache_service
from app.services.stream_manager import stream_manager
from app.telegram_client import telegram_manager


templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter(tags=["Web Administration"])


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Sert le tableau de bord web d'administration interactif (FR / AR).
    """
    # 1. Récupération des statistiques
    vid_stmt = select(
        func.count(Video.id),
        func.coalesce(func.sum(Video.views_count), 0),
        func.coalesce(func.sum(Video.duration_seconds), 0),
    )
    total_videos, total_views, total_duration = (await db.execute(vid_stmt)).one()

    # Nombre de vidéos publiées vs en attente
    pub_vids_count = (await db.execute(select(func.count(Video.id)).where(Video.is_published == True))).scalar_one()
    raw_vids_count = (await db.execute(select(func.count(Video.id)).where(Video.media_item_id == None))).scalar_one()

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_users = (await db.execute(select(func.count(User.id)).where(User.is_active == True))).scalar_one()

    # 2. Cache et flux actifs
    cache_stats = cache_service.get_cache_stats()
    stream_stats = await stream_manager.get_active_stream_counts(db)

    # 3. Liste des Films & Séries (Catalogue)
    media_stmt = select(MediaItem).order_by(desc(MediaItem.created_at))
    media_items_res = await db.execute(media_stmt)
    media_items = list(media_items_res.scalars().all())

    # Vidéos associées groupées par media_item_id
    assigned_vids_stmt = select(Video).where(Video.media_item_id != None).order_by(Video.season_number, Video.episode_number, Video.id)
    assigned_vids = (await db.execute(assigned_vids_stmt)).scalars().all()
    vids_by_media = {}
    for v in assigned_vids:
        vids_by_media.setdefault(v.media_item_id, []).append(v)

    for item in media_items:
        setattr(item, "attached_videos", vids_by_media.get(item.id, []))

    # 4. Vidéos brutes Telegram (en attente d'organisation)
    raw_stmt = select(Video).where(Video.media_item_id == None).order_by(desc(Video.telegram_date)).limit(100)
    raw_videos = (await db.execute(raw_stmt)).scalars().all()

    stats = {
        "total_videos": total_videos,
        "published_videos": pub_vids_count,
        "raw_videos_count": raw_vids_count,
        "total_media_items": len(media_items),
        "total_views": total_views,
        "total_duration_seconds": total_duration,
        "total_users": total_users,
        "active_users": active_users,
        "cache": cache_stats,
        "streams": stream_stats,
    }

    # 5. Liste des utilisateurs récents
    users_stmt = select(User).order_by(desc(User.created_at)).limit(50)
    users = (await db.execute(users_stmt)).scalars().all()

    # 6. Liste des invitations
    invites_stmt = select(InviteCode).order_by(desc(InviteCode.created_at)).limit(50)
    invites = (await db.execute(invites_stmt)).scalars().all()

    # Administrateur actuel par défaut (ou premier admin)
    admin_stmt = select(User).where(User.role == "admin").limit(1)
    current_admin = (await db.execute(admin_stmt)).scalar_one_or_none()

    # 7. État Telegram MTProto
    telegram_status = await telegram_manager.get_connection_status()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "stats": stats,
            "media_items": media_items,
            "raw_videos": raw_videos,
            "users": users,
            "invites": invites,
            "current_user": current_admin or (users[0] if users else None),
            "telegram": telegram_status,
        },
    )

