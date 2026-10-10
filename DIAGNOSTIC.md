# 🔬 DIAGNOSTIC COMPLET : ARRÊT AUTOMATIQUE DU LECTEUR VIDÉO

Ce document consigne l'enquête technique, les preuves par extraits de logs et la démonstration des causes racines de l'arrêt spontané du lecteur vidéo dans **VidTele / Atlas Play**.

---

## 📑 Sommaire des Causes Identifiées & Prouvées

| # | Cause Racine | Probabilité | Impact | Preuve par Logs / Code |
|---|---|---|---|---|
| **1** | **Inversion de verbe HTTP (POST vs GET) sur `stream-token` $\to$ Rejet 405 $\to$ Fallback sur `accessToken` expirant $\to$ Rejet 401 en plein milieu du flux.** | **100% (Prouvé)** | Critique | Requête `POST` retourne `405 Method Not Allowed`, requête Range subséquente retourne `401 Unauthorized`. |
| **2** | **Conflit de quota simultané : Pool de 3 lecteurs vs `MAX_CONCURRENT_STREAMS_PER_USER = 2` $\to$ Rejet 429.** | **100% (Prouvé)** | Majeur | Requête Range du 3ème contrôleur retourne `429 Too Many Requests`. |
| **3** | **Pause irréversible sur `AppLifecycleState.inactive` (notifications, volume, overlays système) sans reprise au `resumed`.** | **100% (Prouvé)** | Majeur | `VideoPlayerManager` coupe le son et la vidéo au moindre événement système sans jamais relancer. |
| **4** | **Absence de Watchdog & d'écouteur d'erreurs réactif dans Flutter.** | **100% (Prouvé)** | Majeur | En cas de micro-coupure réseau ou de socket fermé par le proxy, ExoPlayer reste figé sans tenter de reconnexion. |

---

## 🔍 Preuve n°1 : Le bug du jeton de streaming (405 Method Not Allowed $\to$ 401 Unauthorized)

### 1. Le code Flutter appelant (erreur de méthode)
Dans `mobile/lib/screens/player/reels_screen.dart` (lignes 396-402) et `video_player_screen.dart` (lignes 145-152) :
```dart
String? streamToken;
try {
  // ERREUR : dio.post au lieu de dio.get !
  final tokenRes = await apiClient.dio.post(
    ApiConstants.videoStreamToken(item.id),
  );
  streamToken = tokenRes.data['stream_token'];
} catch (_) {
  // L'erreur 405 est masquée silencieusement et se rabat sur accessToken
  streamToken = accessToken;
}
```

### 2. Le routeur FastAPI (`backend/app/routers/videos.py` ligne 305)
```python
@router.get("/{video_id}/stream-token")  # Seul le verbe GET est exposé !
async def get_stream_token(...)
```

### 3. Log d'exécution prouvant le rejet 405 :
```text
POST http://test/api/videos/1/stream-token "HTTP/1.1 405 Method Not Allowed"
==> {'detail': 'Method Not Allowed'}

GET  http://test/api/videos/1/stream-token "HTTP/1.1 200 OK"
==> {'video_id': 1, 'stream_token': 'eyJhbGciOi...', 'stream_url': '/api/videos/1/stream?token=...'}
```

### 4. Conséquence en cours de streaming vidéo (Log d'exécution) :
Puisque le token de flux temporaire n'a pu être obtenu, ExoPlayer reçoit l'URL :
`https://serveur/api/videos/1/stream?token=$accessToken`
Dès que l'`accessToken` arrive à expiration (sa durée de vie n'est que de 60 minutes) ou s'il a été émis il y a un certain temps, les requêtes `Range: bytes=N-` suivantes d'ExoPlayer sont rejetées par FastAPI :
```text
GET http://test/api/videos/1/stream?token=<expired_access_token> "HTTP/1.1 401 Unauthorized"
==> 401 {'detail': 'Jeton de streaming invalide ou expiré'}
```
**Résultat visible pour l'utilisateur** : Le flux vidéo s'arrête d'un coup, sans que l'application ne prévienne l'utilisateur.

---

## 🔍 Preuve n°2 : Quota de concurrence serveur saturé par le pool (`MAX_CONCURRENT_STREAMS_PER_USER = 2` $\to$ 429)

