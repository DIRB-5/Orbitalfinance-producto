"""
El catálogo real debe reproducir el cotizador del que salió cada producto.

Si alguien edita una condición del catálogo sin respaldo en el archivo, estas
pruebas fallan. Actualizar condiciones = producto nuevo con su propia fuente.
"""

from decimal import Decimal as D

import pytest

from motor_hipotecario.amortizacion import construir_tabla
from motor_hipotecario.cat import calcular_cat
from motor_hipotecario.catalogo import CATALOGO
from motor_hipotecario.modelos import LineaCredito

from .fixtures.cotizadores_reales import HSBC, SANTANDER

TOL = D("0.005")
POR_ID = {p.id: p for p in CATALOGO}


@pytest.mark.parametrize(
    "producto_id, fixture, columnas",
    [
        ("hsbc-cicb-2026-10", HSBC, ("capital", "interes", "seguro_vida", "pago_total", "saldo_final")),
        ("santander-2026-10", SANTANDER, ("interes", "capital", "seguro_vida", "pago_total", "saldo_final")),
    ],
)
def test_producto_reproduce_su_cotizador(producto_id, fixture, columnas):
    producto = POR_ID[producto_id]
    p = fixture["parametros"]
    assert producto.institucion == fixture["institucion"]
    assert fixture["archivo"] in producto.fuente
    tabla = construir_tabla(LineaCredito(producto, p["monto"], p["plazo_meses"]), D("1000000"))
    for mes, esperado in fixture["renglones"].items():
        renglon = tabla.renglones[mes - 1]
        for columna, valor in zip(columnas, esperado):
            calc = getattr(renglon, columna)
            assert abs(calc - valor) < TOL, f"{producto_id} mes {mes} {columna}: {calc} != {valor}"


def test_catalogo_sin_productos_ficticios():
    assert CATALOGO
    for producto in CATALOGO:
        assert "Demo" not in producto.institucion
        assert producto.fuente


@pytest.mark.parametrize(
    "producto_id, fixture, tolerancia",
    [
        ("hsbc-cicb-2026-10", HSBC, D("0.0000001")),
        ("santander-2026-10", SANTANDER, SANTANDER["tolerancia_cat_pb"] / D(10000)),
    ],
)
def test_producto_reproduce_el_cat_de_su_cotizador(producto_id, fixture, tolerancia):
    producto = POR_ID[producto_id]
    p = fixture["parametros"]
    tabla = construir_tabla(LineaCredito(producto, p["monto"], p["plazo_meses"]), D("1000000"))
    assert abs(calcular_cat(tabla, producto) - fixture["cat_esperado"]) < tolerancia



def test_banregio_reproduce_su_cotizador_desde_el_comparador():
    """
    El escenario capturado es de Mejora de Hipoteca (código 4); Adquisición
    Tradicional (código 1) usa las mismas tasas y la misma mecánica. Pasando
    por el comparador, el producto debe resolver tasa y avalúo del escenario
    y reproducir la tabla y el CAT del archivo.
    """
    from datetime import date

    from motor_hipotecario.cat import calcular_cat
    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Escenario

    from .fixtures.cotizadores_reales import BANREGIO

    p = BANREGIO["parametros"]
    escenario = Escenario(
        valor_vivienda=p["valor_inmueble"],
        enganche=p["valor_inmueble"] - p["monto"],
        plazo_meses=p["plazo_meses"],
    )
    resultado = evaluar_producto(
        escenario, POR_ID["banregio-adquisicion-2023-12"], date.fromisoformat(p["fecha_primer_pago"])
    )
    assert resultado.elegible
    assert resultado.producto.tasa_anual == p["tasa_anual"]
    assert resultado.avaluo == p["avaluo"]
    assert resultado.comision_apertura == p["monto"] * p["comision_apertura_pct"]
    for mes, (_, saldo, interes, capital, seguros, total) in BANREGIO["renglones"].items():
        r = resultado.tabla.renglones[mes - 1]
        for calc, esp in ((r.saldo_inicial, saldo), (r.interes, interes), (r.capital, capital),
                          (r.seguro_vida + r.seguro_danos, seguros), (r.pago_total, total)):
            assert abs(calc - esp) < D("0.000001"), f"mes {mes}: {calc} != {esp}"
    assert abs(resultado.cat_estimado - BANREGIO["cat_esperado"]) < D("0.0000001")


