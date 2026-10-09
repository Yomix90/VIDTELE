#!/bin/bash
# Script d'installation automatisée de VidTele sur VPS Ubuntu / Debian
# Exécuter en root : sudo bash setup_vps.sh

set -e

echo "=========================================================="
echo "      VIDTELE - Déploiement Automatisé sur VPS            "
echo "=========================================================="

if [ "$EUID" -ne 0 ]; then
  echo "Erreur : Ce script doit être exécuté avec les privilèges root (sudo)."
  exit 1
fi

APP_DIR="/var/www/vidtele"

# 1. Mise à jour du système & Installation des paquets requis
echo "[1/6] Installation des dépendances système..."
apt update
apt install -y python3 python3-pip python3-venv ffmpeg sqlite3 nginx certbot python3-certbot-nginx git curl ufw

# 2. Préparation des répertoires
echo "[2/6] Configuration du répertoire applicatif /var/www/vidtele..."
mkdir -p "$APP_DIR"
mkdir -p "/var/backups/vidtele"
chown -R www-data:www-data "$APP_DIR"
chown -R www-data:www-data "/var/backups/vidtele"

# 3. Création de l'environnement virtuel Python
echo "[3/6] Initialisation de l'environnement virtuel Python..."
cd "$APP_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configuration du service Systemd
echo "[4/6] Activation du service Systemd vidtele.service..."
cp "$APP_DIR/deploy/vidtele.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable vidtele.service
systemctl restart vidtele.service

# 5. Configuration de Nginx
echo "[5/6] Configuration du Reverse Proxy Nginx..."
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/vidtele.conf
ln -sf /etc/nginx/sites-available/vidtele.conf /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# 6. Planification de la sauvegarde automatique quotidienne à 03h00
echo "[6/6] Configuration de la tâche Cron de sauvegarde quotidienne..."
chmod +x "$APP_DIR/deploy/backup.sh"
chmod +x "$APP_DIR/deploy/prepare_video.sh"
(crontab -l 2>/dev/null | grep -v "vidtele/deploy/backup.sh"; echo "0 3 * * * $APP_DIR/deploy/backup.sh >> /var/log/vidtele_backup.log 2>&1") | crontab -

echo ""
echo "=========================================================="
echo "  Déploiement terminé avec succès !                       "
echo "=========================================================="
echo "Commandes utiles :"
echo "  - État du backend : systemctl status vidtele"
echo "  - Logs en direct  : journalctl -u vidtele -f"
echo "  - Tester Nginx    : nginx -t"
echo "  - Certificat SSL  : certbot --nginx -d votre-domaine.com"
echo "=========================================================="
