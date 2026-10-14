"""Verifica que el dataset CarDD descargado esté completo y bien formado.

Uso:
    python verificar_dataset.py --data carsdd/data.yaml

Imprime imágenes y etiquetas por split, la distribución de instancias por clase,
revisa que cada etiqueta tenga formato de polígono válido y guarda en
test_manifest.txt la lista de imágenes de test con su huella (SHA-256). Si repites
el script más adelante y la huella es la misma, el conjunto de prueba no cambió.
"""
import argparse
import hashlib
from collections import Counter
from pathlib import Path

import yaml

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def resolve_split_dir(dataset_root, value):
    candidate = (dataset_root / value).resolve()
    if candidate.is_dir():
        return candidate
    # Roboflow exporta rutas como ../train/images relativas a otra carpeta
    parts = [part for part in Path(value).parts if part != ".."]
    fallback = (dataset_root / Path(*parts)).resolve()
    return fallback if fallback.is_dir() else None


def check_label_file(path, class_count):
    problems = []
    instances = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        fields = line.split()
        try:
            class_id = int(float(fields[0]))
            values = [float(item) for item in fields[1:]]
        except ValueError:
            problems.append(f"{path.name}:{number} contiene valores no numéricos")
            continue
        if not 0 <= class_id < class_count:
            problems.append(f"{path.name}:{number} clase {class_id} fuera de rango")
        if len(values) < 6 or len(values) % 2 != 0:
            problems.append(f"{path.name}:{number} no es un polígono válido ({len(values)} valores)")
        if any(value < 0 or value > 1 for value in values):
            problems.append(f"{path.name}:{number} tiene coordenadas fuera de 0-1")
        instances.append(class_id)
    return instances, problems


def main():
    parser = argparse.ArgumentParser(description="Verificación del dataset CarDD")
    parser.add_argument("--data", default="carsdd/data.yaml")
    parser.add_argument("--manifest", default="test_manifest.txt")
    args = parser.parse_args()

    data_yaml = Path(args.data).resolve()
    if not data_yaml.is_file():
        raise SystemExit(f"No se encontró {data_yaml}")
    config = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    names = config["names"]
    names = [names[key] for key in sorted(names)] if isinstance(names, dict) else list(names)
    dataset_root = data_yaml.parent

    print(f"Clases ({len(names)}): {names}")
    all_problems = []
    test_images = []
    for split_key in ("train", "val", "test"):
        value = config.get(split_key)
        if not value:
            all_problems.append(f"El data.yaml no define '{split_key}'")
            continue
        image_dir = resolve_split_dir(dataset_root, value)
        if image_dir is None:
            all_problems.append(f"No existe la carpeta de imágenes de '{split_key}': {value}")
            continue
        label_dir = image_dir.parent / "labels"
        images = sorted(p for p in image_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
        counter = Counter()
        missing_labels = 0
        for image in images:
            label = label_dir / f"{image.stem}.txt"
            if not label.is_file():
                missing_labels += 1
                continue
            instances, problems = check_label_file(label, len(names))
            counter.update(instances)
            all_problems.extend(problems)
        print(f"\n{split_key}: {len(images)} imágenes, {sum(counter.values())} instancias, "
              f"{missing_labels} imágenes sin etiqueta (fondo)")
        for class_id, name in enumerate(names):
            print(f"   {name}: {counter.get(class_id, 0)}")
        if split_key == "test":
            test_images = images

    if test_images:
        digest = hashlib.sha256()
        lines = []
        for image in test_images:
            file_hash = hashlib.sha256(image.read_bytes()).hexdigest()
            digest.update(file_hash.encode())
            lines.append(f"{image.name} {file_hash[:16]}")
        Path(args.manifest).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nHuella del conjunto de prueba ({len(test_images)} imágenes): {digest.hexdigest()[:16]}")
        print(f"Lista guardada en {args.manifest}")

    if all_problems:
        print(f"\nSe encontraron {len(all_problems)} problemas (primeros 10):")
        for problem in all_problems[:10]:
            print(" -", problem)
        raise SystemExit(1)
    print("\nDataset OK: carpetas, etiquetas y clases son consistentes.")


if __name__ == "__main__":
    main()
