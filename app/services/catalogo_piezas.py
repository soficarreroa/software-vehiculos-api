"""Selección del precio de catálogo de una pieza según el vehículo.

La tabla `catalogo_precios` tiene una fila por pieza, marca, modelo y rango de años.
Antes se tomaba la primera fila de la pieza sin mirar el vehículo; aquí se elige la
que mejor coincide y, si el vehículo no tiene fila propia, se usa una de referencia
para que la cotización nunca quede vacía.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.services.estimacion_reparacion import normalizar_texto, separar_anio_modelo

CAMPOS_PRECIO = "pieza_id, marca, modelo, ano_desde, ano_hasta, precio_repuesto, precio_mano_obra, precio_pintura, moneda"


def _num(valor: Any) -> float:
    try:
        return float(valor) if valor is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _puntaje(fila: Mapping[str, Any], marca: str, modelo_base: str, modelo_completo: str, anio: int | None) -> int:
    """Mayor es mejor. 0 = la fila no corresponde a la marca del vehículo."""
    if normalizar_texto(fila.get("marca")) != marca:
        return 0
    puntos = 1
    modelo_fila = normalizar_texto(fila.get("modelo"))
    if modelo_fila in (modelo_completo, modelo_base) and modelo_fila:
        puntos += 10
    if anio is not None:
        desde, hasta = fila.get("ano_desde"), fila.get("ano_hasta")
        if (desde is None or desde <= anio) and (hasta is None or anio <= hasta):
            puntos += 2
    return puntos


def elegir_precio(
    filas: Iterable[Mapping[str, Any]],
    vehiculo_marca: Any,
    vehiculo_modelo: Any,
    anio: int | None = None,
) -> dict[str, Any] | None:
    """Fila de precio que mejor aplica al vehículo.

    Orden: mismo modelo > misma marca > cualquier fila con precio (referencia).
    Devuelve None si ninguna fila tiene precio de repuesto.
    """
    con_precio = [f for f in filas if f.get("precio_repuesto") is not None]
    if not con_precio:
        return None

    base, anio_modelo = separar_anio_modelo(vehiculo_modelo)
    marca = normalizar_texto(vehiculo_marca)
    modelo_base = normalizar_texto(base)
    modelo_completo = normalizar_texto(vehiculo_modelo)
    anio = anio if anio is not None else anio_modelo

    mejor = max(con_precio, key=lambda f: _puntaje(f, marca, modelo_base, modelo_completo, anio))
    return dict(mejor)


def desglosar(fila: Mapping[str, Any] | None) -> dict[str, Any]:
    """Precios como números (sin None) y moneda, listos para sumar."""
    fila = fila or {}
    return {
        "precio_repuesto": _num(fila.get("precio_repuesto")),
        "precio_mano_obra": _num(fila.get("precio_mano_obra")),
        "precio_pintura": _num(fila.get("precio_pintura")),
        "moneda": fila.get("moneda") or "COP",
    }


def filas_por_pieza(client: Any, pieza_ids: list[int] | None = None) -> dict[int, list[dict[str, Any]]]:
    """Todas las filas de catalogo_precios agrupadas por pieza (paginando: Supabase corta en 1000)."""
    agrupadas: dict[int, list[dict[str, Any]]] = {}
    desde, paso = 0, 1000
    while True:
        consulta = client.table("catalogo_precios").select(CAMPOS_PRECIO)
        if pieza_ids is not None:
            consulta = consulta.in_("pieza_id", pieza_ids)
        pagina = consulta.order("id").range(desde, desde + paso - 1).execute().data or []
        for fila in pagina:
            agrupadas.setdefault(fila["pieza_id"], []).append(fila)
        if len(pagina) < paso:
            return agrupadas
        desde += paso
