# Sortir `models/` et `datasets/` de l'historique Git (Git LFS)

Le dépôt versionne ~1,1 Go d'artefacts binaires (`models/` ≈ 167 Mo, `datasets/` ≈ 976 Mo) directement dans Git.
Chaque clone les télécharge en entier, et chaque nouvelle version d'un modèle alourdit définitivement l'historique.

> Cette migration **réécrit l'historique** : elle n'a volontairement pas été exécutée automatiquement.
> Faites-la une seule fois, sur un dépôt propre, puis prévenez tous les collaborateurs (ils devront re-cloner).

## Procédure

```bash
# 0. Sauvegarde
git clone --mirror <url-du-depot> weaveguard-backup.git

# 1. Installer Git LFS (une fois par machine)
git lfs install

# 2. Convertir l'historique existant
git lfs migrate import --everything \
  --include="models/**,*.pt,*.pth,*.onnx,*.faiss,datasets/**/*.jpg,datasets/**/*.jpeg,datasets/**/*.png"

# 3. Vérifier
git lfs ls-files | head
du -sh .git

# 4. Publier (réécriture d'historique)
git push --force-with-lease --all
git push --force-with-lease --tags
```

Après la migration, `git lfs track` ajoute les motifs dans `.gitattributes` ; commitez ce fichier.
Le workflow CI (`actions/checkout@v4`) doit alors utiliser `with: { lfs: true }` pour récupérer les modèles.

## Alternative sans réécriture d'historique

Si le dépôt ne doit pas être réécrit, stockez les modèles dans un stockage objet (S3, Hugging Face Hub, release GitHub)
et téléchargez-les via un script `scripts/fetch_models.py` appelé par le `Dockerfile`.
