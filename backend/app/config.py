"""
Configuration globale de l'application via variables d'environnement.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Sécurité et Jetons JWT
    SECRET_KEY: str = "change_me_super_secret_jwt_key_at_least_32_chars_vidtele_2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    STREAM_TOKEN_EXPIRE_SECONDS: int = 7200  # 2 heures de validité pour un token de flux signé

    # Base de données
    DATABASE_URL: str = "sqlite+aiosqlite:///./vidtele.db"

    # Telegram MTProto
    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: str = ""
    TELEGRAM_SESSION_NAME: str = "vidtele_session"
    TELEGRAM_STRING_SESSION: str = ""
    TELEGRAM_CHANNEL_ID: int = 0

    # Stockage et Cache Disque
    CACHE_DIR: str = "./cache"
    THUMBNAILS_DIR: str = "./thumbnails"
    MAX_CACHE_GB: float = 20.0  # 20 Go permet d'héberger 500 à 1000+ épisodes de ~15 Mo
    AUTO_FASTSTART: bool = True  # Remuxage moov atom +faststart sans réencodage pour première image instantanée
    STREAM_CHUNK_SIZE_KB: int = 256  # 256 Ko par morceau pour un équilibre parfait débit/mémoire
    PREWARM_POPULAR_COUNT: int = 20  # Préchargement anticipé des épisodes populaires en tâche de fond

    # Limites et Concurrence (autorise le pool de 3 vidéos + marge)
    MAX_CONCURRENT_STREAMS_PER_USER: int = 4
    MAX_CONCURRENT_STREAMS_GLOBAL: int = 30

    # Tâches périodiques
    SYNC_INTERVAL_MINUTES: int = 15

    # Compte Administrateur initial (créé automatiquement si la table est vide)
    ADMIN_DEFAULT_USERNAME: str = "admin"
    ADMIN_DEFAULT_PASSWORD: str = "VotreMotDePasseSecurise2026!"


    # Anti brute-force
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Création automatique des répertoires de stockage s'ils n'existent pas
Path(settings.CACHE_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.THUMBNAILS_DIR).mkdir(parents=True, exist_ok=True)

# Assurer l'existence du dossier de la base de données SQLite
if "sqlite" in settings.DATABASE_URL:
    db_clean = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    if db_clean and not db_clean.startswith(":memory:"):
        db_path = Path(db_clean)
        if not db_path.is_absolute():
            db_path = Path(__file__).resolve().parent.parent / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

