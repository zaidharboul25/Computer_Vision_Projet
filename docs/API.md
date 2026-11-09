# Documentation de l'API REST — WeaveGuard AI

Ce document détaille les contrats d'échange, les règles de sécurité, le cycle de vie des inspections, la gestion des erreurs et la recette frontend pour récupérer les ressources protégées (§10, AC-01 à AC-10).

---

## 1. Principes d'Authentification & Sécurité

1. **Jeton Bearer obligatoire** :
   Toutes les routes de l'API (à l'exception de `/health` et `/api/v1/auth/login`) exigent l'en-tête HTTP :
   ```http
   Authorization: Bearer <jwt_token>
   ```
2. **Interdiction stricte des jetons dans l'URL** :
   Les endpoints de fichiers (`/image`, `/heatmap`, `/overlay`, `/export` et `/similarity/ref/{ref_id}/thumbnail`) n'acceptent **JAMAIS** de jeton dans l'URL ou la chaîne de requête (query string).
3. **Recette Frontend pour l'affichage des images protégées** :
   Le frontend ne peut pas insérer directement l'URL dans une balise `<img src="...">` sans passer par un appel authentifié. Il doit récupérer le flux sous forme de Blob via `fetch` puis générer une URL locale en mémoire :

   ```javascript
   // Exemple de chargement sécurisé côté client frontend
   async function loadProtectedImage(imageUrl, token) {
     const response = await fetch(imageUrl, {
       headers: {
         'Authorization': `Bearer ${token}`
       }
     });
     if (!response.ok) {
       throw new Error(`Erreur lors du chargement (${response.status})`);
     }
     const blob = await response.blob();
     return URL.createObjectURL(blob);
   }

   // Utilisation :
   // const objectUrl = await loadProtectedImage('/api/v1/inspections/123/overlay', token);
   // imgElement.src = objectUrl;
   ```

4. **Multi-tenancy & Isolation de visibilité (Exigence B)** :
   Un utilisateur (par exemple avec le rôle `operator`) qui tente d'accéder à une inspection créée par un autre utilisateur reçoit systématiquement :
   ```http
   HTTP 404 Not Found
   ```
   avec le code d'erreur `INSPECTION_NOT_FOUND` (et **jamais** un code `403 Forbidden`). Cette règle évite toute fuite d'information sur l'existence ou l'identifiant des inspections des autres opérateurs.

---

## 2. Codes d'Erreur Contractuels

Les erreurs sont toujours retournées au format JSON structuré avec l'identifiant de corrélation `X-Correlation-ID` :

```json
{
  "error": {
    "code": "SERVER_BUSY",
    "message": "File d'attente d'inspection saturée, veuillez réessayer ultérieurement",
    "correlation_id": "c1f7a28e-4a64-4e2b-b9f1-d0b8d5a86d52",
    "details": {}
  }
}
```

| Code d'erreur | HTTP Status | Description |
| :--- | :---: | :--- |
| `UNAUTHENTICATED` | 401 | Jeton JWT manquant, invalide ou expiré |
| `FORBIDDEN` | 403 | Rôle insuffisant pour exécuter cette action d'administration |
| `INSPECTION_NOT_FOUND` | 404 | Inspection inexistante ou inaccessible à cet utilisateur |
| `REGION_NOT_FOUND` | 404 | Région d'inspection introuvable |
| `INVALID_IMAGE` | 400 | Fichier vide, corrompu, GIF animé ou format non autorisé |
| `IMAGE_TOO_LARGE` | 413 | Poids du fichier supérieur à `MAX_UPLOAD_MB` ou dimensions excessives (§10.3) |
| `SERVER_BUSY` | 503 | File d'attente de traitement séquentiel saturée (`MAX_QUEUE`) |
| `DATABASE_UNAVAILABLE` | 503 | Serveur MongoDB inaccessible |
| `MODEL_UNAVAILABLE` | 503 | Poids ou artefacts d'un moteur IA inaccessibles ou corrompus (SHA-256) |
| `INFERENCE_FAILED` | 500 | Erreur interne lors du calcul d'un moteur |
| `EXPORT_ERROR` | 500 | Erreur de schéma ou détection d'une fuite d'information sensible |

---

