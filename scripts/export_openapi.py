"""Script d'export du schéma OpenAPI de l'API WeaveGuard vers docs/openapi.json."""
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Configuration de base pour l'export sans dépendance à MongoDB
try:
    from app.main import app  # type: ignore[missing-import]
except ModuleNotFoundError:
    from backend.app.main import app  # type: ignore[import-not-found,no-redef]


def export_openapi() -> Path:
    openapi_schema = app.openapi()
    docs_dir = ROOT_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    out_file = docs_dir / "openapi.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)

    print(f"Schéma OpenAPI exporté avec succès vers : {out_file}")
    return out_file


if __name__ == "__main__":
    export_openapi()

