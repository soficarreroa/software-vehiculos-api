"""Fine-tuning de YOLOv8n-seg con el dataset CarDD (6 tipos de daño).

Parte siempre de los pesos preentrenados de COCO (yolov8n-seg.pt), NO del modelo
anterior. Por defecto guarda los pesos en una carpeta de candidato, sin modificar
el modelo activo de models/segmentador_cardd/.

Prueba rápida (verifica que todo funciona, ~2 minutos en GPU):
    python ml/training/entrenar_cardd.py --data carsdd/data.yaml --epochs 1 --fraction 0.05 --name prueba_rapida
Entrenamiento completo:
    python ml/training/entrenar_cardd.py --data carsdd/data.yaml --epochs 50 --imgsz 640 --batch 4 --device cpu --workers 0
"""
import argparse
import shutil
from pathlib import Path

try:
    from ultralytics import YOLO
    from ultralytics.data.utils import check_det_dataset
except ImportError as error:
    raise SystemExit("Falta ultralytics. Instálalo con: pip install ultralytics") from error


BASE_DIR = (next((p for p in Path(__file__).resolve().parents if (p / "requirements.txt").is_file()), Path(__file__).resolve().parent))
START_MODEL = "yolov8n-seg.pt"
RUNS_DIR = BASE_DIR / "runs"
ACTIVE_MODEL_DIR = BASE_DIR / "models" / "segmentador_cardd"
MODEL_DIR = BASE_DIR / "models" / "segmentador_cardd_candidato_640_50"


def parse_args():
    parser = argparse.ArgumentParser(description="Fine-tuning YOLOv8n-seg con CarDD")
    parser.add_argument("--data", default=str(BASE_DIR / "carsdd" / "data.yaml"))
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--fraction", type=float, default=1.0,
                        help="Fracción del train a usar (1.0 = todo; 0.05 sirve para una prueba rápida)")
    parser.add_argument("--device", default="cpu", help="0 para GPU, cpu para CPU")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--name", default="cardd_candidato_640_50")
    parser.add_argument(
        "--model-dir",
        default=str(MODEL_DIR),
        help="Carpeta destino de best.pt y last.pt; por defecto no toca el modelo activo",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    data_yaml = Path(args.data)
    if not data_yaml.is_file():
        raise SystemExit(f"No se encontró el data.yaml del dataset: {data_yaml}")

    model_dir = Path(args.model_dir).resolve()
    active_model_dir = ACTIVE_MODEL_DIR.resolve()
    if model_dir == active_model_dir or any(
        (model_dir / checkpoint).resolve() == (active_model_dir / checkpoint).resolve()
        for checkpoint in ("best.pt", "last.pt")
    ):
        raise SystemExit(
            "Se cancela para proteger el modelo activo. Guarda el candidato en otra carpeta."
        )

    dataset = check_det_dataset(str(data_yaml))
    print(f"Dataset: {data_yaml}")
    print(f"Clases: {dataset['names']}")
    for split in ("train", "val", "test"):
        image_dir = Path(dataset[split])
        print(f"{split}: {sum(1 for p in image_dir.iterdir() if p.is_file())} imágenes")

    print(f"Entrenamiento desde {START_MODEL}: {args.epochs} épocas, imgsz={args.imgsz}, "
          f"batch={args.batch}, fraction={args.fraction}")
    model = YOLO(START_MODEL)
    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        fraction=args.fraction,
        patience=15,
        seed=42,
        workers=args.workers,
        device=args.device,
        project=str(RUNS_DIR),
        name=args.name,
    )

    best_weights = Path(model.trainer.best)
    last_weights = Path(model.trainer.last)
    if not best_weights.is_file() or not last_weights.is_file():
        raise SystemExit("El entrenamiento no generó ambos checkpoints best.pt y last.pt.")

    model_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_weights, model_dir / "best.pt")
    shutil.copy2(last_weights, model_dir / "last.pt")
    print(f"\nMejor checkpoint guardado en: {model_dir / 'best.pt'}")
    print(f"Último checkpoint guardado en: {model_dir / 'last.pt'}")


if __name__ == "__main__":
    main()
