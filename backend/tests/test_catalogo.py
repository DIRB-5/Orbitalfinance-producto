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
        "scotiabank-pasivos-pagos-oportunos-2024-01",
        "scotiabank-pasivos-valora-2024-01",
        "santander-sustitucion-2025-12",
        "santander-mejora-condiciones-2025-12",
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
                   "scotiabank-liquidez-libre-7x5-2024-01",
                   "scotiabank-liquidez-libre-pagos-oportunos-7-2024-01",
                   "scotiabank-liquidez-libre-pagos-oportunos-10-2024-01",
                   "scotiabank-liquidez-libre-pagos-oportunos-15-2024-01",
                   "scotiabank-liquidez-libre-valora-2024-01"}


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


# ---------------------------------------------------------------------------
# Scotiabank Valora y Pagos Oportunos (Pago de pasivos y Liquidez Libre)
# ---------------------------------------------------------------------------
# Ningún archivo trae escenario capturado. La referencia está escrita con las
# fórmulas de las hojas ('Valora 10'!G:I, 'POport. 7'!E, Tabla Valora!D:F,
# AH; Tabla Pagos Oportunos!AI:AK) y los CAT esperados se calcularon con una
# réplica celda por celda de cada hoja (IRR de AE22:AE262 / AS13:AS254).

