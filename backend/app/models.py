"""
Modèles SQLAlchemy pour l'application VidTele & StreamAdmin.
"""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utc_now() -> datetime:
    """Retourne la date et l'heure actuelle en UTC (sans fuseau explicite pour compatibilité SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    """Utilisateur de l'application (admin ou utilisateur standard)."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="user", nullable=False)  # "super_admin", "admin" ou "user"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ads_free: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_screens: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    max_concurrent_streams: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    invited_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relations
    history_entries: Mapped[List["WatchHistory"]] = relationship("WatchHistory", back_populates="user", cascade="all, delete-orphan")
    favorites: Mapped[List["Favorite"]] = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    active_streams: Mapped[List["ActiveStream"]] = relationship("ActiveStream", back_populates="user", cascade="all, delete-orphan")


class InviteCode(Base):
    """Codes d'invitation générés par un admin pour créer de nouveaux comptes."""
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    used_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    uses_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    @property
    def remaining_uses(self) -> int:
        return max(0, self.max_uses - (self.uses_count or 0))


class MediaItem(Base):
    """
    Film ou Série regroupant une ou plusieurs vidéos Telegram avec métadonnées enrichies.
    Seuls les éléments avec is_published == True sont visibles dans le catalogue mobile.
    """
    __tablename__ = "media_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    media_type: Mapped[str] = mapped_column(String(32), default="movie", nullable=False)  # "movie" ou "series"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)  # Genre principal
    poster_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # URL ou chemin miniature
    backdrop_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # Bannière / arrière-plan
    release_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relations
    videos: Mapped[List["Video"]] = relationship("Video", back_populates="media_item")


class Video(Base):
    """Métadonnées des vidéos synchronisées depuis le canal Telegram privé."""
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_message_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), default="video/mp4", nullable=False)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    views_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    telegram_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    media_item_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("media_items.id", ondelete="SET NULL"), nullable=True, index=True)
    season_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    episode_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relations
    media_item: Mapped[Optional["MediaItem"]] = relationship("MediaItem", back_populates="videos")
    history_entries: Mapped[List["WatchHistory"]] = relationship("WatchHistory", back_populates="video", cascade="all, delete-orphan")
    favorites: Mapped[List["Favorite"]] = relationship("Favorite", back_populates="video", cascade="all, delete-orphan")


