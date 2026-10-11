"""
Vidéos — Catalogue mobile : liste, catégories, séries, top, accueil, feed vertical, favoris de série.

Code déplacé tel quel depuis l'ancien routers/videos.py (Phase 1).
"""
import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Favorite, User, Video, WatchHistory, Episode, Season, Series, Movie
from app.schemas import (
    CategoryItem,
    FeedItemResponse,
    FeedResponse,
    HomeScreenResponse,
    TopSeriesItem,
    VideoListResponse,
    VideoResponse,
)
from app.security import (
    get_current_active_user,
)


router = APIRouter(prefix="/api/videos", tags=["Vidéos"])



@router.get("", response_model=VideoListResponse)
async def get_videos(
    page: int = Query(1, ge=1, description="Numéro de page"),
    limit: int = Query(20, ge=1, le=100, description="Nombre d'éléments par page"),
    q: Optional[str] = Query(None, description="Recherche textuelle dans le titre et la légende"),
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
    exclude_episodes: bool = Query(True, description="Exclure les épisodes de séries pour afficher seulement les films et vidéos autonomes"),
    sort: str = Query("date_desc", pattern="^(date_desc|date_asc|views_desc|duration_desc)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère la liste paginée des vidéos avec recherche et filtrage.
    Inclut l'état de favori et la progression de lecture de l'utilisateur connecté.
    """
    query = select(Video).where(Video.is_published == True)

    # Exclure les épisodes rattachés à des séries pour ne pas afficher chaque épisode séparément
    if exclude_episodes and not q:
        ep_subq = select(Episode.telegram_video_id).where(Episode.telegram_video_id.isnot(None))
        query = query.where(Video.id.not_in(ep_subq))

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


@router.get("/series")
async def list_public_series(
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    q: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retourne la liste des séries publiées pour le catalogue mobile (sans afficher les épisodes séparément).
    """
    stmt = select(Series).where(Series.visibility == "published")
    if q:
        search_pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Series.title_fr.ilike(search_pattern),
                Series.title_ar.ilike(search_pattern),
                Series.title_en.ilike(search_pattern),
                Series.synopsis_fr.ilike(search_pattern),
            )
        )
    stmt = stmt.order_by(desc(Series.created_at)).offset((page - 1) * limit).limit(limit)
    series_list = (await db.execute(stmt)).scalars().all()

    out = []
    for s in series_list:
        seasons = (await db.execute(select(Season).where(Season.series_id == s.id))).scalars().all()
        season_ids = [sn.id for sn in seasons]
        episodes_count = 0
        if season_ids:
            episodes_count = (await db.execute(
                select(func.count(Episode.id)).where(Episode.season_id.in_(season_ids))
            )).scalar_one() or 0

        out.append({
            "id": s.id,
            "slug": s.slug,
            "title_fr": s.title_fr,
            "title_ar": s.title_ar,
            "title_en": s.title_en,
            "synopsis_fr": s.synopsis_fr,
            "synopsis_ar": s.synopsis_ar,
            "synopsis_en": s.synopsis_en,
            "year_start": s.year_start,
            "rating": s.rating,
            "status": s.status,
            "poster_path": s.poster_path,
            "banner_path": s.banner_path or s.poster_path,
            "seasons_count": len(seasons),
            "episodes_count": episodes_count,
            "created_at": s.created_at,
        })
    return out


