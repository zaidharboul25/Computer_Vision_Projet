"""Schémas Pydantic pour l'authentification et les utilisateurs."""
from typing import Optional
from pydantic import BaseModel, Field
from app.core.permissions import UserRole


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    id: str
    username: str
    role: UserRole
    active: bool
    created_at: str
    last_login: Optional[str] = None


class MeResponse(UserResponse):
    csrf_token: str = Field(..., description="Jeton CSRF à renvoyer dans X-CSRF-Token (requêtes modifiantes par cookie)")


class UserLoginResponse(BaseModel):
    access_token: str = Field(..., description="Jeton Bearer pour les clients API (l'interface web utilise le cookie httpOnly)")
    token_type: str = "bearer"
    user: UserResponse
    csrf_token: Optional[str] = Field(None, description="Jeton CSRF associé à la session par cookie")


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.OPERATOR


class UserUpdateRequest(BaseModel):
    role: Optional[UserRole] = None
    active: Optional[bool] = None


class UserResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)


class ActionStatusResponse(BaseModel):
    status: str = Field("ok", description="Statut de l'opération")
    message: str = Field(..., description="Message informatif")


