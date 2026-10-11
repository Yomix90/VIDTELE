# Architecture — Atlas Play (VidTele)

> Document vivant, mis à jour à chaque phase de la refonte (`AUDIT.md` pour l'état initial).
> Dernière mise à jour : Phase 1 (fondations).

## 1. Vue d'ensemble

```
Canal Telegram privé ──MTProto (Telethon)──► Serveur FastAPI (Docker, Dokploy, VPS Hetzner)
                                                ├─ SQLite  /app/data/vidtele.db  (migrations Alembic)
                                                ├─ Cache vidéo LRU /app/cache
                                                ├─ Admin web (Jinja2) /admin
                                                └─ API JSON /api/...
                                                      │ HTTPS (Traefik)
                                                      ▼
                                        Application Flutter (Android ; iOS prévu)
```

## 2. Serveur (`backend/`)

### 2.1 Couches

| Dossier | Rôle | Règle |
|---|---|---|
| `app/routers/` | Couche HTTP : validation des entrées, appel des services/dépôts, mise en forme des réponses | Aucune requête SQL complexe nouvelle ici : passer par un dépôt |
| `app/services/` | Logique métier : streaming, cache, synchronisation Telegram, versions de l'app, IA | Indépendant de HTTP quand c'est possible |
| `app/repositories/` | Accès aux données (SQLAlchemy) | Fonctions réutilisables et testables seules |
| `app/core/` | Transverse : journalisation, contexte de requête, erreurs, migrations, version minimale | Ne dépend d'aucun routeur |
| `app/models.py`, `app/schemas.py` | Modèles de base / schémas Pydantic de l'API | Toute modification de modèle = migration Alembic |
| `migrations/` | Migrations Alembic versionnées (`versions/0001_...` = référence) | Testées sur une copie de la base de production |
| `tests/` | Tests pytest (base jetable, sans Telegram) | `python -m pytest` depuis `backend/` |

### 2.2 Routeurs

```
app/routers/
├── sante.py               /api/health, /api/health/ready
├── auth.py                /api/auth/*  (inscription sur invitation, connexion, rafraîchissement)
├── videos/
│   ├── catalogue.py       /api/videos (liste, catégories, séries, top, accueil, feed)
│   └── lecture.py         /api/videos/{id} (détail, miniature, jetons de flux, streaming Range)
├── alias.py               /api/home, /api/feed, /api/series/...  (utilisés par l'app)
├── library.py             /api/history, /api/favorites, progression
├── application_mobile.py  /api/app/version
├── ads.py                 /api/config/ads, /api/analytics/ads
├── admin/                 /api/admin/*  (13 modules par domaine)
└── admin_web.py           /admin (pages HTML)
```

### 2.3 Cycle d'une requête

1. `MiddlewareContexteRequete` : `request_id` (en-tête `X-Request-ID`), journal d'accès avec durée, jetons masqués.
2. CORS.
3. `MiddlewareVersionMinimale` : 426 si `X-App-Version` < version minimale (apps ≥ 1.3.0).
4. Routeur → service/dépôt → réponse.
5. Erreur : format uniforme `{"detail", "code", "request_id"}` sur `/api`.

### 2.4 Démarrage

1. Configuration (`app/config.py`) : refus des secrets publics (clé JWT générée si absente).
2. Migrations (`app/core/migrations.py`) : sauvegarde automatique puis mise à niveau Alembic.
3. Données de référence (genres, rangées d'accueil), compte admin initial.
4. Connexion Telegram et synchronisation périodique.

### 2.5 Garde-fous automatiques (CI)

- **Contrat API** (`tests/contrat/formes_api.json`) : forme des 21 réponses utilisées par l'app installée.
- **Inventaire des routes** (`tests/contrat/routes.json`) et détection des routes masquées.
- **ruff** (pyflakes) : noms non définis, imports inutilisés.
- **Images Docker** construites et démarrées à chaque push.

## 3. Application (`mobile/`)

*(Section complétée au fil de la Phase 1 : organisation par fonctionnalités, Riverpod, go_router.)*

### 3.1 Suivi des erreurs

`lib/core/erreurs/suivi_erreurs.dart` capture les erreurs Flutter et asynchrones et les transmet à un
`RapporteurErreurs` (console aujourd'hui, Firebase Crashlytics dès que le projet Firebase est créé).
