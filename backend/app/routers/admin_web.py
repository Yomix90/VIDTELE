"""
Routeur pour l'interface web d'administration StreamAdmin (HTML + Jinja2 + Bootstrap 5).
"""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Episode, HomeRow, InviteCode, Movie, Season, Series, User, Video
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
    """Sert le tableau de bord StreamAdmin interactif (FR / AR)."""
    # 1. Métriques globales
    vid_stmt = select(
        func.count(Video.id),
        func.coalesce(func.sum(Video.views_count), 0),
        func.coalesce(func.sum(Video.duration_seconds), 0),
    )
    total_videos, total_views, total_duration = (await db.execute(vid_stmt)).one()

    # Compteurs spécifiques
    pub_vids_count = (await db.execute(select(func.count(Video.id)).where(Video.is_published == True))).scalar_one()
    raw_vids_count = (await db.execute(select(func.count(Video.id)).where(Video.is_published == False))).scalar_one()

    series_count = (await db.execute(select(func.count(Series.id)))).scalar_one()
    movies_count = (await db.execute(select(func.count(Movie.id)))).scalar_one()

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_users = (await db.execute(select(func.count(User.id)).where(User.is_active == True))).scalar_one()
    invites_count = (await db.execute(select(func.count(InviteCode.id)).where(InviteCode.is_used == False))).scalar_one()

    # 2. Cache et flux actifs
    cache_stats = cache_service.get_cache_stats()
    stream_stats = await stream_manager.get_active_stream_counts(db)

    stats = {
        "total_videos": total_videos,
        "published_videos": pub_vids_count,
        "raw_videos_count": raw_vids_count,
        "series_count": series_count,
        "movies_count": movies_count,
        "total_views": total_views,
        "total_duration_seconds": total_duration,
        "total_users": total_users,
        "active_users": active_users,
        "invites_count": invites_count,
        "cache": cache_stats,
        "streams": stream_stats,
    }

    # 3. Dernières séries
    recent_series = (await db.execute(select(Series).order_by(desc(Series.created_at)).limit(6))).scalars().all()

    # 4. Vidéos brutes Telegram en attente
    raw_videos = (
        await db.execute(select(Video).where(Video.is_published == False).order_by(desc(Video.telegram_date)).limit(10))
    ).scalars().all()

    # 5. Utilisateurs récents
    recent_users = (await db.execute(select(User).order_by(desc(User.created_at)).limit(8))).scalars().all()

    # 6. Admin actuel
    admin_user = (await db.execute(select(User).where(User.role == "admin").limit(1))).scalar_one_or_none()

    # 7. État Telegram
    telegram_status = await telegram_manager.get_connection_status()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "active_page": "dashboard",
            "stats": stats,
            "recent_series": recent_series,
            "raw_videos": raw_videos,
            "recent_users": recent_users,
            "current_user": admin_user,
            "telegram": telegram_status,
        },
    )


@router.get("/admin/series", response_class=HTMLResponse)
async def admin_series_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert la page de liste des séries."""
    series_list = (await db.execute(select(Series).order_by(desc(Series.created_at)))).scalars().all()
    for s in series_list:
        s_count = (await db.execute(select(func.count(Season.id)).where(Season.series_id == s.id))).scalar_one()
        setattr(s, "seasons_count", s_count)

    admin_user = (await db.execute(select(User).where(User.role == "admin").limit(1))).scalar_one_or_none()

    return templates.TemplateResponse(
        request=request,
        name="series.html",
        context={
            "active_page": "series",
            "series_list": series_list,
            "current_user": admin_user,
        },
    )


from sqlalchemy.orm import selectinload

@router.get("/admin/series/{series_id}", response_class=HTMLResponse)
async def admin_series_detail_page(
    series_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert la page détaillée d'une série avec ses saisons et épisodes."""
    stmt = (
        select(Series)
        .options(
            selectinload(Series.seasons)
            .selectinload(Season.episodes)
            .selectinload(Episode.video)
        )
        .where(Series.id == series_id)
    )
    series = (await db.execute(stmt)).scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="Série introuvable")

    # Vidéos brutes disponibles pour rattachement
    raw_videos = (
        await db.execute(select(Video).order_by(desc(Video.telegram_date)).limit(50))
    ).scalars().all()

    admin_user = (await db.execute(select(User).where(User.role == "admin").limit(1))).scalar_one_or_none()

    return templates.TemplateResponse(
        request=request,
        name="serie-detail.html",
        context={
            "active_page": "series",
            "series": series,
            "raw_videos": raw_videos,
            "current_user": admin_user,
        },
    )


