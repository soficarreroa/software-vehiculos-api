"""Prueba de uso real: el modelo recibe fotos y devuelve las clases de daño encontradas.

Corresponde al objetivo de la semana: "YOLO detecta daños en una foto y devuelve las
clases encontradas". Guarda las fotos con las cajas/máscaras dibujadas.

Uso:
    python probar_cardd.py --fotos carsdd/test/images --cantidad 8
    python probar_cardd.py --fotos mi_foto.jpg
"""
import argparse
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError as error:
    raise SystemExit("Falta ultralytics. Instálalo con: pip install ultralytics") from error

BASE_DIR = next((p for p in Path(__file__).resolve().parents if (p / "requirements.txt").is_file()), Path(__file__).resolve().parent)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def main():
    parser = argparse.ArgumentParser(description="Prueba del modelo CarDD sobre fotos")
    parser.add_argument("--fotos", required=True, help="Una foto o una carpeta de fotos")
    parser.add_argument("--model", default=str(BASE_DIR / "models" / "segmentador_cardd" / "best.pt"))
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--cantidad", type=int, default=8)
    parser.add_argument("--imgsz", type=int, default=None,
                        help="Tamaño de imagen (el mismo del entrenamiento)")
    parser.add_argument("--salida", default=str(BASE_DIR / "resultados_cardd" / "pruebas"))
    args = parser.parse_args()

    source = Path(args.fotos)
    if source.is_dir():
        images = sorted(p for p in source.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)[: args.cantidad]
    elif source.is_file():
        images = [source]
    else:
        raise SystemExit(f"No se encontró: {source}")
    if not images:
        raise SystemExit("No hay imágenes para probar.")
    model_path = Path(args.model)
    if not model_path.is_file():
        raise SystemExit(f"No se encontró el modelo: {model_path}")

    model = YOLO(str(model_path))
    output_dir = Path(args.salida)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Modelo: {model_path} | confianza mínima: {args.conf}\n")
    for image in images:
        extra = {"imgsz": args.imgsz} if args.imgsz else {}
        result = model.predict(str(image), conf=args.conf, verbose=False, **extra)[0]
        found = sorted({model.names[int(cls)] for cls in result.boxes.cls})
        detail = ", ".join(f"{model.names[int(c)]} {float(s):.2f}" for c, s in zip(result.boxes.cls, result.boxes.conf))
        print(f"{image.name}: {found if found else 'sin daños detectados'}" + (f"  ({detail})" if detail else ""))
        result.save(filename=str(output_dir / image.name))
    print(f"\nImágenes anotadas guardadas en: {output_dir}")


if __name__ == "__main__":
    main()
