"""
Prueba el manejo de errores de la tarea #39 en POST /api/v1/analisis/danos:

- Foto demasiado pequena -> 422
- Foto borrosa o sin detalle (lisa) -> 422
- Foto nitida valida sin danos -> 200 con danos_detectados vacio y un "mensaje"
- Foto nitida valida con danos -> 200 y "mensaje" en None

El modelo YOLO se reemplaza por una respuesta simulada para que la prueba sea
rapida y no dependa de los pesos del modelo: aqui solo se prueba la logica del
endpoint (calidad de la foto y mensaje), no la deteccion en si.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import io

import numpy as np
from PIL import Image, ImageFilter
from fastapi.testclient import TestClient

from app.core.dependencies import get_usuario_con_rol
from app.main import app
from app.routers import analisis_danos

app.dependency_overrides[get_usuario_con_rol] = lambda: {"id": 1, "correo": "t@test.com", "rol": "cliente", "activo": True}
cliente = TestClient(app)

resultados = []


def jpeg(imagen):
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def foto_nitida(ancho=800, alto=600):
    """Foto sintetica con mucho detalle (ruido), equivale a una foto enfocada."""
    generador = np.random.default_rng(0)
    ruido = generador.integers(0, 256, (alto, ancho, 3), dtype=np.uint8)
    return Image.fromarray(ruido, "RGB")


def enviar(nombre_archivo, contenido):
    return cliente.post("/api/v1/analisis/danos", files={"imagen": (nombre_archivo, contenido, "image/jpeg")})


def registrar(nombre, correcto, detalle=""):
    resultados.append((nombre, correcto))
    print(f"[{'OK ' if correcto else 'FALLO'}] {nombre}  {detalle}")


# Modelo simulado: devuelve lo que cada prueba necesite.
respuesta_modelo = {"danos_detectados": []}


def modelo_falso(contenido, nombre):
    return {"imagen": nombre, "tipos_detectados": [], **respuesta_modelo}


analisis_danos.traducir_imagen_bytes = modelo_falso

# 1) Foto demasiado pequena -> 422
respuesta = enviar("pequena.jpg", jpeg(foto_nitida(150, 150)))
registrar("Foto demasiado pequena (150x150) -> 422", respuesta.status_code == 422, respuesta.json().get("detail", ""))

# 2) Foto borrosa -> 422
respuesta = enviar("borrosa.jpg", jpeg(foto_nitida().filter(ImageFilter.GaussianBlur(15))))
registrar("Foto borrosa -> 422", respuesta.status_code == 422, respuesta.json().get("detail", ""))

# 3) Foto lisa, sin detalle (todo blanco) -> 422
respuesta = enviar("lisa.jpg", jpeg(Image.new("RGB", (800, 600), "white")))
registrar("Foto lisa sin detalle -> 422", respuesta.status_code == 422, respuesta.json().get("detail", ""))

# 4) Foto nitida, el modelo no encuentra danos -> 200 con mensaje
respuesta_modelo["danos_detectados"] = []
respuesta = enviar("limpia.jpg", jpeg(foto_nitida()))
cuerpo = respuesta.json() if respuesta.status_code == 200 else {}
registrar(
    "Foto nitida sin danos -> 200, lista vacia y mensaje",
    respuesta.status_code == 200 and cuerpo.get("danos_detectados") == [] and cuerpo.get("mensaje") == analisis_danos.MENSAJE_SIN_DANOS,
    str(cuerpo.get("mensaje")),
)

# 5) Foto nitida con un dano detectado -> 200 y mensaje en None
respuesta_modelo["danos_detectados"] = [{"tipo_dano": "rayon", "confianza": 0.9}]
respuesta = enviar("con_dano.jpg", jpeg(foto_nitida()))
cuerpo = respuesta.json() if respuesta.status_code == 200 else {}
registrar(
    "Foto nitida con dano -> 200 y mensaje en None",
    respuesta.status_code == 200 and len(cuerpo.get("danos_detectados", [])) == 1 and cuerpo.get("mensaje") is None,
)

# 6) Fotos reales del repo (si estan): la nitida pasa y la misma foto muy desenfocada se rechaza.
#    El desenfoque es proporcional al tamano de la foto (hay fotos de 24 MP y de 640 px).
carpeta = BASE_DIR / "ml" / "resultados" / "set_fotos_extra" / "anotadas"
fotos_reales = sorted(carpeta.glob("*.jp*g")) if carpeta.is_dir() else []
if fotos_reales:
    nitidas_ok = 0
    borrosas_rechazadas = 0
    for ruta in fotos_reales:
        original = Image.open(ruta).convert("RGB")
        nitidas_ok += enviar(ruta.name, jpeg(original)).status_code == 200
        borrosas_rechazadas += enviar(ruta.name, jpeg(original.filter(ImageFilter.GaussianBlur(max(original.size) / 100)))).status_code == 422
    total = len(fotos_reales)
    registrar(f"Fotos reales nitidas aceptadas ({nitidas_ok}/{total})", nitidas_ok == total)
    registrar(f"Mismas fotos con desenfoque fuerte rechazadas ({borrosas_rechazadas}/{total})", borrosas_rechazadas == total)
else:
    print("(No hay fotos reales en ml/resultados/set_fotos_extra/anotadas, se omite la prueba 6)")

print("\nResumen:")
for nombre, correcto in resultados:
    print(f"  {'OK ' if correcto else 'FALLO'}  {nombre}")
total_ok = sum(1 for _, correcto in resultados if correcto)
print(f"\n{total_ok}/{len(resultados)} casos correctos")
