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


# Cumple todas las condiciones de campaña (Credirenovación Vinculación,
# Premium y Green): para probar el cálculo, no la regla de requisitos.
TODAS_LAS_CONDICIONES = {
    "condicionesCliente": ["vinculacion_scotiabank", "premium_scotiabank", "ecotecnologias"],
}

def test_catalogo_en_camel_case_y_decimales_como_texto():
    productos = cliente.get("/api/catalogo").json()["productos"]
    assert {p["institucion"] for p in productos} == {"HSBC", "Santander", "Banregio", "Banorte", "BX+", "Banamex", "Scotiabank", "Afirme"}
    hsbc = next(p for p in productos if p["institucion"] == "HSBC")
    assert hsbc["tasaAnual"] == "0.1175"
    assert hsbc["comisionMensual"] == "290.00"
    assert hsbc["seguroDanosMontoMensual"] == "777.63"
    assert hsbc["catNetosDeIva"] == ["avaluo", "comision_mensual", "seguro_danos"]
    assert hsbc["crecimientoPagoMensual"] == []
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


def test_cofinanciamiento_con_alternativas_sin_cofinanciamiento():
    """Con INFONAVIT: BX+ Cofinavit lo usa (crédito bancario de 1.4 millones y
    crédito del instituto); los demás bancarios se muestran como alternativa
    (el banco financia 1.85 millones) y Banorte FOVISSSTE no aparece."""
    cuerpo = dict(ESCENARIO, cofinanciamiento={
        "instituto": "infonavit", "salarioMensual": "60000",
        "montoCreditoInstituto": "300000", "saldoSubcuenta": "150000",
    })
    opciones = cliente.post("/api/comparar", json=cuerpo).json()["opciones"]
    for o in opciones:
        if o["productoId"].startswith("banorte-fovissste"):
            assert not o["elegible"]
        elif o["productoId"].startswith("bx-apoyo"):
            assert not o["elegible"]  # con crédito Infonavit aplica Cofinavit
        elif o["productoId"].startswith("afirme-tu-casa-2"):
            assert not o["elegible"]  # sin garantía adicional ni gastos financiados
        elif o["productoId"].startswith("scotiabank-credirenovacion-compra"):
            assert not o["elegible"]  # sin presupuesto de obra
        elif o["productoId"].startswith("bx-cofinavit"):
            assert o["elegible"] and not o["alternativaSinCofinanciamiento"]
            assert o["montoCredito"] == "1400000.00"
            assert o["creditoInstituto"]["monto"] == "300000.00"
        else:
            assert o["elegible"] and o["alternativaSinCofinanciamiento"]
            assert o["montoCredito"] == "1850000.00"


def test_opcion_trae_la_tasa_resuelta_para_el_escenario():
    """Banregio publica 11.00 % como referencia; a 240 meses y 74 % de aforo
    su tabla da 11.00 %, a 120 meses da 10.20 %."""
    for plazo, tasa in ((240, "0.11"), (120, "0.102")):
        datos = cliente.post("/api/comparar", json=dict(ESCENARIO, plazoMeses=plazo)).json()
        banregio = next(o for o in datos["opciones"] if o["productoId"].startswith("banregio"))
        assert banregio["tasaAnual"] == tasa


def test_credito_fovissste_en_cofinanciamiento_bancario_es_invalido():
    cuerpo = dict(ESCENARIO, cofinanciamiento={
        "instituto": "fovissste", "salarioMensual": "40000", "montoCreditoInstituto": "200000",
    })
    respuesta = cliente.post("/api/comparar", json=cuerpo)
    assert respuesta.status_code == 422
    assert "FOVISSSTE" in respuesta.json()["detail"]


def test_opcion_trae_el_pago_regular():
    opciones = cliente.post("/api/comparar", json=ESCENARIO).json()["opciones"]
    banorte = next(o for o in opciones if o["productoId"].startswith("banorte-hipoteca"))
    assert banorte["primerPagoIrregular"] and banorte["diasPrimerPeriodo"]
    assert Decimal(banorte["pagoRegularInicial"]) > Decimal(banorte["pagoPrimerMes"])
    santander = next(o for o in opciones if o["productoId"].startswith("santander"))
    assert not santander["primerPagoIrregular"]
    assert santander["pagoRegularInicial"] == santander["pagoPrimerMes"]


