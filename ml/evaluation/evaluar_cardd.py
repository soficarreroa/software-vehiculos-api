"""Evalúa el modelo CarDD con el mismo método de evaluar_detector.py (sin modificarlo).

Necesita evaluar_detector.py en la misma carpeta. Usa el split de test del dataset;
no lo cambies entre evaluaciones.

Uso:
    python evaluar_cardd.py --data carsdd/data.yaml --imgsz 320
(--imgsz debe ser el mismo tamaño con el que se entrenó el modelo.)
"""
import argparse
from pathlib import Path

import ml.evaluation.evaluar_detector as evaluador

try:
    from ultralytics import YOLO
except ImportError as error:
    raise SystemExit("Falta ultralytics. Instálalo con: pip install ultralytics") from error

BASE_DIR = next((p for p in Path(__file__).resolve().parents if (p / "requirements.txt").is_file()), Path(__file__).resolve().parent)


def main():
    parser = argparse.ArgumentParser(description="Evaluación del modelo CarDD")
    parser.add_argument("--data", default=str(BASE_DIR / "carsdd" / "data.yaml"))
    parser.add_argument("--model", default=str(BASE_DIR / "models" / "segmentador_cardd" / "best.pt"))
    parser.add_argument("--reporte", default=str(BASE_DIR / "resultados_cardd"))
    parser.add_argument("--imgsz", type=int, default=None,
                        help="Tamaño de imagen para predecir (el mismo del entrenamiento)")
    args = parser.parse_args()

    original_predict = YOLO.predict
    chunk_size = 16

    def predict_patched(self, *positional, **keywords):
        # Ultralytics procesa una lista de rutas como UN solo lote (ignora "batch") y el NMS
        # se corta por tiempo ("NMS time limit exceeded"), perdiendo detecciones.
        # Por eso se parte la lista en trozos pequeños y se juntan los resultados.
        if args.imgsz:
            keywords.setdefault("imgsz", args.imgsz)
        if positional:
            source, rest_positional = positional[0], positional[1:]
        else:
            source, rest_positional = keywords.pop("source", None), ()
        if isinstance(source, (list, tuple)) and len(source) > chunk_size:
            results = []
            for start in range(0, len(source), chunk_size):
                chunk = list(source[start:start + chunk_size])
                results.extend(original_predict(self, chunk, *rest_positional, **keywords))
            return results
        return original_predict(self, source, *rest_positional, **keywords)

    YOLO.predict = predict_patched
    print(f"Predicción con imgsz={args.imgsz or 'por defecto'}, en trozos de {chunk_size} imágenes")

    # Rutas absolutas: evaluar_detector.py compara rutas absolutas de imágenes con DATASET_DIR
    evaluador.DATA_YAML = Path(args.data).resolve()
    evaluador.DATASET_DIR = evaluador.DATA_YAML.parent
    evaluador.MODEL_PATH = Path(args.model).resolve()
    evaluador.REPORT_DIR = Path(args.reporte).resolve()
    evaluador.main()


if __name__ == "__main__":
    main()
