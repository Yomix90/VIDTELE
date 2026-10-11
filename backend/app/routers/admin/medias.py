"""
Administration — Vidéos brutes et éléments média (regroupement, détection, suppression).

Code déplacé tel quel depuis l'ancien routers/admin.py (Phase 1).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Episode, MediaItem, Movie, Series, User, Video
from app.schemas import (
    BatchDeleteVideosRequest,
    EpisodeAssignRequest,
    MediaItemCreate,
    MediaItemDetailResponse,
    MediaItemResponse,
    MediaItemUpdate,
    MediaItemVideoResponse,
    MessageResponse,
    RawVideoItemResponse,
)
from app.security import get_current_admin
from app.services.cache_service import cache_service
from app.services.parser_service import parser_service
from app.telegram_client import telegram_manager

router = APIRouter()

# -------------------------------------------------------------
# 6. Gestion des Vidéos Brutes & Organisation du Catalogue
# -------------------------------------------------------------

@router.get("/raw-videos", response_model=List[RawVideoItemResponse])
async def list_raw_videos(
    unassigned_only: bool = Query(True, description="Uniquement les vidéos non encore rattachées à un film/série"),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Retourne la liste des vidéos Telegram brutes en attente d'organisation ou de publication.
    """
    stmt = select(Video)
    if unassigned_only:
        stmt = stmt.where(Video.media_item_id == None)
    stmt = stmt.order_by(desc(Video.telegram_date))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/media-items", response_model=List[MediaItemResponse])
