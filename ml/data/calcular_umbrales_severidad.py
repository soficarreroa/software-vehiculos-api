"""Calcula los umbrales de severidad por clase a partir de las etiquetas de entrenamiento de CarDD.

Para cada clase toma el area relativa de cada dano (area del poligono / area de la imagen; las
etiquetas YOLO ya vienen normalizadas entre 0 y 1) y corta en los terciles 33 % y 67 %:
los danos mas pequenos de su tipo son 'leve', los intermedios 'moderado' y los mas grandes 'grave'.
Solo usa train, no valid ni test.

Uso:
    python calcular_umbrales_severidad.py --labels carsdd/train/labels --data carsdd/data.yaml --salida severidad_umbrales.json
"""

import argparse
import json
from pathlib import Path

import yaml


def area_poligono_normalizada(valores):
    puntos = list(zip(valores[0::2], valores[1::2]))
    suma = 0.0
    for i, (x1, y1) in enumerate(puntos):
        x2, y2 = puntos[(i + 1) % len(puntos)]
        suma += x1 * y2 - x2 * y1
    return abs(suma) / 2.0


def percentil(valores_ordenados, fraccion):
    """Percentil con interpolacion lineal (valores_ordenados no vacio)."""
    posicion = (len(valores_ordenados) - 1) * fraccion
    inferior = int(posicion)
    superior = min(inferior + 1, len(valores_ordenados) - 1)
    peso = posicion - inferior
    return valores_ordenados[inferior] * (1 - peso) + valores_ordenados[superior] * peso


def leer_areas(carpeta_etiquetas):
    areas = {}
    for archivo in sorted(Path(carpeta_etiquetas).glob("*.txt")):
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            campos = linea.split()
            if len(campos) < 5:
                continue
            clase = int(float(campos[0]))
            valores = [float(v) for v in campos[1:]]
            if len(valores) == 4:  # formato caja: cx cy w h
                area = valores[2] * valores[3]
            elif len(valores) >= 6 and len(valores) % 2 == 0:  # poligono
                area = area_poligono_normalizada(valores)
            else:
                continue
            areas.setdefault(clase, []).append(area)
    return areas


def main():
    parser = argparse.ArgumentParser(description="Umbrales de severidad por terciles de area relativa")
    parser.add_argument("--labels", default="carsdd/train/labels")
    parser.add_argument("--data", default="carsdd/data.yaml")
    parser.add_argument("--salida", default="severidad_umbrales.json")
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.data).read_text(encoding="utf-8"))
    nombres = config["names"]
    nombres = [nombres[k] for k in sorted(nombres)] if isinstance(nombres, dict) else list(nombres)

    areas = leer_areas(args.labels)
    if not areas:
        raise SystemExit(f"No se encontraron etiquetas en {args.labels}")

    umbrales = {}
    print(f"{'clase':<15}{'n':>6}{'leve hasta':>13}{'moderado hasta':>16}{'mediana':>10}")
    for clase_id, valores in sorted(areas.items()):
        valores.sort()
        nombre = nombres[clase_id]
        umbrales[nombre] = {
            "leve_hasta": round(percentil(valores, 1 / 3), 6),
            "moderado_hasta": round(percentil(valores, 2 / 3), 6),
            "n": len(valores),
        }
        print(f"{nombre:<15}{len(valores):>6}{umbrales[nombre]['leve_hasta']:>13.4f}"
              f"{umbrales[nombre]['moderado_hasta']:>16.4f}{percentil(valores, 0.5):>10.4f}")

    salida = {
        "metodo": "terciles del area relativa (area del dano / area de la imagen) por clase, solo train de CarDD",
        "advertencia": "Linea base por tamano; validar con etiquetas manuales antes de usar en cotizaciones.",
        "umbrales": umbrales,
    }
    Path(args.salida).write_text(json.dumps(salida, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nGuardado en {args.salida}")


if __name__ == "__main__":
    main()
