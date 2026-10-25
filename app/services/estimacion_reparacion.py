"""Estimación de reparación a partir de los daños detectados y el catálogo CSV.

El cálculo es independiente de FastAPI y de Supabase: ``calcular_estimado`` recibe
el vehículo, los daños, las asignaciones de piezas y las filas de precios ya
cargadas. ``estimar_reparacion`` es el punto de integración que carga el CSV por
defecto cuando no se le pasan precios.
"""

from __future__ import annotations

import csv
import math
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
RUTA_CSV_PRECIOS = RAIZ_PROYECTO / "data" / "precios_reparacion_vehiculos.csv"

COLUMNAS_PRECIOS = (
    "marca",
    "modelo",
    "pieza",
    "severidad",
    "tipo_establecimiento",
    "precio_min_cop",
    "precio_max_cop",
    "moneda",
    "origen",
    "es_estimacion",
)
TIPOS_ESTABLECIMIENTO = ("economico", "multimarca", "concesionario")
SEVERIDADES = ("leve", "moderado", "grave")
RANGO_SEVERIDAD = {severidad: indice for indice, severidad in enumerate(SEVERIDADES)}
PIEZAS_ESTIMABLES = (
    "Bumper delantero",
    "Bumper trasero",
    "Guardabarros",
    "Puerta",
    "Capó",
)
EQUIVALENCIAS_PIEZAS = {
    "bumper delantero": "Bumper delantero",
    "bumper trasero": "Bumper trasero",
    "guardabarros": "Guardabarros",
    "puerta": "Puerta",
    "capo": "Capó",
    "parachoques delantero": "Bumper delantero",
    "parachoques trasero": "Bumper trasero",
    "guardabarros delantero derecho": "Guardabarros",
    "puerta delantera izquierda": "Puerta",
}
PATRON_MODELO_CON_ANIO = re.compile(
    r"^(?P<base>.+?)(?:\s+|-\s*)(?P<anio>(?:19|20)\d{2})$"
)
CONFIANZA_MINIMA = 0.25
MONEDA = "COP"
NOTA = (
    "Los valores son aproximados y corresponden a estimaciones de referencia. "
    "El monto final depende de la inspección física del vehículo y de la cotización "
    "del establecimiento."
)


class CatalogoPreciosError(ValueError):
    """El catálogo de precios no tiene el formato esperado."""


class PreciosDuplicadosError(CatalogoPreciosError):
    """Hay más de una fila para la misma combinación de precio."""


class AsignacionesInvalidas(ValueError):
    """Las asignaciones de piezas no corresponden a los daños recibidos."""


def normalizar_texto(valor: Any) -> str:
    """Normaliza mayúsculas, tildes y espacios para comparar nombres del CSV."""
    texto = unicodedata.normalize("NFKD", str(valor if valor is not None else "").strip().casefold())
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    return re.sub(r"\s+", " ", texto)


def normalizar_severidad(valor: Any) -> str | None:
    normalizado = normalizar_texto(valor)
    return normalizado if normalizado in RANGO_SEVERIDAD else None


def normalizar_pieza(valor: Any) -> str | None:
    """Devuelve la categoría del CSV para una pieza, o None si no es equivalente."""
    return EQUIVALENCIAS_PIEZAS.get(normalizar_texto(valor))


def _nombre_pieza_original(valor: Any) -> str | None:
    if valor is None:
        return None
    nombre = str(valor).strip()
    return nombre or None


def separar_anio_modelo(modelo: Any) -> tuple[str, int | None]:
    """Separa un año solo cuando aparece como sufijo explícito del modelo."""
    texto = str(modelo or "").strip()
    coincidencia = PATRON_MODELO_CON_ANIO.fullmatch(texto)
    if not coincidencia:
        return texto, None
    base = coincidencia.group("base").strip()
    if not base:
        return texto, None
    return base, int(coincidencia.group("anio"))


