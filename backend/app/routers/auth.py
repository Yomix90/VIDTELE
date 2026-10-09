"""
Routes d'authentification : Inscription, Connexion, Rafraîchissement de jeton et Profil.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import InviteCode, User
from app.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.security import (
    brute_force_protector,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_client_ip,
    get_current_active_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentification"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Inscription d'un nouvel utilisateur.
    Requiert obligatoirement un code d'invitation valide généré par un administrateur.
    """
    # 1. Vérifier si le nom d'utilisateur est déjà utilisé
    stmt_user = select(User).where(User.username == data.username)
    result_user = await db.execute(stmt_user)
    if result_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce nom d'utilisateur est déjà pris",
        )

    # 2. Vérifier la validité du code d'invitation
    stmt_invite = select(InviteCode).where(InviteCode.code == data.invite_code)
    result_invite = await db.execute(stmt_invite)
    invite = result_invite.scalar_one_or_none()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code d'invitation invalide",
        )

    if invite.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce code d'invitation a déjà été utilisé",
        )

    if invite.expires_at and invite.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce code d'invitation a expiré",
        )

    # 3. Création du nouvel utilisateur
    new_user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        role="user",
        is_active=True,
        max_concurrent_streams=settings.MAX_CONCURRENT_STREAMS_PER_USER,
        last_login_at=now,
    )
    db.add(new_user)
    await db.flush()  # Pour générer l'id de new_user

    # 4. Marquer le code d'invitation comme consommé
    invite.is_used = True
    invite.used_by_id = new_user.id
    invite.used_at = now

    await db.commit()
    await db.refresh(new_user)

    # 5. Générer les jetons d'accès et de rafraîchissement
    access_token = create_access_token(new_user.id, new_user.username, new_user.role)
    refresh_token = create_refresh_token(new_user.id, new_user.username)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=new_user.id,
        username=new_user.username,
        role=new_user.role,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Connexion d'un utilisateur avec protection anti brute-force.
    Renvoie un access token et un refresh token.
    """
    ip = get_client_ip(request)
    identifier = f"{ip}:{data.username}"

    # Vérification du blocage anti brute-force
    is_locked, remaining_seconds = brute_force_protector.is_locked(identifier)
    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Trop de tentatives infructueuses. Veuillez réessayer dans {remaining_seconds} secondes.",
        )

    # Recherche de l'utilisateur
    stmt = select(User).where(User.username == data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        brute_force_protector.register_failure(identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte utilisateur est désactivé",
        )

    # Réinitialisation des tentatives échouées en cas de succès
    brute_force_protector.reset(identifier)

    # Mise à jour de la dernière date de connexion
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user.last_login_at = now
    await db.commit()

    # Création des jetons
    access_token = create_access_token(user.id, user.username, user.role)
    refresh_token = create_refresh_token(user.id, user.username)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        username=user.username,
        role=user.role,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Renouvellement d'un access token à partir d'un refresh token valide.
    """
    payload = decode_token(data.refresh_token, expected_type="refresh")
    user_id_str = payload.get("sub")

    if not user_id_str or not user_id_str.isdigit():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton de rafraîchissement invalide",
        )

    user_id = int(user_id_str)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable ou compte désactivé",
        )

    # Nouveaux jetons
    new_access_token = create_access_token(user.id, user.username, user.role)
    new_refresh_token = create_refresh_token(user.id, user.username)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        username=user.username,
        role=user.role,
    )


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_active_user),
):
    """
    Récupère les informations du compte utilisateur connecté.
    """
    return current_user


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Modification du mot de passe de l'utilisateur connecté.
    """
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'ancien mot de passe est incorrect",
        )

    current_user.hashed_password = hash_password(data.new_password)
    await db.commit()

    return MessageResponse(message="Mot de passe modifié avec succès")
