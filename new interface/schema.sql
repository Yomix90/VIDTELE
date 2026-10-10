-- =====================================================
-- StreamAdmin
-- Schéma SQLite initial
-- Compatible à terme avec PostgreSQL via Alembic
-- =====================================================

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------
-- Paramètres généraux de l'application
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- -----------------------------------------------------
-- Utilisateurs : admins et utilisateurs de l'app mobile
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    email TEXT UNIQUE COLLATE NOCASE,
    full_name TEXT,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('super_admin', 'admin', 'user')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    max_screens INTEGER NOT NULL DEFAULT 1 CHECK(max_screens >= 1),
    expires_at TEXT,
    invited_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    last_login_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_role_active ON users(role, is_active);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- -----------------------------------------------------
-- Appareils connectés des utilisateurs
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_name TEXT NOT NULL,
    device_type TEXT NOT NULL DEFAULT 'other' CHECK(device_type IN ('android', 'ios', 'web', 'desktop', 'other')),
    app_version TEXT,
    ip_address TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    last_seen_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_devices_user ON devices(user_id);
CREATE INDEX IF NOT EXISTS idx_devices_active ON devices(is_active);

-- -----------------------------------------------------
-- Codes d'invitation
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS invitations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    max_uses INTEGER NOT NULL DEFAULT 1 CHECK(max_uses > 0),
    used_count INTEGER NOT NULL DEFAULT 0 CHECK(used_count >= 0),
    expires_at TEXT,
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin', 'user')),
    account_validity_days INTEGER,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'revoked')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_invitations_status ON invitations(status);
CREATE INDEX IF NOT EXISTS idx_invitations_code ON invitations(code);

-- -----------------------------------------------------
-- Comptes Telegram connectés
-- Les secrets ne sont jamais stockés en clair dans la base
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS telegram_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT,
    api_id INTEGER NOT NULL,
    api_hash_encrypted TEXT NOT NULL,
    phone_encrypted TEXT NOT NULL,
    session_encrypted TEXT,
    status TEXT NOT NULL DEFAULT 'disconnected' CHECK(status IN (
        'connected',
        'disconnected',
        'expired',
        'pending_code',
        'pending_password'
    )),
    first_name TEXT,
    last_name TEXT,
    username TEXT,
    connected_at TEXT,
    last_check_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- -----------------------------------------------------
-- Canaux ou groupes Telegram utilisés comme sources
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS telegram_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES telegram_accounts(id) ON DELETE CASCADE,
    telegram_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    username TEXT,
    type TEXT NOT NULL DEFAULT 'channel' CHECK(type IN ('channel', 'group', 'supergroup')),
    is_source INTEGER NOT NULL DEFAULT 1 CHECK(is_source IN (0, 1)),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    listen_realtime INTEGER NOT NULL DEFAULT 0 CHECK(listen_realtime IN (0, 1)),
    videos_count INTEGER NOT NULL DEFAULT 0,
    last_sync_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(account_id, telegram_id)
);

CREATE INDEX IF NOT EXISTS idx_channels_account ON telegram_channels(account_id);
CREATE INDEX IF NOT EXISTS idx_channels_active_source ON telegram_channels(is_active, is_source);

