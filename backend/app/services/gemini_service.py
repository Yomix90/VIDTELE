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

    async def list_available_models(self, api_key: str) -> List[str]:
        """Interroge Google pour récupérer la liste exacte des modèles disponibles pour cette clé."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    models = []
                    for m in data.get("models", []):
                        # On ne garde que les modèles supportant generateContent
                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" in methods:
                            name = m.get("name", "").replace("models/", "")
                            if name:
                                models.append(name)
                    return models
        except Exception as e:
            logger.warning(f"Impossible de lister les modèles Gemini : {e}")
        return []

    async def test_key(self, api_key: str, model: Optional[str] = None) -> Dict[str, Any]:
        """Teste la validité d'une clé API Gemini avec détection et fallback automatique intelligent."""
        raw_model = (model or "").strip()
        target_model = raw_model or self.DEFAULT_MODEL

        # Nettoyage des préfixes éventuels
        if target_model.startswith("models/"):
            target_model = target_model.replace("models/", "")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": "Hello, réponds uniquement 'OK'"}]}]
        }

        async with httpx.AsyncClient(timeout=12.0) as client:
            try:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    return {
                        "success": True,
                        "model_used": target_model,
                        "message": f"Clé API Gemini validée avec succès avec le modèle '{target_model}' !",
                    }

                # Si le modèle demandé n'existe pas (404), on interroge Google pour trouver les modèles actifs
                if res.status_code == 404:
                    available = await self.list_available_models(api_key)
                    # Trouver le meilleur modèle disponible (1.5-flash, 2.0-flash, etc.)
                    best_model = None
                    for candidate in ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-2.0-flash", "gemini-1.5-pro"]:
                        if candidate in available:
                            best_model = candidate
                            break
                    if not best_model and available:
                        best_model = available[0]

                    if best_model:
                        fallback_url = f"https://generativelanguage.googleapis.com/v1beta/models/{best_model}:generateContent?key={api_key}"
                        fallback_res = await client.post(fallback_url, json=payload)
                        if fallback_res.status_code == 200:
                            return {
                                "success": True,
                                "model_used": best_model,
                                "auto_switched": True,
                                "message": f"Le modèle '{target_model}' n'existe pas chez Google. Votre clé a été validée avec succès avec le modèle officiel actif '{best_model}' !",
                            }

                    models_preview = ", ".join(available[:5]) if available else "aucun modèle trouvé"
                    return {
                        "success": False,
                        "error": f"Modèle '{target_model}' introuvable chez Google. Modèles supportés sur votre compte : {models_preview}",
                    }

                data = res.json()
                err = data.get("error", {}).get("message", res.text)
                return {"success": False, "error": f"Erreur Google Gemini ({res.status_code}): {err}"}
            except Exception as e:
                return {"success": False, "error": f"Erreur de connexion aux serveurs Google : {str(e)}"}

    async def translate_and_enrich(
        self,
        title: Optional[str] = None,
        title_fr: Optional[str] = None,
        title_ar: Optional[str] = None,
        title_en: Optional[str] = None,
        synopsis: Optional[str] = None,
        synopsis_fr: Optional[str] = None,
        synopsis_ar: Optional[str] = None,
        synopsis_en: Optional[str] = None,
        content_type: str = "series",
    ) -> Dict[str, Any]:
        """
        Traduit et génère intelligemment les métadonnées multilingues complètes (FR / AR / EN).
        Détecte automatiquement si l'utilisateur a saisi en Arabe, Français ou Anglais,
        conserve la langue d'origine et traduit vers toutes les autres langues.
        """
        conf = await self.get_config()
        api_key = conf.get("api_key")
        model = conf.get("model", self.DEFAULT_MODEL)
        if model in ("gemini-2.0-flash-exp", "gemini-exp", ""):
            model = self.DEFAULT_MODEL

        # Détermination des valeurs de référence fournies
        primary_title = (title_ar or title_fr or title_en or title or "").strip()
        primary_synopsis = (synopsis_ar or synopsis_fr or synopsis_en or synopsis or "").strip()

        if not api_key:
            logger.info("Aucune clé API Gemini configurée. Utilisation du fallback intelligent.")
            return {
                "title_fr": title_fr or primary_title,
                "title_ar": title_ar or primary_title,
                "title_en": title_en or primary_title,
                "synopsis_fr": synopsis_fr or primary_synopsis,
                "synopsis_ar": synopsis_ar or primary_synopsis,
                "synopsis_en": synopsis_en or primary_synopsis,
                "genres": [],
                "year": None,
                "rating_estimated": 7.5,
                "warning": "Veuillez renseigner votre clé API Gemini dans les Paramètres pour activer la traduction automatique par IA.",
            }

        # Construction des éléments fournis pour le prompt
        provided_parts = []
        if title_ar:
            provided_parts.append(f"- Titre en Arabe fourni : \"{title_ar}\"")
        if title_fr:
            provided_parts.append(f"- Titre en Français fourni : \"{title_fr}\"")
        if title_en:
            provided_parts.append(f"- Titre en Anglais fourni : \"{title_en}\"")
        if title and not (title_ar or title_fr or title_en):
            provided_parts.append(f"- Titre fourni (langue à détecter) : \"{title}\"")

        if synopsis_ar:
            provided_parts.append(f"- Synopsis en Arabe fourni : \"{synopsis_ar}\"")
        if synopsis_fr:
            provided_parts.append(f"- Synopsis en Français fourni : \"{synopsis_fr}\"")
        if synopsis_en:
            provided_parts.append(f"- Synopsis en Anglais fourni : \"{synopsis_en}\"")
        if synopsis and not (synopsis_ar or synopsis_fr or synopsis_en):
            provided_parts.append(f"- Synopsis fourni (langue à détecter) : \"{synopsis}\"")

        provided_text = "\n".join(provided_parts) if provided_parts else f"- Titre : \"{primary_title}\""

        prompt = f"""Tu es un expert cinématographique international bilingue et trilingue (Français, Arabe, Anglais) pour la plateforme de streaming Atlas Play.
L'utilisateur te fournit des métadonnées pour un contenu de type '{content_type}'.

ÉLÉMENTS FOURNIS PAR L'UTILISATEUR :
{provided_text}

MISSION D'ENRICHISSEMENT INTELLIGENT :
1. Détecte la langue de chaque champ fourni :
   - Si l'utilisateur a saisi en ARABE (ex: قيامة عثمان, صلاح الدين الأيوبي, شباب البومب, etc.) :
     * Conserve impérativement le titre authentique arabe dans 'title_ar' (en écriture arabe soignée).
     * Traduis et déduis le titre officiel ou naturel en FRANÇAIS dans 'title_fr' (ex: "L'Épopée d'Osman" ou le titre officiel).
     * Déduis le titre international en ANGLAIS dans 'title_en' (ex: "Kurulus: Osman").
     * Si un synopsis en arabe est fourni, traduis-le fidèlement et professionnellement en français ('synopsis_fr') et anglais ('synopsis_en').
   - Si l'utilisateur a saisi en FRANÇAIS :
     * Conserve le titre français dans 'title_fr'.
     * Traduis en arabe littéraire fluide et élégant (فصحى جذابة) dans 'title_ar'.
     * Traduis en anglais dans 'title_en'.
   - Si l'utilisateur a saisi en ANGLAIS :
     * Conserve le titre anglais dans 'title_en'.
     * Traduis en français dans 'title_fr'.
     * Traduis en arabe dans 'title_ar'.
2. Si le film ou la série est célèbre dans les bases mondiales (TMDB, IMDb, Wikipédia), utilise les titres officiels réels reconnus.
3. Rédige un synopsis captivant et engageant pour chaque langue (1 ou 2 paragraphes).
4. Suggère les genres correspondants parmi : action, drame, comedie, policier, mystere, famille, science-fiction, animation.

RÉPONDS STRICTEMENT AU FORMAT JSON SUIVANT (SANS TEXTE AUTOUR) :
{{
  "title_fr": "Titre en français",
  "title_ar": "Titre en arabe",
  "title_en": "Titre en anglais",
  "synopsis_fr": "Synopsis cinématographique en français",
  "synopsis_ar": "ملخص سينمائي جذاب ومشوق باللغة العربية الفصحى",
  "synopsis_en": "Compelling cinematic synopsis in English",
  "genres": ["genre1", "genre2"],
  "year": 2024,
  "age_rating": "Tous publics ou 12+ ou 16+ ou 18+",
  "rating_estimated": 8.0
}}"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
            }
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            try:
                res = await client.post(url, json=payload)
                if res.status_code != 200:
                    err_txt = res.text
                    logger.error(f"Erreur API Gemini ({res.status_code}): {err_txt}")
                    return {
                        "title_fr": title_fr or primary_title,
                        "title_ar": title_ar or primary_title,
                        "title_en": title_en or primary_title,
                        "synopsis_fr": synopsis_fr or primary_synopsis,
                        "synopsis_ar": synopsis_ar or primary_synopsis,
                        "synopsis_en": synopsis_en or primary_synopsis,
                        "genres": [],
                        "error": f"Erreur Google Gemini ({res.status_code})",
                    }

                data = res.json()
                text_out = data["candidates"][0]["content"]["parts"][0]["text"].strip()

                # Nettoyage d'éventuels backticks markdown
                if text_out.startswith("```"):
                    text_out = re.sub(r"^```(?:json)?\s*", "", text_out)
                    text_out = re.sub(r"\s*```$", "", text_out)

                # Extraction d'un bloc JSON {...} si du texte parasite l'entoure
                json_match = re.search(r"\{.*\}", text_out, re.DOTALL)
                if json_match:
                    text_out = json_match.group(0)

                parsed = json.loads(text_out)
                return {
                    "success": True,
                    "title_fr": parsed.get("title_fr") or title_fr or primary_title,
                    "title_ar": parsed.get("title_ar") or title_ar or primary_title,
                    "title_en": parsed.get("title_en") or title_en or primary_title,
                    "synopsis_fr": parsed.get("synopsis_fr") or synopsis_fr or primary_synopsis,
                    "synopsis_ar": parsed.get("synopsis_ar") or synopsis_ar or primary_synopsis,
                    "synopsis_en": parsed.get("synopsis_en") or synopsis_en or primary_synopsis,
                    "genres": parsed.get("genres", []),
                    "year": parsed.get("year"),
                    "age_rating": parsed.get("age_rating", "Tous publics"),
                    "rating_estimated": parsed.get("rating_estimated", 7.5),
                }
            except Exception as e:
                logger.error(f"Exception lors de l'appel Gemini : {e}", exc_info=True)
                return {
                    "title_fr": title_fr or primary_title,
                    "title_ar": title_ar or primary_title,
                    "title_en": title_en or primary_title,
                    "synopsis_fr": synopsis_fr or primary_synopsis,
                    "synopsis_ar": synopsis_ar or primary_synopsis,
                    "synopsis_en": synopsis_en or primary_synopsis,
                    "genres": [],
                    "error": str(e),
                }


gemini_service = GeminiService()
