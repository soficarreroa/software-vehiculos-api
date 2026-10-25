from __future__ import annotations

import csv
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.dependencies import get_usuario_con_rol
from app.routers import cotizaciones
from app.services.estimacion_reparacion import (
    COLUMNAS_PRECIOS,
    PreciosDuplicadosError,
    calcular_estimado,
    cargar_precios_csv,
    normalizar_pieza,
    redondear_cop,
)

VEHICULO_MAZDA = {"id": 1, "marca": "Mazda", "modelo": "Mazda2 Sport"}
VEHICULO_TOYOTA = {"id": 2, "marca": "Toyota", "modelo": "Corolla"}


def precio(
    *,
    marca: str = "Mazda",
    modelo: str = "Mazda2 Sport",
    pieza: str = "Bumper delantero",
    severidad: str = "leve",
    tipo_establecimiento: str = "economico",
    minimo: int = 100_000,
    maximo: int = 200_000,
) -> dict:
    return {
        "marca": marca,
        "modelo": modelo,
        "pieza": pieza,
        "severidad": severidad,
        "tipo_establecimiento": tipo_establecimiento,
        "precio_min_cop": minimo,
        "precio_max_cop": maximo,
        "moneda": "COP",
        "origen": "precios_de_prueba",
        "es_estimacion": True,
    }


def catalogo_severidades(
    *,
    marca: str = "Mazda",
    modelo: str = "Mazda2 Sport",
    pieza: str = "Bumper delantero",
) -> list[dict]:
    valores = {
        "leve": {
            "economico": (100_000, 200_000),
            "multimarca": (300_000, 400_000),
            "concesionario": (500_000, 600_000),
        },
        "moderado": {
            "economico": (700_000, 800_000),
            "multimarca": (900_000, 1_000_000),
            "concesionario": (1_100_000, 1_200_000),
        },
        "grave": {
            "economico": (1_300_000, 1_400_000),
            "multimarca": (1_500_000, 1_600_000),
            "concesionario": (1_700_000, 1_800_000),
        },
    }
    return [
        precio(
            marca=marca,
            modelo=modelo,
            pieza=pieza,
            severidad=severidad,
            tipo_establecimiento=tipo,
            minimo=rango[0],
            maximo=rango[1],
        )
        for severidad, rangos in valores.items()
        for tipo, rango in rangos.items()
    ]


def dano(severidad: str | None = "leve", confianza: float = 0.9, tipo: str = "rayon") -> dict:
    return {"tipo_dano": tipo, "severidad": severidad, "confianza": confianza}


def asignacion(indice: int = 0, pieza: str = "Bumper delantero") -> dict:
    return {"indice_dano": indice, "pieza": pieza}


def test_csv_real_se_carga_completo_y_sin_duplicados():
    precios = cargar_precios_csv()
    assert len(precios) == 945
    claves = {
        (
            fila["marca"],
            fila["modelo"],
            fila["pieza"],
            fila["severidad"],
            fila["tipo_establecimiento"],
        )
        for fila in precios
    }
    assert len(claves) == 945


@pytest.mark.parametrize(
    ("severidad", "esperado"),
    [
        (
            "leve",
            {
                "economico": {"minimo_cop": 100_000, "maximo_cop": 200_000},
                "multimarca": {"minimo_cop": 300_000, "maximo_cop": 400_000},
                "concesionario": {"minimo_cop": 500_000, "maximo_cop": 600_000},
            },
        ),
        (
            "moderado",
            {
                "economico": {"minimo_cop": 700_000, "maximo_cop": 800_000},
                "multimarca": {"minimo_cop": 900_000, "maximo_cop": 1_000_000},
                "concesionario": {"minimo_cop": 1_100_000, "maximo_cop": 1_200_000},
            },
        ),
        (
            "grave",
            {
                "economico": {"minimo_cop": 1_300_000, "maximo_cop": 1_400_000},
                "multimarca": {"minimo_cop": 1_500_000, "maximo_cop": 1_600_000},
                "concesionario": {"minimo_cop": 1_700_000, "maximo_cop": 1_800_000},
            },
        ),
    ],
)
def test_lee_el_rango_correcto_por_severidad_y_establecimiento(severidad, esperado):
    resultado = calcular_estimado(
        VEHICULO_MAZDA,
        [dano(severidad)],
        [asignacion()],
        catalogo_severidades(),
    )

    assert len(resultado["desglose"]) == 1
    assert resultado["desglose"][0]["severidad"] == severidad
    assert resultado["desglose"][0]["precios"] == esperado


