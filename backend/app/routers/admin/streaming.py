"""
Administration — Réglages de streaming simultané et banc d'essai.

Code déplacé tel quel depuis l'ancien routers/admin.py (Phase 1).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import SystemSetting, User
from app.schemas import (
    BenchmarkRunRequest,
    StreamingSettingsUpdate,
)
from app.security import get_current_admin
from app.services.benchmark_service import benchmark_service
from app.services.stream_manager import stream_manager

router = APIRouter()

# =============================================================
# 18. Paramètres de Streaming & Benchmark de Charge VPS
# =============================================================

@router.get("/streaming-settings")
async def get_streaming_settings(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Récupère les paramètres de streaming vidéo et limites de simultanéité."""
    stream_counts = await stream_manager.get_active_stream_counts(db)

    return {
        "max_concurrent_global": settings.MAX_CONCURRENT_STREAMS_GLOBAL,
        "max_concurrent_per_user": settings.MAX_CONCURRENT_STREAMS_PER_USER,
        "stream_token_expire_seconds": settings.STREAM_TOKEN_EXPIRE_SECONDS,
        "max_cache_gb": settings.MAX_CACHE_GB,
        "chunk_size_kb": settings.STREAM_CHUNK_SIZE_KB,
        "current_active_streams": stream_counts.get("current_active", 0),
        "system_specs": benchmark_service.get_system_specs(),
    }


@router.post("/streaming-settings")
async def update_streaming_settings(
    data: StreamingSettingsUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Met à jour les limites de simultanéité (globale et par utilisateur) avec persistance."""
    configs = {
        "MAX_CONCURRENT_STREAMS_GLOBAL": str(data.max_concurrent_global),
        "MAX_CONCURRENT_STREAMS_PER_USER": str(data.max_concurrent_per_user),
    }

    for key, val in configs.items():
        res = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = res.scalar_one_or_none()
        if setting:
            setting.value = val
        else:
            db.add(SystemSetting(key=key, value=val))

    # Mise à jour immédiate en mémoire
    settings.MAX_CONCURRENT_STREAMS_GLOBAL = data.max_concurrent_global
    settings.MAX_CONCURRENT_STREAMS_PER_USER = data.max_concurrent_per_user
    await db.commit()

    return {
        "success": True,
        "message": f"Limites de streaming enregistrées : {data.max_concurrent_global} flux globaux max, {data.max_concurrent_per_user} par utilisateur.",
        "max_concurrent_global": settings.MAX_CONCURRENT_STREAMS_GLOBAL,
        "max_concurrent_per_user": settings.MAX_CONCURRENT_STREAMS_PER_USER,
    }


@router.post("/benchmark/run")
async def run_streaming_benchmark(
    data: BenchmarkRunRequest,
    current_admin: User = Depends(get_current_admin),
):
    """
    Exécute un test de charge asynchrone pour mesurer la capacité du VPS
    (débit Mo/s, latence, nombre maximal de spectateurs simultanés).
    """
    try:
        report = await benchmark_service.run_benchmark(
            concurrency=data.concurrency,
            duration_seconds=data.duration_seconds,
            mode=data.mode,
        )
        return report
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'exécution du test de charge : {str(e)}",
        )


@router.get("/benchmark/specs")
async def get_benchmark_specs(
    current_admin: User = Depends(get_current_admin),
):
    """Retourne les caractéristiques du serveur VPS (CPU, RAM, Disque)."""
    return benchmark_service.get_system_specs()



