# AUDIT — Atlas Play / VidTele (Phase 0)

> Audit réalisé le 11/10/2026 sur la branche `main` (commit `6d66ac6`), en **lecture seule**.
> Seul ce fichier a été ajouté, sur la branche `mise-a-jour-totale`.
> Les mesures ont été faites **en local** (Windows 11, serveur lancé sur une base SQLite jetable, Telegram désactivé).
> Rien n'a été mesuré sur la production ni sur un téléphone réel : ces mesures sont prévues au début de la Phase 2 (protocole en §2.6).

---

## Résumé en 10 points

1. **Le démarrage « à froid » d'une vidéo est lent par construction.** Le serveur télécharge **tout le fichier** depuis Telegram, puis le remuxe avec ffmpeg, et seulement ensuite il envoie le premier octet. Le temps jusqu'à la première image (TTFF) dépend donc de la taille de l'épisode. Les chiffres de `PERFORMANCE.md` (1,4 à 2,8 s à froid) ne sont pas reproductibles avec ce code.
2. **Cause probable des arrêts spontanés :** l'application met le **jeton d'accès** (60 min) dans l'URL du flux (`?token=`). Quand il expire, ExoPlayer reçoit un `401` à la requête Range suivante et la lecture s'arrête. Le watchdog relance alors avec… le même jeton expiré.
3. **Bug vérifié :** `GET /api/videos/series`, `/api/videos/home` et `/api/videos/feed` renvoient **422**, parce que la route `/{video_id}` est déclarée avant elles. Or l'application appelle `/api/videos/series` (`seriesListProvider`) et masque l'erreur : les listes de séries de l'Accueil, de la Recherche et du lecteur sont **vides en silence**.
4. **Sécurité critique :** il y a une `SECRET_KEY` par défaut connue dans le code. Le mot de passe admin est **réécrit à chaque démarrage** à partir de la variable d'environnement (par défaut public dans le compose). L'anti brute-force se contourne avec `X-Forwarded-For` (vérifié). Le jeton de flux n'est **pas lié à la vidéo**.
5. **Secret dans Git :** un `TELEGRAM_API_HASH` réel est présent dans `DOKPLOY.md` (commit `a9e8a7e`, dépôt GitHub `Yomix90/VIDTELE`).
6. **L'APK de production est signé avec la clé de debug.** On ne peut pas le publier sur Google Play, et changer de clé oblige les utilisateurs actuels à désinstaller l'application (question bloquante, §8).
7. **Pas de projet iOS** (`mobile/ios/` absent). Pas de migrations versionnées (des `ALTER TABLE` « doux » avec `except: pass`), pas de CI, pas de suivi des plantages, pas de sauvegarde adaptée à Docker.
8. **Côté Flutter, la qualité est bonne :** `flutter analyze` ne signale aucun problème et les 38 tests passent. Mais `reels_screen.dart` fait 2 182 lignes, la navigation est impérative et il n'y a que le thème sombre.
9. **Côté serveur, les tests sont faibles :** 8 scripts (pas pytest), dont **3 sur 8 passent** sur une base neuve. Les dépendances Python ne sont pas figées, et le `pubspec.lock` est ignoré par Git.
10. **Plusieurs bonnes bases sont à conserver :** gestionnaire de lecteur unique, pool de 3 contrôleurs, watchdog, cycle de vie, consentement UMP, gate AdMob, faststart, LRU, quotas de flux.

---

## 1. Architecture actuelle

### 1.1 Vue d'ensemble

```
Canal Telegram privé ──MTProto (Telethon)──► FastAPI (1 worker uvicorn, Python 3.11 Docker)
                                               ├─ SQLite (aiosqlite) /app/data/vidtele.db
                                               ├─ Cache disque LRU /app/cache (video_<msgid>.mp4)
                                               ├─ Miniatures /app/thumbnails, uploads /app/data/uploads
                                               ├─ Admin web (Jinja2 + Bootstrap) /admin
                                               └─ API JSON /api/...
                                                     │ HTTPS (Traefik / Dokploy)
                                                     ▼
                                   App Flutter (Android ; web en mode dégradé ; pas d'iOS)
                                   Riverpod 2 · Dio · video_player (ExoPlayer) · AdMob
```