def _scotia_referencia(monto, valor, factor, tasa_del_mes, crecimiento, iva, primer_pago):
    """Renglones (saldo, interés, capital, vida, daños, IVA, pago) de la hoja."""
    import calendar
    from datetime import date

    filas, saldo, pago, fecha = [], monto, monto * factor / 1000, primer_pago
    for k in range(1, 241):
        if k > 1:
            fecha = date(fecha.year + fecha.month // 12, fecha.month % 12 + 1, 1)
            if (k - 1) % 12 == 0:
                pago *= 1 + crecimiento                   # J = D13 en el aniversario
        dias = calendar.monthrange(fecha.year, fecha.month)[1]
        interes = saldo * tasa_del_mes(k) / 360 * dias    # F * E / 360 * AI
        capital = min(pago - interes, saldo)              # MIN(I*(1+J), F+G)
        vida, danos = saldo * D("0.0006"), valor * D("0.00031")
        iva_mes = interes * D("0.16") if iva else D(0)
        filas.append((saldo, interes, capital, vida, danos, iva_mes,
                      capital + interes + vida + danos + iva_mes))
        saldo -= capital
        if saldo == 0:
            return filas
    raise AssertionError("la referencia no liquida en 240 meses")


def _tasa_pasivos_po(k):
    return (D("0.1025"), D("0.1005"), D("0.0985"), D("0.0965"), D("0.095"))[min((k - 1) // 12, 4)]


def _tasa_liquidez_valora(k):
    # 15.5 % hasta el mes 36; −0.25 pp cada aniversario con piso de 14.5 %
    return max(D("0.155") - D("0.0025") * max(0, (k - 25) // 12), D("0.145"))


def _tasa_liquidez_po(tasas):
    return lambda k: D(tasas[min((k - 1) // 12, 4)])


_PO_LIQ = {
    84: ("0.15", "0.148", "0.146", "0.144", "0.1425"),
    120: ("0.151", "0.149", "0.147", "0.145", "0.1435"),
    180: ("0.155", "0.153", "0.151", "0.149", "0.1475"),
}

# (producto, destino, plazo, factor, tasa del mes, crecimiento, IVA, meses, CAT)
_CASOS_SCOTIA = [
    ("scotiabank-pasivos-valora-2024-01", "sustitucion", 120, "12.38",
     lambda k: D("0.1025"), "0.026", False, 118, "0.128710"),
    ("scotiabank-pasivos-valora-2024-01", "sustitucion", 180, "9.93",
     lambda k: D("0.1025"), "0.026", False, 169, "0.127456"),
    ("scotiabank-pasivos-valora-2024-01", "sustitucion", 240, "8.86",
     lambda k: D("0.1025"), "0.026", False, 211, "0.126653"),
    ("scotiabank-pasivos-pagos-oportunos-2024-01", "sustitucion", 84, "16.82",
     _tasa_pasivos_po, "0", False, 83, "0.12666936"),
    ("scotiabank-pasivos-pagos-oportunos-2024-01", "sustitucion", 120, "13.45",
     _tasa_pasivos_po, "0", False, 117, "0.124858"),
    ("scotiabank-pasivos-pagos-oportunos-2024-01", "sustitucion", 180, "11.00",
     _tasa_pasivos_po, "0", False, 170, "0.122954"),
    ("scotiabank-pasivos-pagos-oportunos-2024-01", "sustitucion", 240, "9.92",
     _tasa_pasivos_po, "0", False, 216, "0.12179470"),
    ("scotiabank-liquidez-libre-valora-2024-01", "liquidez", 120, "15.80",
     _tasa_liquidez_valora, "0.015", True, 118, "0.19346029"),
    ("scotiabank-liquidez-libre-valora-2024-01", "liquidez", 180, "13.58",
     _tasa_liquidez_valora, "0.015", True, 170, "0.18925093"),
    ("scotiabank-liquidez-libre-pagos-oportunos-7-2024-01", "liquidez", 84, "19.43",
     _tasa_liquidez_po(_PO_LIQ[84]), "0", True, 83, "0.19061974"),
    ("scotiabank-liquidez-libre-pagos-oportunos-10-2024-01", "liquidez", 120, "16.34",
     _tasa_liquidez_po(_PO_LIQ[120]), "0", True, 116, "0.18767018"),
    ("scotiabank-liquidez-libre-pagos-oportunos-15-2024-01", "liquidez", 180, "14.51",
     _tasa_liquidez_po(_PO_LIQ[180]), "0", True, 166, "0.18905666"),
]


@pytest.mark.parametrize("pid, destino, plazo, factor, tasa, crec, iva, meses, cat", _CASOS_SCOTIA)
def test_scotiabank_valora_y_pagos_oportunos_reproducen_sus_formulas(
    pid, destino, plazo, factor, tasa, crec, iva, meses, cat
):
    """Cotización del 2024-03-22 (la guardada en ambos archivos): primer pago el 17 de abril."""
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    valor, monto = D("3000000"), D("1500000")
    if destino == "sustitucion":
        escenario = _escenario_sustitucion(valor, monto, plazo)
    else:
        escenario = _escenario_liquidez(valor, monto, plazo)
    r = evaluar_producto(escenario, POR_ID[pid], momento=date(2024, 3, 22))
    assert r.elegible, r.motivos_rechazo
    assert r.tabla.renglones[0].fecha_pago == date(2024, 4, 17)

    referencia = _scotia_referencia(monto, valor, D(factor), tasa, D(crec), iva, date(2024, 4, 17))
    assert len(r.tabla.renglones) == len(referencia) == meses   # se liquida antes del plazo
    for x, esp in zip(r.tabla.renglones, referencia):
        calc = (x.saldo_inicial, x.interes, x.capital, x.seguro_vida, x.seguro_danos,
                x.iva_intereses, x.pago_total)
        for c, e in zip(calc, esp):
            assert abs(c - e) < D("0.000001"), f"mes {x.mes}: {c} != {e}"
    assert abs(r.cat_estimado - D(cat)) < D("0.000001")


def test_scotiabank_liquidez_libre_cobra_apertura_y_avaluo():
    """2 % + IVA de apertura (sin IVA en el CAT) y avalúo del tabulador LiqLibre."""
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    r = evaluar_producto(_escenario_liquidez(D("3000000"), D("1500000"), 180),
                         POR_ID["scotiabank-liquidez-libre-valora-2024-01"], momento=date(2024, 3, 22))
    assert r.comision_apertura == D("1500000") * D("0.0232")
    assert r.avaluo == D("4663")
    # Aforo máximo 70 %: a 75 % no es elegible
    r = evaluar_producto(_escenario_liquidez(D("2000000"), D("1500000"), 180),
                         POR_ID["scotiabank-liquidez-libre-valora-2024-01"], momento=date(2024, 3, 22))
    assert not r.elegible


def test_scotiabank_pago_de_pasivos_sin_apertura_ni_avaluo():
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    r = evaluar_producto(_escenario_sustitucion(D("1600000"), D("1500000"), 240),
                         POR_ID["scotiabank-pasivos-pagos-oportunos-2024-01"], momento=date(2024, 3, 22))
    assert r.elegible  # aforo 93.75 % < 95 %
    assert r.comision_apertura == 0 and r.avaluo == 0



# ---------------------------------------------------------------------------
# Gastos notariales financiados
# ---------------------------------------------------------------------------
# Ningún cotizador trae un escenario con el financiamiento activo: se valida
# contra sus fórmulas (Banamex Calculos!AX76/AX60 y CJ67/CH85, BX+
# VResPlus!F11, Scotiabank Simulador!F22/F25 e I29/O25).

def _con_gastos(escenario, gastos):
    from dataclasses import replace

    return replace(escenario, gastos_notariales=D(gastos), financiar_gastos_notariales=True)


@pytest.mark.parametrize("pid, destino, valor, monto, gastos, financiado, apertura", [
    # Banamex CTH: MIN(gastos, 5 % del saldo) y la línea topada al 90 %
    ("banamex-cambia-tu-hipoteca-mercado-abierto-2026-08", "sustitucion",
     "3000000", "1500000", "120000", "75000", "0"),
    ("banamex-cambia-tu-hipoteca-mercado-abierto-2026-08", "sustitucion",
     "3000000", "2650000", "120000", "50000", "0"),          # 2,700,000 − 2,650,000
    # Banamex Perfiles: MIN(gastos, 10 % del valor); apertura 1 % sobre CH85
    ("banamex-perfiles-mercado-abierto-2026-08", "adquisicion",
     "3000000", "2000000", "350000", "300000", "23000"),
    ("banamex-perfiles-mercado-abierto-2026-08", "adquisicion",
     "3000000", "2600000", "150000", "100000", "27000"),     # aforo 90 %
    # BX+ Mejora: F11 = D22 + H25, sin tope porcentual (hasta el 85 %)
    ("bx-mejora-tu-hipoteca-2026-01", "sustitucion", "3000000", "2100000", "60000", "60000", "0"),
    # Scotiabank Pago de pasivos: MIN(6 % del saldo, 95 % del valor − saldo)
    ("scotiabank-pasivos-pagos-oportunos-2024-01", "sustitucion",
     "3000000", "1500000", "120000", "90000", "0"),
    ("scotiabank-pasivos-valora-2024-01", "sustitucion",
     "3000000", "2800000", "120000", "50000", "0"),
    # 7x5 Pasivo: 6 % dentro del 75 %; comisión 1.5 % sobre el crédito sin gastos (O32)
    ("scotiabank-7x5-pasivo-hipotecario-2024-01", "sustitucion",
     "3000000", "2000000", "150000", "120000", "30000"),
])
def test_gastos_notariales_financiados_segun_cada_cotizador(
    pid, destino, valor, monto, gastos, financiado, apertura
):
    from datetime import date

    from motor_hipotecario.cat import flujos_cat
    from motor_hipotecario.comparador import evaluar_producto

    base = (_escenario_sustitucion if destino == "sustitucion" else _escenario_adquisicion)(
        D(valor), D(monto), 240
    )
    r = evaluar_producto(_con_gastos(base, gastos), POR_ID[pid], momento=date(2026, 10, 24))
    assert r.elegible, r.motivos_rechazo
    assert r.gastos_financiados == D(financiado)
    assert r.monto_credito == r.tabla.monto == D(monto) + D(financiado)
    assert r.comision_apertura == D(apertura)
    assert r.gastos_de_contado == D(gastos) - D(financiado)
    # CAT: el neto parte del crédito total; los gastos financiados no se restan
    neto, _ = flujos_cat(
        r.tabla, r.producto,
        monto_comision=D(monto) if "scotiabank" in pid else None,
    )
    iva = D("1.16") if _avaluo_neto_de_iva(r.producto) else D(1)
    assert neto == r.monto_credito - r.comision_apertura - r.avaluo / iva - r.comision_investigacion


def _avaluo_neto_de_iva(producto):
    from motor_hipotecario.modelos import ConceptoIVA

    return ConceptoIVA.AVALUO in producto.cat_netos_de_iva


def _escenario_adquisicion(valor, monto, plazo):
    from motor_hipotecario.modelos import Escenario

    return Escenario(valor_vivienda=valor, enganche=valor - monto, plazo_meses=plazo)


def test_bx_mejora_elige_la_tasa_con_el_aforo_que_incluye_los_gastos():
    """VResPlus!F12 = F11/F9 decide el tramo (CC12): 70 % pasa a 72 % con los gastos."""
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    base = _escenario_sustitucion(D("3000000"), D("2100000"), 240)
    sin = evaluar_producto(base, POR_ID["bx-mejora-tu-hipoteca-2026-01"], momento=date(2026, 10, 24))
    con = evaluar_producto(_con_gastos(base, "60000"), POR_ID["bx-mejora-tu-hipoteca-2026-01"],
                           momento=date(2026, 10, 24))
    assert sin.producto.tasa_anual == D("0.0965")
    assert con.producto.tasa_anual == D("0.0985")


def test_comparar_financia_solo_donde_el_producto_lo_permite():
    from datetime import date

    from motor_hipotecario.comparador import comparar

    escenario = _con_gastos(_escenario_sustitucion(D("3000000"), D("1500000"), 240), "120000")
    comparacion = comparar(escenario, CATALOGO, momento=date(2026, 10, 24))
    por_id = {o.producto.id: o for o in comparacion.opciones}
    assert por_id["banorte-mejora-hipoteca-2026-06"].gastos_financiados == 0
    assert por_id["banorte-mejora-hipoteca-2026-06"].gastos_de_contado == D("120000")
    assert por_id["scotiabank-pasivos-pagos-oportunos-2024-01"].gastos_financiados == D("90000")


# ---------------------------------------------------------------------------
# Santander Sustitución con línea de gastos y Afirme Tu Casa 2
# ---------------------------------------------------------------------------

def test_santander_sustitucion_con_linea_de_gastos_reproduce_sus_formulas():
    """
    Réplica de Cal, Liquidez y CAT (que reproduce al centavo el escenario
    guardado de adquisición) con valor 3,000,000, saldo 1,500,000, gastos
    120,000 y 240 meses: la línea de gastos es el 7 % (105,000).
    """
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    escenario = _con_gastos(_escenario_sustitucion(D("3000000"), D("1500000"), 240), "120000")
    r = evaluar_producto(escenario, POR_ID["santander-sustitucion-2025-12"], momento=date(2026, 10, 24))
    assert r.elegible, r.motivos_rechazo
    assert r.gastos_financiados == D("105000") and r.gastos_de_contado == D("15000")
    principal = {
        1: "18017.220681181132281158520163928431066226793165935",
        2: "18015.837770379385374573651921385124539224729570856",
        120: "17716.868214272600609546516304183661439349595437144",
        240: "16769.287399122813710051178650119800143026737963275",
    }
    gastos = {
        1: "1346.2434356826792596810964114749901746358755216155",
        12: "1343.0980017116354945834526677410483049126687297827",
        240: "1102.9660287521367328620429134013014923258017942866",
    }
    for mes, esp in principal.items():
        assert abs(r.tabla.renglones[mes - 1].pago_total - D(esp)) < D("0.000001")
    for mes, esp in gastos.items():
        assert abs(r.tabla_gastos.renglones[mes - 1].pago_total - D(esp)) < D("0.000001")
    assert abs(r.tabla_gastos.renglones[0].iva_intereses - D("157.557988")) < D("0.000001")
    assert abs(r.cat_estimado - D("0.13943305310672")) < D("0.0000001")
    assert abs(r.cat_gastos_estimado - D("0.12955723200051")) < D("0.0000001")
    assert abs(r.pago_regular_inicial - D("19363.464116863811540839616575")) < D("0.000001")


def test_santander_sustitucion_sin_gastos_si_el_siete_por_ciento_no_cabe():
    """Cal!C47: (crédito + 7 %) / valor > aforo → 0, todo o nada."""
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    escenario = _con_gastos(_escenario_sustitucion(D("3000000"), D("2600000"), 240), "120000")
    r = evaluar_producto(escenario, POR_ID["santander-sustitucion-2025-12"], momento=date(2026, 10, 24))
    assert r.elegible
    assert r.gastos_financiados == 0 and r.tabla_gastos is None
    assert r.gastos_de_contado == D("120000")


def _escenario_tu_casa(enganche, garantia, financiar=True):
    from motor_hipotecario.modelos import Escenario

    return Escenario(
        valor_vivienda=D("3000000"), enganche=D(enganche), plazo_meses=180,
        gastos_notariales=D("150000"), financiar_gastos_notariales=financiar,
        valor_garantia_adicional=D(garantia),
    )


def test_afirme_tu_casa_2_financia_gastos_con_la_mecanica_de_adquisicion():
    """
    Sin garantía y con 1,000,000 de enganche el crédito cubre notariales, avalúo
    y la apertura (1 % del total): (2,000,000 + 150,000 + 7,500) / 0.99. Tasa y
    tabla son las de Adquisición al mismo monto (aforo ≤ 80 %).
    """
    from dataclasses import replace
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    momento = date(2026, 7, 6)
    r = evaluar_producto(_escenario_tu_casa("1000000", "0"), POR_ID["afirme-tu-casa-2-2026-07"],
                         momento=momento)
    assert r.elegible, r.motivos_rechazo
    total = (D("2000000") + D("150000") + D("7500")) / D("0.99")
    assert r.monto_credito == total
    assert r.producto.tasa_anual == D("0.1005")
    assert abs(r.desembolso_inicial - D("1000000")) < D("0.01")   # solo el enganche
    adq = evaluar_producto(
        replace(_escenario_tu_casa(str(D("3000000") - total), "0"), financiar_gastos_notariales=False),
        POR_ID["afirme-adquisicion-2026-07"], momento=momento,
    )
    assert adq.monto_credito == total and adq.producto.tasa_anual == D("0.1005")
    assert [x.pago_total for x in r.tabla.renglones] == [x.pago_total for x in adq.tabla.renglones]
    assert r.cat_estimado == adq.cat_estimado


def test_afirme_tu_casa_2_con_garantia_adicional():
    """F3 = MIN(80 % de (vivienda + garantía), vivienda + gastos); dos avalúos."""
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    r = evaluar_producto(_escenario_tu_casa("0", "1500000"), POR_ID["afirme-tu-casa-2-2026-07"],
                         momento=date(2026, 7, 6))
    assert r.elegible, r.motivos_rechazo
    assert r.avaluo == D("7500") + D("3750")          # 2.5 al millar de cada inmueble
    assert r.monto_credito == (D("3000000") + D("150000") + D("11250")) / D("0.99")
    # Sin garantía ni gastos financiados aplica Adquisición
    r = evaluar_producto(_escenario_tu_casa("1000000", "0", financiar=False),
                         POR_ID["afirme-tu-casa-2-2026-07"], momento=date(2026, 7, 6))
    assert not r.elegible



# ---------------------------------------------------------------------------
# Santander Adquisición, versión corregida
# ---------------------------------------------------------------------------
# santander-2026-10 cargaba los montos del flujo del CAT (sin IVA) y el avalúo
# como comisión por apertura. Se cierra y lo sustituye esta versión; la tasa
# es la de mercado abierto (el escenario capturado usa la oferta Asalariados).

def test_santander_adquisicion_cobra_lo_que_cobra_el_cotizador():
    """Con la tasa del escenario capturado (9.5 %, oferta Asalariados), la tabla
    reproduce el pago al cliente (Captura!L88) y el CAT (CAT!E20)."""
    from dataclasses import replace

    from motor_hipotecario.comparador import resolver_para_escenario
    from motor_hipotecario.modelos import Escenario

    p, cobrado = SANTANDER["parametros"], SANTANDER["cobrado"]
    nuevo = POR_ID["santander-adquisicion-2025-12"]
    escenario = Escenario(valor_vivienda=cobrado["valor_vivienda"],
                          enganche=cobrado["valor_vivienda"] - p["monto"], plazo_meses=240)
    resuelto = resolver_para_escenario(nuevo, escenario, 240)
    assert resuelto.avaluo == cobrado["avaluo"] and resuelto.comision_apertura == 0
    capturado = replace(resuelto, tasa_anual=p["tasa_anual"])
    tabla = construir_tabla(LineaCredito(capturado, p["monto"], p["plazo_meses"]), cobrado["valor_vivienda"])
    r1 = tabla.renglones[0]
    assert abs(r1.seguro_danos - cobrado["seguro_danos_mensual"]) < D("1E-20")
    assert r1.comision_mensual == cobrado["comision_mensual"]
    assert abs(r1.pago_total - cobrado["pago_total_mes_1"]) < D("0.000001")
    for mes, (interes, capital, vida, _, saldo) in SANTANDER["renglones"].items():
        x = tabla.renglones[mes - 1]
        for calc, esp in ((x.interes, interes), (x.capital, capital), (x.seguro_vida, vida),
                          (x.saldo_final, saldo)):
            assert abs(calc - esp) < TOL, f"mes {mes}: {calc} != {esp}"
    assert abs(calcular_cat(tabla, capturado) - SANTANDER["cat_esperado"]) < D("0.00000001")


def test_santander_adquisicion_reemplaza_a_la_version_anterior():
    from datetime import date

    from motor_hipotecario.modelos import ConceptoIVA

    viejo, nuevo = POR_ID["santander-2026-10"], POR_ID["santander-adquisicion-2025-12"]
    assert viejo.vigente_en(date(2026, 10, 24)) and not viejo.vigente_en(date(2026, 10, 25))
    assert nuevo.vigente_en(date(2026, 10, 25)) and not nuevo.vigente_en(date(2026, 10, 24))
    assert nuevo.tasa_anual == D("0.1025")                    # Adm!CA8:CA9, oferta Ninguno
    assert 300 not in nuevo.plazos_meses                       # 25 años solo con Asalariados
    assert nuevo.cat_netos_de_iva == frozenset({
        ConceptoIVA.AVALUO, ConceptoIVA.SEGURO_DANOS, ConceptoIVA.COMISION_MENSUAL,
    })
    # La sustitución hereda la versión corregida
    assert POR_ID["santander-sustitucion-2025-12"].vigente_hasta is None


# ---------------------------------------------------------------------------
# Santander Mejora de Condiciones
# ---------------------------------------------------------------------------

def _sustitucion_desde(institucion, plazo=180):
    from dataclasses import replace

    escenario = _con_gastos(_escenario_sustitucion(D("3000000"), D("1500000"), plazo), "120000")
    return replace(escenario, credito_actual=replace(escenario.credito_actual, institucion=institucion))


def test_santander_mejora_de_condiciones_reproduce_sus_formulas():
    """Réplica de Cal, Liquidez y CAT con la tasa de Mejora (10.25 %), 180 meses."""
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    r = evaluar_producto(_sustitucion_desde("Santander"), POR_ID["santander-mejora-condiciones-2025-12"],
                         momento=date(2026, 10, 25))
    assert r.elegible, r.motivos_rechazo
    assert r.gastos_financiados == D("105000") and r.avaluo == D("3000.0036")
    principal = {1: "18755.128649058914129109049777", 60: "18534.484562097303106231871991",
                 180: "17521.431171721039942412443576"}
    gastos = {1: "1385.831742100790655704300151", 60: "1344.458126782104996080470974",
              180: "1155.564163869978391278053913"}
    for mes, esp in principal.items():
        assert abs(r.tabla.renglones[mes - 1].pago_total - D(esp)) < D("0.000001")
    for mes, esp in gastos.items():
        assert abs(r.tabla_gastos.renglones[mes - 1].pago_total - D(esp)) < D("0.000001")
    assert abs(r.cat_estimado - D("0.13079993873644")) < D("0.0000001")
    assert abs(r.cat_gastos_estimado - D("0.11995858200797")) < D("0.0000001")


def test_santander_mejora_o_sustitucion_segun_el_banco_actual():
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto

    mejora, sustitucion = (POR_ID["santander-mejora-condiciones-2025-12"],
                           POR_ID["santander-sustitucion-2025-12"])
    momento = date(2026, 10, 25)
    de_santander = _sustitucion_desde("Banco Santander México")
    assert evaluar_producto(de_santander, mejora, momento=momento).elegible
    assert not evaluar_producto(de_santander, sustitucion, momento=momento).elegible
    de_otro = _sustitucion_desde("BBVA")
    assert not evaluar_producto(de_otro, mejora, momento=momento).elegible
    assert evaluar_producto(de_otro, sustitucion, momento=momento).elegible


def test_santander_mejoras_cofis_reproduce_sus_formulas():
    """
    Mejora de Condiciones con Origen Cofinanciamiento: saldo bancario 1,200,000
    e INFONAVIT 400,000 sobre 3,000,000 a 180 meses, gastos 120,000 (7 % de los
    dos créditos = 112,000). Réplica de Cal, Liquidez, Sustitución y CAT, con
    el pago de la tercera línea fijo como en su CAT (CAT!AW20).
    """
    from dataclasses import replace
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import CreditoInstitutoActual, TipoLinea

    escenario = _con_gastos(_escenario_sustitucion(D("3000000"), D("1200000"), 180), "120000")
    escenario = replace(escenario, credito_actual=replace(
        escenario.credito_actual, institucion="Santander",
        credito_instituto=CreditoInstitutoActual(
            instituto=TipoLinea.INFONAVIT, saldo=D("400000"), pago_mensual=D("4500"),
            plazo_remanente_meses=180,
        ),
    ))
    r = evaluar_producto(escenario, POR_ID["santander-mejora-condiciones-2025-12"],
                         momento=date(2026, 10, 25))
    assert r.elegible, r.motivos_rechazo
    assert r.monto_credito == D("1200000") and r.gastos_financiados == D("112000")
    tercera = r.tabla_instituto_refinanciado
    esperado = {
        "principal": (r.tabla, {1: "15211.302919247131303287239822"}),
        "gastos": (r.tabla_gastos, {1: "1478.220524907510032751253494"}),
        "instituto": (tercera, {1: "5131.100973082377101095746607",
                                60: "5072.262549892614161661832531",
                                180: "4802.114979125610651309984954"}),
    }
    for nombre, (tabla, filas) in esperado.items():
        for mes, valor in filas.items():
            assert abs(tabla.renglones[mes - 1].pago_total - D(valor)) < D("0.000001"), (nombre, mes)
    assert abs(tercera.renglones[59].saldo_final - D("327167.0873320120656703329526")) < D("0.000001")
    assert abs(r.cat_estimado - D("0.13349202193292")) < D("0.0000001")
    assert abs(r.cat_gastos_estimado - D("0.11995858200797")) < D("0.0000001")
    assert abs(r.cat_instituto_refinanciado_estimado - D("0.13530042878267")) < D("0.0000001")
    assert abs(r.pago_regular_inicial - D("21820.624417237018437134239924")) < D("0.000001")



# ---------------------------------------------------------------------------
# Scotiabank Credirenovación (remodelación de la vivienda propia)
# ---------------------------------------------------------------------------
# Sin escenario capturado: valores de una réplica de las hojas Valora y Pagos
# Oportunos (v2025.04) con valor 3,000,000, crédito 1,500,000 y cotización
# 2024-03-22. (meses en que se liquida, pago del mes 1, del mes 13, CAT en %)

_CREDIRENOVACION = {
    ("valora-ninguna", 120): (116, "22920.00", "23238.49", "15.987"),
    ("valora-ninguna", 240): (200, "18090.00", "18363.25", "15.464"),
    ("valora-vinculacion", 180): (169, "17325.00", "17682.73", "13.636"),
    ("valora-green", 120): (117, "20730.00", "21160.23", "13.301"),
    ("valora-premium", 240): (212, "14640.00", "14969.66", "12.286"),
    ("pagos-oportunos-ninguna", 84): (83, "29400.00", "29315.15", "16.821"),
    ("pagos-oportunos-ninguna", 180): (168, "21015.00", "20994.29", "16.013"),
    ("pagos-oportunos-vinculacion", 120): (117, "22425.00", "22372.25", "13.492"),
    ("pagos-oportunos-green", 84): (83, "27255.00", "27163.39", "13.152"),
    ("pagos-oportunos-premium", 120): (117, "21570.00", "21514.38", "12.214"),
    # 20 años con los valores de la campaña (la hoja usa los de Ninguna, W36:X37)
    ("pagos-oportunos-vinculacion", 240): (215, None, None, "13.034"),
    ("pagos-oportunos-premium", 240): (217, None, None, "11.810"),
}


@pytest.mark.parametrize("clave, plazo", sorted(_CREDIRENOVACION))
def test_credirenovacion_reproduce_sus_formulas(clave, plazo):
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Destino, Escenario

    meses, pago1, pago13, cat = _CREDIRENOVACION[(clave, plazo)]
    escenario = Escenario(valor_vivienda=D("3000000"), enganche=D("1500000"), plazo_meses=plazo,
                          destino=Destino.REMODELACION)
    producto = POR_ID[f"scotiabank-credirenovacion-{clave}-2025-04"]
    r = evaluar_producto(escenario, producto, momento=date(2024, 3, 22))
    assert r.elegible, r.motivos_rechazo
    assert len(r.tabla.renglones) == meses
    if pago1:
        assert abs(r.tabla.renglones[0].pago_total - D(pago1)) < D("0.005")
        assert abs(r.tabla.renglones[12].pago_total - D(pago13)) < D("0.005")
    assert abs(r.cat_estimado * 100 - D(cat)) < D("0.0005")


def test_credirenovacion_costos_iniciales_por_campana():
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Destino, Escenario

    escenario = Escenario(valor_vivienda=D("3000000"), enganche=D("1500000"), plazo_meses=120,
                          destino=Destino.REMODELACION)
    costos = {}
    for campana in ("ninguna", "vinculacion", "green", "premium"):
        r = evaluar_producto(escenario, POR_ID[f"scotiabank-credirenovacion-valora-{campana}-2025-04"],
                             momento=date(2024, 3, 22))
        costos[campana] = (r.comision_apertura, r.avaluo, r.dictamen_tecnico)
    assert costos["ninguna"] == (D("15000"), D("8200"), D("15000"))
    assert costos["vinculacion"] == (0, D("8200"), D("15000"))
    assert costos["green"] == (0, D("8200"), 0)
    assert costos["premium"] == (0, 0, D("15000"))


def test_productos_de_remodelacion_en_el_catalogo():
    from motor_hipotecario.modelos import Destino

    ids = {p.id for p in CATALOGO if p.destino is Destino.REMODELACION}
    assert len(ids) == 8 and all(i.startswith("scotiabank-credirenovacion-") for i in ids)


# Modo 2, Compra + Renovación: compra 3,000,000, obra 500,000, enganche
# 800,000 (crédito 2,700,000, aforo 77.1 % del valor proyectado). Valores de
# la réplica de la hoja con el seguro de daños sobre 3,500,000.
_CREDIRENOVACION_COMPRA = {
    ("valora-ninguna", 120): (116, "40667", "15.4277"),
    ("valora-ninguna", 240): (200, "31973", "15.0145"),
    ("valora-vinculacion", 120): (118, "37130", "13.3208"),
    ("valora-green", 240): (210, "27221", "12.6807"),
    ("valora-premium", 240): (212, "25763", "11.8862"),
    ("pagos-oportunos-ninguna", 120): (117, "43340", "15.8022"),
    ("pagos-oportunos-vinculacion", 240): (215, "30434", "12.5753"),
    ("pagos-oportunos-green", 120): (117, "39425", "12.4509"),
    ("pagos-oportunos-premium", 240): (217, "28598", "11.3779"),
}


@pytest.mark.parametrize("clave, plazo", sorted(_CREDIRENOVACION_COMPRA))
def test_credirenovacion_compra_con_remodelacion(clave, plazo):
    from datetime import date

    from motor_hipotecario.comparador import evaluar_producto
    from motor_hipotecario.modelos import Escenario

    meses, pago1, cat = _CREDIRENOVACION_COMPRA[(clave, plazo)]
    escenario = Escenario(valor_vivienda=D("3000000"), enganche=D("800000"), plazo_meses=plazo,
                          monto_remodelacion=D("500000"))
    r = evaluar_producto(escenario, POR_ID[f"scotiabank-credirenovacion-compra-{clave}-2025-04"],
                         momento=date(2024, 3, 22))
    assert r.elegible, r.motivos_rechazo
    assert r.monto_credito == D("2700000") and r.remodelacion_financiada == D("500000")
    assert len(r.tabla.renglones) == meses
    assert abs(r.tabla.renglones[0].pago_total - D(pago1)) < D("0.005")
    assert abs(r.cat_estimado * 100 - D(cat)) < D("0.0001")   # reportado a 4 decimales
    if "premium" not in clave:
        assert r.avaluo == D("11000")                    # tabulador sobre 3,500,000