def test_banregio_crecientes_reproduce_su_cotizador():
    """
    El escenario de TablAmoPagosCrec usa la tasa del tramo de 10 años (10.20 %)
    con plazo de 20: se fija esa tasa y todo lo demás del producto del
    catálogo debe reproducir la tabla y el CAT del archivo.
    """
    from dataclasses import replace
    from datetime import date

    from motor_hipotecario.cat import calcular_cat

    from .fixtures.cotizadores_reales import BANREGIO_CRECIENTE

    p = BANREGIO_CRECIENTE["parametros"]
    producto = replace(
        POR_ID["banregio-adquisicion-crecientes-2023-12"],
        tabla_tasas=(),
        tasa_anual=p["tasa_anual"],
        tarifa_avaluo=(),
        avaluo=p["avaluo"],
    )
    tabla = construir_tabla(
        LineaCredito(producto, p["monto"], p["plazo_meses"]),
        p["valor_inmueble"],
        fecha_primer_pago=date.fromisoformat(p["fecha_primer_pago"]),
    )
    for mes, (_, saldo, interes, capital, seguros, total, final) in BANREGIO_CRECIENTE["renglones"].items():
        r = tabla.renglones[mes - 1]
        for calc, esp in ((r.saldo_inicial, saldo), (r.interes, interes), (r.capital, capital),
                          (r.seguro_vida + r.seguro_danos, seguros), (r.pago_total, total),
                          (r.saldo_final, final)):
            assert abs(calc - esp) < D("0.000001"), f"mes {mes}: {calc} != {esp}"
    assert abs(calcular_cat(tabla, producto) - BANREGIO_CRECIENTE["cat_esperado"]) < D("0.0000001")


@pytest.mark.parametrize("enganche, tasa", [("1000000", "0.105"), ("135000", "0.110")])
def test_banregio_crecientes_usa_la_tasa_de_20_anios(enganche, tasa):
    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Escenario

    escenario = Escenario(
        valor_vivienda=D("1350000"), enganche=D(enganche), plazo_meses=240
    )
    resultado = evaluar_producto(escenario, POR_ID["banregio-adquisicion-crecientes-2023-12"])
    assert resultado.elegible
    assert resultado.producto.tasa_anual == D(tasa)


def test_banregio_crecientes_solo_a_20_anios():
    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Escenario

    escenario = Escenario(valor_vivienda=D("1350000"), enganche=D("300000"), plazo_meses=180)
    resultado = evaluar_producto(escenario, POR_ID["banregio-adquisicion-crecientes-2023-12"])
    assert not resultado.elegible


def _escenario_banorte(salario):
    from motor_hipotecario.modelos import Cofinanciamiento, Escenario, TipoLinea

    from .fixtures.cotizadores_reales import BANORTE_FOVISSSTE

    p = BANORTE_FOVISSSTE["parametros"]
    valor = D("1428571.4285714286")  # Simulador!N11 = monto / 0.7
    return p, Escenario(
        valor_vivienda=valor,
        enganche=valor - p["monto"],
        plazo_meses=p["plazo_meses"],
        cofinanciamiento=Cofinanciamiento(instituto=TipoLinea.FOVISSSTE, salario_mensual=D(salario)),
    )


def test_banorte_fovissste_reproduce_su_cotizador_desde_el_comparador():
    """Escenario del archivo (sin salario: aportaciones en 0), cotizado el
    2026-02-03: el comparador debe derivar el primer pago (3 de marzo), el
    avalúo del tabulador y reproducir tabla y CAT."""
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    from .fixtures.cotizadores_reales import BANORTE_FOVISSSTE

    p, escenario = _escenario_banorte("0")
    resultado = evaluar_producto(
        escenario, POR_ID["banorte-fovissste-para-todos-2026-02"], momento=date(2026, 2, 3)
    )
    assert resultado.elegible
    assert resultado.avaluo == p["avaluo"]
    assert resultado.comision_apertura == 0
    for mes, (fecha, saldo, capital, interes, vida, total, final) in BANORTE_FOVISSSTE["renglones"].items():
        r = resultado.tabla.renglones[mes - 1]
        assert r.fecha_pago.isoformat() == fecha
        for calc, esp in ((r.saldo_inicial, saldo), (r.capital, capital), (r.interes, interes),
                          (r.seguro_vida, vida), (r.pago_total, total), (r.saldo_final, final)):
            assert abs(calc - esp) < D("0.000001"), f"mes {mes}: {calc} != {esp}"
    assert abs(resultado.cat_estimado - BANORTE_FOVISSSTE["cat_esperado"]) < D("0.0000001")


