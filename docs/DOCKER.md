# WeaveGuard AI — Guide de Déploiement et d'Exécution Docker

Ce document décrit le packaging Docker de l'application WeaveGuard AI (Backend FastAPI + Frontend React compilé + Base de données MongoDB). Il permet de tester l'intégralité du système sur une machine hôte en **une seule commande**.

---

## 1. Prérequis Système

- **Système d'exploitation** : Windows 10/11 avec **Docker Desktop** (moteur WSL 2 recommandé).
- **Ressources allouées à Docker** :
  - **RAM** : 6 Go minimum (15 Go détectés et validés lors des benchmarks).
  - **CPU** : 4 cœurs minimum.
- **Ports locaux requis** :
  - `127.0.0.1:8000` libre sur la machine hôte.
  - Le port MongoDB `27017` **n'est pas publié sur l'hôte** (réseau Docker privé isolé), il n'entre donc pas en conflit avec une instance locale de MongoDB.

---

## 2. Configuration Initiale

Le fichier `.env.docker` contient les paramètres nécessaires à l'environnement conteneurisé. Un fichier d'exemple est versionné sous [`.env.docker.example`](file:///C:/Users/zaidh/Desktop/VPO/.env.docker.example).

Si `.env.docker` n'existe pas, initialisez-le :
```powershell
Copy-Item .env.docker.example .env.docker
```
Générez une clé secrète JWT HS256 valide (au moins 32 caractères hexadécimaux) :
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```
Puis renseignez la valeur obtenue dans le champ `JWT_SECRET` de `.env.docker`.

---

## 3. Lancement en Une Commande

Pour compiler le frontend, construire les images Docker et démarrer tous les services en arrière-plan :

```powershell
docker compose up -d
```

### Vérifier l'état de santé des conteneurs
```powershell
docker compose ps
```
Les conteneurs `weaveguard_app` et `weaveguard_mongo` doivent afficher le statut `(healthy)`.

### Accès à l'application
- **Interface Web React (Frontend unifié)** : [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Documentation OpenAPI / Swagger** : [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Sonde de santé (Health Check)** : [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 4. Initialisation des Données et Comptes

### 4.1 Création d'un compte Administrateur
```powershell
docker compose exec app python scripts/create_admin.py --username admin --password "VotreMotDePasse123!"
```

### 4.2 Peuplement du jeu de données de démonstration
Génère les comptes de démonstration (`demo_operator`, `demo_supervisor`, `demo_admin`, etc.) ainsi que 12 inspections traitées par les moteurs IA :
```powershell
docker compose exec app python scripts/seed_demo.py --count 12
```

---

## 5. Commandes de Validation et Tests

### 5.1 Smoke Test End-to-End
Exécute le pipeline complet (authentification, upload, inférence YOLO + PatchCore, overlay, heatmap, export contractuel validé par fastjsonschema et auto-nettoyage) :
```powershell
$env:SMOKE_PASSWORD = "VotreMotDePasse123!"; python backend/scripts/smoke_test_api.py --base-url http://127.0.0.1:8000
```

### 5.2 Exécution de la suite de tests automatisés (Profil `test`)
Lance les 60 tests unitaires et d'intégration dans un conteneur dédié contre une base de données isolée `weaveguard_test` :
```powershell
docker compose --profile test run --rm tests
```

### 5.3 Reproduction des métriques IA sur les images de validation
```powershell
docker compose exec app python scripts/reproduce_metrics.py --limit 20
```

---

## 6. Architecture et Sécurité du Packaging

1. **Multi-Stage Build** :
   - Étage 1 `frontend-build` (`node:22-bookworm-slim`) : installe les dépendances via `npm ci` et génère le bundle de production `dist/`.
   - Étage 2 `runtime` (`python:3.12-slim-bookworm`) : installe les roues PyTorch CPU officielles (`torch==2.13.0+cpu`, `torchvision==0.28.0+cpu`) et sert à la fois l'API FastAPI et les fichiers statiques React avec routage SPA fallback.
   - Étage 3 `test` : installe `pytest`, `pytest-asyncio` et `httpx` pour exécuter la suite de tests conteneurisée.

2. **Sécurité & Isolation** :
   - **Utilisateur non-root** : L'application s'exécute sous `weaveguard` (`uid=10001, gid=10001`).
   - **Montages en lecture seule (`:ro`)** : Les répertoires volumineux (`models/`, `datasets/`, `data/images`) sont montés en lecture seule depuis l'hôte et ne sont jamais modifiables depuis le conteneur.
   - **Liaison réseau stricte** : Le port 8000 est lié exclusivement à `127.0.0.1` (jamais `0.0.0.0` sur l'hôte).
   - **Aucun secret dans l'image** : `.env.docker` est exclu via `.dockerignore` et injecté dynamiquement au runtime par Compose.

3. **Persistance des Volumes** :
   - `weaveguard_mongo_data` : Conserve la base de données MongoDB entre les redémarrages.
   - `weaveguard_storage` : Conserve les artefacts générés (images annotées, heatmaps, vignettes).

---

## 7. Arrêt et Réinitialisation

### Arrêter les conteneurs sans perdre les données
```powershell
docker compose down
```

### Réinitialiser complètement l'environnement (efface les volumes de données)
```powershell
docker compose down -v
```

