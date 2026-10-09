# 🎬 VidTele — Plateforme de Streaming Vidéo Privée façon Netflix depuis Telegram

**VidTele** est une solution complète, moderne et haute performance permettant de transformer un **canal privé Telegram** en une véritable plateforme de streaming vidéo sur smartphone (Android / iOS / Web).

Inspirée directement de l'expérience utilisateur de **Netflix**, elle propose une interface sombre et cinématographique, un moteur de streaming **HTTP 206 partiel sans latence**, un **cache disque LRU intelligent de 20 Go**, et une sécurité sur invitation stricte.

---

## 🌟 Points Forts & Fonctionnalités

### 1. 📱 Expérience Mobile façon Netflix (Flutter)
- **Bannière Hero en Vedette** : Affiche immersive grand format en dégradé sombre avec boutons « Lecture » et « Détails ».
- **Top 5 des Tendances** : Classement des contenus les plus visionnés avec les **grands chiffres stylisés (1 à 5)** emblématiques de Netflix.
- **Carrousels Horizontaux Dynamiques** : Organisation automatique par catégories issues des hashtags Telegram (`#film`, `#serie`, `#anime`, `#action`, etc.).
- **Continuer la lecture** : Mémorisation précise de la position et affichage de la **barre de progression rouge**.
- **Lecteur Vidéo Immersif** :
  - Streaming HTTP 206 avec reprise instantanée (`Range Requests`).
  - Contrôles personnalisés (Avance/Retour 10s, sélection de la vitesse de lecture 0.5x à 2.0x, barre de scrubbing rouge).
  - Envoi périodique d'un heartbeat de progression toutes les 10 secondes.
  - Libération automatique de la session de streaming à la fermeture.
- **Bilingue Français / Arabe (RTL)** : Prise en charge native de la langue arabe avec inversion dynamique de l'interface de droite à gauche.
- **Section « Ma Liste » (Favoris)** et **« Historique de visionnage »**.

### 2. ⚡ Moteur Backend Haute Performance (FastAPI & MTProto)
- **Streaming HTTP 206 Partiel** : Lecture immédiate par découpage de 64 Ko via `aiofiles` et `Range Requests`, sans saturer la RAM du VPS.
- **Cache Disque LRU de 20 Go** :
  - Les vidéos populaires sont servies directement depuis le SSD local.
  - Éviction automatique et nettoyage à 85% de la capacité lorsque le quota est atteint.
- **Passerelle Telegram MTProto (Telethon)** :
  - Connexion asynchrone sécurisée via compte Telegram ou Bot.
  - Extraction automatique des métadonnées (titres, légendes, hashtags, résolutions, durées, miniatures).
  - Écoute en temps réel (`@events.NewMessage`) et tâche d'arrière-plan périodique.
- **Gestionnaire de Flux et Concurrence** :
  - Plafond global paramétrable (ex: 15 flux simultanés maximum).
  - Limite par utilisateur (2 flux max par compte, retour HTTP 429 si dépassé).
  - Nettoyage automatique des flux inactifs (heartbeat expiré après 30s).

### 3. 🛡️ Sécurité & Système VIP
- **Accès Exclusivement sur Invitation** : Inscription verrouillée par des codes VIP à usage unique ou multiple.
- **Authentification JWT Robuste** : Tokens d'accès (15 min) et tokens de rafraîchissement (30 jours) avec renouvellement transparent via intercepteur Dio.
- **Protection Brute-Force** : Verrouillage temporaire des adresses IP après tentatives de connexion échouées.
- **Jetons de Streaming Temporaires** : Les flux vidéo sont protégés par des jetons à durée de vie limitée.

### 4. 🎛️ Double Panneau d'Administration
- **Tableau de Bord Web HTML/Bootstrap** accessible sur `http://votre-serveur:8000/admin` (bilingue FR/AR).
- **Écran d'Administration Mobile Intégré** pour déclencher la synchronisation du canal, générer des codes VIP ou purger le cache directement depuis le téléphone.

---

## 🏗️ Architecture du Projet