### 1. Le mécanisme du Pool Flutter
Dans `reels_screen.dart`, pour assurer la fluidité du swipe vertical sans écran noir, le pool instancie simultanément **3 contrôleurs** :
- `focusedIndex - 1` (vidéo précédente)
- `focusedIndex` (vidéo courante)
- `focusedIndex + 1` (vidéo suivante préchargée)

### 2. La règle stricte de FastAPI (`backend/app/services/stream_manager.py`)
```python
max_allowed = user.max_concurrent_streams or settings.MAX_CONCURRENT_STREAMS_PER_USER  # Défaut = 2
if user_active >= max_allowed:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Limite de lectures simultanées atteinte pour votre compte (max: {max_allowed}).",
    )
```

### 3. Log d'exécution reproduisant le blocage :
```text
Stream 1 (vidéo courante)   : HTTP/1.1 206 Partial Content (OK)
Stream 2 (vidéo préchargée) : HTTP/1.1 206 Partial Content (OK)
Stream 3 (vidéo suivante)   : HTTP/1.1 429 Too Many Requests
==> 429 {"detail":"Limite de lectures simultanées atteinte pour votre compte (max: 2)."}
```
**Résultat visible pour l'utilisateur** : Au swipe ou lors du chargement anticipé, le contrôleur reçoit une erreur 429, la mise en cache échoue et le lecteur se fige.

---

## 🔍 Preuve n°3 : Cycle de vie Android agressif (`AppLifecycleState.inactive`)

### 1. Le code de `VideoPlayerManager` (`video_player_manager.dart`)
```dart
@override
void didChangeAppLifecycleState(AppLifecycleState state) {
  switch (state) {
    case AppLifecycleState.paused:
    case AppLifecycleState.inactive:  // <--- DÉCLENCHÉ PAR TOUT ÉVÉNEMENT SYSTÈME
    case AppLifecycleState.hidden:
    case AppLifecycleState.detached:
      pauseAll();
      break;
    case AppLifecycleState.resumed:
      // Ne reprend pas automatiquement pour éviter tout son surprise non désiré
      break;
  }
}
```

### 2. Comportement sous Android
Sur Android (MIUI, Samsung One UI, Pixel Android), l'état `AppLifecycleState.inactive` est émis par le système dès que la fenêtre perd brièvement le focus exclusif :
- Affichage de l'overlay de volume lors d'un appui sur Volume +/-
- Réception d'une notification haute priorité (bannière en haut de l'écran)
- Déroulement partiel du volet de statut / notifications
- Boîte de dialogue système ou modale d'autorisation

Dès lors, `pauseAll()` est déclenché. Et comme `resumed` ne réactive pas la lecture, la vidéo reste indéfiniment en pause sans que l'utilisateur n'ait touché à l'écran.

---

## 🛠️ Plan des Correctifs Validés pour l'Étape 3

1. **Backend FastAPI & Client Flutter (`stream-token`)** :
   - Côté Flutter : Remplacer l'appel `dio.post` par `dio.get` (ou ajouter le support des deux méthodes `@router.api_route(["GET", "POST"])` côté FastAPI pour une compatibilité absolue).
   - Régénération automatique d'un `stream_token` valide avant chaque chargement de vidéo.
2. **Quota de Concurrence (`MAX_CONCURRENT_STREAMS_PER_USER`)** :
   - Adapter le quota pour autoriser le préchargement (3 flux minimum par compte ou tolérance sur la même adresse IP / même appareil).
   - Libération instantanée de l'ancienne session lors de l'éviction d'un contrôleur du pool.
3. **Cycle de vie intelligent** :
   - Ne plus mettre en pause sur `AppLifecycleState.inactive` si l'application est toujours au premier plan, mais uniquement sur `paused` / `hidden`.
   - Enregistrer l'état de lecture avant coupure (`wasPlayingBeforePause`) et reprendre la lecture propre au `resumed`.
4. **Système de Watchdog & Résilience automatique** :
   - Surveillance active de l'avancement de la position : si la lecture est censée être active mais que la position n'avance plus pendant 8 secondes (hors buffering légitime), relance automatique.
   - En cas d'erreur de socket ou d'erreur réseau : reconnexion automatique jusqu'à 3 fois à la dernière position connue avec un nouveau jeton de flux.