@pytest.mark.parametrize(
    ("vehiculo", "modelo", "minimo_esperado"),
    [
        (VEHICULO_MAZDA, "Mazda2 Sport", 100_000),
        (VEHICULO_TOYOTA, "Corolla", 900_000),
    ],
)
def test_coincide_marca_y_modelo(vehiculo, modelo, minimo_esperado):
    precios = [
        precio(modelo="Mazda2 Sport", minimo=100_000, maximo=200_000),
        precio(marca="Toyota", modelo="Corolla", minimo=900_000, maximo=1_000_000),
    ]

    resultado = calcular_estimado(vehiculo, [dano()], [asignacion()], precios)

    assert resultado["desglose"][0]["precios"]["economico"] == {
        "minimo_cop": minimo_esperado,
        "maximo_cop": minimo_esperado + 100_000,
    }
    assert resultado["modelo"] == modelo
    assert resultado["modelo_csv"] == modelo
    assert resultado["coincidencia_modelo"] == "exacta"


@pytest.mark.parametrize(
    ("pieza_real", "categoria_csv"),
    [
        ("Parachoques Delantero", "Bumper delantero"),
        ("Parachoques Trasero", "Bumper trasero"),
        ("Guardabarros Delantero Derecho", "Guardabarros"),
        ("Puerta Delantera Izquierda", "Puerta"),
        ("Capó", "Capó"),
    ],
)
def test_mapea_piezas_reales_de_supabase_a_categorias_del_csv(pieza_real, categoria_csv):
    assert normalizar_pieza(pieza_real) == categoria_csv


@pytest.mark.parametrize(
    "pieza_sin_equivalencia",
    [
        "Airbag de Volante",
        "Amortiguador Delantero",
        "Espejo Retrovisor Derecho",
        "Faro Principal Derecho",
        "Puerta Maletero",
    ],
)
def test_pieza_real_sin_equivalencia_queda_pendiente(pieza_sin_equivalencia):
    resultado = calcular_estimado(
        VEHICULO_MAZDA,
        [dano()],
        [asignacion(pieza=pieza_sin_equivalencia)],
        catalogo_severidades(),
    )

    assert resultado["desglose"] == []
    assert resultado["totales"]["economico"]["minimo_cop"] is None
    assert resultado["totales"]["economico"]["completo"] is False
    assert resultado["danos_no_estimados"][0]["pieza_original"] == pieza_sin_equivalencia
    assert "equivalencia" in resultado["danos_no_estimados"][0]["motivo"]


def test_preserva_nombre_original_y_marca_categoria_generica():
    resultado = calcular_estimado(
        VEHICULO_MAZDA,
        [dano()],
        [asignacion(pieza="Parachoques Delantero")],
        catalogo_severidades(),
    )

    pieza = resultado["desglose"][0]
    assert pieza["pieza"] == "Bumper delantero"
    assert pieza["pieza_original"] == "Parachoques Delantero"
    assert pieza["piezas_originales"] == ["Parachoques Delantero"]
    assert pieza["es_categoria_generica"] is True
    assert pieza["danos"][0]["pieza_original"] == "Parachoques Delantero"
    assert any("categoría general" in advertencia for advertencia in resultado["advertencias"])


def test_modelo_con_anio_usa_modelo_base_e_informa_que_no_es_especifico():
    precios = catalogo_severidades(marca="Toyota", modelo="Corolla")
    resultado = calcular_estimado(
        {"id": 3, "marca": " toyota ", "modelo": " COROLLA  2020 "},
        [dano()],
        [asignacion()],
        precios,
    )

    assert resultado["marca"] == "toyota"
    assert resultado["modelo"] == "COROLLA  2020"
    assert resultado["marca_csv"] == "Toyota"
    assert resultado["modelo_csv"] == "Corolla"
    assert resultado["anio_detectado"] == 2020
    assert resultado["coincidencia_modelo"] == "modelo_base"
    assert resultado["desglose"][0]["precios"]["economico"]["minimo_cop"] == 100_000
    assert any("no es específico del año 2020" in advertencia for advertencia in resultado["advertencias"])


