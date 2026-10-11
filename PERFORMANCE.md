# Performance de la lecture — mesures avant / après

> Ce document remplace l'ancienne version, dont les chiffres (TTFF 0,3–0,9 s, etc.) n'avaient pas été
> mesurés et n'étaient pas atteignables avec le code de l'époque (téléchargement complet avant le
> premier octet). Ici, chaque valeur indique **comment** elle a été obtenue.

## 1. Objectifs (cahier des charges, Phase 2)

| Indicateur | Objectif |
|---|---|
| Première image, épisode préchargé | < 1,5 s |
| Première image, épisode non préchargé (4G correcte) | < 3 s |
| Changement d'épisode | < 0,5 s |
| Arrêts spontanés sur 30 min de lecture | 0 |

## 2. Serveur — temps jusqu'au premier octet (vidéo **non** en cache)

Mesure : `GestionnaireTelechargements` avec une source Telegram **simulée** (épisode de 20 Mo,
Telegram à 5 Mo/s par morceaux de 512 Ko, 150 ms pour lire le message), sur le PC de développement.

| Cas | Avant (code de la v1.2) | Après (Phase 2) |
|---|---|---|
| Début du fichier | ≥ 4,2 s : téléchargement **complet** puis remuxage ffmpeg | **279 ms** |
| Fin du fichier (index MP4 en fin, demandé par ExoPlayer) | idem, ≥ 4,2 s | **267 ms** (lecture directe à la position) |
| Plusieurs lecteurs sur la même vidéo | 1 téléchargement, les autres **bloqués** par le verrou | 1 téléchargement **partagé**, chacun servi au fil de l'eau |
| Écritures SQLite par requête Range | 2 à 3 (quota + vues) | 0 (au plus 1 toutes les 30 s par session) |

Vidéo **en cache** (mesuré sur serveur local + émulateur) : attente serveur **1 à 3 ms** par requête.

À confirmer en production : le débit réel de Telegram depuis le VPS Hetzner (le journal
`Téléchargement terminé : vidéo X (… Mo en … s)` le donne pour chaque vidéo).

## 3. Application — instrumentation

L'application envoie désormais ses mesures (`POST /api/analytics/playback`) :
première image (préchargée ou non), blocages > 300 ms, reprises du watchdog, erreurs.
Résumé : `GET /api/admin/stats/playback?jours=7` (TTFF p50/p90, blocages, erreurs par code).

### Émulateur (Android 17 x86_64, décodage vidéo **logiciel**) — non représentatif

| Mesure | Valeur | Commentaire |
|---|---|---|
| Première image, 1re vidéo préchargée à l'ouverture de « Découvrir » | 455 ms | |
| Première image après swipe (2e vidéo préchargée) | 8,2 s | 2 décodeurs HD logiciels simultanés sur l'émulateur |
| Blocages | 0,5 à 1,5 s en début de vidéo | idem |

## 4. Mesures réelles à faire (Vivo X200 Pro, Android 16)

1. Brancher le téléphone en USB, activer le **débogage USB** (Options pour les développeurs).
2. Installer la version de test (fournie), pointée sur le serveur de **pré-production** ou de production.
3. Scénario : 20 lectures froides et 20 préchargées en 4G puis en Wi-Fi, une session de 30 min avec
   un swipe toutes les 30 s.
4. Relever `GET /api/admin/stats/playback`, `adb shell dumpsys meminfo com.vidtele.app` et le
   journal serveur.

Ces mesures serviront aussi à **comparer `video_player` et `media_kit`** avant toute décision
(changement de bibliothèque de lecteur = validation préalable requise).
