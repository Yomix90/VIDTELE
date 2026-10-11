"""Accès aux mesures de lecture (table playback_events)."""
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlaybackEvent


async def enregistrer_evenements(db: AsyncSession, evenements: Iterable[PlaybackEvent]) -> int:
    lignes = list(evenements)
    db.add_all(lignes)
    await db.commit()
    return len(lignes)


def _centile(valeurs: list, p: float) -> Optional[int]:
    """Centile p (0-100) par interpolation au plus proche ; None si aucune valeur."""
    if not valeurs:
        return None
    triees = sorted(valeurs)
    rang = max(0, min(len(triees) - 1, round(p / 100 * (len(triees) - 1))))
    return int(triees[rang])


async def statistiques(db: AsyncSession, jours: int = 7) -> dict:
    """Résumé des mesures sur la période : premières images, blocages, erreurs."""
    depuis = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=jours)
    lignes = (
        await db.execute(
            select(
                PlaybackEvent.event_type,
                PlaybackEvent.ttff_ms,
                PlaybackEvent.stall_ms,
                PlaybackEvent.preloaded,
                PlaybackEvent.error_code,
            ).where(PlaybackEvent.created_at >= depuis)
        )
    ).all()

    demarrages = [l for l in lignes if l.event_type == "demarrage" and l.ttff_ms is not None]
    prechargees = [l.ttff_ms for l in demarrages if l.preloaded]
    froides = [l.ttff_ms for l in demarrages if not l.preloaded]
    blocages = [l.stall_ms or 0 for l in lignes if l.event_type == "blocage"]
    erreurs: dict = {}
    for l in lignes:
        if l.event_type == "erreur":
            erreurs[l.error_code or "inconnue"] = erreurs.get(l.error_code or "inconnue", 0) + 1

    return {
        "periode_jours": jours,
        "demarrages": len(demarrages),
        "ttff_ms": {
            "precharge": {"p50": _centile(prechargees, 50), "p90": _centile(prechargees, 90), "nombre": len(prechargees)},
            "non_precharge": {"p50": _centile(froides, 50), "p90": _centile(froides, 90), "nombre": len(froides)},
        },
        "blocages": {"nombre": len(blocages), "duree_p50_ms": _centile(blocages, 50), "duree_p90_ms": _centile(blocages, 90)},
        "erreurs": dict(sorted(erreurs.items(), key=lambda e: -e[1])),
    }
