"""
Migration 001 : Intégration du schéma relationnel StreamAdmin dans VidTele.
Ajoute les tables pour Séries, Saisons, Épisodes, Films, Genres, Collections,
Accueil mobile et journaux, sans toucher aux données existantes.
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def get_db_path() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve()
    # Par défaut dans backend/vidtele.db
    base_dir = Path(__file__).resolve().parent.parent
    return (base_dir / "vidtele.db").resolve()


def run_migration(db_path: Path):
    print("=" * 65)
    print(f"MIGRATION STREAMADMIN : {db_path}")
    print("=" * 65)

    if not db_path.exists():
        print(f"La base {db_path} n'existe pas encore. Elle sera créée lors du démarrage de l'app.")
        return

    # 1. Sauvegarde automatique préalable
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.bak_{timestamp}")
    shutil.copy2(db_path, backup_path)
    print(f"[OK] Sauvegarde de secours créée : {backup_path.name}")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Compter les données existantes avant migration
    initial_counts = {}
    for table in ["users", "videos", "invite_codes", "watch_history", "favorites"]:
        try:
            initial_counts[table] = c.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            initial_counts[table] = 0

    print(f"Données existantes avant migration : {initial_counts}")

    # 2. Extension non destructive de la table 'users'
    user_columns = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
    columns_to_add = [
        ("email", "TEXT"),
        ("full_name", "TEXT"),
        ("max_screens", "INTEGER NOT NULL DEFAULT 2"),
        ("expires_at", "TEXT"),
        ("invited_by", "INTEGER"),
    ]
    for col_name, col_type in columns_to_add:
        if col_name not in user_columns:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};")
            print(f"  + Colonne ajoutée à users : {col_name}")

    # 3. Création des nouvelles tables StreamAdmin
    c.executescript("""
    -- Genres / catégories
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

    -- Collections / sagas de films
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

    -- Séries
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

    -- Saisons
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

    -- Épisodes
    CREATE TABLE IF NOT EXISTS episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
        telegram_video_id INTEGER UNIQUE REFERENCES videos(id) ON DELETE SET NULL,
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

    -- Films
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL UNIQUE,
        collection_id INTEGER REFERENCES collections(id) ON DELETE SET NULL,
        telegram_video_id INTEGER UNIQUE REFERENCES videos(id) ON DELETE SET NULL,
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
    CREATE INDEX IF NOT EXISTS idx_movies_title_fr ON movies(title_fr);
    CREATE INDEX IF NOT EXISTS idx_movies_tmdb ON movies(tmdb_id);

    -- Association Séries / Genres
    CREATE TABLE IF NOT EXISTS series_genres (
        series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
        genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
        PRIMARY KEY(series_id, genre_id)
    );

    -- Association Films / Genres
    CREATE TABLE IF NOT EXISTS movie_genres (
        movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
        genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
        PRIMARY KEY(movie_id, genre_id)
    );

    -- Rangées configurables de l'accueil mobile
    CREATE TABLE IF NOT EXISTS home_rows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        row_type TEXT NOT NULL,
        title_fr TEXT NOT NULL,
        title_ar TEXT,
        genre_id INTEGER REFERENCES genres(id) ON DELETE SET NULL,
        collection_id INTEGER REFERENCES collections(id) ON DELETE SET NULL,
        limit_items INTEGER NOT NULL DEFAULT 20,
        is_active INTEGER NOT NULL DEFAULT 1,
        order_index INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_home_rows_active_order ON home_rows(is_active, order_index);

    -- Éléments du carrousel Héro
    CREATE TABLE IF NOT EXISTS home_hero_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content_type TEXT NOT NULL CHECK(content_type IN ('series', 'movie')),
        content_id INTEGER NOT NULL,
        order_index INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Journal de synchronisation Telegram
    CREATE TABLE IF NOT EXISTS sync_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id INTEGER,
        started_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        started_at TEXT NOT NULL DEFAULT (datetime('now')),
        finished_at TEXT,
        status TEXT NOT NULL DEFAULT 'running',
        videos_found INTEGER NOT NULL DEFAULT 0,
        videos_added INTEGER NOT NULL DEFAULT 0,
        videos_classified INTEGER NOT NULL DEFAULT 0,
        error_message TEXT
    );

    -- Journal d'audit d'administration
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

    -- Appareils connectés des utilisateurs
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        device_name TEXT NOT NULL,
        device_type TEXT NOT NULL DEFAULT 'other',
        app_version TEXT,
        ip_address TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        last_seen_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """)

    # 4. Données de référence minimales (Genres)
    c.executescript("""
    INSERT OR IGNORE INTO genres (id, slug, name_fr, name_ar, icon, order_index) VALUES
        (1, 'action', 'Action', 'أكشن', 'bi-lightning-charge', 1),
        (2, 'drame', 'Drame', 'دراما', 'bi-mask', 2),
        (3, 'comedie', 'Comédie', 'كوميديا', 'bi-emoji-smile', 3),
        (4, 'policier', 'Policier', 'بوليسي', 'bi-shield-lock', 4),
        (5, 'mystere', 'Mystère', 'غموض', 'bi-question-circle', 5),
        (6, 'famille', 'Famille', 'عائلي', 'bi-people', 6),
        (7, 'science-fiction', 'Science-Fiction', 'خيال علمي', 'bi-rocket', 7),
        (8, 'animation', 'Animation', 'رسوم متحركة', 'bi-palette', 8);

    -- Rangées d'accueil par défaut
    INSERT OR IGNORE INTO home_rows (id, row_type, title_fr, title_ar, order_index) VALUES
        (1, 'hero', 'À l''affiche', 'مميز', 1),
        (2, 'recent', 'Nouveautés', 'أحدث الإضافات', 2),
        (3, 'series', 'Séries populaires', 'مسلسلات شائعة', 3),
        (4, 'movies', 'Films récents', 'أفلام حديثة', 4);
    """)

    conn.commit()

    # 5. Vérification de conservation des données
    for table, count_before in initial_counts.items():
        count_after = c.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        assert count_after == count_before, f"ERREUR : Perte de données sur {table} ({count_before} -> {count_after})"

    conn.close()
    print("[OK] Migration exécutée avec succès sans aucune perte de données !")


if __name__ == "__main__":
    db = get_db_path()
    run_migration(db)
