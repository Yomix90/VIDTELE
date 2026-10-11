"""
Administration — Codes d'invitation.

Code déplacé tel quel depuis l'ancien routers/admin.py (Phase 1).
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import InviteCode, User
from app.schemas import (
    InviteCodeCreate,
    InviteCodeResponse,
    MessageResponse,
)
from app.security import get_current_admin

router = APIRouter()

# -------------------------------------------------------------
# 3. Gestion des Codes d'Invitation
# -------------------------------------------------------------

@router.get("/invites", response_model=List[InviteCodeResponse])
async def list_invites(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Liste tous les codes d'invitation générés."""
    stmt = select(InviteCode).order_by(desc(InviteCode.created_at))
    invites = (await db.execute(stmt)).scalars().all()
    return invites


@router.post("/invites", response_model=InviteCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    data: InviteCodeCreate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Génère un nouveau code d'invitation (supporte les codes multi-usages ex: 100, 200, 500...)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_at = now + timedelta(days=data.expires_in_days) if data.expires_in_days else None

    # Code personnalisé ou génération automatique
    if data.code and data.code.strip():
        code = data.code.strip().upper()
        stmt_check = select(InviteCode).where(InviteCode.code == code)
        existing = (await db.execute(stmt_check)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Le code d'invitation '{code}' existe déjà. Veuillez en choisir un autre.",
            )
    else:
        random_part = secrets.token_hex(4).upper()
        code = f"INV-{random_part[:4]}-{random_part[4:]}"

    invite = InviteCode(
        code=code,
        description=data.description.strip() if data.description and data.description.strip() else None,
        created_by_id=current_admin.id,
        max_uses=max(1, data.max_uses),
        uses_count=0,
        expires_at=expires_at,
        is_used=False,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


@router.delete("/invites/{invite_id}", response_model=MessageResponse)
async def delete_invite(
    invite_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Supprime ou révoque un code d'invitation."""
    stmt = select(InviteCode).where(InviteCode.id == invite_id)
    invite = (await db.execute(stmt)).scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Code d'invitation introuvable")

    await db.delete(invite)
    await db.commit()
    return MessageResponse(message="Code d'invitation supprimé")


