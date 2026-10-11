"""Données réelles du tableau de bord d'administration (plus aucune valeur inventée)."""
from datetime import date, datetime, timedelta, timezone
from typing import List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlaybackEvent, User, WatchHistory


def _maintenant() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def lectures_par_jour(db: AsyncSession, jours: int = 14) -> List[dict]:
    """
    Démarrages de lecture par jour, mesurés par l'application (versions >= 1.3).
    Les jours sans lecture apparaissent avec 0, pour une courbe continue.
    """
    debut = (_maintenant() - timedelta(days=jours - 1)).date()
    jour = func.date(PlaybackEvent.created_at)
    lignes = (
        await db.execute(
            select(jour, func.count(PlaybackEvent.id))
            .where(PlaybackEvent.event_type == "demarrage", PlaybackEvent.created_at >= datetime.combine(debut, datetime.min.time()))
            .group_by(jour)
        )
    ).all()
    par_jour = {str(j): n for j, n in lignes}
    resultat = []
    for i in range(jours):
        d: date = debut + timedelta(days=i)
        resultat.append({"jour": d.strftime("%d/%m"), "lectures": par_jour.get(d.isoformat(), 0)})
    return resultat


async def spectateurs_actifs(db: AsyncSession, jours: int = 7) -> int:
    """Utilisateurs ayant regardé au moins une vidéo sur la période (toutes versions de l'app)."""
    depuis = _maintenant() - timedelta(days=jours)
    return (
        await db.execute(
            select(func.count(func.distinct(WatchHistory.user_id))).where(WatchHistory.last_watched_at >= depuis)
        )
    ).scalar_one()


async def nouveaux_utilisateurs(db: AsyncSession, jours: int = 7) -> int:
    depuis = _maintenant() - timedelta(days=jours)
    return (await db.execute(select(func.count(User.id)).where(User.created_at >= depuis))).scalar_one()
