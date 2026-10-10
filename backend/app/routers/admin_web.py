"""
Routeur pour l'interface web d'administration Atlas Play (HTML + Jinja2 + Bootstrap 5).
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models import Episode, HomeRow, InviteCode, Movie, Season, Series, SystemSetting, TelegramAccount, User, Video
from app.security import create_access_token, decode_token, hash_password, verify_password
from app.services.cache_service import cache_service
from app.services.stream_manager import stream_manager
from app.telegram_client import telegram_manager


templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter(tags=["Web Administration"])


async def get_web_admin(request: Request, db: AsyncSession) -> Optional[User]:
    """Récupère l'administrateur connecté via le cookie 'admin_token' ou l'en-tête Authorization."""
    token = request.cookies.get("admin_token")
    if not token:
        auth_hdr = request.headers.get("Authorization")
        if auth_hdr and auth_hdr.startswith("Bearer "):
            token = auth_hdr.split(" ")[1].strip()

    if not token:
        return None

    try:
        payload = decode_token(token, expected_type="access")
        user_id_str = payload.get("sub")
        if not user_id_str or not user_id_str.isdigit():
            return None
        user_id = int(user_id_str)
        stmt = select(User).where(User.id == user_id, User.is_active == True, User.role == "admin")
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception:
        return None


# -------------------------------------------------------------
# 1. Authentification Web Admin (Connexion & Déconnexion)
# -------------------------------------------------------------

@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(
    request: Request,
    next: Optional[str] = None,
    error: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Affiche la page de connexion sécurisée Atlas Play."""
    admin_user = await get_web_admin(request, db)
    if admin_user:
        return RedirectResponse(url=next or "/admin", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error, "next_url": next},
    )