```text
VIDTELE/
├── backend/
│   ├── app/
│   │   ├── core/           # Configuration globale (Pydantic Settings)
│   │   ├── database.py     # SQLAlchemy 2.0 Async + SQLite (aiosqlite)
│   │   ├── models.py       # Modèles (User, InviteCode, Video, WatchHistory, Favorite, ActiveStream)
│   │   ├── security.py     # Hachage bcrypt, JWT, anti-bruteforce
│   │   ├── telegram_client.py # Client MTProto Telethon avec reconnexion FloodWait
│   │   ├── services/
│   │   │   ├── cache_service.py   # Gestionnaire de cache disque LRU (20 Go)
│   │   │   ├── stream_service.py  # Moteur de streaming HTTP 206 chunked
│   │   │   ├── stream_manager.py  # Concurrence des flux (15 flux max)
│   │   │   └── sync_service.py    # Synchronisation canal Telegram & miniatures
│   │   ├── routers/
│   │   │   ├── auth.py      # /api/auth (register, login, refresh, me)
│   │   │   ├── videos.py    # /api/videos (catalogue, catégories, stream HTTP 206)
│   │   │   ├── library.py   # /api/favorites, /api/history, /api/videos/{id}/progress
│   │   │   ├── admin.py     # /api/admin (stats, invites, users, sync, cache purge)
│   │   │   └── admin_web.py # /admin (Interface web d'administration)
│   │   ├── templates/
│   │   │   └── dashboard.html # Template web Bootstrap 5 bilingue FR/AR
│   │   └── main.py          # Point d'entrée FastAPI avec CORS et lifespan
│   ├── login_telegram.py    # Script interactif d'authentification MTProto initiale
│   ├── requirements.txt     # Dépendances Python
│   └── .env                 # Variables d'environnement
│
├── mobile/
│   ├── lib/
│   │   ├── core/
│   │   │   ├── api/        # ApiClient Dio avec intercepteur JWT auto-refresh
│   │   │   ├── constants/  # Endpoints et clés de stockage
│   │   │   ├── storage/    # FlutterSecureStorage & SharedPreferences
│   │   │   └── theme/      # Charte graphique Netflix (Rouge #E50914, Noir #141414)
│   │   ├── models/         # Modèles Dart (User, Video, Category)
│   │   ├── providers/      # Gestion d'état Riverpod (Auth, Video, Library, Locale)
│   │   ├── screens/
│   │   │   ├── auth/       # Écran de connexion & inscription VIP
│   │   │   ├── home/       # Accueil Netflix (Hero, Top 5, Carrousels, Recherche)
│   │   │   ├── player/     # Lecteur vidéo immersif Chewie + HTTP 206
│   │   │   ├── library/    # Écrans Favoris et Historique
│   │   │   ├── settings/   # Paramètres, profil, choix langue FR/AR
│   │   │   ├── admin/      # Panneau d'administration mobile
│   │   │   └── main_navigation_screen.dart # Barre de navigation principale
│   │   └── main.dart       # Entrée Flutter avec initialisation de session
│   └── pubspec.yaml        # Dépendances Flutter
│
└── deploy/
    ├── vidtele.service      # Unité Systemd pour exécution daemon continue
    ├── nginx.conf           # Reverse Proxy Nginx avec proxy_buffering off
    ├── backup.sh            # Script de sauvegarde automatique SQLite et session
    ├── prepare_video.sh     # Optimisation vidéo FastStart via ffmpeg
    └── setup_vps.sh         # Script d'installation automatisée en 1 clic sur VPS
```

---

## 🚀 Guide de Démarrage Rapide

### 1. Configuration du Backend

1. **Créer votre fichier `.env`** dans `backend/.env` :
```env
# Clés Telegram API (obtenues sur https://my.telegram.org)
TELEGRAM_API_ID=VOTRE_API_ID
TELEGRAM_API_HASH=VOTRE_API_HASH
TELEGRAM_CHANNEL_ID=-100XXXXXXXXXX
TELEGRAM_BOT_TOKEN=

# Clés de Sécurité VidTele
JWT_SECRET=generer_une_cle_secrete_aleatoire_64_caracteres
JWT_REFRESH_SECRET=generer_une_autre_cle_secrete_aleatoire_64_caracteres
ADMIN_DEFAULT_PASSWORD=VotreMotDePasseAdminSecurise

# Paramètres de Diffusion & Cache
MAX_CACHE_GB=20.0
MAX_GLOBAL_STREAMS=15
MAX_USER_STREAMS=2
CACHE_DIR=cache
THUMBNAILS_DIR=thumbnails
```

2. **Créer l'environnement virtuel et installer les dépendances** :
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate      # Sur Windows
# source venv/bin/activate   # Sur Linux

pip install -r requirements.txt
```

3. **Authentifier votre compte Telegram** (requis une seule fois) :
```bash
python login_telegram.py
```
*Entrez votre numéro de téléphone au format international, puis le code reçu sur votre application Telegram.*

4. **Lancer le serveur FastAPI** :
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Documentation Swagger interactive : `http://localhost:8000/docs`
- Tableau de bord Administrateur Web : `http://localhost:8000/admin`
- Compte administrateur initial : `admin` / mot de passe défini dans `.env`.
- Code d'invitation VIP par défaut : `BIENVENUE-2026`.

---

### 2. Lancement de l'Application Mobile (Flutter)

1. **Installer les dépendances Flutter** :
```bash
cd mobile
flutter pub get
```

2. **Vérifier les appareils connectés** :
```bash
flutter devices
```

3. **Lancer sur votre smartphone Android ou navigateur** :
```bash
flutter run
```
*Dans l'écran de connexion de l'application mobile, vous pouvez configurer l'URL de votre serveur (ex: `http://192.168.1.XX:8000` pour un test en réseau local Wi-Fi).*

---

