"""
Routeur d'administration complet : Statistiques, Utilisateurs, Invitations, Cache et Synchronisation.
"""
from datetime import datetime, timedelta, timezone
import secrets
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import InviteCode, User, Video
from app.schemas import (
    AdminStatsResponse,
    CacheStats,
    InviteCodeCreate,
    InviteCodeResponse,
    MessageResponse,
    StreamStats,
    SyncStatusResponse,
    UserCreateAdmin,
    UserResponse,
    UserUpdateAdmin,
)
from app.security import get_current_admin, hash_password
from app.services.cache_service import cache_service
from app.services.stream_manager import stream_manager
from app.services.sync_service import sync_service
from app.telegram_client import telegram_manager

router = APIRouter(prefix="/api/admin", tags=["Administration"])


# -------------------------------------------------------------
# 1. Statistiques Globales du Système
# -------------------------------------------------------------

@router.get("/stats", response_model=AdminStatsResponse)
async def get_system_stats(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Retourne l'ensemble des métriques d'exploitation :
    Vidéos, vues, utilisateurs actifs, quotas de streaming et espace cache disque.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    thirty_days_ago = now - timedelta(days=30)

    # Statistiques Vidéos
    vid_stmt = select(
        func.count(Video.id),
        func.coalesce(func.sum(Video.views_count), 0),
        func.coalesce(func.sum(Video.duration_seconds), 0),
    )
    total_videos, total_views, total_duration = (await db.execute(vid_stmt)).one()

    # Statistiques Utilisateurs
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_users = (
        await db.execute(select(func.count(User.id)).where(User.last_login_at >= thirty_days_ago))
    ).scalar_one()

    # Statistiques Invitations
    total_invites = (await db.execute(select(func.count(InviteCode.id)))).scalar_one()
    used_invites = (
        await db.execute(select(func.count(InviteCode.id)).where(InviteCode.is_used == True))
    ).scalar_one()
    active_invites = total_invites - used_invites

    # Statistiques Cache Disque
    cache_info = cache_service.get_cache_stats()

    # Statistiques Streaming Actif
    stream_info = await stream_manager.get_active_stream_counts(db)

    return AdminStatsResponse(
        total_videos=total_videos,
        total_views=total_views,
        total_duration_seconds=total_duration,
        total_users=total_users,
        active_users=active_users,
        total_invites=total_invites,
        active_invites=active_invites,
        used_invites=used_invites,
        cache=CacheStats(**cache_info),
        streams=StreamStats(**stream_info),
    )


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
    """Génère un nouveau code d'invitation unique avec une date d'expiration."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_at = now + timedelta(days=data.expires_in_days) if data.expires_in_days else None

    # Génération d'un code lisible et sécurisé (ex: INV-9A2F-81C3)
    random_part = secrets.token_hex(4).upper()
    code = f"INV-{random_part[:4]}-{random_part[4:]}"

    invite = InviteCode(
        code=code,
        created_by_id=current_admin.id,
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


# -------------------------------------------------------------
# 4. Synchronisation & Cache Disque
# -------------------------------------------------------------

@router.post("/sync", response_model=SyncStatusResponse)
async def trigger_manual_sync(
    current_admin: User = Depends(get_current_admin),
):
    """Déclenche la synchronisation complète du canal privé Telegram."""
    if not telegram_manager.is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram n'est pas configuré dans le fichier .env (API_ID ou API_HASH manquant).",
        )

    if not telegram_manager.session_exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session Telegram inexistante. Exécutez 'python login_telegram.py' sur le serveur.",
        )

    if sync_service.is_syncing():
        return SyncStatusResponse(status="already_running")

    stats = await sync_service.sync_channel()
    if stats.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de synchronisation Telegram: {stats.get('error')}",
        )

    return SyncStatusResponse(
        status="completed",
        added=stats.get("added", 0),
        updated=stats.get("updated", 0),
        total_messages=stats.get("total_messages", 0),
    )


@router.get("/sync-status")
async def get_sync_status(
    current_admin: User = Depends(get_current_admin),
):
    """Statut actuel de la synchronisation et de la liaison Telegram."""
    return {
        "is_syncing": sync_service.is_syncing(),
        "telegram_connected": telegram_manager.is_configured() and telegram_manager.session_exists(),
    }


@router.delete("/cache", response_model=MessageResponse)
async def purge_cache(
    current_admin: User = Depends(get_current_admin),
):
    """Purge complète des fichiers vidéo du cache disque (libère l'espace disque du VPS)."""
    deleted_count = cache_service.clear_all()
    return MessageResponse(message=f"Cache disque vidé avec succès : {deleted_count} fichiers supprimés.")
