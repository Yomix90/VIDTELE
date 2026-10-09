"""
Service de cache disque avec politique d'éviction LRU (Least Recently Used).
Gère le stockage des vidéos téléchargées depuis Telegram et le respect du quota disque.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
from app.config import settings

logger = logging.getLogger("vidtele.cache")


class CacheService:
    """Gestionnaire du cache disque pour les vidéos Telegram."""

    def __init__(self):
        self.cache_dir = Path(settings.CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def get_video_path(self, telegram_message_id: int) -> Path:
        """Retourne le chemin cible du fichier vidéo en cache."""
        return self.cache_dir / f"video_{telegram_message_id}.mp4"

    def is_cached(self, telegram_message_id: int) -> bool:
        """Vérifie si la vidéo complète est disponible sur le disque."""
        path = self.get_video_path(telegram_message_id)
        return path.exists() and path.stat().st_size > 0

    def touch(self, telegram_message_id: int) -> None:
        """Met à jour le temps de dernier accès (atime) pour l'algorithme LRU."""
        path = self.get_video_path(telegram_message_id)
        if path.exists():
            try:
                os.utime(path, None)
            except Exception as e:
                logger.warning(f"Impossible de mettre à jour le timestamp de {path}: {e}")

    def get_cache_stats(self) -> Dict[str, float]:
        """Retourne les métriques d'utilisation du cache disque."""
        total_bytes = 0
        file_count = 0

        for file in self.cache_dir.glob("video_*.mp4"):
            if file.is_file():
                total_bytes += file.stat().st_size
                file_count += 1

        total_gb = total_bytes / (1024 ** 3)
        max_gb = settings.MAX_CACHE_GB
        percent_used = (total_gb / max_gb * 100) if max_gb > 0 else 0.0

        return {
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 ** 2), 2),
            "total_gb": round(total_gb, 3),
            "max_gb": max_gb,
            "percent_used": round(percent_used, 1),
            "file_count": file_count,
        }

    async def ensure_capacity(self, needed_bytes: int = 0) -> None:
        """
        Vérifie si la taille du cache dépasse MAX_CACHE_GB.
        Si oui, purge les fichiers les moins récemment consultés (LRU)
        jusqu'à redescendre sous 85% de la capacité maximale.
        """
        async with self._lock:
            stats = self.get_cache_stats()
            max_bytes = int(settings.MAX_CACHE_GB * (1024 ** 3))
            target_bytes = int(max_bytes * 0.85)  # Seuil de purge à 85%

            current_bytes = stats["total_bytes"]
            if current_bytes + needed_bytes <= max_bytes:
                return

            logger.info(
                f"Capacité de cache presque atteinte ({stats['total_gb']} Go / {settings.MAX_CACHE_GB} Go). "
                "Exécution du nettoyage LRU..."
            )

            # Lister tous les fichiers vidéo avec leur date de dernier accès
            files: List[Path] = [f for f in self.cache_dir.glob("video_*.mp4") if f.is_file()]
            # Trier par atime (le plus ancien en premier)
            files.sort(key=lambda f: f.stat().st_atime)

            for file in files:
                if current_bytes + needed_bytes <= target_bytes:
                    break
                try:
                    f_size = file.stat().st_size
                    file.unlink()
                    current_bytes -= f_size
                    logger.info(f"Éviction LRU : suppression de {file.name} ({round(f_size / 1024**2, 2)} Mo libérés)")
                except Exception as e:
                    logger.error(f"Erreur lors de la suppression de {file.name}: {e}")

    def clear_all(self) -> int:
        """Supprime tous les fichiers du cache disque (pour maintenance admin)."""
        deleted_count = 0
        for file in self.cache_dir.glob("*.mp4"):
            try:
                file.unlink()
                deleted_count += 1
            except Exception as e:
                logger.error(f"Erreur lors de la purge du fichier {file}: {e}")
        return deleted_count


# Instance unique (Singleton)
cache_service = CacheService()
