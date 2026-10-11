"""
Administration — Synchronisation du canal Telegram et purge du cache.

Code déplacé tel quel depuis l'ancien routers/admin.py (Phase 1).
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.models import User
from app.schemas import (
    MessageResponse,
    SyncStatusResponse,
)
from app.security import get_current_admin
from app.services.cache_service import cache_service
from app.services.sync_service import sync_service
from app.telegram_client import telegram_manager

router = APIRouter()

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


