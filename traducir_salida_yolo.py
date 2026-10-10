"""
Traduce la salida cruda de YOLO (boxes, clases numericas, confianza,
mascaras de segmentacion) a un formato mas  simple: una lista de
diccionarios con los datos esenciales de cada dano detectado.
"""

import json
import sys
from pathlib import Path

from ultralytics import YOLO

MODEL_PATH = Path(__file__).resolve().parent / "models" / "segmentador_danos" / "best.pt"


def traducir_resultado(result): 
    """
    Convierte un objeto Results de Ultralytics (la salida cruda de
    model.predict) en una lista simple de diccionarios, uno por cada
    daño detectado en la imagen. 
    """
    danos = []

    if result.boxes is None:
        return danos

    nombres_clases = result.names
    mascaras = result.masks.xy if result.masks is not None else []

    for i, box in enumerate(result.boxes):
        x1, y1, x2, y2 = [round(v, 1) for v in box.xyxy[0].tolist()]
        clase_id = int(box.cls.item())
        confianza = round(float(box.conf.item()), 3)

        dano = {
            "tipo_dano": nombres_clases[clase_id],
            "confianza": confianza,
            "ubicacion": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            "ancho": round(x2 - x1, 1),
            "alto": round(y2 - y1, 1),
            "tiene_contorno": i < len(mascaras),
        }
        danos.append(dano)

    danos.sort(key=lambda d: d["confianza"], reverse=True)
    return danos


def traducir_imagen(ruta_imagen, modelo=None, confianza_minima=0.25):
    """
    Carga el modelo, si no se pasa uno ya cargado, corre la deteccion
    sobre una imagen y devuelve el resultado en formato simple.
    """
    if modelo is None:
        modelo = YOLO(str(MODEL_PATH))

    resultado = modelo.predict(
        source=str(ruta_imagen), conf=confianza_minima, verbose=False
    )[0]

    return {
        "imagen": str(ruta_imagen),
        "danos_detectados": traducir_resultado(resultado),
    }


def encontrar_imagen_de_prueba():
    """
    Si no se pasa ninguna imagen por linea de comandos, busca
    automaticamente la primera del dataset de prueba de danos.
    """
    carpeta_test = Path(__file__).resolve().parent / "Car Damage Images.v3i.yolov8" / "test" / "images"
    imagenes = sorted(carpeta_test.glob("*.jpg"))
    if not imagenes:
        raise SystemExit(f"No se encontraron imagenes de prueba en: {carpeta_test}")
    return imagenes[0]


def main():
    if len(sys.argv) >= 2:
        ruta_imagen = sys.argv[1]
    else:
        ruta_imagen = encontrar_imagen_de_prueba()
        print(f"(No se dio una imagen, usando de ejemplo: {ruta_imagen.name})\n")

    confianza_minima = float(sys.argv[2]) if len(sys.argv) >= 3 else 0.25

    salida = traducir_imagen(ruta_imagen, confianza_minima=confianza_minima)
    print(json.dumps(salida, indent=2, ensure_ascii=False))

    
if __name__ == "__main__":
    main()