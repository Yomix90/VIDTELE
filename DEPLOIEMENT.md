# Déploiement — Atlas Play (Dokploy)

> Dokploy déploie la branche **`main`**. Tout le travail de refonte se fait sur `mise-a-jour-totale` :
> fusionner dans `main` = mettre en production. Ne fusionner qu'après validation de la phase.

## 1. Avant la mise en production des Phases 0.5 et 1

### 1.1 Variables d'environnement Dokploy

| Variable | Obligatoire | Valeur | Remarque |
|---|---|---|---|
| `SECRET_KEY` | **Oui** | résultat de `openssl rand -hex 32` | Si la production utilise déjà une clé forte, la **garder** (sinon tous les utilisateurs sont déconnectés une fois). Une valeur d'exemple du dépôt est refusée et remplacée par une clé générée. |
| `ADMIN_DEFAULT_PASSWORD` | Non | mot de passe fort | Utilisé seulement à la création du 1er admin, ou avec `ADMIN_RESET_PASSWORD=true`. |
| `ADMIN_RESET_PASSWORD` | Non | `false` | Secours en cas d'oubli : `true`, redémarrer, se connecter, remettre `false`. |
| `TRUSTED_PROXIES` | Non | réseaux Docker par défaut | À ajuster si le réseau Traefik/Dokploy n'est pas en 10.x, 172.16-31.x ou 192.168.x. |
| `STREAM_TOKEN_GRACE_MINUTES` | Non | `240` | Tolérance d'expiration du jeton sur l'URL de lecture (évite les coupures). |
| `LOG_FORMAT` / `LOG_LEVEL` | Non | `texte` / `INFO` | `json` pour une collecte automatisée. |
| `APP_VERSION` | Non | ex. `1.3.0` | Affichée par `/api/health/ready`. |
| `DISK_MIN_FREE_GB` | Non | `2.0` | Seuil d'alerte disque de `/api/health/ready`. |

### 1.2 Tester la migration sur une copie de la base de production (obligatoire)

Au premier démarrage, le serveur passe la base sous Alembic (sauvegarde automatique, vérification,
marquage « 0001 »). À tester **avant** sur une copie **anonymisée** :

```bash
# Sur le VPS : copie de la base (le conteneur continue de tourner)
docker exec vidtele-backend sqlite3 /app/data/vidtele.db ".backup '/app/data/copie.db'"
docker cp vidtele-backend:/app/data/copie.db ./copie.db
docker exec vidtele-backend rm /app/data/copie.db

# Anonymisation : retirer la session Telegram, les secrets et les empreintes de mots de passe
sqlite3 copie.db "UPDATE telegram_accounts SET string_session=NULL, api_hash=NULL;
                  UPDATE users SET hashed_password='x';
                  DELETE FROM system_settings WHERE key LIKE '%KEY%' OR key LIKE '%SECRET%';
                  VACUUM;"
```

Transmettre ensuite `copie.db` (jamais la base brute : elle contient la session Telegram qui donne
accès au compte).

### 1.3 Mise en production

1. Vérifier que la CI est verte sur `mise-a-jour-totale` (GitHub → Actions).
2. Fusionner `mise-a-jour-totale` dans `main` → Dokploy reconstruit l'image (Python 3.14).
3. Surveiller les journaux au démarrage :
   - `Sauvegarde de la base avant migration : /app/data/sauvegardes/avant-migration-....db`
   - `Base marquée à la révision de référence 0001.`
   - aucune ligne `CRITICAL` sur `SECRET_KEY` ; si `Le compte admin ... utilise un mot de passe PUBLIC` apparaît, **changer le mot de passe admin** immédiatement.
4. Vérifier `https://<domaine>/api/health/ready` : `"status": "ok"` (ou `degrade` si Telegram est déconnecté).
5. Ouvrir l'application installée : accueil, séries (désormais visibles), lecture d'un épisode.

## 2. Retour en arrière

1. Dans Dokploy, redéployer le commit précédent de `main`.
2. Si la base doit revenir à l'état d'avant migration : arrêter le service, puis
   ```bash
   docker run --rm -v vidtele_data:/data alpine sh -c \
     "cp /data/vidtele.db /data/vidtele.db.apres-migration && cp /data/sauvegardes/avant-migration-AAAAMMJJ-HHMMSS.db /data/vidtele.db"
   ```
   puis redémarrer. (L'ancienne version ignore la table `alembic_version`, le retour sans restauration fonctionne aussi.)

## 3. Publication de l'application Android

- Signature : clé de debug de ce PC (`~/.android/debug.keystore`, SHA-256 `1f50180f…05636f`), identique à celle
  des APK déjà installés. **La sauvegarder hors du PC.** Passage à une vraie clé : rotation (`apksigner rotate`), Phase 6.
- Les APK publiés sont construits par architecture (`--split-per-abi`) : la 1.2.0 arm64 a `versionCode = 2003`.
  La prochaine version doit avoir un `versionCode` **supérieur**, sinon Android refuse la mise à jour.