### 1.2 Serveur (`backend/`)

| Élément | Constat |
|---|---|
| Structure | `routers/` (auth, videos, library, admin **2 698 l.**, admin_web, ads), `services/` (stream, cache, sync, stream_manager, fast_telethon, gemini, parser, benchmark), `models.py`, `schemas.py` (770 l.). Il n'y a pas de couche dépôt : la logique SQL vit dans les routeurs. |
| Base | SQLite et SQLAlchemy 2 async. Les tables sont créées par `create_all`, puis des colonnes sont ajoutées par `ALTER TABLE` dans `init_db()` avec `except: pass`. Un script `migrations/001_*.py` est lancé à la main. **Pas d'Alembic.** |
| Tâches | Synchronisation Telegram périodique (15 min) plus un listener temps réel. Préchauffage avec `asyncio.create_task` sans file d'attente ni limite. |
| Config | `pydantic-settings`. Certaines valeurs sont **écrasées en mémoire** depuis la table `system_settings` (canal, quotas, session Telegram). |
| Docker | Deux Dockerfiles (racine, avec `gcc` inutile, et `backend/`). Deux compose. `docker-compose.dokploy.yml` **publie aussi le port 8000**, ce qui permet de contourner Traefik et HTTPS. |
| Déploiement | Dokploy. Il faut vérifier quelle branche est déployée : `origin/HEAD` pointe vers `master`, mais le travail courant est sur `main`. |

**Versions des dépendances Python** : `requirements.txt` n'utilise que des `>=`, donc **rien n'est figé**. La version en production est celle disponible au moment du build Docker. Versions installées dans le venv local (Python 3.14, alors que Docker utilise 3.11) : FastAPI 0.143.0, Starlette 1.7.0, Uvicorn 0.54.0, SQLAlchemy 2.1.4, Pydantic 2.14.0, pydantic-settings 2.15.0, Telethon 1.45.0, PyJWT 2.15.1, bcrypt 5.0.0, aiosqlite 0.22.1, aiofiles 25.1.0, httpx 0.28.1, Jinja2 3.1.6.

### 1.3 Application (`mobile/`)

| Élément | Constat |
|---|---|
| SDK | Flutter 3.47.7 stable. Contrainte Dart `>=3.2.0`, version de l'app `1.2.0+3`. |
| Structure | Organisée par type de fichier : `core/`, `models/`, `providers/`, `screens/`, `widgets/`. Il n'y a ni couche dépôt ni routeur déclaratif (22 `Navigator.push`). |
| État | Riverpod 2.6.1 (`StateNotifier` et `FutureProvider`). Il reste aussi des singletons globaux (`apiClient`, `storageService`, `VideoPlayerManager()`). |
| Lecteur | `video_player` 2.14.1 (ExoPlayer sur Android, AVPlayer sur iOS). Pool de 3 contrôleurs, `VideoPlayerManager` (un seul lecteur actif, focus audio, wakelock) et `VideoWatchdog` (blocage de 8 s, 3 essais). |
| Android | `minSdk` 24 et `targetSdk` 36 (valeurs par défaut de Flutter), AGP 8.11.1, Kotlin 2.2.20, Gradle 9.3.1. **Deux `MainActivity.kt`** (`com.vidtele.app` et un ancien `com.vidtele.vidtele_mobile`). |
| iOS | **Absent.** |

**Versions des paquets** (lock actuel, puis dernière version disponible) : flutter_riverpod 2.6.1 → **3.4.3** (changements cassants), dio 5.11.1 (à jour), video_player 2.14.1, google_mobile_ads 9.1.0, flutter_secure_storage 9.2.4 → **11.2.0**, cached_network_image 3.4.1 → **4.0.4**, package_info_plus 9.0.1 → 10.2.2, wakelock_plus 1.5.2 → 1.8.1, shared_preferences 2.5.6, audio_session 0.2.4, google_fonts 9.0.0, url_launcher 6.3.3. En dev, `flutter_lints` ^3 est ancien.

