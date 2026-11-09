"""Tests unitaires de la matrice de permissions et rôles."""
import pytest
from app.core.errors import ForbiddenException
from app.core.permissions import AuthenticatedUser, UserRole, require_roles


@pytest.mark.asyncio
async def test_require_roles_success():
    checker = require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)
    user = AuthenticatedUser(username="admin1", role=UserRole.ADMIN.value, active=True)

    result = await checker(user=user)
    assert result.username == "admin1"
    assert result.role == UserRole.ADMIN.value


@pytest.mark.asyncio
async def test_require_roles_forbidden():
    checker = require_roles(UserRole.ADMIN)
    user = AuthenticatedUser(username="op1", role=UserRole.OPERATOR.value, active=True)

    with pytest.raises(ForbiddenException) as exc_info:
        await checker(user=user)
    assert exc_info.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_require_roles_inactive_user():
    checker = require_roles(UserRole.OPERATOR)
    user = AuthenticatedUser(username="op1", role=UserRole.OPERATOR.value, active=False)

    with pytest.raises(ForbiddenException) as exc_info:
        await checker(user=user)
    assert exc_info.value.code == "FORBIDDEN"
    assert "inactif" in exc_info.value.message.lower()

