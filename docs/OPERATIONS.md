# Manuel d'Exploitation & d'Administration — WeaveGuard AI

Ce document détaille les procédures opérationnelles pour démarrer, exploiter, sauvegarder, restaurer et maintenir la plateforme WeaveGuard AI en environnement Windows local (§14).

---

## 1. Démarrage et Arrêt du Serveur

### 1.1 Prérequis
- **OS** : Windows 10/11 64-bit
- **Python** : 3.12 (environnement virtuel `backend/.venv`)
- **Base de données** : MongoDB Community Server 7.0+ actif sur `localhost:27017`
- **Artefacts IA** : Présents et intègres dans le dossier `models/` (vérifiés automatiquement par SHA-256)

### 1.2 Démarrage en Production / Validation Locale
Pour lancer le serveur FastAPI sans rechargement à chaud (mode stable) :

```powershell
# Depuis la racine du dépôt (VPO)
& .\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

### 1.3 Arrêt Propre
- Envoyer le signal d'interruption `Ctrl+C` dans le terminal PowerShell.
- Le cycle `lifespan` de FastAPI :
  1. Attend la fin des tâches en cours dans la file séquentielle `inspection_worker`.
  2. Ferme proprement le pool de connexions `AsyncMongoClient`.
  3. Consigne l'arrêt dans les logs structurés JSON.

---

## 2. Surveillance & Contrôles de Santé

### 2.1 Endpoint de Santé Publique
```http
GET http://127.0.0.1:8000/health
```
- Réponse `HTTP 200 OK` si MongoDB et tous les artefacts IA sont intègres.
- Réponse `HTTP 503 Service Unavailable` si MongoDB est hors service (le serveur reste joignable en mode dégradé).
- **Règle de sécurité** : Aucun secret, chemin absolu d'infrastructure ou chaîne de connexion n'est divulgué dans ce rapport.

### 2.2 Surveillance des Moteurs IA
```http
GET http://127.0.0.1:8000/api/v1/models
Authorization: Bearer <token>
```
Expose les empreintes SHA-256 effectives, les paramètres d'inférence et le statut de chargement de chaque moteur.

---

## 3. Procédure de Sauvegarde & Restauration

> [!WARNING]
> **Confidentialité & Sécurité des Données Sauvegardées** :
> Les sauvegardes contiennent les empreintes de hachage de mots de passe (`password_hash`), les journaux d'audit et les images industrielles stockées. L'accès au répertoire de sauvegarde doit être strictement restreint aux administrateurs habilités. **Ne jamais partager ces archives, ne jamais les téléverser sur des dépôts publics ou non autorisés, et ne jamais les commiter dans Git.**

### 3.1 Sauvegarde Complète (MongoDB + Stockage)
Le script PowerShell automatise la sauvegarde des collections MongoDB au format BSON / JSON Util (préservation intégrale des dates ISO et identifiants UUID) ainsi que des fichiers d'inspection (`backend/storage`) :

```powershell
# Sauvegarde de la base principale 'weaveguard' vers le dossier 'backups/'
.\scripts\backup.ps1

# Options avancées :
# Spécifier une autre base : .\scripts\backup.ps1 -Db weaveguard_test
# Exclure le stockage lourd : .\scripts\backup.ps1 -NoStorage
# Spécifier un dossier cible : .\scripts\backup.ps1 -Out D:\ArchivesWeaveGuard
```

Structure d'une archive créée :
```text
backups/backup_weaveguard_20261102_173000/
├── manifest.json         # Horodatage, source, décomptes par collection
├── mongo/
│   ├── users.json
│   ├── inspections.json
│   ├── regions.json
│   ├── feedback.json
│   └── audit_log.json
└── storage/              # Arborescence originale des images et visualisations
    └── inspections/
        └── <uuid>/
            ├── original.png
            ├── heatmap.png
            ├── overlay.png
            └── raw_map.npy