def test_sustitucion_por_api():
    cuerpo = {
        "valorVivienda": "3000000", "enganche": "1500000", "plazoMeses": 180,
        "gastosNotariales": "60000", "destino": "sustitucion",
        "creditoActual": {"saldoInsoluto": "1500000", "pagoMensual": "21000",
                          "plazoRemanenteMeses": 180, "penalizacionPrepago": "0"},
    }
    opciones = cliente.post("/api/comparar", json=cuerpo).json()["opciones"]
    assert opciones and all(o["productoId"] for o in opciones)
    elegibles = [o for o in opciones if o["elegible"]]
    assert elegibles
    for o in elegibles:
        assert o["ahorroMensual"] is not None and o["costoDeCambiarse"] is not None
        assert len(o["serieAhorro"]) >= 180


def test_liquidez_por_api_trae_iva_de_intereses():
    cuerpo = {"valorVivienda": "3000000", "enganche": "1500000", "plazoMeses": 120,
              "destino": "liquidez"}
    opciones = cliente.post("/api/comparar", json=cuerpo).json()["opciones"]
    banorte = next(o for o in opciones if o["productoId"] == "banorte-liquidez-2026-06")
    assert Decimal(banorte["tabla"][1]["ivaIntereses"]) > 0


def test_sustitucion_sin_credito_actual_es_invalida():
    cuerpo = {"valorVivienda": "3000000", "enganche": "1500000", "plazoMeses": 180,
              "destino": "sustitucion"}
    assert cliente.post("/api/comparar", json=cuerpo).status_code == 422


def test_catalogo_expone_el_crecimiento_anual_del_pago():
    productos = {p["id"]: p for p in cliente.get("/api/catalogo").json()["productos"]}
    assert productos["scotiabank-pasivos-valora-2026-07-v2"]["crecimientoPagoAnual"] == "0.017"
    assert productos["scotiabank-pasivos-pagos-oportunos-2026-07-v2"]["crecimientoPagoAnual"] is None



def test_gastos_notariales_financiados_por_api():
    cuerpo = {
        "valorVivienda": "3000000", "enganche": "1500000", "plazoMeses": 240,
        "gastosNotariales": "120000", "financiarGastosNotariales": True, "destino": "sustitucion",
        "creditoActual": {"saldoInsoluto": "1500000", "pagoMensual": "21000",
                          "plazoRemanenteMeses": 240},
    }
    opciones = {o["productoId"]: o for o in cliente.post("/api/comparar", json=cuerpo).json()["opciones"]}
    scotia = opciones["scotiabank-pasivos-pagos-oportunos-2026-07-v2"]
    assert scotia["gastosFinanciados"] == "90000.00"
    assert scotia["gastosDeContado"] == "30000.00"
    assert scotia["montoCredito"] == "1590000.00"
    productos = {p["id"]: p for p in cliente.get("/api/catalogo").json()["productos"]}
    assert productos["scotiabank-pasivos-pagos-oportunos-2026-07-v2"]["financiamientoGastos"] == {
        "tope": "0.06", "baseTope": "monto_credito", "aperturaYAforoSobreTotal": False,
        "incluyeAperturaYAvaluo": False, "lineaSeparada": False,
    }
    santander = opciones["santander-sustitucion-2025-12"]
    assert santander["montoCredito"] == "1500000.00"
    assert santander["lineaGastos"]["monto"] == "105000.00"
    assert santander["lineaGastos"]["catEstimado"].startswith("0.129557")
    assert productos["hsbc-cicb-2026-10"]["financiamientoGastos"] is None


def test_garantia_adicional_por_api():
    cuerpo = {"valorVivienda": "3000000", "enganche": "0", "plazoMeses": 180,
              "gastosNotariales": "150000", "financiarGastosNotariales": True,
              "valorGarantiaAdicional": "1500000"}
    opciones = {o["productoId"]: o for o in cliente.post("/api/comparar", json=cuerpo).json()["opciones"]}
    tu_casa = opciones["afirme-tu-casa-2-2026-07"]
    assert tu_casa["elegible"], tu_casa["motivosRechazo"]
    assert not opciones["afirme-adquisicion-2026-07"]["elegible"]   # 100 % del valor


