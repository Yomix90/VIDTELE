"""
Sécurité, hachage des mots de passe, gestion des jetons JWT et anti brute-force.
"""
import ipaddress
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User

# Sécurité Bearer Token pour Swagger et les requêtes HTTP
security_bearer = HTTPBearer(auto_error=False)

# -------------------------------------------------------------
# Protection Anti Brute-Force (Mémoire)
# -------------------------------------------------------------
class BruteForceProtector:
    """Suivi des tentatives de connexion échouées par IP/utilisateur."""
    def __init__(self):
        # Clé: identifiant (ip:username), Valeur: liste de timestamps UTC des échecs
        self._failures: dict[str, list[datetime]] = defaultdict(list)

    def is_locked(self, identifier: str, max_attempts: Optional[int] = None) -> Tuple[bool, int]:
        """Vérifie si l'identifiant est bloqué. Renvoie (bloqué, secondes_restantes)."""
        if max_attempts is None:
            max_attempts = settings.MAX_LOGIN_ATTEMPTS
        now = datetime.now(timezone.utc)
        window = timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        # Nettoyage des tentatives hors de la fenêtre
        recent = [t for t in self._failures.get(identifier, []) if (now - t) < window]
        if recent:
            self._failures[identifier] = recent
        else:
            self._failures.pop(identifier, None)

        if len(recent) >= max_attempts:
            oldest = recent[-max_attempts]
            remaining = int((oldest + window - now).total_seconds())
            return True, max(remaining, 1)
        return False, 0

    def register_failure(self, identifier: str) -> None:
        """Enregistre un échec de connexion."""
        self._failures[identifier].append(datetime.now(timezone.utc))
        if len(self._failures) > 10_000:
            self._prune()

    def _prune(self) -> None:
        """Supprime les entrées expirées pour borner la mémoire (clés tournantes d'un attaquant)."""
        limit = datetime.now(timezone.utc) - timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        for key in [k for k, v in self._failures.items() if not v or v[-1] < limit]:
            del self._failures[key]

    def reset(self, identifier: str) -> None:
        """Réinitialise les échecs après une connexion réussie."""
        if identifier in self._failures:
            del self._failures[identifier]


brute_force_protector = BruteForceProtector()


def check_login_allowed(ip: str, username: str) -> Tuple[bool, int]:
    """
    Vérifie les deux verrous anti brute-force :
    - par IP + compte (MAX_LOGIN_ATTEMPTS) ;
    - par compte seul (MAX_LOGIN_ATTEMPTS_PER_ACCOUNT), qui tient même si l'attaquant change d'IP.
    Renvoie (autorisé, secondes_restantes).
    """
    locked, remaining = brute_force_protector.is_locked(f"{ip}:{username}")
    if not locked:
        locked, remaining = brute_force_protector.is_locked(
            f"compte:{username.lower()}", settings.MAX_LOGIN_ATTEMPTS_PER_ACCOUNT
        )
    if locked:
        return False, remaining
    return True, 0


def register_login_failure(ip: str, username: str) -> None:
    brute_force_protector.register_failure(f"{ip}:{username}")
    brute_force_protector.register_failure(f"compte:{username.lower()}")


def reset_login_failures(ip: str, username: str) -> None:
    brute_force_protector.reset(f"{ip}:{username}")
    brute_force_protector.reset(f"compte:{username.lower()}")


# -------------------------------------------------------------
# Hachage et Vérification des Mots de Passe (Bcrypt)
# -------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hache un mot de passe en utilisant bcrypt avec un sel aléatoire."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie la correspondance entre le mot de passe en clair et son hachage."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# -------------------------------------------------------------
# Gestion des Jetons JWT
# -------------------------------------------------------------
def create_access_token(user_id: int, username: str, role: str) -> str:
    """Crée un JWT d'accès de courte durée."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: int, username: str) -> str:
    """Crée un JWT de rafraîchissement de longue durée."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_stream_token(user_id: int, video_id: int) -> str:
    """Crée un jeton d'accès temporaire signé pour le flux vidéo."""
    expire = datetime.now(timezone.utc) + timedelta(seconds=settings.STREAM_TOKEN_EXPIRE_SECONDS)
    payload = {
        "sub": str(user_id),
        "vid": int(video_id),
        "type": "stream",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> dict:
    """Décode et valide un jeton JWT."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_type = payload.get("type")
        if token_type != expected_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Type de jeton invalide (attendu: {expected_type}, reçu: {token_type})",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Le jeton d'authentification a expiré",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton d'authentification invalide",
        )


# -------------------------------------------------------------
# Dépendances FastAPI pour les Utilisateurs
# -------------------------------------------------------------
async def get_current_user(
    request: Request = None,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extrait et vérifie l'utilisateur courant à partir du header Authorization ou du cookie de session."""
    token = None
    if auth and auth.credentials:
        token = auth.credentials
    elif request:
        token = request.cookies.get("admin_token") or request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token, expected_type="access")
    user_id_str = payload.get("sub")
    if not user_id_str or not user_id_str.isdigit():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant utilisateur invalide dans le jeton",
        )

    user_id = int(user_id_str)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Vérifie que l'utilisateur est actif."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte utilisateur désactivé",
        )
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Vérifie que l'utilisateur a le rôle administrateur."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return current_user


async def get_optional_current_user(
    request: Request = None,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Extrait l'utilisateur s'il est authentifié, sinon renvoie None sans lever d'erreur."""
    try:
        return await get_current_user(request=request, auth=auth, db=db)
    except Exception:
        return None


def _parse_networks(raw: str) -> list:
    networks = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                networks.append(ipaddress.ip_network(part, strict=False))
            except ValueError:
                pass
    return networks


def _is_trusted_proxy(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in _parse_networks(settings.TRUSTED_PROXIES))


def get_client_ip(request: Request) -> str:
    """
    Récupère l'adresse IP réelle du client.
    X-Forwarded-For n'est pris en compte que si la connexion vient d'un proxy de confiance
    (Traefik). On lit alors la liste de droite à gauche et on garde la première IP qui
    n'est pas un proxy : c'est celle ajoutée par Traefik, que le client ne peut pas falsifier.
    """
    peer = request.client.host if request.client else "unknown"
    if not _is_trusted_proxy(peer):
        return peer

    forwarded = request.headers.get("X-Forwarded-For", "")
    for candidate in reversed([p.strip() for p in forwarded.split(",") if p.strip()]):
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if not _is_trusted_proxy(candidate):
            return candidate
    return peer
