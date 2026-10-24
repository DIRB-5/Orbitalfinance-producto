"""
Pruebas de regresión contra cotizadores bancarios reales.

Estas pruebas son el contrato del motor con el mundo real: si pasan, el motor
reproduce lo que el banco calcula. Si alguna falla después de un cambio, el
cambio rompió la compatibilidad con una institución, no "la prueba está mal".

ESTADO ACTUAL: los renglones de las tres instituciones se validan contra el
MOTOR. Las funciones `_construir_*` quedan como contraste.

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
from motor_hipotecario.cat import calcular_cat, flujos_cat
from motor_hipotecario.modelos import (
    BaseSeguroDanos,
    ConceptoIVA,
    ConvencionDias,
    LineaCredito,
    ProductoHipotecario,
)

from .fixtures.cotizadores_reales import (
    BANORTE_FOVISSSTE,
    BANREGIO,
    BANREGIO_CRECIENTE,
    HSBC,
    SANTANDER,
)

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


def _tabla_desde_motor(p, institucion, **campos):
    return _producto_y_tabla(p, institucion, **campos)[1]


def _producto_y_tabla(p, institucion, **convenciones):
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
    return producto, construir_tabla(LineaCredito(producto, p["monto"], p["plazo_meses"]), valor)


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


def test_hsbc_cat_desde_motor():
    """
    El motor reproduce el CAT del archivo con el tratamiento de IVA de HSBC:
    daños, comisión mensual y avalúo netos; apertura completa.
    """
    p = HSBC["parametros"]
    producto, tabla = _producto_y_tabla(
        p, "HSBC",
        comision_apertura=p["comision_apertura_pct"],
        avaluo=p["avaluo"],
        cat_netos_de_iva=frozenset(
            {ConceptoIVA.SEGURO_DANOS, ConceptoIVA.COMISION_MENSUAL, ConceptoIVA.AVALUO}
        ),
    )
    neto, flujos = flujos_cat(tabla, producto)
    assert abs(neto - HSBC["cat_desembolso_neto"]) < TOL
    assert abs(flujos[0] - D("24404.87026711205")) < D("0.0000001")
    assert abs(calcular_cat(tabla, producto) - HSBC["cat_esperado"]) < D("0.0000001")


def test_santander_cat_desde_motor():
    """Tratamiento de Santander: solo la apertura neta (7,000 / 1.16)."""
    p = SANTANDER["parametros"]
    producto, tabla = _producto_y_tabla(
        p, "Santander",
        convencion_interes=ConvencionDias.DIAS_30_4166_360,
        convencion_pago=ConvencionDias.DIAS_365_12_360,
        comision_apertura_monto=D("7000"),
        cat_netos_de_iva=frozenset({ConceptoIVA.COMISION_APERTURA}),
    )
    tolerancia = SANTANDER["tolerancia_cat_pb"] / D(10000)
    assert abs(calcular_cat(tabla, producto) - SANTANDER["cat_esperado"]) < tolerancia


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
    filas = _banregio_desde_motor(BANREGIO["parametros"])
    fecha, saldo, interes, capital, seguro, total = filas[mes]
    e_fecha, e_saldo, e_int, e_cap, e_seg, e_tot = BANREGIO["renglones"][mes]
    assert fecha == e_fecha
    for calc, esp, nombre in [(saldo, e_saldo, "saldo"), (interes, e_int, "interés"),
                              (capital, e_cap, "amortización"), (seguro, e_seg, "seguros"),
                              (total, e_tot, "pago")]:
        assert abs(calc - esp) < TOL, f"mes {mes}, {nombre}: {calc} != {esp}"


def _banregio_producto_y_tabla(p, **campos):
    """Daños como tasa sobre el valor de construcción, como en el archivo."""
    producto = ProductoHipotecario(
        id="banregio",
        institucion="Banregio",
        nombre="Escenario del cotizador",
        tasa_anual=p["tasa_anual"],
        plazos_meses=(p["plazo_meses"],),
        aforo_max=D("1"),
        convencion_interes=ConvencionDias.DIAS_REALES_360,
        convencion_pago=ConvencionDias.TASA_ENTRE_12,
        convencion_amortizacion=ConvencionDias.TASA_ENTRE_12,
        seguros_en_pago_fijo=True,
        seguro_vida_mensual=p["seguro_tasa_saldo"],
        seguro_danos_anual=p["seguro_danos_tasa_anual"],
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        factor_construccion=p["seguro_danos_factor_construccion"],
        comision_mensual=p["comision_mensual"],
        **campos,
    )
    tabla = construir_tabla(
        LineaCredito(producto, p["monto"], p["plazo_meses"]),
        p["valor_inmueble"],
        fecha_primer_pago=date.fromisoformat(p["fecha_primer_pago"]),
    )
    return producto, tabla


def test_banregio_danos_sobre_valor_reproduce_el_archivo_exacto():
    """Con el daño calculado sobre el valor (no el fijo cortado), el motor
    empata el archivo en toda la tabla de control."""
    _, tabla = _banregio_producto_y_tabla(BANREGIO["parametros"])
    for mes, (fecha, saldo, interes, capital, seguros, total) in BANREGIO["renglones"].items():
        r = tabla.renglones[mes - 1]
        for calc, esp in ((r.saldo_inicial, saldo), (r.interes, interes), (r.capital, capital),
                          (r.seguro_vida + r.seguro_danos, seguros), (r.pago_total, total)):
            assert abs(calc - esp) < D("0.000001"), f"mes {mes}: {calc} != {esp}"


def test_banregio_cat_desde_motor():
    p = BANREGIO["parametros"]
    producto, tabla = _banregio_producto_y_tabla(
        p,
        comision_apertura=p["comision_apertura_pct"],
        avaluo=p["avaluo"],
        cat_netos_de_iva=frozenset(
            {ConceptoIVA.AVALUO, ConceptoIVA.COMISION_MENSUAL, ConceptoIVA.SEGURO_DANOS}
        ),
    )
    neto, _ = flujos_cat(tabla, producto)
    assert abs(neto - D("1193130")) < TOL  # AA9
    assert abs(calcular_cat(tabla, producto) - BANREGIO["cat_esperado"]) < D("0.0000001")


def _banregio_desde_motor(p):
    """
    Con la forma de `_construir_banregio`. Interés con días reales, capital con
    tasa/12 y seguros dentro del pago base. Los seguros del archivo son un
    componente fijo más una tasa sobre saldo: se representan como seguro de
    daños fijo y seguro de vida sobre saldo; su suma es la columna del archivo.
    """
    producto = ProductoHipotecario(
        id="banregio",
        institucion="Banregio",
        nombre="Escenario del cotizador",
        tasa_anual=p["tasa_anual"],
        plazos_meses=(p["plazo_meses"],),
        aforo_max=D("1"),
        convencion_interes=ConvencionDias.DIAS_REALES_360,
        convencion_pago=ConvencionDias.TASA_ENTRE_12,
        convencion_amortizacion=ConvencionDias.TASA_ENTRE_12,
        seguros_en_pago_fijo=True,
        seguro_vida_mensual=p["seguro_tasa_saldo"],
        seguro_danos_monto_mensual=p["seguro_fijo"],
        comision_mensual=p["comision_mensual"],
    )
    tabla = construir_tabla(
        LineaCredito(producto, p["monto"], p["plazo_meses"]),
        D("1000000"),
        fecha_primer_pago=date.fromisoformat(p["fecha_primer_pago"]),
    )
    return {
        r.mes: (r.fecha_pago.isoformat(), r.saldo_inicial, r.interes, r.capital,
                r.seguro_vida + r.seguro_danos, r.pago_total)
        for r in tabla.renglones
    }


def test_banregio_motor_coincide_con_referencia_en_todos_los_renglones():
    """
    La referencia usa el pago base del fixture, cortado a 4 decimales
    (16953.2283); el motor lo deriva completo (16953.22831910…). Por eso
    difieren hasta ~$0.004, y el motor queda MÁS cerca del archivo (~$0.00002).
    """
    p = BANREGIO["parametros"]
    motor = _banregio_desde_motor(p)
    referencia = _construir_banregio(p)
    assert len(motor) == p["plazo_meses"]
    for mes in range(1, p["plazo_meses"] + 1):
        assert motor[mes][0] == referencia[mes][0]
        for calc, ref, nombre in zip(motor[mes][1:], referencia[mes][1:],
                                     ["saldo", "interés", "amortización", "seguros", "pago"]):
            assert abs(calc - ref) < TOL, f"mes {mes}, {nombre}: {calc} != {ref}"


def test_banregio_pago_no_es_fijo():
    """
    El producto se llama 'pagos fijos' pero el pago varía con los días del mes.

    Se comparan diciembre 2023 (31 días) contra febrero 2024 (29 días): el saldo
    apenas cambió entre ambos, así que la diferencia es atribuible al calendario.
    """
    filas = _banregio_desde_motor(BANREGIO["parametros"])
    dic = filas[1][5]
    feb = filas[3][5]
    assert abs(dic - BANREGIO["pago_dic_2023"]) < D("0.01")
    assert abs(feb - BANREGIO["pago_feb_2024"]) < D("0.01")
    assert dic - feb > BANREGIO["variacion_primer_anio"]


def _banregio_creciente_producto_y_tabla(p, **campos):
    """Pagos crecientes: seguros fuera del pago base, dos fases de crecimiento."""
    producto = ProductoHipotecario(
        id="banregio-creciente",
        institucion="Banregio",
        nombre="Escenario del cotizador",
        tasa_anual=p["tasa_anual"],
        plazos_meses=(p["plazo_meses"],),
        aforo_max=D("1"),
        convencion_interes=ConvencionDias.DIAS_REALES_360,
        convencion_pago=ConvencionDias.TASA_ENTRE_12,
        convencion_amortizacion=ConvencionDias.TASA_ENTRE_12,
        crecimiento_pago_mensual=(
            (1, D(1) / p["fase_1_divisor"] - 1),
            (p["fase_2_desde_mes"], p["fase_2_factor"] - 1),
        ),
        seguro_vida_mensual=p["seguro_tasa_saldo"],
        seguro_danos_anual=p["seguro_danos_tasa_anual"],
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        factor_construccion=p["seguro_danos_factor_construccion"],
        comision_mensual=p["comision_mensual"],
        **campos,
    )
    tabla = construir_tabla(
        LineaCredito(producto, p["monto"], p["plazo_meses"]),
        p["valor_inmueble"],
        fecha_primer_pago=date.fromisoformat(p["fecha_primer_pago"]),
    )
    return producto, tabla


@pytest.mark.parametrize("mes", sorted(BANREGIO_CRECIENTE["renglones"]))
def test_banregio_creciente_renglones(mes):
    _, tabla = _banregio_creciente_producto_y_tabla(BANREGIO_CRECIENTE["parametros"])
    r = tabla.renglones[mes - 1]
    fecha, saldo, interes, capital, seguros, total, saldo_final = BANREGIO_CRECIENTE["renglones"][mes]
    assert r.fecha_pago.isoformat() == fecha
    for calc, esp, nombre in [
        (r.saldo_inicial, saldo, "saldo"), (r.interes, interes, "interés"),
        (r.capital, capital, "capital"), (r.seguro_vida + r.seguro_danos, seguros, "seguros"),
        (r.pago_total, total, "pago"), (r.saldo_final, saldo_final, "saldo final"),
    ]:
        assert abs(calc - esp) < TOL, f"mes {mes}, {nombre}: {calc} != {esp}"


def test_banregio_creciente_cat_desde_motor():
    p = BANREGIO_CRECIENTE["parametros"]
    producto, tabla = _banregio_creciente_producto_y_tabla(
        p,
        comision_apertura=p["comision_apertura_pct"],
        avaluo=p["avaluo"],
        cat_netos_de_iva=frozenset(
            {ConceptoIVA.AVALUO, ConceptoIVA.COMISION_MENSUAL, ConceptoIVA.SEGURO_DANOS}
        ),
    )
    assert len(tabla.renglones) == 240
    assert abs(calcular_cat(tabla, producto) - BANREGIO_CRECIENTE["cat_esperado"]) < D("0.0000001")


def _banorte_producto(p, **campos):
    return ProductoHipotecario(
        id="banorte-fovissste",
        institucion="Banorte",
        nombre="Escenario del cotizador",
        tasa_anual=p["tasa_anual"],
        plazos_meses=(p["plazo_meses"],),
        aforo_max=D("1"),
        convencion_interes=ConvencionDias.DIAS_30_4_360,
        primer_periodo_dias_reales=True,
        seguro_vida_mensual=p["seguro_vida_mensual"],
        **campos,
    )


def _banorte_tabla(producto, p, con_disposicion=True):
    return construir_tabla(
        LineaCredito(producto, p["monto"], p["plazo_meses"]),
        D("1428571.4285714286"),
        fecha_primer_pago=date.fromisoformat(p["fecha_primer_pago"]),
        fecha_disposicion=date.fromisoformat(p["fecha_cotizacion"]) if con_disposicion else None,
    )


@pytest.mark.parametrize("mes", sorted(BANORTE_FOVISSSTE["renglones"]))
def test_banorte_fovissste_renglones(mes):
    p = BANORTE_FOVISSSTE["parametros"]
    tabla = _banorte_tabla(_banorte_producto(p), p)
    assert abs(tabla.pago_capital_interes - p["pago_capital_interes"]) < D("0.000001")
    r = tabla.renglones[mes - 1]
    fecha, saldo, capital, interes, vida, total, final = BANORTE_FOVISSSTE["renglones"][mes]
    assert r.fecha_pago.isoformat() == fecha
    for calc, esp, nombre in [
        (r.saldo_inicial, saldo, "saldo"), (r.capital, capital, "capital"),
        (r.interes, interes, "interés"), (r.seguro_vida, vida, "vida"),
        (r.pago_total, total, "pago"), (r.saldo_final, final, "saldo final"),
    ]:
        assert abs(calc - esp) < TOL, f"mes {mes}, {nombre}: {calc} != {esp}"


def test_banorte_fovissste_cat_sobre_tabla_regular():
    """El CAT del archivo usa el mes 1 a 30.4 días y vida sin prorrateo."""
    p = BANORTE_FOVISSSTE["parametros"]
    producto = _banorte_producto(
        p, avaluo=p["avaluo"], cat_netos_de_iva=frozenset({ConceptoIVA.AVALUO})
    )
    regular = _banorte_tabla(producto, p, con_disposicion=False)
    assert abs(regular.renglones[0].interes - D("8022.2222222222226")) < TOL
    assert regular.renglones[0].seguro_vida == D("600")
    assert abs(calcular_cat(regular, producto) - BANORTE_FOVISSSTE["cat_esperado"]) < D("0.0000001")

