import shutil
from pathlib import Path

try:
    from ultralytics import YOLO
    from ultralytics.data.utils import check_det_dataset
except ImportError as error:
    raise SystemExit(
        "Falta ultralytics. Instálalo con: pip install -r requirements.txt"
    ) from error


BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "Car Damage Images.v3i.yolov8"
DATA_YAML = DATASET_DIR / "data.yaml"
START_MODEL = "yolov8n-seg.pt"
RUNS_DIR = BASE_DIR / "runs"
MODEL_DIR = BASE_DIR / "models" / "segmentador_danos"
LAST_CHECKPOINT = MODEL_DIR / "last.pt"
BEST_CHECKPOINT = MODEL_DIR / "best.pt"
RUN_NAME = "segmentador_danos_6_clases"
CONTINUATION_RUN_NAME = "segmentador_danos_6_clases_continuacion"
EPOCHS = 50
CONTINUATION_EPOCHS = 10
IMAGE_SIZE = 512
BATCH_SIZE = 4


def main():
    if not DATA_YAML.is_file():
        raise SystemExit(f"No se encontró la configuración del dataset: {DATA_YAML}")

    dataset = check_det_dataset(str(DATA_YAML))
    print(f"Dataset: {DATA_YAML}")
    print(f"Clases: {dataset['names']}")
    for split in ("train", "val", "test"):
        image_dir = Path(dataset[split])
        image_count = sum(1 for path in image_dir.iterdir() if path.is_file())
        print(f"{split}: {image_count} imágenes")

    if LAST_CHECKPOINT.is_file():
        model = YOLO(str(LAST_CHECKPOINT))
        run_name = CONTINUATION_RUN_NAME
        epochs = CONTINUATION_EPOCHS
        print(
            f"Continuando ajuste desde {LAST_CHECKPOINT}; "
            f"se ejecutarán hasta {epochs} épocas nuevas."
        )
    else:
        model = YOLO(START_MODEL)
        run_name = RUN_NAME
        epochs = EPOCHS
        print(f"Entrenamiento inicial desde {START_MODEL}: hasta {epochs} épocas.")

    model.train(
        data=str(DATA_YAML),
        epochs=epochs,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,
        patience=10,
        seed=42,
        workers=0,
        project=str(RUNS_DIR),
        name=run_name,
    )

    best_weights = Path(model.trainer.best)
    last_weights = Path(model.trainer.last)
    if not best_weights.is_file() or not last_weights.is_file():
        raise SystemExit("El entrenamiento no generó ambos checkpoints best.pt y last.pt.")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_weights, BEST_CHECKPOINT)
    shutil.copy2(last_weights, LAST_CHECKPOINT)
    print(f"\nMejor checkpoint guardado en: {BEST_CHECKPOINT}")
    print(f"Checkpoint para continuar guardado en: {LAST_CHECKPOINT}")


if __name__ == "__main__":
    main()