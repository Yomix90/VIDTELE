"""
Schémas Pydantic pour la validation des données d'entrée et de sortie.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# -------------------------------------------------------------
# Schémas d'Authentification & Tokens
# -------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="Nom d'utilisateur")
    password: str = Field(..., min_length=6, description="Mot de passe")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="Nom d'utilisateur désiré")
    password: str = Field(..., min_length=6, description="Mot de passe robuste")
    invite_code: str = Field(..., min_length=4, max_length=64, description="Code d'invitation obligatoire")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: int
    username: str
    role: str
    ads_free: bool = False


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


# -------------------------------------------------------------
# Schémas Utilisateur
# -------------------------------------------------------------

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    max_concurrent_streams: int
    ads_free: bool = False
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserCreateAdmin(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6)
    role: str = Field(default="user", pattern="^(admin|user)$")
    max_concurrent_streams: int = Field(default=2, ge=1, le=10)
    ads_free: bool = False


class UserUpdateAdmin(BaseModel):
    role: Optional[str] = Field(default=None, pattern="^(admin|user)$")
    is_active: Optional[bool] = None
    max_concurrent_streams: Optional[int] = Field(default=None, ge=1, le=10)
    ads_free: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6)


# -------------------------------------------------------------
# Schémas Monétisation & Publicités (AdMob Rewarded)
# -------------------------------------------------------------

class AdsConfigResponse(BaseModel):
    enabled: bool = True
    min_videos_per_cycle: int = 4
    max_videos_per_cycle: int = 5
    watch_completion_threshold: float = 0.70
    reward_amount: int = 1
    fallback_bypass_enabled: bool = True


class AdAnalyticsEvent(BaseModel):
    event_type: str = Field(..., description="prompt_shown | reward_earned | ad_dismissed | ad_failed")
    video_id: Optional[str] = None
    cycle_watched_count: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# -------------------------------------------------------------
# Schémas Codes d'Invitation
# -------------------------------------------------------------

class InviteCodeCreate(BaseModel):
    code: Optional[str] = Field(None, max_length=64, description="Code personnalisé (optionnel, ex: ATLAS500). Si absent, généré automatiquement.")
    max_uses: int = Field(default=1, ge=1, le=100000, description="Nombre maximum d'utilisations autorisées (ex: 1, 100, 200, 500...)")
    expires_in_days: Optional[int] = Field(default=30, ge=1, le=3650, description="Durée de validité en jours (None si permanent)")
    description: Optional[str] = Field(None, max_length=255, description="Description ou étiquette (ex: Campagne Telegram 500 places)")


class InviteCodeResponse(BaseModel):
    id: int
    code: str
    description: Optional[str] = None
    max_uses: int = 1
    uses_count: int = 0
    remaining_uses: Optional[int] = None
    is_used: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    created_by_id: Optional[int] = None
    used_by_id: Optional[int] = None
    used_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------
# Schémas Vidéos & Catégories
# -------------------------------------------------------------

class VideoResponse(BaseModel):
    id: int
    telegram_message_id: int
    title: str
    caption: Optional[str] = None
    category: Optional[str] = None
    duration_seconds: int
    file_size_bytes: int
    mime_type: str
    thumbnail_path: Optional[str] = None
    file_name: Optional[str] = None
    views_count: int
    telegram_date: datetime
    is_published: bool = False
    media_item_id: Optional[int] = None
    season_number: int = 1
    episode_number: int = 1
    episode_title: Optional[str] = None
    # Champs contextuels utilisateur (calculés dynamiquement)
    is_favorite: bool = False
    watch_progress_seconds: float = 0.0
    is_completed: bool = False

    model_config = ConfigDict(from_attributes=True)


class VideoListResponse(BaseModel):
    items: list[VideoResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class CategoryItem(BaseModel):
    name: str
    count: int


# -------------------------------------------------------------
# Schémas Films, Séries & Organisation des Vidéos
# -------------------------------------------------------------

class MediaItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Titre du film ou de la série")
    media_type: str = Field(default="movie", pattern="^(movie|series)$", description="'movie' ou 'series'")
    description: Optional[str] = Field(default=None, description="Synopsis ou résumé")
    category: Optional[str] = Field(default=None, description="Genre principal (ex: Action, Drame)")
    poster_url: Optional[str] = Field(default=None, description="URL de l'affiche")
    backdrop_url: Optional[str] = Field(default=None, description="URL de l'image d'arrière-plan")
    release_year: Optional[int] = Field(default=None, ge=1900, le=2100, description="Année de sortie")
    rating: Optional[float] = Field(default=None, ge=0.0, le=10.0, description="Note (ex: 8.5)")
    is_published: bool = Field(default=False, description="Actif et visible sur l'application mobile")
    raw_video_id: Optional[int] = Field(default=None, description="ID d'une vidéo brute à lier immédiatement")


class MediaItemUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    media_type: Optional[str] = Field(default=None, pattern="^(movie|series)$")
    description: Optional[str] = None
    category: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    release_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    rating: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    is_published: Optional[bool] = None


class EpisodeAssignRequest(BaseModel):
    video_id: int = Field(..., description="ID de la vidéo brute à rattacher")
    season_number: int = Field(default=1, ge=1, description="Numéro de saison")
    episode_number: int = Field(default=1, ge=1, description="Numéro d'épisode")
    episode_title: Optional[str] = Field(default=None, description="Titre spécifique de l'épisode")


class MediaItemVideoResponse(BaseModel):
    id: int
    telegram_message_id: int
    title: str
    file_name: Optional[str] = None
    duration_seconds: int
    file_size_bytes: int
    season_number: int = 1
    episode_number: int = 1
    episode_title: Optional[str] = None
    thumbnail_path: Optional[str] = None
    is_published: bool

    model_config = ConfigDict(from_attributes=True)


class MediaItemResponse(BaseModel):
    id: int
    title: str
    media_type: str
    description: Optional[str] = None
    category: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    release_year: Optional[int] = None
    rating: Optional[float] = None
    is_published: bool
    video_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MediaItemDetailResponse(MediaItemResponse):
    videos: list[MediaItemVideoResponse] = []


class RawVideoItemResponse(BaseModel):
    id: int
    telegram_message_id: int
    title: str
    file_name: Optional[str] = None
    duration_seconds: int
    file_size_bytes: int
    mime_type: str
    thumbnail_path: Optional[str] = None
    telegram_date: datetime
    is_published: bool
    media_item_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class SyncStatusResponse(BaseModel):
    status: str
    added: int = 0
    updated: int = 0
    total_messages: int = 0
    error: Optional[str] = None


# -------------------------------------------------------------
# Schémas Suivi, Historique & Favoris
# -------------------------------------------------------------

class ProgressUpdateRequest(BaseModel):
    position_seconds: Optional[float] = Field(None, ge=0.0, description="Position de lecture en secondes")
    progress_seconds: Optional[float] = Field(None, ge=0.0, description="Position alternative")
    completed: bool = Field(default=False, description="Indique si la vidéo est terminée")

    def get_position(self) -> float:
        if self.position_seconds is not None:
            return self.position_seconds
        if self.progress_seconds is not None:
            return self.progress_seconds
        return 0.0


class WatchHistoryItem(BaseModel):
    id: int
    video_id: int
    video_title: str
    video_thumbnail: Optional[str] = None
    duration_seconds: int
    position_seconds: float
    progress_seconds: Optional[float] = None
    last_position_seconds: Optional[float] = None
    completed: bool
    is_completed: Optional[bool] = None
    last_watched_at: datetime
    updated_at: Optional[datetime] = None
    video: Optional[VideoResponse] = None


class FavoriteItem(BaseModel):
    id: int
    video_id: int
    video_title: str
    video_thumbnail: Optional[str] = None
    duration_seconds: int
    created_at: datetime
    video: Optional[VideoResponse] = None


# -------------------------------------------------------------
# Schémas Statistiques Administrateur
# -------------------------------------------------------------

class CacheStats(BaseModel):
    total_bytes: int
    total_mb: float
    total_gb: float
    max_gb: float
    percent_used: float
    file_count: int


class StreamStats(BaseModel):
    current_active: int
    max_global: int
    max_per_user: int


class StreamingSettingsUpdate(BaseModel):
    max_concurrent_global: int = Field(..., ge=1, le=1000, description="Limite globale de flux simultanés")
    max_concurrent_per_user: int = Field(..., ge=1, le=20, description="Limite par utilisateur")


class BenchmarkRunRequest(BaseModel):
    concurrency: int = Field(default=20, ge=1, le=300, description="Nombre de flux simultanés à simuler")
    duration_seconds: float = Field(default=5.0, ge=1.0, le=60.0, description="Durée du test en secondes")
    mode: str = Field(default="burst", description="burst ou playback")
    video_id: Optional[int] = Field(default=None, description="ID spécifique de la vidéo (optionnel)")



class AdminStatsResponse(BaseModel):
    total_videos: int
    total_views: int
    total_duration_seconds: int
    total_users: int
    active_users: int
    total_invites: int
    active_invites: int
    used_invites: int
    cache: CacheStats
    streams: StreamStats


# -------------------------------------------------------------
# Schémas Réponses Générales
# -------------------------------------------------------------

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


# =============================================================
# Nouveaux Schémas StreamAdmin (Séries, Saisons, Épisodes, Films)
# =============================================================

class GenreResponse(BaseModel):
    id: int
    slug: str
    name_fr: str
    name_ar: Optional[str] = None
    icon: Optional[str] = None
    order_index: int = 0

    model_config = ConfigDict(from_attributes=True)


class EpisodeResponse(BaseModel):
    id: int
    season_id: int
    number: int
    title_fr: Optional[str] = None
    title_ar: Optional[str] = None
    synopsis_fr: Optional[str] = None
    duration_sec: Optional[int] = None
    thumbnail_path: Optional[str] = None
    telegram_video_id: Optional[int] = None
    order_index: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EpisodeCreate(BaseModel):
    number: int = Field(..., ge=0)
    title_fr: Optional[str] = None
    title_ar: Optional[str] = None
    synopsis_fr: Optional[str] = None
    duration_sec: Optional[int] = None
    thumbnail_path: Optional[str] = None
    telegram_video_id: Optional[int] = None


class SeasonResponse(BaseModel):
    id: int
    series_id: int
    number: int
    title_fr: Optional[str] = None
    title_ar: Optional[str] = None
    poster_path: Optional[str] = None
    order_index: int = 0
    episode_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class SeasonDetailResponse(SeasonResponse):
    episodes: list[EpisodeResponse] = []


class SeasonCreate(BaseModel):
    number: int = Field(..., ge=0)
    title_fr: Optional[str] = None
    title_ar: Optional[str] = None
    poster_path: Optional[str] = None


class SeriesResponse(BaseModel):
    id: int
    slug: str
    title_fr: str
    title_ar: Optional[str] = None
    title_en: Optional[str] = None
    synopsis_fr: Optional[str] = None
    synopsis_ar: Optional[str] = None
    synopsis_en: Optional[str] = None
    year_start: Optional[int] = None
    rating: Optional[float] = None
    status: str = "ongoing"
    poster_path: Optional[str] = None
    banner_path: Optional[str] = None
    is_featured: bool = False
    visibility: str = "draft"
    seasons_count: int = 0
    episodes_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SeriesDetailResponse(SeriesResponse):
    seasons: list[SeasonDetailResponse] = []


class TopSeriesItem(BaseModel):
    id: int
    rank: int
    title: str
    title_fr: str
    title_ar: Optional[str] = None
    title_en: Optional[str] = None
    synopsis: Optional[str] = None
    poster_path: Optional[str] = None
    banner_path: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[float] = None
    seasons_count: int = 0
    episodes_count: int = 0
    views_last_7d: int = 0
    first_video_id: Optional[int] = None


class HomeHeroItem(BaseModel):
    id: int
    title: str
    title_fr: str
    title_ar: Optional[str] = None
    title_en: Optional[str] = None
    synopsis: Optional[str] = None
    poster_path: Optional[str] = None
    banner_path: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[float] = None
    category: str = "Série"
    episodes_count: int = 0
    first_video_id: Optional[int] = None


class HomeGenreSection(BaseModel):
    name: str
    count: int = 0
    items: List[VideoResponse] = []


class HomeScreenResponse(BaseModel):
    hero: List[HomeHeroItem] = []
    top5: List[TopSeriesItem] = []
    continue_watching: List[VideoResponse] = []
    new: List[VideoResponse] = []
    new_releases: List[VideoResponse] = []
    trending: List[VideoResponse] = []
    genres: List[HomeGenreSection] = []


class FeedItemResponse(BaseModel):
    id: int
    telegram_message_id: int
    title: str
    series_id: Optional[int] = None
    series_title: Optional[str] = None
    season_number: int = 1
    episode_number: int = 1
    episode_title: Optional[str] = None
    caption: Optional[str] = None
    category: str = "Général"
    duration_seconds: int = 0
    file_size_bytes: int = 0
    mime_type: str = "video/mp4"
    thumbnail_path: Optional[str] = None
    views_count: int = 0
    is_favorite: bool = False
    watch_progress_seconds: float = 0.0
    is_completed: bool = False
    stream_url: str
    next_episode_video_id: Optional[int] = None


class FeedResponse(BaseModel):
    items: List[FeedItemResponse] = []
    next_cursor: Optional[int] = None
    has_more: bool = False


class SeriesCreate(BaseModel):
    title_fr: Optional[str] = None
    title_ar: Optional[str] = None
    title_en: Optional[str] = None
    synopsis_fr: Optional[str] = None
    synopsis_ar: Optional[str] = None
    synopsis_en: Optional[str] = None
    year_start: Optional[int] = None
    rating: Optional[float] = None
    status: str = "ongoing"
    poster_path: Optional[str] = None
    banner_path: Optional[str] = None
    visibility: str = "draft"
    is_featured: bool = False


class MovieResponse(BaseModel):
    id: int
    slug: str
    title_fr: str
    title_ar: Optional[str] = None
    synopsis_fr: Optional[str] = None
    year: Optional[int] = None
    duration_sec: Optional[int] = None
    rating: Optional[float] = None
    poster_path: Optional[str] = None
    banner_path: Optional[str] = None
    is_featured: bool = False
    visibility: str = "draft"
    telegram_video_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MovieCreate(BaseModel):
    title_fr: str = Field(..., min_length=1, max_length=255)
    title_ar: Optional[str] = None
    synopsis_fr: Optional[str] = None
    year: Optional[int] = None
    duration_sec: Optional[int] = None
    rating: Optional[float] = None
    poster_path: Optional[str] = None
    banner_path: Optional[str] = None
    telegram_video_id: Optional[int] = None
    visibility: str = "draft"
    is_featured: bool = False


class HomeRowResponse(BaseModel):
    id: int
    row_type: str
    title_fr: str
    title_ar: Optional[str] = None
    limit_items: int = 20
    is_active: bool = True
    order_index: int = 0

    model_config = ConfigDict(from_attributes=True)


class HomeRowCreate(BaseModel):
    row_type: str
    title_fr: str
    title_ar: Optional[str] = None
    limit_items: int = 20
    is_active: bool = True
    order_index: int = 0


# -------------------------------------------------------------
# Schémas Mises à jour Application Mobile (Atlas Play)
# -------------------------------------------------------------

class AppUpdateInfo(BaseModel):
    """Informations de version renvoyées à l'application mobile Flutter."""
    latest_version: str = "1.0.0"
    min_version: str = "1.0.0"
    download_url: Optional[str] = None
    title: str = "Mise à jour disponible"
    release_notes: Optional[str] = None
    force_update: bool = False
    has_update: bool = False