### 1.4 Dette technique (synthèse)

- **Fichiers « dieu »** : `reels_screen.dart` (2 182 l.), `admin.py` (2 698 l.), `videos.py` (1 242 l.), `raw-videos.html` (1 088 l.).
- **Code dupliqué** : la logique « obtenir un jeton et créer le contrôleur » est copiée 3 fois dans `reels_screen.dart`, et la restauration du compte Telegram 2 fois (`main.py` et `stream_service.py`).
- **Erreurs avalées** : `catch (_) {}` côté Dart, `except: pass` côté Python. Le bug des séries vides (§3) est passé inaperçu à cause de ça.
- **Builds non reproductibles** : `mobile/*.lock` est dans `.gitignore`, donc `pubspec.lock` n'est pas versionné, et `requirements.txt` n'est pas figé.
- **Documentation divergente** : `PERFORMANCE.md` annonce des gains non mesurables avec le code actuel, `deploy/` vise une installation systemd/nginx et non Dokploy, et le README mélange les deux.
- **Changements locaux non commités** : 4 fichiers supprimés dans `new interface/`. Je ne les ai pas touchés.

---

## 2. Lecture vidéo

### 2.1 Chaîne complète Telegram → serveur → lecteur

```
App : _initControllerForIndex()
  └─ URL = /api/videos/{id}/stream?token=<JWT D'ACCÈS 60 min>   (pas d'appel /stream-token si un jeton d'accès existe)
       └─ ExoPlayer : GET Range: bytes=0-
            └─ stream_video()
                 1. décode le JWT, puis SELECT user, SELECT video
                 2. stream_manager.register_stream_access()  → DELETE expirés + SELECT + COUNT + INSERT/UPDATE + COMMIT
                 3. si Range commence à 0 : views_count += 1 + COMMIT + préchauffage des 2 épisodes suivants
                 4. ensure_video_in_cache()
                      ├─ en cache → lecture du fichier par blocs de 256 Ko (aiofiles)
                      └─ PAS en cache → verrou par vidéo
                            → client.download_media(message)   ◄── TÉLÉCHARGEMENT COMPLET, 1 seule connexion
                            → ffmpeg -c copy +faststart          ◄── jusqu'à 30 s de timeout
                            → seulement ENSUITE, envoi du 1er octet
```

### 2.2 Goulots d'étranglement (par impact)

| # | Problème | Effet | Preuve |
|---|---|---|---|
| L1 | Téléchargement **complet** depuis Telegram avant le 1er octet (`download_media`, non parallélisé) | Le TTFF à froid ≈ la durée du téléchargement complet + le remux. Avec 15 Mo à 2–8 Mo/s, cela fait environ 2 à 8 s, et beaucoup plus pour un film. | `stream_service.py` l.130 |
| L2 | Les requêtes concurrentes sur la même vidéo attendent le **verrou** pendant tout le téléchargement | Le 2e utilisateur, et la 2e requête Range d'ExoPlayer, sont bloqués | `ensure_video_in_cache` |
| L3 | **Écritures SQLite à chaque requête Range** (`register_stream_access` + `COMMIT`), plus le compteur de vues | Contention sur SQLite (un seul écrivain). ExoPlayer fait plusieurs requêtes Range par vidéo et à chaque `seek`. Les vues sont gonflées, car chaque réouverture en `bytes=0-` compte une vue. | `videos.py` l.403-412 |
| L4 | Pas de préchauffage à la synchronisation : seulement « 2 épisodes suivants » au démarrage d'une lecture, et `PREWARM_POPULAR_COUNT` n'est **pas utilisé** | Le premier épisode d'une série est toujours froid | grep |
| L5 | `ffmpeg faststart` exécuté **avant** de servir, sans limite de concurrence | Pics de CPU sur 2 vCPU, latence | `cache_service.apply_faststart` |
| L6 | Le préchauffage utilise `asyncio.create_task` sans file ni plafond | Plusieurs téléchargements Telegram en parallèle peuvent provoquer un FloodWait et saturer la bande passante | `enqueue_prewarm` |
| L7 | `ensure_capacity` ne compte pas les téléchargements en cours | Le cache peut dépasser le quota, avec un risque de disque plein (40 Go au total) | `cache_service` |

