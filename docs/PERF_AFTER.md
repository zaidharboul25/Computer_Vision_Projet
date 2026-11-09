# Bilan Comparatif des Performances — WeaveGuard AI (Après Optimisation)

Date : 2026-11-07  
Machine cible : 12 cœurs logiques CPU, 32 Go RAM, Windows, Python 3.12, PyTorch 2.13.0+cpu.

Ce document consigne la comparaison rigoureuse **Avant / Après** conformément à la méthodologie contractuelle (« Mesurer avant, mesurer après, avec commandes de reproduction »).

---

## 1. Tableau Comparatif Synthétique

| Métrique | Baseline (Avant) | Après Optimisation | Gain / Évolution | Statut |
|---|:---:|:---:|:---:|:---:|
| **YOLO v8n_640 (Médiane totale)** | 108.17 ms | **101.06 ms** | **-7.11 ms (-6.6 %)** | Exact ✓ (IoU $\ge 0.99$) |
| **YOLO v8n_640 (p95 total)** | 348.46 ms | **315.22 ms** | **-33.24 ms (-9.5 %)** | Exact ✓ |
| **Threads CPU PyTorch** | 6 (auto) | **8 (calibré)** | **Optimal sur 12 cœurs** | Validé par bench 2/4/6/8/12 |
| **Mode d'exécution PyTorch** | `no_grad()` | **`inference_mode()`** | Désactivation tracking | Exact ✓ |
| **Warmup au démarrage** | Absent (cold start) | **Actif (`main.py`)** | 0 latence première requête | Zéro régression |
| **Bundle Frontend (App JS)** | 278.75 Ko | **73.93 Ko** | **-73.5 % (gain TTI)** | Découpage vendor |
| **Bundle Vendor (cache permanent)** | Inexistant (1 fichier) | **204.81 Ko** | Cache HTTP pérenne | Validé (17 tests) |
| **Parité des Sorties IA (50 val)** | N/A (créé) | **152 / 152 passés** | Parité stricte 100% | Validé ✓ |
| **Reproduction Rappels Validation** | 0.766 / 0.427 / 0.797 | **0.766 / 0.427 / 0.797** | **Écart absolu 0.000** | Strictement inchangé |

---

## 2. Détail des Optimisations Exactes Déployées

### A. Passage sous `torch.inference_mode()`
- **Composants concernés** : `PatchCoreEngine.extractor`, `PatchCoreEngine._nn_dist`, `SimilarityEngine.embedder`.
- **Validation** : 152 tests de parité passés sur 50 images de validation (IoU $\ge 0.99$, écarts de scores $\le 10^{-3}$, cosinus d'embeddings $\ge 0.9999$).

### B. Calibrage du Parallélisme CPU (`TORCH_NUM_THREADS = 8`)
- Benchmark comparatif exécuté sur 2, 4, 6, 8 et 12 threads.
- Résultat : 8 threads fournit le meilleur compromis latence/débit sans saturation des bus mémoire (gain de 11 % face à 4 threads).
- Consigné dans `config.py`, `.env.example` et `.env.docker`.

### C. Échauffement Initial au Démarrage (`main.py`)
- Initialisation factice en tâche d'arrière-plan dès le lancement de FastAPI.
- Élimine le délai de compilation JIT et d'allocation mémoire lors de la première inspection soumise par un opérateur.

### D. Découpage du Bundle Frontend (Code-Splitting Vite)
- Séparation de la bibliothèque d'exécution (`vendor`: React, TanStack Query, React Router) du code métier de l'application.
- Le fichier JavaScript applicatif téléchargé à chaque mise à jour passe de 278 Ko à **74 Ko** (17.7 Ko compressé gzip).

---

## 3. Outils et Harnais Livrés

| Script / Outil | Emplacement | Fonction |
|---|---|---|
| **Benchmark Reproductible** | `scripts/benchmark.py` | Mesure continue des latences, p95, RSS, Docker et frontend. |
| **Harnais d'Évaluation Externe** | `scripts/eval_external.py` | Évaluation sur jeu externe (`data/external_test/`) sans toucher au jeu de test. |
| **Dataset Fine-Tuning** | `scripts/prepare_finetune_dataset.py` | Préparation automatisée du dataset YOLO dans `candidates/finetune_data/`. |
| **Protocole Expérimental** | `docs/FINETUNE_PROTOCOL.md` | Guide complet pour entraîner un nouveau modèle en évitant l'oubli catastrophique. |
| **Suite de Parité** | `tests/parity/` | 152 tests automatisés gelés sur 50 clichés de validation. |

---

## 4. Conformité aux Règles

- **`models/`, `datasets/`, `data/`, `notebooks/`** : Aucun fichier modifié (intégrité SHA-256 intacte).
- **Jeu de test (`datasets/images/test`)** : Jamais consulté ni utilisé.
- **Suite de tests backend** : 70 passed.
- **Suite de tests frontend** : 17 passed.