def test_normaliza_marca_y_modelo_por_espacios_mayusculas_y_acentos():
    precios = catalogo_severidades(marca="Mazda", modelo="Mazda2 Sedán")
    resultado = calcular_estimado(
        {"id": 4, "marca": "  MAZDA ", "modelo": " mazda2   sedan "},
        [dano()],
        [asignacion()],
        precios,
    )

    assert resultado["marca_csv"] == "Mazda"
    assert resultado["modelo_csv"] == "Mazda2 Sedán"
    assert resultado["coincidencia_modelo"] == "exacta"
    assert resultado["anio_detectado"] is None
    assert resultado["desglose"][0]["estimado"] is True


@pytest.mark.parametrize("modelo_ambiguo", ["Mazda2 2023", "Toyota Corola 2020"])
def test_modelo_ambiguo_o_con_error_ortografico_queda_pendiente(modelo_ambiguo):
    precios = (
        catalogo_severidades(marca="Mazda", modelo="Mazda2 Sport")
        + catalogo_severidades(marca="Mazda", modelo="Mazda2 Sedán")
        + catalogo_severidades(marca="Toyota", modelo="Corolla")
    )
    marca = "Mazda" if modelo_ambiguo.startswith("Mazda") else "Toyota"
    resultado = calcular_estimado(
        {"id": 5, "marca": marca, "modelo": modelo_ambiguo},
        [dano()],
        [asignacion()],
        precios,
    )

    assert resultado["modelo_csv"] is None
    assert resultado["coincidencia_modelo"] is None
    assert resultado["desglose"][0]["estimado"] is False
    assert resultado["totales"]["economico"]["minimo_cop"] is None
    assert resultado["totales"]["economico"]["completo"] is False
    assert any("correspondencia inequívoca" in advertencia for advertencia in resultado["advertencias"])


def test_agrupa_danos_de_la_misma_pieza_y_aplica_la_severidad_mas_alta():
    resultado = calcular_estimado(
        VEHICULO_MAZDA,
        [dano("leve"), dano("grave", tipo="abolladura"), dano("moderado")],
        [asignacion(0), asignacion(1), asignacion(2)],
        catalogo_severidades(),
    )

    assert len(resultado["desglose"]) == 1
    assert resultado["desglose"][0]["severidad"] == "grave"
    assert len(resultado["desglose"][0]["danos"]) == 3
    assert resultado["desglose"][0]["precios"]["economico"] == {
        "minimo_cop": 1_300_000,
        "maximo_cop": 1_400_000,
    }
    assert resultado["totales"]["economico"]["minimo_cop"] == 1_300_000
    assert resultado["totales"]["economico"]["maximo_cop"] == 1_400_000


def test_dano_sin_asignacion_no_se_estima_ni_vale_cero():
    resultado = calcular_estimado(VEHICULO_MAZDA, [dano()], [], catalogo_severidades())

    assert resultado["desglose"] == []
    assert resultado["totales"]["economico"]["minimo_cop"] is None
    assert resultado["totales"]["economico"]["maximo_cop"] is None
    assert resultado["totales"]["economico"]["completo"] is False
    assert resultado["danos_no_estimados"][0]["indice_dano"] == 0
    assert "asignación" in resultado["danos_no_estimados"][0]["motivo"]


def test_dano_sin_severidad_no_se_estima():
    resultado = calcular_estimado(
        VEHICULO_MAZDA,
        [dano(severidad=None)],
        [asignacion()],
        catalogo_severidades(),
    )

    assert resultado["desglose"] == []
    assert resultado["totales"]["multimarca"]["minimo_cop"] is None
    assert "severidad" in resultado["danos_no_estimados"][0]["motivo"]


def test_pieza_sin_precio_se_reporta_y_no_se_suma_como_cero():
    resultado = calcular_estimado(
        VEHICULO_MAZDA,
        [dano()],
        [asignacion(pieza="Puerta")],
        catalogo_severidades(pieza="Bumper delantero"),
    )

    assert len(resultado["desglose"]) == 1
    assert resultado["desglose"][0]["estimado"] is False
    assert resultado["desglose"][0]["precios"] == {
        "economico": None,
        "multimarca": None,
        "concesionario": None,
    }
    assert resultado["totales"]["economico"]["minimo_cop"] is None
    assert resultado["piezas_sin_precio"][0]["establecimientos"] == [
        "economico",
        "multimarca",
        "concesionario",
    ]
    assert resultado["danos_no_estimados"][0]["indice_dano"] == 0