### 2.3 Arrêts spontanés : causes identifiées

1. **Expiration du jeton dans l'URL (cause n°1 probable).** Le jeton d'accès dure 60 minutes et peut avoir déjà 59 minutes quand il est mis dans l'URL. ExoPlayer refait des requêtes Range pendant la lecture (seek, reprise réseau, retour d'arrière-plan). Elles reçoivent un `401`, et la lecture s'arrête. Dans `onReloadRequested`, le watchdog **réutilise le jeton d'accès stocké** sans le rafraîchir : si Dio n'a pas encore rafraîchi le jeton, les 3 essais échouent.
2. **Quota de flux.** Le `session_id` correspond aux 32 derniers caractères du jeton : quand le jeton change (rafraîchissement), une nouvelle session est créée et l'ancienne reste comptée 120 s. On peut alors recevoir un `429` pendant un changement rapide d'épisode.
3. **Requête bloquée pendant un téléchargement froid.** Si un `seek` tombe pendant que le serveur télécharge, la requête attend le verrou. Le délai d'ExoPlayer peut expirer avant (son timeout de lecture par défaut est de 8 s).
4. **Rafraîchissement concurrent dans Dio.** Le drapeau `_isRefreshing` fait échouer les autres requêtes `401` simultanées au lieu de les mettre en attente. Un échec de rafraîchissement **efface la session** (déconnexion).

### 2.4 Gestion de l'arrière-plan, de la rotation et de la mémoire

