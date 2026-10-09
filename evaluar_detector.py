import csv
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image

try:
    from ultralytics import YOLO
    from ultralytics.data.utils import check_det_dataset
except ImportError as error:
    raise SystemExit(
        "Falta ultralytics. Instálalo con: pip install -r requirements.txt"
    ) from error


BASE_DIR = Path(__file__).resolve().parent
DATA_YAML = BASE_DIR / "Car Damage Images.v3i.yolov8" / "data.yaml"
DATASET_DIR = DATA_YAML.parent
MODEL_PATH = BASE_DIR / "models" / "segmentador_danos" / "best.pt"
REPORT_DIR = BASE_DIR / "resultados_deteccion"
CONFIDENCE_THRESHOLDS = (0.25, 0.35, 0.50, 0.65)
MINIMUM_CONFIDENCE = min(CONFIDENCE_THRESHOLDS)
IOU_THRESHOLD = 0.50
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def normalize_class_name(name):
    return str(name).strip().lower().replace(" ", "_").replace("-", "_")


def get_model_names(model):
    names = model.names
    if isinstance(names, dict):
        return {int(class_id): str(name) for class_id, name in names.items()}
    return {class_id: str(name) for class_id, name in enumerate(names)}


def collect_split(dataset, split, class_names):
    image_dir = Path(dataset[split])
    label_dir = image_dir.parent / "labels"
    if not image_dir.is_dir() or not label_dir.is_dir():
        raise SystemExit(f"Faltan imágenes o etiquetas para el split '{split}': {image_dir}")

    images = sorted(
        path
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        raise SystemExit(f"No hay imágenes en el split '{split}': {image_dir}")

    ground_truth = {}
    for image_path in images:
        label_path = label_dir / f"{image_path.stem}.txt"
        boxes = []
        if label_path.is_file():
            with Image.open(image_path) as image:
                image_width, image_height = image.size
            with label_path.open(encoding="utf-8-sig") as label_file:
                for line in label_file:
                    parts = line.split()
                    if not parts:
                        continue
                    if len(parts) < 7 or (len(parts) - 1) % 2:
                        raise ValueError(f"Polígono YOLO-seg mal formado: {label_path}")
                    class_id = int(parts[0])
                    if class_id not in class_names:
                        raise ValueError(f"Clase fuera del rango configurado: {label_path}")
                    coordinates = list(map(float, parts[1:]))
                    points = [
                        (coordinates[index] * image_width, coordinates[index + 1] * image_height)
                        for index in range(0, len(coordinates), 2)
                    ]
                    boxes.append(
                        {
                            "class_id": class_id,
                            "x1": min(point[0] for point in points),
                            "y1": min(point[1] for point in points),
                            "x2": max(point[0] for point in points),
                            "y2": max(point[1] for point in points),
                        }
                    )
        ground_truth[image_path.resolve()] = boxes
    return images, ground_truth


def predict_split(model, images):
    predictions = defaultdict(list)
    results = model.predict(
        source=[str(path) for path in images],
        conf=MINIMUM_CONFIDENCE,
        verbose=False,
    )
    for result in results:
        image_path = Path(result.path).resolve()
        if result.boxes is None:
            continue
        predicted_masks = result.masks.xy if result.masks is not None else []
        for box_index, box in enumerate(result.boxes):
            x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
            polygon = []
            if box_index < len(predicted_masks):
                polygon = [
                    [float(point[0]), float(point[1])]
                    for point in predicted_masks[box_index].tolist()
                ]
            predictions[image_path].append(
                {
                    "class_id": int(box.cls.item()),
                    "confidence": float(box.conf.item()),
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "polygon": polygon,
                }
            )
    return predictions


def intersection_over_union(first, second):
    intersection_width = max(0.0, min(first["x2"], second["x2"]) - max(first["x1"], second["x1"]))
    intersection_height = max(0.0, min(first["y2"], second["y2"]) - max(first["y1"], second["y1"]))
    intersection = intersection_width * intersection_height
    first_area = max(0.0, first["x2"] - first["x1"]) * max(0.0, first["y2"] - first["y1"])
    second_area = max(0.0, second["x2"] - second["x1"]) * max(0.0, second["y2"] - second["y1"])
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0


def evaluate_predictions(images, ground_truth, predictions, threshold, class_names, dataset_dir):
    counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    detection_rows = []
    total_ground_truth = 0

    for image_path in images:
        resolved_path = image_path.resolve()
        image_boxes = ground_truth[resolved_path]
        total_ground_truth += len(image_boxes)
        unmatched_ground_truth = set(range(len(image_boxes)))
        image_predictions = sorted(
            (
                prediction
                for prediction in predictions.get(resolved_path, [])
                if prediction["confidence"] >= threshold
            ),
            key=lambda prediction: prediction["confidence"],
            reverse=True,
        )

        for prediction in image_predictions:
            best_index = None
            best_iou = 0.0
            for ground_truth_index in unmatched_ground_truth:
                target = image_boxes[ground_truth_index]
                if target["class_id"] != prediction["class_id"]:
                    continue
                overlap = intersection_over_union(prediction, target)
                if overlap > best_iou:
                    best_index = ground_truth_index
                    best_iou = overlap

            is_true_positive = best_index is not None and best_iou >= IOU_THRESHOLD
            if is_true_positive:
                unmatched_ground_truth.remove(best_index)
                counts[prediction["class_id"]]["tp"] += 1
            else:
                counts[prediction["class_id"]]["fp"] += 1

            detection_rows.append(
                {
                    "imagen": image_path.relative_to(dataset_dir).as_posix(),
                    "clase_id": prediction["class_id"],
                    "clase": class_names[prediction["class_id"]],
                    "confianza": prediction["confidence"],
                    "x1": prediction["x1"],
                    "y1": prediction["y1"],
                    "x2": prediction["x2"],
                    "y2": prediction["y2"],
                    "contorno_predicho_xy": json.dumps(
                        prediction["polygon"], separators=(",", ":")
                    ),
                    "resultado_iou_50": "TP" if is_true_positive else "FP",
                    "iou_caja_emparejada": best_iou if is_true_positive else "",
                }
            )

        for ground_truth_index in unmatched_ground_truth:
            class_id = image_boxes[ground_truth_index]["class_id"]
            counts[class_id]["fn"] += 1

    class_metrics = {}
    for class_id, class_name in class_names.items():
        class_counts = counts[class_id]
        precision_denominator = class_counts["tp"] + class_counts["fp"]
        recall_denominator = class_counts["tp"] + class_counts["fn"]
        f1_denominator = 2 * class_counts["tp"] + class_counts["fp"] + class_counts["fn"]
        class_metrics[class_id] = {
            "clase": class_name,
            "precision": class_counts["tp"] / precision_denominator if precision_denominator else 0.0,
            "recall": class_counts["tp"] / recall_denominator if recall_denominator else 0.0,
            "f1": 2 * class_counts["tp"] / f1_denominator if f1_denominator else 0.0,
            **class_counts,
        }

    metrics = {
        "precision_macro": sum(item["precision"] for item in class_metrics.values()) / len(class_metrics),
        "recall_macro": sum(item["recall"] for item in class_metrics.values()) / len(class_metrics),
        "f1_macro": sum(item["f1"] for item in class_metrics.values()) / len(class_metrics),
        "tp": sum(item["tp"] for item in class_metrics.values()),
        "fp": sum(item["fp"] for item in class_metrics.values()),
        "fn": sum(item["fn"] for item in class_metrics.values()),
        "cajas_reales": total_ground_truth,
        "imagenes": len(images),
    }
    return metrics, class_metrics, detection_rows


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if not DATA_YAML.is_file():
        raise SystemExit(f"No se encontró el dataset YOLO: {DATA_YAML}")
    if not MODEL_PATH.is_file():
        raise SystemExit(
            f"No se encontró el modelo entrenado: {MODEL_PATH}. "
            "Ejecuta primero entrenar_detector.py."
        )

    dataset = check_det_dataset(str(DATA_YAML))
    class_names = {int(class_id): str(name) for class_id, name in dataset["names"].items()}
    model = YOLO(str(MODEL_PATH))
    model_names = get_model_names(model)
    if {
        class_id: normalize_class_name(name) for class_id, name in model_names.items()
    } != {
        class_id: normalize_class_name(name) for class_id, name in class_names.items()
    }:
        raise SystemExit("Las clases del modelo no coinciden con data.yaml; revisa models/segmentador_danos/best.pt.")

    validation_images, validation_truth = collect_split(dataset, "val", class_names)
    test_images, test_truth = collect_split(dataset, "test", class_names)
    print(f"Modelo: {MODEL_PATH}")
    print(f"Clases: {list(class_names.values())}")
    print(f"Validación: {len(validation_images)} imágenes; test: {len(test_images)} imágenes")

    validation_predictions = predict_split(model, validation_images)
    validation_rows = []
    for threshold in CONFIDENCE_THRESHOLDS:
        metrics, _, _ = evaluate_predictions(
            validation_images,
            validation_truth,
            validation_predictions,
            threshold,
            class_names,
            DATASET_DIR,
        )
        validation_rows.append({"umbral": threshold, **metrics})

    best_validation_row = max(
        validation_rows,
        key=lambda row: (row["f1_macro"], -row["umbral"]),
    )
    selected_threshold = best_validation_row["umbral"]

    test_predictions = predict_split(model, test_images)
    test_metrics, test_class_metrics, detection_rows = evaluate_predictions(
        test_images,
        test_truth,
        test_predictions,
        selected_threshold,
        class_names,
        DATASET_DIR,
    )

    metric_rows = [
        {"split": "validacion", "estado": "umbral evaluado", **row}
        for row in validation_rows
    ]
    metric_rows.append(
        {
            "split": "test_final",
            "estado": f"umbral elegido en validacion: {selected_threshold:.2f}",
            "umbral": selected_threshold,
            **test_metrics,
        }
    )
    metric_fields = [
        "split",
        "estado",
        "umbral",
        "precision_macro",
        "recall_macro",
        "f1_macro",
        "tp",
        "fp",
        "fn",
        "cajas_reales",
        "imagenes",
    ]
    write_csv(REPORT_DIR / "metricas_umbral.csv", metric_fields, metric_rows)
    write_csv(
        REPORT_DIR / "detecciones_test.csv",
        [
            "imagen",
            "clase_id",
            "clase",
            "confianza",
            "x1",
            "y1",
            "x2",
            "y2",
            "contorno_predicho_xy",
            "resultado_iou_50",
            "iou_caja_emparejada",
        ],
        detection_rows,
    )
    write_csv(
        REPORT_DIR / "metricas_por_clase_test.csv",
        ["clase", "precision", "recall", "f1", "tp", "fp", "fn"],
        list(test_class_metrics.values()),
    )

    print("\nUmbrales en validación (IoU >= 0.50):")
    for row in validation_rows:
        marker = "  <- elegido" if row["umbral"] == selected_threshold else ""
        print(
            f"{row['umbral']:.2f}: precision={row['precision_macro']:.3f}, "
            f"recall={row['recall_macro']:.3f}, F1 macro={row['f1_macro']:.3f}{marker}"
        )
    print(
        f"\nTEST final @ {selected_threshold:.2f}: "
        f"precision={test_metrics['precision_macro']:.3f}, "
        f"recall={test_metrics['recall_macro']:.3f}, "
        f"F1 macro={test_metrics['f1_macro']:.3f}, "
        f"TP={test_metrics['tp']}, FP={test_metrics['fp']}, FN={test_metrics['fn']}"
    )
    print(f"Reportes guardados en: {REPORT_DIR}")


if __name__ == "__main__":
    main()