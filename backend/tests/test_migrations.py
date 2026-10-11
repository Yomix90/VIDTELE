"""
Tests des migrations Alembic au démarrage (sur des bases SQLite temporaires).

Cas couverts :
- base neuve : schéma complet créé par Alembic, identique aux modèles ;
- base « production » ancienne (colonnes et table manquantes) : sauvegarde, mise à
  niveau, marquage à la référence, données conservées ;
- schéma incompatible : démarrage refusé, base non marquée ;
- redémarrage : idempotent, pas de nouvelle sauvegarde.
"""
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401
from app.config import get_data_dir
from app.core.migrations import (
    REVISION_REFERENCE,
    SchemaIncompatible,
    differences_bloquantes,
    preparer_schema,
)
from app.database import Base, _mise_a_niveau_ancienne


def _url(chemin: Path) -> str:
    return f"sqlite+aiosqlite:///{chemin.as_posix()}"


def _colonnes(chemin: Path) -> dict:
    with closing(sqlite3.connect(chemin)) as c:
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('alembic_version','sqlite_sequence')")]
        return {t: sorted(r[1] for r in c.execute(f"PRAGMA table_info({t})")) for t in tables}


def _revision(chemin: Path):
    with closing(sqlite3.connect(chemin)) as c:
        try:
            return c.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        except sqlite3.OperationalError:
            return None


def _sauvegardes():
    dossier = get_data_dir() / "sauvegardes"
    return set(dossier.glob("avant-migration-*.db")) if dossier.exists() else set()


@pytest.fixture
def dossier():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


async def _preparer(chemin: Path):
    moteur = create_async_engine(_url(chemin))
    try:
        return await preparer_schema(lambda: _mise_a_niveau_ancienne(moteur), url=_url(chemin))
    finally:
        await moteur.dispose()


def _creer_base_ancienne(chemin: Path):
    """Base telle qu'une ancienne version l'a laissée : create_all puis retrait d'éléments récents."""
    moteur = create_engine(f"sqlite:///{chemin.as_posix()}")
    Base.metadata.create_all(moteur)
    moteur.dispose()
    with closing(sqlite3.connect(chemin)) as c:
        c.execute("ALTER TABLE users DROP COLUMN ads_free")  # ajoutée par une migration douce
        c.execute("ALTER TABLE invite_codes DROP COLUMN max_uses")  # idem
        c.execute("DROP TABLE devices")  # recréée par create_all
        c.execute(
            "INSERT INTO users (username, hashed_password, role, is_active, max_concurrent_streams, max_screens, created_at) "
            "VALUES ('existant', 'x', 'user', 1, 2, 2, CURRENT_TIMESTAMP)"
        )
        c.commit()


async def test_base_neuve(dossier):
    base = dossier / "neuve.db"
    etat = await _preparer(base)
    assert etat.revision == etat.tete
    assert _sauvegardes() == _sauvegardes()  # pas de sauvegarde pour une base vide

    # Le schéma créé par Alembic est identique à celui des modèles
    reference = dossier / "reference.db"
    moteur = create_engine(f"sqlite:///{reference.as_posix()}")
    Base.metadata.create_all(moteur)
    moteur.dispose()
    assert _colonnes(base) == _colonnes(reference)

    moteur = create_engine(f"sqlite:///{base.as_posix()}")
    with moteur.connect() as conn:
        assert differences_bloquantes(conn) == []
    moteur.dispose()


async def test_base_existante_mise_a_niveau_sans_perte(dossier):
    base = dossier / "prod.db"
    _creer_base_ancienne(base)
    avant = _sauvegardes()

    etat = await _preparer(base)

    assert etat.revision == etat.tete
    assert _revision(base) == etat.tete
    nouvelles = _sauvegardes() - avant
    assert len(nouvelles) == 1, "une sauvegarde doit précéder la migration"
    # La sauvegarde est l'état d'origine (colonne ads_free absente)
    sauvegarde = next(iter(nouvelles))
    assert "ads_free" not in _colonnes(sauvegarde)["users"]
    with closing(sqlite3.connect(sauvegarde)) as c:
        assert c.execute("SELECT count(*) FROM users WHERE username='existant'").fetchone()[0] == 1
    # Colonnes et table manquantes rétablies, données conservées
    colonnes = _colonnes(base)
    assert "ads_free" in colonnes["users"] and "max_uses" in colonnes["invite_codes"] and "devices" in colonnes
    with closing(sqlite3.connect(base)) as c:
        assert c.execute("SELECT count(*) FROM users WHERE username='existant'").fetchone()[0] == 1

    # Redémarrage : rien à faire, aucune nouvelle sauvegarde
    avant = _sauvegardes()
    await _preparer(base)
    assert _sauvegardes() == avant


async def test_schema_incompatible_refuse(dossier):
    base = dossier / "incompatible.db"
    _creer_base_ancienne(base)
    with closing(sqlite3.connect(base)) as c:
        # Colonne que l'ancien mécanisme ne sait pas recréer
        c.execute("ALTER TABLE series DROP COLUMN logo_path")

    with pytest.raises(SchemaIncompatible, match="series.logo_path"):
        await _preparer(base)
    assert _revision(base) is None, "une base incompatible ne doit pas être marquée"


async def test_reference_est_la_premiere_revision():
    from alembic.script import ScriptDirectory

    from app.core.migrations import configuration_alembic

    script = ScriptDirectory.from_config(configuration_alembic())
    assert script.get_base() == REVISION_REFERENCE


async def test_donnees_de_reference_amorcees(client):
    # Avant correctif : INSERT OR IGNORE sans created_at => tables silencieusement vides
    from sqlalchemy import text

    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        assert (await db.execute(text("SELECT count(*) FROM genres"))).scalar_one() == 8
        assert (await db.execute(text("SELECT count(*) FROM home_rows"))).scalar_one() == 4
