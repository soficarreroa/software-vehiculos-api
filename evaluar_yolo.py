import csv
from collections import defaultdict
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError as error:
    raise SystemExit(
        "Falta ultralytics. Instálalo con: pip install -r requirements.txt"
    ) from error


MODEL_PATH = "runs/clasificador_tipo_dano/weights/best.pt"
CONFIDENCE_THRESHOLDS = (0.25, 0.35, 0.50, 0.65)
DATASET_DIR = Path(__file__).resolve().parent / "dataset_clasificacion" / "test"
REPORT_DIR = Path(__file__).resolve().parent / "resultados_yolo"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
DAMAGE_TYPES = {"abolladura", "rayon", "golpe_estructural", "rotura"}
EXPECTED_CLASSES = DAMAGE_TYPES


def normalize_class_name(name):
    return str(name).strip().lower().replace(" ", "_").replace("-", "_")


def get_ground_truth(image_path):
    damage_type = image_path.parent.name
    if damage_type not in DAMAGE_TYPES:
        raise ValueError(f"Tipo de daño no reconocido en la ruta: {image_path}")
    return damage_type


def collect_images():
    images = []
    for image_path in sorted(DATASET_DIR.rglob("*")):
        if image_path.is_file() and image_path.suffix.lower() in IMAGE_EXTENSIONS:
            images.append((image_path, get_ground_truth(image_path)))
    return images


def get_model_names(model):
    names = model.names
    if isinstance(names, dict):
        return {int(class_id): str(name) for class_id, name in names.items()}
    return {class_id: str(name) for class_id, name in enumerate(names)}


def classify_image(model, image_path, ground_truth, model_names):
    result = model.predict(source=str(image_path), verbose=False)[0]
    if result.probs is None:
        raise RuntimeError(
            f"El modelo '{MODEL_PATH}' no es de clasificación de imágenes. "
            "Usa un checkpoint de clasificación, por ejemplo yolov8n-cls.pt."
        )

    class_id = int(result.probs.top1)
    confidence = float(result.probs.top1conf.item())
    class_name = model_names[class_id]
    return {
        "image": image_path.relative_to(DATASET_DIR.parent.parent).as_posix(),
        "ground_truth": ground_truth,
        "class_id": class_id,
        "class_name": class_name,
        "normalized_class": normalize_class_name(class_name),
        "confidence": confidence,
    }


