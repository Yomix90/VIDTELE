"""
Administration — Traduction automatique (Gemini).

Code déplacé tel quel depuis l'ancien routers/admin.py (Phase 1).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import SystemSetting, User
from app.schemas import (
    GeminiConfigRequest,
    GeminiTranslateRequest,
    MessageResponse,
)
from app.security import get_current_admin
from app.services.gemini_service import gemini_service

router = APIRouter()

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
    Traduit et génère intelligemment les métadonnées FR / AR / EN
    avec synopsis cinématiques et suggestion de genres (détecte l'arabe, français, anglais).
    """
    has_any_title = bool((data.title and data.title.strip()) or 
                         (data.title_fr and data.title_fr.strip()) or 
                         (data.title_ar and data.title_ar.strip()) or 
                         (data.title_en and data.title_en.strip()))

    if not has_any_title:
        raise HTTPException(
            status_code=400,
            detail="Veuillez renseigner au moins un titre (en arabe, français ou anglais) pour lancer la traduction IA.",
        )

    res = await gemini_service.translate_and_enrich(
        title=data.title,
        title_fr=data.title_fr,
        title_ar=data.title_ar,
        title_en=data.title_en,
        synopsis=data.synopsis,
        synopsis_fr=data.synopsis_fr,
        synopsis_ar=data.synopsis_ar,
        synopsis_en=data.synopsis_en,
        content_type=data.content_type,
    )
    return res


