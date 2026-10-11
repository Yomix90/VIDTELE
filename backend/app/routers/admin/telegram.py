"""
Administration — Connexion Telegram : canal, comptes, authentification par téléphone.

Code déplacé tel quel depuis l'ancien routers/admin.py (Phase 1).
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import SystemSetting, TelegramAccount, User
from app.schemas import (
    TelegramAccountCreate,
    TelegramAccountResponse,
    TelegramConfigUpdateRequest,
    TelegramPhoneAuthRequest,
    TelegramPhoneVerifyRequest,
)
from app.security import get_current_admin
from app.telegram_client import telegram_manager

router = APIRouter()

# -------------------------------------------------------------
# 6. Gestion Dynamique des Canaux Telegram MTProto
# -------------------------------------------------------------

from pydantic import BaseModel


class ChannelTestRequest(BaseModel):
    channel_target: str

class ChannelSetRequest(BaseModel):
    channel_id: str


@router.get("/telegram/status")
async def get_telegram_status(
    current_admin: User = Depends(get_current_admin),
):
    """Retourne l'état de connexion MTProto et le canal configuré."""
    return await telegram_manager.get_connection_status()


@router.get("/telegram/channels")
async def list_telegram_channels(
    current_admin: User = Depends(get_current_admin),
):
    """Liste tous les canaux et groupes auxquels le compte Telegram connecté a accès."""
    return await telegram_manager.list_available_channels()


@router.post("/telegram/test-channel")
async def test_telegram_channel(
    req: ChannelTestRequest,
    current_admin: User = Depends(get_current_admin),
):
    """Vérifie si un canal ou groupe spécifique est accessible par VidTele."""
    result = await telegram_manager.test_channel(req.channel_target)
    return result