def test_mejora_refinancia_el_credito_infonavit_por_api():
    cuerpo = {
        "valorVivienda": "3000000", "enganche": "1800000", "plazoMeses": 180,
        "destino": "sustitucion",
        "creditoActual": {
            "saldoInsoluto": "1200000", "pagoMensual": "16000", "plazoRemanenteMeses": 180,
            "institucion": "Santander",
            "creditoInstituto": {"instituto": "infonavit", "saldo": "400000",
                                 "pagoMensual": "4500", "plazoRemanenteMeses": 180},
        },
    }
    opciones = {o["productoId"]: o for o in cliente.post("/api/comparar", json=cuerpo).json()["opciones"]}
    mejora = opciones["santander-mejora-condiciones-2025-12"]
    assert mejora["elegible"], mejora["motivosRechazo"]
    assert mejora["lineaInstituto"]["monto"] == "400000.00"
    assert mejora["lineaInstituto"]["catEstimado"].startswith("0.13530")
    # Los demás sustituyen solo el bancario
    assert opciones["banorte-mejora-hipoteca-2026-06"]["lineaInstituto"] is None


def test_credito_del_instituto_no_puede_ser_bancario():
    cuerpo = {"valorVivienda": "3000000", "enganche": "1800000", "plazoMeses": 180,
              "destino": "sustitucion",
              "creditoActual": {"saldoInsoluto": "1200000", "pagoMensual": "16000",
                                "plazoRemanenteMeses": 180,
                                "creditoInstituto": {"instituto": "bancario", "saldo": "1",
                                                     "pagoMensual": "1", "plazoRemanenteMeses": 1}}}
    assert cliente.post("/api/comparar", json=cuerpo).status_code == 422


def test_remodelacion_por_api():
    cuerpo = {**TODAS_LAS_CONDICIONES, "valorVivienda": "3000000", "enganche": "1500000", "plazoMeses": 120,
              "destino": "remodelacion"}
    opciones = cliente.post("/api/comparar", json=cuerpo).json()["opciones"]
    ids = {o["productoId"] for o in opciones if o["elegible"]}
    # Sin hipoteca vigente: los 8 de vivienda libre (la segunda hipoteca no aplica)
    assert len(ids) == 8 and all("credirenovacion" in i and "2a-hipoteca" not in i for i in ids)
    ninguna = next(o for o in opciones if o["productoId"].startswith("scotiabank-credirenovacion-valora-ninguna"))
    assert ninguna["dictamenTecnico"] == "15000.00"


def test_compra_con_remodelacion_por_api():
    cuerpo = {**TODAS_LAS_CONDICIONES, "valorVivienda": "3000000", "enganche": "800000", "plazoMeses": 240,
              "montoRemodelacion": "500000"}
    opciones = cliente.post("/api/comparar", json=cuerpo).json()["opciones"]
    elegibles = [o for o in opciones if o["elegible"]]
    assert len(elegibles) == 8
    assert all(o["productoId"].startswith("scotiabank-credirenovacion-compra") for o in elegibles)
    assert all(o["montoCredito"] == "2700000.00" and o["remodelacionFinanciada"] == "500000.00"
               for o in elegibles)
    hsbc = next(o for o in opciones if o["productoId"].startswith("hsbc"))
    assert any("remodelación" in m for m in hsbc["motivosRechazo"])


def test_pasivo_con_remodelacion_por_api():
    cuerpo = {
        "valorVivienda": "3000000", "enganche": "1500000", "plazoMeses": 240,
        **TODAS_LAS_CONDICIONES, "destino": "sustitucion", "montoRemodelacion": "500000",
        "creditoActual": {"saldoInsoluto": "1500000", "pagoMensual": "21000",
                          "plazoRemanenteMeses": 240, "institucion": "Banorte"},
    }
    opciones = cliente.post("/api/comparar", json=cuerpo).json()["opciones"]
    elegibles = [o for o in opciones if o["elegible"]]
    assert len(elegibles) == 6
    assert all(o["productoId"].startswith("scotiabank-credirenovacion-pasivo") for o in elegibles)
    assert all(o["montoCredito"] == "2000000.00" for o in elegibles)



