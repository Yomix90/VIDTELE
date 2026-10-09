"""
Script interactif pour initialiser la session Telegram MTProto (Telethon).
À exécuter UNE SEULE FOIS pour générer le fichier de session persistant.
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# Chargement du fichier .env
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "vidtele_session")


def print_banner():
    print("=" * 70)
    print("          VIDTELE - CONNEXION INITIALE TELEGRAM MTPROTO")
    print("=" * 70)
    print("Ce script permet de connecter le serveur à votre compte Telegram")
    print("et de créer le fichier de session sécurisé qui sera utilisé par l'API.\n")


def check_or_prompt_credentials():
    global API_ID, API_HASH
    if not API_ID or API_ID == "0" or not API_HASH or API_HASH == "none":
        print("[!] Configuration des identifiants Telegram MTProto :")
        print("    1. Rendez-vous sur https://my.telegram.org")
        print("    2. Allez dans 'API development tools'")
        print("    3. Copiez précisément votre App api_id et App api_hash\n")

        API_ID = input("Entrez votre API_ID (chiffres uniquement) : ").strip()
        API_HASH = input("Entrez votre API_HASH (32 caractères hexadécimaux) : ").strip()

    try:
        api_id_int = int(API_ID)
    except ValueError:
        print("\n[ERREUR] L'API_ID doit être un nombre entier valide.")
        sys.exit(1)

    API_HASH = API_HASH.strip().lower()
    if len(API_HASH) != 32:
        print(f"\n[ERREUR] L'API_HASH saisi fait {len(API_HASH)} caractères.")
        print("Un API_HASH Telegram valide doit faire exactement 32 caractères (sans espace).")
        print(f"Valeur saisie : '{API_HASH}'")
        sys.exit(1)

    # Sauvegarde automatique dans .env si valide
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        if "TELEGRAM_API_ID=" in content:
            import re
            content = re.sub(r"TELEGRAM_API_ID=.*", f"TELEGRAM_API_ID={api_id_int}", content)
            content = re.sub(r"TELEGRAM_API_HASH=.*", f"TELEGRAM_API_HASH={API_HASH}", content)
            env_path.write_text(content, encoding="utf-8")

    return api_id_int, API_HASH


async def main():
    print_banner()
    api_id, api_hash = check_or_prompt_credentials()

    session_name = SESSION_NAME
    if Path(session_name).is_absolute():
        session_path = Path(session_name)
    else:
        session_path = Path(__file__).resolve().parent / session_name
    session_path.parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(str(session_path), api_id, api_hash)

    print(f"\n[*] Connexion aux serveurs Telegram avec la session '{session_path}'...")
    await client.connect()

    if not await client.is_user_authorized():
        phone = input("\nEntrez votre numéro de téléphone au format international (ex: +33612345678) : ").strip()
        print(f"[*] Envoi du code de vérification à {phone}...")
        await client.send_code_request(phone)

        code = input("Entrez le code reçu sur votre application Telegram : ").strip()
        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            print("[*] Votre compte est protégé par la vérification en 2 étapes (2FA).")
            password = input("Entrez votre mot de passe 2FA : ").strip()
            await client.sign_in(password=password)

    me = await client.get_me()
    print("\n" + "=" * 70)
    print(f"[SUCCÈS] Connecté avec succès en tant que : {me.first_name} (@{me.username or 'sans_username'})")
    print(f"Session enregistrée dans : {session_path}.session")
    print("=" * 70)

    # Export pour Dokploy (StringSession)
    try:
        from telethon.sessions import StringSession
        string_session = StringSession.save(client.session)
        print("\n" + "=" * 70)
        print("          POUR DÉPLOIEMENT DOKPLOY / DOCKER (FACULTATIF)")
        print("=" * 70)
        print("Vous pouvez définir cette variable d'environnement dans l'interface Dokploy :")
        print(f"TELEGRAM_STRING_SESSION={string_session}")
        print("(Permet à VidTele de tourner sans avoir à copier le fichier .session)")
        print("=" * 70)
    except Exception as e:
        pass

    # Aide pour trouver le Channel ID
    print("\n[*] Recherche de vos canaux Telegram pour vous aider à trouver votre CHANNEL_ID :")
    print("-" * 70)
    dialog_count = 0
    async for dialog in client.iter_dialogs():
        if dialog.is_channel:
            dialog_count += 1
            print(f"  • Nom: '{dialog.name}' | ID: {dialog.id}")

    if dialog_count == 0:
        print("  (Aucun canal trouvé sur ce compte. Créez un canal privé et invitez-y ce compte.)")
    print("-" * 70)
    print("\nCONSEIL : Copiez l'ID de votre canal privé ci-dessus (ex: -100xxxxxxxxxx)")
    print("et mettez-le dans le fichier .env (paramètre TELEGRAM_CHANNEL_ID).\n")

    await client.disconnect()
    print("[*] Déconnexion terminée. La session est prête pour l'API VidTele !")


if __name__ == "__main__":
    asyncio.run(main())