class AppUpdateConfig(BaseModel):
    """Configuration soumise par l'administrateur dans le Dashboard."""
    latest_version: str = Field(..., description="Dernière version disponible (ex: 1.1.0)")
    min_version: str = Field(..., description="Version minimale obligatoire (ex: 1.0.0)")
    download_url: Optional[str] = Field(None, description="Lien de téléchargement direct de l'APK")
    title: Optional[str] = Field("Nouvelle mise à jour disponible", description="Titre du dialogue")
    release_notes: Optional[str] = Field(None, description="Notes de mise à jour (changements)")
    force_update: bool = Field(False, description="Bloquer l'utilisation de l'app si non mis à jour")


# -------------------------------------------------------------
# Schémas Multi-Comptes et Diagnostics Telegram MTProto
# -------------------------------------------------------------

class TelegramAccountResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    account_user_id: Optional[int] = None
    account_username: Optional[str] = None
    account_first_name: Optional[str] = None
    is_active: bool = False
    status: str = "idle"
    last_error: Optional[str] = None
    created_at: datetime
    last_tested_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TelegramAccountCreate(BaseModel):
    name: str = Field(..., description="Nom convivial du compte (ex: Compte Principal, Backup)")
    string_session: str = Field(..., description="Clé de session StringSession Telethon")
    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    make_active: bool = True


