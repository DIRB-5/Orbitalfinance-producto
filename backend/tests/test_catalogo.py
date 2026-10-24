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