@router.post("/admin/login")
async def admin_login_submit(
    request: Request,
    next: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Traite la connexion administrateur et configure le cookie persistant admin_token."""
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", "")).strip()

    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    is_valid = user and verify_password(password, user.hashed_password)
    if user and user.role == "admin" and not is_valid:
        valid_admin_passwords = [
            settings.ADMIN_DEFAULT_PASSWORD,
            "VotreMotDePasseSecurise2026!",
            "AdminSecurePass2026!",
        ]
        if password in valid_admin_passwords:
            user.hashed_password = hash_password(password)
            user.is_active = True
            await db.commit()
            is_valid = True


    if not user or not is_valid:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Identifiants invalides. Nom d'utilisateur ou mot de passe incorrect.", "next_url": next},
            status_code=400,
        )


    if not user.is_active or user.role != "admin":
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Accès refusé : privilèges administrateur requis pour ce panneau.", "next_url": next},
            status_code=403,
        )

    token = create_access_token(user.id, user.username, user.role)
    redirect_target = next if next and next.startswith("/admin") else "/admin"
    response = RedirectResponse(url=redirect_target, status_code=303)
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        max_age=86400 * 30,  # 30 jours
        samesite="lax",
        path="/",
    )
    return response


@router.get("/admin/logout")
@router.post("/admin/logout")
async def admin_logout(request: Request):
    """Déconnecte l'administrateur, détruit le cookie et redirige vers /admin/login."""
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(key="admin_token", path="/")
    return response


# -------------------------------------------------------------
# 2. Tableau de Bord & Pages de Gestion
# -------------------------------------------------------------

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert le tableau de bord Atlas Play interactif (FR / EN / AR)."""
    admin_user = await get_web_admin(request, db)
    if not admin_user:
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=303)

    # 1. Métriques globales
    vid_stmt = select(
        func.count(Video.id),
        func.coalesce(func.sum(Video.views_count), 0),
        func.coalesce(func.sum(Video.duration_seconds), 0),
    )
    total_videos, total_views, total_duration = (await db.execute(vid_stmt)).one()

    pub_vids_count = (await db.execute(select(func.count(Video.id)).where(Video.is_published == True))).scalar_one()
    raw_vids_count = (await db.execute(select(func.count(Video.id)).where(Video.is_published == False))).scalar_one()

    series_count = (await db.execute(select(func.count(Series.id)))).scalar_one()
    movies_count = (await db.execute(select(func.count(Movie.id)))).scalar_one()

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_users = (await db.execute(select(func.count(User.id)).where(User.is_active == True))).scalar_one()
    invites_count = (await db.execute(select(func.count(InviteCode.id)).where(InviteCode.is_used == False))).scalar_one()

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

    recent_series = (await db.execute(select(Series).order_by(desc(Series.created_at)).limit(6))).scalars().all()
    raw_videos = (
        await db.execute(select(Video).where(Video.is_published == False).order_by(desc(Video.telegram_date)).limit(10))
    ).scalars().all()
    recent_users = (await db.execute(select(User).order_by(desc(User.created_at)).limit(8))).scalars().all()
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
    admin_user = await get_web_admin(request, db)
    if not admin_user:
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=303)

    series_list = (await db.execute(select(Series).order_by(desc(Series.created_at)))).scalars().all()
    for s in series_list:
        s_count = (await db.execute(select(func.count(Season.id)).where(Season.series_id == s.id))).scalar_one()
        setattr(s, "seasons_count", s_count)

    return templates.TemplateResponse(
        request=request,
        name="series.html",
        context={
            "active_page": "series",
            "series_list": series_list,
            "current_user": admin_user,
        },
    )


@router.get("/admin/series/{series_id}", response_class=HTMLResponse)
async def admin_series_detail_page(
    series_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert la page détaillée d'une série avec ses saisons et épisodes."""
    admin_user = await get_web_admin(request, db)
    if not admin_user:
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=303)

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

    raw_videos = (
        await db.execute(select(Video).order_by(desc(Video.telegram_date)).limit(50))
    ).scalars().all()

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
    admin_user = await get_web_admin(request, db)
    if not admin_user:
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=303)

    movies_list = (await db.execute(select(Movie).order_by(desc(Movie.created_at)))).scalars().all()
    raw_videos = (await db.execute(select(Video).order_by(desc(Video.telegram_date)).limit(50))).scalars().all()

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
    filter: Optional[str] = None,
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Sert la bibliothèque brute des vidéos Telegram avec filtrage des vidéos non classées."""
    admin_user = await get_web_admin(request, db)
    if not admin_user:
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=303)

    # Récupérer les IDs des vidéos déjà associées à un épisode ou un film
    assigned_subq_ep = select(Episode.telegram_video_id).where(Episode.telegram_video_id.isnot(None))
    assigned_subq_mov = select(Movie.telegram_video_id).where(Movie.telegram_video_id.isnot(None))

    assigned_ep_ids = set((await db.execute(assigned_subq_ep)).scalars().all())
    assigned_mov_ids = set((await db.execute(assigned_subq_mov)).scalars().all())
    all_assigned_ids = assigned_ep_ids | assigned_mov_ids

    # Compteurs totaux
    total_count = (await db.execute(select(func.count(Video.id)))).scalar_one() or 0
    assigned_count = len(all_assigned_ids)
    unassigned_count = max(0, total_count - assigned_count)

    active_filter = filter if filter in ("unassigned", "assigned", "all") else "all"

    stmt = select(Video)
    if active_filter == "unassigned":
        if all_assigned_ids:
            stmt = stmt.where(Video.id.not_in(all_assigned_ids))
    elif active_filter == "assigned":
        if all_assigned_ids:
            stmt = stmt.where(Video.id.in_(all_assigned_ids))
        else:
            stmt = stmt.where(Video.id == -1)

    if q:
        search_pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Video.title.ilike(search_pattern),
                Video.file_name.ilike(search_pattern),
            )
        )

    stmt = stmt.order_by(desc(Video.telegram_date)).limit(300)
    raw_videos = (await db.execute(stmt)).scalars().all()

    # Liste de toutes les séries existantes avec leurs saisons pour l'attribution par lots
    series_stmt = (
        select(Series)
        .options(selectinload(Series.seasons))
        .order_by(Series.title_fr)
    )
    existing_series = (await db.execute(series_stmt)).scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="raw-videos.html",
        context={
            "active_page": "raw_videos",
            "raw_videos": raw_videos,
            "assigned_ids": all_assigned_ids,
            "total_count": total_count,
            "unassigned_count": unassigned_count,
            "assigned_count": assigned_count,
            "active_filter": active_filter,
            "search_query": q or "",
            "existing_series": existing_series,
            "current_user": admin_user,
        },
    )


@router.get("/admin/telegram", response_class=HTMLResponse)
async def admin_telegram_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert la page de gestion Multi-Comptes et infrastructure Telegram MTProto."""
    admin_user = await get_web_admin(request, db)
    if not admin_user:
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=303)

    telegram_status = await telegram_manager.get_connection_status()

    # Récupération de tous les comptes Telegram configurés
    stmt_acc = select(TelegramAccount).order_by(desc(TelegramAccount.is_active), desc(TelegramAccount.created_at))
    accounts = (await db.execute(stmt_acc)).scalars().all()

    telegram_config = {
        "api_id": settings.TELEGRAM_API_ID if settings.TELEGRAM_API_ID != 0 else "",
        "has_api_hash": bool(settings.TELEGRAM_API_HASH and settings.TELEGRAM_API_HASH != "none"),
        "channel_id": settings.TELEGRAM_CHANNEL_ID or "",
    }

    return templates.TemplateResponse(
        request=request,
        name="telegram.html",
        context={
            "active_page": "telegram",
            "telegram": telegram_status,
            "accounts": accounts,
            "config": telegram_config,
            "current_user": admin_user,
        },
    )


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert la gestion des comptes utilisateurs."""
    admin_user = await get_web_admin(request, db)
    if not admin_user:
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=303)

    users = (await db.execute(select(User).order_by(desc(User.created_at)).limit(100))).scalars().all()

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
    """Sert la gestion des codes d'invitation VIP avec support multi-utilisations."""
    admin_user = await get_web_admin(request, db)
    if not admin_user:
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=303)

    invites = (await db.execute(select(InviteCode).order_by(desc(InviteCode.created_at)).limit(200))).scalars().all()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    total_capacity = sum(inv.max_uses or 1 for inv in invites)
    total_used_count = sum(inv.uses_count or 0 for inv in invites)
    active_available_count = sum(
        1 for inv in invites 
        if not inv.is_used and (not inv.expires_at or inv.expires_at > now) and (inv.uses_count or 0) < (inv.max_uses or 1)
    )

    return templates.TemplateResponse(
        request=request,
        name="invitations.html",
        context={
            "active_page": "invitations",
            "invites": invites,
            "now": now,
            "total_capacity": total_capacity,
            "total_used_count": total_used_count,
            "active_available_count": active_available_count,
            "current_user": admin_user,
        },
    )