class TelegramPhoneAuthRequest(BaseModel):
    phone: str = Field(..., description="Numéro de téléphone au format international (ex: +33612345678)")
    api_id: Optional[int] = None
    api_hash: Optional[str] = None


class TelegramPhoneVerifyRequest(BaseModel):
    phone: str
    code: str = Field(..., description="Code de vérification reçu sur Telegram")
    phone_code_hash: str
    password_2fa: Optional[str] = None
    account_name: Optional[str] = "Nouveau Compte"
    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    make_active: bool = True


class TelegramConfigUpdateRequest(BaseModel):
    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    channel_id: Optional[str] = None


# -------------------------------------------------------------
# Schémas Modifications Séries, Films, Épisodes & Lots
# -------------------------------------------------------------

class SeriesUpdate(BaseModel):
    title_fr: Optional[str] = None
    title_ar: Optional[str] = None
    title_en: Optional[str] = None
    synopsis_fr: Optional[str] = None
    synopsis_ar: Optional[str] = None
    synopsis_en: Optional[str] = None
    year_start: Optional[int] = None
    rating: Optional[float] = None
    poster_path: Optional[str] = None
    banner_path: Optional[str] = None
    status: Optional[str] = None
    visibility: Optional[str] = None


class MovieUpdate(BaseModel):
    title_fr: Optional[str] = None
    title_ar: Optional[str] = None
    title_en: Optional[str] = None
    synopsis_fr: Optional[str] = None
    synopsis_ar: Optional[str] = None
    synopsis_en: Optional[str] = None
    year: Optional[int] = None
    duration_sec: Optional[int] = None
    rating: Optional[float] = None
    poster_path: Optional[str] = None
    banner_path: Optional[str] = None
    telegram_video_id: Optional[int] = None
    visibility: Optional[str] = None


