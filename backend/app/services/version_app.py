"""
Versions de l'application mobile : dernière version, version minimale, mise à jour
conseillée ou obligatoire.

Deux mécanismes complémentaires :
1. GET /api/app/version (au lancement de l'app) : toutes les versions, y compris celles
   déjà installées, affichent la fenêtre de mise à jour (bloquante si obligatoire).
2. En-tête X-App-Version (versions >= 1.3.0) : toute requête /api d'une version
   inférieure à la version minimale reçoit 426 « Mise à jour requise ».

Les réglages (table system_settings, modifiables dans l'admin) sont mis en cache
quelques secondes pour ne pas interroger la base à chaque requête.
"""
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import SystemSetting

CLES = (
    "app_latest_version",
    "app_min_version",
    "app_update_url",
    "app_update_title",
    "app_update_notes",
    "app_update_force",
)
DUREE_CACHE_SECONDES = 30.0


@dataclass(frozen=True)
class ParametresVersion:
    derniere: str
    minimale: str
    url: str
    titre: str
    notes: str
    forcer_tout_le_monde: bool


def analyser_version(version: Optional[str]) -> Tuple[int, int, int]:
    """'1.2.0', '1.2', 'v1.3.0+5' -> (majeur, mineur, correctif). Valeur illisible -> (0, 0, 0)."""
    texte = str(version or "").strip().lstrip("vV").split("+", 1)[0].split("-", 1)[0]
    parties = []
    for morceau in texte.split(".")[:3]:
        try:
            parties.append(int(morceau))
        except ValueError:
            parties.append(0)
    while len(parties) < 3:
        parties.append(0)
    return tuple(parties)


_cache: Optional[Tuple[float, dict]] = None


def invalider_cache() -> None:
    """À appeler après une modification des réglages dans l'admin."""
    global _cache
    _cache = None


async def lire_reglages_bruts() -> dict:
    global _cache
    maintenant = time.monotonic()
    if _cache and maintenant - _cache[0] < DUREE_CACHE_SECONDES:
        return _cache[1]
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(SystemSetting).where(SystemSetting.key.in_(CLES)))
        valeurs = {row.key: row.value for row in res.scalars().all()}
    _cache = (maintenant, valeurs)
    return valeurs


def construire_parametres(valeurs: dict, url_par_defaut: str = "") -> ParametresVersion:
    return ParametresVersion(
        derniere=valeurs.get("app_latest_version", "1.2.0"),
        minimale=valeurs.get("app_min_version", "1.0.0"),
        url=valeurs.get("app_update_url") or url_par_defaut,
        titre=valeurs.get("app_update_title", "Nouvelle version Atlas Play disponible"),
        notes=valeurs.get(
            "app_update_notes",
            "Améliorations des posters, zapping TikTok, enchaînement automatique des épisodes et veille d'écran.",
        ),
        forcer_tout_le_monde=str(valeurs.get("app_update_force", "false")).lower() == "true",
    )


def est_trop_ancienne(version_app: str, minimale: str) -> bool:
    return analyser_version(version_app) < analyser_version(minimale)
