"""
Administration — Films.

Code déplacé tel quel depuis l'ancien routers/admin.py (Phase 1).
"""
import secrets
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Movie, User, Video
from app.schemas import (
    MessageResponse,
    MovieCreate,
    MovieResponse,
    MovieUpdate,
)
from app.security import get_current_admin
from app.services.parser_service import slugify

router = APIRouter()

# =============================================================
# 8. Gestion Avancée StreamAdmin : Films
# =============================================================

@router.get("/movies", response_model=List[MovieResponse])
async def list_movies(
    search: Optional[str] = Query(None),
    visibility: Optional[str] = Query(None, pattern="^(published|draft|hidden)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Liste tous les films du catalogue."""
    stmt = select(Movie).order_by(desc(Movie.created_at))
    if search:
        stmt = stmt.where(Movie.title_fr.ilike(f"%{search.strip()}%"))
    if visibility:
        stmt = stmt.where(Movie.visibility == visibility)

    movies = (await db.execute(stmt.offset(skip).limit(limit))).scalars().all()
    return [MovieResponse.model_validate(m) for m in movies]


@router.post("/movies", response_model=MovieResponse, status_code=status.HTTP_201_CREATED)
async def create_movie(
    data: MovieCreate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Crée un film dans le catalogue et peut lui rattacher immédiatement une vidéo Telegram."""
    base_slug = slugify(data.title_fr)
    existing = (await db.execute(select(Movie).where(Movie.slug == base_slug))).scalar_one_or_none()
    slug = f"{base_slug}-{secrets.token_hex(2)}" if existing else base_slug

    if data.telegram_video_id:
        v = (await db.execute(select(Video).where(Video.id == data.telegram_video_id))).scalar_one_or_none()
        if not v:
            raise HTTPException(status_code=404, detail="Vidéo Telegram introuvable")
        v.is_published = (data.visibility == "published")
        v.title = data.title_fr
        if data.poster_path and not v.thumbnail_path:
            v.thumbnail_path = data.poster_path

    movie = Movie(
        slug=slug,
        title_fr=data.title_fr.strip(),
        title_ar=data.title_ar.strip() if data.title_ar else None,
        synopsis_fr=data.synopsis_fr.strip() if data.synopsis_fr else None,
        year=data.year,
        duration_sec=data.duration_sec,
        rating=data.rating,
        poster_path=data.poster_path.strip() if data.poster_path else None,
        banner_path=data.banner_path.strip() if data.banner_path else None,
        telegram_video_id=data.telegram_video_id,
        visibility=data.visibility,
        is_featured=data.is_featured,
    )
    db.add(movie)
    await db.commit()
    await db.refresh(movie)
    return MovieResponse.model_validate(movie)


# =============================================================
# 15. Édition et Suppression Films
# =============================================================

@router.patch("/movies/{movie_id}", response_model=MovieResponse)
@router.put("/movies/{movie_id}", response_model=MovieResponse)
async def update_movie(
    movie_id: int,
    data: MovieUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Met à jour les informations d'un film (titres multilingues, synopsis, affiches, vidéo rattachée)."""
    movie = (await db.execute(select(Movie).where(Movie.id == movie_id))).scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Film introuvable")

    if data.title_fr is not None:
        movie.title_fr = data.title_fr.strip()
    if data.title_ar is not None:
        movie.title_ar = data.title_ar.strip() if data.title_ar else None
    if data.title_en is not None:
        movie.title_en = data.title_en.strip() if data.title_en else None
    if data.synopsis_fr is not None:
        movie.synopsis_fr = data.synopsis_fr.strip() if data.synopsis_fr else None
    if data.synopsis_ar is not None:
        movie.synopsis_ar = data.synopsis_ar.strip() if data.synopsis_ar else None
    if data.synopsis_en is not None:
        movie.synopsis_en = data.synopsis_en.strip() if data.synopsis_en else None
    if data.year is not None:
        movie.year = data.year
    if data.duration_sec is not None:
        movie.duration_sec = data.duration_sec
    if data.rating is not None:
        movie.rating = data.rating
    if data.poster_path is not None and data.poster_path.strip():
        movie.poster_path = data.poster_path.strip()
    if data.banner_path is not None and data.banner_path.strip():
        movie.banner_path = data.banner_path.strip()
    if data.visibility is not None:
        movie.visibility = data.visibility
        if movie.telegram_video_id:
            v = (await db.execute(select(Video).where(Video.id == movie.telegram_video_id))).scalar_one_or_none()
            if v:
                v.is_published = (data.visibility == "published")

    if data.telegram_video_id is not None:
        if data.telegram_video_id == 0:
            if movie.telegram_video_id:
                old_v = (await db.execute(select(Video).where(Video.id == movie.telegram_video_id))).scalar_one_or_none()
                if old_v:
                    old_v.is_published = False
            movie.telegram_video_id = None
        else:
            v = (await db.execute(select(Video).where(Video.id == data.telegram_video_id))).scalar_one_or_none()
            if not v:
                raise HTTPException(status_code=404, detail="Vidéo Telegram introuvable")
            movie.telegram_video_id = v.id
            v.is_published = (movie.visibility == "published")
            v.title = movie.title_fr
            if movie.poster_path and not v.thumbnail_path:
                v.thumbnail_path = movie.poster_path
            if v.duration_seconds and not movie.duration_sec:
                movie.duration_sec = v.duration_seconds

    await db.commit()
    await db.refresh(movie)
    return MovieResponse.model_validate(movie)


@router.delete("/movies/{movie_id}", response_model=MessageResponse)
async def delete_movie(
    movie_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Supprime un film. La vidéo Telegram rattachée est détachée
    et redevient brute (is_published = False) sans être effacée de Telegram.
    """
    movie = (await db.execute(select(Movie).where(Movie.id == movie_id))).scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Film introuvable")

    if movie.telegram_video_id:
        v = (await db.execute(select(Video).where(Video.id == movie.telegram_video_id))).scalar_one_or_none()
        if v:
            v.is_published = False

    await db.delete(movie)
    await db.commit()
    return MessageResponse(message=f"Film '{movie.title_fr}' supprimé avec succès. La vidéo Telegram a été détachée.")


