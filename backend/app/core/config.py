"""Configuration globale de l'application WeaveGuard AI.

Utilise pydantic-settings pour charger et valider les variables d'environnement.
"""
from pathlib import Path
from typing import List, Literal, Optional, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    # Base de données MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "weaveguard"

    # Sécurité & JWT
    JWT_SECRET: str = Field(..., min_length=32, description="Clé secrète cryptographique HS256")
    JWT_EXPIRE_MINUTES: int = 60
    JWT_ALGORITHM: str = "HS256"
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15
    # Limitation par adresse IP (en plus du verrouillage par compte) : protège aussi contre
    # l'énumération d'identifiants inconnus et le « password spraying » sur plusieurs comptes.
    LOGIN_IP_MAX_ATTEMPTS: int = 20
    LOGIN_IP_WINDOW_SECONDS: int = 300

    # Session par cookie httpOnly (le jeton n'est plus lisible par JavaScript → résiste au vol par XSS)
    COOKIE_NAME: str = "wg_token"
    COOKIE_SECURE: Optional[bool] = Field(None, description="None => activé automatiquement si ENV=prod")
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    # Chemins
    MODELS_DIR: Path = Path("models")
    DATASET_DIR: Path = Path("datasets")
    DTD_DIR: Path = Path("data/images")
    STORAGE_DIR: Path = Path("backend/storage")
    FRONTEND_DIST_DIR: Optional[Path] = Field(None, description="Répertoire des fichiers statiques compilés du frontend")

    # Exécution & IA
    DEVICE: Literal["auto", "cuda", "cpu"] = "auto"
    TORCH_NUM_THREADS: Optional[int] = 8
    INFERENCE_LONG_SIDE: int = 1448
    ENGINES_ENABLED: Union[List[str], str] = ["yolo", "patchcore", "similarity"]

    # Limites images & file
    MAX_QUEUE: int = 20
    MAX_UPLOAD_MB: int = 50
    MAX_IMAGE_SIDE: int = 8000
    ALLOWED_FORMATS: Union[List[str], str] = ["jpeg", "jpg", "png"]

    # Exploitation, Rétention & Revue
    RETENTION_DAYS: int = 90
    REJECTION_REASONS: Union[List[str], str] = [
        "artefact_tissage",
        "faux_positif_texture",
        "pli_tissu",
        "couture",
        "ombre_eclairage",
        "autre",
    ]
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    ENV: Literal["dev", "validation", "prod"] = "dev"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("ENGINES_ENABLED", "ALLOWED_FORMATS", "CORS_ORIGINS", "REJECTION_REASONS", mode="after")
    @classmethod
    def normalize_list(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def forbid_wildcard_cors_with_credentials(self):
        origins = self.CORS_ORIGINS if isinstance(self.CORS_ORIGINS, list) else [self.CORS_ORIGINS]
        if "*" in origins:
            raise ValueError(
                "CORS_ORIGINS ne peut pas contenir '*' : l'API utilise des cookies d'authentification "
                "(allow_credentials=True). Listez explicitement les origines autorisées."
            )
        return self

    @property
    def cookie_secure(self) -> bool:
        """Drapeau Secure du cookie de session : explicite, sinon actif en production."""
        if self.COOKIE_SECURE is not None:
            return self.COOKIE_SECURE
        return self.ENV == "prod"

    def resolve_path(self, path: Path) -> Path:
        """Résout un chemin relativement à la racine du projet s'il n'est pas absolu."""
        if path.is_absolute():
            return path
        return (PROJECT_ROOT / path).resolve()

    def get_models_dir(self) -> Path:
        return self.resolve_path(self.MODELS_DIR)

    def get_dataset_dir(self) -> Path:
        return self.resolve_path(self.DATASET_DIR)

    def get_dtd_dir(self) -> Path:
        return self.resolve_path(self.DTD_DIR)

    def get_storage_dir(self) -> Path:
        path = self.resolve_path(self.STORAGE_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_frontend_dist_dir(self) -> Optional[Path]:
        """Retourne le répertoire des fichiers compilés du frontend s'il existe."""
        if self.FRONTEND_DIST_DIR is not None:
            path = self.resolve_path(self.FRONTEND_DIST_DIR)
            if path.exists() and path.is_dir():
                return path
        # Détection automatique standard
        default_path = (PROJECT_ROOT / "frontend" / "dist").resolve()
        if default_path.exists() and default_path.is_dir():
            return default_path
        return None

    def get_effective_device(self) -> str:
        """Détermine le device actif (cpu|cuda) de façon agnostique et sécurisée."""
        if self.DEVICE == "cpu":
            return "cpu"
        if self.DEVICE == "cuda":
            import torch

            if torch.cuda.is_available():
                return "cuda"
            return "cpu"
        # auto
        import torch

        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def validate_artifact_paths(self) -> List[str]:
        """Vérifie la présence des artefacts obligatoires autorisés."""
        errors = []
        models_dir = self.get_models_dir()
        dataset_dir = self.get_dataset_dir()
        dtd_dir = self.get_dtd_dir()

        required = [
            models_dir / "weaveguard_yolo_v1" / "best.pt",
            models_dir / "weaveguard_yolo_v1" / "model_card.json",
            models_dir / "patchcore" / "patchcore_v1" / "memory_bank.pt",
            models_dir / "patchcore" / "patchcore_v1" / "calibration.json",
            models_dir / "similarity" / "similarity_v1" / "config.json",
            models_dir / "similarity" / "similarity_v1" / "index_dtd.faiss",
            models_dir / "similarity" / "similarity_v1" / "index_weaveguard.faiss",
            models_dir / "fusion" / "fusion_v1" / "fusion_spec.json",
            models_dir / "domain_bias_report_v1.json",
            dataset_dir / "dataset_stats.json",
            dtd_dir,
        ]

        for p in required:
            if not p.exists():
                errors.append(f"Artefact obligatoire manquant : {p}")

        return errors


settings = Settings()

# Configuration du parallélisme CPU PyTorch si spécifié
if settings.TORCH_NUM_THREADS is not None and settings.TORCH_NUM_THREADS > 0:
    import torch

    torch.set_num_threads(settings.TORCH_NUM_THREADS)
