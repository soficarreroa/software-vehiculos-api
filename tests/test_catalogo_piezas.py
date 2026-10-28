from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.dependencies import get_usuario_con_rol
from app.routers import cotizaciones, piezas
from app.services.catalogo_piezas import desglosar, elegir_precio, filas_por_pieza


def fila(marca, modelo, repuesto, desde=2010, hasta=2030, pieza_id=1, mano=100.0, pintura=50.0):
    return {
        "pieza_id": pieza_id, "marca": marca, "modelo": modelo, "ano_desde": desde, "ano_hasta": hasta,
        "precio_repuesto": repuesto, "precio_mano_obra": mano, "precio_pintura": pintura, "moneda": "COP",
    }


class FakeQuery:
    def __init__(self, filas):
        self.filas, self._in, self._rango = list(filas), None, None

    def select(self, *_a, **_k): return self
    def eq(self, col, val):
        self.filas = [f for f in self.filas if f.get(col) == val]
        return self
    def in_(self, col, vals):
        self.filas = [f for f in self.filas if f.get(col) in vals]
        return self
    def order(self, *_a, **_k): return self
    def range(self, a, b):
        self._rango = (a, b)
        return self
    def execute(self):
        datos = self.filas if self._rango is None else self.filas[self._rango[0]: self._rango[1] + 1]
        return SimpleNamespace(data=datos)


class FakeClient:
    def __init__(self, **tablas): self.tablas = tablas
    def table(self, nombre): return FakeQuery(self.tablas[nombre])


def test_prefiere_mismo_modelo_sobre_misma_marca():
    filas = [fila("Toyota", "Corolla", 100), fila("Toyota", "Hilux", 900), fila("Mazda", "3", 5)]
    assert elegir_precio(filas, "toyota", "Hilux")["precio_repuesto"] == 900


def test_modelo_con_anio_usa_el_modelo_base():
    filas = [fila("Toyota", "Corolla", 100), fila("Toyota", "Hilux", 900)]
    assert elegir_precio(filas, "Toyota", "Hilux 2020")["precio_repuesto"] == 900


def test_respeta_rango_de_anios_entre_filas_del_mismo_modelo():
    filas = [fila("Toyota", "Hilux", 100, 2005, 2015), fila("Toyota", "Hilux", 900, 2016, 2026)]
    assert elegir_precio(filas, "Toyota", "Hilux 2020")["precio_repuesto"] == 900


def test_marca_sin_filas_cae_a_precio_de_referencia():
    assert elegir_precio([fila("Mazda", "3", 700)], "Tesla", "Model 3")["precio_repuesto"] == 700


def test_sin_precios_devuelve_none_y_desglosar_da_ceros():
    assert elegir_precio([fila("Mazda", "3", None)], "Mazda", "3") is None
    assert desglosar(None) == {"precio_repuesto": 0.0, "precio_mano_obra": 0.0, "precio_pintura": 0.0, "moneda": "COP"}


def test_desglosar_tolera_columnas_nulas():
    d = desglosar({"precio_repuesto": 10, "precio_mano_obra": None, "precio_pintura": None, "moneda": None})
    assert d["precio_mano_obra"] == 0.0 and d["moneda"] == "COP"


def test_filas_por_pieza_pagina_mas_de_mil_filas():
    filas = [fila("Kia", f"M{i}", 1, pieza_id=i % 3 + 1) for i in range(2500)]
    agrupadas = filas_por_pieza(FakeClient(catalogo_precios=filas))
    assert sum(len(v) for v in agrupadas.values()) == 2500


def _app(monkeypatch, vehiculos, piezas_tabla, precios):
    fake = FakeClient(vehiculos=vehiculos, piezas=piezas_tabla, catalogo_precios=precios)
    monkeypatch.setattr(piezas, "client", fake)
    app = FastAPI()
    app.include_router(piezas.router, prefix="/api/v1")
    app.dependency_overrides[get_usuario_con_rol] = lambda: {"id": 1}
    return TestClient(app)


def test_endpoint_piezas_usa_precio_del_vehiculo_y_ofrece_piezas_sin_precio_en_cero(monkeypatch):
    ahora = "2026-01-01T00:00:00"
    piezas_tabla = [
        {"id": 1, "codigo": "A", "nombre": "Parabrisas", "zona": None, "descripcion": None, "creado_en": ahora},
        {"id": 2, "codigo": "B", "nombre": "Sin precio", "zona": None, "descripcion": None, "creado_en": ahora},
    ]
    precios = [fila("Toyota", "Corolla", 100), fila("Toyota", "Hilux", 900)]
    cliente = _app(monkeypatch, [{"id": 7, "usuario_id": 1, "marca": "Toyota", "modelo": "Hilux 2020"}], piezas_tabla, precios)
    r = cliente.get("/api/v1/vehiculos/7/piezas-disponibles")
    assert r.status_code == 200
    cuerpo = r.json()
    # La pieza sin fila de precio igual se ofrece (con precios en 0) para poder elegirla
    assert [p["nombre"] for p in cuerpo] == ["Parabrisas", "Sin precio"]
    assert cuerpo[0]["precio_repuesto"] == 900
    assert cuerpo[1]["precio_repuesto"] == 0
