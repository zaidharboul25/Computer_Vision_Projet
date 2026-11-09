# WeaveGuard AI — Plateforme d'Inspection Textile par Vision par Ordinateur

WeaveGuard AI est une solution industrielle d'inspection de tissus combinant deux modèles d'IA complémentaires (détection supervisée YOLOv11 et détection non supervisée d'anomalies de texture PatchCore), un module d'analyse de similarité de texture (DTD), et une interface de revue humaine traçable.

Le backend est développé sous **FastAPI** et s'appuie sur une base de données **MongoDB locale** (Windows).

---

## Architecture Générale

- **Backend** : FastAPI (Python 3.12), architecture asynchrone native (`AsyncMongoClient`), Pydantic v2.
- **Moteurs IA** :
  - **YOLOv11** (`models/weaveguard_yolo_v1`) : détection supervisée d'anomalies textiles.
  - **PatchCore** (`models/patchcore/patchcore_v1`) : mémoire de patchs normaux et calcul de heatmap d'anomalie.
  - **Fusion** : consolidation géométrique IoU et corrélation croisée (§7 contractuel).
  - **Similarité DTD** (`models/similarity/similarity_v1`) : classification de texture et plus proches voisins.
- **Base de données** : MongoDB local (`weaveguard`), stockage sur disque des images et heatmaps dans `backend/storage/`.
- **Sécurité** : JWT HS256, hachage Argon2, RBAC strict sur 5 rôles (`operator`, `supervisor`, `admin`, `ml_engineer`, `auditor`), traçabilité réflexive d'audit.

---

## Démarrage rapide (Docker — recommandé, toutes plateformes)

```bash
cp .env.docker.example .env.docker
python backend/scripts/generate_secret.py        # copier la valeur dans JWT_SECRET (.env.docker)
docker compose up --build -d                     # MongoDB + API sur http://127.0.0.1:8000
docker compose exec app python backend/scripts/seed_demo.py --db weaveguard --count 12
cd frontend && npm install && npm run dev        # interface sur http://localhost:5173
```

Les mots de passe des comptes `demo_*` sont générés aléatoirement et affichés par le script de peuplement.
Ouvrez l'interface avec le **même nom d'hôte** que l'API (`localhost` des deux côtés) : l'authentification repose sur un cookie `httpOnly`.

Qualité : `npm run lint`, `npx tsc -b`, `npm test` (frontend), `npm run test:e2e` (Playwright), `pytest backend/tests` (backend).
L'intégration continue (`.github/workflows/ci.yml`) exécute l'ensemble. Voir aussi `docs/LFS_MIGRATION.md` pour alléger le dépôt.

---

## Démarrer pour une Démonstration (Windows, sans Docker)


### 1. Prérequis
- Système d'exploitation : Windows 10/11 (x64)
- Python 3.12 installé dans l'environnement virtuel local : `backend/.venv`
- Service MongoDB local actif (port standard `127.0.0.1:27017`)

### 2. Peuplement des Données de Démonstration
Pour initialiser la base `weaveguard` avec un jeu de 12 inspections réelles issues des images de validation, les heatmaps et des revues humaines simulées :

```powershell
$env:PYTHONPATH = "backend"
.\backend\.venv\Scripts\python.exe backend/scripts/seed_demo.py --db weaveguard --count 12
```

> **Comptes de démonstration créés** :
> - `demo_operator` (rôle : `operator`)
> - `demo_supervisor` (rôle : `supervisor`)
> - `demo_ml_engineer` (rôle : `ml_engineer`)
> - `demo_auditor` (rôle : `auditor`)
> - `demo_admin` (rôle : `admin`)
>
> *Remarque de sécurité* : Les mots de passe sont générés aléatoirement lors du premier lancement de l'initialisation et affichés sur la console terminale. Pour définir ou réinitialiser un compte administrateur interactif, utilisez `.\backend\.venv\Scripts\python.exe backend/scripts/create_admin.py`.

### 3. Lancement du Serveur de Démonstration

Exécutez le script PowerShell dédié qui teste automatiquement MongoDB avant de démarrer FastAPI :

```powershell
.\scripts\start_dev.ps1
```

Le script démarre `uvicorn` (sans `--reload` pour une stabilité maximale des modèles en mémoire) :
- **Documentation interactive Swagger** : [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Vérification de santé (Health Check)** : [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## Commandes d'Exploitation & Maintenance

### Tests Automatisés
```powershell
# Exécution de la suite complète de tests unitaires et d'intégration (hors tests lents IA)
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -v

# Exécution incluant les tests lents de reproductibilité des moteurs IA réels
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -v -m slow
```

### Export de la Spécification OpenAPI
```powershell
$env:PYTHONPATH = "backend"
.\backend\.venv\Scripts\python.exe scripts/export_openapi.py
```
Le schéma OpenAPI à jour est généré dans `docs/openapi.json`.

### Sauvegarde et Restauration Complète
```powershell
# Sauvegarde locale (base MongoDB + stockage disque des images/heatmaps)
.\scripts\backup.ps1 -Db weaveguard

# Restauration complète depuis une archive zip horodatée
.\scripts\restore.ps1 -Archive <chemin_archive.zip> -Db weaveguard
```

### Rétention et Purge des Données
```powershell
# Simulation (dry-run par défaut)
$env:PYTHONPATH = "backend"
.\backend\.venv\Scripts\python.exe backend/scripts/purge_retention.py --days 90

# Application effective avec consignation dans le journal d'audit
.\backend\.venv\Scripts\python.exe backend/scripts/purge_retention.py --days 90 --apply
```