class WatchHistory(Base):
    """Historique de visionnage et position de reprise par utilisateur."""
    __tablename__ = "watch_history"
    __table_args__ = (UniqueConstraint("user_id", "video_id", name="uq_user_video_history"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id: Mapped[int] = mapped_column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    position_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_watched_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relations
    user: Mapped["User"] = relationship("User", back_populates="history_entries")
    video: Mapped["Video"] = relationship("Video", back_populates="history_entries")


class Favorite(Base):
    """Vidéos ajoutées en favoris par un utilisateur."""
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "video_id", name="uq_user_video_favorite"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id: Mapped[int] = mapped_column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    # Relations
    user: Mapped["User"] = relationship("User", back_populates="favorites")
    video: Mapped["Video"] = relationship("Video", back_populates="favorites")


class ActiveStream(Base):
    """Sessions de streaming en cours (suivi du nombre de flux simultanés)."""
    __tablename__ = "active_streams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id: Mapped[int] = mapped_column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    session_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relations
    user: Mapped["User"] = relationship("User", back_populates="active_streams")


class SystemSetting(Base):
    """Paramètres système dynamiques persistés en base de données."""
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


# =========================================================================
# Nouveaux Modèles Relationnels StreamAdmin (Séries, Films, Accueil)
# =========================================================================

class Genre(Base):
    """Genres / Catégories (Action, Drame, Comédie, etc.)."""
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name_fr: Mapped[str] = mapped_column(String(128), nullable=False)
    name_ar: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class Collection(Base):
    """Collections et sagas de films (ex: Harry Potter, Star Wars)."""
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    title_fr: Mapped[str] = mapped_column(String(255), nullable=False)
    title_ar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description_fr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    poster_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    banner_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class Series(Base):
    """Série TV ou web-série avec saisons et épisodes."""
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    title_fr: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    title_ar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title_en: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title_original: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    synopsis_fr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synopsis_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synopsis_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    year_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    year_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    age_rating: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ongoing", nullable=False)  # "ongoing", "ended", "canceled"
    trailer_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    poster_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    banner_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    logo_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    tmdb_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)  # "published", "draft", "hidden"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relations
    seasons: Mapped[List["Season"]] = relationship("Season", back_populates="series", cascade="all, delete-orphan", order_by="Season.number")


class Season(Base):
    """Saison d'une série."""
    __tablename__ = "seasons"
    __table_args__ = (UniqueConstraint("series_id", "number", name="uq_series_season_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    series_id: Mapped[int] = mapped_column(Integer, ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title_fr: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title_ar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    poster_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relations
    series: Mapped["Series"] = relationship("Series", back_populates="seasons")
    episodes: Mapped[List["Episode"]] = relationship("Episode", back_populates="season", cascade="all, delete-orphan", order_by="Episode.number")


class Episode(Base):
    """Épisode d'une saison rattaché à une vidéo Telegram."""
    __tablename__ = "episodes"
    __table_args__ = (UniqueConstraint("season_id", "number", name="uq_season_episode_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    season_id: Mapped[int] = mapped_column(Integer, ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    telegram_video_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("videos.id", ondelete="SET NULL"), unique=True, nullable=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title_fr: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title_ar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title_en: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    synopsis_fr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synopsis_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synopsis_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    release_date: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relations
    season: Mapped["Season"] = relationship("Season", back_populates="episodes")
    video: Mapped[Optional["Video"]] = relationship("Video")


class Movie(Base):
    """Film autonome rattaché à une vidéo Telegram."""
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    collection_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("collections.id", ondelete="SET NULL"), nullable=True)
    telegram_video_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("videos.id", ondelete="SET NULL"), unique=True, nullable=True)
    title_fr: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    title_ar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title_en: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title_original: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    synopsis_fr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synopsis_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synopsis_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    age_rating: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trailer_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    poster_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    banner_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    logo_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    tmdb_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)  # "published", "draft", "hidden"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relations
    video: Mapped[Optional["Video"]] = relationship("Video")
    collection: Mapped[Optional["Collection"]] = relationship("Collection")


class HomeRow(Base):
    """Rangées configurables de l'accueil mobile (Hero, Nouveautés, Séries, Films, Genres)."""
    __tablename__ = "home_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    row_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "hero", "recent", "series", "movies", "genre", "collection"
    title_fr: Mapped[str] = mapped_column(String(255), nullable=False)
    title_ar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    genre_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("genres.id", ondelete="SET NULL"), nullable=True)
    collection_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("collections.id", ondelete="SET NULL"), nullable=True)
    limit_items: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class HomeHeroItem(Base):
    """Éléments épinglés dans le carrousel Héro de l'accueil mobile."""
    __tablename__ = "home_hero_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "series" ou "movie"
    content_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class SyncLog(Base):
    """Historique des synchronisations Telegram."""
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    started_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)  # "running", "success", "warning", "failed"
    videos_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    videos_added: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    videos_classified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    """Journal d'audit administratif."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class Device(Base):
    """Appareils connectés des utilisateurs."""
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_type: Mapped[str] = mapped_column(String(32), default="other", nullable=False)
    app_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class TelegramAccount(Base):
    """Comptes Telegram MTProto configurés et reliés (Gestion Multi-Comptes)."""
    __tablename__ = "telegram_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)  # Nom convivial : 'Compte Principal', 'Backup'
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    api_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    api_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    string_session: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    account_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    account_username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    account_first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="idle", nullable=False)  # "connected", "error", "idle"
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    last_tested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

