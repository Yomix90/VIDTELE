"""
Gestionnaire des sessions de streaming actives et respect des quotas de simultanéité.
Garantit qu'aucun utilisateur ni le serveur ne dépasse les limites configurées.
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ActiveStream, User


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class StreamManager:
    """Suivi et régulation des flux vidéo actifs."""

    SESSION_TIMEOUT_SECONDS = 120  # Une session inactive pendant 2 minutes est libérée
    # Le lecteur envoie une requête Range par morceau et à chaque déplacement : on n'écrit en
    # base (quota + battement de cœur) qu'une fois toutes les 30 s par session, au lieu de
    # chaque requête. SQLite n'accepte qu'un écrivain à la fois : c'était un goulot.
    INTERVALLE_ECRITURE_SECONDES = 30
    # Une même vidéo regardée par le même utilisateur ne compte qu'une vue par demi-heure
    # (avant : chaque requête « bytes=0- », reconnexions comprises, ajoutait une vue).
    FENETRE_VUE_SECONDES = 30 * 60

    def __init__(self):
        self._sessions_recentes: Dict[str, float] = {}
        self._vues_recentes: Dict[Tuple[int, int], float] = {}

    def _purger(self, cache: dict, duree: float) -> None:
        if len(cache) > 5000:
            limite = time.monotonic() - duree
            for cle in [c for c, t in cache.items() if t < limite]:
                del cache[cle]

    def nouvelle_vue(self, user_id: int, video_id: int) -> bool:
        """Vrai si cette lecture doit compter comme une nouvelle vue (et lancer le préchauffage)."""
        maintenant = time.monotonic()
        cle = (user_id, video_id)
        precedente = self._vues_recentes.get(cle)
        if precedente is not None and maintenant - precedente < self.FENETRE_VUE_SECONDES:
            return False
        self._vues_recentes[cle] = maintenant
        self._purger(self._vues_recentes, self.FENETRE_VUE_SECONDES)
        return True

    async def cleanup_expired_sessions(self, db: AsyncSession) -> None:
        """Nettoie les sessions expirées en base."""
        now = utc_now()
        stmt = delete(ActiveStream).where(ActiveStream.expires_at < now)
        await db.execute(stmt)

    async def register_stream_access(
        self,
        user: User,
        video_id: int,
        session_token: str,
        ip_address: Optional[str],
        db: AsyncSession,
    ) -> None:
        """
        Vérifie les quotas et met à jour la session de streaming active.
        Lève une exception HTTP 429 si le quota utilisateur ou global est dépassé.
        """
        # Session déjà enregistrée récemment : aucune écriture en base
        derniere = self._sessions_recentes.get(session_token)
        if derniere is not None and time.monotonic() - derniere < self.INTERVALLE_ECRITURE_SECONDES:
            return

        now = utc_now()
        # 1. Nettoyer d'abord les sessions obsolètes
        await self.cleanup_expired_sessions(db)

        # 2. Vérifier si cette session précise existe déjà (renouvellement de battement de cœur)
        stmt_curr = select(ActiveStream).where(ActiveStream.session_token == session_token)
        curr_session = (await db.execute(stmt_curr)).scalar_one_or_none()

        if curr_session:
            # Session existante -> mise à jour du heartbeat
            curr_session.last_active_at = now
            curr_session.expires_at = now + timedelta(seconds=self.SESSION_TIMEOUT_SECONDS)
            await db.commit()
            self._memoriser_session(session_token)
            return

        # 3. Nouvelle session : Vérifier le quota global du serveur
        count_global_stmt = select(func.count(ActiveStream.id))
        total_active = (await db.execute(count_global_stmt)).scalar_one()

        if total_active >= settings.MAX_CONCURRENT_STREAMS_GLOBAL:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Serveur saturé : nombre maximal de lectures simultanées atteint. Réessayez dans quelques minutes.",
            )

        # 4. Vérifier le quota par utilisateur (les administrateurs sont exemptés pour tests/supervision)
        if user.role != "admin":
            count_user_stmt = select(func.count(ActiveStream.id)).where(ActiveStream.user_id == user.id)
            user_active = (await db.execute(count_user_stmt)).scalar_one()

            max_allowed = user.max_concurrent_streams or settings.MAX_CONCURRENT_STREAMS_PER_USER
            if user_active >= max_allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Limite de lectures simultanées atteinte pour votre compte (max: {max_allowed}).",
                )


        # 5. Créer la nouvelle session active
        new_stream = ActiveStream(
            user_id=user.id,
            video_id=video_id,
            session_token=session_token,
            ip_address=ip_address,
            last_active_at=now,
            expires_at=now + timedelta(seconds=self.SESSION_TIMEOUT_SECONDS),
        )
        db.add(new_stream)
        await db.commit()
        self._memoriser_session(session_token)

    def _memoriser_session(self, session_token: str) -> None:
        self._sessions_recentes[session_token] = time.monotonic()
        self._purger(self._sessions_recentes, self.SESSION_TIMEOUT_SECONDS)

    async def release_stream_session(self, session_token: str, db: AsyncSession) -> None:
        """Libère explicitement une session lorsqu'un lecteur vidéo se ferme."""
        self._sessions_recentes.pop(session_token, None)
        stmt = delete(ActiveStream).where(ActiveStream.session_token == session_token)
        await db.execute(stmt)
        await db.commit()

    async def get_active_stream_counts(self, db: AsyncSession) -> dict:
        """Retourne les métriques des flux actifs pour le tableau de bord admin."""
        await self.cleanup_expired_sessions(db)
        total = (await db.execute(select(func.count(ActiveStream.id)))).scalar_one()
        return {
            "current_active": total,
            "max_global": settings.MAX_CONCURRENT_STREAMS_GLOBAL,
            "max_per_user": settings.MAX_CONCURRENT_STREAMS_PER_USER,
        }


# Instance unique (Singleton)
stream_manager = StreamManager()
