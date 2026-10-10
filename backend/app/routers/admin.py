"""
Routeur d'administration complet : Statistiques, Utilisateurs, Invitations, Cache et Synchronisation.
"""
import aiofiles
import os
import secrets
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Episode, Genre, HomeHeroItem, HomeRow, InviteCode, MediaItem, Movie, Season, Series, SystemSetting, TelegramAccount, User, Video
from app.schemas import (
    AppUpdateConfig,
    AppUpdateInfo,
    AdminStatsResponse,
    BatchDeleteVideosRequest,
    BatchSeriesCreate,
    BatchAddToExistingSeries,
    CacheStats,
    EpisodeAssignRequest,
    EpisodeCreate,
    EpisodeResponse,
    EpisodeUpdate,
    GeminiConfigRequest,
    GeminiTranslateRequest,
    GenreResponse,
    HomeRowCreate,
    HomeRowResponse,
    InviteCodeCreate,
    InviteCodeResponse,
    MediaItemCreate,
    MediaItemDetailResponse,
    MediaItemResponse,
    MediaItemUpdate,
    MediaItemVideoResponse,
    MessageResponse,
    MovieCreate,
    MovieResponse,
    MovieUpdate,
    RawVideoItemResponse,
    SeasonCreate,
    SeasonDetailResponse,
    SeasonResponse,
    SeriesCreate,
    SeriesDetailResponse,
    SeriesResponse,
    SeriesUpdate,
    StreamStats,
    SyncStatusResponse,
    TelegramAccountCreate,
    TelegramAccountResponse,
    TelegramConfigUpdateRequest,
    TelegramPhoneAuthRequest,
    TelegramPhoneVerifyRequest,
    UserCreateAdmin,
    UserResponse,
    UserUpdateAdmin,
)
from app.security import get_current_admin, hash_password
from app.services.cache_service import cache_service
from app.services.gemini_service import gemini_service
from app.services.parser_service import parser_service, slugify
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


# -------------------------------------------------------------
# 4. Synchronisation & Cache Disque
# -------------------------------------------------------------

@router.post("/sync", response_model=SyncStatusResponse)
@router.post("/telegram/sync", response_model=SyncStatusResponse)
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
    if stats.get("status") == "channel_not_found":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Canal Telegram introuvable ou compte non membre du canal. Vérifiez l'identifiant du canal dans l'onglet Telegram.",
        )
    if stats.get("status") == "not_connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client Telegram non connecté. Activez ou testez votre compte dans l'onglet Telegram.",
        )
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
@router.get("/telegram/sync-status")
async def get_sync_status(
    current_admin: User = Depends(get_current_admin),
):
    """Statut actuel de la synchronisation et de la liaison Telegram."""
    return {
        "is_syncing": sync_service.is_syncing(),
        "telegram_connected": telegram_manager.is_configured() and telegram_manager.session_exists(),
    }


@router.post("/cache/purge", response_model=MessageResponse)
@router.delete("/cache/purge", response_model=MessageResponse)
@router.delete("/cache", response_model=MessageResponse)
async def purge_cache(
    current_admin: User = Depends(get_current_admin),
):
    """Purge complète des fichiers vidéo du cache disque (libère l'espace disque du VPS)."""
    deleted_count = cache_service.clear_all()
    return MessageResponse(message=f"Cache disque vidé avec succès : {deleted_count} fichiers supprimés.")


# -------------------------------------------------------------
# 6. Gestion Dynamique des Canaux Telegram MTProto
# -------------------------------------------------------------

from pydantic import BaseModel

class ChannelTestRequest(BaseModel):
    channel_target: str

class ChannelSetRequest(BaseModel):
    channel_id: str


@router.get("/telegram/status")
async def get_telegram_status(
    current_admin: User = Depends(get_current_admin),
):
    """Retourne l'état de connexion MTProto et le canal configuré."""
    return await telegram_manager.get_connection_status()


@router.get("/telegram/channels")
async def list_telegram_channels(
    current_admin: User = Depends(get_current_admin),
):
    """Liste tous les canaux et groupes auxquels le compte Telegram connecté a accès."""
    return await telegram_manager.list_available_channels()


@router.post("/telegram/test-channel")
async def test_telegram_channel(
    req: ChannelTestRequest,
    current_admin: User = Depends(get_current_admin),
):
    """Vérifie si un canal ou groupe spécifique est accessible par VidTele."""
    result = await telegram_manager.test_channel(req.channel_target)
    return result


