"""
Service d'intégration Google Gemini AI pour la traduction et la génération
automatique des métadonnées cinématographiques (Français, Arabe, Anglais).
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import SystemSetting

logger = logging.getLogger("vidtele.gemini")


class GeminiService:
    """Service de traduction et d'enrichissement par IA Google Gemini."""

    DEFAULT_MODEL = "gemini-1.5-flash"

    async def get_config(self) -> Dict[str, str]:
        """Récupère la clé API et le modèle configurés."""
        import os
        api_key = os.getenv("GEMINI_API_KEY", "")
        model = os.getenv("GEMINI_MODEL", self.DEFAULT_MODEL)

        try:
            async with AsyncSessionLocal() as db:
                stmt = select(SystemSetting).where(SystemSetting.key.in_(["GEMINI_API_KEY", "GEMINI_MODEL"]))
                res = await db.execute(stmt)
                settings_dict = {row.key: row.value for row in res.scalars().all()}
                if settings_dict.get("GEMINI_API_KEY"):
                    api_key = settings_dict["GEMINI_API_KEY"].strip()
                if settings_dict.get("GEMINI_MODEL"):
                    model = settings_dict["GEMINI_MODEL"].strip()
        except Exception as e:
            logger.warning(f"Erreur lors de la lecture des paramètres Gemini : {e}")

        return {"api_key": api_key, "model": model or self.DEFAULT_MODEL}

    async def test_key(self, api_key: str, model: Optional[str] = None) -> Dict[str, Any]:
        """Teste la validité d'une clé API Gemini."""
        target_model = model or self.DEFAULT_MODEL
        if target_model in ("gemini-2.0-flash-exp", "gemini-exp", ""):
            target_model = self.DEFAULT_MODEL

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": "Hello, reponds simplement 'OK'"}]}]
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    return {"success": True, "message": f"Clé API Gemini validée avec succès avec le modèle {target_model} !"}
                else:
                    data = res.json()
                    err = data.get("error", {}).get("message", res.text)
                    return {"success": False, "error": f"Erreur Gemini ({res.status_code}): {err}"}
            except Exception as e:
                return {"success": False, "error": f"Erreur de connexion aux serveurs Google : {str(e)}"}

    async def translate_and_enrich(
        self,
        title: str,
        synopsis: Optional[str] = None,
        content_type: str = "series",
    ) -> Dict[str, Any]:
        """
        Traduit et génère les métadonnées multilingues complètes (FR / AR / EN)
        avec synopsis cinématique et suggestion de genres.
        """
        conf = await self.get_config()
        api_key = conf.get("api_key")
        model = conf.get("model", self.DEFAULT_MODEL)
        if model in ("gemini-2.0-flash-exp", "gemini-exp", ""):
            model = self.DEFAULT_MODEL

        if not api_key:
            logger.info("Aucune clé API Gemini configurée. Utilisation du fallback basique.")
            return {
                "title_fr": title,
                "title_ar": title,
                "title_en": title,
                "synopsis_fr": synopsis or "",
                "synopsis_ar": synopsis or "",
                "synopsis_en": synopsis or "",
                "genres": [],
                "year": None,
                "rating_estimated": 7.5,
                "warning": "Veuillez renseigner votre clé API Gemini dans les Paramètres pour activer la traduction automatique par IA.",
            }

        prompt = f"""Tu es un expert international en métadonnées de films et séries TV pour la plateforme de streaming Atlas Play.
Analyse le titre et le synopsis suivants (qui peuvent être en français, arabe, anglais ou autre langue) :
Type de contenu: {content_type}
Titre fourni: {title}
Synopsis fourni: {synopsis or "Non fourni"}

Génère un objet JSON STRICT avec les champs suivants :
{{
  "title_fr": "Titre officiel ou traduit en français",
  "title_ar": "Titre officiel ou cinématique en arabe (écriture arabe standard)",
  "title_en": "Titre officiel ou en anglais",
  "synopsis_fr": "Un synopsis cinématique captivant et professionnel en français (1 ou 2 paragraphes)",
  "synopsis_ar": "Un synopsis cinématique captivant en arabe standard moderne (فصحى جذابة)",
  "synopsis_en": "A captivating, professional synopsis in English",
  "genres": ["liste des genres correspondants parmi: action, drame, comedie, policier, mystere, famille, science-fiction, animation"],
  "year": 2024,
  "age_rating": "Tous publics ou 12+ ou 16+ ou 18+",
  "rating_estimated": 7.8
}}
Réponds UNIQUEMENT avec le JSON, sans balises markdown ni texte autour."""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
            }
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            try:
                res = await client.post(url, json=payload)
                if res.status_code != 200:
                    err_txt = res.text
                    logger.error(f"Erreur API Gemini ({res.status_code}): {err_txt}")
                    return {
                        "title_fr": title,
                        "title_ar": title,
                        "title_en": title,
                        "synopsis_fr": synopsis or "",
                        "synopsis_ar": synopsis or "",
                        "synopsis_en": synopsis or "",
                        "genres": [],
                        "error": f"Erreur Google Gemini: {res.status_code}",
                    }

                data = res.json()
                text_out = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                # Nettoyage d'éventuels backticks markdown
                if text_out.startswith("```"):
                    text_out = re.sub(r"^```(?:json)?\n", "", text_out)
                    text_out = re.sub(r"\n```$", "", text_out)

                parsed = json.loads(text_out)
                return {
                    "success": True,
                    "title_fr": parsed.get("title_fr") or title,
                    "title_ar": parsed.get("title_ar") or title,
                    "title_en": parsed.get("title_en") or title,
                    "synopsis_fr": parsed.get("synopsis_fr") or synopsis or "",
                    "synopsis_ar": parsed.get("synopsis_ar") or synopsis or "",
                    "synopsis_en": parsed.get("synopsis_en") or synopsis or "",
                    "genres": parsed.get("genres", []),
                    "year": parsed.get("year"),
                    "age_rating": parsed.get("age_rating", "Tous publics"),
                    "rating_estimated": parsed.get("rating_estimated", 7.5),
                }
            except Exception as e:
                logger.error(f"Exception lors de l'appel Gemini : {e}", exc_info=True)
                return {
                    "title_fr": title,
                    "title_ar": title,
                    "title_en": title,
                    "synopsis_fr": synopsis or "",
                    "synopsis_ar": synopsis or "",
                    "synopsis_en": synopsis or "",
                    "genres": [],
                    "error": str(e),
                }


gemini_service = GeminiService()
