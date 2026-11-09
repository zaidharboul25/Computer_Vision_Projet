# Registre des Décisions d'Architecture (ADR) — WeaveGuard AI

Ce document consigne les choix techniques, les arbitrages d'ingénierie et les raisons associées, conformément à la section 0 du cahier des charges.

---

## ADR-01 : Utilisation de `AsyncMongoClient` natif de PyMongo (version 4.17+)
* **Contexte** : Motor est déprécié au profit du support asynchrone officiel introduit dans PyMongo. Le cahier des charges demandait de vérifier si l'API asynchrone était disponible sous Python 3.12.
* **Décision** : Utiliser `from pymongo import AsyncMongoClient` directement dans toute l'application.
* **Conséquences** : Code moderne, haute performance asynchrone, aucune dépendance obsolète (Motor), intégration native avec asyncio et FastAPI.

---

## ADR-02 : Prise en compte de la VRAM GPU réelle (4 Go) et inférence CPU par défaut
* **Contexte** : La machine cible dispose physiquement d'une NVIDIA GeForce GTX 1050 avec 4 096 Mo (4 Go) de VRAM (compute capability 6.1, sm_61). Cependant, aucune roue CUDA n'a été testée sur cette machine ; l'inférence CPU est utilisée.
* **Décision** :
  - Le code reste rigoureusement agnostique du matériel (`DEVICE=auto|cpu|cuda`, aucun `.cuda()` en dur, aucun test n'exigeant de GPU).
  - Exécution CPU en float32, chargement séquentiel d'un seul modèle actif à la fois, recherche du plus proche voisin PatchCore par blocs bornés (`chunk=4096`).
  - Nombre de threads CPU configurable via la variable d'environnement `TORCH_NUM_THREADS`.
  - Aucune modification de seuil, de paramètres YOLO ou de taille de banque PatchCore pour "gagner en vitesse" : les résultats doivent être strictement conformes aux spécifications.
  - Documentation de la procédure d'essai GPU ultérieur dans `docs/GPU_OPTIONAL.md`.
* **Conséquences** : Portabilité totale, stabilité sans risque de plantage pilote, respect absolu des seuils calibrés.

---

## ADR-03 : Périmètre strict des sources de données et modèles autorisés
* **Contexte** : Le dépôt comporte des répertoires d'expérimentation et d'anciens jeux de données (`data/BDFD9`, `data/hole_detection`, `models/yolo/`).
* **Décision** : Déclarer ces dossiers comme strictement hors périmètre pour le backend.
* **Sources autorisées** :
  - `models/weaveguard_yolo_v1`
  - `models/patchcore/patchcore_v1`
  - `models/similarity/similarity_v1`
  - `models/fusion/fusion_v1`
  - `models/domain_bias_report_v1.json`
  - `data/images` (DTD, 47 catégories)
  - `datasets/` (WeaveGuard v2)
* **Conséquences** : Aucune pollution par des artefacts non validés ou des dossiers temporaires d'entraînement.

---

## ADR-04 : Format contractuel des erreurs et corrélation de bout en bout
* **Contexte** : L'API doit garantir qu'aucune trace interne (stacktrace) ni aucun secret ou chemin local n'est exposé au client, tout en permettant le débogage.
* **Décision** : Middleware `CorrelationIdMiddleware` injectant systématiquement `X-Correlation-ID` et un format d'erreur unique :
  ```json
  {
    "error": {
      "code": "...",
      "message": "...",
      "correlation_id": "...",
      "details": {}
    }
  }
  ```
* **Conséquences** : Respect strict du contrat d'interface et traçabilité immédiate dans les logs structurés.

---

## ADR-05 : Hachage de mot de passe Argon2 et protection contre le brute-force
* **Contexte** : Le cahier des charges exige Argon2 pour les mots de passe et un verrouillage temporaire après N tentatives infructueuses.
* **Décision** :
  - Bibliothèque `argon2-cffi`.
  - Politique de mot de passe renforcée : 12 caractères minimum requis lors de la création d'administrateur.
  - Seuil fixé à 5 tentatives infructueuses consécutives, entraînant un verrouillage temporaire de 15 minutes (`LOCKOUT_MINUTES=15`).
* **Conséquences** : Sécurité conforme aux standards cryptographiques actuels.

---

## ADR-06 : Enforce de l'algorithme JWT HS256 à la validation
* **Contexte** : Prévenir les attaques de type substitution d'algorithme (ex: algorithme `none` ou substitution asymétrique RSA/HMAC).
* **Décision** : Dans `decode_access_token`, l'algorithme est explicitement restreint via `algorithms=[settings.JWT_ALGORITHM]` (`HS256`). Tout jeton signé avec un autre algorithme ou non signé est immédiatement rejeté par `PyJWT`.
* **Conséquences** : Intégrité stricte des jetons d'authentification.

---

## ADR-07 : Égalité des messages d'erreur d'authentification (Anti-Enumération)
* **Contexte** : Prévenir l'énumération des noms d'utilisateurs par analyse des messages d'erreur ou des codes HTTP.
* **Décision** : Renvoyer strictement le même message : `"Identifiant ou mot de passe incorrect"` avec le code d'erreur `UNAUTHENTICATED` (HTTP 401), qu'il s'agisse d'un utilisateur inexistant ou d'un mot de passe incorrect.
* **Conséquences** : Un attaquant ne peut pas déduire la présence d'un compte sur le serveur.

---

## ADR-08 : Persistance du compteur de verrouillage dans MongoDB
* **Contexte** : Éviter qu'un redémarrage du serveur ou une instanciation multi-processus ne réinitialise les compteurs de tentatives infructueuses.
* **Décision** : Les champs `failed_attempts` et `locked_until` (horodatage ISO 8601 UTC) sont persistés directement dans le document utilisateur au sein de la collection MongoDB `users`. La durée de verrouillage est de 15 minutes à compter de la 5ème tentative échouée.
* **Conséquences** : État de sécurité persistant et résilient aux redémarrages.

---

## ADR-09 : Traçabilité complète des événements d'authentification dans l'Audit Log
* **Contexte** : Exigence contractuelle de traçabilité des opérations de sécurité sans exposer de secrets.
* **Décision** : Journalisation systématique dans la collection MongoDB `audit_log` des événements :
  - `login_success` (user_id, username, rôle) ;
  - `login_failure` (nom d'utilisateur, motif anonymisé : `unknown_user` ou `bad_password`) ;
  - `account_locked` (user_id, username, durée du verrou) ;
  - `user_created` (nom de l'utilisateur créé, rôle, administrateur auteur) ;
  - `user_updated` (champs modifiés, administrateur auteur).
* **Conséquences** : Auditabilité complète et conformité avec les exigences de sécurité §10 et §12 du cahier des charges.

---

## ADR-10 : Tolérance de reproduction des métriques ML ($\pm 0.03$)
* **Contexte** : Le script de reproduction de la validation compare les rappels mesurés par les moteurs backend sur les 162 images de validation WeaveGuard v2 avec les chiffres de référence de `fusion_spec.json`.
* **Décision** : Fixer une tolérance maximale de $\pm 0.03$ (3 points de pourcentage) sur les rappels (YOLO seul, PatchCore seul souple, Union souple). Cette marge couvre les légères différences d'implémentation de redimensionnement bilinéaire (Pillow vs torchvision) et les arrondis de coordonnées de boîtes englobantes sans altérer la fidélité méthodologique.
* **Conséquences** : Détection immédiate de toute régression de prétraitement ou de seuil, tout en évitant les faux négatifs de test liés aux arrondis de virgule flottante.

---

## ADR-11 : Mesures de Latence CPU de Référence (Phase 2)
* **Contexte** : NFR-01 impose de mesurer la latence sur le matériel cible en découpant le prétraitement, le modèle et le post-traitement.
* **Mesure** : Évaluée sur 5 images représentatives du split de validation (`datasets/images/val`), valeur médiane en millisecondes (CPU hôte Windows, Python 3.12, PyTorch CPU float32) :

| Moteur | Prétraitement | Modèle | Post-traitement | TOTAL Médian |
| :--- | :---: | :---: | :---: | :---: |
| **YOLO v8n_640** | 0.00 ms | 91.04 ms | 0.12 ms | **91.13 ms** |
| **PatchCore v1** | 31.87 ms | 2 767.27 ms | 22.19 ms | **2 823.91 ms** |
| **Similarité v1** (WG + DTD) | 9.98 ms | 211.04 ms | 6.26 ms | **225.17 ms** |

* **Observations** :
  - YOLO est très rapide sur CPU (~91 ms par image).
  - Similarité s'exécute en ~225 ms pour les deux recherches FAISS combinées.
  - PatchCore prend ~2,8 s sur CPU pour balayer les 40 960 patches de mémoire par blocs de 4 096, ce qui reste parfaitement fluide pour un traitement séquentiel en arrière-plan sans bloquer le serveur.

* **Reproduction des métriques de validation (§6)** :
  - Le script `backend/scripts/reproduce_metrics.py` réutilise exactement les classes de moteurs instanciées dans le registre backend (`YoloEngine`, `PatchCoreEngine`) et la logique de fusion contractuelle (`backend/app/engines/fusion.py`), strictement identiques à celles mobilisées par l'API.
  - Le script a été exécuté exclusivement sur les 162 images du jeu de validation (`datasets/images/val`). Le jeu de test (`datasets/images/test`) n'a **JAMAIS** été consulté ni utilisé.
  - Les résultats entiers et taux reproduisent rigoureusement les métriques de référence (`models/fusion/fusion_v1/fusion_spec.json`) :
    * Rappel YOLO seul : **0.766** (147 / 192 boîtes GT détectées)
    * Rappel PatchCore seul (souple) : **0.427** (82 / 192 boîtes GT corroborées)
    * Rappel Union souple : **0.797** (153 / 192 boîtes GT détectées par au moins un moteur)
    * Régions PatchCore seules / image : **0.401** (65 régions isolées sur 162 images)
    * Écart absolu : **0.000** sur tous les critères (tolérance contractuelle ±0.030).

---

## ADR-12 : Prétraitement d'Upload, Anti-Bombe de Décompression et Conversion RGB 8-bit (Phase 3)
* **Contexte** : FR-IMG-01 à FR-IMG-05 et Exigence C imposent de valider rigoureusement les fichiers téléchargés (vide, extension trompeuse, dimensions excessives, modes de couleur variés).
* **Décision** :
  1. Fixer `Image.MAX_IMAGE_PIXELS = settings.MAX_IMAGE_SIDE * settings.MAX_IMAGE_SIDE` (64 mégapixels). Toute image dépassant ce seuil lève `IMAGE_TOO_LARGE` (413) avant décompression complète.
  2. Conversion systématique en RGB 8-bit avec gestion explicite des canaux : fond blanc neutre pour la transparence (RGBA/LA), normalisation d'échelle pour les entiers 16/32 bits (I).
  3. Redressement de l'orientation EXIF via `ImageOps.exif_transpose` : l'image stockée est l'image orientée, et ses dimensions natives constituent le repère de référence (AC-02).
  4. Si le plus grand côté dépasse `INFERENCE_LONG_SIDE` (1448 px), l'image est redimensionnée proportionnellement pour l'inférence (`resize_factor < 1.0`), et les boîtes résultantes sont rééchelonnées vers le repère natif de l'image stockée (`[x/scale, y/scale, w/scale, h/scale]`).

---

## ADR-13 : Format et Normalisation de la Heatmap (Exigence F)
* **Contexte** : PatchCore génère une carte de score bidimensionnelle continue (float32). L'interface utilisateur requiert une visualisation spatiale standardisée et téléchargeable.
* **Décision** :
  1. La carte brute en virgule flottante est sauvegardée localement dans `storage/inspections/{id}/raw_map.npy` (non servie directement) pour permettre toute analyse quantitative ultérieure.
  2. La heatmap servie au client est un PNG 8 bits (mode 'L') normalisé selon la formule :
     `norm_map = clip((raw_map / vmax) * 255, 0, 255)` avec `vmax = max(raw_map)` (0 -> 0, vmax -> 255).
  3. Les métadonnées complètes `{scale: "raw", min, max, tau, vmax, width, height}` sont persistées et exposées dans la ressource inspection.

---

## ADR-14 : Isolation de Visibilité Multi-Tenancy (Exigence B)
* **Contexte** : Un opérateur ne doit pas avoir accès aux inspections d'un autre opérateur. Renvoyer un code `403 FORBIDDEN` révélerait à l'attaquant qu'une ressource existe sous cet identifiant.
* **Décision** :
  - Lorsqu'un utilisateur demande une ressource (`/inspections/{id}`, `/regions`, `/image`, `/heatmap`, `/overlay`, `/export`) pour laquelle il n'a pas les droits de lecture, le serveur renvoie systématiquement `404 NOT_FOUND` avec le code `INSPECTION_NOT_FOUND`.
  - Seuls les rôles `supervisor`, `admin`, `auditor` et `ml_engineer` disposent des droits de lecture transverse sur l'ensemble de l'historique d'inspection.

---

## ADR-15 : Schéma d'Export Versionné et Séparation Prédictions / Décisions (Exigence I, AC-04, AC-07)
* **Contexte** : L'export JSON de l'inspection doit être reproductible, vérifiable automatiquement par schéma et exempt de fuite de secrets ou chemins d'infrastructure.
* **Décision** :
  1. Schéma versionné formel `weaveguard.inspection/1.0` défini dans `backend/app/schemas/export_schema_v1.json` et validé à chaque export via `fastjsonschema`.
  2. Séparation étanche de la section `predictions` (résultats immuables des modèles IA) et de la section `human_reviews` (historique des validations par les opérateurs).
  3. Filtre anti-fuite analysant le document sérialisé : interdiction absolue de motifs comme `C:\`, `/home/`, `.env`, `JWT`, etc., levant une erreur `EXPORT_ERROR` (500) en cas d'anomalie.

---

## ADR-16 : Immutabilité des Régions et Historique de Revue Humaine en Ajout Seul (Phase 4, AC-07)
* **Contexte** : Pour garantir la non-répudiation et la traçabilité qualité, les prédictions des modèles IA ne doivent jamais être modifiées ni écrasées par les interventions humaines.
* **Décision** :
  1. La collection `regions` est strictement en lecture seule après insertion : aucune méthode de mise à jour (`update`) ou de suppression (`delete`) n'est exposée par `RegionRepository`. Les routes HTTP `PUT`, `PATCH`, `DELETE` sur `/api/v1/regions/{id}` renvoient `405 Method Not Allowed`.
  2. Chaque décision de validation humaine est consignée sous forme d'un document distinct dans la collection `feedback` (pattern *append-only*).
  3. La décision humaine courante d'une région est résolue dynamiquement par le document le plus récent selon l'ordre `(created_at DESC, _id DESC)`.
  4. Validation stricte des motifs de rejet : autorisés uniquement parmi `["artefact_tissage", "faux_positif_texture", "pli_tissu", "ombre_eclairage", "autre"]`. Le motif est obligatoire pour `rejected`, strictement interdit pour `confirmed`, et le commentaire est plafonné à 500 caractères.
  5. Seuls les utilisateurs avec le rôle `operator` peuvent soumettre un feedback, et uniquement sur leurs propres inspections (renvoyant `404 INSPECTION_NOT_FOUND` en cas de tentative sur l'inspection d'un tiers pour éviter la fuite d'information).

---

## ADR-17 : Formule de Normalisation de la Heatmap avec Seuil Comparatif (Correction Étape 4)
* **Contexte** : Une normalisation purement locale `vmax = max(score_map)` faisait saturer vers 255 des tissus parfaitement sains ayant un score maximal résiduel faible (ex: 1.19 pour un seuil tau=1.25), faussant la perception visuelle de l'opérateur.
* **Décision** :
  1. Adoption de la formule de borne supérieure : `vmax = max(2 * tau, float(np.max(score_map)))`.
  2. Cette calibration garantit que le seuil `tau` occupe toujours au plus la moitié de la plage dynamique (teinte froide/neutre) : une image sans anomalie reste confinée dans les teintes froides et aucun pixel ne dépasse `(tau / vmax) * 255`.
  3. Les métadonnées complètes `{scale: "raw", min, max, tau, vmax, width, height}` sont incluses dans la ressource pour permettre tout réétalonnage côté frontend.

---

## ADR-18 : Statistiques Synthétiques du Tableau de Bord Sans Métriques ML Dérivées (§14.2)
* **Contexte** : Le tableau de bord d'exploitation doit offrir une visibilité immédiate sur les volumes de production et de revue, sans induire l'utilisateur en erreur sur la performance intrinsèque des modèles.
* **Décision** :
  1. `GET /api/v1/stats/summary` n'expose **que des décomptes bruts** issus de MongoDB : total et répartition des inspections par statut (`pending`, `running`, `done`, `error`), total des régions par moteur (`yolo`, `patchcore`), total des revues par état (`confirmed`, `rejected`, `uncertain`, `unreviewed`) et 5 dernières inspections.
  2. **Aucune métrique ML** (mAP, précision, rappel, F1) n'est calculée ni inventée ici : ces métriques nécessitent une vérité terrain exhaustive issue du banc de validation et ne relèvent pas du tableau de bord temps réel d'exploitation.
  3. Paramètre `include_demo` (défaut `true`) permettant d'isoler ou d'inclure les inspections de démonstration sans polluer les agrégats réels.

---

## ADR-19 : Traçabilité Réflexive d'Audit et Procédures d'Exploitation Scriptées (§12, §14)
* **Contexte** : La conformité réglementaire textile exige une traçabilité inviolable des accès, des exports et des opérations de maintenance.
* **Décision** :
  1. La collection `audit_log` est immuable. Tout accès à l'endpoint de consultation `/api/v1/audit` consigne réflexivement un événement `action="audit_view"` dans le journal lui-même.
  2. Toute consultation d'export ML consigne un événement `action="feedback_export"`.
  3. Sauvegarde et restauration complètes scriptées en PowerShell (`scripts/backup.ps1`, `scripts/restore.ps1`) pilotant des utilitaires Python (`db_backup.py`, `db_restore.py`) basés sur `bson.json_util` (préservation 100% des types temporels et UUIDs, indépendamment de la présence de `mongodump` sur Windows).
  4. Politique de rétention des données (`purge_retention.py`) configurée par défaut en mode `dry-run` : la suppression réelle exige le drapeau explicite `--apply` et consigne un audit `retention_purged`.





---

## ADR-20 : Séquencement Déterministe des Feedbacks Concurrents par Région
* **Contexte** : Lors de soumissions simultanées de revues humaines dans la même milliseconde, l'horodatage `created_at` seul ne garantit pas un ordre d'évaluation parfaitement déterministe.
* **Décision** :
  1. Utilisation d'un compteur incrémental atomique par région dans la collection `counters` : `find_one_and_update({"_id": f"region_feedback_{region_id}"}, {"$inc": {"seq": 1}}, upsert=True)`.
  2. Chaque document `feedback` inclut son numéro de séquence `seq`.
  3. La résolution de la décision active et le tri de l'historique s'effectuent par ordre composite `seq DESC, created_at DESC, _id DESC`.
  4. Index composé dédié sur `[("region_id", ASCENDING), ("seq", DESCENDING)]`.
* **Conséquences** : Ordre strictement reproductible et insensible aux horloges concurrentes.

---

## ADR-21 : Benchmark de Performance et Couverture Indexée (IXSCAN) sur 1 000 Inspections (AC-08)
* **Contexte** : Le critère d'acceptation AC-08 impose une consultation fluide de l'historique et des statistiques sans dégradation lors de la montée en charge. Tous les filtres de recherche doivent s'appuyer sur des index MongoDB sans tri en mémoire.
* **Décision & Mesures Réelles** :
  - Évaluation réalisée sur une base locale de 1 000 inspections via `backend/scripts/benchmark_inspections.py` et `backend/tests/integration/test_phase4_performance.py`.
  - Résultat de l'analyse des plans d'exécution `explain(verbosity="executionStats")` :

| Filtre testé | Index utilisé | Plan d'exécution | Clés / Docs examinés | Latence médiane API |
| :--- | :--- | :--- | :---: | :---: |
| **Baseline (sans filtre)** | `created_at_-1` | `LIMIT -> FETCH -> IXSCAN` | 20 / 20 | **7.21 ms** |
| **Statut (`status=done`)** | `status_1_created_at_-1` | `LIMIT -> FETCH -> IXSCAN` | 20 / 20 | **7.80 ms** |
| **Utilisateur (`created_by=operator_0`)** | `created_by_1_created_at_-1` | `LIMIT -> FETCH -> IXSCAN` | 20 / 20 | **7.64 ms** |
| **Période temporelle (`date_from`)** | `created_at_-1` | `LIMIT -> FETCH -> IXSCAN` | 20 / 20 | **7.20 ms** |
| **Revue humaine (`review_status=reviewed`)** | `created_at_-1` | `LIMIT -> FETCH -> IXSCAN` | 20 / 20 | **9.88 ms** |
| **Préfixe identifiant (`id_filter=0000`)** | `created_at_-1` (ou `id_1`) | `LIMIT -> FETCH -> IXSCAN` | 77 / 77 | **7.00 ms** |
| **Synthèse agrégée (`GET /stats/summary`)** | Pipeline `$match` + `$group` | Agrégation native MongoDB | - | **12.40 ms** |

* **Constats & Validations** :
  1. Aucun tri en mémoire (`SORT stage`) n'est déclenché : le tri `created_at DESC` est directement satisfait par les index préfixés ou simples.
  2. Toutes les requêtes sont servies en moins de 10 ms sur MongoDB local, très largement en-dessous du plafond contractuel de 250 ms.


---

## ADR-22 : Contraintes de Téléversement, Rétention Scriptée et Périmètre de Similarité Frontend
* **Contexte** : Dans le cadre de l'intégration du frontend React, plusieurs frontières d'architecture doivent être formalisées pour éviter les dérives et les doublons de logique.
* **Décision** :
  1. **Contraintes d'upload sans valeurs en dur** : Le frontend ne définit aucune constante en dur pour `MAX_UPLOAD_MB` ou les extensions autorisées. Le serveur FastAPI valide les flux entrants et renvoie les erreurs contractuelles `IMAGE_TOO_LARGE` (413) et `INVALID_IMAGE` (400) avec leurs messages explicites, affichés directement à l'écran.
  2. **Périmètre de la Similarité & Backlog** : Seuls les modes formellement exposés par l'API (`POST /api/v1/similarity/search` avec upload d'image, et consultation des références) sont intégrés dans l'interface. La recherche de similarité directe par sélection d'une région découpée est consignée en **backlog** (nécessitera une route dédiée de recadrage/embedding serveur).
  3. **Rétention scriptée sans exposition HTTP** : Aucune route HTTP de purge n'est exposée afin de garantir l'intégrité réglementaire des audits et inspections. La politique de rétention demeure une tâche d'exploitation scriptée (`backend/scripts/purge_retention.py` avec audit `retention_purged`).

---

## ADR-23 : Architecture Frontend de Nouvelle Inspection & Suivi Temps Réel (Phase 2)
* **Contexte** : La soumission d'une nouvelle inspection et le suivi séquentiel de l'inférence doivent garantir la réactivité sans surcharge, l'accessibilité aux lecteurs d'écran (`aria-live`) et le respect des libellés contractuels.
* **Décisions** :
  1. **Téléversement & Découverte Dynamique des Moteurs** : La sélection des moteurs interroge dynamiquement `/health` au chargement. Aucune limitation de taille de fichier n'est codée en dur côté client : le serveur applique la validation d'intégrité et renvoie `IMAGE_TOO_LARGE` ou `INVALID_IMAGE` avec son identifiant de corrélation.
  2. **Suivi Temps Réel par Polling Adaptatif** : TanStack Query interroge `GET /api/v1/inspections/{id}` avec un `refetchInterval` de 1 000 ms tant que `status === 'pending' | 'running'`, puis coupe le polling dès que `status === 'done' | 'error'`.
  3. **Accessibilité & Télémétrie des Moteurs** : Le conteneur de progression des moteurs est annoté `aria-live="polite"` pour avertir les technologies d'assistance des transitions d'état. Les latences décomposées (`preprocess`, `model`, `postprocess`, `total`) et les versions d'artefacts sont affichées sans arrondis trompeurs.
  4. **Résultat Partiel & État Aucune Région** :
     - En cas d'échec partiel (`partial: true`), un bandeau d'alerte spécifique informe l'utilisateur que certains moteurs ont produit des résultats exploitables.
     - Lorsque `regions_count === 0`, l'interface affiche obligatoirement et textuellement : « Aucune région détectée par les moteurs exécutés » et en sous-titre « Ce résultat n'est pas une garantie d'absence de défaut » (testé unitairement).
  5. **Téléchargements Sécurisés des Fichiers Protégés** : L'export JSON (AC-04) et l'overlay PNG (AC-03) transitent par `apiFetchBlob` avec l'en-tête `Authorization: Bearer`, garantissant qu'aucun jeton n'apparaît dans les URLs.


---

## ADR-24 : Restitution Visuelle TrueType et Avertissement Descriptif Hors Domaine

* **Contexte** : Deux ajustements ergonomiques et métrologiques ont été identifiés lors des essais en conditions opérationnelles :
  1. Les caractères accentués et tirets cadratins (`é`, `è`, `à`, `—`) dans les étiquettes de l'overlay s'affichaient sous forme de rectangles de remplacement (`▯`) avec la police matricielle par défaut de Pillow.
  2. Les opérateurs sur ligne de production ont besoin d'un indicateur de confiance interprétable pour savoir si le textile inspecté s'éloigne notablement des distributions textiles observées lors de l'apprentissage (risque de dérive ou textile non documenté).

* **Décisions & Mesures Prises** :
  1. **Police TrueType Embarquée (`DejaVuSans.ttf`)** :
     - Intégration de la police libre `DejaVu Sans` dans le dépôt applicatif sous `backend/app/assets/fonts/DejaVuSans.ttf` avec sa licence (`LICENSE.txt`), garantissant son inclusion native dans l'image Docker indépendamment du système hôte.
     - Dimensionnement proportionnel dynamique à la largeur de l'image inspectée (`max(14, int(image.width * 0.018))`) assurant une lisibilité optimale sur les hautes résolutions.
     - Vérification unitaire de l'intégrité de la table de glyphes latins accentués sans aucun glyphe de substitution `.notdef`.
  2. **Indicateur de Représentativité (« Hors Domaine ») non Invasif** :
     - À chaque inspection, le plongement de l'image est extrait par ResNet-50 et sa similarité cosinus maximale avec la galerie de référence WeaveGuard est mesurée (même si le moteur de similarité n'a pas été demandé explicitement pour l'affichage des voisins).
     - Si le moteur de similarité est désactivé ou indisponible, l'état `status: "unavailable"` est consigné sans extrapolation de valeur.
     - Le seuil de référence n'est **jamais codé en dur** : il est extrait dynamiquement de `models/domain_bias_report_v1.json` (`familiarity_quantiles[0]` = minimum observé sur validation+test).
     - Si la similarité maximale est inférieure à ce minimum, l'avertissement formel est consigné dans `warnings[]` :
       *« Cette image ressemble peu aux images d'apprentissage (similarité maximale X, minimum observé en validation/test Y). Les résultats peuvent être moins fiables. »*
     - L'objet structuré `domain_check = {max_similarity, reference_min, reference_source, status}` est rattaché à l'inspection et inclus dans l'export JSON contractuel (schéma AC-04).
  3. **Nuance Métrologique Essentielle** :
     - La plage de référence documentée dans `models/domain_bias_report_v1.json` a été initialement établie sur la galerie d'entraînement seule, alors que l'index FAISS de production regroupe les ensembles `train` et `val`.
     - Par conséquent, cet indicateur est **strictement descriptif et qualitatif** (« en dehors de la plage observée lors de l'évaluation ») et ne constitue **pas un seuil de décision calibré** ni un filtre d'exclusion.
     - **Aucun résultat, boîte ou décision de moteur n'est modifié, filtré ou écarté** sur la base de cet avertissement. L'arbitrage final demeure sous la responsabilité exclusive de l'opérateur humain.


---

## ADR-25 : Optimisation de l'Inférence CPU via torch.inference_mode() et Calibrage des Threads

* **Contexte** : L'exécution sur machine hôte à processeur multi-cœur sans GPU nécessite d'éliminer toute surcharge d'autograd et de saturer de manière optimale la bande passante mémoire L3 sans goulot d'étranglement hyperthread.
* **Décisions** :
  1. Substitution de @torch.no_grad() par @torch.inference_mode() au niveau des extracteurs PatchCoreEngine et SimilarityEngine.
  2. Calibrage empirique du nombre de threads CPU (TORCH_NUM_THREADS = 8) suite au benchmark systématique (2, 4, 6, 8, 12 threads), apportant un gain de 11 % face à 4 threads sans instabilité.
  3. Échauffement initial au démarrage (main.py) via une passe factice en arrière-plan éliminant le surcoût de cold-start de la première requête utilisateur.
* **Conséquences** :
  - Parité numérique exacte prouvée sur 50 clichés de validation (152 tests de parité validés avec IoU >= 0.99 et score +- 1e-3).
  - Aucune dérive métrologique sur le banc de validation WeaveGuard v2.

---

## ADR-26 : Découpage Modulaire du Frontend (Code-Splitting Vendor)

* **Contexte** : L'interface React servie par le conteneur applicatif regroupait toutes les dépendances lourdes (React, TanStack Query, React Router) dans un unique bundle monolithique de 279 Ko rechargé à chaque build.
* **Décisions** :
  1. Configuration du découpage Rollup dans vite.config.ts via manualChunks.vendor.
  2. Isolation des bibliothèques tierces dans vendor-[hash].js (204 Ko) bénéficiant d'une mise en cache HTTP immuable dans les navigateurs.
  3. Réduction de la taille du code JavaScript métier téléversé à chaque navigation à 74 Ko (17.7 Ko compressé gzip), soit une réduction de charge de 73.5 % pour l'opérateur.
* **Conséquences** : Temps d'interactivité (TTI) diminué sur les postes d'atelier, 17 tests unitaires frontend passés avec succès.

---

## ADR-27 : Harnais d'Évaluation Externe et Sanctuaire des Jeux de Données

* **Contexte** : Les cycles d'amélioration continue et de fine-tuning imposent de tester des données inédites ou d'entraîner de nouveaux candidats sans jamais violer l'étanchéité du jeu de test officiel (datasets/images/test).
* **Décisions** :
  1. Implémentation du script scripts/eval_external.py ciblant le répertoire externe dédié data/external_test/ (ignoré par git). En l'absence de données, le script s'arrête proprement avec instructions sans erreur.
  2. Implémentation du script scripts/prepare_finetune_dataset.py et du protocole docs/FINETUNE_PROTOCOL.md orientant les nouveaux modèles candidats exclusivement dans candidates/ (ignoré par git), garantissant que le dossier de production models/ demeure strictement immuable.
* **Conséquences** : Rigueur méthodologique ML absolue, conformité NFR-02 et NFR-12.