class EpisodeUpdate(BaseModel):
    number: Optional[int] = None
    title_fr: Optional[str] = None
    title_ar: Optional[str] = None
    title_en: Optional[str] = None
    synopsis_fr: Optional[str] = None
    synopsis_ar: Optional[str] = None
    synopsis_en: Optional[str] = None
    duration_sec: Optional[int] = None
    season_id: Optional[int] = None
    telegram_video_id: Optional[int] = None


class BatchSeriesCreate(BaseModel):
    title_fr: str
    title_ar: Optional[str] = None
    title_en: Optional[str] = None
    synopsis_fr: Optional[str] = None
    poster_path: Optional[str] = None
    banner_path: Optional[str] = None
    video_ids: List[int]
    auto_detect: bool = True
    visibility: str = "published"


class BatchAddToExistingSeries(BaseModel):
    series_id: int
    video_ids: List[int]
    season_id: Optional[int] = None
    auto_detect: bool = True
    publish: bool = True


class GeminiTranslateRequest(BaseModel):
    title: Optional[str] = None
    title_fr: Optional[str] = None
    title_ar: Optional[str] = None
    title_en: Optional[str] = None
    synopsis: Optional[str] = None
    synopsis_fr: Optional[str] = None
    synopsis_ar: Optional[str] = None
    synopsis_en: Optional[str] = None
    content_type: str = "series"


class GeminiConfigRequest(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None


class BatchDeleteVideosRequest(BaseModel):
    video_ids: List[int]
    delete_from_telegram: bool = True


