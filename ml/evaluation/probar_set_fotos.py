"""Prueba el modelo CarDD (models/segmentador_cardd/best.pt) contra un set de fotos
etiquetado por carpetas <raiz>/<tipo>/<severidad>/<archivo>.jpg y genera una tabla
comparativa de aciertos y fallos de tipo de dano y de severidad.

Reutiliza app/services/traducir_salida_yolo.traducir_imagen (que a su vez usa
app/services/severidad.py) en lugar de duplicar la logica del modelo.

Uso (desde la raiz del repo):
    python -m ml.evaluation.probar_set_fotos <ruta_raiz>
    python -m ml.evaluation.probar_set_fotos <ruta_raiz> --conf 0.25
    python -m ml.evaluation.probar_set_fotos <ruta_raiz> --salida <carpeta>

Salidas (por defecto en ml/resultados/set_fotos/):
    resultados_por_foto.csv, resumen_por_categoria.csv, matriz_confusion_tipo.csv
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image

BASE_DIR = next(
    (p for p in Path(__file__).resolve().parents if (p / "requirements.txt").is_file()),
    Path(__file__).resolve().parent,
)
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.traducir_salida_yolo import MODEL_PATH, traducir_imagen
from app.services.severidad import NIVELES
from ultralytics import YOLO

EXTENSIONES = {".jpg", ".jpeg", ".png", ".webp"}
SALIDA_POR_DEFECTO = BASE_DIR / "ml" / "resultados" / "set_fotos"
SIN_DETECCION = "sin_deteccion"

# Clase cruda del modelo (ingles, confirmado en traducir_salida_yolo.TIPOS_DANO) -> tipo del set.
MAPEO_TIPO = {
    "dent": "abolladura",
    "scratch": "rayon",
    "glass shatter": "rotura",
    "lamp broken": "rotura",
    "crack": "rotura",
    "tire flat": "sin_equivalente",
}

# Nivel que devuelve severidad.py (NIVELES) -> severidad del set.
MAPEO_SEVERIDAD = {
    "leve": "leve",
    "moderado": "moderado",
    "grave": "severo",
}

COLUMNAS_FOTO = [
    "archivo",
    "tipo_esperado",
    "severidad_esperada",
    "clase_modelo",
    "tipo_detectado",
    "severidad_detectada",
    "confianza",
    "area_relativa",
    "num_detecciones",
    "acierto_tipo",
    "acierto_severidad",
    "acierto_tipo_en_alguna_deteccion",
    "motivo_fallo",
]


def mapear_tipo(clase_yolo, tipo_dano=None):
    if clase_yolo in MAPEO_TIPO:
        return MAPEO_TIPO[clase_yolo]
    return tipo_dano


def mapear_severidad(severidad):
    if severidad is None:
        return None
    return MAPEO_SEVERIDAD.get(severidad, severidad)


def fila_sin_deteccion(archivo, tipo_esperado, severidad_esperada, motivo):
    return {
        "archivo": archivo,
        "tipo_esperado": tipo_esperado,
        "severidad_esperada": severidad_esperada,
        "clase_modelo": None,
        "tipo_detectado": None,
        "severidad_detectada": None,
        "confianza": None,
        "area_relativa": None,
        "num_detecciones": 0,
        "acierto_tipo": False,
        "acierto_severidad": False,
        "acierto_tipo_en_alguna_deteccion": False,
        "motivo_fallo": motivo,
    }


def construir_fila(archivo, tipo_esperado, severidad_esperada, danos):
    if not danos:
        return fila_sin_deteccion(archivo, tipo_esperado, severidad_esperada, "sin detección")

    principal = max(danos, key=lambda d: d["confianza"])
    clase_modelo = principal.get("clase_yolo")
    tipo_detectado = mapear_tipo(clase_modelo, principal.get("tipo_dano"))
    severidad_detectada = mapear_severidad(principal.get("severidad"))

    acierto_tipo = tipo_detectado == tipo_esperado
    acierto_severidad = severidad_detectada == severidad_esperada
    acierto_en_alguna = any(
        mapear_tipo(d.get("clase_yolo"), d.get("tipo_dano")) == tipo_esperado for d in danos
    )

    if clase_modelo == "tire flat":
        motivo = "clase sin equivalente"
    elif not acierto_tipo:
        motivo = "tipo incorrecto"
    elif not acierto_severidad:
        motivo = "severidad incorrecta"
    else:
        motivo = ""

    return {
        "archivo": archivo,
        "tipo_esperado": tipo_esperado,
        "severidad_esperada": severidad_esperada,
        "clase_modelo": clase_modelo,
        "tipo_detectado": tipo_detectado,
        "severidad_detectada": severidad_detectada,
        "confianza": principal.get("confianza"),
        "area_relativa": principal.get("area_relativa"),
        "num_detecciones": len(danos),
        "acierto_tipo": acierto_tipo,
        "acierto_severidad": acierto_severidad,
        "acierto_tipo_en_alguna_deteccion": acierto_en_alguna,
        "motivo_fallo": motivo,
    }


def es_legible(ruta):
    try:
        with Image.open(ruta) as imagen:
            imagen.verify()
        return True
    except Exception:
        return False


def dividir_etiqueta(raiz, ruta):
    partes = ruta.relative_to(raiz).parts
    tipo_esperado = partes[-3] if len(partes) >= 3 else ""
    severidad_esperada = partes[-2] if len(partes) >= 2 else ""
    return tipo_esperado, severidad_esperada


def iterar_imagenes(raiz):
    for ruta in sorted(raiz.rglob("*")):
        if ruta.is_file() and ruta.suffix.lower() in EXTENSIONES:
            yield ruta


def procesar_imagen(raiz, ruta, modelo, confianza_minima):
    archivo = ruta.relative_to(raiz).as_posix()
    tipo_esperado, severidad_esperada = dividir_etiqueta(raiz, ruta)

    if not es_legible(ruta):
        return fila_sin_deteccion(archivo, tipo_esperado, severidad_esperada, "imagen ilegible")

    try:
        resultado = traducir_imagen(ruta, modelo=modelo, confianza_minima=confianza_minima)
    except Exception as error:
        return fila_sin_deteccion(
            archivo, tipo_esperado, severidad_esperada, f"imagen ilegible (error al predecir: {error})"
        )

    return construir_fila(archivo, tipo_esperado, severidad_esperada, resultado["danos_detectados"])


def clave_detectada(fila):
    if fila["motivo_fallo"].startswith("imagen ilegible"):
        return "imagen_ilegible"
    if fila["num_detecciones"] == 0:
        return SIN_DETECCION
    return fila["tipo_detectado"]


def escribir_csv(ruta, columnas, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)


def agrupar(filas, clave):
    grupos = defaultdict(lambda: {"tipo": 0, "severidad": 0, "total": 0})
    for fila in filas:
        acumulado = grupos[clave(fila)]
        acumulado["tipo"] += int(bool(fila["acierto_tipo"]))
        acumulado["severidad"] += int(bool(fila["acierto_severidad"]))
        acumulado["total"] += 1
    return grupos


def resumen_por_grupos(grupos):
    for valor in sorted(grupos):
        datos = grupos[valor]
        for metrica in ("tipo", "severidad"):
            aciertos = datos[metrica]
            total = datos["total"]
            yield {
                "valor": valor,
                "metrica": metrica,
                "aciertos": aciertos,
                "total": total,
                "porcentaje": round(100 * aciertos / total, 1) if total else 0.0,
            }


def escribir_resumen(ruta, filas):
    filas_csv = []
    for agrupacion, clave in (
        ("tipo_esperado", lambda f: f["tipo_esperado"]),
        ("severidad_esperada", lambda f: f["severidad_esperada"]),
        ("combinacion", lambda f: f"{f['tipo_esperado']}/{f['severidad_esperada']}"),
    ):
        for fila in resumen_por_grupos(agrupar(filas, clave)):
            filas_csv.append({"agrupacion": agrupacion, **fila})
    escribir_csv(ruta, ["agrupacion", "valor", "metrica", "aciertos", "total", "porcentaje"], filas_csv)
    return filas_csv


def escribir_matriz_confusion(ruta, filas):
    esperados = sorted({fila["tipo_esperado"] for fila in filas})
    detectadas = sorted({clave_detectada(fila) for fila in filas})
    columnas = ["esperado", *detectadas, "total"]

    conteo = defaultdict(lambda: defaultdict(int))
    for fila in filas:
        conteo[fila["tipo_esperado"]][clave_detectada(fila)] += 1

    filas_csv = []
    for esperado in esperados:
        fila = {"esperado": esperado}
        for detectada in detectadas:
            fila[detectada] = conteo[esperado][detectada]
        fila["total"] = sum(conteo[esperado].values())
        filas_csv.append(fila)

    escribir_csv(ruta, columnas, filas_csv)
    return columnas, filas_csv


def imprimir_resumen(filas_csv, columnas_matriz, matriz):
    print("\n=== Resumen (aciertos/total = %) ===")
    agrupacion_actual = None
    for fila in filas_csv:
        if fila["agrupacion"] != agrupacion_actual:
            agrupacion_actual = fila["agrupacion"]
            print(f"\n-- por {agrupacion_actual} --")
        print(
            f"  {fila['valor']:<18} {fila['metrica']:<9} "
            f"{fila['aciertos']}/{fila['total']}  {fila['porcentaje']:.1f}%"
        )

    print("\n=== Matriz de confusion de tipo (esperado x detectado) ===")
    ancho = max(len(fila["esperado"]) for fila in matriz) if matriz else 0
    print(f"  {'esperado'.ljust(ancho)} | " + " ".join(f"{c:>{len(c)}}" for c in columnas_matriz[1:]))
    for fila in matriz:
        valores = " ".join(f"{fila[c]:>{len(c)}}" for c in columnas_matriz[1:])
        print(f"  {fila['esperado'].ljust(ancho)} | {valores}")


def parse_args():
    parser = argparse.ArgumentParser(description="Prueba el modelo CarDD contra un set de fotos por carpetas")
    parser.add_argument("raiz", help="Carpeta raiz con estructura <tipo>/<severidad>/<archivo>")
    parser.add_argument("--conf", type=float, default=0.25, help="Confianza minima (por defecto 0.25)")
    parser.add_argument("--salida", default=str(SALIDA_POR_DEFECTO), help="Carpeta de salida de los CSV")
    return parser.parse_args()


def main():
    args = parse_args()
    raiz = Path(args.raiz)
    if not raiz.is_dir():
        raise SystemExit(f"No se encontro la carpeta raiz: {raiz}")
    if not MODEL_PATH.is_file():
        raise SystemExit(f"No se encontro el modelo: {MODEL_PATH}")

    imagenes = list(iterar_imagenes(raiz))
    if not imagenes:
        raise SystemExit(f"No hay imagenes en: {raiz}")

    print(f"Raiz: {raiz}")
    print(f"Modelo: {MODEL_PATH} | confianza minima: {args.conf} | imagenes: {len(imagenes)}")

    modelo = YOLO(str(MODEL_PATH))
    filas = [procesar_imagen(raiz, ruta, modelo, args.conf) for ruta in imagenes]

    salida = Path(args.salida)
    escribir_csv(salida / "resultados_por_foto.csv", COLUMNAS_FOTO, filas)
    filas_resumen = escribir_resumen(salida / "resumen_por_categoria.csv", filas)
    columnas_matriz, matriz = escribir_matriz_confusion(salida / "matriz_confusion_tipo.csv", filas)

    imprimir_resumen(filas_resumen, columnas_matriz, matriz)
    print(f"\nCSV guardados en: {salida}")


if __name__ == "__main__":
    main()
