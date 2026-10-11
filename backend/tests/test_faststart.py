"""Remuxage faststart réel (ffmpeg) d'un fichier .tmp : l'index « moov » doit passer devant « mdat »."""
import shutil
import subprocess

import pytest

from app.services.cache_service import cache_service

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent (installé en CI)")


def _ordre_atomes(donnees: bytes) -> list:
    """Atomes MP4 de premier niveau, dans l'ordre du fichier."""
    atomes, position = [], 0
    while position + 8 <= len(donnees):
        taille = int.from_bytes(donnees[position : position + 4], "big")
        atomes.append(donnees[position + 4 : position + 8].decode("latin-1"))
        if taille < 8:
            break
        position += taille
    return atomes


async def test_faststart_sur_fichier_temporaire(tmp_path):
    source = tmp_path / "source.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=160x120:rate=10",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
        check=True,
    )
    atomes = _ordre_atomes(source.read_bytes())
    assert atomes.index("mdat") < atomes.index("moov"), "fichier de départ : index en fin"

    temporaire = tmp_path / "video_42.tmp"
    shutil.copy(source, temporaire)
    await cache_service.faststart_fichier(temporaire)

    atomes = _ordre_atomes(temporaire.read_bytes())
    assert atomes.index("moov") < atomes.index("mdat"), "après faststart : index en tête"
    assert not list(tmp_path.glob("*.remux.tmp")), "fichier intermédiaire supprimé"


async def test_faststart_echoue_sans_abimer_le_fichier(tmp_path):
    temporaire = tmp_path / "video_43.tmp"
    temporaire.write_bytes(b"pas une video")
    with pytest.raises(RuntimeError):
        await cache_service.faststart_fichier(temporaire)
    assert temporaire.read_bytes() == b"pas une video"
