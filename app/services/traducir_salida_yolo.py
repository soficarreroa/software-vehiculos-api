"""
Traduce las detecciones de dano a un formato mas simple: una lista de
diccionarios con los datos esenciales de cada dano detectado.

El modelo entrenado con CarDD (YOLO de segmentacion) YA NO se carga en este
backend: corre en un servicio aparte (software-vehiculos-ia). Aqui se le manda
la foto por HTTP (ver cliente_ia.py) y se traduce la lista "detecciones" que
responde (clase, confianza, bbox, area_pct) al mismo formato que antes devolvia
este modulo, para que analisis_danos.py y el frontend no cambien.

Los nombres de clase del modelo estan en ingles y se traducen a los tipos de
dano de la tabla de costos del proyecto. Ademas estima una severidad preliminar
(leve / moderado / grave) por tamano relativo del dano (ver severidad.py); si no
existe severidad_umbrales.json, la severidad queda en None.

cargar_modelo, traducir_resultado y traducir_imagen se conservan SOLO para los
scripts de ml/ que corren el modelo en local. Importan ultralytics dentro de
cargar_modelo, asi que el servidor no lo necesita instalado.
"""

import json
import sys
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock

from PIL import Image

try:
    from .severidad import area_poligono, cargar_umbrales, estimar_severidad, etiqueta_costo
    from .cliente_ia import ServicioIAError, detectar_danos
except ImportError:  # se ejecuta como script, no como parte de un paquete
    from severidad import area_poligono, cargar_umbrales, estimar_severidad, etiqueta_costo
    from cliente_ia import ServicioIAError, detectar_danos

# Raiz del repositorio: sube de carpeta hasta encontrar requirements.txt (sirve en la raiz o en app/services/).
BASE_DIR = next((p for p in Path(__file__).resolve().parents if (p / "requirements.txt").is_file()), Path(__file__).resolve().parent)
MODEL_PATH = BASE_DIR / "models" / "segmentador_cardd_candidato_416_25" / "best.pt"

# Tamaño y umbral seleccionados al evaluar el candidato en validación de CarDD.
# CONFIANZA_MINIMA tambien se aplica a lo que responde el servicio de IA.
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
    """Carga el modelo YOLO LOCAL (solo para los scripts de ml/; el servidor usa el servicio de IA)."""
    from ultralytics import YOLO  # import tardio: el servidor no necesita ultralytics

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
    daño detectado en la imagen. (Solo para el modelo local de ml/.)
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


def traducir_detecciones(
    detecciones, ancho_img=None, alto_img=None, umbrales=None, confianza_minima=CONFIANZA_MINIMA
):
    """
    Convierte la lista "detecciones" del servicio de IA
        [{"clase": "dent", "confianza": 0.70, "bbox": [x1, y1, x2, y2], "area_pct": 16.41}]
    en la misma lista de diccionarios que antes producia traducir_resultado.

    area_pct es el area de la mascara como % de la imagen; se divide entre 100 para
    obtener area_relativa (0 a 1), que es lo que espera estimar_severidad. Si el servicio
    no manda area_pct, se usa la caja (necesita ancho_img y alto_img).
    """
    if umbrales is None:
        umbrales = cargar_umbrales()

    danos = []
    for deteccion in detecciones:
        confianza_cruda = float(deteccion["confianza"])
        if confianza_cruda < confianza_minima:
            continue

        x1, y1, x2, y2 = [round(float(v), 1) for v in deteccion["bbox"]]
        clase_yolo = deteccion["clase"]
        tipo_dano = TIPOS_DANO.get(clase_yolo, clase_yolo)

        area_pct = deteccion.get("area_pct")
        if area_pct is not None:
            area_relativa = float(area_pct) / 100.0
            tiene_contorno = True
        elif ancho_img and alto_img:
            area_relativa = min(1.0, ((x2 - x1) * (y2 - y1)) / (ancho_img * alto_img))
            tiene_contorno = False
        else:
            area_relativa = 0.0
            tiene_contorno = False

        severidad = estimar_severidad(clase_yolo, area_relativa, umbrales)

        danos.append(
            {
                "tipo_dano": tipo_dano,
                "clase_yolo": clase_yolo,
                "confianza": round(confianza_cruda, 3),
                "ubicacion": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                "ancho": round(x2 - x1, 1),
                "alto": round(y2 - y1, 1),
                "tiene_contorno": tiene_contorno,
                "area_relativa": round(area_relativa, 4),
                "severidad": severidad,
                "etiqueta_costo": etiqueta_costo(tipo_dano, severidad) if severidad else None,
            }
        )

    danos.sort(key=lambda d: d["confianza"], reverse=True)
    return danos


def traducir_imagen(ruta_imagen, modelo=None, confianza_minima=CONFIANZA_MINIMA):
    """
    Carga el modelo LOCAL, si no se pasa uno ya cargado, corre la deteccion
    sobre una imagen y devuelve el resultado en formato simple, incluyendo
    la lista de tipos de dano encontrados en la foto. (Solo para scripts de ml/.)
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


def traducir_imagen_bytes(
    contenido, nombre_imagen, modelo=None, confianza_minima=CONFIANZA_MINIMA, tipo_contenido="image/jpeg"
):
    """Analiza bytes de imagen sin guardarlos en disco.

    Por defecto le manda la foto al servicio de IA por HTTP (cliente_ia.detectar_danos).
    Si se pasa `modelo` (un YOLO ya cargado) se usa ese modelo local, como antes; eso es
    solo para pruebas y scripts, el servidor nunca lo hace.

    Puede lanzar ServicioIANoDisponible o ServicioIAError (ver cliente_ia.py).
    """
    if modelo is not None:
        with Image.open(BytesIO(contenido)) as imagen:
            imagen_rgb = imagen.convert("RGB")

        with _PREDICTION_LOCK:
            resultado = modelo.predict(
                source=imagen_rgb, conf=confianza_minima, imgsz=IMGSZ, verbose=False
            )[0]

        danos = traducir_resultado(resultado)
    else:
        with Image.open(BytesIO(contenido)) as imagen:
            ancho_img, alto_img = imagen.size

        detecciones = detectar_danos(contenido, nombre_imagen, tipo_contenido)
        try:
            danos = traducir_detecciones(
                detecciones, ancho_img, alto_img, confianza_minima=confianza_minima
            )
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise ServicioIAError(
                f"El servicio de IA devolvio detecciones con formato inesperado: {error!r}"
            ) from error

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
