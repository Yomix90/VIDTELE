"""
Administration — Gestion des comptes utilisateurs.

Code déplacé tel quel depuis l'ancien routers/admin.py (Phase 1).
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import (
    MessageResponse,
    UserCreateAdmin,
    UserResponse,
    UserUpdateAdmin,
)
from app.security import get_current_admin, hash_password

router = APIRouter()

# -------------------------------------------------------------
# 2. Gestion des Utilisateurs
# -------------------------------------------------------------

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Liste tous les comptes utilisateurs avec leurs droits et statuts."""
    stmt = select(User).order_by(desc(User.created_at)).offset(skip).limit(limit)
    users = (await db.execute(stmt)).scalars().all()
    return users


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreateAdmin,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Création manuelle d'un utilisateur par un administrateur (sans code d'invitation)."""
    stmt = select(User).where(User.username == data.username)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Ce nom d'utilisateur est déjà pris")

    new_user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        role=data.role,
        is_active=True,
        max_concurrent_streams=data.max_concurrent_streams,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdateAdmin,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Mise à jour d'un compte utilisateur (activation, rôle, quota de flux, réinitialisation mot de passe)."""
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.max_concurrent_streams is not None:
        user.max_concurrent_streams = data.max_concurrent_streams
    if data.password is not None:
        user.hashed_password = hash_password(data.password)

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Suppression d'un compte utilisateur."""
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte administrateur")

    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    await db.delete(user)
    await db.commit()
    return MessageResponse(message=f"Utilisateur '{user.username}' supprimé avec succès")