@router.post("/telegram/set-channel")
async def set_telegram_channel(
    req: ChannelSetRequest,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enregistre le nouveau canal Telegram actif (en base et mémoire)."""
    clean_target = req.channel_id.strip()
    try:
        cid = int(clean_target)
    except ValueError:
        test_res = await telegram_manager.test_channel(clean_target)
        if not test_res.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=test_res.get("error", "Identifiant de canal invalide."),
            )
        cid = int(test_res.get("formatted_id") or test_res.get("id"))

    # Test d'accès
    test_res = await telegram_manager.test_channel(cid)
    if not test_res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de valider ce canal : {test_res.get('error')}",
        )

    # 1. Mise à jour en mémoire
    await telegram_manager.set_active_channel(cid)

    # 2. Sauvegarde persistante en base SQLite (SystemSetting)
    from app.models import SystemSetting
    stmt = select(SystemSetting).where(SystemSetting.key == "TELEGRAM_CHANNEL_ID")
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        existing.value = str(cid)
    else:
        db.add(SystemSetting(key="TELEGRAM_CHANNEL_ID", value=str(cid)))
    await db.commit()

    # 3. Sauvegarde dans .env si accessible
    try:
        import re
        from pathlib import Path
        for p in [Path(__file__).resolve().parent.parent.parent / ".env", Path("/app/data/.env"), Path(".env")]:
            if p.exists():
                txt = p.read_text(encoding="utf-8")
                if "TELEGRAM_CHANNEL_ID=" in txt:
                    txt = re.sub(r"TELEGRAM_CHANNEL_ID=.*", f"TELEGRAM_CHANNEL_ID={cid}", txt)
                else:
                    txt += f"\nTELEGRAM_CHANNEL_ID={cid}\n"
                p.write_text(txt, encoding="utf-8")
                break
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Canal configuré avec succès : '{test_res.get('title')}' (ID: {cid})",
        "channel": test_res,
    }


# -------------------------------------------------------------
# 5b. Gestion Multi-Comptes & Diagnostics Telegram MTProto
# -------------------------------------------------------------

@router.get("/telegram/accounts", response_model=List[TelegramAccountResponse])
async def list_telegram_accounts(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retourne l'ensemble des comptes Telegram configurés et reliés."""
    stmt = select(TelegramAccount).order_by(desc(TelegramAccount.is_active), desc(TelegramAccount.created_at))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/telegram/accounts", response_model=TelegramAccountResponse, status_code=status.HTTP_201_CREATED)
async def add_telegram_account_session(
    data: TelegramAccountCreate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Lie un nouveau compte Telegram à partir d'une clé StringSession.
    Teste la session avant de l'enregistrer.
    """
    # 1. Tester la validité de la session
    test_res = await telegram_manager.test_session_string(
        string_session=data.string_session,
        api_id=data.api_id,
        api_hash=data.api_hash,
    )
    if not test_res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=test_res.get("error", "Clé StringSession invalide ou expirée."),
        )

    user_info = test_res.get("user", {})

    # 2. Si le compte doit être activé, désactiver les autres
    if data.make_active:
        stmt_deact = select(TelegramAccount).where(TelegramAccount.is_active == True)
        active_accounts = (await db.execute(stmt_deact)).scalars().all()
        for a in active_accounts:
            a.is_active = False

    # 3. Créer l'enregistrement
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    account = TelegramAccount(
        name=data.name.strip(),
        phone=user_info.get("phone"),
        api_id=data.api_id,
        api_hash=data.api_hash,
        string_session=data.string_session.strip(),
        is_active=data.make_active,
        account_user_id=user_info.get("id"),
        account_username=user_info.get("username"),
        account_first_name=user_info.get("first_name"),
        status="connected",
        last_tested_at=now,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    # 4. Basculer le client actif si demandé
    if data.make_active:
        await telegram_manager.switch_active_account(
            string_session=data.string_session.strip(),
            api_id=data.api_id,
            api_hash=data.api_hash,
        )

    return account


@router.post("/telegram/accounts/{account_id}/activate")
async def activate_telegram_account(
    account_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Définit ce compte Telegram comme le compte actif pour le streaming et la synchronisation."""
    stmt = select(TelegramAccount).where(TelegramAccount.id == account_id)
    account = (await db.execute(stmt)).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Compte Telegram introuvable.")

    if not account.string_session:
        raise HTTPException(status_code=400, detail="Ce compte n'a pas de session StringSession valide.")

    # Désactiver tous les autres comptes
    all_accounts = (await db.execute(select(TelegramAccount))).scalars().all()
    for a in all_accounts:
        a.is_active = (a.id == account.id)

    # Basculer le client en mémoire
    switch_res = await telegram_manager.switch_active_account(
        string_session=account.string_session,
        api_id=account.api_id,
        api_hash=account.api_hash,
    )

    account.status = "connected" if switch_res.get("success") else "error"
    account.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()

    return {
        "success": True,
        "message": f"Compte '{account.name}' activé avec succès !",
        "status": switch_res.get("status"),
    }


@router.post("/telegram/accounts/{account_id}/test")
async def test_specific_telegram_account(
    account_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Teste la connexion d'un compte Telegram spécifique et mesure sa latence."""
    stmt = select(TelegramAccount).where(TelegramAccount.id == account_id)
    account = (await db.execute(stmt)).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Compte Telegram introuvable.")

    if not account.string_session:
        return {
            "success": False,
            "error": "Aucune session StringSession enregistrée pour ce compte.",
        }

    test_res = await telegram_manager.test_session_string(
        string_session=account.string_session,
        api_id=account.api_id,
        api_hash=account.api_hash,
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    account.last_tested_at = now
    if test_res.get("success"):
        account.status = "connected"
        account.last_error = None
        user = test_res.get("user", {})
        account.account_user_id = user.get("id")
        account.account_first_name = user.get("first_name")
        account.account_username = user.get("username")
    else:
        account.status = "error"
        account.last_error = test_res.get("error")

    await db.commit()
    return test_res


@router.delete("/telegram/accounts/{account_id}")
async def delete_telegram_account(
    account_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Supprime un compte Telegram lié."""
    stmt = select(TelegramAccount).where(TelegramAccount.id == account_id)
    account = (await db.execute(stmt)).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Compte Telegram introuvable.")

    # Vérifier le nombre total de comptes
    total = (await db.execute(select(func.count(TelegramAccount.id)))).scalar_one()
    if total <= 1:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer le seul compte Telegram restant.",
        )

    if account.is_active:
        raise HTTPException(
            status_code=400,
            detail="Ce compte est actuellement actif. Activez d'abord un autre compte avant de supprimer celui-ci.",
        )

    await db.delete(account)
    await db.commit()
    return {"success": True, "message": f"Compte '{account.name}' délié avec succès."}


@router.post("/telegram/auth/send-code")
async def send_telegram_phone_code(
    data: TelegramPhoneAuthRequest,
    current_admin: User = Depends(get_current_admin),
):
    """Envoie une demande de code de confirmation par SMS ou message Telegram officiel."""
    res = await telegram_manager.send_phone_code(
        phone=data.phone,
        api_id=data.api_id,
        api_hash=data.api_hash,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Échec de l'envoi du code."))
    return res


@router.post("/telegram/auth/verify-code")
async def verify_telegram_phone_code(
    data: TelegramPhoneVerifyRequest,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Vérifie le code OTP reçu et le mot de passe 2FA si présent,
    puis lie automatiquement le compte à la plateforme Atlas Play.
    """
    res = await telegram_manager.verify_phone_code(
        phone=data.phone,
        code=data.code,
        phone_code_hash=data.phone_code_hash,
        password_2fa=data.password_2fa,
    )
    if not res.get("success"):
        # Peut nécessiter le mot de passe 2FA
        if res.get("needs_2fa"):
            return {
                "success": False,
                "needs_2fa": True,
                "message": res.get("message", "Mot de passe 2FA requis."),
            }
        raise HTTPException(status_code=400, detail=res.get("error", "Code de validation incorrect."))

    string_session = res.get("string_session")
    user_info = res.get("user", {})

    # Désactiver les autres si demandé
    if data.make_active:
        stmt_deact = select(TelegramAccount).where(TelegramAccount.is_active == True)
        for a in (await db.execute(stmt_deact)).scalars().all():
            a.is_active = False

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    account = TelegramAccount(
        name=data.account_name.strip() if data.account_name else f"Compte {user_info.get('first_name', 'Telegram')}",
        phone=data.phone,
        api_id=data.api_id,
        api_hash=data.api_hash,
        string_session=string_session,
        is_active=data.make_active,
        account_user_id=user_info.get("id"),
        account_username=user_info.get("username"),
        account_first_name=user_info.get("first_name"),
        status="connected",
        last_tested_at=now,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    if data.make_active:
        await telegram_manager.switch_active_account(
            string_session=string_session,
            api_id=data.api_id,
            api_hash=data.api_hash,
        )

    return {
        "success": True,
        "message": f"Compte '{account.name}' connecté et lié avec succès !",
        "account": account,
    }


@router.post("/telegram/test-connection")
async def run_telegram_diagnostics(
    current_admin: User = Depends(get_current_admin),
):
    """Lance un test de diagnostic complet de la connexion active et du canal de stockage."""
    return await telegram_manager.get_detailed_diagnostics()


@router.post("/telegram/config")
async def update_telegram_config(
    data: TelegramConfigUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Met à jour les identifiants Telegram (API_ID, API_HASH, CHANNEL_ID) persistés en base."""

    if data.api_id is not None:
        settings.TELEGRAM_API_ID = data.api_id
        db.add(SystemSetting(key="TELEGRAM_API_ID", value=str(data.api_id)))

    if data.api_hash is not None and data.api_hash.strip():
        settings.TELEGRAM_API_HASH = data.api_hash.strip()
        db.add(SystemSetting(key="TELEGRAM_API_HASH", value=data.api_hash.strip()))

    if data.channel_id is not None and data.channel_id.strip():
        cid_str = data.channel_id.strip()
        try:
            cid = int(cid_str)
            settings.TELEGRAM_CHANNEL_ID = cid
            db.add(SystemSetting(key="TELEGRAM_CHANNEL_ID", value=str(cid)))
            await telegram_manager.set_active_channel(cid)
        except ValueError:
            pass

    await db.commit()
    diag = await telegram_manager.get_detailed_diagnostics()
    return {
        "success": True,
        "message": "Configuration Telegram mise à jour avec succès.",
        "diagnostics": diag,
    }



