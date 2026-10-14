"""Divide un dataset YOLO que viene todo en train en train / valid / test.

La versión v3 de CarDD en Roboflow trae las 4,000 imágenes en train. Este script crea
valid y test con una semilla fija (misma división si se repite) y un reparto
estratificado: cada imagen se agrupa por su clase más rara, para que las clases con
pocos ejemplos queden representadas en los tres grupos.

Uso:
    python dividir_dataset.py --dataset carsdd
Mueve archivos (el ZIP original en Descargas sirve de respaldo) y guarda la lista
completa en split_manifest.csv dentro del dataset.
"""
import argparse
import csv
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def read_classes(label_path):
    if not label_path.is_file():
        return []
    classes = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            classes.append(int(float(line.split()[0])))
    return classes


def main():
    parser = argparse.ArgumentParser(description="División train/valid/test estratificada")
    parser.add_argument("--dataset", default="carsdd")
    parser.add_argument("--valid", type=float, default=0.20)
    parser.add_argument("--test", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    root = Path(args.dataset)
    image_dir = root / "train" / "images"
    label_dir = root / "train" / "labels"
    if not image_dir.is_dir() or not label_dir.is_dir():
        raise SystemExit(f"No se encontró {image_dir} o {label_dir}")
    for split in ("valid", "test"):
        existing = root / split / "images"
        if existing.is_dir() and any(existing.iterdir()):
            raise SystemExit(f"{existing} ya tiene archivos: el dataset ya está dividido.")

    images = sorted(p for p in image_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
    per_image = {image: read_classes(label_dir / f"{image.stem}.txt") for image in images}
    global_count = Counter(c for classes in per_image.values() for c in classes)
    print(f"Imágenes: {len(images)} | instancias por clase: {dict(sorted(global_count.items()))}")

    groups = defaultdict(list)
    for image, classes in per_image.items():
        rarest = min(classes, key=lambda c: (global_count[c], c)) if classes else -1
        groups[rarest].append(image)

    rng = random.Random(args.seed)
    assignment = {}
    for key in sorted(groups):
        members = groups[key]
        rng.shuffle(members)
        total = len(members)
        n_test = max(1, round(total * args.test)) if total >= 3 else 0
        n_valid = max(1, round(total * args.valid)) if total >= 3 else 0
        for index, image in enumerate(members):
            if index < n_test:
                assignment[image] = "test"
            elif index < n_test + n_valid:
                assignment[image] = "valid"
            else:
                assignment[image] = "train"

    for split in ("valid", "test"):
        (root / split / "images").mkdir(parents=True, exist_ok=True)
        (root / split / "labels").mkdir(parents=True, exist_ok=True)

    rows = []
    for image in sorted(assignment):
        split = assignment[image]
        label = label_dir / f"{image.stem}.txt"
        if split != "train":
            shutil.move(str(image), str(root / split / "images" / image.name))
            if label.is_file():
                shutil.move(str(label), str(root / split / "labels" / label.name))
        rows.append((image.name, split))

    manifest = root / "split_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["imagen", "split"])
        writer.writerows(rows)

    counts = Counter(split for _, split in rows)
    print(f"\nDivisión terminada (semilla {args.seed}): "
          f"train={counts['train']}, valid={counts['valid']}, test={counts['test']}")
    print(f"Lista completa guardada en {manifest}")
    print("Siguiente paso: python verificar_dataset.py --data carsdd/data.yaml")


if __name__ == "__main__":
    main()
