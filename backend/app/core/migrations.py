"""
Application des migrations Alembic au démarrage, sans risque pour les données.

Trois cas :
1. Base neuve (aucune table)           -> `upgrade head` crée tout le schéma.
2. Base existante sans Alembic (prod)  -> sauvegarde, mise à niveau par l'ancien mécanisme,
                                          vérification du schéma, `stamp` sur la référence,
                                          puis `upgrade head`. Si la vérification échoue, le
                                          serveur REFUSE de démarrer (rien n'est modifié de plus).
3. Base déjà suivie par Alembic        -> sauvegarde s'il y a des migrations en attente,
                                          puis `upgrade head`.

Les sauvegardes SQLite vont dans DATA_DIR/sauvegardes/ (les 10 plus récentes sont gardées).
"""
import asyncio
import logging
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Optional

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, pool
from sqlalchemy.engine import Connection

from app.config import get_data_dir, settings

logger = logging.getLogger("vidtele.migrations")

# Révision correspondant au schéma existant en production au début de la Phase 1
REVISION_REFERENCE = "0001"
SAUVEGARDES_CONSERVEES = 10
_DOSSIER_BACKEND = Path(__file__).resolve().parent.parent.parent


class SchemaIncompatible(RuntimeError):
    """Le schéma réel ne correspond pas à la référence : démarrage refusé."""


@dataclass
class EtatBase:
    tables: set
    revision: Optional[str]
    tete: str


def _url_synchrone(url: str) -> str:
    return url.replace("+aiosqlite", "")


def configuration_alembic(url: Optional[str] = None) -> Config:
    cfg = Config(str(_DOSSIER_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_DOSSIER_BACKEND / "migrations"))
    cfg.attributes["url"] = url or settings.DATABASE_URL
    cfg.attributes["depuis_application"] = True
    return cfg


def chemin_sqlite(url: str) -> Optional[Path]:
    """Chemin du fichier SQLite, ou None (autre moteur ou base en mémoire)."""
    if not url.startswith("sqlite"):
        return None
    brut = url.split(":///", 1)[1] if ":///" in url else ""
    if not brut or brut.startswith(":memory:"):
        return None
    chemin = Path(brut)
    if not chemin.is_absolute():
        chemin = _DOSSIER_BACKEND / chemin
    return chemin


def sauvegarder_sqlite(url: str, raison: str) -> Optional[Path]:
    """Copie cohérente de la base (API de sauvegarde SQLite, sans arrêter le serveur)."""
    source = chemin_sqlite(url)
    if source is None or not source.exists():
        return None
    dossier = get_data_dir() / "sauvegardes"
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / f"{raison}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    # closing() : « with sqlite3.connect() » seul ne ferme PAS la connexion
    with closing(sqlite3.connect(str(source))) as src, closing(sqlite3.connect(str(cible))) as dst:
        src.backup(dst)
    logger.warning("Sauvegarde de la base avant migration : %s", cible)

    anciennes = sorted(dossier.glob(f"{raison}-*.db"))
    for fichier in anciennes[:-SAUVEGARDES_CONSERVEES]:
        fichier.unlink(missing_ok=True)
    return cible


def _lire_etat(url: str) -> EtatBase:
    moteur = create_engine(_url_synchrone(url), poolclass=pool.NullPool)
    try:
        with moteur.connect() as conn:
            tables = set(inspect(conn).get_table_names()) - {"alembic_version"}
            revision = MigrationContext.configure(conn).get_current_revision()
    finally:
        moteur.dispose()
    tete = ScriptDirectory.from_config(configuration_alembic(url)).get_current_head()
    return EtatBase(tables=tables, revision=revision, tete=tete)


def differences_bloquantes(conn: Connection) -> list:
    """
    Compare le schéma réel aux modèles. Seuls les MANQUES sont bloquants (table ou colonne
    absente : le code planterait). Les éléments en trop (anciennes colonnes, index) et les
    petites différences de type sont tolérés pour ne rien supprimer.
    """
    import app.models  # noqa: F401
    from app.database import Base

    contexte = MigrationContext.configure(conn, opts={"compare_type": False})
    bloquants = []
    for diff in compare_metadata(contexte, Base.metadata):
        operations = diff if isinstance(diff, list) else [diff]
        for op in operations:
            if op[0] == "add_table":
                bloquants.append(f"table manquante : {op[1].name}")
            elif op[0] == "add_column":
                bloquants.append(f"colonne manquante : {op[2]}.{op[3].name}")
    return bloquants


def _verifier_schema(url: str) -> list:
    moteur = create_engine(_url_synchrone(url), poolclass=pool.NullPool)
    try:
        with moteur.connect() as conn:
            return differences_bloquantes(conn)
    finally:
        moteur.dispose()


async def preparer_schema(
    mise_a_niveau_ancienne: Callable[[], Awaitable[None]],
    url: Optional[str] = None,
) -> EtatBase:
    """Amène la base à la dernière révision. Appelée une fois au démarrage."""
    url = url or settings.DATABASE_URL
    cfg = configuration_alembic(url)
    etat = await asyncio.to_thread(_lire_etat, url)

    if etat.revision is None and etat.tables:
        logger.warning(
            "Base existante non suivie par Alembic (%d tables) : passage au schéma de référence %s.",
            len(etat.tables),
            REVISION_REFERENCE,
        )
        await asyncio.to_thread(sauvegarder_sqlite, url, "avant-migration")
        await mise_a_niveau_ancienne()
        bloquants = await asyncio.to_thread(_verifier_schema, url)
        if bloquants:
            raise SchemaIncompatible(
                "Schéma incompatible avec la référence, démarrage annulé (base sauvegardée, non marquée) : "
                + "; ".join(bloquants)
            )
        await asyncio.to_thread(command.stamp, cfg, REVISION_REFERENCE)
        logger.warning("Base marquée à la révision de référence %s.", REVISION_REFERENCE)
    elif etat.revision is not None and etat.revision != etat.tete:
        await asyncio.to_thread(sauvegarder_sqlite, url, "avant-migration")

    if etat.revision != etat.tete:
        await asyncio.to_thread(command.upgrade, cfg, "head")
        logger.info("Migrations appliquées : base à la révision %s.", etat.tete)
    return await asyncio.to_thread(_lire_etat, url)
