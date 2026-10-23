"""
Pruebas de regresión contra cotizadores bancarios reales.

Estas pruebas son el contrato del motor con el mundo real: si pasan, el motor
reproduce lo que el banco calcula. Si alguna falla después de un cambio, el
cambio rompió la compatibilidad con una institución, no "la prueba está mal".

ESTADO ACTUAL: los renglones de HSBC y Santander se validan contra el MOTOR.
Banregio todavía valida su implementación de referencia (`_construir_banregio`)
porque el motor aún no soporta días reales ni base de amortización separada.

PENDIENTE: cuando el motor soporte las convenciones de
docs/validacion_modelos.md sección 5, hay que SUSTITUIR cada `_construir_*` por
una llamada al motor. Ese es el momento en que estas pruebas dejan de validar
código de referencia y pasan a validar el producto. No borres las funciones de
referencia al hacerlo: sirven de contraste si el motor empieza a divergir.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal as D

import pytest

from motor_hipotecario.amortizacion import construir_tabla
from motor_hipotecario.modelos import ConvencionDias, LineaCredito, ProductoHipotecario

from .fixtures.cotizadores_reales import BANREGIO, HSBC, SANTANDER

TOL = D("0.005")  # medio centavo


def _construir_hsbc(p):
    """tasa/12 en todo. Sin redondeo intermedio."""
    i = p["tasa_anual"] / D(12)
    n = p["plazo_meses"]
    pago = p["monto"] * i / (1 - (1 + i) ** -n)
    saldo = p["monto"]
    filas = {}
    for m in range(1, n + 1):
        interes = saldo * i
        vida = saldo * p["seguro_vida_mensual"]
        cuota = min(saldo + interes, pago)
        capital = cuota - interes
        total = cuota + vida + p["seguro_danos_mensual"] + p["comision_mensual"]
        saldo = saldo - capital
        filas[m] = (capital, interes, vida, total, saldo)
    return filas


def _construir_santander(p):
    """Dos factores distintos: uno para el pago, otro para el interés."""
    tasa = p["tasa_anual"]
    i_pago = tasa / D(360) * (D(365) / D(12))
    i_int = tasa * D("30.4166") / D(360)
    n = p["plazo_meses"]
    pago = p["monto"] * i_pago / (1 - (1 + i_pago) ** -n)
    saldo = p["monto"]
    filas = {}
    for m in range(1, n + 1):
        interes = saldo * i_int
        vida = saldo * p["seguro_vida_mensual"]
        cuota = min(saldo + interes, pago)
        capital = cuota - interes
        total = cuota + vida + p["seguro_danos_mensual"] + p["comision_mensual"]
        saldo = saldo - capital
        filas[m] = (interes, capital, vida, total, saldo)
    return filas


def _construir_banregio(p):
    """Interés con días reales; amortización con tasa/12."""
    tasa = p["tasa_anual"]
    y, mo, _ = map(int, p["fecha_primer_pago"].split("-"))
    saldo = p["monto"]
    filas = {}
    for m in range(1, p["plazo_meses"] + 1):
        dias = D(calendar.monthrange(y, mo)[1])
        interes = saldo * tasa * dias / D(360)
        seguro = p["seguro_fijo"] + p["seguro_tasa_saldo"] * saldo
        capital = p["pago_base_fijo"] - seguro - saldo * tasa / D(12)
        capital = min(capital, saldo)
        total = interes + capital + p["comision_mensual"] + seguro
        filas[m] = (f"{y:04d}-{mo:02d}-01", saldo, interes, capital, seguro, total)
        saldo -= capital
        mo += 1
        if mo > 12:
            mo = 1
            y += 1
    return filas


def _cat(flujos, neto):
    fl = [-float(neto)] + [float(f) for f in flujos]
    def vpn(r):
        return sum(f / ((1 + r) ** k) for k, f in enumerate(fl))
    lo, hi = 1e-9, 2.0
    for _ in range(300):
        mid = (lo + hi) / 2
        if vpn(mid) > 0:
            lo = mid
        else:
            hi = mid
    return D(repr((1 + (lo + hi) / 2) ** 12 - 1))


def _tabla_desde_motor(p, institucion, **convenciones):
    """
    Corre un escenario de cotizador en el motor. El seguro de daños y la
    comisión mensual son montos fijos, como vienen en el archivo; el valor del
    inmueble no interviene.
    """
    valor = D("1000000")
    producto = ProductoHipotecario(
        id=institucion.lower(),
        institucion=institucion,
        nombre="Escenario del cotizador",
        tasa_anual=p["tasa_anual"],
        plazos_meses=(p["plazo_meses"],),
        aforo_max=D("1"),
        seguro_vida_mensual=p["seguro_vida_mensual"],
        seguro_danos_monto_mensual=p["seguro_danos_mensual"],
        comision_mensual=p["comision_mensual"],
        **convenciones,
    )
    return construir_tabla(LineaCredito(producto, p["monto"], p["plazo_meses"]), valor)


def _hsbc_desde_motor(p):
    """Con la forma de `_construir_hsbc`."""
    tabla = _tabla_desde_motor(p, "HSBC")
    return {
        r.mes: (r.capital, r.interes, r.seguro_vida,
                r.pago_total, r.saldo_final)
        for r in tabla.renglones
    }


def _santander_desde_motor(p):
    """Con la forma de `_construir_santander`: dos convenciones distintas."""
    tabla = _tabla_desde_motor(
        p, "Santander",
        convencion_interes=ConvencionDias.DIAS_30_4166_360,
        convencion_pago=ConvencionDias.DIAS_365_12_360,
    )
    return {
        r.mes: (r.interes, r.capital, r.seguro_vida,
                r.pago_total, r.saldo_final)
        for r in tabla.renglones
    }


# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mes", sorted(HSBC["renglones"]))
def test_hsbc_renglones(mes):
    filas = _hsbc_desde_motor(HSBC["parametros"])
    esperado = HSBC["renglones"][mes]
    for calc, esp, nombre in zip(filas[mes], esperado,
                                 ["capital", "interés", "seguro vida", "pago total", "saldo"]):
        assert abs(calc - esp) < TOL, f"mes {mes}, {nombre}: {calc} != {esp}"


def test_hsbc_motor_coincide_con_referencia_en_todos_los_renglones():
    """
    El fixture solo trae cinco meses de control. La referencia está validada
    contra los 240 renglones del archivo (docs/validacion_modelos.md), así que
    se usa de contraste para cubrir los meses intermedios.
    """
    p = HSBC["parametros"]
    motor = _hsbc_desde_motor(p)
    referencia = _construir_hsbc(p)
    assert len(motor) == p["plazo_meses"]
    for mes in range(1, p["plazo_meses"] + 1):
        for calc, ref, nombre in zip(motor[mes], referencia[mes],
                                     ["capital", "interés", "seguro vida", "pago total", "saldo"]):
            assert abs(calc - ref) < TOL, f"mes {mes}, {nombre}: {calc} != {ref}"


def test_hsbc_cat():
    p = HSBC["parametros"]
    iva = D("1.16")
    flujos = []
    saldo = p["monto"]
    i = p["tasa_anual"] / D(12)
    n = p["plazo_meses"]
    pago = p["monto"] * i / (1 - (1 + i) ** -n)
    for m in range(1, n + 1):
        interes = saldo * i
        vida = saldo * p["seguro_vida_mensual"]
        cuota = min(saldo + interes, pago)
        # IVA excluido solo de los conceptos que lo causan
        flujos.append(cuota + vida
                      + p["seguro_danos_mensual"] / iva
                      + p["comision_mensual"] / iva)
        saldo -= cuota - interes
    neto = p["monto"] - p["monto"] * p["comision_apertura_pct"] - p["avaluo"] / iva
    assert abs(neto - HSBC["cat_desembolso_neto"]) < TOL
    assert abs(_cat(flujos, neto) - HSBC["cat_esperado"]) < D("0.0000001")


@pytest.mark.parametrize("mes", sorted(SANTANDER["renglones"]))
def test_santander_renglones(mes):
    filas = _santander_desde_motor(SANTANDER["parametros"])
    esperado = SANTANDER["renglones"][mes]
    for calc, esp, nombre in zip(filas[mes], esperado,
                                 ["interés", "capital", "seguro vida", "pago total", "saldo"]):
        assert abs(calc - esp) < TOL, f"mes {mes}, {nombre}: {calc} != {esp}"


def test_santander_motor_coincide_con_referencia_en_todos_los_renglones():
    """Mismo contraste que HSBC, en los 300 meses."""
    p = SANTANDER["parametros"]
    motor = _santander_desde_motor(p)
    referencia = _construir_santander(p)
    assert len(motor) == p["plazo_meses"]
    for mes in range(1, p["plazo_meses"] + 1):
        for calc, ref, nombre in zip(motor[mes], referencia[mes],
                                     ["interés", "capital", "seguro vida", "pago total", "saldo"]):
            assert abs(calc - ref) < TOL, f"mes {mes}, {nombre}: {calc} != {ref}"


def test_santander_cat():
    """
    A diferencia de HSBC, el CAT de Santander solo se reproduce con el seguro de
    daños y la comisión mensual COMPLETOS. La comisión por apertura ya viene
    neta de IVA en el archivo. No se sabe si los montos de daños y comisión del
    archivo ya son netos o si Santander los mete con IVA: queda para riesgo.
    """
    p = SANTANDER["parametros"]
    tasa = p["tasa_anual"]
    i_pago = tasa / D(360) * (D(365) / D(12))
    i_int = tasa * D("30.4166") / D(360)
    n = p["plazo_meses"]
    pago = p["monto"] * i_pago / (1 - (1 + i_pago) ** -n)
    flujos = []
    saldo = p["monto"]
    for _ in range(n):
        interes = saldo * i_int
        vida = saldo * p["seguro_vida_mensual"]
        cuota = min(saldo + interes, pago)
        flujos.append(cuota + vida + p["seguro_danos_mensual"] + p["comision_mensual"])
        saldo -= cuota - interes
    neto = p["monto"] - p["comision_apertura"]
    tolerancia = SANTANDER["tolerancia_cat_pb"] / D(10000)
    assert abs(_cat(flujos, neto) - SANTANDER["cat_esperado"]) < tolerancia


@pytest.mark.parametrize("mes", sorted(BANREGIO["renglones"]))
def test_banregio_renglones(mes):
    filas = _construir_banregio(BANREGIO["parametros"])
    fecha, saldo, interes, capital, seguro, total = filas[mes]
    e_fecha, e_saldo, e_int, e_cap, e_seg, e_tot = BANREGIO["renglones"][mes]
    assert fecha == e_fecha
    for calc, esp, nombre in [(saldo, e_saldo, "saldo"), (interes, e_int, "interés"),
                              (capital, e_cap, "amortización"), (seguro, e_seg, "seguros"),
                              (total, e_tot, "pago")]:
        assert abs(calc - esp) < TOL, f"mes {mes}, {nombre}: {calc} != {esp}"


def test_banregio_pago_no_es_fijo():
    """
    El producto se llama 'pagos fijos' pero el pago varía con los días del mes.

    Se comparan diciembre 2023 (31 días) contra febrero 2024 (29 días): el saldo
    apenas cambió entre ambos, así que la diferencia es atribuible al calendario.
    """
    filas = _construir_banregio(BANREGIO["parametros"])
    dic = filas[1][5]
    feb = filas[3][5]
    assert abs(dic - BANREGIO["pago_dic_2023"]) < D("0.01")
    assert abs(feb - BANREGIO["pago_feb_2024"]) < D("0.01")
    assert dic - feb > BANREGIO["variacion_primer_anio"]
