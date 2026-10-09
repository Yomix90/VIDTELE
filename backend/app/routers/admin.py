"""
Routeur d'administration complet : Statistiques, Utilisateurs, Invitations, Cache et Synchronisation.
"""
from datetime import datetime, timedelta, timezone
import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import InviteCode, MediaItem, User, Video
from app.schemas import (
    AdminStatsResponse,
    CacheStats,
    EpisodeAssignRequest,
    InviteCodeCreate,
    InviteCodeResponse,
    MediaItemCreate,
    MediaItemDetailResponse,
    MediaItemResponse,
    MediaItemUpdate,
    MediaItemVideoResponse,
    MessageResponse,
    RawVideoItemResponse,
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