## 3. Endpoints de l'API

### 3.1 Authentification & Utilisateurs

- `POST /api/v1/auth/login` : Authentification et obtention du jeton Bearer (formulaire `username`, `password`).
- `GET /api/v1/auth/me` : Profil de l'utilisateur connecté.
- `GET /api/v1/users` : Liste des comptes (rôle `admin` requis).
- `POST /api/v1/users` : Création d'un compte (rôle `admin` requis).
- `PATCH /api/v1/users/{id}` : Modification d'un compte (rôle `admin` requis).

### 3.2 Inspections Textiles

- `POST /api/v1/inspections` (Multipart Form)
  - `file`: fichier image (JPEG ou PNG)
  - `engines`: chaîne optionnelle des moteurs à activer (`yolo,patchcore,similarity`)
  - `scale_mode`: mode d'échelle d'inférence (`native` par défaut, ou `normalized` expérimental). En mode `normalized`, toute image dont le grand côté est inférieur à `INFERENCE_LONG_SIDE` (1448 px) est agrandie par interpolation bicubique jusqu'à cette dimension avant inférence ; les boîtes prédites sont ramenées au repère natif de l'image stockée.
  - Réponse : `HTTP 202 Accepted` avec `{"id": "...", "status": "pending", "created_at": "..."}`.
  - Erreurs possibles : `400 INVALID_IMAGE`, `413 FILE_TOO_LARGE`, `503 SERVER_BUSY`.

- `GET /api/v1/inspections`
  - Filtres : `skip`, `limit`, `status`, `created_by`, `date_from`, `date_to`.
  - Contrôle d'accès : un opérateur ne voit que ses inspections ; superviseurs et administrateurs voient tout l'historique.

- `GET /api/v1/inspections/{id}`
  - Renvoie le statut global (`pending`, `running`, `done`, `error`), les métadonnées de l'image (dimensions natives, redressement EXIF, facteur de redimensionnement `resize_factor`, mode d'échelle `scale_mode`), les avertissements (`warnings[]` incluant l'avertissement d'échelle explicite et l'avertissement hors domaine éventuel), l'état en temps réel de chaque moteur, et l'évaluation `domain_check` (`max_similarity`, `reference_min`, `reference_source`, `status: "in_range" | "below_range" | "unavailable"`).

- `GET /api/v1/inspections/{id}/regions`
  - Liste des régions détectées, immuables.
  - Chaque région possède son identifiant technique unique `id` (UUID) et son identifiant court d'affichage déterministe `display_id` :
    * `Y1, Y2...` pour YOLO par ordre de confiance décroissante.
    * `P1, P2...` pour PatchCore par ordre de score de distance décroissant.
  - Format des boîtes : `[x, y, largeur, hauteur]` en repère natif de l'image stockée (AC-02).
  - Libellés exacts : `Défaut proposé : {classe}` (YOLO) ou `Anomalie suspectée — score de distance` (PatchCore).

- `GET /api/v1/inspections/{id}/image`
  - Renvoie l'image stockée (redressée selon l'EXIF, RGB).

- `GET /api/v1/inspections/{id}/heatmap`
  - Renvoie la carte de chaleur PatchCore normalisée au format PNG 8 bits (0 -> 0, vmax -> 255).

