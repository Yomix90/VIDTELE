"""
Administration — Données de référence : genres et rangées d'accueil.

Code déplacé tel quel depuis l'ancien routers/admin.py (Phase 1).
"""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Genre, HomeRow, User
from app.schemas import (
    GenreResponse,
    HomeRowResponse,
)
from app.security import get_current_admin

router = APIRouter()

# =============================================================
# 9. Genres & Rangées d'Accueil Mobile
# =============================================================

@router.get("/genres", response_model=List[GenreResponse])
async def list_genres(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retourne la liste des genres disponibles."""
    genres = (await db.execute(select(Genre).order_by(Genre.order_index))).scalars().all()
    return [GenreResponse.model_validate(g) for g in genres]


@router.get("/home-rows", response_model=List[HomeRowResponse])
async def list_home_rows(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retourne les rangées configurées pour l'accueil de l'application mobile."""
    rows = (await db.execute(select(HomeRow).order_by(HomeRow.order_index))).scalars().all()
    return [HomeRowResponse.model_validate(r) for r in rows]