def test_banorte_fovissste_aplica_aportaciones_y_exige_cofinanciamiento():
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Escenario

    producto = POR_ID["banorte-fovissste-para-todos-2026-02"]
    _, escenario = _escenario_banorte("30000")
    resultado = evaluar_producto(escenario, producto, momento=date(2026, 2, 3))
    assert resultado.tabla.renglones[3].aportacion == D("3000")  # 10 % de 30,000
    assert resultado.tabla.plazo_efectivo_meses < 240

    sin = Escenario(valor_vivienda=escenario.valor_vivienda, enganche=escenario.enganche,
                    plazo_meses=240)
    assert not evaluar_producto(sin, producto, momento=date(2026, 2, 3)).elegible


# ---------------------------------------------------------------------------
# BX+ Cofinavit: el archivo no trae escenario capturado. Se contrasta contra
# una implementación de referencia escrita con las fórmulas de VResPlus.
# ---------------------------------------------------------------------------

def _bx_referencia(valor, credito, tasa, plazo):
    """VResPlus: F14 = −PMT(tasa/12, n, F11); P = O·tasa/12; Q = R − P;
    U = O·0.00065; V = 70 % valor × 0.301‰ × 1.16; W = 299 × 1.16."""
    i = tasa / 12
    pago = credito * i / (1 - (1 + i) ** -plazo)
    danos = valor * D("0.7") * D("0.301") / 1000 * D("1.16")
    saldo, filas = credito, []
    for _ in range(plazo):
        interes = saldo * i
        capital = min(pago - interes, saldo)
        vida = saldo * D("0.00065")
        filas.append((saldo, interes, capital, vida, danos, capital + interes + vida + danos + D("346.84")))
        saldo -= capital
    # CAT (AJ): −crédito + apertura + avalúo s/IVA; capital + interés + vida
    # + daños/1.16 + 299
    apertura = min(credito * D("0.01"), D("150000"))
    flujos = [cap + intr + v + d / D("1.16") + D("299") for (_, intr, cap, v, d, _) in filas]
    return filas, apertura, flujos


def test_bx_cofinavit_reproduce_las_formulas_del_cotizador():
    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Cofinanciamiento, Escenario, TipoLinea

    from .test_cotizadores_reales import _cat

    valor = D("2500000")
    escenario = Escenario(
        valor_vivienda=valor, enganche=D("550000"), plazo_meses=240,
        cofinanciamiento=Cofinanciamiento(
            instituto=TipoLinea.INFONAVIT, salario_mensual=D("0"),
            monto_credito_instituto=D("300000"), saldo_subcuenta=D("150000"),
        ),
    )
    resultado = evaluar_producto(escenario, POR_ID["bx-cofinavit-2026-01"])
    assert resultado.elegible
    assert resultado.monto_credito == D("1500000")       # aforo bancario 60 %
    assert resultado.producto.tasa_anual == D("0.0965")   # tramo hasta 70 %
    assert resultado.comision_apertura == D("15000")
    assert resultado.avaluo == D("4600") * D("1.16")       # tramo 2-3 millones

    filas, apertura, flujos = _bx_referencia(valor, D("1500000"), D("0.0965"), 240)
    for mes in (1, 2, 12, 120, 239, 240):
        r = resultado.tabla.renglones[mes - 1]
        saldo, interes, capital, vida, danos, total = filas[mes - 1]
        for calc, esp in ((r.saldo_inicial, saldo), (r.interes, interes), (r.capital, capital),
                          (r.seguro_vida, vida), (r.seguro_danos, danos), (r.pago_total, total)):
            assert abs(calc - esp) < D("0.000001"), f"mes {mes}: {calc} != {esp}"
    cat_ref = _cat(flujos, D("1500000") - apertura - D("4600"))
    assert abs(resultado.cat_estimado - cat_ref) < D("0.0000001")


