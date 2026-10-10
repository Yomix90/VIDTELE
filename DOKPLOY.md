# 🚀 Guide de Déploiement VidTele sur VPS via Dokploy

Ce guide détaille pas à pas comment installer et déployer **VidTele** sur votre VPS avec **Dokploy**, connecté à votre compte GitHub **Yomix90** (`https://github.com/Yomix90/VIDTELE`).

---

## 📋 Table des Matières
1. [Architecture & Fonctionnement](#1-architecture--fonctionnement)
2. [Étape 1 : Connexion de GitHub à Dokploy](#2-étape-1--connexion-de-github-à-dokploy)
3. [Étape 2 : Choix du Mode de Déploiement](#3-étape-2--choix-du-mode-de-déploiement)
   - [Option A : Déploiement Compose (Recommandé)](#option-a--déploiement-compose-recommandé)
   - [Option B : Déploiement Application (Dockerfile)](#option-b--déploiement-application-dockerfile)
4. [Étape 3 : Gestion de la Session Telegram MTProto](#4-étape-3--gestion-de-la-session-telegram-mtproto)
5. [Étape 4 : Variables d'Environnement](#5-étape-4--variables-denvironnement)
6. [Étape 5 : Volumes Persistants (SQLite & Cache)](#6-étape-5--volumes-persistants-sqlite--cache)
7. [Étape 6 : Domaine & Certificat SSL (HTTPS)](#7-étape-6--domaine--certificat-ssl-https)
8. [Étape 7 : Connecter l'Application Mobile Flutter](#8-étape-7--connecter-lapplication-mobile-flutter)
9. [Maintenance, Logs & Administration](#9-maintenance-logs--administration)

---

## 1. Architecture & Fonctionnement

VidTele est architecturé pour un déploiement conteneurisé ultra-léger et haute performance :
- **FastAPI / Python 3.11** avec serveur ASGI Uvicorn.
- **SQLite Asynchrone** (`aiosqlite`) : stocké dans `/app/data/vidtele.db`.
- **Passerelle MTProto Telethon** : gère le streaming vidéo directement depuis votre canal privé Telegram.
- **Cache LRU (20 Go)** : stocké dans `/app/cache` pour une lecture instantanée.
- **Traefik (Dokploy)** : Reverse proxy automatique avec certificats SSL Let's Encrypt gérés en 1 clic.

---

## 2. Étape 1 : Connexion de GitHub à Dokploy

1. Connectez-vous à l'interface de votre **Dokploy** (`http://ip-de-votre-vps:3000` ou votre sous-domaine Dokploy).
2. Rendez-vous dans **Settings** > **Git Providers**.
3. Cliquez sur **Add GitHub** (GitHub App ou Token personnel) :
   - Autorisez l'accès à votre compte **Yomix90**.
   - Sélectionnez le dépôt `Yomix90/VIDTELE`.

---

## 3. Étape 2 : Choix du Mode de Déploiement

### Option A : Déploiement Compose (Recommandé)
Le mode Compose gère automatiquement les volumes persistants et l'orchestration.

1. Dans Dokploy, créez un nouveau projet (ex: `vidtele`).
2. Cliquez sur **Create Service** > choisissez **Compose**.
3. Renseignez les paramètres suivants :
   - **Name** : `vidtele`
   - **Source** : `GitHub`
   - **Repository** : `Yomix90/VIDTELE`
   - **Branch** : `master` (ou `main`)
   - **Compose Path** : `docker-compose.yml` (ou `docker-compose.dokploy.yml`)
4. Allez dans l'onglet **Environment** et collez vos variables (voir section 5).
5. Cliquez sur **Deploy**.

---

### Option B : Déploiement Application (Dockerfile)
Si vous préférez le mode "Application" direct de Dokploy :

1. Cliquez sur **Create Service** > choisissez **Application**.
2. Renseignez :
   - **Source** : `GitHub`
   - **Repository** : `Yomix90/VIDTELE`
   - **Branch** : `master`
   - **Build Type** : `Dockerfile`
   - **Dockerfile Path** : `Dockerfile`
   - **Context Path** : `.`
   - **Port** : `8000`
3. Configurez les volumes persistants (voir section 6).
4. Renseignez les variables d'environnement (voir section 5).
5. Cliquez sur **Deploy**.

---

## 4. Étape 3 : Gestion de la Session Telegram MTProto

Telegram exige une authentification interactive (téléphone + code SMS/Telegram + 2FA). VidTele propose **deux méthodes** simples pour Dokploy :

### ⭐ Méthode 1 : Sans aucun fichier (StringSession - La plus simple !)
Vous n'avez pas besoin de copier de fichier sur le VPS.
1. Sur votre PC local, dans le dossier du projet, exécutez :
   ```bash
   python backend/export_session_string.py
   ```
2. Le script génère une ligne commençant par `TELEGRAM_STRING_SESSION=1BJWap...`.
3. Copiez cette valeur complète et collez-la dans les **Environment Variables** de Dokploy !
4. VidTele se connecte immédiatement à Telegram dès le lancement du conteneur.

### Méthode 2 : Via le Terminal Web de Dokploy
Si vous préférez créer la session directement sur le VPS :
1. Déployez l'application sur Dokploy.
2. Allez dans l'onglet **Terminal / Console** du conteneur dans Dokploy.
3. Cliquez sur **Connect** et lancez :
   ```bash
   python login_telegram.py
   ```
4. Entrez votre numéro et le code reçu sur Telegram. La session est automatiquement sauvegardée dans le volume persistant `/app/data/vidtele_session.session`.

---

## 5. Étape 4 : Variables d'Environnement

Dans Dokploy (onglet **Environment**), collez les variables suivantes :

```env
# Port du service
PORT=8000

# Clé de signature des jetons : générez-la avec `openssl rand -hex 32` (ne jamais réutiliser un exemple).
# Vide = clé aléatoire persistante générée dans /app/data/.jwt_secret au 1er démarrage.
SECRET_KEY=<résultat de openssl rand -hex 32>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30
STREAM_TOKEN_EXPIRE_SECONDS=7200

# Base de données persistante
DATABASE_URL=sqlite+aiosqlite:////app/data/vidtele.db

# Identifiants Telegram MTProto (https://my.telegram.org)
TELEGRAM_API_ID=<votre api_id>
TELEGRAM_API_HASH=<votre api_hash>
TELEGRAM_SESSION_NAME=/app/data/vidtele_session
TELEGRAM_CHANNEL_ID=-100XXXXXXXXXX

# Session en mémoire (Optionnel mais recommandé pour Dokploy)
TELEGRAM_STRING_SESSION=votre_string_session_generee

# Stockage et Quota du Cache
CACHE_DIR=/app/cache
THUMBNAILS_DIR=/app/thumbnails
MAX_CACHE_GB=20.0

# Concurrence de streaming
MAX_CONCURRENT_STREAMS_PER_USER=2
MAX_CONCURRENT_STREAMS_GLOBAL=30
SYNC_INTERVAL_MINUTES=15

# Compte administrateur créé au 1er démarrage UNIQUEMENT (s'il n'existe aucun admin).
# Vide = mot de passe aléatoire écrit dans /app/data/admin_initial_password.txt.
# Le mot de passe n'est plus réécrit aux démarrages suivants : changez-le depuis l'admin.
ADMIN_DEFAULT_USERNAME=admin
ADMIN_DEFAULT_PASSWORD=<mot de passe fort et unique>
# Secours en cas d'oubli : true + redémarrage réécrit le mot de passe depuis ADMIN_DEFAULT_PASSWORD, puis remettre false
ADMIN_RESET_PASSWORD=false

# Proxys autorisés à transmettre l'IP réelle (X-Forwarded-For) : réseaux Docker/Traefik par défaut
# TRUSTED_PROXIES=127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16

# Tolérance d'expiration du jeton sur l'URL de lecture (évite les coupures en cours de lecture)
# STREAM_TOKEN_GRACE_MINUTES=240
```

---

## 6. Étape 5 : Volumes Persistants (SQLite & Cache)

Pour conserver vos utilisateurs, vos données et votre cache vidéo lors des redéploiements et mises à jour :

### Si vous utilisez `docker-compose.yml` :
Les volumes Docker suivants sont créés et montés **automatiquement** :
- `vidtele_data` -> `/app/data` (base SQLite + fichier session)
- `vidtele_cache` -> `/app/cache` (vidéos téléchargées en cache)
- `vidtele_thumbnails` -> `/app/thumbnails` (miniatures)

### Si vous utilisez le mode "Application" (Dockerfile) :
Dans l'onglet **Volumes** de votre application dans Dokploy, ajoutez 3 volumes nommés :
1. `vidtele_data` monté sur `/app/data`
2. `vidtele_cache` monté sur `/app/cache`
3. `vidtele_thumbnails` monté sur `/app/thumbnails`

---

## 7. Étape 6 : Domaine & Certificat SSL (HTTPS)

1. Dans Dokploy, ouvrez l'onglet **Domains**.
2. Cliquez sur **Add Domain**.
3. Renseignez votre nom de domaine ou sous-domaine (ex: `vidtele.votredomaine.com`).
4. Port du conteneur : `8000`.
5. Cochez **HTTPS (SSL)**.
6. Assurez-vous que votre enregistrement DNS de type `A` (`vidtele.votredomaine.com`) pointe bien vers l'adresse IP de votre VPS.
7. Dokploy et Traefik génèrent automatiquement votre certificat Let's Encrypt !

---

## 8. Étape 7 : Connecter l'Application Mobile Flutter

Une fois votre serveur déployé :
1. Lancez l'application mobile VidTele sur votre smartphone.
2. Sur l'écran de connexion, cliquez sur l'icône **Serveur / Paramètres**.
3. Saisissez l'adresse de votre serveur :
   - `https://vidtele.votredomaine.com` (si domaine avec SSL)
   - ou `http://vps-ip:8000` (si accès IP direct)
4. Connectez-vous avec :
   - Identifiant : `admin`
   - Mot de passe : celui configuré dans `ADMIN_DEFAULT_PASSWORD` lors de la création (ou le contenu de `/app/data/admin_initial_password.txt`)
5. Pour inscrire des utilisateurs VIP :
   - Utilisez le code d'invitation initial `BIENVENUE-2026`
   - Ou générez-en de nouveaux depuis l'écran Admin mobile ou le tableau de bord web.

---

## 9. Maintenance, Logs & Administration

- **Tableau de Bord Web Admin** : Accessible sur `https://vidtele.votredomaine.com/admin`
- **Documentation API Swagger** : `https://vidtele.votredomaine.com/docs`
- **Vérification de Santé (Healthcheck)** : `https://vidtele.votredomaine.com/api/health`
- **Logs en direct** : Directement dans l'onglet **Logs** de Dokploy.
- **Redémarrage en cas de mise à jour** :
  Chaque fois que vous faites un `git push` sur `Yomix90/VIDTELE`, Dokploy peut reconstruire et redéployer automatiquement votre application grâce aux Webhooks GitHub !