-- -----------------------------------------------------
-- Vidéos brutes détectées dans Telegram
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS telegram_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL REFERENCES telegram_channels(id) ON DELETE CASCADE,
    message_id INTEGER NOT NULL,
    file_unique_id TEXT,
    file_name TEXT,
    caption TEXT,
    duration_sec INTEGER,
    size_bytes INTEGER,
    mime_type TEXT,
    thumbnail_path TEXT,
    status TEXT NOT NULL DEFAULT 'unclassified' CHECK(status IN (
        'unclassified',
        'proposed',
        'classified',
        'ignored'
    )),
    detected_kind TEXT CHECK(detected_kind IN ('series', 'movie')),
    detected_title TEXT,
    detected_season INTEGER,
    detected_episode INTEGER,
    detected_confidence REAL,
    classified_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(channel_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_telegram_videos_channel ON telegram_videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_telegram_videos_status ON telegram_videos(status);
CREATE INDEX IF NOT EXISTS idx_telegram_videos_detected ON telegram_videos(detected_kind, detected_title);
CREATE INDEX IF NOT EXISTS idx_telegram_videos_file_unique ON telegram_videos(file_unique_id);

-- -----------------------------------------------------
-- Collections / sagas de films
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title_fr TEXT NOT NULL,
    title_ar TEXT,
    description_fr TEXT,
    description_ar TEXT,
    poster_path TEXT,
    banner_path TEXT,
    order_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_collections_order ON collections(order_index);

-- -----------------------------------------------------
-- Genres / catégories
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name_fr TEXT NOT NULL,
    name_ar TEXT,
    icon TEXT,
    order_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_genres_order ON genres(order_index);

-- -----------------------------------------------------
-- Séries
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title_fr TEXT NOT NULL,
    title_ar TEXT,
    title_original TEXT,
    synopsis_fr TEXT,
    synopsis_ar TEXT,
    year_start INTEGER,
    year_end INTEGER,
    country TEXT,
    language TEXT,
    age_rating TEXT,
    rating REAL CHECK(rating >= 0 AND rating <= 10),
    status TEXT NOT NULL DEFAULT 'ongoing' CHECK(status IN ('ongoing', 'ended', 'canceled')),
    trailer_url TEXT,
    poster_path TEXT,
    banner_path TEXT,
    logo_path TEXT,
    tmdb_id INTEGER,
    is_featured INTEGER NOT NULL DEFAULT 0 CHECK(is_featured IN (0, 1)),
    visibility TEXT NOT NULL DEFAULT 'draft' CHECK(visibility IN ('published', 'draft', 'hidden')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_series_visibility_featured ON series(visibility, is_featured);
CREATE INDEX IF NOT EXISTS idx_series_title_fr ON series(title_fr);
CREATE INDEX IF NOT EXISTS idx_series_tmdb ON series(tmdb_id);

-- -----------------------------------------------------
-- Saisons
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    number INTEGER NOT NULL CHECK(number >= 0),
    title_fr TEXT,
    title_ar TEXT,
    poster_path TEXT,
    order_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(series_id, number)
);

CREATE INDEX IF NOT EXISTS idx_seasons_series_order ON seasons(series_id, order_index);

-- -----------------------------------------------------
-- Épisodes
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    telegram_video_id INTEGER UNIQUE REFERENCES telegram_videos(id) ON DELETE SET NULL,
    number INTEGER NOT NULL CHECK(number >= 0),
    title_fr TEXT,
    title_ar TEXT,
    synopsis_fr TEXT,
    synopsis_ar TEXT,
    duration_sec INTEGER,
    thumbnail_path TEXT,
    release_date TEXT,
    order_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(season_id, number)
);

CREATE INDEX IF NOT EXISTS idx_episodes_season_order ON episodes(season_id, order_index);
CREATE INDEX IF NOT EXISTS idx_episodes_telegram_video ON episodes(telegram_video_id);

-- -----------------------------------------------------
-- Films
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    collection_id INTEGER REFERENCES collections(id) ON DELETE SET NULL,
    telegram_video_id INTEGER UNIQUE REFERENCES telegram_videos(id) ON DELETE SET NULL,
    title_fr TEXT NOT NULL,
    title_ar TEXT,
    title_original TEXT,
    synopsis_fr TEXT,
    synopsis_ar TEXT,
    year INTEGER,
    duration_sec INTEGER,
    country TEXT,
    language TEXT,
    age_rating TEXT,
    rating REAL CHECK(rating >= 0 AND rating <= 10),
    trailer_url TEXT,
    poster_path TEXT,
    banner_path TEXT,
    logo_path TEXT,
    tmdb_id INTEGER,
    position INTEGER,
    is_featured INTEGER NOT NULL DEFAULT 0 CHECK(is_featured IN (0, 1)),
    visibility TEXT NOT NULL DEFAULT 'draft' CHECK(visibility IN ('published', 'draft', 'hidden')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_movies_visibility_featured ON movies(visibility, is_featured);
CREATE INDEX IF NOT EXISTS idx_movies_collection_position ON movies(collection_id, position);
CREATE INDEX IF NOT EXISTS idx_movies_title_fr ON movies(title_fr);
CREATE INDEX IF NOT EXISTS idx_movies_tmdb ON movies(tmdb_id);

-- -----------------------------------------------------
-- Relations séries / genres
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS series_genres (
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
    PRIMARY KEY(series_id, genre_id)
);

CREATE INDEX IF NOT EXISTS idx_series_genres_genre ON series_genres(genre_id);

-- -----------------------------------------------------
-- Relations films / genres
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS movie_genres (
    movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
    PRIMARY KEY(movie_id, genre_id)
);

CREATE INDEX IF NOT EXISTS idx_movie_genres_genre ON movie_genres(genre_id);

-- -----------------------------------------------------
-- Rangées configurables de l'accueil mobile
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS home_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    row_type TEXT NOT NULL CHECK(row_type IN (
        'hero',
        'recent',
        'series',
        'movies',
        'genre',
        'collection',
        'continue',
        'featured'
    )),
    title_fr TEXT NOT NULL,
    title_ar TEXT,
    genre_id INTEGER REFERENCES genres(id) ON DELETE SET NULL,
    collection_id INTEGER REFERENCES collections(id) ON DELETE SET NULL,
    limit_items INTEGER NOT NULL DEFAULT 20 CHECK(limit_items > 0),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    order_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_home_rows_active_order ON home_rows(is_active, order_index);

-- -----------------------------------------------------
-- Éléments du carrousel héro
-- content_type + content_id est volontairement polymorphe
-- L'intégrité est garantie côté application
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS home_hero_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type TEXT NOT NULL CHECK(content_type IN ('series', 'movie')),
    content_id INTEGER NOT NULL,
    order_index INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_home_hero_active_order ON home_hero_items(is_active, order_index);

-- -----------------------------------------------------
-- Progression de visionnage
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS watch_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content_type TEXT NOT NULL CHECK(content_type IN ('series', 'movie')),
    content_id INTEGER NOT NULL,
    episode_id INTEGER REFERENCES episodes(id) ON DELETE CASCADE,
    position_seconds INTEGER NOT NULL DEFAULT 0 CHECK(position_seconds >= 0),
    duration_seconds INTEGER NOT NULL DEFAULT 0 CHECK(duration_seconds >= 0),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Un seul état de progression par utilisateur, contenu et épisode
CREATE UNIQUE INDEX IF NOT EXISTS ux_watch_progress_unique
ON watch_progress(user_id, content_type, content_id, COALESCE(episode_id, 0));

CREATE INDEX IF NOT EXISTS idx_watch_progress_user_updated ON watch_progress(user_id, updated_at DESC);

-- -----------------------------------------------------
-- Favoris
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content_type TEXT NOT NULL CHECK(content_type IN ('series', 'movie')),
    content_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, content_type, content_id)
);

CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id);

-- -----------------------------------------------------
-- Historique des synchronisations Telegram
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER REFERENCES telegram_channels(id) ON DELETE SET NULL,
    started_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running', 'success', 'warning', 'failed')),
    videos_found INTEGER NOT NULL DEFAULT 0,
    videos_added INTEGER NOT NULL DEFAULT 0,
    videos_classified INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_sync_logs_channel_started ON sync_logs(channel_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_logs_status ON sync_logs(status);

-- -----------------------------------------------------
-- Journal d'audit administratif
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    details TEXT,
    ip_address TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_created ON audit_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id);

-- -----------------------------------------------------
-- Événements de connexion pour sécurité anti brute-force
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS login_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    success INTEGER NOT NULL DEFAULT 0 CHECK(success IN (0, 1)),
    failure_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_login_events_username_created ON login_events(username, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_login_events_ip_created ON login_events(ip_address, created_at DESC);

-- -----------------------------------------------------
-- Entrées de cache vidéo
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS cache_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type TEXT NOT NULL CHECK(content_type IN ('episode', 'movie')),
    content_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0 CHECK(size_bytes >= 0),
    last_access_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(content_type, content_id, file_path)
);

CREATE INDEX IF NOT EXISTS idx_cache_entries_content ON cache_entries(content_type, content_id);
CREATE INDEX IF NOT EXISTS idx_cache_entries_last_access ON cache_entries(last_access_at);

-- -----------------------------------------------------
-- Données de référence minimales
-- -----------------------------------------------------
INSERT OR IGNORE INTO settings (key, value, description) VALUES
    ('app_name', 'StreamAdmin', 'Nom de l''application'),
    ('accent_color', '#E50914', 'Couleur d''accent principale'),
    ('default_language', 'fr', 'Langue par défaut'),
    ('max_screens_default', '2', 'Nombre maximum d''écrans simultanés par défaut'),
    ('cache_max_gb', '80', 'Taille maximale du cache vidéo en Go'),
    ('token_ttl_minutes', '43200', 'Durée de validité des jetons JWT en minutes');

INSERT OR IGNORE INTO genres (id, slug, name_fr, name_ar, icon, order_index) VALUES
    (1, 'action', 'Action', 'أكشن', 'bi-lightning-charge', 1),
    (2, 'drame', 'Drame', 'دراما', 'bi-mask', 2),
    (3, 'comedie', 'Comédie', 'كوميديا', 'bi-emoji-smile', 3),
    (4, 'policier', 'Policier', 'بوليسي', 'bi-shield-lock', 4),
    (5, 'mystere', 'Mystère', 'غموض', 'bi-question-circle', 5),
    (6, 'famille', 'Famille', 'عائلي', 'bi-people', 6);