def test_establecimiento_sin_precio_no_devuelve_total_cero_completo():
    precios = [
        precio(tipo_establecimiento="economico", minimo=100_000, maximo=200_000),
        precio(tipo_establecimiento="multimarca", minimo=300_000, maximo=400_000),
    ]
    resultado = calcular_estimado(VEHICULO_MAZDA, [dano()], [asignacion()], precios)

    assert resultado["danos_no_estimados"] == []
    assert resultado["totales"]["economico"]["minimo_cop"] == 100_000
    assert resultado["totales"]["economico"]["completo"] is True
    assert resultado["totales"]["concesionario"] == {
        "minimo_cop": None,
        "maximo_cop": None,
        "completo": False,
        "piezas_no_estimadas": ["Bumper delantero"],
    }
    assert resultado["piezas_sin_precio"] == [
        {
            "pieza": "Bumper delantero",
            "pieza_original": "Bumper delantero",
            "piezas_originales": ["Bumper delantero"],
            "es_categoria_generica": False,
            "severidad": "leve",
            "establecimientos": ["concesionario"],
        }
    ]


def test_confianza_menor_al_minimo_se_ignora():
    resultado = calcular_estimado(
        VEHICULO_MAZDA,
        [dano(confianza=0.249)],
        [asignacion()],
        catalogo_severidades(),
    )

    assert resultado["desglose"] == []
    assert resultado["danos_no_estimados"] == []
    assert resultado["danos_ignorados"][0]["indice_dano"] == 0
    assert resultado["totales"]["economico"]["minimo_cop"] == 0
    assert resultado["totales"]["economico"]["completo"] is True


def test_confianza_exactamente_en_el_minimo_se_estima():
    resultado = calcular_estimado(
        VEHICULO_MAZDA,
        [dano(confianza=0.25)],
        [asignacion()],
        catalogo_severidades(),
    )

    assert len(resultado["desglose"]) == 1
    assert resultado["danos_ignorados"] == []


def test_no_usa_el_precio_de_una_severidad_menor_si_falta_la_grave():
    resultado = calcular_estimado(
        VEHICULO_MAZDA,
        [dano("leve"), dano("grave")],
        [asignacion(0), asignacion(1)],
        catalogo_severidades(),
    )

    assert len(resultado["desglose"]) == 1
    assert resultado["desglose"][0]["severidad"] == "grave"
    assert resultado["desglose"][0]["precios"]["economico"] == {
        "minimo_cop": 1_300_000,
        "maximo_cop": 1_400_000,
    }

    precios_sin_grave = [precio(severidad="leve", minimo=100_000, maximo=200_000)]
    resultado_sin_grave = calcular_estimado(
        VEHICULO_MAZDA,
        [dano("leve"), dano("grave")],
        [asignacion(0), asignacion(1)],
        precios_sin_grave,
    )

    assert resultado_sin_grave["desglose"][0]["severidad"] == "grave"
    assert resultado_sin_grave["desglose"][0]["precios"]["economico"] is None
    assert len(resultado_sin_grave["danos_no_estimados"]) == 2


def test_lista_de_danos_vacia_devuelve_totales_cero():
    resultado = calcular_estimado(VEHICULO_MAZDA, [], [], catalogo_severidades())

    assert resultado["desglose"] == []
    assert resultado["danos_no_estimados"] == []
    assert resultado["totales"]["economico"] == {
        "minimo_cop": 0,
        "maximo_cop": 0,
        "completo": True,
        "piezas_no_estimadas": [],
    }
    assert resultado["advertencias"] == ["No se recibieron daños para estimar."]


def test_totales_independientes_por_establecimiento():
    precios = catalogo_severidades(pieza="Bumper delantero") + [
        precio(
            pieza="Puerta",
            tipo_establecimiento="economico",
            minimo=50_000,
            maximo=60_000,
        ),
        precio(
            pieza="Puerta",
            tipo_establecimiento="multimarca",
            minimo=70_000,
            maximo=80_000,
        ),
        precio(
            pieza="Puerta",
            tipo_establecimiento="concesionario",
            minimo=90_000,
            maximo=100_000,
        ),
    ]

    resultado = calcular_estimado(
        VEHICULO_MAZDA,
        [dano("leve"), dano("leve")],
        [asignacion(0, "Bumper delantero"), asignacion(1, "Puerta")],
        precios,
    )

    assert resultado["totales"]["economico"]["minimo_cop"] == 150_000
    assert resultado["totales"]["economico"]["maximo_cop"] == 260_000
    assert resultado["totales"]["multimarca"]["minimo_cop"] == 370_000
    assert resultado["totales"]["multimarca"]["maximo_cop"] == 480_000
    assert resultado["totales"]["concesionario"]["minimo_cop"] == 590_000
    assert resultado["totales"]["concesionario"]["maximo_cop"] == 700_000