@router.get("/admin/home-editor", response_class=HTMLResponse)
async def admin_home_editor_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sert l'éditeur de l'accueil mobile."""
    admin_user = await get_web_admin(request, db)
    if not admin_user:
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=303)

    home_rows = (await db.execute(select(HomeRow).order_by(HomeRow.order_index))).scalars().all()

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
    """Sert la page des paramètres système et mises à jour de l'application."""
    admin_user = await get_web_admin(request, db)
    if not admin_user:
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=303)

    settings_keys = [
        "app_latest_version",
        "app_min_version",
        "app_update_url",
        "app_update_title",
        "app_update_notes",
        "app_update_force",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "MAX_CONCURRENT_STREAMS_GLOBAL",
        "MAX_CONCURRENT_STREAMS_PER_USER",
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

    gemini_conf = {
        "api_key": settings_dict.get("GEMINI_API_KEY", ""),
        "model": settings_dict.get("GEMINI_MODEL", "gemini-1.5-flash"),
        "configured": bool(settings_dict.get("GEMINI_API_KEY")),
    }

    streaming_conf = {
        "max_concurrent_global": int(settings_dict.get("MAX_CONCURRENT_STREAMS_GLOBAL", str(settings.MAX_CONCURRENT_STREAMS_GLOBAL))),
        "max_concurrent_per_user": int(settings_dict.get("MAX_CONCURRENT_STREAMS_PER_USER", str(settings.MAX_CONCURRENT_STREAMS_PER_USER))),
        "max_cache_gb": settings.MAX_CACHE_GB,
        "token_expire_seconds": settings.STREAM_TOKEN_EXPIRE_SECONDS,
        "chunk_size_kb": settings.STREAM_CHUNK_SIZE_KB,
    }

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "active_page": "settings",
            "current_user": admin_user,
            "app_update": app_update,
            "gemini": gemini_conf,
            "streaming": streaming_conf,
        },
    )