- **Arrière-plan** : c'est bien géré. `paused`/`hidden` mettent en pause, `inactive` est ignoré, la lecture reprend au retour, et les interruptions audio et le débranchement des écouteurs sont pris en compte. La lecture audio en arrière-plan n'existe pas (c'est conforme au cahier des charges).
- **Rotation** : `configChanges` contient `orientation|screenSize`, donc il n'y a pas de recréation de l'activité, ce qui est bien. En revanche, `setPreferredOrientations` force l'orientation **sans respecter le verrouillage de rotation du système**, et la sortie du lecteur revient de force en `portraitUp`.
- **Mémoire** : il y a au plus 3 contrôleurs ExoPlayer, et ceux hors de la cible sont libérés tout de suite, ce qui est bien. Il faudra mesurer sur un téléphone d'entrée de gamme, car 3 décodeurs matériels simultanés peuvent échouer sur certains SoC.
- **Mise en mémoire tampon** : `video_player` **ne permet pas** de régler le `LoadControl` d'ExoPlayer (les valeurs par défaut sont 2,5 s avant lecture et 50 s de tampon max). Pour ajuster ces paramètres, il faudrait `media_kit` ou un fork (choix risqué, à valider, §7).

### 2.5 Points de lecture à conserver

`VideoPlayerManager` (un seul lecteur actif), le pool de 3 contrôleurs, `VideoWatchdog` (avec 3 essais et un bouton Réessayer), la reprise de position, le préchargement 8 s avant la fin, le masquage automatique des contrôles avec son réglage, et la synchronisation de la progression toutes les 4 s.

### 2.6 Mesures

| Mesure | Valeur | Méthode |
|---|---|---|
| Démarrage du serveur (base vide) | ≈ 1 s | uvicorn en local |
| `GET /api/health` | 2 à 19 ms | curl 127.0.0.1 |
| `GET /api/home`, `/api/feed`, `/api/series/top` (base vide) | 200 en ≈ 10–30 ms | curl |
| TTFF chaud / froid, changement d'épisode, arrêts sur 30 min, mémoire, CPU, fps, taille de l'APK, démarrage de l'app | **non mesurés** | Il faut un téléphone et la production : voir le protocole ci-dessous |

**Protocole proposé pour le début de la Phase 2 (mesure « avant ») :**

1. Ajouter des logs horodatés côté serveur : réception de la requête, puis premier octet envoyé.
2. Ajouter dans l'app un chronomètre `initialize()` → première image, envoyé au serveur.
3. Faire 20 lectures froides et 20 chaudes sur 4G, avec un téléphone d'entrée de gamme et un téléphone milieu de gamme.
4. Lancer une session de 30 minutes avec swipe toutes les 30 s.
5. Relever `adb shell dumpsys meminfo`, le profil Flutter DevTools et `docker stats` sur le VPS.

---

## 3. Interface

| Constat | Gravité |
|---|---|
| **Séries vides en silence** à l'Accueil, dans la Recherche et dans le lecteur (`seriesListProvider` reçoit un 422, cf. résumé) | Critique (fonctionnel) |
| Il n'y a que le thème sombre (`getDarkTheme`), et les couleurs sont nommées `netflixBlack`… La couleur d'accent n'est pas configurable | Moyenne |
| `google_fonts` télécharge les polices **au premier lancement** (réseau requis, saut visuel). Elles devraient être embarquées dans l'app | Moyenne |
| Accessibilité : seulement **6** `Semantics`/`semanticLabel`/`tooltip` dans toute l'app. L'échelle de texte système et les tailles de zones tactiles ne sont pas vérifiées | Haute |
| RTL : il est géré par `MaterialApp` via la locale `ar`, mais il y a des positions codées en gauche/droite (à vérifier écran par écran). La locale `en` est présente alors que le cahier des charges demande FR et AR | Moyenne |
| Navigation impérative, sans liens profonds ni restauration d'état | Moyenne |
| `reels_screen.dart` (2 182 l.) mélange interface, réseau, jetons, publicités et orientation : il est difficile à tester et provoque des reconstructions coûteuses (`setState` global) | Haute |
| Les états vides et d'erreur existent (`empty_state`, `error_state`, shimmer) mais les erreurs sont souvent avalées, donc l'écran reste vide au lieu d'afficher l'erreur | Moyenne |
| Le partage de série est déjà supprimé côté app (commit `d880bad`). Il reste à vérifier qu'il n'y a pas de traductions orphelines | Faible |
| Écran `debug/ads_debug_screen.dart` (477 l.) : à vérifier qu'il n'est pas accessible en release | Moyenne |
| Écran `admin/admin_screen.dart` dans l'app mobile, en doublon de l'admin web | À décider |

---

## 4. Compatibilité

| Point | État |
|---|---|
| Android minimum | API 24 (Android 7.0), valeur Flutter par défaut, non figée dans `build.gradle.kts` |
| Android cible | API 36. Il manque une demande d'autorisation de notifications sur Android 13+, mais elle n'est pas nécessaire tant qu'il n'y a pas de notifications push |
| Edge-to-edge (Android 15+) | Mode `edgeToEdge` utilisé. Les marges (insets) restent à vérifier sur les écrans à encoche et les barres de geste |
| Trafic HTTP en clair | `usesCleartextTraffic="true"` : à retirer en production, car le serveur est en HTTPS |
| iOS | **Pas de dossier `ios/`.** Il n'y a ni ID AdMob iOS, ni ATT, ni Info.plist. Le tout est à créer (Mac et Xcode requis pour compiler) |
| Tablettes et grands écrans | Aucune mise en page adaptative détectée |
| Mode sombre/clair | Sombre uniquement |
| Codecs | Aucune vérification : un fichier HEVC, MKV ou VP9 posté sur le canal sera servi tel quel. Le MKV ne passe pas sur iOS |
| Web | Fonctionne en mode dégradé, sans AdMob (hors cahier des charges) |

---

## 5. Sécurité

| # | Problème | Gravité | Preuve |
|---|---|---|---|
| S1 | `SECRET_KEY` par défaut **publique** dans `config.py` et dans `docker-compose.yml` (`:-change_me_...`). Si la variable n'est pas définie en production, n'importe qui peut forger un JWT admin | **Critique** (à vérifier en prod) | code |
| S2 | Le mot de passe admin est **réécrit à chaque démarrage** avec `ADMIN_DEFAULT_PASSWORD`, dont la valeur par défaut est publique (`AdminSecurePass2026!`). Changer le mot de passe depuis l'admin ne sert donc à rien | **Critique** | `main.py` l.52 |
| S3 | Anti brute-force contourné en changeant l'en-tête `X-Forwarded-For` : 8 échecs sans blocage, alors qu'il y a un blocage au 6e échec depuis la même IP | **Haute** | testé |
| S4 | Le jeton de flux contient `vid` mais **n'est jamais vérifié** : un jeton ouvre toutes les vidéos pendant 2 h | Haute | `videos.py` stream_video |
| S5 | Le jeton **d'accès** passe dans l'URL (`?token=`), donc il se retrouve dans les journaux Traefik, l'historique et les proxys | Haute | reels_screen |
| S6 | `TELEGRAM_API_HASH` réel versionné dans `DOKPLOY.md` | Haute | `git log -S` |
| S7 | La **StringSession Telegram est stockée en clair** dans SQLite (`telegram_accounts`) : quiconque obtient une copie de la base contrôle le compte Telegram | Haute | `database.py`, `main.py` |
| S8 | Jetons de rafraîchissement sans état : ni révocation, ni liste des appareils, et l'ancien jeton reste valide après rotation | Moyenne | `auth.py` |
| S9 | CORS `*` avec `allow_credentials=True`, aucun en-tête de sécurité (HSTS, X-Frame-Options, CSP), cookie admin sans `Secure` et pas de protection CSRF sur les formulaires de l'admin | Moyenne | testé (`curl -I`) |
| S10 | Le port 8000 est publié en plus de Traefik, donc on peut accéder à l'API en HTTP sans TLS | Moyenne | compose Dokploy |
| S11 | Le code d'invitation `BIENVENUE-2026` est créé automatiquement et il est prévisible | Moyenne | `main.py` |
| S12 | Les erreurs 500 renvoient `str(e)` au client (fuite d'informations internes) | Faible | `stream_service` |
| S13 | Téléversements sans limite de taille explicite (`UploadFile`), à vérifier dans `admin.py` | Moyenne | grep |
| S14 | Clé API Gemini stockée en base (`system_settings`) | Faible | `gemini_service` |
| S15 | L'URL du serveur est modifiable depuis l'écran de connexion de l'app, donc les jetons peuvent être envoyés vers un autre hôte | Faible | `login_screen` |

**Points positifs :** bcrypt (12 tours), jetons typés (access/refresh/stream), `flutter_secure_storage`, quotas de flux, la table `AuditLog` existe, et `.env`, `*.session` et `*.db` sont bien exclus de Git.

**Sauvegardes :** `deploy/backup.sh` vise `/var/www/vidtele/backend`, qui n'existe pas en Docker. Il n'y a donc **probablement aucune sauvegarde fonctionnelle** des volumes `vidtele_data` (base, session, uploads).

**Journaux :** texte brut via `logging.basicConfig`, sans identifiant de requête ni format JSON, sans rotation gérée et sans masquage des jetons dans les URL.

---

## 6. Fiabilité

| Élément | État |
|---|---|
| Tests serveur | 8 scripts `test_*.py` à lancer à la main (pas pytest). Sur une base neuve : **3 sur 8 passent** (auth, media_organization, stream). Les autres échouent sur des hypothèses dépassées : identifiants codés en dur, `/admin` qui redirige en 303, table absente, comptage figé |
| Tests Flutter | **38/38 réussis**, `flutter analyze` sans problème. Couverture non mesurée |
| CI/CD | Aucune (pas de `.github/workflows`) |
| Suivi des plantages | Aucun (ni Crashlytics ni Sentry) |
| Santé | `/api/health` statique : il ne vérifie ni la base, ni Telegram, ni le disque |
| Reconnexion Telegram | Démarrage paresseux à la première requête de flux (`ensure_video_in_cache`). Il n'y a pas de surveillance active, et la reconnexion déclenchée par une requête utilisateur ajoute de la latence |
| Statistiques de lecture | Il n'y a pas d'endpoint `POST /api/analytics/playback` (seulement `/api/analytics/ads`) |
| Version minimale de l'app | Déjà en place : `GET /api/app/version` avec `min_version` et `force_update`, plus `update_service.dart`. À conserver et compléter |
| Mise à jour sans interruption | Avec un seul conteneur, un redéploiement coupe les flux en cours. Pas de procédure de retour en arrière documentée |

---

## 7. Classement et feuille de route

### 7.1 Problèmes par gravité et par effort

| Priorité | Problème | Effort |
|---|---|---|
| **P0** | S1/S2 : clé secrète et mot de passe admin par défaut, réinitialisation au démarrage | S |
| **P0** | S6 : retirer le hash de `DOKPLOY.md` et en créer un nouveau si le dépôt est public | S |
| **P0** | Ordre des routes : 422 sur `/api/videos/series` (séries vides) | S |
| **P0** | S3/S4 : contournement par `X-Forwarded-For`, jeton de flux non lié à la vidéo | S |
| **P0** | Arrêts spontanés : jeton d'accès dans l'URL, puis 401 à l'expiration | M |
| **P1** | L1/L2 : streaming « passe-plat » depuis Telegram (servir pendant le téléchargement), téléchargement parallèle par blocs | L |
| **P1** | L3 : sortir les écritures SQLite du chemin chaud des requêtes Range | S |
| **P1** | Sauvegardes Docker plus test de restauration | M |
| **P1** | Signature de l'APK de production (dépend de la réponse à la question bloquante, §8) | S |
| **P1** | Alembic (base de référence = schéma actuel de production), dépendances figées, `pubspec.lock` versionné | M |
| **P2** | S7/S8/S9/S10 : session chiffrée, révocation des jetons, en-têtes de sécurité, CORS, CSRF, port 8000 | M |
| **P2** | CI GitHub Actions, tests pytest, suivi des plantages, journaux JSON, `/health` complet | M |
| **P2** | Découpage de `reels_screen.dart`, de `admin.py` et de `videos.py` | L |
| **P3** | Refonte de l'interface (design system, thème clair, accessibilité, tablettes) | L |
| **P3** | Projet iOS | L (et Mac requis) |

### 7.2 Feuille de route recommandée

Je propose d'**ajouter une « Phase 0.5 : correctifs urgents »** avant la Phase 1. Ce sont de petits commits, sans changement d'API cassant, déployables rapidement :

- S1, S2, S3, S4 et S6 ;
- l'ordre des routes ;
- côté serveur : accepter un jeton de flux dédié avec une durée plus longue, sans casser les anciennes versions de l'app.

Le reste suit tes phases 1 à 6, avec ces ajustements :

- **Phase 1** : migrer **Riverpod 3 et go_router en même temps que** la découpe feature-first, pour ne pas réécrire deux fois. Alembic commence par une migration « baseline » appliquée sur une **copie** de la base de production.
- **Phase 2, serveur** : la priorité est le **streaming progressif depuis Telegram**.
  - Avec `iter_download(offset=…)` de Telethon, on peut servir n'importe quelle plage directement depuis Telegram tout en écrivant dans le cache. Cela vaut aussi pour la fin du fichier, ce qui gère les MP4 dont le `moov` est à la fin.
  - Le remux faststart passe alors en tâche de fond **après** le service, dans une file limitée à 1 ffmpeg à la fois.
  - On peut s'attendre à un TTFF à froid d'environ 1 à 2 s, quelle que soit la taille du fichier. C'est **à mesurer**, pas une promesse.
- **HLS** : je **le déconseille pour l'instant**. Un MP4 faststart servi en Range donne déjà un démarrage rapide pour des épisodes courts. Le HLS par remux (`-c copy -f hls`) multiplie les fichiers, complique le cache LRU et le préchauffage, et n'apporte un vrai gain qu'avec plusieurs qualités, c'est-à-dire un transcodage hors de portée de 2 vCPU. À réévaluer si les films longs posent problème.
- **Choix du lecteur** (décision à valider avec toi, après des mesures sur tes appareils) :
  - `video_player`, l'actuel : stable et officiel, mais sans réglage du tampon.
  - `media_kit` : réglage fin, mais basé sur libmpv, donc APK plus lourd (+15 à 25 Mo) et API différente.
  - `video_player` avec un `LoadControl` personnalisé via un fork ou un plugin maison : léger, mais avec un coût de maintenance.

  Je propose un banc de test A/B dans la Phase 2 avant toute décision.

**Principaux risques :**

- Changer de clé de signature : les utilisateurs devraient désinstaller l'app.
- Lancer la première migration Alembic sur une base de production qui a dérivé du code.
- Que le streaming progressif déclenche des FloodWait Telegram : il faudra limiter le débit.
- Migrer Riverpod 3 sur 2 000 lignes de lecteur.
- iOS sans Mac.

---

## 8. Questions

**Bloquantes avant la Phase 0.5 et la Phase 1**

1. **Signature de l'APK** : l'app installée chez tes utilisateurs est signée avec la **clé de debug** d'une machine. As-tu toujours cette machine ou le fichier `~/.android/debug.keystore` utilisé ? Si on passe à une vraie clé de release, les utilisateurs actuels devront **désinstaller puis réinstaller l'app**, et ils perdront leur session (mais pas leurs favoris ni leur historique, qui sont stockés sur le serveur). Est-ce acceptable ?
2. **Production** : dans Dokploy, `SECRET_KEY` et `ADMIN_DEFAULT_PASSWORD` sont-ils définis avec des valeurs fortes, différentes des valeurs par défaut ? Quelle branche Dokploy déploie-t-il, `main` ou `master` ?
3. **Dépôt GitHub** : `Yomix90/VIDTELE` est-il **public** ? Si oui, il faut considérer le hash d'API Telegram comme compromis.
4. Valides-tu l'ajout de la **Phase 0.5 (correctifs urgents)** ?
5. Les 4 fichiers supprimés dans `new interface/` (non commités) : suppression voulue ?

**Celles de ta liste**

6. Versions minimales : Android 7 (API 24) te convient-il ? iOS est-il visé maintenant ou plus tard ? As-tu un Mac et un compte Apple Developer ?
7. Quels téléphones et versions d'Android as-tu pour les tests ? Y a-t-il un modèle d'entrée de gamme prioritaire ?
8. Nom, logo et couleur d'accent : on garde « Atlas Play » et le logo actuel (`atlas_play_logo.svg`) ? L'identifiant Android `com.vidtele.app` ne pourra pas changer sans créer une nouvelle app.
9. Combien d'utilisateurs simultanés attends-tu à court terme ? Quelle est la taille moyenne d'un épisode et d'un film ? Quelle part des 40 Go du disque réserver au cache (actuellement 20 Go) ?
10. Les films doivent-ils aussi s'ouvrir dans le lecteur vertical ?
11. Dans quel ordre de priorité : vitesse de démarrage, design, stabilité, iOS, ou statistiques et administration ?

**Complémentaires**

12. La langue anglaise (`en`) est présente dans l'app : la garde-t-on, ou seulement le français et l'arabe ?
13. L'écran **admin dans l'app mobile** et la **traduction Gemini** : à conserver ?
14. Suivi des plantages : préfères-tu **Firebase Crashlytics** (gratuit, Firebase est déjà dans l'écosystème AdMob) ou **Sentry** (auto-hébergeable, couvre aussi le serveur) ?