@router.post("/telegram/set-channel")
async def set_telegram_channel(
    req: ChannelSetRequest,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enregistre le nouveau canal Telegram actif (en base et mémoire)."""
    clean_target = req.channel_id.strip()
    try:
        cid = int(clean_target)
    except ValueError:
        test_res = await telegram_manager.test_channel(clean_target)
        if not test_res.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=test_res.get("error", "Identifiant de canal invalide."),
            )
        cid = int(test_res.get("formatted_id") or test_res.get("id"))

    # Test d'accès
    test_res = await telegram_manager.test_channel(cid)
    if not test_res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de valider ce canal : {test_res.get('error')}",
        )

    # 1. Mise à jour en mémoire
    await telegram_manager.set_active_channel(cid)

    # 2. Sauvegarde persistante en base SQLite (SystemSetting)
    from app.models import SystemSetting
    stmt = select(SystemSetting).where(SystemSetting.key == "TELEGRAM_CHANNEL_ID")
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        existing.value = str(cid)
    else:
        db.add(SystemSetting(key="TELEGRAM_CHANNEL_ID", value=str(cid)))
    await db.commit()

    # 3. Sauvegarde dans .env si accessible
    try:
        from pathlib import Path
        import re
        for p in [Path(__file__).resolve().parent.parent.parent / ".env", Path("/app/data/.env"), Path(".env")]:
            if p.exists():
                txt = p.read_text(encoding="utf-8")
                if "TELEGRAM_CHANNEL_ID=" in txt:
                    txt = re.sub(r"TELEGRAM_CHANNEL_ID=.*", f"TELEGRAM_CHANNEL_ID={cid}", txt)
                else:
                    txt += f"\nTELEGRAM_CHANNEL_ID={cid}\n"
                p.write_text(txt, encoding="utf-8")
                break
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Canal configuré avec succès : '{test_res.get('title')}' (ID: {cid})",
        "channel": test_res,
    }


# -------------------------------------------------------------
# 5b. Gestion Multi-Comptes & Diagnostics Telegram MTProto
# -------------------------------------------------------------

@router.get("/telegram/accounts", response_model=List[TelegramAccountResponse])
async def list_telegram_accounts(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retourne l'ensemble des comptes Telegram configurés et reliés."""
    stmt = select(TelegramAccount).order_by(desc(TelegramAccount.is_active), desc(TelegramAccount.created_at))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/telegram/accounts", response_model=TelegramAccountResponse, status_code=status.HTTP_201_CREATED)
async def add_telegram_account_session(
    data: TelegramAccountCreate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Lie un nouveau compte Telegram à partir d'une clé StringSession.
    Teste la session avant de l'enregistrer.
    """
    # 1. Tester la validité de la session
    test_res = await telegram_manager.test_session_string(
        string_session=data.string_session,
        api_id=data.api_id,
        api_hash=data.api_hash,
    )
    if not test_res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=test_res.get("error", "Clé StringSession invalide ou expirée."),
        )

    user_info = test_res.get("user", {})

    # 2. Si le compte doit être activé, désactiver les autres
    if data.make_active:
        stmt_deact = select(TelegramAccount).where(TelegramAccount.is_active == True)
        active_accounts = (await db.execute(stmt_deact)).scalars().all()
        for a in active_accounts:
            a.is_active = False

    # 3. Créer l'enregistrement
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    account = TelegramAccount(
        name=data.name.strip(),
        phone=user_info.get("phone"),
        api_id=data.api_id,
        api_hash=data.api_hash,
        string_session=data.string_session.strip(),
        is_active=data.make_active,
        account_user_id=user_info.get("id"),
        account_username=user_info.get("username"),
        account_first_name=user_info.get("first_name"),
        status="connected",
        last_tested_at=now,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    # 4. Basculer le client actif si demandé
    if data.make_active:
        await telegram_manager.switch_active_account(
            string_session=data.string_session.strip(),
            api_id=data.api_id,
            api_hash=data.api_hash,
        )

    return account


@router.post("/telegram/accounts/{account_id}/activate")
async def activate_telegram_account(
    account_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Définit ce compte Telegram comme le compte actif pour le streaming et la synchronisation."""
    stmt = select(TelegramAccount).where(TelegramAccount.id == account_id)
    account = (await db.execute(stmt)).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Compte Telegram introuvable.")

    if not account.string_session:
        raise HTTPException(status_code=400, detail="Ce compte n'a pas de session StringSession valide.")

    # Désactiver tous les autres comptes
    all_accounts = (await db.execute(select(TelegramAccount))).scalars().all()
    for a in all_accounts:
        a.is_active = (a.id == account.id)

    # Basculer le client en mémoire
    switch_res = await telegram_manager.switch_active_account(
        string_session=account.string_session,
        api_id=account.api_id,
        api_hash=account.api_hash,
    )

    account.status = "connected" if switch_res.get("success") else "error"
    account.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()

    return {
        "success": True,
        "message": f"Compte '{account.name}' activé avec succès !",
        "status": switch_res.get("status"),
    }


@router.post("/telegram/accounts/{account_id}/test")
async def test_specific_telegram_account(
    account_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Teste la connexion d'un compte Telegram spécifique et mesure sa latence."""
    stmt = select(TelegramAccount).where(TelegramAccount.id == account_id)
    account = (await db.execute(stmt)).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Compte Telegram introuvable.")

    if not account.string_session:
        return {
            "success": False,
            "error": "Aucune session StringSession enregistrée pour ce compte.",
        }

    test_res = await telegram_manager.test_session_string(
        string_session=account.string_session,
        api_id=account.api_id,
        api_hash=account.api_hash,
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    account.last_tested_at = now
    if test_res.get("success"):
        account.status = "connected"
        account.last_error = None
        user = test_res.get("user", {})
        account.account_user_id = user.get("id")
        account.account_first_name = user.get("first_name")
        account.account_username = user.get("username")
    else:
        account.status = "error"
        account.last_error = test_res.get("error")

    await db.commit()
    return test_res


@router.delete("/telegram/accounts/{account_id}")
async def delete_telegram_account(
    account_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Supprime un compte Telegram lié."""
    stmt = select(TelegramAccount).where(TelegramAccount.id == account_id)
    account = (await db.execute(stmt)).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Compte Telegram introuvable.")

    # Vérifier le nombre total de comptes
    total = (await db.execute(select(func.count(TelegramAccount.id)))).scalar_one()
    if total <= 1:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer le seul compte Telegram restant.",
        )

    if account.is_active:
        raise HTTPException(
            status_code=400,
            detail="Ce compte est actuellement actif. Activez d'abord un autre compte avant de supprimer celui-ci.",
        )

    await db.delete(account)
    await db.commit()
    return {"success": True, "message": f"Compte '{account.name}' délié avec succès."}


@router.post("/telegram/auth/send-code")
async def send_telegram_phone_code(
    data: TelegramPhoneAuthRequest,
    current_admin: User = Depends(get_current_admin),
):
    """Envoie une demande de code de confirmation par SMS ou message Telegram officiel."""
    res = await telegram_manager.send_phone_code(
        phone=data.phone,
        api_id=data.api_id,
        api_hash=data.api_hash,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Échec de l'envoi du code."))
    return res


@router.post("/telegram/auth/verify-code")
async def verify_telegram_phone_code(
    data: TelegramPhoneVerifyRequest,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Vérifie le code OTP reçu et le mot de passe 2FA si présent,
    puis lie automatiquement le compte à la plateforme Atlas Play.
    """
    res = await telegram_manager.verify_phone_code(
        phone=data.phone,
        code=data.code,
        phone_code_hash=data.phone_code_hash,
        password_2fa=data.password_2fa,
    )
    if not res.get("success"):
        # Peut nécessiter le mot de passe 2FA
        if res.get("needs_2fa"):
            return {
                "success": False,
                "needs_2fa": True,
                "message": res.get("message", "Mot de passe 2FA requis."),
            }
        raise HTTPException(status_code=400, detail=res.get("error", "Code de validation incorrect."))

    string_session = res.get("string_session")
    user_info = res.get("user", {})

    # Désactiver les autres si demandé
    if data.make_active:
        stmt_deact = select(TelegramAccount).where(TelegramAccount.is_active == True)
        for a in (await db.execute(stmt_deact)).scalars().all():
            a.is_active = False

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    account = TelegramAccount(
        name=data.account_name.strip() if data.account_name else f"Compte {user_info.get('first_name', 'Telegram')}",
        phone=data.phone,
        api_id=data.api_id,
        api_hash=data.api_hash,
        string_session=string_session,
        is_active=data.make_active,
        account_user_id=user_info.get("id"),
        account_username=user_info.get("username"),
        account_first_name=user_info.get("first_name"),
        status="connected",
        last_tested_at=now,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    if data.make_active:
        await telegram_manager.switch_active_account(
            string_session=string_session,
            api_id=data.api_id,
            api_hash=data.api_hash,
        )

    return {
        "success": True,
        "message": f"Compte '{account.name}' connecté et lié avec succès !",
        "account": account,
    }


@router.post("/telegram/test-connection")
async def run_telegram_diagnostics(
    current_admin: User = Depends(get_current_admin),
):
    """Lance un test de diagnostic complet de la connexion active et du canal de stockage."""
    return await telegram_manager.get_detailed_diagnostics()


@router.post("/telegram/config")
async def update_telegram_config(
    data: TelegramConfigUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Met à jour les identifiants Telegram (API_ID, API_HASH, CHANNEL_ID) persistés en base."""
    from app.config import settings

    if data.api_id is not None:
        settings.TELEGRAM_API_ID = data.api_id
        db.add(SystemSetting(key="TELEGRAM_API_ID", value=str(data.api_id)))

    if data.api_hash is not None and data.api_hash.strip():
        settings.TELEGRAM_API_HASH = data.api_hash.strip()
        db.add(SystemSetting(key="TELEGRAM_API_HASH", value=data.api_hash.strip()))

    if data.channel_id is not None and data.channel_id.strip():
        cid_str = data.channel_id.strip()
        try:
            cid = int(cid_str)
            settings.TELEGRAM_CHANNEL_ID = cid
            db.add(SystemSetting(key="TELEGRAM_CHANNEL_ID", value=str(cid)))
            await telegram_manager.set_active_channel(cid)
        except ValueError:
            pass

    await db.commit()
    diag = await telegram_manager.get_detailed_diagnostics()
    return {
        "success": True,
        "message": "Configuration Telegram mise à jour avec succès.",
        "diagnostics": diag,
    }



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
# 7. Gestion Avancée StreamAdmin : Séries, Saisons & Épisodes
# =============================================================




@router.get("/series", response_model=List[SeriesResponse])
async def list_series(
    search: Optional[str] = Query(None, description="Recherche par titre"),
    visibility: Optional[str] = Query(None, pattern="^(published|draft|hidden)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Liste toutes les séries du catalogue avec nombre de saisons et épisodes."""
    stmt = select(Series).order_by(desc(Series.created_at))
    if search:
        stmt = stmt.where(Series.title_fr.ilike(f"%{search.strip()}%"))
    if visibility:
        stmt = stmt.where(Series.visibility == visibility)

    series_list = (await db.execute(stmt.offset(skip).limit(limit))).scalars().all()

    items = []
    for s in series_list:
        # Compter les saisons et épisodes
        seasons_res = await db.execute(select(Season.id).where(Season.series_id == s.id))
        season_ids = [row[0] for row in seasons_res.all()]
        s_count = len(season_ids)
        ep_count = 0
        if season_ids:
            ep_stmt = select(func.count(Episode.id)).where(Episode.season_id.in_(season_ids))
            ep_count = (await db.execute(ep_stmt)).scalar_one()

        items.append(
            SeriesResponse(
                id=s.id,
                slug=s.slug,
                title_fr=s.title_fr,
                title_ar=s.title_ar,
                synopsis_fr=s.synopsis_fr,
                year_start=s.year_start,
                rating=s.rating,
                status=s.status,
                poster_path=s.poster_path,
                banner_path=s.banner_path,
                is_featured=s.is_featured,
                visibility=s.visibility,
                seasons_count=s_count,
                episodes_count=ep_count,
                created_at=s.created_at,
            )
        )
    return items


@router.post("/series", response_model=SeriesResponse, status_code=status.HTTP_201_CREATED)
async def create_series(
    data: SeriesCreate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Crée une nouvelle série et initialise automatiquement la Saison 1."""
    base_slug = slugify(data.title_fr)
    # Assurer l'unicité du slug
    existing = (await db.execute(select(Series).where(Series.slug == base_slug))).scalar_one_or_none()
    slug = f"{base_slug}-{secrets.token_hex(2)}" if existing else base_slug

    new_series = Series(
        slug=slug,
        title_fr=data.title_fr.strip(),
        title_ar=data.title_ar.strip() if data.title_ar else None,
        synopsis_fr=data.synopsis_fr.strip() if data.synopsis_fr else None,
        synopsis_ar=data.synopsis_ar.strip() if data.synopsis_ar else None,
        year_start=data.year_start,
        rating=data.rating,
        status=data.status,
        poster_path=data.poster_path.strip() if data.poster_path else None,
        banner_path=data.banner_path.strip() if data.banner_path else None,
        visibility=data.visibility,
        is_featured=data.is_featured,
    )
    db.add(new_series)
    await db.flush()

    # Créer automatiquement la Saison 1
    s1 = Season(
        series_id=new_series.id,
        number=1,
        title_fr="Saison 1",
        title_ar="الموسم 1",
        order_index=1,
    )
    db.add(s1)
    await db.commit()
    await db.refresh(new_series)

    return SeriesResponse(
        id=new_series.id,
        slug=new_series.slug,
        title_fr=new_series.title_fr,
        title_ar=new_series.title_ar,
        synopsis_fr=new_series.synopsis_fr,
        year_start=new_series.year_start,
        rating=new_series.rating,
        status=new_series.status,
        poster_path=new_series.poster_path,
        banner_path=new_series.banner_path,
        is_featured=new_series.is_featured,
        visibility=new_series.visibility,
        seasons_count=1,
        episodes_count=0,
        created_at=new_series.created_at,
    )


@router.get("/series/{series_id}", response_model=SeriesDetailResponse)
async def get_series_detail(
    series_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Récupère tous les détails d'une série avec ses saisons et épisodes ordonnés."""
    stmt = select(Series).where(Series.id == series_id)
    series = (await db.execute(stmt)).scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="Série introuvable")

    seasons_stmt = select(Season).where(Season.series_id == series.id).order_by(Season.number)
    seasons = (await db.execute(seasons_stmt)).scalars().all()

    season_details = []
    total_episodes = 0
    for s in seasons:
        ep_stmt = select(Episode).where(Episode.season_id == s.id).order_by(Episode.number)
        episodes = (await db.execute(ep_stmt)).scalars().all()
        total_episodes += len(episodes)
        ep_responses = [EpisodeResponse.model_validate(ep) for ep in episodes]

        season_details.append(
            SeasonDetailResponse(
                id=s.id,
                series_id=s.series_id,
                number=s.number,
                title_fr=s.title_fr,
                title_ar=s.title_ar,
                poster_path=s.poster_path,
                order_index=s.order_index,
                episode_count=len(episodes),
                episodes=ep_responses,
            )
        )

    return SeriesDetailResponse(
        id=series.id,
        slug=series.slug,
        title_fr=series.title_fr,
        title_ar=series.title_ar,
        title_en=series.title_en,
        synopsis_fr=series.synopsis_fr,
        synopsis_ar=series.synopsis_ar,
        synopsis_en=series.synopsis_en,
        year_start=series.year_start,
        rating=series.rating,
        status=series.status,
        poster_path=series.poster_path,
        banner_path=series.banner_path,
        is_featured=series.is_featured,
        visibility=series.visibility,
        seasons_count=len(seasons),
        episodes_count=total_episodes,
        created_at=series.created_at,
        seasons=season_details,
    )


@router.post("/series/{series_id}/seasons", response_model=SeasonResponse, status_code=status.HTTP_201_CREATED)
async def add_season_to_series(
    series_id: int,
    data: SeasonCreate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Ajoute une nouvelle saison à une série existante."""
    series = (await db.execute(select(Series).where(Series.id == series_id))).scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="Série introuvable")

    # Vérifier doublon de numéro
    existing = (
        await db.execute(select(Season).where(Season.series_id == series_id, Season.number == data.number))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"La saison {data.number} existe déjà pour cette série.")

    season = Season(
        series_id=series_id,
        number=data.number,
        title_fr=data.title_fr or f"Saison {data.number}",
        title_ar=data.title_ar or f"الموسم {data.number}",
        poster_path=data.poster_path,
        order_index=data.number,
    )
    db.add(season)
    await db.commit()
    await db.refresh(season)

    return SeasonResponse(
        id=season.id,
        series_id=season.series_id,
        number=season.number,
        title_fr=season.title_fr,
        title_ar=season.title_ar,
        poster_path=season.poster_path,
        order_index=season.order_index,
        episode_count=0,
    )


class AssignVideoRequest(BaseModel):
    telegram_video_id: int


@router.post("/seasons/{season_id}/episodes", response_model=EpisodeResponse, status_code=status.HTTP_201_CREATED)
async def create_episode(
    season_id: int,
    data: EpisodeCreate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Crée un épisode dans une saison et peut lui rattacher immédiatement une vidéo Telegram."""
    season = (await db.execute(select(Season).where(Season.id == season_id))).scalar_one_or_none()
    if not season:
        raise HTTPException(status_code=404, detail="Saison introuvable")

    series = (await db.execute(select(Series).where(Series.id == season.series_id))).scalar_one_or_none()

    # Si une vidéo est rattachée, valider son existence
    if data.telegram_video_id:
        v = (await db.execute(select(Video).where(Video.id == data.telegram_video_id))).scalar_one_or_none()
        if not v:
            raise HTTPException(status_code=404, detail="Vidéo Telegram introuvable")
        v.is_published = (series.visibility == "published") if series else False
        v.season_number = season.number
        v.episode_number = data.number
        v.episode_title = data.title_fr
        if series:
            ep_title = f" : {data.title_fr}" if data.title_fr else ""
            v.title = f"{series.title_fr} - S{season.number:02d}E{data.number:02d}{ep_title}"

    episode = Episode(
        season_id=season_id,
        number=data.number,
        title_fr=data.title_fr or f"Épisode {data.number}",
        title_ar=data.title_ar or f"الحلقة {data.number}",
        synopsis_fr=data.synopsis_fr,
        duration_sec=data.duration_sec,
        thumbnail_path=data.thumbnail_path,
        telegram_video_id=data.telegram_video_id,
        order_index=data.number,
    )
    db.add(episode)
    await db.commit()
    await db.refresh(episode)
    return EpisodeResponse.model_validate(episode)


@router.post("/episodes/{episode_id}/assign-video", response_model=MessageResponse)
async def assign_video_to_episode(
    episode_id: int,
    req: AssignVideoRequest,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Associe ou remplace la vidéo Telegram d'un épisode."""
    episode = (await db.execute(select(Episode).where(Episode.id == episode_id))).scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Épisode introuvable")

    video = (await db.execute(select(Video).where(Video.id == req.telegram_video_id))).scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo Telegram introuvable")

    season = (await db.execute(select(Season).where(Season.id == episode.season_id))).scalar_one_or_none()
    series = (await db.execute(select(Series).where(Series.id == season.series_id))).scalar_one_or_none() if season else None

    episode.telegram_video_id = video.id
    if video.duration_seconds and not episode.duration_sec:
        episode.duration_sec = video.duration_seconds
    if video.thumbnail_path and not episode.thumbnail_path:
        episode.thumbnail_path = video.thumbnail_path

    # Synchroniser l'état de publication de la vidéo avec la série
    video.is_published = (series.visibility == "published") if series else False
    if season:
        video.season_number = season.number
        video.episode_number = episode.number
        if series:
            ep_title = f" : {episode.title_fr}" if episode.title_fr else ""
            video.title = f"{series.title_fr} - S{season.number:02d}E{episode.number:02d}{ep_title}"

    await db.commit()
    return MessageResponse(message=f"Vidéo '{video.title}' associée avec succès à l'épisode {episode.number}.")


@router.post("/series/{series_id}/toggle-visibility")
async def toggle_series_visibility(
    series_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Bascule la visibilité d'une série (published <-> draft) et répercute sur ses vidéos Telegram."""
    series = (await db.execute(select(Series).where(Series.id == series_id))).scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="Série introuvable")

    new_vis = "draft" if series.visibility == "published" else "published"
    series.visibility = new_vis

    # Mettre à jour toutes les vidéos rattachées à ses épisodes
    seasons = (await db.execute(select(Season.id).where(Season.series_id == series.id))).scalars().all()
    if seasons:
        episodes = (await db.execute(select(Episode).where(Episode.season_id.in_(seasons)))).scalars().all()
        vid_ids = [ep.telegram_video_id for ep in episodes if ep.telegram_video_id]
        if vid_ids:
            vids = (await db.execute(select(Video).where(Video.id.in_(vid_ids)))).scalars().all()
            for v in vids:
                v.is_published = (new_vis == "published")

    await db.commit()
    return {
        "success": True,
        "visibility": new_vis,
        "message": f"Série '{series.title_fr}' est maintenant {'publiée sur mobile' if new_vis == 'published' else 'en brouillon'}.",
    }


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
# 11. Gestion des Mises à Jour de l'Application Mobile (Atlas Play)
# =============================================================

@router.get("/app-update")
async def get_app_update_settings(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Récupère la configuration actuelle des mises à jour mobile."""
    settings_keys = [
        "app_latest_version",
        "app_min_version",
        "app_update_url",
        "app_update_title",
        "app_update_notes",
        "app_update_force",
    ]
    res = await db.execute(select(SystemSetting).where(SystemSetting.key.in_(settings_keys)))
    settings_dict = {row.key: row.value for row in res.scalars().all()}

    return {
        "latest_version": settings_dict.get("app_latest_version", "1.0.0"),
        "min_version": settings_dict.get("app_min_version", "1.0.0"),
        "download_url": settings_dict.get("app_update_url", ""),
        "title": settings_dict.get("app_update_title", "Mise à jour disponible"),
        "release_notes": settings_dict.get("app_update_notes", ""),
        "force_update": settings_dict.get("app_update_force", "false").lower() == "true",
    }


@router.post("/app-update", response_model=MessageResponse)
async def update_app_update_settings(
    data: AppUpdateConfig,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enregistre la configuration de mise à jour déployée pour l'application mobile."""
    configs = {
        "app_latest_version": data.latest_version.strip(),
        "app_min_version": data.min_version.strip(),
        "app_update_url": data.download_url.strip() if data.download_url else "",
        "app_update_title": data.title.strip() if data.title else "Mise à jour disponible",
        "app_update_notes": data.release_notes.strip() if data.release_notes else "",
        "app_update_force": "true" if data.force_update else "false",
    }

    for key, val in configs.items():
        res = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = res.scalar_one_or_none()
        if setting:
            setting.value = val
        else:
            db.add(SystemSetting(key=key, value=val))

    await db.commit()
    return MessageResponse(message="Configuration de mise à jour mobile enregistrée avec succès.")


# =============================================================
# 12. Téléversement d'Images sur le Serveur VPS (Affiches / Bannières)
# =============================================================

@router.post("/upload-image")
async def upload_image_to_vps(
    file: UploadFile = File(...),
    current_admin: User = Depends(get_current_admin),
):
    """
    Sauvegarde une affiche ou bannière sur le serveur VPS dans /static/uploads/.
    Renvoie l'URL publique accessible par l'application mobile et l'interface web.
    """
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".jpg"
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Format d'image non supporté ({ext}). Formats acceptés : JPG, PNG, WEBP, GIF.",
        )

    upload_dir = Path("app/static/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex[:12]}_{secrets.token_hex(4)}{ext}"
    dest_path = upload_dir / filename

    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'enregistrement de l'image : {str(e)}")

    url = f"/static/uploads/{filename}"
    return {
        "success": True,
        "url": url,
        "filename": filename,
        "message": "Image enregistrée avec succès sur le serveur.",
    }


# =============================================================
# 12 bis. Téléversement d'APK Mobile Atlas Play sur le Serveur VPS
# =============================================================

@router.post("/upload-apk")
async def upload_apk_to_vps(
    file: UploadFile = File(...),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Sauvegarde un fichier d'application Android (.apk) sur le serveur VPS dans /static/uploads/apk/.
    Renvoie l'URL publique directe de téléchargement.
    """
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".apk"
    if ext != ".apk":
        raise HTTPException(
            status_code=400,
            detail="Seuls les fichiers avec l'extension .apk sont autorisés.",
        )

    upload_dir = Path("app/static/uploads/apk")
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_original_name = os.path.basename(file.filename) if file.filename else "atlas-play.apk"
    base_name = os.path.splitext(safe_original_name)[0]
    filename = f"{base_name}_{uuid.uuid4().hex[:6]}.apk"
    dest_path = upload_dir / filename

    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        # Conserver une copie à chemin fixe pour le téléchargement direct
        shutil.copyfile(dest_path, upload_dir / "atlas-play.apk")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'enregistrement de l'APK : {str(e)}")

    download_url = f"/static/uploads/apk/{filename}"
    size_mb = round(os.path.getsize(dest_path) / (1024 * 1024), 2)

    # Mettre à jour automatiquement le paramètre système app_update_url
    try:
        stmt_set = select(SystemSetting).where(SystemSetting.key == "app_update_url")
        setting = (await db.execute(stmt_set)).scalar_one_or_none()
        if setting:
            setting.value = download_url
        else:
            db.add(SystemSetting(key="app_update_url", value=download_url))
        await db.commit()
    except Exception as e:
        logger.warning(f"Impossible de mettre à jour app_update_url en base: {e}")

    return {
        "success": True,
        "download_url": download_url,
        "filename": filename,
        "size_mb": size_mb,
        "message": f"Fichier APK '{safe_original_name}' ({size_mb} Mo) téléversé avec succès sur le serveur !",
    }



# =============================================================
# 13. Téléversement Direct de Vidéo vers Telegram avec Streaming MTProto
# =============================================================

@router.post("/videos/upload")
async def upload_video_direct_to_telegram(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Téléverse directement une vidéo depuis le panneau web vers le canal Telegram privé
    avec activation du streaming MTProto (supports_streaming=True).
    La vidéo est immédiatement indexée dans la base de données.
    """
    cache_upload_dir = Path("cache/uploads")
    cache_upload_dir.mkdir(parents=True, exist_ok=True)

    original_filename = file.filename or "video.mp4"
    safe_temp_name = f"upload_{uuid.uuid4().hex}_{original_filename}"
    temp_file_path = str(cache_upload_dir / safe_temp_name)

    try:
        async with aiofiles.open(temp_file_path, "wb") as buffer:
            while chunk := await file.read(2 * 1024 * 1024):  # Chunks de 2 Mo asynchrones
                await buffer.write(chunk)

        upload_caption = caption or title or original_filename

        res = await telegram_manager.upload_video_file(
            file_path=temp_file_path,
            file_name=original_filename,
            caption=upload_caption,
        )

        if not res.get("success"):
            raise HTTPException(
                status_code=500,
                detail=res.get("error", "Échec de l'envoi de la vidéo vers Telegram."),
            )

        message = res.get("message")
        video = None
        if message:
            video = await sync_service._process_video_message(message, db)
            if video and title:
                video.title = title.strip()
                await db.commit()
                await db.refresh(video)

        return {
            "success": True,
            "message": "Vidéo téléversée vers Telegram avec succès et prête pour le streaming !",
            "video_id": video.id if video else None,
            "title": video.title if video else original_filename,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'upload vidéo : {str(e)}")
    finally:
        # Nettoyage du fichier temporaire du cache
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass


# =============================================================
# 14. Édition et Suppression Séries & Épisodes
# =============================================================

@router.patch("/series/{series_id}", response_model=SeriesResponse)
@router.put("/series/{series_id}", response_model=SeriesResponse)
async def update_series(
    series_id: int,
    data: SeriesUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Met à jour les informations d'une série (titres multilingues, synopsis, affiches, statut)."""
    series = (await db.execute(select(Series).where(Series.id == series_id))).scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="Série introuvable")

    if data.title_fr is not None:
        series.title_fr = data.title_fr.strip()
    if data.title_ar is not None:
        series.title_ar = data.title_ar.strip() if data.title_ar else None
    if data.title_en is not None:
        series.title_en = data.title_en.strip() if data.title_en else None
    if data.synopsis_fr is not None:
        series.synopsis_fr = data.synopsis_fr.strip() if data.synopsis_fr else None
    if data.synopsis_ar is not None:
        series.synopsis_ar = data.synopsis_ar.strip() if data.synopsis_ar else None
    if data.synopsis_en is not None:
        series.synopsis_en = data.synopsis_en.strip() if data.synopsis_en else None
    if data.year_start is not None:
        series.year_start = data.year_start
    if data.rating is not None:
        series.rating = data.rating
    if data.poster_path is not None:
        series.poster_path = data.poster_path.strip() if data.poster_path else None
    if data.banner_path is not None:
        series.banner_path = data.banner_path.strip() if data.banner_path else None
    if data.status is not None:
        series.status = data.status
    if data.visibility is not None and data.visibility != series.visibility:
        series.visibility = data.visibility
        # Répercuter sur les vidéos Telegram associées
        seasons = (await db.execute(select(Season.id).where(Season.series_id == series.id))).scalars().all()
        if seasons:
            episodes = (await db.execute(select(Episode).where(Episode.season_id.in_(seasons)))).scalars().all()
            vid_ids = [ep.telegram_video_id for ep in episodes if ep.telegram_video_id]
            if vid_ids:
                vids = (await db.execute(select(Video).where(Video.id.in_(vid_ids)))).scalars().all()
                for v in vids:
                    v.is_published = (data.visibility == "published")

    await db.commit()
    await db.refresh(series)

    # Récupérer les compteurs
    seasons_res = await db.execute(select(Season.id).where(Season.series_id == series.id))
    season_ids = [row[0] for row in seasons_res.all()]
    ep_count = 0
    if season_ids:
        ep_count = (await db.execute(select(func.count(Episode.id)).where(Episode.season_id.in_(season_ids)))).scalar_one()

    return SeriesResponse(
        id=series.id,
        slug=series.slug,
        title_fr=series.title_fr,
        title_ar=series.title_ar,
        title_en=series.title_en,
        synopsis_fr=series.synopsis_fr,
        synopsis_ar=series.synopsis_ar,
        synopsis_en=series.synopsis_en,
        year_start=series.year_start,
        rating=series.rating,
        status=series.status,
        poster_path=series.poster_path,
        banner_path=series.banner_path,
        is_featured=series.is_featured,
        visibility=series.visibility,
        seasons_count=len(season_ids),
        episodes_count=ep_count,
        created_at=series.created_at,
    )


@router.delete("/series/{series_id}", response_model=MessageResponse)
async def delete_series(
    series_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Supprime une série ainsi que ses saisons et épisodes.
    Les vidéos Telegram associées NE SONT PAS supprimées : elles sont détachées
    et redeviennent des vidéos brutes (non publiées).
    """
    series = (await db.execute(select(Series).where(Series.id == series_id))).scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="Série introuvable")

    seasons = (await db.execute(select(Season).where(Season.series_id == series.id))).scalars().all()
    season_ids = [s.id for s in seasons]
    if season_ids:
        episodes = (await db.execute(select(Episode).where(Episode.season_id.in_(season_ids)))).scalars().all()
        for ep in episodes:
            if ep.telegram_video_id:
                v = (await db.execute(select(Video).where(Video.id == ep.telegram_video_id))).scalar_one_or_none()
                if v:
                    v.is_published = False
            await db.delete(ep)
        for s in seasons:
            await db.delete(s)

    await db.delete(series)
    await db.commit()
    return MessageResponse(message=f"Série '{series.title_fr}' supprimée avec succès. Les vidéos ont été détachées.")


@router.patch("/episodes/{episode_id}", response_model=EpisodeResponse)
@router.put("/episodes/{episode_id}", response_model=EpisodeResponse)
async def update_episode(
    episode_id: int,
    data: EpisodeUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Modifie le numéro, titre, synopsis ou vidéo Telegram d'un épisode."""
    episode = (await db.execute(select(Episode).where(Episode.id == episode_id))).scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Épisode introuvable")

    if data.number is not None:
        episode.number = data.number
        episode.order_index = data.number
    if data.title_fr is not None:
        episode.title_fr = data.title_fr.strip()
    if data.title_ar is not None:
        episode.title_ar = data.title_ar.strip() if data.title_ar else None
    if data.title_en is not None:
        episode.title_en = data.title_en.strip() if data.title_en else None
    if data.synopsis_fr is not None:
        episode.synopsis_fr = data.synopsis_fr.strip() if data.synopsis_fr else None
    if data.duration_sec is not None:
        episode.duration_sec = data.duration_sec

    if data.telegram_video_id is not None:
        if data.telegram_video_id == 0:
            if episode.telegram_video_id:
                old_v = (await db.execute(select(Video).where(Video.id == episode.telegram_video_id))).scalar_one_or_none()
                if old_v:
                    old_v.is_published = False
            episode.telegram_video_id = None
        else:
            v = (await db.execute(select(Video).where(Video.id == data.telegram_video_id))).scalar_one_or_none()
            if not v:
                raise HTTPException(status_code=404, detail="Vidéo Telegram introuvable")
            episode.telegram_video_id = v.id
            if v.duration_seconds and not episode.duration_sec:
                episode.duration_sec = v.duration_seconds

    await db.commit()
    await db.refresh(episode)
    return EpisodeResponse.model_validate(episode)


@router.delete("/episodes/{episode_id}", response_model=MessageResponse)
async def delete_episode(
    episode_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Supprime un épisode. La vidéo Telegram rattachée est détachée
    et redevient brute sans être effacée de Telegram.
    """
    episode = (await db.execute(select(Episode).where(Episode.id == episode_id))).scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Épisode introuvable")

    if episode.telegram_video_id:
        v = (await db.execute(select(Video).where(Video.id == episode.telegram_video_id))).scalar_one_or_none()
        if v:
            v.is_published = False

    await db.delete(episode)
    await db.commit()
    return MessageResponse(message=f"Épisode {episode.number} supprimé avec succès.")


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
    if data.poster_path is not None:
        movie.poster_path = data.poster_path.strip() if data.poster_path else None
    if data.banner_path is not None:
        movie.banner_path = data.banner_path.strip() if data.banner_path else None
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


# =============================================================
# 16. Création de Série par Lots avec Détection Intelligente
# =============================================================

@router.post("/series/batch-create")
async def create_series_from_batch(
    data: BatchSeriesCreate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Prend une liste d'identifiants de vidéos brutes, analyse intelligemment les numéros
    d'épisodes et saisons (ex: S01E03, 1x04, الحلقة 05), crée la série, les saisons
    nécessaires et lie automatiquement chaque épisode.
    """
    if not data.video_ids:
        raise HTTPException(status_code=400, detail="Veuillez sélectionner au moins une vidéo.")

    # Récupérer toutes les vidéos demandées
    stmt = select(Video).where(Video.id.in_(data.video_ids))
    videos = (await db.execute(stmt)).scalars().all()
    if not videos:
        raise HTTPException(status_code=404, detail="Aucune vidéo valide trouvée pour cette sélection.")

    base_slug = slugify(data.title_fr)
    existing = (await db.execute(select(Series).where(Series.slug == base_slug))).scalar_one_or_none()
    slug = f"{base_slug}-{secrets.token_hex(2)}" if existing else base_slug

    new_series = Series(
        slug=slug,
        title_fr=data.title_fr.strip(),
        title_ar=data.title_ar.strip() if data.title_ar else None,
        title_en=data.title_en.strip() if data.title_en else None,
        synopsis_fr=data.synopsis_fr.strip() if data.synopsis_fr else None,
        poster_path=data.poster_path.strip() if data.poster_path else None,
        banner_path=data.banner_path.strip() if data.banner_path else None,
        visibility=data.visibility,
    )
    db.add(new_series)
    await db.flush()

    # Dictionnaire des saisons créées : season_number -> Season
    seasons_cache: Dict[int, Season] = {}

    # Analyser et trier les vidéos
    parsed_items = []
    for idx, v in enumerate(videos):
        text = v.file_name or v.title or v.caption or f"Episode {idx+1}"
        parsed = parser_service.parse_video_title(text) if data.auto_detect else {
            "season": 1,
            "episode": idx + 1,
            "clean_title": f"Épisode {idx + 1}",
        }
        season_num = parsed.get("season") or 1
        episode_num = parsed.get("episode") or (idx + 1)
        parsed_items.append({
            "video": v,
            "season_num": season_num,
            "episode_num": episode_num,
            "clean_title": parsed.get("clean_title") or f"Épisode {episode_num}",
        })

    # Trier par saison puis épisode
    parsed_items.sort(key=lambda x: (x["season_num"], x["episode_num"]))

    episodes_created = 0
    for item in parsed_items:
        s_num = item["season_num"]
        if s_num not in seasons_cache:
            season = Season(
                series_id=new_series.id,
                number=s_num,
                title_fr=f"Saison {s_num}",
                title_ar=f"الموسم {s_num}",
                order_index=s_num,
            )
            db.add(season)
            await db.flush()
            seasons_cache[s_num] = season
        else:
            season = seasons_cache[s_num]

        v = item["video"]
        v.is_published = (data.visibility == "published")
        v.season_number = s_num
        v.episode_number = item["episode_num"]
        v.title = f"{new_series.title_fr} - S{s_num:02d}E{item['episode_num']:02d}"

        ep = Episode(
            season_id=season.id,
            number=item["episode_num"],
            title_fr=item["clean_title"],
            title_ar=f"الحلقة {item['episode_num']}",
            duration_sec=v.duration_seconds,
            thumbnail_path=v.thumbnail_path or new_series.poster_path,
            telegram_video_id=v.id,
            order_index=item["episode_num"],
        )
        db.add(ep)
        episodes_created += 1

    await db.commit()
    await db.refresh(new_series)

    return {
        "success": True,
        "series_id": new_series.id,
        "title": new_series.title_fr,
        "seasons_count": len(seasons_cache),
        "episodes_count": episodes_created,
        "message": f"Série '{new_series.title_fr}' créée avec succès avec {len(seasons_cache)} saison(s) et {episodes_created} épisode(s) liés !",
    }


@router.post("/series/batch-add-videos")
async def add_videos_to_existing_series(
    data: BatchAddToExistingSeries,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Associe un lot de vidéos brutes à une série existante,
    avec détection automatique ou manuelle de la saison et des numéros d'épisodes.
    """
    if not data.video_ids:
        raise HTTPException(status_code=400, detail="Veuillez sélectionner au moins une vidéo.")

    series = (await db.execute(select(Series).where(Series.id == data.series_id))).scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="Série introuvable.")

    # Récupérer les saisons existantes de la série
    seasons_res = (await db.execute(select(Season).where(Season.series_id == series.id))).scalars().all()
    seasons_cache: Dict[int, Season] = {s.number: s for s in seasons_res}

    # Si une saison spécifique a été choisie
    forced_season = None
    if data.season_id:
        forced_season = next((s for s in seasons_res if s.id == data.season_id), None)
        if not forced_season:
            raise HTTPException(status_code=404, detail="Saison sélectionnée introuvable dans cette série.")

    # Charger les vidéos
    videos = (await db.execute(select(Video).where(Video.id.in_(data.video_ids)))).scalars().all()
    if not videos:
        raise HTTPException(status_code=404, detail="Aucune vidéo valide trouvée pour cette sélection.")

    # Trouver le numéro d'épisode le plus élevé par saison
    episodes_res = (await db.execute(
        select(Episode)
        .join(Season, Episode.season_id == Season.id)
        .where(Season.series_id == series.id)
    )).scalars().all()

    # Dictionnaire (season_number, episode_number) -> Episode
    existing_episodes_map: Dict[tuple, Episode] = {}
    max_ep_per_season: Dict[int, int] = {}
    for ep in episodes_res:
        s_obj = next((s for s in seasons_res if s.id == ep.season_id), None)
        if s_obj:
            existing_episodes_map[(s_obj.number, ep.number)] = ep
            max_ep_per_season[s_obj.number] = max(max_ep_per_season.get(s_obj.number, 0), ep.number)

    # Analyser les vidéos
    parsed_items = []
    for idx, v in enumerate(videos):
        text = v.file_name or v.title or v.caption or f"Episode {idx+1}"
        parsed = parser_service.parse_video_title(text) if data.auto_detect else {
            "season": forced_season.number if forced_season else 1,
            "episode": None,
            "clean_title": f"Épisode {idx + 1}",
        }

        s_num = forced_season.number if forced_season else (parsed.get("season") or 1)
        ep_num = parsed.get("episode")
        clean_title = parsed.get("clean_title") or (f"Épisode {ep_num}" if ep_num else f"Épisode {idx + 1}")

        parsed_items.append({
            "video": v,
            "season_num": s_num,
            "episode_num": ep_num,
            "clean_title": clean_title,
        })

    # Trier par saison puis par numéro d'épisode
    parsed_items.sort(key=lambda x: (x["season_num"], x["episode_num"] or 0, x["video"].file_name or x["video"].title))

    episodes_assigned = 0
    for item in parsed_items:
        s_num = item["season_num"]

        # S'assurer que la saison existe
        if s_num not in seasons_cache:
            new_season = Season(
                series_id=series.id,
                number=s_num,
                title_fr=f"Saison {s_num}",
                title_ar=f"الموسم {s_num}",
                order_index=s_num,
            )
            db.add(new_season)
            await db.flush()
            seasons_cache[s_num] = new_season
            target_season = new_season
        else:
            target_season = seasons_cache[s_num]

        # Déterminer le numéro d'épisode
        ep_num = item["episode_num"]
        if ep_num is None:
            ep_num = max_ep_per_season.get(s_num, 0) + 1

        max_ep_per_season[s_num] = max(max_ep_per_season.get(s_num, 0), ep_num)

        v = item["video"]
        v.is_published = data.publish
        v.season_number = s_num
        v.episode_number = ep_num
        v.title = f"{series.title_fr} - S{s_num:02d}E{ep_num:02d}"

        # Vérifier si cet épisode existe déjà dans cette saison
        existing_ep = existing_episodes_map.get((s_num, ep_num))
        if existing_ep:
            existing_ep.telegram_video_id = v.id
            if v.duration_seconds and not existing_ep.duration_sec:
                existing_ep.duration_sec = v.duration_seconds
            if not existing_ep.thumbnail_path:
                existing_ep.thumbnail_path = v.thumbnail_path or series.poster_path
        else:
            new_ep = Episode(
                season_id=target_season.id,
                number=ep_num,
                title_fr=item["clean_title"],
                title_ar=f"الحلقة {ep_num}",
                duration_sec=v.duration_seconds,
                thumbnail_path=v.thumbnail_path or series.poster_path,
                telegram_video_id=v.id,
                order_index=ep_num,
            )
            db.add(new_ep)
            existing_episodes_map[(s_num, ep_num)] = new_ep

        episodes_assigned += 1

    if data.publish and series.visibility == "draft":
        series.visibility = "published"

    await db.commit()
    await db.refresh(series)

    return {
        "success": True,
        "series_id": series.id,
        "title": series.title_fr,
        "added_count": episodes_assigned,
        "message": f"{episodes_assigned} vidéo(s) ajoutée(s) avec succès à la série '{series.title_fr}' !",
    }


# =============================================================
# 17. Intégration Google Gemini AI (Traduction & Enrichissement)
# =============================================================

@router.get("/ai/config")
async def get_ai_config(
    current_admin: User = Depends(get_current_admin),
):
    """Récupère l'état et le modèle configuré pour l'IA Gemini."""
    conf = await gemini_service.get_config()
    return {
        "configured": bool(conf.get("api_key")),
        "model": conf.get("model", "gemini-1.5-flash"),
        "has_key": bool(conf.get("api_key")),
    }


@router.post("/ai/config", response_model=MessageResponse)
async def update_ai_config(
    data: GeminiConfigRequest,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enregistre la clé API Gemini et le modèle sélectionné."""
    if data.api_key is not None:
        stmt = select(SystemSetting).where(SystemSetting.key == "GEMINI_API_KEY")
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row:
            row.value = data.api_key.strip()
        else:
            db.add(SystemSetting(key="GEMINI_API_KEY", value=data.api_key.strip()))

    if data.model is not None:
        stmt = select(SystemSetting).where(SystemSetting.key == "GEMINI_MODEL")
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row:
            row.value = data.model.strip()
        else:
            db.add(SystemSetting(key="GEMINI_MODEL", value=data.model.strip()))

    await db.commit()
    return MessageResponse(message="Configuration Gemini AI enregistrée avec succès.")


@router.post("/ai/test-key")
async def test_ai_key(
    data: GeminiConfigRequest,
    current_admin: User = Depends(get_current_admin),
):
    """Teste la validité d'une clé API Gemini auprès de Google."""
    if not data.api_key:
        raise HTTPException(status_code=400, detail="Veuillez fournir une clé API Gemini.")
    return await gemini_service.test_key(api_key=data.api_key, model=data.model)


@router.post("/ai/translate")
async def translate_with_gemini(
    data: GeminiTranslateRequest,
    current_admin: User = Depends(get_current_admin),
):
    """
    Traduit et génère automatiquement les métadonnées FR / AR / EN
    avec synopsis cinématiques et suggestion de genres.
    """
    if not data.title:
        raise HTTPException(status_code=400, detail="Veuillez fournir au moins un titre.")

    res = await gemini_service.translate_and_enrich(
        title=data.title,
        synopsis=data.synopsis,
        content_type=data.content_type,
    )
    return res


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


