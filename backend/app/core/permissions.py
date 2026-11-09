"""Matrice de rôles et permissions centralisée de WeaveGuard AI (§10).

Rôles contractuels :
- operator    : créer des inspections, voir les siennes, overlays/heatmaps, revue, commentaires
- supervisor  : voir toutes les inspections, filtres, statistiques, décisions, exports
- admin       : utilisateurs, rôles, paramètres, rétention, journal d'audit, activation de modèles
- ml_engineer : modèles, rapports d'évaluation, similarité, export des retours, lecture des inspections
- auditor     : lecture seule des résultats autorisés, exports, journal d'audit
"""
from enum import Enum
from typing import Callable, List, Optional
from fastapi import Depends, Header
import jwt
from app.core.errors import ForbiddenException, UnauthenticatedException
from app.core.security import decode_access_token


class UserRole(str, Enum):
    OPERATOR = "operator"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"
    ML_ENGINEER = "ml_engineer"
    AUDITOR = "auditor"


ALL_ROLES = [UserRole.OPERATOR, UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.ML_ENGINEER, UserRole.AUDITOR]


class AuthenticatedUser:
    def __init__(self, username: str, role: str, active: bool = True, id: Optional[str] = None):
        self.username = username
        self.role = role
        self.active = active
        self.id = id or username

    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def can_view_all_inspections(self) -> bool:
        return self.role in {UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.ML_ENGINEER, UserRole.AUDITOR}


def extract_token_from_header(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise UnauthenticatedException(message="En-tête Authorization manquant")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthenticatedException(message="Format de jeton invalide (Bearer attendu)")
    return parts[1]


async def get_current_user(token: str = Depends(extract_token_from_header)) -> AuthenticatedUser:
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise UnauthenticatedException(message="Jeton JWT expiré")
    except jwt.PyJWTError:
        raise UnauthenticatedException(message="Jeton JWT invalide ou signature incorrecte")

    username = payload.get("sub")
    role = payload.get("role")
    if not username or not role:
        raise UnauthenticatedException(message="Jeton JWT incomplet")

    return AuthenticatedUser(username=username, role=role, active=True)


def require_roles(*allowed_roles) -> Callable:
    """Dépendance FastAPI vérifiant que l'utilisateur possède l'un des rôles requis."""
    flat_roles = []
    for r in allowed_roles:
        if isinstance(r, (list, tuple, set)):
            flat_roles.extend(r)
        else:
            flat_roles.append(r)
    role_values = {r.value if isinstance(r, UserRole) else r for r in flat_roles}

    async def role_checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if not user.active:
            raise ForbiddenException(message="Compte utilisateur inactif")
        if user.role not in role_values:
            raise ForbiddenException(
                message=f"Action interdite : rôle '{user.role}' insuffisant. Requis : {list(role_values)}"
            )
        return user

    return role_checker