def _clave_precio(
    marca: Any,
    modelo: Any,
    pieza: Any,
    severidad: Any,
    tipo_establecimiento: Any,
) -> tuple[str, str, str, str, str]:
    return (
        normalizar_texto(marca),
        normalizar_texto(modelo),
        normalizar_texto(pieza),
        normalizar_texto(severidad),
        normalizar_texto(tipo_establecimiento),
    )


def _entero_positivo(valor: Any, nombre_columna: str, numero_fila: int) -> int:
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError) as error:
        raise CatalogoPreciosError(
            f"Fila {numero_fila}: {nombre_columna} no es un entero válido"
        ) from error
    if numero <= 0:
        raise CatalogoPreciosError(f"Fila {numero_fila}: {nombre_columna} debe ser mayor que cero")
    return numero


def cargar_precios_csv(ruta: str | Path | None = None) -> list[dict[str, Any]]:
    """Carga y valida el catálogo de precios; no modifica el archivo."""
    ruta_csv = Path(ruta) if ruta is not None else RUTA_CSV_PRECIOS
    if not ruta_csv.is_file():
        raise FileNotFoundError(f"No se encontró el catálogo de precios: {ruta_csv}")

    with ruta_csv.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        if tuple(lector.fieldnames or ()) != COLUMNAS_PRECIOS:
            raise CatalogoPreciosError(
                "El CSV de precios no tiene las columnas esperadas: "
                + ",".join(COLUMNAS_PRECIOS)
            )

        precios: list[dict[str, Any]] = []
        vistos: dict[tuple[str, str, str, str, str], int] = {}

        for numero_fila, fila in enumerate(lector, start=2):
            if not any(str(valor or "").strip() for valor in fila.values()):
                continue

            marca = str(fila.get("marca") or "").strip()
            modelo = str(fila.get("modelo") or "").strip()
            pieza = normalizar_pieza(fila.get("pieza"))
            severidad = normalizar_severidad(fila.get("severidad"))
            tipo_establecimiento = normalizar_texto(fila.get("tipo_establecimiento"))

            if not marca or not modelo:
                raise CatalogoPreciosError(f"Fila {numero_fila}: marca y modelo son obligatorios")
            if pieza is None:
                raise CatalogoPreciosError(f"Fila {numero_fila}: pieza no reconocida")
            if severidad is None:
                raise CatalogoPreciosError(f"Fila {numero_fila}: severidad no válida")
            if tipo_establecimiento not in TIPOS_ESTABLECIMIENTO:
                raise CatalogoPreciosError(
                    f"Fila {numero_fila}: tipo_establecimiento no válido"
                )

            moneda = str(fila.get("moneda") or "").strip().upper()
            if moneda != MONEDA:
                raise CatalogoPreciosError(f"Fila {numero_fila}: la moneda debe ser COP")

            es_estimacion = str(fila.get("es_estimacion") or "").strip().lower()
            if es_estimacion != "true":
                raise CatalogoPreciosError(f"Fila {numero_fila}: es_estimacion debe ser true")

            origen = str(fila.get("origen") or "").strip()
            if not origen:
                raise CatalogoPreciosError(f"Fila {numero_fila}: origen es obligatorio")

            precio_min = _entero_positivo(fila.get("precio_min_cop"), "precio_min_cop", numero_fila)
            precio_max = _entero_positivo(fila.get("precio_max_cop"), "precio_max_cop", numero_fila)
            if precio_min > precio_max:
                raise CatalogoPreciosError(
                    f"Fila {numero_fila}: precio_min_cop no puede ser mayor que precio_max_cop"
                )

            clave = _clave_precio(marca, modelo, pieza, severidad, tipo_establecimiento)
            if clave in vistos:
                raise PreciosDuplicadosError(
                    "Precio duplicado para "
                    f"{marca}/{modelo}/{pieza}/{severidad}/{tipo_establecimiento} "
                    f"(filas {vistos[clave]} y {numero_fila})"
                )
            vistos[clave] = numero_fila

            precios.append(
                {
                    "marca": marca,
                    "modelo": modelo,
                    "pieza": pieza,
                    "severidad": severidad,
                    "tipo_establecimiento": tipo_establecimiento,
                    "precio_min_cop": precio_min,
                    "precio_max_cop": precio_max,
                    "moneda": moneda,
                    "origen": origen,
                    "es_estimacion": True,
                }
            )

    if not precios:
        raise CatalogoPreciosError("El catálogo de precios está vacío")

    return precios


