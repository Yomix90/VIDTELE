#!/bin/bash
# Script d'optimisation vidéo VidTele pour Telegram et Streaming HTTP 206
# Usage: ./prepare_video.sh input.mp4 [output.mp4]

set -e

INPUT_FILE="$1"
OUTPUT_FILE="${2:-output_optimized.mp4}"

if [ -z "$INPUT_FILE" ] || [ ! -f "$INPUT_FILE" ]; then
    echo "Usage: $0 <fichier_source.mp4|mkv|mov> [fichier_sortie.mp4]"
    exit 1
fi

echo "=== Optimisation VidTele Vidéo ==="
echo "Source : $INPUT_FILE"
echo "Cible  : $OUTPUT_FILE"

# 1. Vérification de ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "Erreur : ffmpeg n'est pas installé sur votre système."
    echo "Sur Ubuntu/Debian : sudo apt update && sudo apt install -y ffmpeg"
    exit 1
fi

# 2. Re-muxage / Optimisation avec FastStart (MOOV atom en début de fichier)
# Cela permet un démarrage instantané de la lecture vidéo sur mobile sans devoir charger tout le fichier
echo "Placement de l'en-tête MP4 au début du fichier (moov atom faststart)..."

ffmpeg -i "$INPUT_FILE" \
    -c:v libx264 -preset medium -crf 23 \
    -c:a aac -b:a 128k \
    -pix_fmt yuv420p \
    -movflags +faststart \
    "$OUTPUT_FILE" -y

SIZE_MB=$(du -m "$OUTPUT_FILE" | cut -f1)
echo "Optimisation terminée avec succès !"
echo "Fichier généré : $OUTPUT_FILE (Taille: ${SIZE_MB} Mo)"

if [ "$SIZE_MB" -gt 50 ]; then
    echo "Attention : La taille dépasse 50 Mo (${SIZE_MB} Mo). Pour un streaming mobile ultra-rapide,"
    echo "il est recommandé de découper les vidéos ou d'augmenter le CRF (ex: -crf 26)."
fi
