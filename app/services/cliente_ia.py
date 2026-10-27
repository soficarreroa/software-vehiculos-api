"""
Cliente HTTP del servicio de IA (software-vehiculos-ia).

El modelo YOLO ya no corre dentro de este backend: este modulo le manda la foto
al servicio de IA (POST /detectar) y devuelve la lista "detecciones" que ese
servicio responde. Asi el backend no necesita ultralytics ni PyTorch.

Variables de entorno:
    IA_SERVER_URL  URL base del servicio de IA, sin "/" final y sin "/detectar"
                   (ej. https://software-vehiculos-ia.onrender.com)
    IA_API_KEY     la misma clave que tiene la variable API_KEY del servicio de IA
    IA_TIMEOUT     (opcional) segundos maximos de espera; por defecto 120.
                   El plan gratis de Render duerme el servicio y la primera
                   foto puede tardar 1-2 minutos.
"""

import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()  # en local lee el .env; en Render las variables ya vienen del entorno

logger = logging.getLogger(__name__)

TIMEOUT_POR_DEFECTO = 120


class ServicioIAError(Exception):
    """El servicio de IA fallo o respondio algo inesperado. `estado` = codigo HTTP, si lo hubo."""

    def __init__(self, mensaje, estado=None):
        super().__init__(mensaje)
        self.estado = estado


class ServicioIANoDisponible(ServicioIAError):
    """El servicio de IA no respondio a tiempo o esta dormido / reiniciandose (timeout, 502, 503, 504)."""


def _timeout():
    try:
        return float(os.getenv("IA_TIMEOUT", TIMEOUT_POR_DEFECTO))
    except ValueError:
        return TIMEOUT_POR_DEFECTO


def detectar_danos(contenido: bytes, nombre: str, tipo: str):
    """Manda la foto al servicio de IA y devuelve su lista de detecciones.

    Cada deteccion es un diccionario como:
        {"clase": "dent", "confianza": 0.70, "bbox": [x1, y1, x2, y2], "area_pct": 16.41}

    Lanza ServicioIANoDisponible si no responde a tiempo (esta dormido o reiniciando)
    y ServicioIAError para cualquier otra falla (clave incorrecta, URL mal escrita, etc.).
    """
    url_base = (os.getenv("IA_SERVER_URL") or "").strip().rstrip("/")
    if not url_base:
        raise ServicioIAError("Falta la variable de entorno IA_SERVER_URL")

    try:
        r = requests.post(
            f"{url_base}/detectar",
            headers={"x-api-key": os.getenv("IA_API_KEY", "")},
            files={"imagen": (nombre, contenido, tipo)},
            timeout=_timeout(),
        )
    except requests.Timeout as error:
        raise ServicioIANoDisponible(
            f"El servicio de IA no respondio en {_timeout():.0f} s (puede estar despertando)"
        ) from error
    except requests.ConnectionError as error:
        raise ServicioIANoDisponible(
            f"No se pudo conectar con el servicio de IA ({url_base}): {error.__class__.__name__}"
        ) from error
    except requests.RequestException as error:
        raise ServicioIAError(f"Fallo la llamada al servicio de IA: {error.__class__.__name__}") from error

    if r.status_code in (401, 403):
        raise ServicioIAError(
            f"El servicio de IA rechazo la clave ({r.status_code}): "
            "revisa que IA_API_KEY sea igual a API_KEY del servicio de IA",
            r.status_code,
        )
    if r.status_code == 404:
        raise ServicioIAError(
            "El servicio de IA respondio 404: revisa IA_SERVER_URL "
            "(debe ser solo la URL base, sin /detectar)",
            404,
        )
    if r.status_code in (429, 502, 503, 504):
        raise ServicioIANoDisponible(
            f"El servicio de IA respondio {r.status_code} (despertando, reiniciando o sin memoria)",
            r.status_code,
        )
    if not r.ok:
        raise ServicioIAError(f"El servicio de IA respondio {r.status_code}: {r.text[:200]}", r.status_code)

    try:
        detecciones = r.json()["detecciones"]
    except (ValueError, KeyError, TypeError) as error:
        raise ServicioIAError("El servicio de IA respondio algo que no es JSON con 'detecciones'") from error
    if not isinstance(detecciones, list):
        raise ServicioIAError("El campo 'detecciones' del servicio de IA no es una lista")
    return detecciones