def _indexar_precios(precios: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str, str, str, str], dict[str, Any]]:
    indice: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}

    for fila in precios:
        try:
            clave = _clave_precio(
                fila["marca"],
                fila["modelo"],
                fila["pieza"],
                fila["severidad"],
                fila["tipo_establecimiento"],
            )
        except KeyError as error:
            raise CatalogoPreciosError(f"Precio incompleto: falta {error.args[0]}") from error

        if clave in indice:
            raise PreciosDuplicadosError(
                "Precio duplicado para "
                f"{fila['marca']}/{fila['modelo']}/{fila['pieza']}/"
                f"{fila['severidad']}/{fila['tipo_establecimiento']}"
            )

        try:
            minimo = int(fila["precio_min_cop"])
            maximo = int(fila["precio_max_cop"])
        except (KeyError, TypeError, ValueError) as error:
            raise CatalogoPreciosError("Rango de precio incompleto o inválido") from error

        if minimo <= 0 or maximo <= 0 or minimo > maximo:
            raise CatalogoPreciosError(
                f"Rango de precio inválido para {fila['marca']}/{fila['modelo']}/"
                f"{fila['pieza']}/{fila['severidad']}/{fila['tipo_establecimiento']}"
            )

        indice[clave] = {
            **dict(fila),
            "precio_min_cop": minimo,
            "precio_max_cop": maximo,
        }

    return indice


def _resolver_vehiculo(
    marca: Any,
    modelo: Any,
    indice_precios: Mapping[tuple[str, str, str, str, str], Mapping[str, Any]],
) -> dict[str, Any] | None:
    marca_normalizada = normalizar_texto(marca)
    modelo_normalizado = normalizar_texto(modelo)
    if not marca_normalizada or not modelo_normalizado:
        return None

    for clave, fila in indice_precios.items():
        if clave[0] == marca_normalizada and clave[1] == modelo_normalizado:
            _, anio = separar_anio_modelo(modelo)
            return {
                "marca_csv": fila["marca"],
                "modelo_csv": fila["modelo"],
                "anio_detectado": anio,
                "coincidencia_modelo": "exacta",
                "modelo_base": None,
            }

    modelo_base, anio = separar_anio_modelo(modelo)
    if anio is None:
        return None

    base_normalizada = normalizar_texto(modelo_base)
    if not base_normalizada or base_normalizada == modelo_normalizado:
        return None

    for clave, fila in indice_precios.items():
        if clave[0] == marca_normalizada and clave[1] == base_normalizada:
            return {
                "marca_csv": fila["marca"],
                "modelo_csv": fila["modelo"],
                "anio_detectado": anio,
                "coincidencia_modelo": "modelo_base",
                "modelo_base": modelo_base,
            }

    return None


def _confianza(valor: Any) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _validar_asignaciones(
    asignaciones: Sequence[Mapping[str, Any]] | None,
    total_danos: int,
) -> dict[int, Any]:
    por_indice: dict[int, Any] = {}

    for asignacion in asignaciones or []:
        try:
            indice = int(asignacion["indice_dano"])
        except (KeyError, TypeError, ValueError) as error:
            raise AsignacionesInvalidas("Cada asignación debe incluir un indice_dano válido") from error

        if indice < 0 or indice >= total_danos:
            raise AsignacionesInvalidas(
                f"El índice de daño {indice} está fuera del rango 0..{total_danos - 1}"
            )
        if indice in por_indice:
            raise AsignacionesInvalidas(f"El daño {indice} tiene más de una asignación de pieza")

        por_indice[indice] = asignacion.get("pieza")

    return por_indice


def redondear_cop(valor: int | None) -> int | None:
    """Redondea al múltiplo de 10.000 más cercano sin tocar los precios base."""
    if valor is None:
        return None
    redondeado = (Decimal(valor) / Decimal("10000")).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(redondeado * Decimal("10000"))


