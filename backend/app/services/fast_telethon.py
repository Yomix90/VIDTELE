"""
Module d'accélération MTProto pour Telethon (Fast Telethon Upload).
Permet l'envoi de fichiers et vidéos vers Telegram en morceaux parallèles (512 Ko)
multi-connexions pour démultiplier la vitesse d'upload (multipliée par 5 à 10x).
"""
import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Callable, Optional, Union

from telethon import helpers
from telethon.tl import functions, types
from telethon.tl.types import InputFile, InputFileBig

logger = logging.getLogger(__name__)

# Taille optimale d'un morceau MTProto recommandée par Telegram : 512 Ko (524288 octets)
PART_SIZE = 512 * 1024


async def fast_upload_file(
    client,
    file_path: Union[str, Path],
    file_name: Optional[str] = None,
    max_workers: int = 6,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Union[InputFile, InputFileBig]:
    """
    Téléverse un fichier local vers les serveurs Telegram en parallélisant les requêtes MTProto
    (SaveBigFilePartRequest / SaveFilePartRequest).
    
    Retourne un objet InputFile ou InputFileBig prêt à être envoyé sans ré-upload via client.send_file().
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Fichier introuvable sur le disque : {path}")

    file_size = path.stat().st_size
    if file_size == 0:
        raise ValueError("Impossible de téléverser un fichier vide (0 octet).")

    if not file_name:
        file_name = path.name

    is_big = file_size > 10 * 1024 * 1024  # Plus grand que 10 Mo
    part_count = (file_size + PART_SIZE - 1) // PART_SIZE
    file_id = helpers.generate_random_long()

    # File d'attente contenant tous les index de morceaux à envoyer
    queue = asyncio.Queue()
    for part_index in range(part_count):
        offset = part_index * PART_SIZE
        chunk_len = min(PART_SIZE, file_size - offset)
        queue.put_nowait((part_index, offset, chunk_len))

    uploaded_bytes = 0
    lock = asyncio.Lock()
    hash_md5 = hashlib.md5() if not is_big else None
    parts_data = {} if not is_big else None

    with open(path, "rb") as f:
        async def worker():
            nonlocal uploaded_bytes
            while not queue.empty():
                try:
                    part_index, offset, chunk_len = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                # Lecture synchrone déléguée dans un thread séparé pour ne jamais bloquer l'event loop
                def read_chunk():
                    f.seek(offset)
                    return f.read(chunk_len)

                chunk = await asyncio.to_thread(read_chunk)

                if len(chunk) != chunk_len:
                    raise IOError(
                        f"Taille lue invalide pour le morceau {part_index}: {len(chunk)} octets au lieu de {chunk_len}"
                    )

                if not is_big:
                    parts_data[part_index] = chunk

                # Préparation de la requête MTProto
                if is_big:
                    req = functions.upload.SaveBigFilePartRequest(
                        file_id=file_id,
                        file_part=part_index,
                        file_total_parts=part_count,
                        bytes=chunk,
                    )
                else:
                    req = functions.upload.SaveFilePartRequest(
                        file_id=file_id,
                        file_part=part_index,
                        bytes=chunk,
                    )

                # Tentative d'envoi avec reprise automatique sur temporisation / floodwait
                sent = False
                for attempt in range(4):
                    try:
                        res = await client(req)
                        if res:
                            sent = True
                            break
                    except Exception as exc:
                        exc_msg = str(exc)
                        if "FLOOD_WAIT" in exc_msg or "FLOOD_PREMIUM_WAIT" in exc_msg:
                            wait_sec = 2
                            digits = "".join(filter(str.isdigit, exc_msg))
                            if digits:
                                wait_sec = int(digits)
                            logger.warning(f"Telegram FloodWait ({wait_sec}s) sur upload morceau {part_index}")
                            await asyncio.sleep(min(wait_sec, 30))
                        else:
                            await asyncio.sleep(0.4 * (attempt + 1))

                if not sent:
                    raise RuntimeError(f"Échec définitif du téléversement du morceau {part_index}/{part_count} vers Telegram.")

                # Mise à jour de la progression
                async with lock:
                    uploaded_bytes += chunk_len
                    current_up = uploaded_bytes

                if progress_callback:
                    try:
                        cb_res = progress_callback(current_up, file_size)
                        if asyncio.iscoroutine(cb_res):
                            await cb_res
                    except Exception:
                        pass

                queue.task_done()

        # Ajuster le nombre de workers selon le nombre total de morceaux
        actual_workers = max(1, min(max_workers, part_count))
        workers = [asyncio.create_task(worker()) for _ in range(actual_workers)]
        await asyncio.gather(*workers)

    if not is_big:
        for idx in range(part_count):
            hash_md5.update(parts_data[idx])
        return types.InputFile(
            id=file_id,
            parts=part_count,
            name=file_name,
            md5_checksum=hash_md5.hexdigest(),
        )
    else:
        return types.InputFileBig(
            id=file_id,
            parts=part_count,
            name=file_name,
        )
