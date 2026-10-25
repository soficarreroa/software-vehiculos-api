"""
Traduce la salida cruda de YOLO (boxes, clases numericas, confianza,
mascaras de segmentacion) a un formato mas simple: una lista de
diccionarios con los datos esenciales de cada dano detectado.

Usa el modelo entrenado con CarDD (models/segmentador_cardd_candidato_416_25/best.pt, ver
ENTRENAMIENTO_CARDD.md). Los nombres de clase del modelo estan en ingles y se
traducen a los tipos de dano de la tabla de costos del proyecto. Ademas estima
una severidad preliminar (leve / moderado / grave) por tamano relativo del dano
(ver severidad.py); si no existe severidad_umbrales.json, la severidad queda en None.
"""

import json
import sys
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock

from PIL import Image
from ultralytics import YOLO

try:
    from .severidad import area_poligono, cargar_umbrales, estimar_severidad, etiqueta_costo
except ImportError:  # se ejecuta como script, no como parte de un paquete
    from severidad import area_poligono, cargar_umbrales, estimar_severidad, etiqueta_costo

# Raiz del repositorio: sube de carpeta hasta encontrar requirements.txt (sirve en la raiz o en app/services/).
BASE_DIR = next((p for p in Path(__file__).resolve().parents if (p / "requirements.txt").is_file()), Path(__file__).resolve().parent)
MODEL_PATH = BASE_DIR / "models" / "segmentador_cardd_candidato_416_25" / "best.pt"

# Tamaño y umbral seleccionados al evaluar el candidato en validación de CarDD.
IMGSZ = 416
CONFIANZA_MINIMA = 0.30
_PREDICTION_LOCK = Lock()

# Clase del modelo (CarDD) -> tipo de dano del proyecto (tabla de costos).
TIPOS_DANO = {
    "crack": "grieta",
    "dent": "abolladura",
    "glass shatter": "vidrio_roto",
    "lamp broken": "luz_rota",
    "scratch": "rayon",
    "tire flat": "llanta_baja",
}


@lru_cache(maxsize=1)
def cargar_modelo():
    """Carga una sola instancia del modelo por proceso."""
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"No se encontró el modelo YOLO: {MODEL_PATH}")
    return YOLO(str(MODEL_PATH))


def calcular_area_relativa(result, indice, caja):
    """Area del dano / area de la foto: usa la mascara si existe y, si no, la caja."""
    if result.masks is not None and indice < len(result.masks.xyn):
        poligono = result.masks.xyn[indice]
        if len(poligono) >= 3:
            return area_poligono(poligono)
    alto_img, ancho_img = result.orig_shape
    x1, y1, x2, y2 = caja
    return ((x2 - x1) * (y2 - y1)) / (ancho_img * alto_img)


def traducir_resultado(result, umbrales=None):
    """
    Convierte un objeto Results de Ultralytics (la salida cruda de
    model.predict) en una lista simple de diccionarios, uno por cada
    daño detectado en la imagen.
    """
    danos = []

    if result.boxes is None:
        return danos

    if umbrales is None:
        umbrales = cargar_umbrales()

    nombres_clases = result.names
    mascaras = result.masks.xy if result.masks is not None else []

    for i, box in enumerate(result.boxes):
        x1, y1, x2, y2 = [round(v, 1) for v in box.xyxy[0].tolist()]
        clase_id = int(box.cls.item())
        confianza = round(float(box.conf.item()), 3)
        clase_yolo = nombres_clases[clase_id]
        tipo_dano = TIPOS_DANO.get(clase_yolo, clase_yolo)

        area_relativa = calcular_area_relativa(result, i, (x1, y1, x2, y2))
        severidad = estimar_severidad(clase_yolo, area_relativa, umbrales)

        dano = {
            "tipo_dano": tipo_dano,
            "clase_yolo": clase_yolo,
            "confianza": confianza,
            "ubicacion": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            "ancho": round(x2 - x1, 1),
            "alto": round(y2 - y1, 1),
            "tiene_contorno": i < len(mascaras),
            "area_relativa": round(area_relativa, 4),
            "severidad": severidad,
            "etiqueta_costo": etiqueta_costo(tipo_dano, severidad) if severidad else None,
        }
        danos.append(dano)

    danos.sort(key=lambda d: d["confianza"], reverse=True)
    return danos


def traducir_imagen(ruta_imagen, modelo=None, confianza_minima=CONFIANZA_MINIMA):
    """
    Carga el modelo, si no se pasa uno ya cargado, corre la deteccion
    sobre una imagen y devuelve el resultado en formato simple, incluyendo
    la lista de tipos de dano encontrados en la foto.
    """
    if modelo is None:
        modelo = cargar_modelo()

    with _PREDICTION_LOCK:
        resultado = modelo.predict(
            source=str(ruta_imagen), conf=confianza_minima, imgsz=IMGSZ, verbose=False
        )[0]

    danos = traducir_resultado(resultado)
    return {
        "imagen": str(ruta_imagen),
        "tipos_detectados": sorted({dano["tipo_dano"] for dano in danos}),
        "danos_detectados": danos,
    }


def traducir_imagen_bytes(contenido, nombre_imagen, modelo=None, confianza_minima=CONFIANZA_MINIMA):
    """Analiza bytes de imagen sin guardarlos en disco."""
    if modelo is None:
        modelo = cargar_modelo()

    with Image.open(BytesIO(contenido)) as imagen:
        imagen_rgb = imagen.convert("RGB")

    with _PREDICTION_LOCK:
        resultado = modelo.predict(
            source=imagen_rgb, conf=confianza_minima, imgsz=IMGSZ, verbose=False
        )[0]

    danos = traducir_resultado(resultado)
    return {
        "imagen": nombre_imagen,
        "tipos_detectados": sorted({dano["tipo_dano"] for dano in danos}),
        "danos_detectados": danos,
    }


def encontrar_imagen_de_prueba():
    """
    Si no se pasa ninguna imagen por linea de comandos, busca
    automaticamente la primera del dataset de prueba de CarDD.
    """
    carpeta_test = BASE_DIR / "carsdd" / "test" / "images"
    imagenes = sorted(carpeta_test.glob("*.jpg"))
    if not imagenes:
        raise SystemExit(
            f"No se encontraron imagenes de prueba en: {carpeta_test}\n"
            "Pasa una imagen como argumento o descarga el dataset (ver ENTRENAMIENTO_CARDD.md)."
        )
    return imagenes[0]


def main():
    if len(sys.argv) >= 2:
        ruta_imagen = sys.argv[1]
    else:
        ruta_imagen = encontrar_imagen_de_prueba()
        print(f"(No se dio una imagen, usando de ejemplo: {ruta_imagen.name})\n")

    confianza_minima = float(sys.argv[2]) if len(sys.argv) >= 3 else CONFIANZA_MINIMA

    salida = traducir_imagen(ruta_imagen, confianza_minima=confianza_minima)
    print(json.dumps(salida, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
