# Guide d'Expérimentation GPU (Optionnel) — WeaveGuard AI

Ce document détaille la procédure isolée pour tester l'accélération matérielle GPU (CUDA) ultérieurement, **sans modifier ni impacter l'environnement stable de production `backend/.venv`**.

---

## 1. Principe d'Isolation

L'environnement de référence actuel `backend/.venv` tourne de manière stable et validée en mode **inférence CPU**. Pour évaluer la compatibilité d'une roue PyTorch CUDA sur votre carte graphique (par ex. NVIDIA GeForce GTX 1050, micro-architecture Pascal `sm_61`), vous devez créer un environnement virtuel distinct : `backend/.venv-gpu`.

---

## 2. Procédure Pas à Pas (PowerShell sous Windows)

### Étape 1 : Créer le venv isolé GPU
Depuis la racine du projet (`VPO`) :
```powershell
python -m venv backend/.venv-gpu
```

### Étape 2 : Installer la roue PyTorch avec support CUDA
Recherchez et installez une version de PyTorch précompilée avec CUDA depuis le dépôt officiel de roues PyTorch :
```powershell
# Exemple pour CUDA 12.1 :
.\backend\.venv-gpu\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Ou exemple pour CUDA 11.8 (si compatible) :
.\backend\.venv-gpu\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### Étape 3 : Installer les dépendances du backend
```powershell
.\backend\.venv-gpu\Scripts\python.exe -m pip install -r backend/requirements.txt
```

### Étape 4 : Exécuter le diagnostic matériel
```powershell
.\backend\.venv-gpu\Scripts\python.exe backend/scripts/check_gpu.py
```

---

## 3. Critères d'Acceptation GPU

Pour que l'environnement GPU soit considéré comme viable, **l'ensemble** des critères suivants doit être validé :
1. **Disponibilité CUDA** : `torch.cuda.is_available()` renvoie `True`.
2. **Support de l'architecture** : `torch.cuda.get_arch_list()` contient l'architecture de votre GPU (par exemple `sm_61` pour une GTX 1050 / Pascal) **OU** une opération tensorielle réelle et une inférence supervisée YOLO s'exécutent sur GPU sans lever l'erreur CUDA :
   > `RuntimeError: CUDA error: no kernel image is available for execution on the device`
3. **Marge mémoire VRAM** : Le chargement séquentiel ne produit pas d'erreur de mémoire saturée (`CUDA out of memory`).

---

## 4. Retour Arrière Immédiat (Fallback CPU)

Si le diagnostic échoue ou lève l'erreur `no kernel image is available` :
1. Ne pas utiliser `.venv-gpu`.
2. Conserver la variable `DEVICE=cpu` (ou `DEVICE=auto` qui bascule automatiquement sur CPU).
3. Continuer à utiliser l'environnement principal validé : `backend/.venv`.
4. Optionnellement, supprimer le venv de test :
   ```powershell
   Remove-Item -Recurse -Force backend/.venv-gpu
   ```

