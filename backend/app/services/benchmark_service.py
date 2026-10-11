"""
Service d'analyse de performances et de benchmark de streaming simultané pour VidTele.
Permet d'évaluer la capacité réelle du VPS (débit Mo/s, latence, nombre maximal de spectateurs simultanés).
"""
import asyncio
import os
import platform
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List
import aiofiles

from app.config import settings


class BenchmarkService:
    """Moteur de test de charge et d'estimation de capacité VPS pour le streaming vidéo."""

    def __init__(self):
        self._test_file_path: Path = Path(settings.CACHE_DIR) / "benchmark_test.mp4"

    async def ensure_benchmark_file(self, size_mb: int = 10) -> Path:
        """Garantit l'existence d'un fichier vidéo de test sur le cache disque du VPS."""
        Path(settings.CACHE_DIR).mkdir(parents=True, exist_ok=True)
        target_size = size_mb * 1024 * 1024

        if self._test_file_path.exists() and self._test_file_path.stat().st_size >= target_size:
            return self._test_file_path

        # Génération rapide d'un fichier de test
        chunk = b"\x00" * (256 * 1024)  # Blocs de 256 Ko
        written = 0
        async with aiofiles.open(self._test_file_path, "wb") as f:
            while written < target_size:
                await f.write(chunk)
                written += len(chunk)

        return self._test_file_path

    def get_system_specs(self) -> Dict[str, Any]:
        """Récupère les caractéristiques matérielles du VPS (CPU, RAM, Disque)."""
        specs = {
            "cpu_cores": os.cpu_count() or 1,
            "os_platform": platform.platform(),
            "disk_total_gb": round(shutil.disk_usage(settings.CACHE_DIR).total / (1024**3), 2),
            "disk_free_gb": round(shutil.disk_usage(settings.CACHE_DIR).free / (1024**3), 2),
            "ram_total_gb": None,
            "ram_available_gb": None,
        }

        # Lecture de la RAM sous Linux (/proc/meminfo)
        meminfo = Path("/proc/meminfo")
        if meminfo.exists():
            try:
                with open(meminfo, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            specs["ram_total_gb"] = round(int(line.split()[1]) / (1024 * 1024), 2)
                        elif line.startswith("MemAvailable:"):
                            specs["ram_available_gb"] = round(int(line.split()[1]) / (1024 * 1024), 2)
            except Exception:
                pass

        return specs

    async def run_benchmark(
        self,
        concurrency: int = 20,
        duration_seconds: float = 5.0,
        mode: str = "burst",
        chunk_size_bytes: int = 262144,  # 256 Ko
    ) -> Dict[str, Any]:
        """
        Exécute un test de charge asynchrone simulant `concurrency` lecteurs simultanés.
        Mesure le débit d'E/S, le débit agrégé, le temps de réponse et estime la capacité max du VPS.
        """
        file_path = await self.ensure_benchmark_file(size_mb=10)
        file_size = file_path.stat().st_size

        total_bytes_transferred = 0
        total_chunks = 0
        successful_streams = 0
        failed_streams = 0
        latencies_ms: List[float] = []

        lock = asyncio.Lock()
        stop_event = asyncio.Event()

        # Délai par bloc si mode 'playback' réaliste (ex: 2.5 Mbps = ~320 Ko/s => ~0.8s par bloc de 256 Ko)
        chunk_delay = (chunk_size_bytes / (2.5 * 1024 * 1024 / 8)) if mode == "playback" else 0.0

        async def virtual_player_worker(worker_id: int):
            nonlocal total_bytes_transferred, total_chunks, successful_streams, failed_streams
            bytes_read_stream = 0
            offset = (worker_id * chunk_size_bytes * 2) % max(1, file_size - chunk_size_bytes)

            try:
                async with aiofiles.open(file_path, "rb") as f:
                    while not stop_event.is_set():
                        t_start = time.perf_counter()
                        await f.seek(offset)
                        chunk = await f.read(chunk_size_bytes)
                        t_end = time.perf_counter()

                        if not chunk:
                            # Reboucler
                            offset = 0
                            continue

                        latency = (t_end - t_start) * 1000.0
                        offset = (offset + len(chunk)) % max(1, file_size - chunk_size_bytes)
                        bytes_read_stream += len(chunk)

                        async with lock:
                            total_bytes_transferred += len(chunk)
                            total_chunks += 1
                            if len(latencies_ms) < 2000:
                                latencies_ms.append(latency)

                        if chunk_delay > 0:
                            await asyncio.sleep(chunk_delay)
                        else:
                            # Céder l'event loop pour simuler un vrai flux asynchrone non-bloquant
                            await asyncio.sleep(0.001)

                async with lock:
                    successful_streams += 1

            except Exception:
                async with lock:
                    failed_streams += 1

        t_benchmark_start = time.perf_counter()

        # Démarrage des coroutines simulant les lecteurs simultanés
        tasks = [asyncio.create_task(virtual_player_worker(i)) for i in range(concurrency)]

        # Attendre la durée spécifiée
        await asyncio.sleep(duration_seconds)
        stop_event.set()

        # Attente de la fin propre des coroutines
        await asyncio.gather(*tasks, return_exceptions=True)

        t_benchmark_end = time.perf_counter()
        actual_duration = max(0.1, t_benchmark_end - t_benchmark_start)

        # Calculs de débit et métriques
        throughput_bytes_sec = total_bytes_transferred / actual_duration
        throughput_mb_s = round(throughput_bytes_sec / (1024 * 1024), 2)
        throughput_mbps = round((throughput_bytes_sec * 8) / (1000 * 1000), 2)

        sorted_latencies = sorted(latencies_ms) if latencies_ms else [0.0]
        avg_latency = round(sum(sorted_latencies) / len(sorted_latencies), 2) if sorted_latencies else 0.0
        min_latency = round(sorted_latencies[0], 2)
        max_latency = round(sorted_latencies[-1], 2)
        p50_latency = round(sorted_latencies[len(sorted_latencies) // 2], 2)
        p95_index = int(len(sorted_latencies) * 0.95)
        p95_latency = round(sorted_latencies[min(p95_index, len(sorted_latencies) - 1)], 2)

        # Modèle d'estimation de capacité VPS (utilisateurs simultanés sans coupure)
        # Profils de consommation typiques :
        # - SD 480p  : ~0.8 Mbps (~100 Ko/s)
        # - HD 720p  : ~2.0 Mbps (~250 Ko/s)
        # - FHD 1080p: ~3.5 Mbps (~440 Ko/s)
        effective_throughput_mbps = throughput_mbps if mode == "burst" else max(throughput_mbps, concurrency * 2.5)

        estimated_sd_users = max(concurrency, int(effective_throughput_mbps / 0.8))
        estimated_hd_users = max(concurrency, int(effective_throughput_mbps / 2.0))
        estimated_fhd_users = max(1, int(effective_throughput_mbps / 3.5))

        # Recommandation personnalisée de limite globale pour le serveur
        # Pour garantir une marge de sécurité de 25% contre les pics :
        recommended_limit = min(500, max(20, int(estimated_hd_users * 0.8)))

        # Diagnostic des goulets d'étranglement
        diagnostics = []
        if settings.MAX_CONCURRENT_STREAMS_GLOBAL < recommended_limit:
            diagnostics.append(
                f"Votre limite logicielle MAX_CONCURRENT_STREAMS_GLOBAL ({settings.MAX_CONCURRENT_STREAMS_GLOBAL}) "
                f"est inférieure à ce que votre VPS peut supporter ({recommended_limit} flux recommandés). "
                f"Vous pouvez l'augmenter dans les paramètres."
            )
        else:
            diagnostics.append(
                f"Votre VPS est bien calibré : limite actuelle réglée à {settings.MAX_CONCURRENT_STREAMS_GLOBAL} flux simultanés."
            )

        if avg_latency < 20.0:
            diagnostics.append("Temps d'accès disque ultra-rapide (< 20 ms), parfait pour la réactivité du lecteur.")
        elif avg_latency < 100.0:
            diagnostics.append("Temps d'accès disque satisfaisant.")
        else:
            diagnostics.append("Temps d'accès disque élevé sous forte charge, envisagez un stockage NVMe ou SSD.")

        return {
            "success": True,
            "concurrency_tested": concurrency,
            "mode": mode,
            "duration_seconds": round(actual_duration, 2),
            "total_bytes_transferred": total_bytes_transferred,
            "total_chunks_streamed": total_chunks,
            "successful_streams": successful_streams,
            "failed_streams": failed_streams,
            "throughput_mb_s": throughput_mb_s,
            "throughput_mbps": throughput_mbps,
            "latency": {
                "avg_ms": avg_latency,
                "min_ms": min_latency,
                "max_ms": max_latency,
                "p50_ms": p50_latency,
                "p95_ms": p95_latency,
            },
            "capacity_estimates": {
                "sd_480p_users": estimated_sd_users,
                "hd_720p_users": estimated_hd_users,
                "fhd_1080p_users": estimated_fhd_users,
                "recommended_global_limit": recommended_limit,
                "current_global_limit": settings.MAX_CONCURRENT_STREAMS_GLOBAL,
            },
            "system_specs": self.get_system_specs(),
            "diagnostics": diagnostics,
        }


benchmark_service = BenchmarkService()
