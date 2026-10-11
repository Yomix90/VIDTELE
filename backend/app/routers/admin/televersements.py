"""
Administration — Téléversements : images, APK, vidéos vers Telegram.

Code déplacé tel quel depuis l'ancien routers/admin.py (Phase 1).
"""
import logging
import os
import secrets
import shutil
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    SystemSetting,
    User,
)
from app.security import get_current_admin
from app.services.sync_service import sync_service
from app.telegram_client import telegram_manager

# (Corrige un NameError latent : « logger » n'était pas défini dans l'ancien admin.py)
logger = logging.getLogger("vidtele.admin.televersements")

router = APIRouter()

# =============================================================
# 12. Téléversement d'Images sur le Serveur VPS (Affiches / Bannières)
# =============================================================

def get_persistent_uploads_dir(subfolder: str = "") -> Path:
    """
    Retourne le dossier d'uploads persistant :
    - /app/data/uploads si dans le conteneur Docker (volume persistant vidtele_data:/app/data)
    - ou app/static/uploads en développement local.
    """
    if Path("/app/data").is_dir():
        base = Path("/app/data/uploads")
    else:
        base = Path(__file__).resolve().parent.parent / "static" / "uploads"
    target = base / subfolder if subfolder else base
    target.mkdir(parents=True, exist_ok=True)
    return target


@router.post("/upload-image")
async def upload_image_to_vps(
    file: UploadFile = File(...),
    current_admin: User = Depends(get_current_admin),
):
    """
    Sauvegarde une affiche ou bannière sur le serveur VPS dans le stockage persistant.
    Renvoie l'URL publique accessible par l'application mobile et l'interface web.
    """
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".jpg"
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Format d'image non supporté ({ext}). Formats acceptés : JPG, PNG, WEBP, GIF.",
        )

    upload_dir = get_persistent_uploads_dir()
    filename = f"{uuid.uuid4().hex[:12]}_{secrets.token_hex(4)}{ext}"
    dest_path = upload_dir / filename

    try:
        async with aiofiles.open(dest_path, "wb") as buffer:
            while chunk := await file.read(1024 * 512):
                await buffer.write(chunk)

        # Copie de sécurité dans app/static/uploads si distinct pour compatibilité locale
        local_static = Path(__file__).resolve().parent.parent / "static" / "uploads" / filename
        if local_static != dest_path:
            try:
                local_static.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(dest_path, local_static)
            except Exception:
                pass
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
    Sauvegarde un fichier d'application Android (.apk) sur le serveur VPS dans le stockage persistant.
    Renvoie l'URL publique directe de téléchargement.
    """
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".apk"
    if ext != ".apk":
        raise HTTPException(
            status_code=400,
            detail="Seuls les fichiers avec l'extension .apk sont autorisés.",
        )

    upload_dir = get_persistent_uploads_dir("apk")
    safe_original_name = os.path.basename(file.filename) if file.filename else "atlas-play.apk"
    base_name = os.path.splitext(safe_original_name)[0]
    filename = f"{base_name}_{uuid.uuid4().hex[:6]}.apk"
    dest_path = upload_dir / filename

    try:
        async with aiofiles.open(dest_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024 * 2):
                await buffer.write(chunk)
        # Conserver une copie à chemin fixe pour le téléchargement direct
        shutil.copyfile(dest_path, upload_dir / "atlas-play.apk")

        # Copie locale de compatibilité
        local_apk = Path(__file__).resolve().parent.parent / "static" / "uploads" / "apk"
        if local_apk != upload_dir:
            try:
                local_apk.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(dest_path, local_apk / filename)
                shutil.copyfile(dest_path, local_apk / "atlas-play.apk")
            except Exception:
                pass
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