- `GET /api/v1/inspections/{id}/overlay`
  - Renvoie l'image annotée (AC-03) :
    * Sur l'image : badge court (`Y1`, `P1`...) posé strictement à l'intérieur du repère image (recale vers l'intérieur si boîte en bord ou coin), fond semi-opaque.
    * Tracé distinctif : trait **plein** pour YOLO, trait **pointillé** (tirets explicites) pour PatchCore. La couleur seule ne porte jamais le sens.
    * Bandeau de légende ajouté **sous** l'image (sans masquer le tissu) : une ligne détaillée par région (`[Y1] [YOLO • Trait plein] Défaut proposé : ... | Confiance`, `[P1] [PatchCore • Trait pointillé] Anomalie suspectée ...`).
  - Paramètre optionnel : `?format=png|webp|jpeg` (défaut : `png`).

- `GET /api/v1/inspections/{id}/export`
  - Export JSON validé contre `export_schema_v1.json`.
  - Contient `scale_mode` dans les métadonnées de l'image, `display_id` pour chaque région, et le bloc `domain_check`.
  - Séparation stricte entre prédictions et revues humaines.
  - Garanti sans aucun chemin local (`C:\`) ni secret (`.env`, `JWT`).

### 3.3 Régions & Revue Humaine (Phase 4)

- `POST /api/v1/regions/{id}/feedback`
  - Enregistre la validation humaine d'une région candidate.
  - **Règles contractuelles (§6.5, AC-07)** :
    * Réservé aux utilisateurs avec le rôle `operator` sur **leurs propres** inspections (403 pour autres rôles, 404 `INSPECTION_NOT_FOUND` si inspection invisible).
    * Décisions : `confirmed`, `rejected`, `uncertain`.
    * Motif (`rejection_reason`) : **obligatoire** si `rejected` (parmi `artefact_tissage`, `faux_positif_texture`, `pli_tissu`, `ombre_eclairage`, `autre`), **strictement interdit** si `confirmed` (renvoie 400 `INVALID_FEEDBACK`).
    * Commentaire optionnel (500 caractères max).
    * Historique en **ajout seul** (append-only) : la décision courante est la plus récente `(created_at DESC, _id DESC)`.

- `GET /api/v1/regions/{id}/thumbnail`
  - Télécharge la vignette recadrée de la région au format PNG.
  - Isolation multi-opérateur stricte : renvoie 404 `INSPECTION_NOT_FOUND` si l'inspection n'appartient pas à l'opérateur (jamais 403).

- `GET /api/v1/regions/{id}/history`
  - Renvoie l'historique chronologique complet des revues pour une région.

- `GET /api/v1/regions/{id}`
  - Renvoie le détail de la région et sa décision humaine courante.
  - Les modifications destructives (PUT/PATCH/DELETE) sont interdites (HTTP 405 Method Not Allowed).

### 3.4 Statistiques Synthétiques (Tableau de Bord)

- `GET /api/v1/stats/summary`
  - Paramètre : `?include_demo=true|false` (défaut: `true`).
  - **Règle méthodologique stricte (§14.2)** : Renvoie **uniquement** des décomptes calculés depuis la base MongoDB locale :
    * Inspections : total, pending, running, done, error.
    * Régions : total, yolo, patchcore.
    * Revues : total, confirmed, rejected, uncertain, unreviewed.
    * Dernières inspections (5 plus récentes).
  - **Aucune** métrique de performance ML (mAP, F1-score, précision, rappel) n'est calculée ni inventée ici.

### 3.5 Journalisation d'Audit & Export ML

- `GET /api/v1/audit`
  - Filtres : `skip`, `limit`, `action`, `user_id`, `username`, `date_from`, `date_to`.
  - Accès restreint aux rôles `admin` et `auditor`.
  - **Traçabilité réflexive (§12)** : Toute consultation de cet endpoint consigne elle-même un événement d'audit immuable `action="audit_view"`.

- `GET /api/v1/feedback/export`
  - Paramètres : `skip`, `limit`.
  - Accès restreint aux rôles `admin` et `ml_engineer`.
  - Jointure complète entre feedback humain, coordonnées `bbox` et classification pour faciliter les futurs réentraînements ou analyses d'erreurs IA.
  - Consigne un événement d'audit `action="feedback_export"`.

### 3.6 Similarité Visuelle

- `POST /api/v1/similarity/search`
  - `file`: image ou vignette à rechercher.
  - `index_name`: `weaveguard`, `dtd` ou `all`.
  - `k`: nombre de voisins.
  - Libellés exacts :
    * `Textiles similaires (index WeaveGuard)`
    * `Textures similaires (galerie DTD générique)`

- `GET /api/v1/similarity/ref/{ref_id}/thumbnail`
  - Vignette de référence autorisée (protection anti path-traversal stricte).

### 3.4 Modèles & Rapports

- `GET /api/v1/models` : Métadonnées publiques, paramètres et empreintes SHA-256 des modèles.
- `GET /api/v1/reports/domain-bias` : Rapport contractuel d'évaluation du biais de domaine.
- `GET /health` : Contrôle de disponibilité sans secrets (statut de la base MongoDB et des artefacts).

