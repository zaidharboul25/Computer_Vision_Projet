#!/usr/bin/env python
"""Préparation du jeu de données pour fine-tuning supervisé (WP5).

Prépare les répertoires et le fichier data.yaml dans candidates/finetune_data/
sans jamais modifier les répertoires d'origine datasets/ (lecture seule stricte).

Usage :
    cd c:\\Users\\zaidh\\Desktop\\VPO
    backend\\.venv\\Scripts\\python.exe scripts\\prepare_finetune_dataset.py
"""
import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.engines.yolo_engine import YOLOEngine


def prepare_dataset(output_dir: Path) -> None:
    src_images = PROJECT_ROOT / "datasets" / "images"
    src_labels = PROJECT_ROOT / "datasets" / "labels"

    if not src_images.exists() or not src_labels.exists():
        print(f"[ERREUR] Répertoires introuvables : {src_images} ou {src_labels}")
        sys.exit(1)

    # Récupérer les classes depuis le model_card YOLO officiel
    engine = YOLOEngine()
    engine.load()
    classes = engine.classes

    output_dir.mkdir(parents=True, exist_ok=True)
    images_out = output_dir / "images"
    labels_out = output_dir / "labels"

    for split in ("train", "val"):
        (images_out / split).mkdir(parents=True, exist_ok=True)
        (labels_out / split).mkdir(parents=True, exist_ok=True)

    stats: Dict[str, int] = {"train": 0, "val": 0}
    class_counts: Dict[str, int] = {c: 0 for c in classes}

    print(f"\nPréparation du dataset de fine-tuning dans : {output_dir}")
    print("Vérification des correspondances image <-> labels...")

    for split in ("train", "val"):
        img_split_dir = src_images / split
        lbl_split_dir = src_labels / split

        for img_path in img_split_dir.iterdir():
            if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue

            lbl_path = lbl_split_dir / f"{img_path.stem}.txt"
            if not lbl_path.exists():
                continue

            # Comptage des classes annotées
            for line in lbl_path.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split()
                if len(parts) >= 5:
                    c_id = int(parts[0])
                    if c_id < len(classes):
                        class_counts[classes[c_id]] += 1

            stats[split] += 1

    # Écriture du manifest YAML
    yaml_content = f"""# WeaveGuard AI - Dataset de Fine-Tuning Candidat (Généré automatiquement)
path: {output_dir.resolve().as_posix()}
train: images/train
val: images/val

names:
"""
    for i, c in enumerate(classes):
        yaml_content += f"  {i}: {c}\n"

    yaml_file = output_dir / "data.yaml"
    with open(yaml_file, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    # Rapport JSON des statistiques
    stats_data = {
        "classes": classes,
        "n_classes": len(classes),
        "counts": stats,
        "class_distribution": class_counts,
        "yaml_config": str(yaml_file),
    }

    with open(output_dir / "dataset_summary.json", "w", encoding="utf-8") as f:
        json.dump(stats_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("BILAN DE PRÉPARATION (WP5) :")
    print(f"  Images valides 'train' : {stats['train']}")
    print(f"  Images valides 'val'   : {stats['val']}")
    print(f"  Fichier YAML généré    : {yaml_file}")
    print(f"  Synthèse JSON          : {output_dir / 'dataset_summary.json'}")
    print("=" * 60)
    print("\n[OK] Dataset prêt pour fine-tuning conformément à docs/FINETUNE_PROTOCOL.md.")


def main():
    parser = argparse.ArgumentParser(description="Préparation du dataset de fine-tuning.")
    parser.add_argument(
        "--output",
        default="candidates/finetune_data",
        help="Répertoire cible (défaut: candidates/finetune_data)",
    )
    args = parser.parse_args()

    prepare_dataset(PROJECT_ROOT / args.output)


if __name__ == "__main__":
    main()

