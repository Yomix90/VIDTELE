"""Accès aux vidéos en base."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Video


async def trouver_video(db: AsyncSession, identifiant: int) -> Optional[Video]:
    """
    Vidéo par identifiant interne, ou à défaut par identifiant de message Telegram
    (compatibilité avec d'anciennes URL qui utilisaient ce dernier).
    """
    video = (await db.execute(select(Video).where(Video.id == identifiant))).scalar_one_or_none()
    if video is None:
        video = (
            await db.execute(select(Video).where(Video.telegram_message_id == identifiant))
        ).scalars().first()
    return video
