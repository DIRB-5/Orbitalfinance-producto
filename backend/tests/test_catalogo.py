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


def _atm_referencia(valor, credito, tasa, factores):
    """TablaATM: S = monto × factor del año / 1000; cierra con C + O."""
    i = tasa / 12
    c, s, filas, flujos = credito, None, [], []
    for mes in range(1, 241):
        anio = (mes - 1) // 12
        o = c * i
        cand = credito * factores[anio] / 1000
        s = c + o if c + o < cand else cand
        k = s - o
        vida = c * D("0.000474")
        danos = max(D("0.8") * valor * D("0.0003"), D("0.0003") * c)
        filas.append((c, o, k))
        flujos.append(s + vida + danos)
        c -= k
        if c == 0:
            break
    return filas, flujos


def test_banamex_a_tu_medida_reproduce_las_formulas_del_cotizador():
    from motor_hipotecario.amortizacion import factores_crecientes
    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Escenario

    from .test_cotizadores_reales import _cat

    valor, credito = D("3000000"), D("2400000")
    escenario = Escenario(valor_vivienda=valor, enganche=valor - credito, plazo_meses=240)
    resultado = evaluar_producto(escenario, POR_ID["banamex-a-tu-medida-mercado-abierto-2026-08"])
    assert resultado.elegible
    factores = factores_crecientes(D("8.88"), D("0.02"), 20)
    filas, flujos = _atm_referencia(valor, credito, D("0.105"), factores)
    assert resultado.tabla.plazo_efectivo_meses == len(filas) == 233  # el análisis: mes 233
    for r, (c, o, k) in zip(resultado.tabla.renglones, filas):
        for calc, esp in ((r.saldo_inicial, c), (r.interes, o), (r.capital, k)):
            assert abs(calc - esp) < D("0.000001"), f"mes {r.mes}: {calc} != {esp}"
    neto = credito - D("5500") / D("1.16") - credito * D("0.01")
    assert abs(resultado.cat_estimado - _cat(flujos, neto)) < D("0.0000001")


@pytest.mark.parametrize("enganche, tasa", [("750000", "0.102"), ("500000", "0.105"), ("400000", "0.11")])
def test_bx_tradicional_tasa_por_aforo(enganche, tasa):
    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Escenario

    escenario = Escenario(valor_vivienda=D("2500000"), enganche=D(enganche), plazo_meses=240)
    resultado = evaluar_producto(escenario, POR_ID["bx-tradicional-2023-03"])
    assert resultado.elegible
    assert resultado.producto.tasa_anual == D(tasa)


def test_bx_tradicional_reproduce_las_formulas_del_cotizador():
    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Escenario

    from .test_cotizadores_reales import _cat

    valor, credito = D("2500000"), D("1750000")
    escenario = Escenario(valor_vivienda=valor, enganche=valor - credito, plazo_meses=240)
    resultado = evaluar_producto(escenario, POR_ID["bx-tradicional-2023-03"])
    assert resultado.comision_apertura == D("17500")
    filas, apertura, flujos = _bx_referencia(valor, credito, D("0.102"), 240)
    for mes in (1, 2, 12, 120, 239, 240):
        r = resultado.tabla.renglones[mes - 1]
        saldo, interes, capital, vida, danos, total = filas[mes - 1]
        for calc, esp in ((r.saldo_inicial, saldo), (r.interes, interes), (r.capital, capital),
                          (r.seguro_vida, vida), (r.seguro_danos, danos), (r.pago_total, total)):
            assert abs(calc - esp) < D("0.000001"), f"mes {mes}: {calc} != {esp}"
    assert abs(resultado.cat_estimado - _cat(flujos, credito - apertura - D("4600"))) < D("0.0000001")


