"""
Configuration globale de l'application via variables d'environnement.
"""
import logging
import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Sécurité et Jetons JWT
    # Vide ou valeur d'exemple => une clé aléatoire persistante est générée dans DATA_DIR (voir plus bas)
    SECRET_KEY: str = ""
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

    # Dossier de données persistantes (volume Docker). Vide => /app/data s'il existe, sinon backend/data
    DATA_DIR: str = ""

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

    # Compte Administrateur initial (créé UNIQUEMENT s'il n'existe aucun admin).
    # Le mot de passe n'est plus réécrit à chaque démarrage, sauf si ADMIN_RESET_PASSWORD=true
    # (procédure de secours : définir la variable, redémarrer, puis la retirer).
    ADMIN_DEFAULT_USERNAME: str = "admin"
    ADMIN_DEFAULT_PASSWORD: str = ""
    ADMIN_RESET_PASSWORD: bool = False


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


# -------------------------------------------------------------
# Dossier de données persistantes
# -------------------------------------------------------------
def get_data_dir() -> Path:
    """Retourne le dossier persistant (volume Docker /app/data en production)."""
    if settings.DATA_DIR:
        path = Path(settings.DATA_DIR)
    elif Path("/app/data").is_dir():
        path = Path("/app/data")
    else:
        path = Path(__file__).resolve().parent.parent / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_private_file(path: Path, content: str) -> None:
    """Écrit un fichier lisible uniquement par son propriétaire (0600 sous Linux)."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)


# -------------------------------------------------------------
# Clé secrète JWT : refus des valeurs publiques connues
# -------------------------------------------------------------
# Valeurs publiées dans le dépôt (code, .env.example, docker-compose) : ne doivent jamais signer de jetons.
PUBLIC_DEFAULT_SECRET_KEYS = {
    "",
    "change_me_super_secret_jwt_key_at_least_32_chars_vidtele_2026",
}

# Mots de passe admin publiés dans le dépôt : refusés à la création, signalés s'ils sont encore utilisés.
PUBLIC_DEFAULT_ADMIN_PASSWORDS = {
    "",
    "VotreMotDePasseSecurise2026!",
    "AdminSecurePass2026!",
}

# Origine de la clé utilisée : "env" (variable fournie) ou "generated" (fichier persistant)
SECRET_KEY_SOURCE = "env"


def _resolve_secret_key() -> None:
    """
    Si SECRET_KEY est absente ou vaut une valeur publique, on utilise une clé aléatoire
    persistante stockée dans DATA_DIR/.jwt_secret (créée au premier démarrage).
    La clé n'est jamais écrite dans les journaux.
    """
    global SECRET_KEY_SOURCE
    logger = logging.getLogger("vidtele.config")
    current = (settings.SECRET_KEY or "").strip()

    if current not in PUBLIC_DEFAULT_SECRET_KEYS:
        if len(current) < 32:
            logger.warning("SECRET_KEY fait moins de 32 caractères : utilisez 'openssl rand -hex 32'.")
        return

    key_file = get_data_dir() / ".jwt_secret"
    if key_file.exists() and key_file.read_text(encoding="utf-8").strip():
        settings.SECRET_KEY = key_file.read_text(encoding="utf-8").strip()
    else:
        settings.SECRET_KEY = secrets.token_hex(32)
        write_private_file(key_file, settings.SECRET_KEY)
    SECRET_KEY_SOURCE = "generated"
    logger.critical(
        "SECRET_KEY absente ou égale à une valeur publique : utilisation d'une clé aléatoire "
        "persistante (%s). Définissez SECRET_KEY dans Dokploy pour la maîtriser.",
        key_file,
    )


_resolve_secret_key()