def test_segunda_hipoteca_por_api():
    cuerpo = {
        "valorVivienda": "3000000", "enganche": "2500000", "plazoMeses": 120,
        **TODAS_LAS_CONDICIONES, "destino": "remodelacion",
        "creditoActual": {"saldoInsoluto": "1000000", "pagoMensual": "12000",
                          "plazoRemanenteMeses": 180, "institucion": "Scotiabank"},
    }
    opciones = cliente.post("/api/comparar", json=cuerpo).json()["opciones"]
    elegibles = [o for o in opciones if o["elegible"]]
    assert len(elegibles) == 6
    assert all("2a-hipoteca" in o["productoId"] and o["montoCredito"] == "500000.00" for o in elegibles)
    assert all(o["ahorroMensual"] is None for o in elegibles)


def test_ingreso_requerido_por_api():
    cuerpo = {"valorVivienda": "3000000", "enganche": "800000", "plazoMeses": 240,
              "montoRemodelacion": "500000"}
    opciones = {o["productoId"]: o for o in cliente.post("/api/comparar", json=cuerpo).json()["opciones"]}
    assert opciones["scotiabank-credirenovacion-compra-valora-ninguna-2026-07"]["ingresoRequerido"] == "83622.86"
    productos = {p["id"]: p for p in cliente.get("/api/catalogo").json()["productos"]}
    green = productos["scotiabank-credirenovacion-valora-green-2026-07"]
    assert green["factorPagoIngresoMax"] == "0.55" and green["ingresoMinimo"] == "20000.00"


def test_requisitos_del_cliente_por_api():
    catalogo = cliente.get("/api/catalogo").json()
    assert {r["id"] for r in catalogo["requisitosCliente"]} == {
        "vinculacion_scotiabank", "premium_scotiabank", "ecotecnologias"}
    premium = next(p for p in catalogo["productos"]
                   if p["id"] == "scotiabank-credirenovacion-valora-premium-2026-07")
    assert premium["requisitosCliente"] == ["premium_scotiabank"]
    cuerpo = {"valorVivienda": "3000000", "enganche": "1500000", "plazoMeses": 120,
              "destino": "remodelacion"}
    elegibles = [o["productoId"] for o in cliente.post("/api/comparar", json=cuerpo).json()["opciones"]
                 if o["elegible"]]
    assert len(elegibles) == 2 and all("ninguna" in i for i in elegibles)


def test_entregas_por_avance_de_obra_por_api():
    cuerpo = {"valorVivienda": "3000000", "enganche": "1500000", "plazoMeses": 120,
              "destino": "remodelacion",
              # Folleto julio 2026: 50 % a la firma, el resto con el avance de obra
              "ministraciones": [{"mes": 1, "monto": "750000"}, {"mes": 4, "monto": "750000"}]}
    opciones = cliente.post("/api/comparar", json=cuerpo).json()["opciones"]
    valora = next(o for o in opciones if o["productoId"] == "scotiabank-credirenovacion-valora-ninguna-2026-07")
    assert valora["elegible"]
    assert [r["disposicion"] for r in valora["tabla"][:5]] == ["0.00", "0.00", "0.00", "750000.00", "0.00"]
    assert valora["pagoRegularInicial"] == valora["tabla"][3]["pagoTotal"]



def test_catalogo_expone_la_base_de_la_supervision_de_obra():
    productos = {p["id"]: p for p in cliente.get("/api/catalogo").json()["productos"]}
    pasivo = productos["scotiabank-credirenovacion-pasivo-valora-ninguna-2026-07-v3"]
    assert (pasivo["dictamenTecnicoPct"], pasivo["dictamenTecnicoMaximo"]) == ("0.01", "18000.00")
    assert pasivo["dictamenSobreObra"] is True
    assert productos["scotiabank-credirenovacion-valora-ninguna-2026-07"]["dictamenSobreObra"] is False


def test_pasivo_con_remodelacion_cobra_la_supervision_por_api():
    cuerpo = {**TODAS_LAS_CONDICIONES, "valorVivienda": "3000000", "enganche": "1500000", "plazoMeses": 240,
              "destino": "sustitucion", "montoRemodelacion": "500000",
              "creditoActual": {"saldoInsoluto": "1500000", "pagoMensual": "18000",
                                "plazoRemanenteMeses": 240, "institucion": "Banorte"}}
    opciones = {o["productoId"]: o for o in cliente.post("/api/comparar", json=cuerpo).json()["opciones"]}
    pasivo = opciones["scotiabank-credirenovacion-pasivo-valora-ninguna-2026-07-v3"]
    assert pasivo["elegible"], pasivo["motivosRechazo"]
    assert pasivo["dictamenTecnico"] == "5000.00"
