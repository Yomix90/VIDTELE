"""
Service de cache disque avec politique d'éviction LRU (Least Recently Used).
Gère le stockage des vidéos téléchargées depuis Telegram et le respect du quota disque.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, List
from app.config import settings

logger = logging.getLogger("vidtele.cache")


class CacheService:
    """Gestionnaire du cache disque pour les vidéos Telegram."""

    def __init__(self):
        self.cache_dir = Path(settings.CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def get_video_path(self, telegram_message_id: int, extension: str = "mp4") -> Path:
        """Retourne le chemin cible du fichier vidéo en cache en préservant l'extension ou en détectant un fichier existant."""
        clean_ext = extension.lstrip(".") if extension else "mp4"
        # Si un fichier existe déjà sous une autre extension (ex: .ts ou .mp4), le retourner
        for candidate in self.cache_dir.glob(f"video_{telegram_message_id}.*"):
            if candidate.is_file() and candidate.suffix != ".tmp":
                return candidate
        return self.cache_dir / f"video_{telegram_message_id}.{clean_ext}"

    def is_cached(self, telegram_message_id: int) -> bool:
        """Vérifie si la vidéo complète est disponible sur le disque (quelle que soit son extension)."""
        for candidate in self.cache_dir.glob(f"video_{telegram_message_id}.*"):
            if candidate.is_file() and candidate.suffix != ".tmp" and candidate.stat().st_size > 0:
                return True
        return False

    def touch(self, telegram_message_id: int) -> None:
        """Met à jour le temps de dernier accès (atime) pour l'algorithme LRU."""
        for path in self.cache_dir.glob(f"video_{telegram_message_id}.*"):
            if path.is_file() and path.suffix != ".tmp":
                try:
                    os.utime(path, None)
                except Exception as e:
                    logger.warning(f"Impossible de mettre à jour le timestamp de {path}: {e}")

    def get_cache_stats(self) -> Dict[str, float]:
        """Retourne les métriques d'utilisation du cache disque."""
        total_bytes = 0
        file_count = 0

        for file in self.cache_dir.glob("video_*.*"):
            if file.is_file() and file.suffix != ".tmp":
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
            files: List[Path] = [f for f in self.cache_dir.glob("video_*.*") if f.is_file() and f.suffix != ".tmp"]
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
        for file in self.cache_dir.glob("video_*.*"):
            try:
                file.unlink()
                deleted_count += 1
            except Exception as e:
                logger.error(f"Erreur lors de la purge du fichier {file}: {e}")
        return deleted_count

    async def apply_faststart(self, file_path: Path) -> Path:
        """
        Remuxe le fichier vidéo MP4 en déplaçant le 'moov atom' au tout début du fichier
        (drapeau -movflags +faststart de FFmpeg).
        Opération purement structurelle sans aucun réencodage (CPU très faible, ~50ms pour 15 Mo).
        Permet au lecteur mobile de démarrer la lecture dès les premiers 64 Ko reçus
        sans avoir à chercher la fin du fichier.
        """
        if not settings.AUTO_FASTSTART:
            return file_path

        if not file_path.exists() or file_path.suffix.lower() != ".mp4":
            return file_path

        temp_faststart = file_path.parent / f"{file_path.stem}_faststart.tmp"
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(file_path),
            "-c", "copy",
            "-movflags", "+faststart",
            str(temp_faststart),
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)

            if process.returncode == 0 and temp_faststart.exists() and temp_faststart.stat().st_size > 0:
                # Remplacement atomique
                temp_faststart.replace(file_path)
                try:
                    msg_id = int(file_path.stem.replace("video_", "")) if "video_" in file_path.stem else 0
                    if msg_id:
                        self.touch(msg_id)
                except Exception:
                    pass
                logger.info(f"Remuxage FastStart réussi pour {file_path.name}")
            else:
                if temp_faststart.exists():
                    temp_faststart.unlink(missing_ok=True)
                logger.warning(f"FFmpeg FastStart a échoué (code {process.returncode}): {stderr.decode(errors='ignore')[:200]}")
        except Exception as e:
            if temp_faststart.exists():
                temp_faststart.unlink(missing_ok=True)
            logger.warning(f"Impossible d'appliquer FastStart sur {file_path.name} (continuera sans faststart): {e}")

        return file_path


# Instance unique (Singleton)
cache_service = CacheService()