@pytest.mark.parametrize("mes", [1, 2, 12, 60, 120, 240])
def test_banorte_hipoteca_fuerte_reproduce_su_cotizador(mes):
    """Escenario capturado del Simulador Universal (perfil Premium 8.80 %,
    cotizado el 2026-06-15): el producto del catálogo, con esa tasa, debe
    reproducir tabla y CAT pasando por el comparador."""
    from dataclasses import replace
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Escenario

    from .fixtures.cotizadores_reales import BANORTE_HIPOTECA_FUERTE as B

    p = B["parametros"]
    producto = replace(POR_ID["banorte-hipoteca-fuerte-2026-06"], tasa_anual=p["tasa_anual"])
    escenario = Escenario(
        valor_vivienda=p["valor_inmueble"], enganche=p["valor_inmueble"] - p["monto"],
        plazo_meses=p["plazo_meses"],
    )
    resultado = evaluar_producto(escenario, producto, momento=date.fromisoformat(p["fecha_cotizacion"]))
    assert resultado.elegible
    assert resultado.avaluo == p["avaluo"]
    assert resultado.comision_apertura == p["monto"] * p["comision_apertura_pct"]
    r = resultado.tabla.renglones[mes - 1]
    fecha, saldo, capital, interes, vida, danos, comision, pago, final = B["renglones"][mes]
    assert r.fecha_pago.isoformat() == fecha
    for calc, esp, nombre in ((r.saldo_inicial, saldo, "saldo"), (r.capital, capital, "capital"),
                              (r.interes, interes, "interés"), (r.seguro_vida, vida, "vida"),
                              (r.seguro_danos, danos, "daños"), (r.comision_mensual, comision, "comisión"),
                              (r.pago_total, pago, "pago"), (r.saldo_final, final, "saldo final")):
        assert abs(calc - esp) < D("0.000001"), f"mes {mes} {nombre}: {calc} != {esp}"
    assert abs(resultado.cat_estimado - B["cat_esperado"]) < D("0.0000001")


@pytest.mark.parametrize("mes", [1, 2, 12, 60, 120, 180])
def test_afirme_reproduce_su_cotizador(mes):
    """Escenario capturado (nómina Afirme: 10.40 %, sin apertura), abierto el
    2026-07-06: el producto del catálogo con esas condiciones debe reproducir
    tabla y CAT pasando por el comparador."""
    from dataclasses import replace
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Escenario

    from .fixtures.cotizadores_reales import AFIRME as A

    p = A["parametros"]
    producto = replace(
        POR_ID["afirme-adquisicion-2026-07"],
        tasa_anual=p["tasa_anual"], tabla_tasas=(), comision_apertura=D("0"),
    )
    escenario = Escenario(
        valor_vivienda=p["valor_inmueble"], enganche=p["valor_inmueble"] - p["monto"],
        plazo_meses=p["plazo_meses"],
    )
    resultado = evaluar_producto(escenario, producto, momento=date.fromisoformat(p["fecha_apertura"]))
    assert resultado.elegible
    assert resultado.avaluo == p["avaluo"]
    assert abs(resultado.tabla.pago_capital_interes - p["cuota"]) < D("0.000001")
    r = resultado.tabla.renglones[mes - 1]
    fecha, saldo, capital, interes, vida, desempleo, pago = A["renglones"][mes]
    assert r.fecha_pago.isoformat() == fecha
    for calc, esp, nombre in ((r.saldo_inicial, saldo, "saldo"), (r.capital, capital, "capital"),
                              (r.interes, interes, "interés"), (r.seguro_vida, vida, "vida"),
                              (r.seguro_desempleo, desempleo, "desempleo"), (r.pago_total, pago, "pago")):
        assert abs(calc - esp) < D("0.000001"), f"mes {mes} {nombre}: {calc} != {esp}"
    assert abs(resultado.cat_estimado - A["cat_esperado"]) < D("0.0000001")


# ---------------------------------------------------------------------------
# Sustitución de hipoteca
# ---------------------------------------------------------------------------

def _escenario_sustitucion(valor, monto, plazo):
    from motor_hipotecario.modelos import CreditoActual, Destino, Escenario

    return Escenario(
        valor_vivienda=valor, enganche=valor - monto, plazo_meses=plazo,
        destino=Destino.SUSTITUCION,
        credito_actual=CreditoActual(
            saldo_insoluto=monto, pago_mensual=D("25000"), plazo_remanente_meses=plazo,
        ),
    )


def test_productos_de_sustitucion_en_el_catalogo():
    from motor_hipotecario.modelos import Destino

    ids = {p.id for p in CATALOGO if p.destino is Destino.SUSTITUCION}
    assert ids == {
        "banregio-mejora-hipoteca-2023-12",
        "banamex-cambia-tu-hipoteca-mercado-abierto-2026-08",
        "bx-mejora-tu-hipoteca-2026-01",
        "banorte-mejora-hipoteca-2026-06",
        "scotiabank-7x5-pasivo-hipotecario-2024-01",
    }


