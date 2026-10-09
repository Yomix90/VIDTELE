"""
Utilitaire pour exporter une session Telegram existante (.session) sous forme de chaîne StringSession.
Idéal pour Dokploy, Railway, Docker, et les environnements cloud où vous préférez
passer la variable d'environnement TELEGRAM_STRING_SESSION au lieu d'un fichier .session sur disque.
"""
import os
import sys
from pathlib import Path

# Détection et inclusion automatique de l'environnement virtuel local (backend/venv)
current_dir = Path(__file__).resolve().parent
candidates = [
    current_dir / "venv" / "Lib" / "site-packages",
    current_dir.parent / "backend" / "venv" / "Lib" / "site-packages",
    current_dir / "venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages",
]
for candidate in candidates:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

try:
    from dotenv import load_dotenv
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    # Si le venv existe mais que l'interpréteur courant n'a pas accès aux paquets C/binaires
    venv_python = current_dir / "venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        import subprocess
        result = subprocess.run([str(venv_python), str(__file__)] + sys.argv[1:])
        sys.exit(result.returncode)
    print("Erreur : Telethon n'est pas installé dans cet environnement.")
    print("Veuillez exécuter avec l'environnement virtuel :")
    print(r"  .\backend\venv\Scripts\python.exe backend/export_session_string.py")
    sys.exit(1)

env_path = current_dir / ".env"
load_dotenv(dotenv_path=env_path)


def main():
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_name = os.getenv("TELEGRAM_SESSION_NAME", "vidtele_session")

    if not api_id or not api_hash:
        print("[!] TELEGRAM_API_ID ou TELEGRAM_API_HASH manquant dans le fichier .env.")
        sys.exit(1)

    session_path = Path(session_name) if Path(session_name).is_absolute() else current_dir / session_name
    session_file = Path(f"{session_path}.session")

    if not session_file.exists():
        print(f"[!] Fichier de session introuvable : {session_file}")
        print("Veuillez d'abord exécuter 'python backend/login_telegram.py' pour vous connecter.")
        sys.exit(1)

    try:
        client = TelegramClient(str(session_path), int(api_id), api_hash)
        string_session = StringSession.save(client.session)
        client.disconnect()

        print("=" * 70)
        print("      VIDTELE - EXPORT DE LA SESSION TELEGRAM POUR DOKPLOY")
        print("=" * 70)
        print("\nVotre session Telegram a été convertie avec succès en StringSession !")
        print("\nVariable d'environnement pour Dokploy :")
        print("-" * 70)
        print(f"TELEGRAM_STRING_SESSION={string_session}")
        print("-" * 70)
        print("\nConseil Dokploy :")
        print("1. Copiez la valeur ci-dessus dans les variables d'environnement de Dokploy.")
        print("2. Ainsi, VidTele se connectera directement à Telegram sans nécessiter")
        print("   de volume de fichier .session sur votre VPS !")
        print("=" * 70)
    except Exception as e:
        print(f"[ERREUR] Impossible d'exporter la session : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
