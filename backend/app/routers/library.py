"""
Routeur pour la bibliothèque utilisateur : Favoris et Historique de visionnage.
"""
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Favorite, User, Video, WatchHistory
from app.schemas import FavoriteItem, MessageResponse, ProgressUpdateRequest, WatchHistoryItem
from app.security import get_current_active_user

router = APIRouter(tags=["Bibliothèque & Suivi"])


# -------------------------------------------------------------
# Historique de visionnage & Position de reprise
# -------------------------------------------------------------

@router.put("/api/videos/{video_id}/progress", response_model=MessageResponse)
async def update_video_progress(
    video_id: int,
    data: ProgressUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Enregistre la position de reprise (en secondes) et le statut de complétion.
    Appelé automatiquement par le lecteur vidéo mobile à intervalles réguliers et lors de la mise en pause.
    """
    # Vérifier l'existence de la vidéo
    stmt_vid = select(Video.id).where(Video.id == video_id)
    if not (await db.execute(stmt_vid)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Vidéo introuvable")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    stmt_hist = select(WatchHistory).where(
        WatchHistory.user_id == current_user.id,
        WatchHistory.video_id == video_id,
    )
    hist = (await db.execute(stmt_hist)).scalar_one_or_none()

    if hist:
        hist.position_seconds = data.position_seconds
        hist.completed = data.completed
        hist.last_watched_at = now
    else:
        hist = WatchHistory(
            user_id=current_user.id,
            video_id=video_id,
            position_seconds=data.position_seconds,
            completed=data.completed,
            last_watched_at=now,
        )
        db.add(hist)

    await db.commit()
    return MessageResponse(message="Progression enregistrée avec succès")


@router.get("/api/history", response_model=List[WatchHistoryItem])
async def get_watch_history(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère l'historique complet des vidéos visionnées par l'utilisateur connecté,
    trié par date de dernier visionnage décroissante.
    """
    stmt = (
        select(WatchHistory, Video)
        .join(Video, WatchHistory.video_id == Video.id)
        .where(
            WatchHistory.user_id == current_user.id,
            Video.is_published == True,
        )
        .order_by(desc(WatchHistory.last_watched_at))
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for hist, vid in rows:
        items.append(
            WatchHistoryItem(
                id=hist.id,
                video_id=vid.id,
                video_title=vid.title,
                video_thumbnail=vid.thumbnail_path,
                duration_seconds=vid.duration_seconds,
                position_seconds=hist.position_seconds,
                completed=hist.completed,
                last_watched_at=hist.last_watched_at,
            )
        )
    return items


# -------------------------------------------------------------
# Gestion des Favoris
# -------------------------------------------------------------

@router.get("/api/favorites", response_model=List[FavoriteItem])
async def get_favorites(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Liste toutes les vidéos ajoutées en favoris par l'utilisateur connecté.
    """
    stmt = (
        select(Favorite, Video)
        .join(Video, Favorite.video_id == Video.id)
        .where(
            Favorite.user_id == current_user.id,
            Video.is_published == True,
        )
        .order_by(desc(Favorite.created_at))
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for fav, vid in rows:
        items.append(
            FavoriteItem(
                id=fav.id,
                video_id=vid.id,
                video_title=vid.title,
                video_thumbnail=vid.thumbnail_path,
                duration_seconds=vid.duration_seconds,
                created_at=fav.created_at,
            )
        )
    return items


@router.post("/api/favorites/{video_id}", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    video_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Ajoute une vidéo aux favoris de l'utilisateur connecté.
    """
    # Vérifier l'existence de la vidéo
    stmt_vid = select(Video.id).where(Video.id == video_id)
    if not (await db.execute(stmt_vid)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Vidéo introuvable")

    # Vérifier si déjà en favoris
    stmt_fav = select(Favorite).where(
        Favorite.user_id == current_user.id,
        Favorite.video_id == video_id,
    )
    if (await db.execute(stmt_fav)).scalar_one_or_none():
        return MessageResponse(message="Vidéo déjà présente dans les favoris")

    fav = Favorite(user_id=current_user.id, video_id=video_id)
    db.add(fav)
    await db.commit()

    return MessageResponse(message="Vidéo ajoutée aux favoris")


@router.delete("/api/favorites/{video_id}", response_model=MessageResponse)
async def remove_favorite(
    video_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Supprime une vidéo des favoris de l'utilisateur connecté.
    """
    stmt = delete(Favorite).where(
        Favorite.user_id == current_user.id,
        Favorite.video_id == video_id,
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Cette vidéo n'est pas dans vos favoris")

    return MessageResponse(message="Vidéo retirée des favoris")
