"""
Schémas Pydantic pour la validation des données d'entrée et de sortie.
"""
from datetime import datetime
from typing import Optional
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
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserCreateAdmin(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6)
    role: str = Field(default="user", pattern="^(admin|user)$")
    max_concurrent_streams: int = Field(default=2, ge=1, le=10)


class UserUpdateAdmin(BaseModel):
    role: Optional[str] = Field(default=None, pattern="^(admin|user)$")
    is_active: Optional[bool] = None
    max_concurrent_streams: Optional[int] = Field(default=None, ge=1, le=10)
    password: Optional[str] = Field(default=None, min_length=6)


# -------------------------------------------------------------
# Schémas Codes d'Invitation
# -------------------------------------------------------------

class InviteCodeCreate(BaseModel):
    expires_in_days: Optional[int] = Field(default=7, ge=1, le=365, description="Durée de validité en jours")


class InviteCodeResponse(BaseModel):
    id: int
    code: str
    is_used: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    created_by_id: Optional[int] = None
    used_by_id: Optional[int] = None

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
    position_seconds: float = Field(..., ge=0.0, description="Position de lecture en secondes")
    completed: bool = Field(default=False, description="Indique si la vidéo est terminée")


class WatchHistoryItem(BaseModel):
    id: int
    video_id: int
    video_title: str
    video_thumbnail: Optional[str] = None
    duration_seconds: int
    position_seconds: float
    completed: bool
    last_watched_at: datetime


class FavoriteItem(BaseModel):
    id: int
    video_id: int
    video_title: str
    video_thumbnail: Optional[str] = None
    duration_seconds: int
    created_at: datetime


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
