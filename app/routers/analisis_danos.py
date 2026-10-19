import logging
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.core.dependencies import get_usuario_con_rol
from app.services.traducir_salida_yolo import traducir_imagen_bytes

router = APIRouter()
logger = logging.getLogger(__name__)

TAMANO_MAXIMO_BYTES = 10 * 1024 * 1024
PIXELES_MAXIMOS = 40_000_000
TIPOS_CONTENIDO_PERMITIDOS = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


@router.post("/analisis/danos")
async def analizar_danos(
    imagen: UploadFile = File(..., description="Imagen del vehículo (JPEG, PNG o WEBP)"),
    usuario: dict = Depends(get_usuario_con_rol),
):
    """Detecta daños en una imagen usando el modelo YOLO entrenado con CarDD."""
    try:
        contenido = await imagen.read(TAMANO_MAXIMO_BYTES + 1)
    finally:
        await imagen.close()

    if not contenido:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La imagen está vacía")
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="La imagen supera el límite de 10 MB",
        )

    tipo_contenido = (imagen.content_type or "").split(";", 1)[0].lower()
    formato_esperado = TIPOS_CONTENIDO_PERMITIDOS.get(tipo_contenido)
    if formato_esperado is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Formato no permitido. Usa una imagen JPEG, PNG o WEBP",
        )

    try:
        with Image.open(BytesIO(contenido)) as archivo_imagen:
            formato_real = archivo_imagen.format
            ancho, alto = archivo_imagen.size
            archivo_imagen.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no contiene una imagen válida",
        ) from error

    if formato_real != formato_esperado:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="El tipo de contenido no coincide con el formato real de la imagen",
        )
    if ancho * alto > PIXELES_MAXIMOS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="La imagen supera el máximo permitido de 40 megapíxeles",
        )

    try:
        return traducir_imagen_bytes(contenido, imagen.filename or "imagen")
    except FileNotFoundError as error:
        logger.error("No está disponible el modelo YOLO: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El modelo de análisis de daños no está disponible",
        ) from error
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo decodificar la imagen",
        ) from error
    except Exception as error:
        logger.exception("Error al analizar la imagen con YOLO")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo completar el análisis de daños",
        ) from error