def test_banregio_mejora_reproduce_su_cotizador():
    """El escenario capturado de Banregio ES de Mejora de Hipoteca (código 4)."""
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    from .fixtures.cotizadores_reales import BANREGIO

    p = BANREGIO["parametros"]
    escenario = _escenario_sustitucion(p["valor_inmueble"], p["monto"], p["plazo_meses"])
    r = evaluar_producto(
        escenario, POR_ID["banregio-mejora-hipoteca-2023-12"], date.fromisoformat(p["fecha_primer_pago"])
    )
    assert r.elegible
    assert r.producto.tasa_anual == p["tasa_anual"]
    for mes, (_, saldo, interes, capital, seguros, total) in BANREGIO["renglones"].items():
        x = r.tabla.renglones[mes - 1]
        for calc, esp in ((x.saldo_inicial, saldo), (x.interes, interes), (x.capital, capital),
                          (x.seguro_vida + x.seguro_danos, seguros), (x.pago_total, total)):
            assert abs(calc - esp) < D("0.000001"), f"mes {mes}: {calc} != {esp}"
    assert abs(r.cat_estimado - BANREGIO["cat_esperado"]) < D("0.0000001")
    assert r.ahorro_mensual == D("25000") - r.pago_regular_inicial


def test_banamex_cambia_tu_hipoteca_reproduce_las_formulas():
    """Perfiles con apertura 0 % y avalúo gratis abajo de 15 millones (TablaCTH)."""
    from motor_hipotecario.comparador import evaluar_producto

    from .test_cotizadores_reales import _cat

    valor, credito = D("3000000"), D("1800000")
    r = evaluar_producto(
        _escenario_sustitucion(valor, credito, 240),
        POR_ID["banamex-cambia-tu-hipoteca-mercado-abierto-2026-08"],
    )
    assert r.elegible
    assert r.comision_apertura == 0 and r.avaluo == 0
    filas, flujos, _ = _banamex_referencia(valor, credito, D("0.102"), 240, D("0"))
    for x, (c, o, k, vida, danos) in zip(r.tabla.renglones, filas):
        for calc, esp in ((x.saldo_inicial, c), (x.interes, o), (x.capital, k),
                          (x.seguro_vida, vida), (x.seguro_danos, danos)):
            assert abs(calc - esp) < D("0.000001"), f"mes {x.mes}: {calc} != {esp}"
    assert abs(r.cat_estimado - _cat(flujos, credito)) < D("0.0000001")


def test_bx_mejora_tu_hipoteca_reproduce_las_formulas():
    from motor_hipotecario.comparador import evaluar_producto

    from .test_cotizadores_reales import _cat

    valor, credito = D("2500000"), D("1750000")
    r = evaluar_producto(_escenario_sustitucion(valor, credito, 240), POR_ID["bx-mejora-tu-hipoteca-2026-01"])
    assert r.elegible
    assert r.comision_apertura == 0
    assert r.producto.tasa_anual == D("0.0965")
    filas, _, flujos = _bx_referencia(valor, credito, D("0.0965"), 240)
    for mes in (1, 2, 12, 120, 240):
        x = r.tabla.renglones[mes - 1]
        saldo, interes, capital, vida, danos, total = filas[mes - 1]
        for calc, esp in ((x.saldo_inicial, saldo), (x.capital, capital), (x.pago_total, total)):
            assert abs(calc - esp) < D("0.000001"), f"mes {mes}: {calc} != {esp}"
    assert abs(r.cat_estimado - _cat(flujos, credito - D("4600"))) < D("0.0000001")


@pytest.mark.parametrize("mes", [1, 2, 12, 60, 120, 180])
def test_banorte_mejora_reproduce_su_cotizador(mes):
    """Escenario capturado de Mejora de Hipoteca (8.80 %, cotizado el 2026-04-04)."""
    from dataclasses import replace
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    from .fixtures.cotizadores_reales import BANORTE_MEJORA as B

    p = B["parametros"]
    producto = replace(POR_ID["banorte-mejora-hipoteca-2026-06"], tasa_anual=p["tasa_anual"])
    escenario = _escenario_sustitucion(p["valor_inmueble"], p["monto"], p["plazo_meses"])
    r = evaluar_producto(escenario, producto, momento=date.fromisoformat(p["fecha_cotizacion"]))
    assert r.elegible
    assert r.avaluo == p["avaluo"] and r.comision_apertura == 0
    assert r.comision_investigacion == p["gastos_aprobacion"]
    x = r.tabla.renglones[mes - 1]
    saldo, capital, interes, vida, danos, com, pago, final = B["renglones"][mes]
    for calc, esp, nombre in ((x.saldo_inicial, saldo, "saldo"), (x.capital, capital, "capital"),
                              (x.interes, interes, "interés"), (x.seguro_vida, vida, "vida"),
                              (x.seguro_danos, danos, "daños"), (x.comision_mensual, com, "comisión"),
                              (x.pago_total, pago, "pago"), (x.saldo_final, final, "saldo final")):
        assert abs(calc - esp) < D("0.000001"), f"mes {mes} {nombre}: {calc} != {esp}"
    assert abs(r.cat_estimado - B["cat_esperado"]) < D("0.0000001")