def _dano_resumen(
    indice: int,
    dano: Mapping[str, Any],
    severidad: str | None,
    pieza_original: str | None,
) -> dict[str, Any]:
    return {
        "indice_dano": indice,
        "tipo_dano": dano.get("tipo_dano"),
        "confianza": _confianza(dano.get("confianza")),
        "severidad": severidad,
        "pieza_original": pieza_original,
    }


def _agregar_advertencia(advertencias: list[str], mensaje: str) -> None:
    if mensaje not in advertencias:
        advertencias.append(mensaje)


def calcular_estimado(
    vehiculo: Mapping[str, Any],
    danos: Sequence[Mapping[str, Any]] | None,
    asignaciones: Sequence[Mapping[str, Any]] | None,
    precios: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Calcula el estimado sin consultar la base de datos ni escribir archivos."""
    if not isinstance(vehiculo, Mapping):
        raise TypeError("vehiculo debe ser un diccionario")

    lista_danos = list(danos or [])
    indice_precios = _indexar_precios(precios)
    asignaciones_por_indice = _validar_asignaciones(asignaciones, len(lista_danos))

    marca = str(vehiculo.get("marca") or "").strip()
    modelo = str(vehiculo.get("modelo") or "").strip()
    resolucion_vehiculo = _resolver_vehiculo(marca, modelo, indice_precios)

    grupos: dict[str, dict[str, Any]] = {}
    danos_no_estimados: list[dict[str, Any]] = []
    danos_ignorados: list[dict[str, Any]] = []
    advertencias: list[str] = []

    if not lista_danos:
        _agregar_advertencia(advertencias, "No se recibieron daños para estimar.")

    if not marca or not modelo:
        _agregar_advertencia(
            advertencias,
            "El vehículo no tiene marca o modelo definido; no se pueden buscar precios.",
        )
    elif resolucion_vehiculo is None:
        _agregar_advertencia(
            advertencias,
            f"No se encontró una correspondencia inequívoca para el vehículo "
            f"'{marca} {modelo}' en el catálogo de precios. Los daños quedan pendientes.",
        )
    elif resolucion_vehiculo["coincidencia_modelo"] == "modelo_base":
        anio = resolucion_vehiculo["anio_detectado"]
        _agregar_advertencia(
            advertencias,
            f"El vehículo '{marca} {modelo}' se estimó con el modelo base "
            f"'{resolucion_vehiculo['modelo_csv']}' del catálogo; el precio no es "
            f"específico del año {anio}.",
        )

    for indice, dano in enumerate(lista_danos):
        pieza_original = _nombre_pieza_original(asignaciones_por_indice.get(indice))

        if not isinstance(dano, Mapping):
            danos_no_estimados.append(
                {
                    "indice_dano": indice,
                    "tipo_dano": None,
                    "severidad": None,
                    "pieza_original": pieza_original,
                    "motivo": "El daño no tiene un formato válido.",
                }
            )
            continue

        tipo_dano = dano.get("tipo_dano")
        confianza = _confianza(dano.get("confianza"))

        if confianza is None:
            danos_no_estimados.append(
                {
                    "indice_dano": indice,
                    "tipo_dano": tipo_dano,
                    "severidad": normalizar_severidad(dano.get("severidad")),
                    "pieza_original": pieza_original,
                    "motivo": "La confianza del daño no está disponible.",
                }
            )
            continue

        if confianza < CONFIANZA_MINIMA:
            danos_ignorados.append(
                {
                    "indice_dano": indice,
                    "tipo_dano": tipo_dano,
                    "confianza": confianza,
                    "pieza_original": pieza_original,
                    "motivo": f"Confianza {confianza:.3f} inferior a {CONFIANZA_MINIMA:.2f}.",
                }
            )
            continue

        severidad = normalizar_severidad(dano.get("severidad"))
        if severidad is None:
            danos_no_estimados.append(
                {
                    "indice_dano": indice,
                    "tipo_dano": tipo_dano,
                    "severidad": None,
                    "pieza_original": pieza_original,
                    "motivo": "El daño no tiene una severidad válida.",
                }
            )
            continue

        pieza = normalizar_pieza(pieza_original)
        if pieza is None:
            motivo = (
                "El daño no tiene asignación de pieza."
                if pieza_original is None
                else f"La pieza '{pieza_original}' no tiene equivalencia con las "
                "categorías del catálogo de precios."
            )
            danos_no_estimados.append(
                {
                    "indice_dano": indice,
                    "tipo_dano": tipo_dano,
                    "severidad": severidad,
                    "pieza_original": pieza_original,
                    "motivo": motivo,
                }
            )
            continue

        grupo = grupos.setdefault(
            pieza,
            {
                "pieza": pieza,
                "pieza_original": pieza_original,
                "piezas_originales": [],
                "es_categoria_generica": False,
                "severidad": severidad,
                "danos": [],
            },
        )
        if pieza_original not in grupo["piezas_originales"]:
            grupo["piezas_originales"].append(pieza_original)
        if normalizar_texto(pieza_original) != normalizar_texto(pieza):
            grupo["es_categoria_generica"] = True
        if RANGO_SEVERIDAD[severidad] > RANGO_SEVERIDAD[grupo["severidad"]]:
            grupo["severidad"] = severidad
        grupo["danos"].append(_dano_resumen(indice, dano, severidad, pieza_original))

    if danos_ignorados:
        _agregar_advertencia(
            advertencias,
            f"{len(danos_ignorados)} daño(s) ignorado(s) por confianza inferior a "
            f"{CONFIANZA_MINIMA:.2f}.",
        )

    desglose: list[dict[str, Any]] = []
    piezas_sin_precio: list[dict[str, Any]] = []

    grupos_ordenados = sorted(
        grupos.values(),
        key=lambda grupo: min(dano["indice_dano"] for dano in grupo["danos"]),
    )

    marca_busqueda = resolucion_vehiculo["marca_csv"] if resolucion_vehiculo else None
    modelo_busqueda = resolucion_vehiculo["modelo_csv"] if resolucion_vehiculo else None

    for grupo in grupos_ordenados:
        precios_pieza: dict[str, dict[str, int] | None] = {}
        establecimientos_sin_precio: list[str] = []

        for tipo_establecimiento in TIPOS_ESTABLECIMIENTO:
            fila = None
            if marca_busqueda and modelo_busqueda:
                fila = indice_precios.get(
                    _clave_precio(
                        marca_busqueda,
                        modelo_busqueda,
                        grupo["pieza"],
                        grupo["severidad"],
                        tipo_establecimiento,
                    )
                )
            if fila is None:
                precios_pieza[tipo_establecimiento] = None
                establecimientos_sin_precio.append(tipo_establecimiento)
            else:
                precios_pieza[tipo_establecimiento] = {
                    "minimo_cop": int(fila["precio_min_cop"]),
                    "maximo_cop": int(fila["precio_max_cop"]),
                }

        estimado = any(precio is not None for precio in precios_pieza.values())

        if grupo["es_categoria_generica"]:
            for pieza_original in grupo["piezas_originales"]:
                if normalizar_texto(pieza_original) == normalizar_texto(grupo["pieza"]):
                    continue
                _agregar_advertencia(
                    advertencias,
                    f"La pieza '{pieza_original}' se estimó con la categoría general "
                    f"'{grupo['pieza']}' del catálogo; el precio no es una cotización "
                    "exacta de esa pieza específica.",
                )

        if establecimientos_sin_precio:
            piezas_sin_precio.append(
                {
                    "pieza": grupo["pieza"],
                    "pieza_original": grupo["pieza_original"],
                    "piezas_originales": list(grupo["piezas_originales"]),
                    "es_categoria_generica": grupo["es_categoria_generica"],
                    "severidad": grupo["severidad"],
                    "establecimientos": establecimientos_sin_precio,
                }
            )

        if not estimado:
            motivo = (
                "No hay precio para esta pieza y severidad en ningún establecimiento."
                if resolucion_vehiculo
                else "No se pudo identificar el vehículo en el catálogo de precios."
            )
            for dano in grupo["danos"]:
                danos_no_estimados.append(
                    {
                        "indice_dano": dano["indice_dano"],
                        "tipo_dano": dano["tipo_dano"],
                        "severidad": dano["severidad"],
                        "pieza_original": dano["pieza_original"],
                        "motivo": motivo,
                    }
                )

        desglose.append(
            {
                "pieza": grupo["pieza"],
                "pieza_original": grupo["pieza_original"],
                "piezas_originales": list(grupo["piezas_originales"]),
                "es_categoria_generica": grupo["es_categoria_generica"],
                "severidad": grupo["severidad"],
                "danos": grupo["danos"],
                "precios": precios_pieza,
                "establecimientos_sin_precio": establecimientos_sin_precio,
                "estimado": estimado,
            }
        )

    danos_no_estimados.sort(key=lambda dano: dano["indice_dano"])
    if danos_no_estimados:
        _agregar_advertencia(
            advertencias,
            f"{len(danos_no_estimados)} daño(s) no se pudieron estimar. "
            "Los totales no incluyen esos daños.",
        )
    if piezas_sin_precio:
        _agregar_advertencia(
            advertencias,
            "Hay piezas sin precio para uno o más establecimientos. "
            "La estimación correspondiente está incompleta.",
        )

    totales: dict[str, dict[str, Any]] = {}
    for tipo_establecimiento in TIPOS_ESTABLECIMIENTO:
        piezas_con_precio = [
            item["precios"][tipo_establecimiento]
            for item in desglose
            if item["precios"][tipo_establecimiento] is not None
        ]
        piezas_no_estimadas = [
            item["pieza"]
            for item in desglose
            if item["precios"][tipo_establecimiento] is None
        ]
        completo = not danos_no_estimados and not piezas_no_estimadas

        if not desglose and not danos_no_estimados:
            totales[tipo_establecimiento] = {
                "minimo_cop": 0,
                "maximo_cop": 0,
                "completo": True,
                "piezas_no_estimadas": [],
            }
        elif piezas_con_precio:
            minimo = sum(precio["minimo_cop"] for precio in piezas_con_precio)
            maximo = sum(precio["maximo_cop"] for precio in piezas_con_precio)
            totales[tipo_establecimiento] = {
                "minimo_cop": redondear_cop(minimo),
                "maximo_cop": redondear_cop(maximo),
                "completo": completo,
                "piezas_no_estimadas": piezas_no_estimadas,
            }
        else:
            totales[tipo_establecimiento] = {
                "minimo_cop": None,
                "maximo_cop": None,
                "completo": False,
                "piezas_no_estimadas": piezas_no_estimadas,
            }

    return {
        "vehiculo_id": vehiculo.get("id"),
        "marca": marca or None,
        "modelo": modelo or None,
        "marca_csv": marca_busqueda,
        "modelo_csv": modelo_busqueda,
        "anio_detectado": (
            resolucion_vehiculo["anio_detectado"] if resolucion_vehiculo else None
        ),
        "coincidencia_modelo": (
            resolucion_vehiculo["coincidencia_modelo"] if resolucion_vehiculo else None
        ),
        "moneda": MONEDA,
        "desglose": desglose,
        "totales": totales,
        "danos_no_estimados": danos_no_estimados,
        "danos_ignorados": danos_ignorados,
        "piezas_sin_precio": piezas_sin_precio,
        "advertencias": advertencias,
        "nota": NOTA,
    }


def estimar_reparacion(
    vehiculo: Mapping[str, Any],
    danos: Sequence[Mapping[str, Any]] | None,
    asignaciones: Sequence[Mapping[str, Any]] | None,
    precios: Iterable[Mapping[str, Any]] | None = None,
    ruta_precios: str | Path | None = None,
) -> dict[str, Any]:
    """Integra la carga del CSV con el cálculo puro."""
    catalogo = list(precios) if precios is not None else cargar_precios_csv(ruta_precios)
    return calcular_estimado(vehiculo, danos, asignaciones, catalogo)
