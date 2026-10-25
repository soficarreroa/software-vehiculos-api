"""
Verifica que una foto sea lo bastante clara para analizarla con YOLO.

Devuelve un mensaje de error en espanol si la foto no sirve (muy pequena o
borrosa) o None si esta bien. Solo usa Pillow y numpy (ya vienen instalados
junto con ultralytics), no agrega dependencias nuevas.

Como se mide la nitidez: se pasa la foto a escala de grises, se reduce a un
maximo de LADO_ANALISIS px (para que la medida no dependa de la resolucion de
la camara) y se calcula la varianza del Laplaciano. Una foto nitida tiene
muchos bordes definidos (varianza alta); una borrosa los pierde (varianza ~0).

IMPORTANTE: UMBRAL_NITIDEZ se calibro con las 31 fotos de ml/resultados/
set_fotos_extra/anotadas/ (las nitidas dieron >= 35 y las mismas fotos con
desenfoque fuerte dieron ~2-3). Se dejo conservador (10) para no rechazar fotos
buenas. Cuando haya un set de fotos limpias, conviene recalibrarlo.
"""

from io import BytesIO

import numpy as np
from PIL import Image

LADO_MENOR_MINIMO = 200  # px; el modelo usa imgsz=320, menos que esto no es util
LADO_ANALISIS = 640  # px; tamano al que se reduce la foto para medir nitidez
UMBRAL_NITIDEZ = 10.0  # varianza del Laplaciano por debajo de la cual es borrosa

MENSAJE_POCA_RESOLUCION = (
    f"La foto tiene muy poca resolución (mínimo {LADO_MENOR_MINIMO} px por lado). "
    "Toma otra foto con la cámara a mayor calidad"
)
MENSAJE_BORROSA = (
    "La foto está borrosa o poco clara. Toma otra con buena luz, enfocada "
    "y más cerca del daño"
)


def medir_nitidez(imagen: Image.Image) -> float:
    """Varianza del Laplaciano de la foto en escala de grises (mas alto = mas nitida)."""
    gris = imagen.convert("L")
    ancho, alto = gris.size
    escala = LADO_ANALISIS / max(ancho, alto)
    if escala < 1:
        gris = gris.resize((max(1, round(ancho * escala)), max(1, round(alto * escala))), Image.LANCZOS)

    pixeles = np.asarray(gris, dtype=np.float64)
    if pixeles.shape[0] < 3 or pixeles.shape[1] < 3:
        return 0.0
    laplaciano = (
        -4 * pixeles[1:-1, 1:-1]
        + pixeles[:-2, 1:-1]
        + pixeles[2:, 1:-1]
        + pixeles[1:-1, :-2]
        + pixeles[1:-1, 2:]
    )
    return float(laplaciano.var())


def verificar_calidad_imagen(contenido: bytes) -> str | None:
    """None si la foto es aceptable; si no, el mensaje que se le muestra al usuario."""
    with Image.open(BytesIO(contenido)) as imagen:
        if min(imagen.size) < LADO_MENOR_MINIMO:
            return MENSAJE_POCA_RESOLUCION
        if medir_nitidez(imagen) < UMBRAL_NITIDEZ:
            return MENSAJE_BORROSA
    return None
