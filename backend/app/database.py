"""
Configuration de la base de données asynchrone SQLAlchemy 2.0 avec SQLite (aiosqlite).
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# Création du moteur asynchrone
# connect_args={"check_same_thread": False} requis pour SQLite en mode asynchrone
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

# Fabrique de sessions asynchrones
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Classe de base pour tous les modèles SQLAlchemy."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dépendance FastAPI fournissant une session de base de données asynchrone.
    Garantit la fermeture propre de la session en fin de requête.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


from sqlalchemy import text


async def init_db() -> None:
    """Initialise les tables de la base de données et applique les migrations douces si nécessaires."""
    import app.models  # Assure le chargement de toutes les classes filles de Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Migrations douces pour SQLite sur la table 'videos'
        columns_to_add = [
            ("is_published", "BOOLEAN DEFAULT 0 NOT NULL"),
            ("media_item_id", "INTEGER REFERENCES media_items(id) ON DELETE SET NULL"),
            ("season_number", "INTEGER DEFAULT 1 NOT NULL"),
            ("episode_number", "INTEGER DEFAULT 1 NOT NULL"),
            ("episode_title", "VARCHAR(255)"),
        ]

        try:
            res = await conn.execute(text("PRAGMA table_info(videos)"))
            existing_cols = {row[1] for row in res.fetchall()}
            for col_name, col_def in columns_to_add:
                if col_name not in existing_cols:
                    await conn.execute(text(f"ALTER TABLE videos ADD COLUMN {col_name} {col_def}"))
        except Exception:
            pass

        # Migrations douces pour SQLite sur la table 'users'
        user_cols_to_add = [
            ("email", "VARCHAR(255)"),
            ("full_name", "VARCHAR(255)"),
            ("max_screens", "INTEGER DEFAULT 2 NOT NULL"),
            ("expires_at", "DATETIME"),
            ("invited_by", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
        ]
        try:
            res_u = await conn.execute(text("PRAGMA table_info(users)"))
            existing_user_cols = {row[1] for row in res_u.fetchall()}
            for col_name, col_def in user_cols_to_add:
                if col_name not in existing_user_cols:
                    await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"))
        except Exception:
            pass

        # Amorçage automatique des genres de référence si vide
        try:
            res_g = await conn.execute(text("SELECT count(*) FROM genres"))
            if res_g.scalar_one() == 0:
                await conn.execute(text("""
                    INSERT OR IGNORE INTO genres (id, slug, name_fr, name_ar, icon, order_index) VALUES
                    (1, 'action', 'Action', 'أكشن', 'bi-lightning-charge', 1),
                    (2, 'drame', 'Drame', 'دراما', 'bi-mask', 2),
                    (3, 'comedie', 'Comédie', 'كوميديا', 'bi-emoji-smile', 3),
                    (4, 'policier', 'Policier', 'بوليسي', 'bi-shield-lock', 4),
                    (5, 'mystere', 'Mystère', 'غموض', 'bi-question-circle', 5),
                    (6, 'famille', 'Famille', 'عائلي', 'bi-people', 6),
                    (7, 'science-fiction', 'Science-Fiction', 'خيال علمي', 'bi-rocket', 7),
                    (8, 'animation', 'Animation', 'رسوم متحركة', 'bi-palette', 8)
                """))
        except Exception:
            pass

        # Amorçage automatique des rangées d'accueil par défaut si vide
        try:
            res_h = await conn.execute(text("SELECT count(*) FROM home_rows"))
            if res_h.scalar_one() == 0:
                await conn.execute(text("""
                    INSERT OR IGNORE INTO home_rows (id, row_type, title_fr, title_ar, order_index) VALUES
                    (1, 'hero', 'À l''affiche', 'مميز', 1),
                    (2, 'recent', 'Nouveautés', 'أحدث الإضافات', 2),
                    (3, 'series', 'Séries populaires', 'مسلسلات شائعة', 3),
                    (4, 'movies', 'Films récents', 'أفلام حديثة', 4)
                """))
        except Exception:
            pass
