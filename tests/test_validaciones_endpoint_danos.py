"""
Prueba los casos de error y validacion del endpoint POST /api/v1/analisis/danos:
sin autenticacion, sin archivo, archivo vacio, formato no soportado, imagen
corrupta, imagen muy grande (bytes) y confirma que una imagen valida sin danos
devuelve una lista vacia en vez de un error.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import io
from PIL import Image
from fastapi.testclient import TestClient

from app.core.dependencies import get_usuario_con_rol
from app.main import app

cliente_sin_override = TestClient(app)

resultados = []


def probar(nombre, respuesta, status_esperado):
    correcto = respuesta.status_code == status_esperado
    resultados.append((nombre, respuesta.status_code, status_esperado, correcto))
    detalle = ""
    try:
        detalle = respuesta.json().get("detail", "")
    except Exception:
        pass
    marca = "OK " if correcto else "FALLO"
    print(f"[{marca}] {nombre}: esperado={status_esperado} obtuvo={respuesta.status_code}  {detalle}")


# 1) Sin token de autenticacion -> 401
imagen_prueba = io.BytesIO()
Image.new("RGB", (100, 100), "white").save(imagen_prueba, format="JPEG")
imagen_prueba.seek(0)
respuesta = cliente_sin_override.post("/api/v1/analisis/danos", files={"imagen": ("foto.jpg", imagen_prueba, "image/jpeg")})
probar("Sin token de autenticacion", respuesta, 401)

# A partir de aqui, simulamos un usuario autenticado (no probamos login, eso ya se valido en la tarea de login)
app.dependency_overrides[get_usuario_con_rol] = lambda: {"id": 1, "correo": "t@test.com", "rol": "cliente", "activo": True}
cliente = TestClient(app)

# 2) Archivo vacio -> 400
respuesta = cliente.post("/api/v1/analisis/danos", files={"imagen": ("vacia.jpg", b"", "image/jpeg")})
probar("Imagen vacia (0 bytes)", respuesta, 400)

# 3) Formato no soportado (gif) -> 415
respuesta = cliente.post("/api/v1/analisis/danos", files={"imagen": ("foto.gif", b"GIF89a....", "image/gif")})
probar("Formato no soportado (gif)", respuesta, 415)

# 4) content-type no coincide con el contenido real (dice jpeg pero es texto) -> 400
respuesta = cliente.post("/api/v1/analisis/danos", files={"imagen": ("falsa.jpg", b"esto no es una imagen", "image/jpeg")})
probar("Archivo corrupto / no es imagen real", respuesta, 400)

# 5) Imagen valida de 100x100 blanca, sin ningun dano -> 200 con lista vacia
imagen_pequena = io.BytesIO()
Image.new("RGB", (100, 100), "white").save(imagen_pequena, format="JPEG")
imagen_pequena.seek(0)
respuesta = cliente.post("/api/v1/analisis/danos", files={"imagen": ("blanco.jpg", imagen_pequena, "image/jpeg")})
ok_200 = respuesta.status_code == 200
danos = respuesta.json().get("danos_detectados", []) if ok_200 else None
print(f"[{'OK ' if ok_200 else 'FALLO'}] Imagen sin danos (blanco liso): status={respuesta.status_code} danos_detectados={danos}")
resultados.append(("Imagen sin danos -> 200 con lista vacia", respuesta.status_code, 200, ok_200 and danos == []))

# 6) Imagen muy grande en bytes (>10MB) -> 413
grande = io.BytesIO()
Image.new("RGB", (3000, 3000), "white").save(grande, format="BMP")  # BMP sin comprimir, pesa varios MB
grande.seek(0)
contenido_grande = grande.read()
print(f"Tamano de la imagen de prueba 'grande': {len(contenido_grande) / (1024*1024):.1f} MB")
respuesta = cliente.post("/api/v1/analisis/danos", files={"imagen": ("grande.jpg", contenido_grande, "image/jpeg")})
probar("Imagen que supera el limite de 10 MB", respuesta, 413)

print("\nResumen:")
for nombre, obtenido, esperado, correcto in resultados:
    print(f"  {'OK ' if correcto else 'FALLO'}  {nombre} (esperado {esperado}, obtuvo {obtenido})")

total_ok = sum(1 for _, _, _, correcto in resultados if correcto)
print(f"\n{total_ok}/{len(resultados)} casos de validacion correctos")
