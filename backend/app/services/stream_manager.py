"""
Gestionnaire des sessions de streaming actives et respect des quotas de simultanéité.
Garantit qu'aucun utilisateur ni le serveur ne dépasse les limites configurées.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
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
            return

        # 3. Nouvelle session : Vérifier le quota global du serveur
        count_global_stmt = select(func.count(ActiveStream.id))
        total_active = (await db.execute(count_global_stmt)).scalar_one()

        if total_active >= settings.MAX_CONCURRENT_STREAMS_GLOBAL:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Serveur saturé : nombre maximal de lectures simultanées atteint. Réessayez dans quelques minutes.",
            )

        # 4. Vérifier le quota par utilisateur
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

    async def release_stream_session(self, session_token: str, db: AsyncSession) -> None:
        """Libère explicitement une session lorsqu'un lecteur vidéo se ferme."""
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