```

### 3.2 Restauration
Pour restaurer une sauvegarde vers une base de destination :

```powershell
# Restauration dans une base de recette ou principale
.\scripts\restore.ps1 -BackupDir .\backups\backup_weaveguard_20261102_173000 -TargetDb weaveguard -RestoreStorage
```
- Le script valide au document près la conformité avec `manifest.json`.
- En cas de divergence de décompte, la procédure s'interrompt en levant une erreur explicite.

---

## 4. Politique de Rétention et Purge

Conformément à l'exigence §12, les inspections anciennes peuvent être archivées puis purgées périodiquement.

### 4.1 Simulation Sécurisée (Dry-Run)
Par défaut, le script s'exécute en mode simulation et ne modifie aucune donnée :

```powershell
& .\backend\.venv\Scripts\python.exe backend/scripts/purge_retention.py --days 90
```

### 4.2 Application Réelle
Pour exécuter la suppression effective des inspections, régions, revues et dossiers disque :

```powershell
& .\backend\.venv\Scripts\python.exe backend/scripts/purge_retention.py --days 90 --apply
```
- Tout passage de la purge consigne automatiquement un enregistrement d'audit `action="retention_purged"`.

---

## 5. Gestion des Données de Démonstration

Pour les présentations, tests d'acceptation et formation des opérateurs :

### 5.1 Peuplement Automatique (Inférence Réelle)
Traite jusqu'à 12 images de validation (`datasets/images/val`) avec les vrais modèles IA et simule des revues d'opérateurs :

```powershell
& .\backend\.venv\Scripts\python.exe backend/scripts/seed_demo.py --count 12
```
- Toutes les entrées portent `is_demo: true` et peuvent être exclues du tableau de bord via `include_demo=false`.

### 5.2 Purge Intégrale de la Démo
Pour nettoyer complètement les données de démonstration sans impacter les inspections réelles :

```powershell
& .\backend\.venv\Scripts\python.exe backend/scripts/seed_demo.py --purge
```

---

## 6. Gestion du Mode Dégradé & Continuité

### 6.1 Indisponibilité de MongoDB
- Si MongoDB s'arrête ou n'est pas joignable au lancement, le serveur démarre en **mode dégradé**.
- Les routes nécessitant la base de données renvoient immédiatement `HTTP 503 DATABASE_UNAVAILABLE`.
- Dès rétablissement de MongoDB, les connexions reprennent automatiquement sans exiger de redémarrage de l'API.

### 6.2 Reprise après Redémarrage Brutal (Coupure de Courant / Crash Serveur)
- Au démarrage du worker d'inspection, la méthode `cleanup_orphan_inspections()` s'exécute automatiquement.
- Toute inspection restée bloquée à l'état `pending` ou `running` est immédiatement basculée à l'état `error` avec le message contractuel :
  `"interrompue par un redémarrage"`
  évitant ainsi que des inspections fantômes ne bloquent l'interface utilisateur.

---

## 7. Procédure de Rollback ou Mise à Jour d'un Modèle IA

1. **Sauvegarde de l'ancien modèle** : Conserver le dossier dans `models/<engine>/<version_precedente>`.
2. **Déploiement du nouveau modèle** :
   - Déposer les artefacts dans `models/<engine>/<nouvelle_version>`.
   - Calculer leurs empreintes SHA-256 :
     ```powershell
     Get-FileHash -Algorithm SHA256 models/<chemin_fichier>
     ```
   - Mettre à jour `IntegrityVerifier` dans `backend/app/engines/integrity.py` avec les nouvelles empreintes attendues.
   - Ajuster les chemins dans `backend/app/core/config.py` si les noms de répertoires changent.
3. **Validation de non-régression** :
   - Exécuter la suite de tests automatisés :
     ```powershell
     & .\backend\.venv\Scripts\python.exe -m pytest backend/tests -v
     ```
   - Lancer la reproduction des métriques de validation :
     ```powershell
     & .\backend\.venv\Scripts\python.exe backend/scripts/reproduce_metrics.py
     ```
4. **Rollback immédiat en cas d'anomalie** :
   - Rétablir les chemins et les hachages SHA-256 dans `integrity.py` et `config.py`.
   - Redémarrer le processus uvicorn. Le contrôle d'intégrité garantit que le modèle précédent est validé au chargement.

