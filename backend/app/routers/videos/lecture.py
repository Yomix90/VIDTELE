"""
Vidéos — Lecture : détail d'une vidéo, miniature, jetons de flux, streaming Range et arrêt.

Code déplacé tel quel depuis l'ancien routers/videos.py (Phase 1).
"""
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Favorite, User, Video, WatchHistory
from app.schemas import (
    VideoResponse,
)
from app.security import (
    create_stream_token,
    decode_stream_url_token,
    get_client_ip,
    get_current_active_user,
)
from app.services.stream_manager import stream_manager
from app.services.stream_service import stream_service


from app.repositories.videos import trouver_video

router = APIRouter(prefix="/api/videos", tags=["Vidéos"])

@router.get("/{video_id:int}", response_model=VideoResponse)
async def get_video_detail(
    video_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère les détails complets d'une vidéo spécifique (réservé aux vidéos publiées pour les non-admins).
    """
    stmt = select(Video).where(Video.id == video_id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if not video or (not video.is_published and current_user.role != "admin"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vidéo introuvable ou non publiée",
        )

    # Favori
    fav_stmt = select(Favorite.id).where(
        Favorite.user_id == current_user.id,
        Favorite.video_id == video.id,
    )
    is_fav = (await db.execute(fav_stmt)).scalar_one_or_none() is not None

    # Historique
    hist_stmt = select(WatchHistory).where(
        WatchHistory.user_id == current_user.id,
        WatchHistory.video_id == video.id,
    )
    hist = (await db.execute(hist_stmt)).scalar_one_or_none()

    pos = hist.position_seconds if hist else 0.0
    completed = hist.completed if hist else False

    return VideoResponse(
        id=video.id,
        telegram_message_id=video.telegram_message_id,
        title=video.title,
        caption=video.caption,
        category=video.category,
        duration_seconds=video.duration_seconds,
        file_size_bytes=video.file_size_bytes,
        mime_type=video.mime_type,
        thumbnail_path=video.thumbnail_path,
        file_name=video.file_name,
        views_count=video.views_count,
        telegram_date=video.telegram_date,
        is_published=video.is_published,
        media_item_id=video.media_item_id,
        season_number=video.season_number,
        episode_number=video.episode_number,
        episode_title=video.episode_title,
        is_favorite=is_fav,
        watch_progress_seconds=pos,
        is_completed=completed,
    )


@router.get("/{video_id:int}/thumbnail")
async def get_video_thumbnail(video_id: int, db: AsyncSession = Depends(get_db)):
    """
    Renvoie le fichier image de la miniature avec mise en cache HTTP.
    """
    # 1. Vérifier si video_id correspond à un id de vidéo ou telegram_message_id (priorité absolue à l'ID primaire)
    video = await trouver_video(db, video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Miniature introuvable")

    # Nom de fichier sur le disque
    filename = f"thumb_{video.telegram_message_id}.jpg"
    disk_path = Path(settings.THUMBNAILS_DIR) / filename

    if not disk_path.exists():
        if video.thumbnail_path:
            clean_thumb = video.thumbnail_path.strip()
            if clean_thumb.startswith("http://") or clean_thumb.startswith("https://"):
                return RedirectResponse(url=clean_thumb)
            if clean_thumb.startswith("/static/"):
                disk_static = Path(__file__).resolve().parent.parent / clean_thumb.lstrip("/")
                if disk_static.exists():
                    return FileResponse(
                        path=disk_static,
                        headers={"Cache-Control": "public, max-age=86400"},
                    )
        # Générer un placeholder SVG simple si la miniature n'existe pas encore sur disque
        svg_content = """<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">
            <rect width="320" height="180" fill="#1e293b"/>
            <polygon points="135,65 195,90 135,115" fill="#38bdf8"/>
        </svg>"""
        return Response(content=svg_content, media_type="image/svg+xml")

    return FileResponse(
        path=disk_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.api_route("/{video_id:int}/stream-token", methods=["GET", "POST"])
async def get_stream_token(
    video_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Génère un jeton signé temporaire pour le lecteur vidéo mobile.
    Permet la lecture sans avoir à configurer des en-têtes Authorization complexes dans le player.
    """
    video = await trouver_video(db, video_id)

    if not video or (not video.is_published and current_user.role != "admin"):
        raise HTTPException(status_code=404, detail="Vidéo introuvable ou non publiée")

    token = create_stream_token(user_id=current_user.id, video_id=video.id)
    return {
        "video_id": video.id,
        "stream_token": token,
        "stream_url": f"/api/videos/{video.id}/stream?token={token}",
    }


@router.get("/{video_id:int}/stream")
async def stream_video(
    video_id: int,
    request: Request,
    token: Optional[str] = Query(None, description="Jeton de flux temporaire ou JWT d'accès"),
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint de streaming vidéo avec support complet des requêtes HTTP Range (206 Partial Content).
    Gère l'authentification par paramètre ?token= ou par en-tête Authorization: Bearer.
    """
    # 1. Vérification de l'authentification (Query param, Header Authorization ou Cookie session admin)
    raw_token = token
    if not raw_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header.replace("Bearer ", "").strip()
        elif request.cookies.get("admin_token") or request.cookies.get("access_token"):
            raw_token = request.cookies.get("admin_token") or request.cookies.get("access_token")

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton d'authentification requis pour le streaming (header, cookie ou ?token=)",
        )


    # Décodage et validation du token ('stream' lié à la vidéo, ou 'access' des anciennes versions de l'app)
    payload = decode_stream_url_token(raw_token)

    user_id_str = payload.get("sub")
    if not user_id_str or not user_id_str.isdigit():
        raise HTTPException(status_code=401, detail="Jeton de streaming corrompu")

    user_id = int(user_id_str)
    user_stmt = select(User).where(User.id == user_id)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou compte désactivé")

    # 2. Récupération de la vidéo (priorité absolue à l'ID primaire Video.id)
    video = await trouver_video(db, video_id)

    if not video or (not video.is_published and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Vidéo introuvable ou non publiée")

    # Un jeton de flux n'ouvre que la vidéo pour laquelle il a été émis
    if payload.get("type") == "stream" and payload.get("vid") != video.id:
        raise HTTPException(status_code=403, detail="Jeton de flux non valable pour cette vidéo")

    # 3. Contrôle et enregistrement des quotas de flux simultanés (anti-abus)
    client_ip = get_client_ip(request)
    # On utilise un identifiant de session dérivé du token ou personnalisé pour le suivi précis de chaque lecteur
    custom_session = request.headers.get("X-Session-ID") or request.query_params.get("session_id")
    if custom_session:
        session_id = custom_session[:64]
    else:
        session_id = raw_token[-32:] if len(raw_token) >= 32 else raw_token
    await stream_manager.register_stream_access(user, video.id, session_id, client_ip, db)


    # 4. Une vue par lecture (et non par requête Range) + préchauffage des épisodes suivants
    range_header = request.headers.get("Range")
    debut_de_fichier = not range_header or range_header.replace(" ", "").startswith("bytes=0-")
    if debut_de_fichier and stream_manager.nouvelle_vue(user.id, video.id):
        video.views_count += 1
        await db.commit()
        asyncio.create_task(stream_service.prewarm_next_episodes_in_series(video))

    # 5. Délégation au moteur de streaming Range 206
    return await stream_service.create_streaming_response(video, range_header)


@router.post("/{video_id:int}/stream/stop")
async def stop_stream(
    video_id: int,
    request: Request,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Libère immédiatement le quota de flux simultané lorsqu'un lecteur vidéo termine ou se ferme.
    """
    raw_token = token
    if not raw_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header.replace("Bearer ", "").strip()

    if raw_token:
        session_id = raw_token[-32:] if len(raw_token) >= 32 else raw_token
        await stream_manager.release_stream_session(session_id, db)

    return {"status": "released", "video_id": video_id}