---

## 🐳 Déploiement sur VPS via Dokploy (Recommandé)

VidTele est 100% préconfiguré pour **Dokploy** via Docker Compose ou Dockerfile avec gestion automatique du SSL Traefik et des volumes persistants.

1. **Connecter GitHub à Dokploy** : Liez votre compte `Yomix90` et le dépôt `Yomix90/VIDTELE`.
2. **Créer un service Compose** : Sélectionnez le dépôt, la branche `master`, et le fichier `docker-compose.yml`.
3. **Configurer les variables d'environnement** : Copiez le contenu de `.env.example` dans l'interface Dokploy.
4. **Session Telegram** :
   - Utilisez `TELEGRAM_STRING_SESSION` (obtenue via `python backend/export_session_string.py`) pour une initialisation instantanée sans fichier !
   - Ou lancez `python login_telegram.py` directement dans le Web Terminal de Dokploy.
5. **Consultez le guide complet** : [DOKPLOY.md](file:///c:/Users/USF/Desktop/VIDTELE/DOKPLOY.md) pour les instructions détaillées pas à pas.

---

## 🌐 Déploiement Manuel sur VPS (Ubuntu / Debian - Nginx & Systemd)

Un script tout-en-un est fourni dans le dossier `deploy/` :

```bash
# 1. Cloner ou transférer le projet sur le VPS dans /var/www/vidtele
sudo git clone https://github.com/Yomix90/VIDTELE.git /var/www/vidtele

# 2. Renseigner vos variables d'environnement
sudo cp /var/www/vidtele/backend/.env.example /var/www/vidtele/backend/.env
sudo nano /var/www/vidtele/backend/.env

# 3. Authentifier Telegram une première fois
cd /var/www/vidtele/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python login_telegram.py

# 4. Lancer le déploiement automatique Nginx + Systemd + Cron
sudo bash /var/www/vidtele/deploy/setup_vps.sh

# 5. Installer le certificat SSL HTTPS gratuit
sudo certbot --nginx -d vidtele.votre-domaine.com
```

---

## 📡 Spécification des Endpoints de l'API REST

| Méthode | Route | Rôle | Accès |
|---|---|---|---|
| `POST` | `/api/auth/register` | Inscription avec code d'invitation | Public |
| `POST` | `/api/auth/login` | Connexion utilisateur (retourne tokens JWT) | Public |
| `POST` | `/api/auth/refresh` | Renouvellement automatique de l'Access Token | Public |
| `GET` | `/api/auth/me` | Informations du profil connecté | Authentifié |
| `GET` | `/api/videos` | Catalogue complet des vidéos avec progression | Authentifié |
| `GET` | `/api/videos/categories` | Liste des catégories avec nombre de vidéos | Authentifié |
| `GET` | `/api/videos/{id}` | Détails d'une vidéo spécifique | Authentifié |
| `GET` | `/api/videos/{id}/thumbnail` | Image de couverture / miniature | Public / Cache |
| `POST` | `/api/videos/{id}/stream-token` | Génération d'un jeton temporaire de lecture | Authentifié |
| `GET` | `/api/videos/{id}/stream` | **Flux vidéo HTTP 206 partiel (`Range`)** | Stream Token |
| `POST` | `/api/videos/{id}/stream/stop` | Déclaration d'arrêt & libération de slot | Authentifié |
| `PUT` | `/api/videos/{id}/progress` | Envoi de progression (`progress_seconds`) | Authentifié |
| `GET` | `/api/favorites` | Liste des vidéos favorites de l'utilisateur | Authentifié |
| `POST` | `/api/favorites/{id}` | Ajouter aux favoris | Authentifié |
| `DELETE` | `/api/favorites/{id}` | Retirer des favoris | Authentifié |
| `GET` | `/api/history` | Historique des vidéos visionnées | Authentifié |
| `POST` | `/api/admin/sync` | Déclencher la synchronisation Telegram | Admin |
| `GET` | `/api/admin/stats` | Métriques en temps réel (streams, cache, users) | Admin |
| `POST` | `/api/admin/invites` | Création de codes d'invitation VIP | Admin |
| `POST` | `/api/admin/cache/clear` | Purge manuelle du cache disque | Admin |

---

## 🛠️ Optimisation des Vidéos

Pour garantir un chargement **instantané** des vidéos sur mobile sans aucun buffering initial, les fichiers MP4 doivent avoir leur atome d'indexation (`moov atom`) positionné au tout début du fichier (`+faststart`).

Le script utilitaire `deploy/prepare_video.sh` automatise cette conversion :
```bash
bash deploy/prepare_video.sh ma_video.mp4 ma_video_optimisee.mp4
```

---

## 📄 Licence & Mentions Légales
Ce projet est conçu pour un usage privé et légal de diffusion de contenus multimédias dont vous détenez les droits de visionnage.
VidTele utilise l'API officielle Telegram via MTProto conforme aux conditions d'utilisation de Telegram.