async def enrich_videos_list(videos: List[Video], user_id: int, db: AsyncSession) -> List[VideoResponse]:
    """Enrichit une liste de vidéos avec favoris, historique et posters associés."""
    if not videos:
        return []
    video_ids = [v.id for v in videos]

    # Favoris
    fav_res = await db.execute(
        select(Favorite.video_id).where(
            Favorite.user_id == user_id,
            Favorite.video_id.in_(video_ids),
        )
    )
    user_fav_ids = set(fav_res.scalars().all())

    # Historique de visionnage
    user_history_map = {}
    hist_res = await db.execute(
        select(WatchHistory).where(
            WatchHistory.user_id == user_id,
            WatchHistory.video_id.in_(video_ids),
        )
    )
    for h in hist_res.scalars().all():
        user_history_map[h.video_id] = (h.position_seconds, h.completed)

    # Récupérer les affiches des séries et films
    poster_map = {}
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

    out: List[VideoResponse] = []
    for v in videos:
        pos, completed = user_history_map.get(v.id, (0.0, False))
        effective_thumb = v.thumbnail_path or poster_map.get(v.id) or f"/api/videos/{v.id}/thumbnail"
        out.append(
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
    return out


async def compute_top_series(
    period: str,
    limit: int,
    db: AsyncSession,
) -> List[dict]:
    """Calcule le classement des séries les plus regardées sur une période donnée (ex: 7d)."""
    cutoff = None
    if period == "7d":
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    elif period == "30d":
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # 1. Compte des lectures par série via WatchHistory et Episode
    wh_stmt = (
        select(Season.series_id, func.count(WatchHistory.id).label("watch_count"))
        .join(Episode, Episode.telegram_video_id == WatchHistory.video_id)
        .join(Season, Season.id == Episode.season_id)
        .join(Series, Series.id == Season.series_id)
        .where(Series.visibility == "published")
    )
    if cutoff:
        wh_stmt = wh_stmt.where(WatchHistory.last_watched_at >= cutoff)
    wh_stmt = wh_stmt.group_by(Season.series_id).order_by(desc("watch_count")).limit(limit)

    wh_rows = (await db.execute(wh_stmt)).all()
    top_series_ids = [row[0] for row in wh_rows if row[0] is not None]
    views_map = {row[0]: row[1] for row in wh_rows if row[0] is not None}

    # 2. Compléter si nécessaire avec les séries publiées les mieux notées / récentes
    if len(top_series_ids) < limit:
        needed = limit - len(top_series_ids)
        suppl_stmt = select(Series.id).where(
            Series.visibility == "published",
            Series.id.not_in(top_series_ids) if top_series_ids else True,
        ).order_by(desc(Series.rating), desc(Series.created_at)).limit(needed)
        suppl_res = (await db.execute(suppl_stmt)).scalars().all()
        top_series_ids.extend(suppl_res)

    if not top_series_ids:
        fallback_stmt = select(Series.id).order_by(desc(Series.created_at)).limit(limit)
        top_series_ids = (await db.execute(fallback_stmt)).scalars().all()

    # 3. Charger les séries dans l'ordre du classement
    out = []
    for rank, sid in enumerate(top_series_ids, start=1):
        s = (await db.execute(select(Series).where(Series.id == sid))).scalar_one_or_none()
        if not s:
            continue

        seasons = (await db.execute(select(Season).where(Season.series_id == s.id))).scalars().all()
        season_ids = [sn.id for sn in seasons]
        ep_count = 0
        if season_ids:
            ep_count = (await db.execute(
                select(func.count(Episode.id)).where(Episode.season_id.in_(season_ids))
            )).scalar_one() or 0

        first_ep_stmt = (
            select(Episode, Video)
            .join(Season, Episode.season_id == Season.id)
            .outerjoin(Video, Episode.telegram_video_id == Video.id)
            .where(Season.series_id == s.id)
            .order_by(Season.number, Episode.number)
            .limit(1)
        )
        ep_row = (await db.execute(first_ep_stmt)).first()
        first_vid = ep_row[1].id if ep_row and ep_row[1] else None

        out.append({
            "id": s.id,
            "rank": rank,
            "title": s.title_fr or s.title_en or s.title_ar,
            "title_fr": s.title_fr,
            "title_ar": s.title_ar,
            "title_en": s.title_en,
            "synopsis": s.synopsis_fr or s.synopsis_ar or s.synopsis_en or "",
            "poster_path": s.poster_path,
            "banner_path": s.banner_path or s.poster_path,
            "year": s.year_start,
            "rating": s.rating,
            "seasons_count": len(seasons),
            "episodes_count": ep_count,
            "views_last_7d": views_map.get(s.id, 0),
            "first_video_id": first_vid,
        })

    return out


@router.get("/series/top", response_model=List[TopSeriesItem])
async def get_top_series(
    period: str = Query("7d", description="Période : 7d, 30d, all"),
    limit: int = Query(5, ge=1, le=20, description="Nombre max de séries"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Classement Top 5 des séries par lectures des 7 derniers jours."""
    return await compute_top_series(period=period, limit=limit, db=db)


@router.get("/home", response_model=HomeScreenResponse)
async def get_home_content(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Fournit l'ensemble des sections de la page d'accueil :
    - hero (slider des séries en vedette)
    - top5 (Top 5 des séries par nombre de lectures sur 7 jours)
    - continue_watching (reprise de lecture de l'utilisateur)
    - new / new_releases (derniers contenus publiés)
    - trending (vidéos les plus populaires)
    - genres (catégories avec leurs vidéos)
    """
    # 1. Hero
    hero_stmt = (
        select(Series)
        .where(Series.visibility == "published")
        .order_by(desc(Series.is_featured), desc(Series.created_at))
        .limit(10)
    )
    hero_series = (await db.execute(hero_stmt)).scalars().all()
    if not hero_series:
        hero_stmt2 = select(Series).order_by(desc(Series.created_at)).limit(10)
        hero_series = (await db.execute(hero_stmt2)).scalars().all()

    hero_items = []
    for s in hero_series:
        seasons = (await db.execute(select(Season.id).where(Season.series_id == s.id))).scalars().all()
        ep_count = 0
        if seasons:
            ep_count = (await db.execute(select(func.count(Episode.id)).where(Episode.season_id.in_(seasons)))).scalar_one() or 0

        first_ep_stmt = (
            select(Episode, Video)
            .join(Season, Episode.season_id == Season.id)
            .outerjoin(Video, Episode.telegram_video_id == Video.id)
            .where(Season.series_id == s.id)
            .order_by(Season.number, Episode.number)
            .limit(1)
        )
        ep_row = (await db.execute(first_ep_stmt)).first()
        first_vid = ep_row[1].id if ep_row and ep_row[1] else None

        hero_items.append({
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
            "category": "Micro-série" if ep_count > 0 else "Série",
            "episodes_count": ep_count,
            "first_video_id": first_vid,
        })

    # 2. Top 5
    top5_series = await compute_top_series(period="7d", limit=5, db=db)

    # 3. Continuer la lecture
    cw_stmt = (
        select(Video)
        .join(WatchHistory, WatchHistory.video_id == Video.id)
        .where(
            WatchHistory.user_id == current_user.id,
            WatchHistory.position_seconds > 0,
            WatchHistory.completed == False,
            Video.is_published == True,
        )
        .order_by(desc(WatchHistory.last_watched_at))
        .limit(15)
    )
    cw_videos = (await db.execute(cw_stmt)).scalars().all()
    continue_watching = await enrich_videos_list(cw_videos, current_user.id, db)

    # 4. Nouveautés
    new_stmt = (
        select(Video)
        .where(Video.is_published == True)
        .order_by(desc(Video.telegram_date), desc(Video.id))
        .limit(15)
    )
    new_videos = (await db.execute(new_stmt)).scalars().all()
    new_releases = await enrich_videos_list(new_videos, current_user.id, db)

    # 5. Tendances
    trending_stmt = (
        select(Video)
        .where(Video.is_published == True)
        .order_by(desc(Video.views_count), desc(Video.id))
        .limit(15)
    )
    trending_videos = (await db.execute(trending_stmt)).scalars().all()
    trending = await enrich_videos_list(trending_videos, current_user.id, db)

    # 6. Catégories / Genres
    cat_stmt = (
        select(Video.category, func.count(Video.id).label("count"))
        .where(Video.is_published == True)
        .group_by(Video.category)
        .order_by(desc("count"))
        .limit(8)
    )
    cat_rows = (await db.execute(cat_stmt)).all()

    genres = []
    for cat_name, cat_count in cat_rows:
        vids_stmt = (
            select(Video)
            .where(Video.is_published == True, Video.category == cat_name)
            .order_by(desc(Video.views_count), desc(Video.id))
            .limit(10)
        )
        cat_vids = (await db.execute(vids_stmt)).scalars().all()
        enriched_cat_vids = await enrich_videos_list(cat_vids, current_user.id, db)
        if enriched_cat_vids:
            genres.append({
                "name": cat_name,
                "count": cat_count,
                "items": enriched_cat_vids,
            })

    return {
        "hero": hero_items,
        "top5": top5_series,
        "continue_watching": continue_watching,
        "new": new_releases,
        "new_releases": new_releases,
        "trending": trending,
        "genres": genres,
    }


@router.get("/feed", response_model=FeedResponse)
async def get_vertical_feed(
    cursor: Optional[int] = Query(None, description="Curseur ID de pagination (Video.id)"),
    limit: int = Query(15, ge=1, le=50, description="Nombre de vidéos par page"),
    series_id: Optional[int] = Query(None, description="Filtrer pour binger une série spécifique"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Flux vertical plein écran optimisé pour le swipe vidéo façon TikTok / Reels.
    Supporte la pagination par curseur, l'enchaînement automatique (binge),
    et les épisodes avec miniatures et progression de reprise.
    """
    if series_id:
        # Mode Binge d'une série spécifique : ordre chronologique strict (S1E1, S1E2...)
        stmt = (
            select(Video, Episode, Season, Series)
            .join(Episode, Episode.telegram_video_id == Video.id)
            .join(Season, Episode.season_id == Season.id)
            .join(Series, Season.series_id == Series.id)
            .where(Series.id == series_id, Video.is_published == True)
        )
        if cursor:
            stmt = stmt.where(Video.id > cursor)
        stmt = stmt.order_by(Season.number.asc(), Episode.number.asc(), Video.id.asc()).limit(limit + 1)
    else:
        # Flux général : vidéos et épisodes récents pour la découverte
        stmt = (
            select(Video, Episode, Season, Series)
            .outerjoin(Episode, Episode.telegram_video_id == Video.id)
            .outerjoin(Season, Episode.season_id == Season.id)
            .outerjoin(Series, Season.series_id == Series.id)
            .where(Video.is_published == True)
        )
        if cursor:
            stmt = stmt.where(Video.id < cursor)
        stmt = stmt.order_by(desc(Video.id)).limit(limit + 1)

    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    effective_rows = rows[:limit] if has_more else rows
    next_cursor = effective_rows[-1][0].id if (has_more and effective_rows) else None

    video_ids = [r[0].id for r in effective_rows]

    # Favoris utilisateur
    user_fav_ids = set()
    if video_ids:
        fav_res = await db.execute(
            select(Favorite.video_id).where(
                Favorite.user_id == current_user.id,
                Favorite.video_id.in_(video_ids),
            )
        )
        user_fav_ids = set(fav_res.scalars().all())

    # Historique de reprise utilisateur
    user_history_map = {}
    if video_ids:
        hist_res = await db.execute(
            select(WatchHistory).where(
                WatchHistory.user_id == current_user.id,
                WatchHistory.video_id.in_(video_ids),
            )
        )
        for h in hist_res.scalars().all():
            user_history_map[h.video_id] = (h.position_seconds, h.completed)

    feed_items = []
    for v, ep, season, series in effective_rows:
        pos, completed = user_history_map.get(v.id, (0.0, False))

        # Trouver l'épisode suivant pour le mode binge
        next_vid_id = None
        if ep and season:
            # Épisode suivant dans la même saison
            next_ep_stmt = (
                select(Episode.telegram_video_id)
                .where(
                    Episode.season_id == season.id,
                    Episode.number == ep.number + 1,
                    Episode.telegram_video_id.isnot(None),
                )
                .limit(1)
            )
            next_vid_id = (await db.execute(next_ep_stmt)).scalar_one_or_none()

            # Si fin de saison, premier épisode de la saison suivante
            if not next_vid_id and series:
                next_season_stmt = (
                    select(Season.id)
                    .where(Season.series_id == series.id, Season.number == season.number + 1)
                    .limit(1)
                )
                next_season_id = (await db.execute(next_season_stmt)).scalar_one_or_none()
                if next_season_id:
                    first_ep_next_season = (
                        select(Episode.telegram_video_id)
                        .where(
                            Episode.season_id == next_season_id,
                            Episode.number == 1,
                            Episode.telegram_video_id.isnot(None),
                        )
                        .limit(1)
                    )
                    next_vid_id = (await db.execute(first_ep_next_season)).scalar_one_or_none()

        effective_thumb = (
            v.thumbnail_path
            or (ep.thumbnail_path if ep else None)
            or (series.poster_path if series else None)
            or f"/api/videos/{v.id}/thumbnail"
        )

        effective_title = (
            ep.title_fr
            if (ep and ep.title_fr)
            else (f"{series.title_fr} - S{season.number:02d}E{ep.number:02d}" if (series and ep and season) else v.title)
        )

        feed_items.append(
            FeedItemResponse(
                id=v.id,
                telegram_message_id=v.telegram_message_id,
                title=effective_title,
                series_id=series.id if series else None,
                series_title=series.title_fr if series else None,
                season_number=season.number if season else v.season_number or 1,
                episode_number=ep.number if ep else v.episode_number or 1,
                episode_title=ep.title_fr if ep else v.episode_title,
                caption=ep.synopsis_fr if (ep and ep.synopsis_fr) else v.caption,
                category=series.title_fr if series else v.category,
                duration_seconds=v.duration_seconds,
                file_size_bytes=v.file_size_bytes,
                mime_type=v.mime_type,
                thumbnail_path=effective_thumb,
                views_count=v.views_count,
                is_favorite=(v.id in user_fav_ids),
                watch_progress_seconds=pos,
                is_completed=completed,
                stream_url=f"/api/videos/{v.id}/stream",
                next_episode_video_id=next_vid_id,
            )
        )

    return FeedResponse(
        items=feed_items,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/series/{series_id}")
async def get_public_series_detail(
    series_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère le détail complet d'une série avec sa table des saisons et épisodes
    strictement ordonnés par numéro d'épisode croissant (E01, E02...) et progression utilisateur.
    """
    series = (await db.execute(select(Series).where(Series.id == series_id))).scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="Série introuvable.")

    seasons = (await db.execute(
        select(Season)
        .where(Season.series_id == series.id)
        .order_by(Season.number.asc(), Season.order_index.asc())
    )).scalars().all()

    season_ids = [s.id for s in seasons]
    episodes = []
    if season_ids:
        episodes = (await db.execute(
            select(Episode)
            .where(Episode.season_id.in_(season_ids))
            .order_by(Episode.number.asc(), Episode.order_index.asc())
        )).scalars().all()

    video_ids = [ep.telegram_video_id for ep in episodes if ep.telegram_video_id]
    user_history_map = {}
    if video_ids:
        hist_stmt = select(WatchHistory).where(
            WatchHistory.user_id == current_user.id,
            WatchHistory.video_id.in_(video_ids),
        )
        for h in (await db.execute(hist_stmt)).scalars().all():
            user_history_map[h.video_id] = (h.position_seconds, h.completed, h.last_watched_at)

    video_map = {}
    if video_ids:
        v_res = await db.execute(select(Video).where(Video.id.in_(video_ids)))
        for v in v_res.scalars().all():
            video_map[v.id] = v

    seasons_out = []
    last_watched_ep = None
    latest_watched_time = None

    for s in seasons:
        s_eps = [ep for ep in episodes if ep.season_id == s.id]
        # Ordre croissant absolu par numéro d'épisode
        s_eps.sort(key=lambda x: (x.number, x.order_index))

        eps_out = []
        for ep in s_eps:
            vid = video_map.get(ep.telegram_video_id) if ep.telegram_video_id else None
            pos, completed, last_time = user_history_map.get(ep.telegram_video_id, (0.0, False, None))

            if last_time and (latest_watched_time is None or last_time > latest_watched_time):
                latest_watched_time = last_time
                last_watched_ep = ep.id

            effective_thumb = ep.thumbnail_path or (vid.thumbnail_path if vid else None) or series.poster_path
            effective_duration = ep.duration_sec or (vid.duration_seconds if vid else 0)

            eps_out.append({
                "id": ep.id,
                "season_id": ep.season_id,
                "season_number": s.number,
                "number": ep.number,
                "title_fr": ep.title_fr or f"Épisode {ep.number}",
                "title_ar": ep.title_ar,
                "title_en": ep.title_en,
                "synopsis_fr": ep.synopsis_fr,
                "synopsis_ar": ep.synopsis_ar,
                "synopsis_en": ep.synopsis_en,
                "duration_sec": effective_duration,
                "thumbnail_path": effective_thumb,
                "telegram_video_id": ep.telegram_video_id,
                "video": {
                    "id": vid.id if vid else ep.telegram_video_id or 0,
                    "telegram_message_id": vid.telegram_message_id if vid else 0,
                    "title": f"{series.title_fr} - S{s.number:02d}E{ep.number:02d}" + (f" : {ep.title_fr}" if ep.title_fr else ""),
                    "category": "Série",
                    "duration_seconds": effective_duration,
                    "file_size_bytes": vid.file_size_bytes if vid else 0,
                    "mime_type": vid.mime_type if vid else "video/mp4",
                    "thumbnail_path": effective_thumb,
                    "file_name": vid.file_name if vid else None,
                    "views_count": vid.views_count if vid else 0,
                    "telegram_date": vid.telegram_date if vid else series.created_at,
                    "is_published": True,
                    "season_number": s.number,
                    "episode_number": ep.number,
                    "episode_title": ep.title_fr,
                    "is_favorite": False,
                    "watch_progress_seconds": pos,
                    "is_completed": completed,
                } if vid else None,
                "watch_progress_seconds": pos,
                "is_completed": completed,
            })

        seasons_out.append({
            "id": s.id,
            "number": s.number,
            "title_fr": s.title_fr or f"Saison {s.number}",
            "title_ar": s.title_ar,
            "poster_path": s.poster_path,
            "episode_count": len(eps_out),
            "episodes": eps_out,
        })

    # 1. Vérifier si l'utilisateur a cette série dans ses favoris
    is_series_favorite = False
    if video_ids:
        fav_stmt = select(Favorite.id).where(
            Favorite.user_id == current_user.id,
            Favorite.video_id.in_(video_ids),
        ).limit(1)
        if (await db.execute(fav_stmt)).scalar_one_or_none():
            is_series_favorite = True

    # 2. Extraire les genres/catégories distincts
    genres_set = set()
    for v in video_map.values():
        if v.category and v.category != "Série":
            genres_set.add(v.category)
    if not genres_set:
        genres_set = {"Drame", "Micro-série"}
    genres_list = sorted(list(genres_set))

    # 3. Séries similaires
    similar_stmt = select(Series).where(
        Series.visibility == "published",
        Series.id != series.id,
    ).order_by(desc(Series.rating), desc(Series.created_at)).limit(6)
    similar_res = (await db.execute(similar_stmt)).scalars().all()
    similar_out = []
    for sim in similar_res:
        sim_seasons = (await db.execute(select(Season.id).where(Season.series_id == sim.id))).scalars().all()
        sim_ep_count = 0
        if sim_seasons:
            sim_ep_count = (await db.execute(select(func.count(Episode.id)).where(Episode.season_id.in_(sim_seasons)))).scalar() or 0
        similar_out.append({
            "id": sim.id,
            "title_fr": sim.title_fr,
            "title_ar": sim.title_ar,
            "title_en": sim.title_en,
            "poster_path": sim.poster_path,
            "banner_path": sim.banner_path or sim.poster_path,
            "rating": sim.rating,
            "year_start": sim.year_start,
            "episodes_count": sim_ep_count,
        })

    return {
        "id": series.id,
        "slug": series.slug,
        "title_fr": series.title_fr,
        "title_ar": series.title_ar,
        "title_en": series.title_en,
        "synopsis_fr": series.synopsis_fr,
        "synopsis_ar": series.synopsis_ar,
        "synopsis_en": series.synopsis_en,
        "year_start": series.year_start,
        "rating": series.rating,
        "status": series.status,
        "poster_path": series.poster_path,
        "banner_path": series.banner_path or series.poster_path,
        "seasons_count": len(seasons_out),
        "episodes_count": len(episodes),
        "last_watched_episode_id": last_watched_ep,
        "genres": genres_list,
        "is_favorite": is_series_favorite,
        "similar_series": similar_out,
        "seasons": seasons_out,
    }


@router.post("/series/{series_id}/favorite")
async def toggle_series_favorite(
    series_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Bascule l'état favori d'une série pour l'utilisateur connecté.
    Ajoute ou retire le premier épisode disponible de la table des favoris.
    """
    series = (await db.execute(select(Series).where(Series.id == series_id))).scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="Série introuvable.")

    ep_stmt = (
        select(Episode)
        .join(Season, Episode.season_id == Season.id)
        .where(Season.series_id == series_id)
        .order_by(Season.number.asc(), Episode.number.asc())
        .limit(1)
    )
    first_ep = (await db.execute(ep_stmt)).scalar_one_or_none()
    
    vid_id = first_ep.telegram_video_id if first_ep else None
    if not vid_id:
        fallback_vid = (await db.execute(select(Video.id).order_by(Video.id.asc()).limit(1))).scalar_one_or_none()
        vid_id = fallback_vid

    if not vid_id:
        raise HTTPException(status_code=400, detail="Aucune vidéo disponible sur le serveur.")

    fav_stmt = select(Favorite).where(
        Favorite.user_id == current_user.id,
        Favorite.video_id == vid_id,
    )
    existing_fav = (await db.execute(fav_stmt)).scalar_one_or_none()
    if existing_fav:
        await db.delete(existing_fav)
        await db.commit()
        return {"status": "removed", "is_favorite": False, "message": "Série retirée des favoris"}
    else:
        new_fav = Favorite(user_id=current_user.id, video_id=vid_id)
        db.add(new_fav)
        await db.commit()
        return {"status": "added", "is_favorite": True, "message": "Série ajoutée aux favoris"}