def calculate_metrics(images, predictions, threshold):
    counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    supported_classes = {ground_truth for _, ground_truth in images}
    correct = 0
    rejected = 0

    for image_path, ground_truth in images:
        prediction = predictions[image_path]
        predicted_class = prediction["normalized_class"]
        if (
            predicted_class not in EXPECTED_CLASSES
            or prediction["confidence"] < threshold
        ):
            counts[ground_truth]["fn"] += 1
            rejected += 1
            continue

        if predicted_class == ground_truth:
            counts[ground_truth]["tp"] += 1
            correct += 1
        else:
            counts[predicted_class]["fp"] += 1
            counts[ground_truth]["fn"] += 1

    class_precisions = []
    class_recalls = []
    class_f1_scores = []
    for class_name in supported_classes:
        class_counts = counts[class_name]
        precision_denominator = class_counts["tp"] + class_counts["fp"]
        recall_denominator = class_counts["tp"] + class_counts["fn"]
        f1_denominator = 2 * class_counts["tp"] + class_counts["fp"] + class_counts["fn"]
        class_precisions.append(
            class_counts["tp"] / precision_denominator if precision_denominator else 0.0
        )
        class_recalls.append(
            class_counts["tp"] / recall_denominator if recall_denominator else 0.0
        )
        class_f1_scores.append(
            2 * class_counts["tp"] / f1_denominator if f1_denominator else 0.0
        )

    precision = sum(class_precisions) / len(class_precisions)
    recall = sum(class_recalls) / len(class_recalls)
    f1 = sum(class_f1_scores) / len(class_f1_scores)
    return {
        "precision_macro": precision,
        "recall_macro": recall,
        "f1_macro": f1,
        "accuracy": correct / len(images),
        "correct_images": correct,
        "sin_clasificacion": rejected,
        "image_count": len(images),
    }


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if not DATASET_DIR.is_dir():
        raise SystemExit(
            f"No se encontró el conjunto de prueba: {DATASET_DIR}. "
            "Ejecuta primero entrenar_clasificador.py."
        )

    images = collect_images()
    if not images:
        raise SystemExit(f"No se encontraron imágenes en {DATASET_DIR}")

    model_path = Path(MODEL_PATH)
    if not model_path.is_absolute() and not model_path.exists():
        model_path = Path(__file__).resolve().parent / model_path

    if not model_path.is_file():
        raise SystemExit(
            f"No se encontró el modelo entrenado: {model_path}. "
            "Ejecuta primero entrenar_clasificador.py."
        )

    print(f"Modelo de clasificación: {model_path}")
    print(f"Imágenes: {len(images)}")
    print(f"Umbrales: {', '.join(f'{value:.2f}' for value in CONFIDENCE_THRESHOLDS)}")
    model = YOLO(str(model_path))
    model_names = get_model_names(model)
    normalized_names = {normalize_class_name(name) for name in model_names.values()}
    missing_classes = sorted(EXPECTED_CLASSES - normalized_names)
    if missing_classes:
        print(
            "AVISO: el modelo no contiene las 12 clases de daños. "
            "Se guardarán sus predicciones, pero las métricas no serán válidas "
            "hasta entrenarlo con las cuatro clases de daño."
        )

    predictions = {}
    for index, (image_path, ground_truth) in enumerate(images, start=1):
        predictions[image_path] = classify_image(
            model, image_path, ground_truth, model_names
        )
        prediction = predictions[image_path]
        print(
            f"[{index}/{len(images)}] {image_path.name}: "
            f"{prediction['class_name']} ({prediction['confidence']:.1%})"
        )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    prediction_rows = [
        {
            "imagen": prediction["image"],
            "etiqueta_real": prediction["ground_truth"],
            "clase_predicha": prediction["class_name"],
            "confianza": f"{prediction['confidence']:.6f}",
        }
        for prediction in predictions.values()
    ]
    write_csv(
        REPORT_DIR / "clasificaciones.csv",
        ["imagen", "etiqueta_real", "clase_predicha", "confianza"],
        prediction_rows,
    )

    metric_rows = []
    metric_fields = [
        "umbral",
        "estado",
        "precision_macro",
        "recall_macro",
        "f1_macro",
        "accuracy",
        "correct_images",
        "sin_clasificacion",
        "image_count",
    ]
    if missing_classes:
        metric_rows = [
            {
                "umbral": threshold,
                "estado": "modelo sin clases personalizadas; métricas no válidas",
            }
            for threshold in CONFIDENCE_THRESHOLDS
        ]
        print("No se comparan métricas: entrena primero el clasificador con las cuatro clases.")
    else:
        for threshold in CONFIDENCE_THRESHOLDS:
            metric_rows.append(
                {
                    "umbral": threshold,
                    "estado": "ok",
                    **calculate_metrics(images, predictions, threshold),
                }
            )
        best_row = max(metric_rows, key=lambda row: row["f1_macro"])
        print("\nResumen por umbral:")
        print("umbral  precisión  recall  F1 macro  exactitud  sin clasificación")
        for row in metric_rows:
            marker = "  <- mejor F1" if row is best_row else ""
            print(
                f"{row['umbral']:.2f}     {row['precision_macro']:.3f}      "
                f"{row['recall_macro']:.3f}   {row['f1_macro']:.3f}     "
                f"{row['accuracy']:.3f}       {row['sin_clasificacion']}{marker}"
            )

    write_csv(REPORT_DIR / "metricas_umbral.csv", metric_fields, metric_rows)
    print(f"\nReportes guardados en: {REPORT_DIR}")


if __name__ == "__main__":
    main()