# Mesures de Performance Initiales (Baseline) — WeaveGuard AI (WP0)

Date : 2026-11-07  
Machine cible : 12 cœurs logiques CPU, 32 Go RAM, Windows, Python 3.12, PyTorch 2.13.0+cpu.

Ce document consigne les mesures réelles avant toute tentative d'optimisation (règle « mesurer avant, mesurer après »).  
Chaque mesure est issue de l'exécution de `scripts/benchmark.py` sur les 20 premières images de validation (`datasets/images/val`) après 2 passes de warmup.

---

## 1. Latence par Moteur d'Inférence (Médiane & p95 sur 20 images val)

| Moteur | Prétraitement | Modèle | Post-traitement | **TOTAL Médian** | TOTAL p95 | Peak RSS | Threads |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **YOLO v8n_640** | 0.00 ms | 107.94 ms | 0.19 ms | **108.17 ms** | 348.46 ms | 415.7 Mo | 8 / 12 |
| **PatchCore v1** | 29.05 ms | 3 501.14 ms | 34.29 ms | **3 564.12 ms** | 4 593.70 ms | 1 745.5 Mo | 8 / 12 |
| **Similarité v1** (WG + DTD) | 13.78 ms | 214.09 ms | 6.93 ms | **251.11 ms** | 340.44 ms | 658.2 Mo | 8 / 12 |

> **Constat** : Le modèle PatchCore (recherche des plus proches voisins sur 40 960 vecteurs de 1 024 dimensions) représente **90.8 %** du temps total de calcul de la chaîne complète. C'est la priorité n°1 pour les optimisations CPU.

---

## 2. Empreinte Mémoire & Stockage

- **Consommation RAM Crête (PatchCore actif)** : **1 745.5 Mo** (charge de la banque de mémoire 40 960 × 1 024 float32 + activations WideResNet50_2).
- **Consommation RAM YOLO seul** : **415.7 Mo**.
- **Taille de l'image Docker `vpo-app`** : **605.9 Mo** (0.59 Go).
- **Bundle Frontend compilé** : **272.2 Ko** (JS) / **30.6 Ko** (CSS).

---

## 3. Métriques de Référence à Préserver (Inviolables)

Mesurées sur les 162 images de validation de `datasets/images/val` :

- Rappel YOLO seul : **0.766** (147 / 192 boîtes GT)
- Rappel PatchCore seul (souple $\ge 10\,\%$ de la boîte) : **0.427** (82 / 192 boîtes GT)
- Rappel Union souple : **0.797** (153 / 192 boîtes GT)
- Régions PatchCore seules / image : **0.401** (65 régions orphelines sur 162 images)
- Écart absolu : **0.000** sur tous les critères par rapport à `fusion_spec.json`.

---

## 4. Commande de Reproduction

```powershell
cd c:\Users\zaidh\Desktop\VPO
backend\.venv\Scripts\python.exe scripts/benchmark.py --images 20 --warmup 2 --output docs/perf_baseline.json
```

