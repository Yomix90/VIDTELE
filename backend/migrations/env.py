"""
Environnement Alembic.

- L'URL vient de la configuration de l'application (DATABASE_URL), jamais d'un fichier.
- Moteur SYNCHRONE (sqlite3) : les migrations s'exécutent dans un thread au démarrage,
  sans interférer avec la boucle asyncio du serveur.
- render_as_batch=True : SQLite ne sait pas modifier une colonne en place ; Alembic
  recrée alors la table en copiant les données.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (charge toutes les tables dans Base.metadata)
from app.config import settings
from app.database import Base

config = context.config

# En ligne de commande uniquement : le serveur garde sa propre journalisation
if config.config_file_name is not None and not config.attributes.get("depuis_application"):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def url_synchrone() -> str:
    """Convertit l'URL asynchrone de l'application en URL synchrone pour Alembic."""
    url = config.attributes.get("url") or settings.DATABASE_URL
    return url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg")


def _options() -> dict:
    return {
        "target_metadata": target_metadata,
        "render_as_batch": True,
        "compare_type": True,
    }


def run_migrations_offline() -> None:
    """Génère le SQL sans se connecter (python -m alembic upgrade head --sql)."""
    context.configure(url=url_synchrone(), literal_binds=True, **_options())
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connexion = config.attributes.get("connection")
    if connexion is not None:
        context.configure(connection=connexion, **_options())
        with context.begin_transaction():
            context.run_migrations()
        return

    moteur = create_engine(url_synchrone(), poolclass=pool.NullPool)
    with moteur.connect() as connexion:
        context.configure(connection=connexion, **_options())
        with context.begin_transaction():
            context.run_migrations()
    moteur.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
