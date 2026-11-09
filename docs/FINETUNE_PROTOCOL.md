# Protocole Expérimental de Fine-Tuning Supervisé (WP5) — WeaveGuard AI

Ce protocole formalise la démarche d'adaptation supervisée du modèle YOLO (`weaveguard_yolo_v1`) pour intégrer de nouvelles classes de défauts ou spécialiser le modèle sur de nouveaux contextes textiles (ex : maille, tricot), conformément aux exigences méthodologiques NFR-02 et NFR-12.

---

## 1. Principes Directeurs et Gardes-Fous

1. **Isolation stricte** :
   - Les répertoires `models/` et `datasets/` restent **en lecture seule absolue**.
   - Tout modèle candidat issu du fine-tuning doit être enregistré sous `candidates/models/` et rester **désactivé par défaut**.
2. **Préservation du test set** :
   - Le jeu `datasets/images/test` ne doit **jamais** être utilisé lors de l'entraînement ou du réglage des hyperparamètres.
   - Les décisions d'acceptation d'un candidat se basent exclusivement sur le jeu de validation (`datasets/images/val`).
3. **Non-régression des rappels de référence** :
   - Le rappel YOLO sur les classes existantes ne doit pas chuter de plus de **0.02** par rapport au baseline (0.766).
   - L'union souple avec PatchCore doit conserver un rappel $\ge 0.797$ sur `val`.

---

## 2. Procédure d'Exécution

### Étape 1 : Préparation du Dataset
Exécuter le script de packaging qui génère la configuration `data.yaml` sans dupliquer inutilement les fichiers :

```powershell
cd c:\Users\zaidh\Desktop\VPO
backend\.venv\Scripts\python.exe scripts/prepare_finetune_dataset.py --output candidates/finetune_data
```

### Étape 2 : Entraînement avec Gel du Backbone
Pour éviter l'oubli catastrophique des caractéristiques géométriques et textures textiles :
- Modèle de départ : `models/weaveguard_yolo_v1/best.pt`
- Résolution nominale : `imgsz=640`
- Gel des couches initiales (Backbone gelé) : `freeze=10`
- Taux d'apprentissage : `lr0=0.001`, `lrf=0.01` (Cos decay)
- Optimiseur : `AdamW` avec `weight_decay=0.0005`
- Époques : 30 à 50 (avec arrêt anticipé `patience=10`)

Commande d'exemple Ultralytics :
```powershell
yolo detect train data=candidates/finetune_data/data.yaml model=models/weaveguard_yolo_v1/best.pt epochs=30 imgsz=640 freeze=10 project=candidates/models name=yolo_candidate_v2
```

### Étape 3 : Évaluation de Non-Régression
1. Exécuter `scripts/reproduce_metrics.py` avec le modèle candidat.
2. Vérifier les critères d'acceptation :
   - Rappel global $\ge 0.766 \pm 0.03$
   - Taux de faux positifs par image $\le 0.25$
3. Si le candidat surpasse le modèle de référence, soumettre la demande de bascule d'artefact documentée dans `docs/DECISIONS.md`.

