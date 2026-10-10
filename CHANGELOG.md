# 📜 CHANGELOG - Branche `lecteur-vertical`

Toutes les modifications apportées pour l'unification du lecteur vertical, la fiabilisation du streaming et la suppression du partage.

---

## [1.2.0] - 2026-10-10

### 🎬 A. Lecteur Vertical Unique pour Toutes les Séries & Vidéos
- **Suppression intégrale de l'ancien lecteur classique** (`mobile/lib/screens/player/video_player_screen.dart`).
- **Suppression du package `chewie`** (ainsi que `provider` et `nested` qui n'étaient plus nécessaires) dans `mobile/pubspec.yaml`.
- **Reroutage de l'ensemble des points d'entrée** vers le lecteur vertical plein écran (`ReelsScreen`) :
  - Page d'Accueil (`home_screen.dart`) : slider héroïque, top 5, carrousels de catégories.
  - Page de Détail de Série (`series_detail_screen.dart`) : bouton principal « Regarder », bouton « Regarder en vertical », et clic sur chaque épisode individuel.
  - Recherche (`search_screen.dart`) : clic sur les résultats vidéo ou séries.
  - Ma Liste / Favoris (`favorites_screen.dart`) : clic sur les cartes et reprise directe.
  - Historique (« Continuer à regarder ») (`history_screen.dart`) : reprise instantanée à la seconde exacte mémorisée.
  - Films et vidéos autonomes : ouverts également en plein écran dans `ReelsScreen` avec bouton retour supérieur gauche (`isStandalone: true`).
- **Navigation tactile optimisée** :
  - Swipe vers le haut : épisode suivant de la série.
  - Swipe vers le bas : épisode précédent de la série.
  - Tap simple : bascule lecture / pause avec icône animée.
  - Barre de progression fine rouge interactive au bas de l'écran.
  - Bottom sheet interactif listant tous les épisodes de la saison avec indicateur de progression.
- **Enchaînement automatique & Préchargement anticipé** :
  - Préchargement de l'épisode suivant 8 secondes avant la fin du précédent pour éliminer tout temps de chargement.
  - Enchaînement immédiat à la fin de l'épisode sans action requise de l'utilisateur.
- **Carte cinématique « Série terminée »** :
  - Affichée automatiquement après le dernier épisode de la série.
  - Propose 3 séries recommandées cliquables lançant immédiatement la série suivante dans le lecteur vertical.
  - Boutons « Recommencer la série » (retour à l'épisode 1) et « Retour à l'accueil ».

---

### 🛡️ B. Résolution de l'Arrêt Automatique du Lecteur Vidéo (Causes Racines & Watchdog)
- **Cause 1 (FastAPI Route 405 Method Not Allowed $\to$ 401)** :
  - La route `/api/videos/{video_id}/stream-token` n'acceptait que `GET`. L'appel client en `POST` échouait, masqué par un fallback sur `accessToken` expirant au bout de 60 minutes $\to$ arrêt brutal du flux avec code HTTP 401.
  - *Correctif* : Route backend configurée avec `@router.api_route(["GET", "POST"])` (`backend/app/routers/videos.py`) et bascule en `GET` dans le client mobile.
- **Cause 2 (Saturation du quota de streams simultanés `MAX_CONCURRENT_STREAMS_PER_USER = 2` $\to$ 429)** :
  - Le pool vertical préchargeait 3 vidéos (`précédente`, `courante`, `suivante`) ce qui dépassait le quota strict de 2 streams autorisés simultanément par utilisateur.
  - *Correctif* : Augmentation de la limite à 4 streams simultanés dans `backend/app/config.py` et `docker-compose.yml`.
- **Cause 3 (Interruption par `AppLifecycleState.inactive`)** :
  - Les notifications Android, volets de volume ou dialogues système passaient l'application en `inactive`, ce qui coupait la lecture sans jamais la relancer au retour au premier plan.
  - *Correctif* : `VideoPlayerManager` ignore désormais l'état `inactive` (maintient la vidéo en premier plan), coupe proprement sur `paused`/`hidden`, et relance automatiquement le flux au retour `resumed`.
- **Cause 4 (Watchdog de surveillance & Auto-retry 3x)** :
  - Création de `VideoWatchdog` (`mobile/lib/core/services/video_watchdog.dart`) :
    - Détection proactive des blocages (position figée > 8 secondes alors que la lecture est désirée).
    - Reconnexion automatique jusqu'à 3 tentatives avec rafraîchissement transparent du jeton de streaming et reprise à la dernière seconde exacte.
    - Écoute en continu de `controller.value.hasError` avec reconnexion immédiate en cas de micro-coupure réseau.
    - Indicateur de buffering discret sans écran noir.

---

### 🚫 C. Suppression Définitive du Partage de Série
- Retrait de l'icône de partage dans la barre supérieure (`SliverAppBar`) de la page de détail.
- Retrait du bouton de partage sous le synopsis. Le bouton « Ma liste » est désormais élégamment centré.
- Suppression de la méthode `_shareSeries` et du presse-papier associé.
- Suppression des clés de traduction `shareSeries` et `linkCopied` dans `mobile/lib/core/localization/app_localizations.dart` (Français, Anglais, Arabe).
- Vérification côté backend : aucun endpoint public de partage n'existait, garantissant l'absence d'impact serveur.
- Aucun autre mécanisme (comme le système de favoris, comptes ou vidéos) n'a été altéré.

---

### 🧪 D. Tests & Validation
- **Tests unitaires et d'intégration** : 35 tests passés avec succès (`mobile/test/`).
  - `video_watchdog_test.dart` : tests du watchdog 8s, simulation de stall, reprise automatique.
  - `video_player_manager_test.dart` : tests du cycle de vie Android (`inactive`, `paused`, `resumed`).
  - `watch_gate_test.dart` : vérification du seuil publicitaire (4-5 vidéos), maintien de la logique de récompense AdMob.
  - `series_detail_test.dart`, `reels_feed_test.dart`, `home_widgets_test.dart`, `navigation_lifecycle_test.dart`, `ad_gate_ui_test.dart`.
- **Analyse statique** : `flutter analyze lib test` : 0 avertissement, 0 erreur.