def test_redondea_totales_al_multiplo_de_10000_sin_cambiar_precios_base():
    precios = [precio(minimo=12_345, maximo=67_890)]
    resultado = calcular_estimado(VEHICULO_MAZDA, [dano()], [asignacion()], precios)

    assert resultado["desglose"][0]["precios"]["economico"] == {
        "minimo_cop": 12_345,
        "maximo_cop": 67_890,
    }
    assert resultado["totales"]["economico"]["minimo_cop"] == 10_000
    assert resultado["totales"]["economico"]["maximo_cop"] == 70_000
    assert redondear_cop(125_000) == 130_000


def test_detecta_precios_duplicados_en_el_calculo():
    precios = [
        precio(minimo=100_000, maximo=200_000),
        precio(minimo=110_000, maximo=210_000),
    ]

    with pytest.raises(PreciosDuplicadosError):
        calcular_estimado(VEHICULO_MAZDA, [dano()], [asignacion()], precios)


def _escribir_csv(ruta: Path, filas: list[dict]) -> Path:
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=COLUMNAS_PRECIOS)
        writer.writeheader()
        writer.writerows(filas)
    return ruta


def test_cargar_csv_detecta_duplicados(tmp_path):
    fila = {
        "marca": "Mazda",
        "modelo": "Mazda2 Sport",
        "pieza": "Bumper delantero",
        "severidad": "leve",
        "tipo_establecimiento": "economico",
        "precio_min_cop": 100_000,
        "precio_max_cop": 200_000,
        "moneda": "COP",
        "origen": "prueba",
        "es_estimacion": "true",
    }
    ruta = _escribir_csv(tmp_path / "duplicados.csv", [fila, fila])

    with pytest.raises(PreciosDuplicadosError):
        cargar_precios_csv(ruta)


def test_cargar_csv_detecta_rango_invalido(tmp_path):
    fila = {
        "marca": "Mazda",
        "modelo": "Mazda2 Sport",
        "pieza": "Bumper delantero",
        "severidad": "leve",
        "tipo_establecimiento": "economico",
        "precio_min_cop": 300_000,
        "precio_max_cop": 200_000,
        "moneda": "COP",
        "origen": "prueba",
        "es_estimacion": "true",
    }
    ruta = _escribir_csv(tmp_path / "rango_invalido.csv", [fila])

    with pytest.raises(ValueError):
        cargar_precios_csv(ruta)


class _FakeQuery:
    def __init__(self, data: list[dict]):
        self.data = data

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self.data)


class _FakeClient:
    def __init__(self, vehiculos: list[dict]):
        self.vehiculos = vehiculos
        self.llamadas: list[str] = []

    def table(self, nombre: str):
        self.llamadas.append(nombre)
        if nombre != "vehiculos":
            raise AssertionError(f"El endpoint no debe consultar ni escribir en {nombre}")
        return _FakeQuery(self.vehiculos)


def _crear_cliente_http(monkeypatch, vehiculos: list[dict]) -> tuple[TestClient, _FakeClient]:
    fake_client = _FakeClient(vehiculos)
    monkeypatch.setattr(cotizaciones, "client", fake_client)

    app = FastAPI()
    app.include_router(cotizaciones.router, prefix="/api/v1")
    app.dependency_overrides[get_usuario_con_rol] = lambda: {
        "id": 1,
        "correo": "prueba@test.com",
        "rol": "cliente",
        "activo": True,
    }
    return TestClient(app), fake_client


def _payload_estimacion() -> dict:
    return {
        "vehiculo_id": 7,
        "danos": [{"tipo_dano": "rayon", "severidad": "leve", "confianza": 0.91}],
        "asignaciones": [{"indice_dano": 0, "pieza": "Bumper delantero"}],
    }


def test_endpoint_estimar_usa_el_csv_y_no_escribe_en_base_de_datos(monkeypatch):
    cliente, fake_client = _crear_cliente_http(
        monkeypatch,
        [{"id": 7, "marca": "Mazda", "modelo": "Mazda2 Sport"}],
    )

    respuesta = cliente.post("/api/v1/cotizaciones/estimar", json=_payload_estimacion())

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["vehiculo_id"] == 7
    assert cuerpo["moneda"] == "COP"
    assert cuerpo["desglose"][0]["precios"]["economico"] == {
        "minimo_cop": 180_000,
        "maximo_cop": 400_000,
    }
    assert cuerpo["totales"]["economico"]["minimo_cop"] == 180_000
    assert fake_client.llamadas == ["vehiculos"]


