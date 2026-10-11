"""
Inventaire des routes : garde-fou des refactorisations (découpage des routeurs).

1. Aucune route de l'API ne disparaît (instantané tests/contrat/routes.json, construit
   depuis le schéma OpenAPI public).
2. Aucune route n'est masquée par une autre déclarée avant elle (bug « /{video_id}
   capture /series » corrigé en Phase 0.5) : une requête construite sur le chemin de
   chaque route doit être traitée par la fonction de cette route-là.

Les requêtes sont envoyées sans authentification : elles sont refusées avant toute
action, seul le routage est observé.

Régénérer l'instantané (ajout volontaire de routes) : MAJ_CONTRAT=1 pytest tests/test_inventaire_routes.py
"""
import json
import os
import re
from pathlib import Path

import httpx
import pytest

from app.main import app

FICHIER = Path(__file__).parent / "contrat" / "routes.json"
METHODES = ("get", "post", "put", "patch", "delete")


def _operations():
    """(méthode, chemin, nom de la fonction) pour chaque opération du schéma OpenAPI."""
    ops = []
    for chemin, item in app.openapi()["paths"].items():
        for methode in METHODES:
            if methode in item:
                operation_id = item[methode]["operationId"]
                ops.append((methode.upper(), chemin, operation_id))
    return ops


def test_aucune_route_supprimee():
    actuel = sorted({f"{m} {c}" for m, c, _ in _operations()})
    if os.environ.get("MAJ_CONTRAT") == "1" or not FICHIER.exists():
        FICHIER.write_text(json.dumps(actuel, indent=1, ensure_ascii=False), encoding="utf-8")
        pytest.skip("Inventaire des routes (re)généré.")
    attendu = json.loads(FICHIER.read_text(encoding="utf-8"))
    disparues = sorted(set(attendu) - set(actuel))
    assert not disparues, "Routes supprimées (les apps installées ou l'admin en dépendent) :\n" + "\n".join(disparues)


async def test_aucune_route_masquee(client):
    traitee_par = {}

    async def capture(scope, receive, send):
        await app(scope, receive, send)
        if scope["type"] == "http":
            traitee_par[(scope["method"], scope["path"])] = getattr(scope.get("endpoint"), "__name__", None)

    masquees = []
    transport = httpx.ASGITransport(app=capture, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for methode, chemin, operation_id in _operations():
            concret = re.sub(r"\{[^}]+\}", "1", chemin)
            await client.request(methode, concret)
            fonction = traitee_par.get((methode, concret))
            # operationId = <nom de la fonction>_<chemin>_<méthode>
            if fonction is None or not operation_id.startswith(f"{fonction}_"):
                masquees.append(f"{methode} {chemin} (attendu {operation_id}) traitée par {fonction}")
    assert not masquees, "\n".join(masquees)