# Crédito bancario = 2.5M − enganche − 300k (Infonavit) − 150k (SSV)
@pytest.mark.parametrize("enganche, tasa", [
    ("300000", "0.0965"),  # 1.75M = 70 %
    ("250000", "0.0985"),  # 1.80M = 72 %
    ("0", "0.1030"),       # 2.05M = 82 %
])
def test_bx_cofinavit_tasa_por_aforo_bancario(enganche, tasa):
    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Cofinanciamiento, Escenario, TipoLinea

    escenario = Escenario(
        valor_vivienda=D("2500000"), enganche=D(enganche), plazo_meses=240,
        cofinanciamiento=Cofinanciamiento(
            instituto=TipoLinea.INFONAVIT, salario_mensual=D("0"),
            monto_credito_instituto=D("300000"), saldo_subcuenta=D("150000"),
        ),
    )
    assert evaluar_producto(escenario, POR_ID["bx-cofinavit-2026-01"]).producto.tasa_anual == D(tasa)


def _bx_apoyo_referencia(valor, credito, tasa, plazo, salario):
    """
    BX+ INFONAVIT (Simulador col. N, VResPlus O/Q/R/Z): pago fijo; aportación
    en meses pares desde el 4 = MIN(10 % salario, 7,884.24), × 1.03 cada año
    desde el mes 14; se paga solo si el saldo tras el capital es positivo y
    se omite si no cabe; reduce el saldo del mismo mes.
    """
    i = tasa / 12
    pago = credito * i / (1 - (1 + i) ** -plazo)
    base = min(D("0.10") * salario, D("7884.24"))
    saldo, filas = credito, []
    for mes in range(1, plazo + 1):
        interes = saldo * i
        capital = saldo if (saldo - (pago - interes) <= 0 or mes == plazo) else pago - interes
        aport = D("0")
        if mes >= 4 and mes % 2 == 0:
            aport = base * D("1.03") ** ((mes - 1) // 12)
            if saldo - capital <= 0 or aport > saldo - capital:
                aport = D("0")
        filas.append((saldo, interes, capital, aport))
        saldo = saldo - capital - aport
        if saldo == 0:
            break
    return filas


def test_bx_apoyo_infonavit_reproduce_las_formulas_del_cotizador():
    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Cofinanciamiento, Escenario, TipoLinea

    valor, salario = D("2500000"), D("60000")
    escenario = Escenario(
        valor_vivienda=valor, enganche=D("600000"), plazo_meses=240,
        cofinanciamiento=Cofinanciamiento(
            instituto=TipoLinea.INFONAVIT, salario_mensual=salario, saldo_subcuenta=D("150000"),
        ),
    )
    resultado = evaluar_producto(escenario, POR_ID["bx-apoyo-infonavit-2026-01"])
    assert resultado.elegible
    assert resultado.monto_credito == D("1750000")        # la subcuenta reduce el crédito
    assert resultado.producto.tasa_anual == D("0.0965")   # 70 %
    assert resultado.tabla_instituto is None

    filas = _bx_apoyo_referencia(valor, D("1750000"), D("0.0965"), 240, salario)
    assert resultado.tabla.plazo_efectivo_meses == len(filas)
    for r, (saldo, interes, capital, aport) in zip(resultado.tabla.renglones, filas):
        for calc, esp in ((r.saldo_inicial, saldo), (r.interes, interes),
                          (r.capital, capital), (r.aportacion, aport)):
            assert abs(calc - esp) < D("0.000001"), f"mes {r.mes}: {calc} != {esp}"
    assert resultado.tabla.renglones[3].aportacion == D("6000")
    assert resultado.tabla.renglones[13].aportacion == D("6000") * D("1.03")


def test_bx_apoyo_infonavit_no_ofrece_aforo_de_85():
    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Cofinanciamiento, Escenario, TipoLinea

    escenario = Escenario(
        valor_vivienda=D("2500000"), enganche=D("200000"), plazo_meses=240,
        cofinanciamiento=Cofinanciamiento(
            instituto=TipoLinea.INFONAVIT, salario_mensual=D("60000"), saldo_subcuenta=D("150000"),
        ),
    )  # crédito 2.15M = 86 %
    assert not evaluar_producto(escenario, POR_ID["bx-apoyo-infonavit-2026-01"]).elegible


# ---------------------------------------------------------------------------
# Banamex Hipoteca Perfiles: sin escenario capturado; referencia con las
# fórmulas de TablaPerfiles (pseudocódigo del análisis del archivo).
# ---------------------------------------------------------------------------

def _banamex_referencia(valor, credito, tasa, plazo, avaluo):
    from decimal import ROUND_CEILING

    i = tasa / 12
    pmt = D(1000) * i / (1 - (1 + i) ** -plazo)
    factor = (pmt * 100).to_integral_value(rounding=ROUND_CEILING) / 100
    s = credito * factor / 1000
    c, filas, flujos = credito, [], []
    for mes in range(1, plazo + 1):
        o = c * i
        pago = c + o if (c + o < s or mes == plazo) else s
        k = pago - o
        vida = c * D("0.000474")
        danos = max(D("0.8") * valor * D("0.0003"), D("0.0003") * c)
        filas.append((c, o, k, vida, danos))
        flujos.append(pago + vida + danos)
        c -= k
        if c == 0:
            break
    neto = credito - avaluo / D("1.16") - credito * D("0.01")
    return filas, flujos, neto


def test_banamex_reproduce_las_formulas_del_cotizador():
    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Escenario

    from .test_cotizadores_reales import _cat

    valor = D("3000000")
    escenario = Escenario(valor_vivienda=valor, enganche=D("600000"), plazo_meses=240)
    resultado = evaluar_producto(escenario, POR_ID["banamex-perfiles-mercado-abierto-2026-08"])
    assert resultado.elegible
    assert resultado.avaluo == D("5500")            # 1 a 3 millones, IVA incluido
    assert resultado.comision_apertura == D("24000")

    filas, flujos, neto = _banamex_referencia(valor, D("2400000"), D("0.105"), 240, D("5500"))
    assert resultado.tabla.plazo_efectivo_meses == len(filas)
    for r, (c, o, k, vida, danos) in zip(resultado.tabla.renglones, filas):
        for calc, esp in ((r.saldo_inicial, c), (r.interes, o), (r.capital, k),
                          (r.seguro_vida, vida), (r.seguro_danos, danos)):
            assert abs(calc - esp) < D("0.000001"), f"mes {r.mes}: {calc} != {esp}"
    assert abs(resultado.cat_estimado - _cat(flujos, neto)) < D("0.0000001")


def test_scotiabank_7x5_reproduce_las_formulas_del_cotizador():
    """Sin escenario capturado: referencia con las fórmulas de la Tabla de
    amortizacion (pago al millar 10.27 los primeros 60 meses, días reales,
    reamortización mensual desde el 61 a TIIE + 4.5) más seguros y CAT."""
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Escenario

    from .test_cotizadores_reales import _cat
    from .test_motor import _referencia_7x5

    valor, credito, tiie = D("1500000"), D("1125000"), D("0.07")
    escenario = Escenario(valor_vivienda=valor, enganche=valor - credito, plazo_meses=240, tiie=tiie)
    resultado = evaluar_producto(
        escenario, POR_ID["scotiabank-7x5-adquisicion-2024-01"], momento=date(2026, 10, 24)
    )
    assert resultado.elegible
    assert resultado.tabla.renglones[0].fecha_pago == date(2026, 11, 17)
    assert resultado.comision_apertura == credito * D("0.0125")
    assert resultado.avaluo == D("4500")              # 1 a 1.5 millones

    filas = _referencia_7x5(credito, D("0.1075"), tiie, date(2026, 11, 17))
    flujos = []
    for r, (saldo, interes, capital) in zip(resultado.tabla.renglones, filas):
        vida, danos = saldo * D("0.0006"), valor * D("0.00031")
        for calc, esp in ((r.saldo_inicial, saldo), (r.interes, interes), (r.capital, capital),
                          (r.seguro_vida, vida), (r.seguro_danos, danos)):
            assert abs(calc - esp) < D("0.000001"), f"mes {r.mes}: {calc} != {esp}"
        flujos.append(capital + interes + vida + danos)
    neto = credito - credito * D("0.0125") - D("4500")
    assert abs(resultado.cat_estimado - _cat(flujos, neto)) < D("0.0000001")
