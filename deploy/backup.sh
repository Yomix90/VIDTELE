#!/bin/bash
# Script de Sauvegarde Automatique VidTele (Base SQLite & Session Telethon)
# À exécuter quotidiennement via crontab (ex: 0 3 * * * /var/www/vidtele/deploy/backup.sh)

set -e

BACKUP_DIR="/var/backups/vidtele"
APP_DIR="/var/www/vidtele/backend"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DEST_FOLDER="$BACKUP_DIR/backup_$TIMESTAMP"

echo "[VidTele Backup] Démarrage de la sauvegarde du $(date)..."

# Création du dossier de destination
mkdir -p "$DEST_FOLDER"

# 1. Sauvegarde propre et cohérente de la base SQLite (sans verrou bloquant)
if [ -f "$APP_DIR/vidtele.db" ]; then
    echo "[VidTele Backup] Sauvegarde de SQLite vidtele.db..."
    sqlite3 "$APP_DIR/vidtele.db" ".backup '$DEST_FOLDER/vidtele.db'"
else
    echo "[VidTele Backup] Attention : vidtele.db non trouvé."
fi

# 2. Sauvegarde du fichier de session Telethon (MTProto credentials)
if [ -f "$APP_DIR/vidtele_session.session" ]; then
    echo "[VidTele Backup] Sauvegarde de la session Telethon..."
    cp "$APP_DIR/vidtele_session.session" "$DEST_FOLDER/vidtele_session.session"
fi

# 3. Sauvegarde du fichier d'environnement .env
if [ -f "$APP_DIR/.env" ]; then
    echo "[VidTele Backup] Sauvegarde de la configuration .env..."
    cp "$APP_DIR/.env" "$DEST_FOLDER/.env"
fi

# 4. Compression de l'archive tar.gz
cd "$BACKUP_DIR"
tar -czf "vidtele_backup_$TIMESTAMP.tar.gz" "backup_$TIMESTAMP"
rm -rf "backup_$TIMESTAMP"

echo "[VidTele Backup] Sauvegarde terminée : $BACKUP_DIR/vidtele_backup_$TIMESTAMP.tar.gz"

# 5. Purge automatique des sauvegardes de plus de 14 jours
find "$BACKUP_DIR" -type f -name "vidtele_backup_*.tar.gz" -mtime +14 -exec rm -f {} \;
echo "[VidTele Backup] Nettoyage des anciennes sauvegardes (> 14 jours) terminé."