def test_scotiabank_pasivo_hipotecario():
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    valor, credito = D("1500000"), D("1125000")
    escenario = _escenario_sustitucion(valor, credito, 240)
    r = evaluar_producto(escenario, POR_ID["scotiabank-7x5-pasivo-hipotecario-2024-01"],
                         momento=date(2026, 10, 24))
    adq = evaluar_producto(
        replace_escenario_adquisicion(escenario), POR_ID["scotiabank-7x5-adquisicion-2024-01"],
        momento=date(2026, 10, 24),
    )
    assert r.elegible
    assert r.comision_apertura == credito * D("0.015") and r.avaluo == 0
    # Misma tabla que el 7x5 de adquisición
    assert [x.pago_total for x in r.tabla.renglones] == [x.pago_total for x in adq.tabla.renglones]


def replace_escenario_adquisicion(escenario):
    from dataclasses import replace

    from motor_hipotecario.modelos import Destino

    return replace(escenario, destino=Destino.ADQUISICION, credito_actual=None)


# ---------------------------------------------------------------------------
# Terreno
# ---------------------------------------------------------------------------

def _escenario_terreno(valor, monto, plazo):
    from motor_hipotecario.modelos import Destino, Escenario

    return Escenario(valor_vivienda=valor, enganche=valor - monto, plazo_meses=plazo,
                     destino=Destino.TERRENO)


def test_productos_de_terreno_en_el_catalogo():
    from motor_hipotecario.modelos import Destino

    ids = {p.id for p in CATALOGO if p.destino is Destino.TERRENO}
    assert ids == {"afirme-terreno-90-2026-09", "banregio-terreno-2023-12",
                   "banorte-terreno-urbanizado-2026-06"}
    for p in CATALOGO:
        if p.destino is Destino.TERRENO:
            assert p.seguro_danos_anual == 0 and p.seguro_danos_monto_mensual is None


@pytest.mark.parametrize("mes", [1, 2, 12, 60, 120, 180])
def test_afirme_terreno_reproduce_su_cotizador(mes):
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    from .fixtures.cotizadores_reales import AFIRME_TERRENO as A

    p = A["parametros"]
    r = evaluar_producto(
        _escenario_terreno(p["valor_inmueble"], p["monto"], p["plazo_meses"]),
        POR_ID["afirme-terreno-90-2026-09"], momento=date.fromisoformat(p["fecha_apertura"]),
    )
    assert r.elegible
    assert r.avaluo == p["avaluo"]
    assert abs(r.tabla.pago_capital_interes - p["cuota"]) < D("0.000001")
    x = r.tabla.renglones[mes - 1]
    fecha, saldo, capital, interes, vida, desempleo = A["renglones"][mes]
    assert x.fecha_pago.isoformat() == fecha
    for calc, esp, nombre in ((x.saldo_inicial, saldo, "saldo"), (x.capital, capital, "capital"),
                              (x.interes, interes, "interés"), (x.seguro_vida, vida, "vida"),
                              (x.seguro_desempleo, desempleo, "desempleo")):
        assert abs(calc - esp) < D("0.000001"), f"mes {mes} {nombre}: {calc} != {esp}"
    assert abs(r.cat_estimado - A["cat_de_lo_cobrado"]) < D("0.0000001")


@pytest.mark.parametrize("plazo, enganche, tasa", [(120, "800000", "0.1005"), (180, "300000", "0.1135"),
                                                   (240, "800000", "0.11")])
def test_banregio_terreno_tasa_y_sin_danos(plazo, enganche, tasa):
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    r = evaluar_producto(_escenario_terreno(D("1500000"), D("1500000") - D(enganche), plazo),
                         POR_ID["banregio-terreno-2023-12"], date(2026, 12, 1))
    assert r.elegible and r.producto.tasa_anual == D(tasa)
    assert all(x.seguro_danos == 0 for x in r.tabla.renglones)


