# ==============================================================================
# WeaveGuard AI - Dockerfile Multi-étages (Frontend compilé + Backend CPU)
# ==============================================================================

# ------------------------------------------------------------------------------
# Étage 1 : Compilation du Frontend (React + Vite + TypeScript)
# ------------------------------------------------------------------------------
FROM node:22-bookworm-slim AS frontend-build

WORKDIR /build

# 1. Copie des fichiers de dépendances et installation propre
COPY frontend/package*.json ./
RUN npm ci

# 2. Copie du code source frontend et compilation de production
COPY frontend ./
ENV VITE_API_URL=""
RUN npm run build


# ------------------------------------------------------------------------------
# Étage 2 : Runtime Backend (FastAPI + Inférence CPU + Fichiers Statiques)
# ------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

# Empêcher la création de fichiers .pyc et forcer l'affichage immédiat des logs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    TORCH_NUM_THREADS=4 \
    DEVICE=cpu \
    HOST=0.0.0.0 \
    PORT=8000 \
    FRONTEND_DIST_DIR=/app/frontend/dist

# 1. Dépendances système minimales pour OpenCV, Torch et Pillow (nettoyage apt immédiat)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 2. Création d'un utilisateur non-root dédié
RUN groupadd -g 10001 weaveguard && \
    useradd -u 10001 -g weaveguard -m -s /bin/sh -d /home/weaveguard weaveguard

# 3. Arborescence de travail
WORKDIR /app

# 4. Installation des dépendances Python (roues CPU PyTorch officielles + requirements)
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.13.0 torchvision==0.28.0 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    python -c "import torch, torchvision, ultralytics, faiss, scipy, PIL, argon2, pymongo; print('Dépendances Python validées.')"

# 5. Création des répertoires de montage, de distribution et de stockage avec permissions non-root
RUN mkdir -p /app/backend /app/docs /app/frontend/dist /app/storage /app/models /app/datasets /app/data/images && \
    chown -R weaveguard:weaveguard /app

# 6. Copie du code backend, du contrat OpenAPI et du build frontend React
COPY --chown=weaveguard:weaveguard backend /app/backend
COPY --chown=weaveguard:weaveguard docs/openapi.json /app/docs/openapi.json
COPY --from=frontend-build --chown=weaveguard:weaveguard /build/dist /app/frontend/dist

# Création du lien symbolique pour exécuter facilement "python scripts/..." depuis /app
RUN ln -s /app/backend/scripts /app/scripts

# 7. Bascule vers l'utilisateur non-root
USER weaveguard

# 8. Exposition du port de service interne
EXPOSE 8000

# 9. Healthcheck autonome (sans curl, via urllib standard)
HEALTHCHECK --interval=5s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()" || exit 1

# 10. Commande de démarrage : uvicorn avec un SEUL worker
CMD ["uvicorn", "app.main:app", "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "8000"]


# ------------------------------------------------------------------------------
# Étage 3 : Test automatisé (CI / Docker compose profile test)
# ------------------------------------------------------------------------------
FROM runtime AS test

USER root
COPY backend/requirements-dev.txt /tmp/requirements-dev.txt
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt
USER weaveguard

# Par défaut, exécute la suite de tests unitaires et intégration (sans les tests @pytest.mark.slow)
CMD ["pytest", "backend/tests", "-m", "not slow", "-v"]
