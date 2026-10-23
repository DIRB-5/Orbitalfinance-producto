"""Pruebas de la API: contrato de nombres, serialización y orden."""

from decimal import Decimal

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

cliente = TestClient(app)

ESCENARIO = {
    "valorVivienda": "2500000",
    "enganche": "650000",
    "plazoMeses": 240,
    "gastosNotariales": "140000",
    "ingresoMensual": "90000",
    "factorPagoIngreso": "0.35",
}


def test_catalogo_en_camel_case_y_decimales_como_texto():
    productos = cliente.get("/api/catalogo").json()["productos"]
    assert {p["institucion"] for p in productos} == {"HSBC", "Santander"}
    hsbc = next(p for p in productos if p["institucion"] == "HSBC")
    assert hsbc["tasaAnual"] == "0.1175"
    assert hsbc["comisionMensual"] == "290.00"
    assert hsbc["seguroDanosMontoMensual"] == "777.63"
    assert hsbc["catNetosDeIva"] == ["avaluo", "comision_mensual", "seguro_danos"]
    assert hsbc["crecimientoPagoAnual"] == "0"
    assert hsbc["tasasEscalonadas"] == []


def test_comparar_ordena_por_costo_total_y_rotula_cat_estimado():
    respuesta = cliente.post("/api/comparar", json=ESCENARIO)
    assert respuesta.status_code == 200
    opciones = respuesta.json()["opciones"]
    elegibles = [o for o in opciones if o["elegible"]]
    costos = [Decimal(o["costoTotal"]) for o in elegibles]
    assert costos == sorted(costos)
    for o in opciones:
        assert "catEstimado" in o and "cat" not in o
        assert len(o["tabla"]) == o["plazoEfectivoMeses"] <= o["plazoCalculadoMeses"]
        assert Decimal(o["costoTotal"]).as_tuple().exponent == -2


def test_escenario_invalido_responde_422():
    malo = dict(ESCENARIO, enganche="3000000")
    assert cliente.post("/api/comparar", json=malo).status_code == 422


def test_renglones_traen_fecha_de_pago():
    cuerpo = dict(ESCENARIO, fechaPrimerPago="2027-01-01")
    datos = cliente.post("/api/comparar", json=cuerpo).json()
    assert datos["fechaPrimerPago"] == "2027-01-01"
    tabla = datos["opciones"][0]["tabla"]
    assert [r["fechaPago"] for r in tabla[:2]] == ["2027-01-01", "2027-02-01"]


def test_cofinanciamiento_sin_productos_que_lo_acepten():
    """El catálogo actual no tiene productos de cofinanciamiento: todos quedan
    no elegibles con su motivo, y el crédito bancario se reduce."""
    cuerpo = dict(ESCENARIO, cofinanciamiento={
        "instituto": "infonavit", "salarioMensual": "60000",
        "montoCreditoInstituto": "300000", "saldoSubcuenta": "150000",
    })
    opciones = cliente.post("/api/comparar", json=cuerpo).json()["opciones"]
    assert opciones and not any(o["elegible"] for o in opciones)
    assert all(o["montoCredito"] == "1400000.00" for o in opciones)
    assert all("INFONAVIT" in " ".join(o["motivosRechazo"]) for o in opciones)