def test_endpoint_estimar_vehiculo_inexistente(monkeypatch):
    cliente, _ = _crear_cliente_http(monkeypatch, [])

    respuesta = cliente.post("/api/v1/cotizaciones/estimar", json=_payload_estimacion())

    assert respuesta.status_code == 404


def test_endpoint_estimar_pieza_sin_equivalencia_queda_pendiente(monkeypatch):
    cliente, fake_client = _crear_cliente_http(
        monkeypatch,
        [{"id": 7, "marca": "Mazda", "modelo": "Mazda2 Sport"}],
    )
    payload = _payload_estimacion()
    payload["asignaciones"] = [{"indice_dano": 0, "pieza": "Faro Principal Derecho"}]

    respuesta = cliente.post("/api/v1/cotizaciones/estimar", json=payload)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["desglose"] == []
    assert cuerpo["danos_no_estimados"][0]["pieza_original"] == "Faro Principal Derecho"
    assert cuerpo["totales"]["economico"]["minimo_cop"] is None
    assert cuerpo["totales"]["economico"]["completo"] is False
    assert fake_client.llamadas == ["vehiculos"]


def test_endpoint_estimar_pieza_real_conserva_original_y_usa_categoria(monkeypatch):
    cliente, fake_client = _crear_cliente_http(
        monkeypatch,
        [{"id": 7, "marca": "Mazda", "modelo": "Mazda2 Sport"}],
    )
    payload = _payload_estimacion()
    payload["asignaciones"] = [{"indice_dano": 0, "pieza": "Parachoques Delantero"}]

    respuesta = cliente.post("/api/v1/cotizaciones/estimar", json=payload)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["desglose"][0]["pieza"] == "Bumper delantero"
    assert cuerpo["desglose"][0]["pieza_original"] == "Parachoques Delantero"
    assert cuerpo["desglose"][0]["es_categoria_generica"] is True
    assert cuerpo["desglose"][0]["precios"]["economico"] == {
        "minimo_cop": 180_000,
        "maximo_cop": 400_000,
    }
    assert fake_client.llamadas == ["vehiculos"]


def test_endpoint_estimar_modelo_real_con_anio_usa_modelo_base(monkeypatch):
    cliente, fake_client = _crear_cliente_http(
        monkeypatch,
        [{"id": 7, "marca": "Mazda", "modelo": "CX-30 2023"}],
    )
    payload = _payload_estimacion()
    payload["danos"][0]["severidad"] = "moderado"
    payload["asignaciones"] = [
        {"indice_dano": 0, "pieza": "Guardabarros Delantero Derecho"}
    ]

    respuesta = cliente.post("/api/v1/cotizaciones/estimar", json=payload)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["modelo_csv"] == "CX-30"
    assert cuerpo["anio_detectado"] == 2023
    assert cuerpo["coincidencia_modelo"] == "modelo_base"
    assert cuerpo["desglose"][0]["pieza"] == "Guardabarros"
    assert cuerpo["desglose"][0]["pieza_original"] == "Guardabarros Delantero Derecho"
    assert cuerpo["desglose"][0]["estimado"] is True
    assert any("no es específico del año 2023" in a for a in cuerpo["advertencias"])
    assert fake_client.llamadas == ["vehiculos"]


@pytest.mark.parametrize(
    "payload",
    [
        {
            "vehiculo_id": 7,
            "danos": [{"tipo_dano": "rayon", "severidad": "leve", "confianza": 0.91}],
            "asignaciones": [
                {"indice_dano": 0, "pieza": "Bumper delantero"},
                {"indice_dano": 0, "pieza": "Puerta"},
            ],
        },
        {
            "vehiculo_id": 7,
            "danos": [{"tipo_dano": "rayon", "severidad": "leve", "confianza": 0.91}],
            "asignaciones": [{"indice_dano": 3, "pieza": "Bumper delantero"}],
        },
    ],
)
def test_endpoint_estimar_valida_indices_de_asignaciones(monkeypatch, payload):
    cliente, _ = _crear_cliente_http(
        monkeypatch,
        [{"id": 7, "marca": "Mazda", "modelo": "Mazda2 Sport"}],
    )

    respuesta = cliente.post("/api/v1/cotizaciones/estimar", json=payload)

    assert respuesta.status_code == 422
