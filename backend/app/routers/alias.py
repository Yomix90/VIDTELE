"""
Alias à la racine de /api utilisés par l'application mobile (/api/home, /api/feed,
/api/series/...). Ils délèguent au catalogue (routers/videos/catalogue.py).
Code déplacé tel quel depuis main.py (Phase 1).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.routers.videos import (
    get_home_content,
    get_public_series_detail,
    get_top_series,
    get_vertical_feed,
    toggle_series_favorite,
)
from app.schemas import FeedResponse, HomeScreenResponse, TopSeriesItem
from app.security import get_current_active_user

router = APIRouter()


@router.get("/api/home", response_model=HomeScreenResponse, tags=["Accueil"])
async def get_home_alias(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Alias racine pour le chargement complet de l'écran d'accueil."""
    return await get_home_content(current_user=current_user, db=db)


@router.get("/api/series/top", response_model=List[TopSeriesItem], tags=["Séries"])
async def get_series_top_alias(
    period: str = "7d",
    limit: int = 5,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Alias racine pour le classement Top des séries."""
    return await get_top_series(period=period, limit=limit, current_user=current_user, db=db)


@router.get("/api/feed", response_model=FeedResponse, tags=["Feed Vertical"])
async def get_feed_alias(
    cursor: Optional[int] = None,
    limit: int = 15,
    series_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Alias racine pour le flux vertical d'épisodes et de vidéos."""
    return await get_vertical_feed(
        cursor=cursor,
        limit=limit,
        series_id=series_id,
        current_user=current_user,
        db=db,
    )


@router.get("/api/series/{series_id}", tags=["Séries"])
async def get_series_detail_alias(
    series_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Alias racine pour le détail d'une série avec épisodes et séries similaires."""
    return await get_public_series_detail(series_id=series_id, current_user=current_user, db=db)


@router.post("/api/series/{series_id}/favorite", tags=["Séries"])
async def toggle_series_favorite_alias(
    series_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Alias racine pour basculer le statut favori d'une série."""
    return await toggle_series_favorite(series_id=series_id, current_user=current_user, db=db)