@router.get("/admin/movies", response_class=HTMLResponse)
async def admin_movies_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert la page du catalogue des films."""
    movies_list = (await db.execute(select(Movie).order_by(desc(Movie.created_at)))).scalars().all()
    raw_videos = (await db.execute(select(Video).order_by(desc(Video.telegram_date)).limit(50))).scalars().all()
    admin_user = (await db.execute(select(User).where(User.role == "admin").limit(1))).scalar_one_or_none()

    return templates.TemplateResponse(
        request=request,
        name="movies.html",
        context={
            "active_page": "movies",
            "movies_list": movies_list,
            "raw_videos": raw_videos,
            "current_user": admin_user,
        },
    )


@router.get("/admin/raw-videos", response_class=HTMLResponse)
async def admin_raw_videos_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert la bibliothèque brute des vidéos Telegram."""
    raw_videos = (await db.execute(select(Video).order_by(desc(Video.telegram_date)).limit(100))).scalars().all()
    admin_user = (await db.execute(select(User).where(User.role == "admin").limit(1))).scalar_one_or_none()

    return templates.TemplateResponse(
        request=request,
        name="raw-videos.html",
        context={
            "active_page": "raw_videos",
            "raw_videos": raw_videos,
            "current_user": admin_user,
        },
    )


@router.get("/admin/telegram", response_class=HTMLResponse)
async def admin_telegram_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert la page de gestion Telegram MTProto."""
    telegram_status = await telegram_manager.get_connection_status()
    admin_user = (await db.execute(select(User).where(User.role == "admin").limit(1))).scalar_one_or_none()

    return templates.TemplateResponse(
        request=request,
        name="telegram.html",
        context={
            "active_page": "telegram",
            "telegram": telegram_status,
            "current_user": admin_user,
        },
    )


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert la gestion des comptes utilisateurs."""
    users = (await db.execute(select(User).order_by(desc(User.created_at)).limit(100))).scalars().all()
    admin_user = (await db.execute(select(User).where(User.role == "admin").limit(1))).scalar_one_or_none()

    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={
            "active_page": "users",
            "users": users,
            "current_user": admin_user,
        },
    )


@router.get("/admin/invitations", response_class=HTMLResponse)
async def admin_invitations_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert la gestion des codes d'invitation."""
    invites = (await db.execute(select(InviteCode).order_by(desc(InviteCode.created_at)).limit(100))).scalars().all()
    admin_user = (await db.execute(select(User).where(User.role == "admin").limit(1))).scalar_one_or_none()

    return templates.TemplateResponse(
        request=request,
        name="invitations.html",
        context={
            "active_page": "invitations",
            "invites": invites,
            "current_user": admin_user,
        },
    )


@router.get("/admin/home-editor", response_class=HTMLResponse)
async def admin_home_editor_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert l'éditeur de l'accueil mobile."""
    home_rows = (await db.execute(select(HomeRow).order_by(HomeRow.order_index))).scalars().all()
    admin_user = (await db.execute(select(User).where(User.role == "admin").limit(1))).scalar_one_or_none()

    return templates.TemplateResponse(
        request=request,
        name="home-editor.html",
        context={
            "active_page": "home_editor",
            "home_rows": home_rows,
            "current_user": admin_user,
        },
    )


@router.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert la page des paramètres."""
    admin_user = (await db.execute(select(User).where(User.role == "admin").limit(1))).scalar_one_or_none()

    from app.models import SystemSetting
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

    app_update = {
        "latest_version": settings_dict.get("app_latest_version", "1.0.0"),
        "min_version": settings_dict.get("app_min_version", "1.0.0"),
        "download_url": settings_dict.get("app_update_url", ""),
        "title": settings_dict.get("app_update_title", "Mise à jour disponible"),
        "release_notes": settings_dict.get("app_update_notes", ""),
        "force_update": settings_dict.get("app_update_force", "false").lower() == "true",
    }

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "active_page": "settings",
            "current_user": admin_user,
            "app_update": app_update,
        },
    )
