"""
Prueba el endpoint real POST /api/v1/analisis/danos (no el modelo directamente)
contra fotos de danos, y compara la deteccion contra la etiqueta real que trae
cada nombre de archivo:  <tipo>__<severidad>__<numero>.<ext>

Usa FastAPI TestClient (manda peticiones HTTP de verdad al app de FastAPI,
incluyendo la validacion de archivos) y sobreescribe SOLO la dependencia de
autenticacion (get_usuario_con_rol) para no depender de un login real de
Supabase; todo lo demas (lectura del archivo, validaciones, inferencia de
YOLO, armado de la respuesta) corre tal cual corre en produccion.

IMPORTANTE: las unicas fotos versionadas en el repo (ml/resultados/set_fotos_extra/anotadas/)
ya tienen cajas y etiquetas de una evaluacion anterior dibujadas encima (vienen de
probar_set_fotos.py / probar_cardd.py, que guardan la imagen ya anotada). Correr
este script contra esas fotos NO es una prueba representativa: la deteccion se hace
sobre una imagen "contaminada" con texto y cajas de colores superpuestos, no sobre
la foto original. Para una prueba real, pasa la ruta de un set de fotos SIN anotar
por --fotos (ver mas abajo) o copia aqui el set original del equipo.
"""
import csv
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from app.core.dependencies import get_usuario_con_rol
from app.main import app

FOTOS_DIR = (
    Path(sys.argv[1]) if len(sys.argv) >= 2
    else REPO_ROOT / "ml" / "resultados" / "set_fotos_extra" / "anotadas"
)
SALIDA_CSV = Path(__file__).resolve().parent / "resultados_prueba_endpoint.csv"

app.dependency_overrides[get_usuario_con_rol] = lambda: {
    "id": 1, "correo": "prueba@test.com", "rol": "cliente", "activo": True
}

cliente = TestClient(app)

TIPOS_CONTENIDO = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def principal():
    fotos = sorted(FOTOS_DIR.glob("*"))
    fotos = [f for f in fotos if f.suffix.lower() in TIPOS_CONTENIDO]
    print(f"Probando {len(fotos)} fotos contra el endpoint real (carpeta: {FOTOS_DIR})...\n")

    filas = []
    for foto in fotos:
        partes = foto.stem.split("__")
        tipo_esperado = partes[0] if len(partes) >= 1 else "?"
        severidad_esperada = partes[1] if len(partes) >= 2 else "?"

        with foto.open("rb") as f:
            inicio = time.time()
            respuesta = cliente.post(
                "/api/v1/analisis/danos",
                files={"imagen": (foto.name, f, TIPOS_CONTENIDO[foto.suffix.lower()])},
            )
            duracion = round(time.time() - inicio, 2)

        if respuesta.status_code != 200:
            print(f"{foto.name}: ERROR HTTP {respuesta.status_code} -> {respuesta.text[:150]}")
            filas.append({
                "archivo": foto.name, "tipo_esperado": tipo_esperado,
                "severidad_esperada": severidad_esperada, "status_http": respuesta.status_code,
                "tipos_detectados": "", "num_danos": 0, "confianza_max": "",
                "severidad_detectada": "", "tiempo_seg": duracion,
            })
            continue

        data = respuesta.json()
        danos = data.get("danos_detectados", [])
        tipos = data.get("tipos_detectados", [])
        confianza_maxima = max((d["confianza"] for d in danos), default=0)
        severidades = sorted({d["severidad"] for d in danos if d.get("severidad")})

        print(f"{foto.name}: esperado={tipo_esperado}/{severidad_esperada} | "
              f"detectado={tipos or 'NADA'} | severidad={severidades or '-'} | "
              f"confianza_max={confianza_maxima:.2f} | {duracion}s")

        filas.append({
            "archivo": foto.name, "tipo_esperado": tipo_esperado,
            "severidad_esperada": severidad_esperada, "status_http": respuesta.status_code,
            "tipos_detectados": ";".join(tipos), "num_danos": len(danos),
            "confianza_max": round(confianza_maxima, 3), "severidad_detectada": ";".join(severidades),
            "tiempo_seg": duracion,
        })

    with SALIDA_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)

    sin_deteccion = sum(1 for r in filas if r["num_danos"] == 0)
    print(f"\nTotal: {len(filas)} fotos | sin ninguna deteccion: {sin_deteccion}")
    print(f"Resultados guardados en: {SALIDA_CSV}")


if __name__ == "__main__":
    principal()
