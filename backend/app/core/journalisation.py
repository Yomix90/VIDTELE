"""
Journalisation structurée.

- Chaque ligne porte l'identifiant de la requête en cours (request_id) pour suivre
  un problème de bout en bout (app -> Traefik -> serveur).
- Les jetons (?token=..., Bearer ..., refresh_token) sont masqués avant écriture :
  ils ne doivent jamais apparaître dans les journaux Dokploy.
- LOG_FORMAT=json produit une ligne JSON par événement (exploitable par un outil
  de collecte) ; LOG_FORMAT=texte (défaut) reste lisible dans l'interface Dokploy.
"""
import json
import logging
import re
from contextvars import ContextVar
from datetime import datetime, timezone

# Identifiant de la requête HTTP en cours ("-" hors requête : démarrage, tâches de fond)
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_MOTIFS_SECRETS = [
    # ?token=xxx ou &token=xxx dans une URL
    (re.compile(r"(?i)([?&](?:token|access_token|refresh_token)=)[^&\s\"']+"), r"\1***"),
    # En-tête Authorization: Bearer xxx
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-_\.=]+"), r"\1***"),
    # "refresh_token": "xxx" / 'password': 'xxx' dans un dictionnaire journalisé
    (
        re.compile(
            r"(?i)([\"']?(?:refresh_token|access_token|password|string_session|api_hash)[\"']?\s*[:=]\s*[\"']?)[^\"',\s}]+"
        ),
        r"\1***",
    ),
    # JWT nu (trois segments base64url commençant par eyJ)
    (re.compile(r"eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"), "***jwt***"),
]


def masquer_secrets(texte: str) -> str:
    """Remplace les jetons et mots de passe d'un texte par ***."""
    for motif, remplacement in _MOTIFS_SECRETS:
        texte = motif.sub(remplacement, texte)
    return texte


class FiltreContexte(logging.Filter):
    """Ajoute request_id à chaque enregistrement et masque les secrets."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        if isinstance(record.msg, str):
            record.msg = masquer_secrets(record.msg)
        if isinstance(record.args, tuple):
            # On garde un tuple (certains formateurs en dépendent) en masquant ses textes
            record.args = tuple(masquer_secrets(a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: masquer_secrets(v) if isinstance(v, str) else v for k, v in record.args.items()}
        return True


class FormateurJson(logging.Formatter):
    """Une ligne JSON par événement."""

    def format(self, record: logging.LogRecord) -> str:
        donnees = {
            "horodatage": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "niveau": record.levelname,
            "module": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        for cle in ("methode", "chemin", "statut", "duree_ms", "ip"):
            if hasattr(record, cle):
                donnees[cle] = getattr(record, cle)
        if record.exc_info:
            donnees["exception"] = masquer_secrets(self.formatException(record.exc_info))
        return json.dumps(donnees, ensure_ascii=False)


class FormateurTexte(logging.Formatter):
    """Format lisible ; l'exception éventuelle est elle aussi masquée."""

    def __init__(self):
        super().__init__("%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s")

    def formatException(self, ei) -> str:
        return masquer_secrets(super().formatException(ei))


def configurer_journalisation(niveau: str = "INFO", format_: str = "texte") -> None:
    """Configure la racine et les journaux d'uvicorn (appelée une fois au chargement de l'app)."""
    formateur = FormateurJson() if format_.lower() == "json" else FormateurTexte()

    gestionnaire = logging.StreamHandler()
    gestionnaire.setFormatter(formateur)
    gestionnaire.addFilter(FiltreContexte())

    racine = logging.getLogger()
    for h in list(racine.handlers):
        racine.removeHandler(h)
    racine.addHandler(gestionnaire)
    racine.setLevel(niveau.upper())

    # Uvicorn installe ses propres gestionnaires avant d'importer l'app : on les aligne
    for nom in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        journal = logging.getLogger(nom)
        journal.handlers = []
        journal.propagate = True
    # Le journal d'accès d'uvicorn est remplacé par celui du middleware (avec durée et request_id)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # Telethon est très bavard en INFO (reconnexions réseau)
    logging.getLogger("telethon").setLevel(max(logging.WARNING, racine.level))
