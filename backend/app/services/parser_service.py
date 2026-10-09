"""
Service d'analyse et de détection automatique des motifs de fichiers vidéo Telegram.
Détecte les séries (S01E02, etc.), films, années, résolutions et génère les slugs.
"""
import re
import unicodedata
from typing import Any, Dict, Optional


def slugify(text: str) -> str:
    """Génère un slug propre à partir d'une chaîne de caractères (ex: 'Breaking Bad' -> 'breaking-bad')."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


class VideoParserService:
    """Analyseur automatique de métadonnées pour les fichiers multimédias Telegram."""

    # Balises de release et formats techniques à nettoyer
    RELEASE_TAGS = [
        r"\b(1080p|720p|480p|2160p|4k|uhd)\b",
        r"\b(bluray|bdrip|brrip|web-dl|webrip|web|hdtv|dvdrip)\b",
        r"\b(x264|x265|hevc|h264|h265|avc|10bit|aac|ac3|dts|mp4|mkv|avi)\b",
        r"\b(multi|vostfr|vf|truefrench|french|eng|subfrench)\b",
        r"\b(yts|yify|rarbg|psa|eztv|galaxy)\b",
    ]

    # Motifs pour détecter une série (Saison et Épisode)
    SERIES_PATTERNS = [
        # S01E02 ou s1e2
        re.compile(r"[\._\s-][sS](?P<season>\d{1,2})[eE](?P<episode>\d{1,3})[\._\s-]?", re.IGNORECASE),
        # 1x02 ou 01x02
        re.compile(r"[\._\s-](?P<season>\d{1,2})[xX](?P<episode>\d{1,3})[\._\s-]?", re.IGNORECASE),
        # Saison 1 Episode 2 / Season 1 Episode 2
        re.compile(r"\b(?:saison|season)[\s_.-]?(?P<season>\d{1,2})[\s_.-]+(?:episode|ep)[\s_.-]?(?P<episode>\d{1,3})\b", re.IGNORECASE),
        # Episode 02 / Ep 02 / Ep. 02 / الحلقة 02
        re.compile(r"\b(?:episode|ep|épisode|الحلقة)[\s_.-]?(?P<episode>\d{1,3})\b", re.IGNORECASE),
    ]

    # Motif pour détecter une année (1950 - 2030)
    YEAR_PATTERN = re.compile(r"[\s._\(\[](19\d{2}|20\d{2})[\s._\)\]]")

    def parse_video_title(self, raw_title: str) -> Dict[str, Any]:
        """
        Analyse le nom d'un fichier ou le titre d'une vidéo Telegram
        et extrait les informations de type, titre nettoyé, saison, épisode, et année.
        """
        if not raw_title:
            return {
                "kind": "movie",
                "clean_title": "Vidéo sans titre",
                "season": 1,
                "episode": 1,
                "year": None,
                "confidence": 0.1,
            }

        # Retirer l'extension de fichier si présente
        clean = re.sub(r"\.(mp4|mkv|avi|mov|wmv|flv|webm)$", "", raw_title.strip(), flags=re.IGNORECASE)

        # 1. Détection de motif de série
        detected_season = None
        detected_episode = None
        series_match = None

        for pattern in self.SERIES_PATTERNS:
            match = pattern.search(clean)
            if match:
                groups = match.groupdict()
                if "season" in groups and groups["season"]:
                    detected_season = int(groups["season"])
                else:
                    detected_season = 1  # Par défaut saison 1 si seulement l'épisode est mentionné
                
                if "episode" in groups and groups["episode"]:
                    detected_episode = int(groups["episode"])
                
                series_match = match
                break

        # 2. Détection de l'année
        year = None
        year_match = self.YEAR_PATTERN.search(clean)
        if year_match:
            year = int(year_match.group(1))

        # 3. Extraction et nettoyage du titre principal
        if series_match:
            kind = "series"
            # Extraire tout ce qui est avant le tag S01E02
            title_part = clean[:series_match.start()]
            confidence = 0.95
        elif year_match:
            kind = "movie"
            # Extraire tout ce qui est avant l'année
            title_part = clean[:year_match.start()]
            confidence = 0.85
        else:
            kind = "movie"
            title_part = clean
            confidence = 0.50

        # Remplacer les points, tirets et underscores par des espaces
        clean_title = re.sub(r"[\._-]+", " ", title_part).strip()

        # Supprimer les balises de release
        for tag_regex in self.RELEASE_TAGS:
            clean_title = re.sub(tag_regex, "", clean_title, flags=re.IGNORECASE).strip()

        # Supprimer les espaces multiples
        clean_title = re.sub(r"\s+", " ", clean_title).strip()
        if not clean_title:
            clean_title = raw_title.strip()

        return {
            "kind": kind,
            "clean_title": clean_title,
            "season": detected_season or 1,
            "episode": detected_episode or 1,
            "year": year,
            "confidence": confidence,
            "slug": slugify(clean_title),
        }


parser_service = VideoParserService()
