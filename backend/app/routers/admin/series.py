"""
Administration — Séries, saisons et épisodes (dont création par lot).

Code déplacé tel quel depuis l'ancien routers/admin.py (Phase 1).
"""
import secrets
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Episode, Season, Series, User, Video
from app.schemas import (
    BatchAddToExistingSeries,
    BatchSeriesCreate,
    EpisodeCreate,
    EpisodeResponse,
    EpisodeUpdate,
    MessageResponse,
    SeasonCreate,
    SeasonDetailResponse,
    SeasonResponse,
    SeriesCreate,
    SeriesDetailResponse,
    SeriesResponse,
    SeriesUpdate,
)
from app.security import get_current_admin
from app.services.parser_service import parser_service, slugify

router = APIRouter()

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
    title_fr = (data.title_fr or data.title_ar or data.title_en or "").strip()
    if not title_fr:
        raise HTTPException(status_code=400, detail="Veuillez renseigner au moins un titre pour la série.")

    base_slug = slugify(title_fr)
    existing = (await db.execute(select(Series).where(Series.slug == base_slug))).scalar_one_or_none()
    slug = f"{base_slug}-{secrets.token_hex(2)}" if existing else base_slug

    new_series = Series(
        slug=slug,
        title_fr=title_fr,
        title_ar=data.title_ar.strip() if data.title_ar else None,
        title_en=data.title_en.strip() if data.title_en else None,
        synopsis_fr=data.synopsis_fr.strip() if data.synopsis_fr else None,
        synopsis_ar=data.synopsis_ar.strip() if data.synopsis_ar else None,
        synopsis_en=data.synopsis_en.strip() if data.synopsis_en else None,
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
    if data.poster_path is not None and data.poster_path.strip():
        series.poster_path = data.poster_path.strip()
    if data.banner_path is not None and data.banner_path.strip():
        series.banner_path = data.banner_path.strip()
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


