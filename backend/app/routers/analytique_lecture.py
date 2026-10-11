"""
Mesures de lecture envoyées par l'application (Phase 2).

- POST /api/analytics/playback      : l'app envoie un lot d'événements (max 50).
- GET  /api/admin/stats/playback    : résumé pour l'administration (TTFF p50/p90, blocages, erreurs).
"""
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import PlaybackEvent, User
from app.repositories import lecture as depot_lecture
from app.security import get_current_active_user, get_current_admin

router = APIRouter(tags=["Mesures de lecture"])


class EvenementLecture(BaseModel):
    """Un événement de lecture mesuré par l'application."""

    video_id: Optional[int] = Field(None, ge=1)
    type: Literal["demarrage", "blocage", "erreur", "reprise", "fin"]
    ttff_ms: Optional[int] = Field(None, ge=0, le=600_000, description="Temps jusqu'à la première image")
    stall_ms: Optional[int] = Field(None, ge=0, le=3_600_000, description="Durée d'un blocage")
    position_s: Optional[float] = Field(None, ge=0, le=86_400)
    precharge: Optional[bool] = None
    reseau: Optional[Literal["wifi", "mobile", "ethernet", "aucun", "inconnu"]] = None
    code_erreur: Optional[str] = Field(None, max_length=64)
    modele_appareil: Optional[str] = Field(None, max_length=64)


class LotEvenements(BaseModel):
    evenements: List[EvenementLecture] = Field(..., min_length=1, max_length=50)


@router.post("/api/analytics/playback", status_code=202)
async def recevoir_mesures(
    lot: LotEvenements,
    request: Request,
    utilisateur: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Enregistre un lot de mesures. La version de l'app vient de l'en-tête X-App-Version."""
    version_app = (request.headers.get("X-App-Version") or "")[:32] or None
    nombre = await depot_lecture.enregistrer_evenements(
        db,
        (
            PlaybackEvent(
                user_id=utilisateur.id,
                video_id=e.video_id,
                event_type=e.type,
                ttff_ms=e.ttff_ms,
                stall_ms=e.stall_ms,
                position_s=e.position_s,
                preloaded=e.precharge,
                network=e.reseau,
                error_code=e.code_erreur,
                app_version=version_app,
                device_model=e.modele_appareil,
            )
            for e in lot.evenements
        ),
    )
    return {"enregistres": nombre}


@router.get("/api/admin/stats/playback")
async def statistiques_lecture(
    jours: int = Query(7, ge=1, le=90),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Résumé des mesures de lecture sur les derniers jours."""
    return await depot_lecture.statistiques(db, jours)
