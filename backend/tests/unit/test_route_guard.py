"""Test garde-fou : vérifie qu'aucune route protégée n'est exposée sans contrôle d'accès."""
from fastapi.routing import APIRoute
from app.core.permissions import get_current_user, require_roles
from app.main import app

# Routes contractuellement publiques (exemptées d'authentification)
PUBLIC_ROUTES = {
    "/health",
    "/api/v1/auth/login",
    # Documentation OpenAPI
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/openapi.json",
}


def test_all_routes_have_security_dependencies():
    """Parcourt toutes les routes de l'application FastAPI.

    Échoue si une route (hors exceptions publiques) ne possède aucune dépendance
    d'authentification ou de rôle.
    """
    unprotected_routes = []

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue

        path = route.path
        if path in PUBLIC_ROUTES:
            continue

        # Extraction des dépendances
        has_auth = False
        all_deps = list(route.dependencies)
        if hasattr(route, "dependant"):
            for dep in route.dependant.dependencies:
                all_deps.append(dep)
            for param in route.dependant.params:
                if hasattr(param, "dependencies"):
                    all_deps.extend(param.dependencies)

        # Vérification si l'une des dépendances fait appel à get_current_user ou require_roles
        for dep in all_deps:
            call_fn = getattr(dep, "call", dep)
            if call_fn == get_current_user:
                has_auth = True
                break
            # require_roles génère une fonction closure role_checker
            fn_name = getattr(call_fn, "__name__", "")
            fn_qualname = getattr(call_fn, "__qualname__", "")
            if "role_checker" in fn_name or "role_checker" in fn_qualname or "require_roles" in fn_qualname:
                has_auth = True
                break

        if not has_auth:
            unprotected_routes.append(f"{route.methods} {path}")

    assert not unprotected_routes, (
        f"Garde-fou violé : les routes suivantes n'ont pas de dépendance d'authentification ou de rôle : "
        f"{unprotected_routes}"
    )

