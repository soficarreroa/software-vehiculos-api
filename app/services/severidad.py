"""Estimacion preliminar de severidad (leve / moderado / grave) de un dano detectado.

IMPORTANTE: es una linea base basada en el TAMANO relativo del dano (area de la mascara
sobre el area de la foto) comparado con los danos del mismo tipo en CarDD. No mide
profundidad, ni si hay pieza rota o expuesta (criterios del informe de clases), ni usa
tamanos reales en cm. Los umbrales salen de calcular_umbrales_severidad.py y deben
validarse con etiquetas manuales (validar_severidad.py) antes de usarse en cotizaciones.
"""

import json
from pathlib import Path

UMBRALES_PATH = Path(__file__).resolve().with_name("severidad_umbrales.json")
NIVELES = ("leve", "moderado", "grave")

# (tipo de dano, nivel) -> etiqueta de la tabla de costos (18 clases del proyecto)
ETIQUETAS_COSTO = {
    ("abolladura", "leve"): "abolladura_leve",
    ("abolladura", "moderado"): "abolladura_moderada",
    ("abolladura", "grave"): "abolladura_grave",
    ("rayon", "leve"): "rayon_leve",
    ("rayon", "moderado"): "rayon_moderado",
    ("rayon", "grave"): "rayon_grave",
    ("grieta", "leve"): "grieta_leve",
    ("grieta", "moderado"): "grieta_moderada",
    ("grieta", "grave"): "grieta_grave",
    ("vidrio_roto", "leve"): "vidrio_roto_leve",
    ("vidrio_roto", "moderado"): "vidrio_roto_moderado",
    ("vidrio_roto", "grave"): "vidrio_roto_grave",
    ("luz_rota", "leve"): "luz_rota_leve",
    ("luz_rota", "moderado"): "luz_rota_moderada",
    ("luz_rota", "grave"): "luz_rota_grave",
    ("llanta_baja", "leve"): "llanta_baja_leve",
    ("llanta_baja", "moderado"): "llanta_baja_moderada",
    ("llanta_baja", "grave"): "llanta_baja_grave",
}


def area_poligono(puntos):
    """Area (formula del cordon) de un poligono dado como lista de (x, y)."""
    puntos = [(float(x), float(y)) for x, y in puntos]
    if len(puntos) < 3:
        return 0.0
    suma = 0.0
    for i, (x1, y1) in enumerate(puntos):
        x2, y2 = puntos[(i + 1) % len(puntos)]
        suma += x1 * y2 - x2 * y1
    return abs(suma) / 2.0


def cargar_umbrales(ruta=None):
    """Devuelve el diccionario de umbrales por clase, o None si el archivo no existe."""
    ruta = Path(ruta) if ruta else UMBRALES_PATH
    if not ruta.is_file():
        return None
    with ruta.open(encoding="utf-8") as archivo:
        return json.load(archivo).get("umbrales")


def estimar_severidad(clase_yolo, area_relativa, umbrales=None):
    """Devuelve 'leve', 'moderado' o 'grave'; None si no hay umbrales para esa clase."""
    if umbrales is None:
        umbrales = cargar_umbrales()
    if not umbrales or clase_yolo not in umbrales:
        return None
    corte = umbrales[clase_yolo]
    if area_relativa <= corte["leve_hasta"]:
        return "leve"
    if area_relativa <= corte["moderado_hasta"]:
        return "moderado"
    return "grave"


def etiqueta_costo(tipo_dano, severidad):
    """Etiqueta de la tabla de costos (por ejemplo 'rayon_moderado'), o None."""
    return ETIQUETAS_COSTO.get((tipo_dano, severidad))
