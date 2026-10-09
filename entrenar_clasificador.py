import random
import shutil
from collections import defaultdict
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError as error:
    raise SystemExit(
        "Falta ultralytics. Instálalo con: pip install -r requirements.txt"
    ) from error


BASE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = BASE_DIR / "fotos-clasificadas" / "clasificadas"
DATASET_DIR = BASE_DIR / "dataset_clasificacion"
RUNS_DIR = BASE_DIR / "runs"
MODEL_PATH = "yolov8n-cls.pt"
RUN_NAME = "clasificador_tipo_dano"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
DAMAGE_TYPES = {"abolladura", "rayon", "golpe_estructural", "rotura"}
VALIDATION_RATIO = 0.15
TEST_RATIO = 0.15
SEED = 42
EPOCHS = 50
IMAGE_SIZE = 224
BATCH_SIZE = 8


def collect_images():
    images_by_class = defaultdict(list)
    for image_path in sorted(SOURCE_DIR.rglob("*")):
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        damage_type = image_path.parent.parent.name
        severity = image_path.parent.name
        if damage_type not in DAMAGE_TYPES:
            raise ValueError(f"Tipo de daño no reconocido en la ruta: {image_path}")
        if severity not in {"leve", "moderado", "severo"}:
            raise ValueError(f"Severidad no reconocida en la ruta: {image_path}")
        images_by_class[damage_type].append(image_path)

    missing_classes = DAMAGE_TYPES - images_by_class.keys()
    if missing_classes:
        raise SystemExit(f"Faltan imágenes para estas clases: {', '.join(sorted(missing_classes))}")
    return images_by_class


def prepare_dataset(images_by_class):
    if DATASET_DIR.exists():
        expected_directories = [
            DATASET_DIR / split / damage_type
            for split in ("train", "val", "test")
            for damage_type in DAMAGE_TYPES
        ]
        if all(path.is_dir() for path in expected_directories):
            print(f"Usando la partición existente: {DATASET_DIR}")
            return
        raise SystemExit(
            f"La carpeta {DATASET_DIR} ya existe pero está incompleta. "
            "Revísala antes de volver a preparar el dataset."
        )

    random_generator = random.Random(SEED)
    for damage_type in sorted(DAMAGE_TYPES):
        images = images_by_class[damage_type][:]
        if len(images) < 3:
            raise SystemExit(
                f"La clase {damage_type} necesita al menos 3 imágenes "
                "para separar train, val y test."
            )

        random_generator.shuffle(images)
        test_count = max(1, round(len(images) * TEST_RATIO))
        validation_count = max(1, round(len(images) * VALIDATION_RATIO))
        test_images = images[:test_count]
        validation_images = images[test_count : test_count + validation_count]
        train_images = images[test_count + validation_count :]

        for split, split_images in (
            ("train", train_images),
            ("val", validation_images),
            ("test", test_images),
        ):
            class_dir = DATASET_DIR / split / damage_type
            class_dir.mkdir(parents=True, exist_ok=True)
            for image_path in split_images:
                severity = image_path.parent.name
                destination = class_dir / f"{severity}__{image_path.name}"
                shutil.copy2(image_path, destination)

    print(f"Dataset de clasificación creado: {DATASET_DIR}")
    for split in ("train", "val", "test"):
        counts = {
            damage_type: len(list((DATASET_DIR / split / damage_type).iterdir()))
            for damage_type in sorted(DAMAGE_TYPES)
        }
        print(f"{split}: {counts}")


def main():
    if not SOURCE_DIR.is_dir():
        raise SystemExit(f"No se encontró el dataset original: {SOURCE_DIR}")

    images_by_class = collect_images()
    print("Imágenes de origen por clase:")
    for damage_type in sorted(DAMAGE_TYPES):
        print(f"  {damage_type}: {len(images_by_class[damage_type])}")

    prepare_dataset(images_by_class)
    print(
        "AVISO: este dataset es pequeño; en especial, los resultados de "
        "rotura no serán estadísticamente confiables."
    )

    model = YOLO(MODEL_PATH)
    model.train(
        data=str(DATASET_DIR),
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,
        seed=SEED,
        workers=0,
        patience=10,
        project=str(RUNS_DIR),
        name=RUN_NAME,
        exist_ok=True,
    )
    print(f"\nModelo entrenado: {RUNS_DIR / RUN_NAME / 'weights' / 'best.pt'}")


if __name__ == "__main__":
    main()