"""
Routeur pour les vidéos : liste, catégories, détails et miniatures.
"""
import math
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response, RedirectResponse
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Favorite, User, Video, WatchHistory, Episode, Season, Series, Movie
from app.schemas import CategoryItem, VideoListResponse, VideoResponse
from app.security import create_stream_token, decode_token, get_client_ip, get_current_active_user
from app.services.stream_manager import stream_manager
from app.services.stream_service import stream_service

router = APIRouter(prefix="/api/videos", tags=["Vidéos"])


@router.get("", response_model=VideoListResponse)
async def get_videos(
    page: int = Query(1, ge=1, description="Numéro de page"),
    limit: int = Query(20, ge=1, le=100, description="Nombre d'éléments par page"),
    q: Optional[str] = Query(None, description="Recherche textuelle dans le titre et la légende"),
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
    sort: str = Query("date_desc", pattern="^(date_desc|date_asc|views_desc|duration_desc)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère la liste paginée des vidéos avec recherche et filtrage.
    Inclut l'état de favori et la progression de lecture de l'utilisateur connecté.
    """
    query = select(Video).where(Video.is_published == True)

    # Filtrage par mot-clé (insensible à la casse)
    if q:
        search_pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                Video.title.ilike(search_pattern),
                Video.caption.ilike(search_pattern),
                Video.category.ilike(search_pattern),
            )
        )

    # Filtrage par catégorie
    if category:
        query = query.where(Video.category == category.strip())

    # Comptage du nombre total de vidéos correspondant aux critères
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total_count = total_result.scalar_one()

    # Tri
    if sort == "date_desc":
        query = query.order_by(desc(Video.telegram_date))
    elif sort == "date_asc":
        query = query.order_by(Video.telegram_date)
    elif sort == "views_desc":
        query = query.order_by(desc(Video.views_count))
    elif sort == "duration_desc":
        query = query.order_by(desc(Video.duration_seconds))

    # Pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    videos = result.scalars().all()

    # Récupérer les favoris et historiques de l'utilisateur pour ces vidéos
    video_ids = [v.id for v in videos]
    user_fav_ids = set()
    user_history_map = {}

    if video_ids:
        # Favoris
        fav_stmt = select(Favorite.video_id).where(
            Favorite.user_id == current_user.id,
            Favorite.video_id.in_(video_ids),
        )
        fav_res = await db.execute(fav_stmt)
        user_fav_ids = set(fav_res.scalars().all())

        # Historique
        hist_stmt = select(WatchHistory).where(
            WatchHistory.user_id == current_user.id,
            WatchHistory.video_id.in_(video_ids),
        )
        hist_res = await db.execute(hist_stmt)
        for h in hist_res.scalars().all():
            user_history_map[h.video_id] = (h.position_seconds, h.completed)

    # Récupérer les affiches/posters des séries et films pour les vidéos sans miniature directe
    poster_map = {}
    if video_ids:
        ep_stmt = (
            select(Episode.telegram_video_id, Episode.thumbnail_path, Series.poster_path)
            .join(Season, Episode.season_id == Season.id)
            .join(Series, Season.series_id == Series.id)
            .where(Episode.telegram_video_id.in_(video_ids))
        )
        ep_res = await db.execute(ep_stmt)
        for vid_id, ep_thumb, series_poster in ep_res.all():
            if vid_id and (ep_thumb or series_poster):
                poster_map[vid_id] = ep_thumb or series_poster

        mv_stmt = select(Movie.telegram_video_id, Movie.poster_path).where(
            Movie.telegram_video_id.in_(video_ids)
        )
        mv_res = await db.execute(mv_stmt)
        for vid_id, mv_poster in mv_res.all():
            if vid_id and mv_poster:
                poster_map[vid_id] = mv_poster

    # Construction de la réponse enrichie
    items: List[VideoResponse] = []
    for v in videos:
        pos, completed = user_history_map.get(v.id, (0.0, False))
        effective_thumb = v.thumbnail_path or poster_map.get(v.id) or f"/api/videos/{v.id}/thumbnail"
        items.append(
            VideoResponse(
                id=v.id,
                telegram_message_id=v.telegram_message_id,
                title=v.title,
                caption=v.caption,
                category=v.category,
                duration_seconds=v.duration_seconds,
                file_size_bytes=v.file_size_bytes,
                mime_type=v.mime_type,
                thumbnail_path=effective_thumb,
                file_name=v.file_name,
                views_count=v.views_count,
                telegram_date=v.telegram_date,
                is_published=v.is_published,
                media_item_id=v.media_item_id,
                season_number=v.season_number,
                episode_number=v.episode_number,
                episode_title=v.episode_title,
                is_favorite=(v.id in user_fav_ids),
                watch_progress_seconds=pos,
                is_completed=completed,
            )
        )

    total_pages = math.ceil(total_count / limit) if total_count > 0 else 1

    return VideoListResponse(
        items=items,
        total=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@router.get("/categories", response_model=List[CategoryItem])
async def get_categories(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère la liste de toutes les catégories avec le nombre de vidéos publiées par catégorie.
    """
    stmt = (
        select(Video.category, func.count(Video.id).label("count"))
        .where(Video.is_published == True)
        .group_by(Video.category)
        .order_by(desc("count"))
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        CategoryItem(name=row[0] or "Général", count=row[1])
        for row in rows
    ]


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video_detail(
    video_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère les détails complets d'une vidéo spécifique (réservé aux vidéos publiées pour les non-admins).
    """
    stmt = select(Video).where(Video.id == video_id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if not video or (not video.is_published and current_user.role != "admin"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vidéo introuvable ou non publiée",
        )

    # Favori
    fav_stmt = select(Favorite.id).where(
        Favorite.user_id == current_user.id,
        Favorite.video_id == video.id,
    )
    is_fav = (await db.execute(fav_stmt)).scalar_one_or_none() is not None

    # Historique
    hist_stmt = select(WatchHistory).where(
        WatchHistory.user_id == current_user.id,
        WatchHistory.video_id == video.id,
    )
    hist = (await db.execute(hist_stmt)).scalar_one_or_none()

    pos = hist.position_seconds if hist else 0.0
    completed = hist.completed if hist else False

    return VideoResponse(
        id=video.id,
        telegram_message_id=video.telegram_message_id,
        title=video.title,
        caption=video.caption,
        category=video.category,
        duration_seconds=video.duration_seconds,
        file_size_bytes=video.file_size_bytes,
        mime_type=video.mime_type,
        thumbnail_path=video.thumbnail_path,
        file_name=video.file_name,
        views_count=video.views_count,
        telegram_date=video.telegram_date,
        is_published=video.is_published,
        media_item_id=video.media_item_id,
        season_number=video.season_number,
        episode_number=video.episode_number,
        episode_title=video.episode_title,
        is_favorite=is_fav,
        watch_progress_seconds=pos,
        is_completed=completed,
    )


@router.get("/{video_id}/thumbnail")
async def get_video_thumbnail(video_id: int, db: AsyncSession = Depends(get_db)):
    """
    Renvoie le fichier image de la miniature avec mise en cache HTTP.
    """
    # 1. Vérifier si video_id correspond à un id de vidéo ou telegram_message_id
    stmt = select(Video).where(or_(Video.id == video_id, Video.telegram_message_id == video_id))
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="Miniature introuvable")

    # Nom de fichier sur le disque
    filename = f"thumb_{video.telegram_message_id}.jpg"
    disk_path = Path(settings.THUMBNAILS_DIR) / filename

    if not disk_path.exists():
        if video.thumbnail_path:
            clean_thumb = video.thumbnail_path.strip()
            if clean_thumb.startswith("http://") or clean_thumb.startswith("https://"):
                return RedirectResponse(url=clean_thumb)
            if clean_thumb.startswith("/static/"):
                disk_static = Path(__file__).resolve().parent.parent / clean_thumb.lstrip("/")
                if disk_static.exists():
                    return FileResponse(
                        path=disk_static,
                        headers={"Cache-Control": "public, max-age=86400"},
                    )
        # Générer un placeholder SVG simple si la miniature n'existe pas encore sur disque
        svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">
            <rect width="320" height="180" fill="#1e293b"/>
            <polygon points="135,65 195,90 135,115" fill="#38bdf8"/>
        </svg>"""
        return Response(content=svg_content, media_type="image/svg+xml")

    return FileResponse(
        path=disk_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/{video_id}/stream-token")
async def get_stream_token(
    video_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Génère un jeton signé temporaire pour le lecteur vidéo mobile.
    Permet la lecture sans avoir à configurer des en-têtes Authorization complexes dans le player.
    """
    stmt = select(Video).where(Video.id == video_id)
    video = (await db.execute(stmt)).scalar_one_or_none()
    if not video or (not video.is_published and current_user.role != "admin"):
        raise HTTPException(status_code=404, detail="Vidéo introuvable ou non publiée")

    token = create_stream_token(user_id=current_user.id, video_id=video_id)
    return {
        "video_id": video_id,
        "stream_token": token,
        "stream_url": f"/api/videos/{video_id}/stream?token={token}",
    }


@router.get("/{video_id}/stream")
async def stream_video(
    video_id: int,
    request: Request,
    token: Optional[str] = Query(None, description="Jeton de flux temporaire ou JWT d'accès"),
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint de streaming vidéo avec support complet des requêtes HTTP Range (206 Partial Content).
    Gère l'authentification par paramètre ?token= ou par en-tête Authorization: Bearer.
    """
    # 1. Vérification de l'authentification (Query param, Header Authorization ou Cookie session admin)
    raw_token = token
    if not raw_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header.replace("Bearer ", "").strip()
        elif request.cookies.get("admin_token") or request.cookies.get("access_token"):
            raw_token = request.cookies.get("admin_token") or request.cookies.get("access_token")

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton d'authentification requis pour le streaming (header, cookie ou ?token=)",
        )


    # Décodage et validation du token (supporte les tokens 'access' et 'stream')
    try:
        payload = decode_token(raw_token, expected_type="stream")
    except HTTPException:
        # Essayer avec le type 'access'
        try:
            payload = decode_token(raw_token, expected_type="access")
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Jeton de streaming invalide ou expiré",
            )

    user_id_str = payload.get("sub")
    if not user_id_str or not user_id_str.isdigit():
        raise HTTPException(status_code=401, detail="Jeton de streaming corrompu")

    user_id = int(user_id_str)
    user_stmt = select(User).where(User.id == user_id)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou compte désactivé")

    # 2. Récupération de la vidéo
    stmt = select(Video).where(Video.id == video_id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if not video or (not video.is_published and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Vidéo introuvable ou non publiée")

    # 3. Contrôle et enregistrement des quotas de flux simultanés (anti-abus)
    client_ip = get_client_ip(request)
    # On utilise un identifiant de session dérivé du token
    session_id = raw_token[-32:] if len(raw_token) >= 32 else raw_token
    await stream_manager.register_stream_access(user, video.id, session_id, client_ip, db)

    # 4. Incrémentation des vues si la lecture démarre au début (start == 0)
    range_header = request.headers.get("Range")
    if not range_header or range_header.startswith("bytes=0-"):
        video.views_count += 1
        await db.commit()

    # 5. Délégation au moteur de streaming Range 206
    return await stream_service.create_streaming_response(video, range_header)


@router.post("/{video_id}/stream/stop")
async def stop_stream(
    video_id: int,
    request: Request,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Libère immédiatement le quota de flux simultané lorsqu'un lecteur vidéo termine ou se ferme.
    """
    raw_token = token
    if not raw_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header.replace("Bearer ", "").strip()

    if raw_token:
        session_id = raw_token[-32:] if len(raw_token) >= 32 else raw_token
        await stream_manager.release_stream_session(session_id, db)

    return {"status": "released", "video_id": video_id}




@router.get("/series/latest")
async def get_latest_series_slider(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère la liste des dernières séries ajoutées pour le carousel/slider d'accueil mobile.
    """
    stmt = (
        select(Series)
        .where(Series.visibility == "published")
        .order_by(desc(Series.created_at))
        .limit(limit)
    )
    res = await db.execute(stmt)
    series_list = res.scalars().all()

    if not series_list:
        stmt2 = select(Series).order_by(desc(Series.created_at)).limit(limit)
        series_list = (await db.execute(stmt2)).scalars().all()

    out = []
    for s in series_list:
        first_ep_stmt = (
            select(Episode, Video)
            .join(Season, Episode.season_id == Season.id)
            .outerjoin(Video, Episode.telegram_video_id == Video.id)
            .where(Season.series_id == s.id)
            .order_by(Season.number, Episode.number)
            .limit(1)
        )
        ep_row = (await db.execute(first_ep_stmt)).first()
        first_video_id = ep_row[1].id if ep_row and ep_row[1] else None

        out.append({
            "id": s.id,
            "title": s.title_fr or s.title_en or s.title_ar,
            "title_fr": s.title_fr,
            "title_ar": s.title_ar,
            "title_en": s.title_en,
            "synopsis": s.synopsis_fr or s.synopsis_ar or s.synopsis_en or "",
            "poster_path": s.poster_path,
            "banner_path": s.banner_path or s.poster_path,
            "year": s.year_start,
            "rating": s.rating,
            "first_video_id": first_video_id,
        })
    return out