@pytest.mark.parametrize("plazo, tasa", [(120, "0.1018"), (180, "0.1068")])
def test_banorte_terreno_urbanizado(plazo, tasa):
    from datetime import date

    from motor_hipotecario.cat import flujos_cat
    from motor_hipotecario.comparador import evaluar_producto

    producto = POR_ID["banorte-terreno-urbanizado-2026-06"]
    r = evaluar_producto(_escenario_terreno(D("1500000"), D("1000000"), plazo), producto,
                         momento=date(2026, 6, 15))
    assert r.elegible and r.producto.tasa_anual == D(tasa)
    assert r.comision_apertura == 0 and r.comision_investigacion == D("500")
    assert all(x.seguro_danos == 0 and x.comision_mensual == 250 for x in r.tabla.renglones)
    neto, _ = flujos_cat(r.tabla, r.producto)
    assert neto == D("1000000") - r.avaluo / D("1.16") - D("500") / D("1.16")


# ---------------------------------------------------------------------------
# Liquidez
# ---------------------------------------------------------------------------

def _escenario_liquidez(valor, monto, plazo):
    from motor_hipotecario.modelos import Destino, Escenario

    return Escenario(valor_vivienda=valor, enganche=valor - monto, plazo_meses=plazo,
                     destino=Destino.LIQUIDEZ)


def test_productos_de_liquidez_en_el_catalogo():
    from motor_hipotecario.modelos import Destino

    ids = {p.id for p in CATALOGO if p.destino is Destino.LIQUIDEZ}
    assert ids == {"banorte-liquidez-2026-06", "banamex-liquidez-mercado-abierto-2026-08",
                   "bx-liquidez-2022-10", "banregio-liquidez-2023-12",
                   "scotiabank-liquidez-libre-7x5-2024-01"}


@pytest.mark.parametrize("producto_id, valor, monto, plazo, tasa, iva_en_pago", [
    ("banorte-liquidez-2026-06", "3000000", "1500000", 120, "0.1299", True),
    ("banamex-liquidez-mercado-abierto-2026-08", "3000000", "1500000", 120, "0.13", True),
    ("bx-liquidez-2022-10", "3000000", "1500000", 120, "0.147", False),
    ("banregio-liquidez-2023-12", "3000000", "1500000", 120, "0.1225", True),
    ("scotiabank-liquidez-libre-7x5-2024-01", "3000000", "1500000", 60, "0.14", True),
])
def test_liquidez_elegible_con_su_tasa_e_iva(producto_id, valor, monto, plazo, tasa, iva_en_pago):
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    r = evaluar_producto(_escenario_liquidez(D(valor), D(monto), plazo), POR_ID[producto_id],
                         date(2026, 11, 1), momento=date(2026, 10, 24))
    assert r.elegible, r.motivos_rechazo
    assert r.producto.tasa_anual == D(tasa)
    assert (r.tabla.renglones[1].iva_intereses > 0) is iva_en_pago
    assert r.tabla.renglones[-1].saldo_final == 0


def test_liquidez_respeta_su_aforo():
    from motor_hipotecario.comparador import evaluar_producto

    # 60 % de aforo: Banregio y BX+ (50 %) no; Banamex (65 %) sí
    escenario = _escenario_liquidez(D("3000000"), D("1800000"), 120)
    from datetime import date
    assert not evaluar_producto(escenario, POR_ID["banregio-liquidez-2023-12"], date(2026, 11, 1)).elegible
    assert not evaluar_producto(escenario, POR_ID["bx-liquidez-2022-10"]).elegible
    assert evaluar_producto(escenario, POR_ID["banamex-liquidez-mercado-abierto-2026-08"]).elegible


def test_liquidez_no_cuenta_el_patrimonio_como_desembolso():
    """En liquidez no hay enganche: el día de la firma solo salen los gastos."""
    from motor_hipotecario.comparador import evaluar_producto

    escenario = _escenario_liquidez(D("3000000"), D("1200000"), 120)
    producto = next(p for p in CATALOGO if p.id == "banorte-liquidez-2026-06")
    r = evaluar_producto(escenario, producto)
    assert r.enganche == 0
    assert r.desembolso_inicial == (
        r.comision_apertura + r.avaluo + r.gastos_notariales + r.comision_investigacion
    )