async def list_media_items(
    media_type: Optional[str] = Query(None, pattern="^(movie|series)$"),
    published_only: Optional[bool] = Query(None),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Liste tous les films et séries créés dans le catalogue avec le nombre de vidéos associées.
    """
    count_sub = (
        select(Video.media_item_id, func.count(Video.id).label("v_count"))
        .group_by(Video.media_item_id)
        .subquery()
    )

    stmt = (
        select(MediaItem, func.coalesce(count_sub.c.v_count, 0))
        .outerjoin(count_sub, MediaItem.id == count_sub.c.media_item_id)
        .order_by(desc(MediaItem.created_at))
    )

    if media_type:
        stmt = stmt.where(MediaItem.media_type == media_type)
    if published_only is not None:
        stmt = stmt.where(MediaItem.is_published == published_only)

    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for item, v_count in rows:
        resp = MediaItemResponse(
            id=item.id,
            title=item.title,
            media_type=item.media_type,
            description=item.description,
            category=item.category,
            poster_url=item.poster_url,
            backdrop_url=item.backdrop_url,
            release_year=item.release_year,
            rating=item.rating,
            is_published=item.is_published,
            video_count=v_count,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        items.append(resp)
    return items


@router.post("/media-items", response_model=MediaItemDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_media_item(
    data: MediaItemCreate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Crée un nouveau Film ou Série. Peut optionnellement rattacher immédiatement une vidéo brute.
    """
    new_item = MediaItem(
        title=data.title.strip(),
        media_type=data.media_type,
        description=data.description.strip() if data.description else None,
        category=data.category.strip() if data.category else None,
        poster_url=data.poster_url.strip() if data.poster_url else None,
        backdrop_url=data.backdrop_url.strip() if data.backdrop_url else None,
        release_year=data.release_year,
        rating=data.rating,
        is_published=data.is_published,
    )
    db.add(new_item)
    await db.flush()

    attached_videos = []
    if data.raw_video_id:
        v_stmt = select(Video).where(Video.id == data.raw_video_id)
        v = (await db.execute(v_stmt)).scalar_one_or_none()
        if v:
            v.media_item_id = new_item.id
            v.is_published = new_item.is_published
            if new_item.media_type == "movie":
                v.title = new_item.title
            else:
                v.title = f"{new_item.title} - S01E01"
            if new_item.category:
                v.category = new_item.category
            if new_item.poster_url and not v.thumbnail_path:
                v.thumbnail_path = new_item.poster_url
            attached_videos.append(v)

    await db.commit()
    await db.refresh(new_item)

    return MediaItemDetailResponse(
        id=new_item.id,
        title=new_item.title,
        media_type=new_item.media_type,
        description=new_item.description,
        category=new_item.category,
        poster_url=new_item.poster_url,
        backdrop_url=new_item.backdrop_url,
        release_year=new_item.release_year,
        rating=new_item.rating,
        is_published=new_item.is_published,
        video_count=len(attached_videos),
        created_at=new_item.created_at,
        updated_at=new_item.updated_at,
        videos=[MediaItemVideoResponse.model_validate(v) for v in attached_videos],
    )


@router.get("/media-items/{item_id}", response_model=MediaItemDetailResponse)
async def get_media_item(
    item_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère les détails d'un Film ou d'une Série avec l'ensemble des vidéos/épisodes associés.
    """
    stmt = select(MediaItem).where(MediaItem.id == item_id)
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Élément de catalogue introuvable")

    v_stmt = (
        select(Video)
        .where(Video.media_item_id == item.id)
        .order_by(Video.season_number, Video.episode_number, Video.id)
    )
    videos = (await db.execute(v_stmt)).scalars().all()

    return MediaItemDetailResponse(
        id=item.id,
        title=item.title,
        media_type=item.media_type,
        description=item.description,
        category=item.category,
        poster_url=item.poster_url,
        backdrop_url=item.backdrop_url,
        release_year=item.release_year,
        rating=item.rating,
        is_published=item.is_published,
        video_count=len(videos),
        created_at=item.created_at,
        updated_at=item.updated_at,
        videos=[MediaItemVideoResponse.model_validate(v) for v in videos],
    )


@router.put("/media-items/{item_id}", response_model=MediaItemResponse)
async def update_media_item(
    item_id: int,
    data: MediaItemUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Met à jour les métadonnées d'un film ou d'une série. Si 'is_published' change,
    l'état est propagé à toutes les vidéos/épisodes rattachés.
    """
    stmt = select(MediaItem).where(MediaItem.id == item_id)
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Élément introuvable")

    if data.title is not None:
        item.title = data.title.strip()
    if data.media_type is not None:
        item.media_type = data.media_type
    if data.description is not None:
        item.description = data.description.strip() if data.description else None
    if data.category is not None:
        item.category = data.category.strip() if data.category else None
    if data.poster_url is not None:
        item.poster_url = data.poster_url.strip() if data.poster_url else None
    if data.backdrop_url is not None:
        item.backdrop_url = data.backdrop_url.strip() if data.backdrop_url else None
    if data.release_year is not None:
        item.release_year = data.release_year
    if data.rating is not None:
        item.rating = data.rating

    if data.is_published is not None and data.is_published != item.is_published:
        item.is_published = data.is_published
        v_stmt = select(Video).where(Video.media_item_id == item.id)
        videos = (await db.execute(v_stmt)).scalars().all()
        for v in videos:
            v.is_published = item.is_published
            if item.category:
                v.category = item.category
            if item.poster_url and not v.thumbnail_path:
                v.thumbnail_path = item.poster_url

    await db.commit()
    await db.refresh(item)

    count_stmt = select(func.count(Video.id)).where(Video.media_item_id == item.id)
    v_count = (await db.execute(count_stmt)).scalar_one()

    return MediaItemResponse(
        id=item.id,
        title=item.title,
        media_type=item.media_type,
        description=item.description,
        category=item.category,
        poster_url=item.poster_url,
        backdrop_url=item.backdrop_url,
        release_year=item.release_year,
        rating=item.rating,
        is_published=item.is_published,
        video_count=v_count,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post("/media-items/{item_id}/toggle-publish")
async def toggle_media_item_publish(
    item_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Bascule en 1 clic l'état publié / brouillon d'un film ou d'une série et répercute sur ses vidéos.
    """
    stmt = select(MediaItem).where(MediaItem.id == item_id)
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Élément introuvable")

    item.is_published = not item.is_published

    v_stmt = select(Video).where(Video.media_item_id == item.id)
    videos = (await db.execute(v_stmt)).scalars().all()
    for v in videos:
        v.is_published = item.is_published
        if item.category:
            v.category = item.category

    await db.commit()
    await db.refresh(item)

    return {
        "success": True,
        "is_published": item.is_published,
        "message": f"'{item.title}' est maintenant {'publié sur le mobile' if item.is_published else 'masqué (brouillon)'}.",
    }


@router.delete("/media-items/{item_id}", response_model=MessageResponse)
async def delete_media_item(
    item_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Supprime un Film ou Série du catalogue. Les vidéos Telegram associées ne sont PAS supprimées :
    elles redeviennent des vidéos brutes non publiées (media_item_id = None, is_published = False).
    """
    stmt = select(MediaItem).where(MediaItem.id == item_id)
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Élément introuvable")

    v_stmt = select(Video).where(Video.media_item_id == item.id)
    videos = (await db.execute(v_stmt)).scalars().all()
    for v in videos:
        v.media_item_id = None
        v.is_published = False

    await db.delete(item)
    await db.commit()
    return MessageResponse(message=f"'{item.title}' supprimé du catalogue. Les vidéos sont retournées aux vidéos brutes.")


@router.post("/media-items/{item_id}/episodes", response_model=MessageResponse)
async def attach_episode_to_media(
    item_id: int,
    data: EpisodeAssignRequest,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Associe une vidéo Telegram brute à un film ou comme épisode d'une série.
    """
    item_stmt = select(MediaItem).where(MediaItem.id == item_id)
    item = (await db.execute(item_stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Film ou Série introuvable")

    vid_stmt = select(Video).where(Video.id == data.video_id)
    video = (await db.execute(vid_stmt)).scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo brute introuvable")

    video.media_item_id = item.id
    video.season_number = data.season_number
    video.episode_number = data.episode_number
    video.episode_title = data.episode_title.strip() if data.episode_title else None
    video.is_published = item.is_published

    if item.media_type == "movie":
        video.title = item.title
    else:
        ep_suffix = f" : {video.episode_title}" if video.episode_title else ""
        video.title = f"{item.title} - S{video.season_number:02d}E{video.episode_number:02d}{ep_suffix}"

    if item.category:
        video.category = item.category
    if item.poster_url and not video.thumbnail_path:
        video.thumbnail_path = item.poster_url

    await db.commit()
    return MessageResponse(message=f"Vidéo associée avec succès à '{item.title}'")


@router.delete("/media-items/{item_id}/episodes/{video_id}", response_model=MessageResponse)
async def detach_episode_from_media(
    item_id: int,
    video_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Détache une vidéo d'un film ou d'une série. La vidéo redevient brute et dépubliée.
    """
    vid_stmt = select(Video).where(Video.id == video_id, Video.media_item_id == item_id)
    video = (await db.execute(vid_stmt)).scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo introuvable dans cet élément")

    video.media_item_id = None
    video.is_published = False

    await db.commit()
    return MessageResponse(message="Vidéo détachée avec succès (repositionnée en vidéo brute)")



# =============================================================
# 10. Détection Automatique Intelligente pour Vidéos Brutes
# =============================================================

@router.post("/raw-videos/{video_id}/auto-detect")
async def auto_detect_raw_video(
    video_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse le nom de fichier ou titre d'une vidéo Telegram avec parser_service
    et propose automatiquement une série/film avec numéro de saison et épisode.
    """
    video = (await db.execute(select(Video).where(Video.id == video_id))).scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo introuvable")

    text_to_parse = video.file_name or video.title or video.caption or ""
    parsed = parser_service.parse_video_title(text_to_parse)

    # Vérifier si une série du même nom existe déjà dans le catalogue
    existing_series = (
        await db.execute(select(Series).where(Series.slug == parsed["slug"]))
    ).scalar_one_or_none()

    parsed["existing_series_id"] = existing_series.id if existing_series else None
    parsed["video_id"] = video.id
    parsed["original_text"] = text_to_parse

    return parsed


# =============================================================
# 18. Suppression Unitaire et par Lots de Vidéos Brutes (Base & Telegram)
# =============================================================

@router.delete("/raw-videos/{video_id}", response_model=MessageResponse)
async def delete_single_raw_video(
    video_id: int,
    delete_from_telegram: bool = Query(True, description="Supprimer également le fichier sur le canal Telegram"),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Supprime une vidéo brute de la base de données Atlas Play, détache ses éventuelles
    liaisons (épisode / film), vide son cache local et la supprime directement sur le canal Telegram.
    """
    video = (await db.execute(select(Video).where(Video.id == video_id))).scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo introuvable")

    # 1. Détacher les épisodes ou films pointant vers cette vidéo
    episodes = (await db.execute(select(Episode).where(Episode.telegram_video_id == video.id))).scalars().all()
    for ep in episodes:
        ep.telegram_video_id = None

    movies = (await db.execute(select(Movie).where(Movie.telegram_video_id == video.id))).scalars().all()
    for m in movies:
        m.telegram_video_id = None

    # 2. Supprimer sur le canal Telegram si demandé
    deleted_on_telegram = False
    if delete_from_telegram and video.telegram_message_id:
        deleted_on_telegram = await telegram_manager.delete_telegram_messages([video.telegram_message_id])

    # 3. Supprimer du cache local disque si présent
    try:
        cache_service.purge_cache()
    except Exception:
        pass

    # 4. Supprimer de la base de données
    await db.delete(video)
    await db.commit()

    tg_status = " et sur le canal Telegram" if deleted_on_telegram else ""
    return MessageResponse(message=f"Vidéo #{video_id} supprimée avec succès de la base{tg_status}.")


@router.post("/raw-videos/batch-delete")
async def batch_delete_raw_videos(
    data: BatchDeleteVideosRequest,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Supprime une sélection de vidéos brutes de la base de données Atlas Play
    et supprime définitivement tous les messages correspondants sur le canal Telegram.
    """
    if not data.video_ids:
        raise HTTPException(status_code=400, detail="Veuillez sélectionner au moins une vidéo.")

    stmt = select(Video).where(Video.id.in_(data.video_ids))
    videos = (await db.execute(stmt)).scalars().all()
    if not videos:
        raise HTTPException(status_code=404, detail="Aucune vidéo trouvée pour ces identifiants.")

    # Récupérer les identifiants de messages Telegram
    tg_msg_ids = [v.telegram_message_id for v in videos if v.telegram_message_id]
    v_ids = [v.id for v in videos]

    # Détacher les épisodes et films rattachés
    eps = (await db.execute(select(Episode).where(Episode.telegram_video_id.in_(v_ids)))).scalars().all()
    for ep in eps:
        ep.telegram_video_id = None

    movies = (await db.execute(select(Movie).where(Movie.telegram_video_id.in_(v_ids)))).scalars().all()
    for m in movies:
        m.telegram_video_id = None

    # Supprimer sur Telegram
    deleted_count_tg = 0
    if data.delete_from_telegram and tg_msg_ids:
        ok = await telegram_manager.delete_telegram_messages(tg_msg_ids)
        if ok:
            deleted_count_tg = len(tg_msg_ids)

    # Supprimer de la base de données
    for v in videos:
        await db.delete(v)

    await db.commit()

    return {
        "success": True,
        "deleted_count": len(videos),
        "deleted_from_telegram": deleted_count_tg,
        "message": f"{len(videos)} vidéo(s) supprimée(s) avec succès de la base et {deleted_count_tg} message(s) supprimé(s) sur Telegram !",
    }


