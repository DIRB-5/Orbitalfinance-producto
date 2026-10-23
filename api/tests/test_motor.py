"""
Pruebas del motor. Estas son la razón por la que el motor va primero:
validan que la matemática cierra antes de que exista una sola pantalla.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from motor_hipotecario.amortizacion import (
    construir_tabla,
    pago_frances,
    redondear,
    tasa_normalizada,
    tasa_periodica,
)
from motor_hipotecario.cat import calcular_cat, tasa_efectiva_anual
from motor_hipotecario.catalogo_demo import CATALOGO_DEMO
from motor_hipotecario.comparador import comparar, evaluar_producto
from motor_hipotecario.modelos import (
    BaseSeguroDanos,
    ConvencionDias,
    Escenario,
    LineaCredito,
    ProductoHipotecario,
)

HOY = date(2026, 6, 1)


def producto_limpio(**kwargs) -> ProductoHipotecario:
    """Producto sin comisiones ni seguros. Sirve de control matemático."""
    base = dict(
        id="control",
        institucion="Control",
        nombre="Sin comisiones ni seguros",
        tasa_anual=Decimal("0.1085"),
        plazos_meses=(120, 180, 240),
        aforo_max=Decimal("0.95"),
        vigente_desde=date(2026, 1, 1),
    )
    base.update(kwargs)
    return ProductoHipotecario(**base)


# --------------------------------------------------------------------------
# Pago fijo
# --------------------------------------------------------------------------


def test_pago_frances_valor_conocido():
    """1,000,000 a 10.85 % en 240 meses ≈ 10,218.7 de capital + interés."""
    pago = pago_frances(Decimal("1000000"), Decimal("0.1085"), 240)
    assert Decimal("10215") < pago < Decimal("10225")


def test_pago_frances_tasa_cero():
    pago = pago_frances(Decimal("1200000"), Decimal("0"), 120)
    assert pago == Decimal("10000")


def test_pago_frances_rechaza_plazo_invalido():
    with pytest.raises(ValueError):
        pago_frances(Decimal("1000000"), Decimal("0.10"), 0)


# --------------------------------------------------------------------------
# Integridad de la tabla de amortización
# --------------------------------------------------------------------------


def test_saldo_final_es_exactamente_cero():
    """
    La prueba que atrapa los errores de redondeo acumulado.

    El último renglón liquida el remanente, así que el saldo final es cero por
    construcción. Lo que hay que vigilar es CUÁNTO absorbe ese ajuste: el
    capital del último mes debe ser el que da el pago fijo. Con redondeo a
    centavos en la cadena, el ajuste era de centavos o pesos.
    """
    linea = LineaCredito(producto_limpio(), Decimal("1850000"), 240)
    tabla = construir_tabla(linea, Decimal("2500000"))
    ultimo = tabla.renglones[-1]
    assert ultimo.saldo_final == Decimal("0")
    ajuste = ultimo.capital - (tabla.pago_capital_interes - ultimo.interes)
    assert abs(ajuste) < Decimal("1E-15")


def test_suma_de_capital_iguala_el_monto():
    monto = Decimal("1850000")
    linea = LineaCredito(producto_limpio(), monto, 240)
    tabla = construir_tabla(linea, Decimal("2500000"))
    suma = sum(r.capital for r in tabla.renglones)
    # Sin redondeo intermedio la suma no es idéntica: queda un residuo del
    # orden de 1e-21 por la precisión de Decimal. Cualquier cosa por encima de
    # 1e-15 indica un error de cálculo, no de precisión.
    assert abs(suma - monto) < Decimal("1E-15")


def test_numero_de_renglones_igual_al_plazo():
    for plazo in (120, 180, 240):
        linea = LineaCredito(producto_limpio(), Decimal("1000000"), plazo)
        tabla = construir_tabla(linea, Decimal("1500000"))
        assert len(tabla.renglones) == plazo


def test_saldo_es_monotonamente_decreciente():
    linea = LineaCredito(producto_limpio(), Decimal("1850000"), 240)
    tabla = construir_tabla(linea, Decimal("2500000"))
    for anterior, siguiente in zip(tabla.renglones, tabla.renglones[1:]):
        assert siguiente.saldo_inicial < anterior.saldo_inicial


def test_capital_crece_e_interes_decrece():
    """Comportamiento característico del sistema francés."""
    linea = LineaCredito(producto_limpio(), Decimal("1850000"), 240)
    tabla = construir_tabla(linea, Decimal("2500000"))
    primero, ultimo_regular = tabla.renglones[0], tabla.renglones[-2]
    assert ultimo_regular.capital > primero.capital
    assert ultimo_regular.interes < primero.interes


def test_encadenamiento_de_saldos():
    """El saldo final de cada mes es el inicial del siguiente."""
    linea = LineaCredito(CATALOGO_DEMO[0], Decimal("1850000"), 240)
    tabla = construir_tabla(linea, Decimal("2500000"))
    for anterior, siguiente in zip(tabla.renglones, tabla.renglones[1:]):
        assert anterior.saldo_final == siguiente.saldo_inicial


def test_seguro_de_vida_decrece_con_el_saldo():
    linea = LineaCredito(CATALOGO_DEMO[0], Decimal("1850000"), 240)
    tabla = construir_tabla(linea, Decimal("2500000"))
    assert tabla.renglones[-1].seguro_vida < tabla.renglones[0].seguro_vida


def test_seguro_de_danos_es_constante():
    linea = LineaCredito(CATALOGO_DEMO[0], Decimal("1850000"), 240)
    tabla = construir_tabla(linea, Decimal("2500000"))
    valores = {r.seguro_danos for r in tabla.renglones}
    assert len(valores) == 1


def test_pago_total_decrece_por_el_seguro_de_vida():
    """El pago NO es fijo: esta es la trampa del comparativo por mensualidad."""
    linea = LineaCredito(CATALOGO_DEMO[0], Decimal("1850000"), 240)
    tabla = construir_tabla(linea, Decimal("2500000"))
    assert tabla.primer_pago > tabla.renglones[100].pago_total


def test_base_del_seguro_de_danos_cambia_el_costo():
    sobre_total = producto_limpio(
        id="p1",
        seguro_danos_anual=Decimal("0.0035"),
        base_seguro_danos=BaseSeguroDanos.VALOR_TOTAL,
    )
    sobre_construccion = producto_limpio(
        id="p2",
        seguro_danos_anual=Decimal("0.0035"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        factor_construccion=Decimal("0.70"),
    )
    valor = Decimal("2500000")
    t1 = construir_tabla(LineaCredito(sobre_total, Decimal("1850000"), 240), valor)
    t2 = construir_tabla(
        LineaCredito(sobre_construccion, Decimal("1850000"), 240), valor
    )
    assert t1.total_seguros > t2.total_seguros


# --------------------------------------------------------------------------
# CAT
# --------------------------------------------------------------------------


def test_cat_sin_costos_iguala_la_tasa_efectiva():
    """
    Prueba de sanidad del solver: sin comisiones ni seguros, el CAT debe ser
    exactamente (1 + i/12)^12 − 1.
    """
    producto = producto_limpio()
    linea = LineaCredito(producto, Decimal("1850000"), 240)
    tabla = construir_tabla(linea, Decimal("2500000"))
    cat = calcular_cat(tabla, producto)
    esperado = tasa_efectiva_anual(Decimal("0.1085"))
    assert abs(cat - esperado) < Decimal("0.0001")


def test_cat_es_mayor_que_la_tasa_cuando_hay_costos():
    producto = CATALOGO_DEMO[0]
    linea = LineaCredito(producto, Decimal("1850000"), 240)
    tabla = construir_tabla(linea, Decimal("2500000"))
    cat = calcular_cat(tabla, producto)
    assert cat > producto.tasa_anual


def test_cat_sube_al_subir_la_comision():
    barato = producto_limpio(id="b", comision_apertura=Decimal("0.005"))
    caro = producto_limpio(id="c", comision_apertura=Decimal("0.020"))
    valor = Decimal("2500000")
    cat_barato = calcular_cat(
        construir_tabla(LineaCredito(barato, Decimal("1850000"), 240), valor), barato
    )
    cat_caro = calcular_cat(
        construir_tabla(LineaCredito(caro, Decimal("1850000"), 240), valor), caro
    )
    assert cat_caro > cat_barato


def test_cat_en_rango_realista():
    for producto in CATALOGO_DEMO:
        plazo = max(p for p in producto.plazos_meses if p <= 240)
        tabla = construir_tabla(
            LineaCredito(producto, Decimal("1850000"), plazo), Decimal("2500000")
        )
        cat = calcular_cat(tabla, producto)
        assert Decimal("0.08") < cat < Decimal("0.30"), f"{producto.id}: {cat}"


# --------------------------------------------------------------------------
# Elegibilidad
# --------------------------------------------------------------------------


def test_rechaza_aforo_excesivo():
    escenario = Escenario(
        valor_vivienda=Decimal("2500000"),
        enganche=Decimal("125000"),  # 5 % -> aforo 95 %
        plazo_meses=240,
    )
    producto = producto_limpio(aforo_max=Decimal("0.85"))
    resultado = evaluar_producto(escenario, producto)
    assert not resultado.elegible
    assert any("aforo" in m.lower() for m in resultado.motivos_rechazo)


def test_rechaza_plazo_no_disponible():
    escenario = Escenario(
        valor_vivienda=Decimal("2500000"),
        enganche=Decimal("650000"),
        plazo_meses=240,
    )
    producto = producto_limpio(plazos_meses=(60, 120, 180))
    resultado = evaluar_producto(escenario, producto)
    assert not resultado.elegible
    assert any("plazo" in m.lower() for m in resultado.motivos_rechazo)


def test_rechaza_por_capacidad_de_pago():
    escenario = Escenario(
        valor_vivienda=Decimal("2500000"),
        enganche=Decimal("650000"),
        plazo_meses=240,
        ingreso_mensual=Decimal("25000"),
    )
    resultado = evaluar_producto(escenario, producto_limpio())
    assert not resultado.elegible
    assert any("ingreso" in m.lower() for m in resultado.motivos_rechazo)


def test_calcula_tabla_aunque_no_sea_elegible():
    """El asesor necesita mostrar qué pasaría si el cliente ajusta el enganche."""
    escenario = Escenario(
        valor_vivienda=Decimal("2500000"),
        enganche=Decimal("125000"),
        plazo_meses=240,
    )
    resultado = evaluar_producto(escenario, producto_limpio(aforo_max=Decimal("0.85")))
    assert not resultado.elegible
    assert len(resultado.tabla.renglones) == 240


# --------------------------------------------------------------------------
# Comparación
# --------------------------------------------------------------------------


def test_la_tasa_mas_baja_no_siempre_gana():
    """
    La premisa central del producto. Si esta prueba falla, el comparador no
    está aportando nada que un Excel no haga.
    """
    escenario = Escenario(
        valor_vivienda=Decimal("2500000"),
        enganche=Decimal("650000"),
        plazo_meses=240,
        ingreso_mensual=Decimal("90000"),
        factor_pago_ingreso=Decimal("0.35"),
    )
    comparacion = comparar(escenario, CATALOGO_DEMO, momento=HOY)
    elegibles = comparacion.ordenadas_por_costo()

    menor_tasa = min(elegibles, key=lambda o: o.producto.tasa_anual)
    menor_costo = elegibles[0]

    assert menor_tasa.producto.id != menor_costo.producto.id


def test_diferencia_entre_mejor_y_peor_es_material():
    """
    El ahorro entre la mejor y la peor opción debe representar al menos un 2 %
    del monto del crédito. Se expresa como proporción y no como monto fijo
    para que la prueba no dependa de los valores del catálogo ficticio.
    """
    escenario = Escenario(
        valor_vivienda=Decimal("2500000"),
        enganche=Decimal("650000"),
        plazo_meses=240,
        ingreso_mensual=Decimal("90000"),
        factor_pago_ingreso=Decimal("0.35"),
    )
    comparacion = comparar(escenario, CATALOGO_DEMO, momento=HOY)
    proporcion = comparacion.ahorro_vs_peor / escenario.monto_credito
    assert proporcion > Decimal("0.02")


def test_snapshot_congela_los_productos():
    escenario = Escenario(
        valor_vivienda=Decimal("2500000"),
        enganche=Decimal("650000"),
        plazo_meses=240,
    )
    comparacion = comparar(
        escenario, CATALOGO_DEMO, momento=HOY, asesor_id="ase-1", organizacion_id="org-1"
    )
    assert comparacion.snapshot.generado_en == HOY
    assert comparacion.snapshot.asesor_id == "ase-1"
    assert len(comparacion.snapshot.productos) == len(CATALOGO_DEMO)


def test_producto_no_vigente_queda_fuera():
    vencido = producto_limpio(
        id="vencido",
        vigente_desde=date(2025, 1, 1),
        vigente_hasta=date(2025, 12, 31),
    )
    escenario = Escenario(
        valor_vivienda=Decimal("2500000"),
        enganche=Decimal("650000"),
        plazo_meses=240,
    )
    comparacion = comparar(escenario, CATALOGO_DEMO + [vencido], momento=HOY)
    ids = {o.producto.id for o in comparacion.opciones}
    assert "vencido" not in ids


def test_costo_total_supera_al_monto_del_credito():
    escenario = Escenario(
        valor_vivienda=Decimal("2500000"),
        enganche=Decimal("650000"),
        plazo_meses=240,
        gastos_notariales=Decimal("140000"),
    )
    comparacion = comparar(escenario, CATALOGO_DEMO, momento=HOY)
    for opcion in comparacion.opciones:
        assert opcion.costo_total > opcion.monto_credito
        assert opcion.costo_financiero > 0


def test_escenario_invalido_es_rechazado():
    escenario = Escenario(
        valor_vivienda=Decimal("2500000"),
        enganche=Decimal("2500000"),
        plazo_meses=240,
    )
    with pytest.raises(ValueError):
        comparar(escenario, CATALOGO_DEMO, momento=HOY)


def test_condicion_negociada_mejora_el_costo():
    from motor_hipotecario.catalogo_demo import CATALOGO_DEMO_NEGOCIADO

    escenario = Escenario(
        valor_vivienda=Decimal("2500000"),
        enganche=Decimal("650000"),
        plazo_meses=240,
    )
    estandar = evaluar_producto(escenario, CATALOGO_DEMO[0])
    negociado = evaluar_producto(escenario, CATALOGO_DEMO_NEGOCIADO[0])
    assert negociado.costo_total < estandar.costo_total
    assert negociado.advertencias  # debe advertir que es condición negociada


# --------------------------------------------------------------------------
# Preparación para cofinanciamiento
# --------------------------------------------------------------------------


def test_multiples_lineas_suman_flujos():
    """
    v1 usa una sola línea, pero el modelo ya soporta N. Esta prueba fija el
    contrato para cuando entre INFONAVIT.
    """
    bancario = producto_limpio(id="banco", tasa_anual=Decimal("0.1085"))
    social = producto_limpio(id="social", tasa_anual=Decimal("0.0400"))
    valor = Decimal("2500000")

    t1 = construir_tabla(LineaCredito(bancario, Decimal("1200000"), 240), valor)
    t2 = construir_tabla(LineaCredito(social, Decimal("650000"), 240), valor)

    pago_combinado = t1.primer_pago + t2.primer_pago
    monto_combinado = t1.monto + t2.monto

    assert monto_combinado == Decimal("1850000")
    assert pago_combinado > t1.primer_pago


# --------------------------------------------------------------------------
# Convención de conteo de días
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "convencion, esperado",
    [
        (ConvencionDias.TASA_ENTRE_12, Decimal("0.12") / Decimal(12)),
        (ConvencionDias.DIAS_30_4166_360, Decimal("0.12") * Decimal("30.4166") / Decimal(360)),
        (ConvencionDias.DIAS_30_4_360, Decimal("0.12") * Decimal("30.4") / Decimal(360)),
        (ConvencionDias.DIAS_365_12_360, Decimal("0.12") / Decimal(360) * (Decimal(365) / Decimal(12))),
    ],
)
def test_tasa_periodica_por_convencion(convencion, esperado):
    assert tasa_periodica(Decimal("0.12"), convencion) == esperado


def test_convencion_por_defecto_es_tasa_entre_12():
    """Agregar la convención no debe mover ningún producto existente."""
    producto = producto_limpio()
    assert producto.convencion_interes is ConvencionDias.TASA_ENTRE_12
    assert producto.convencion_pago is None
    tabla = construir_tabla(LineaCredito(producto, Decimal("1850000"), 240), Decimal("2500000"))
    assert tabla.renglones[0].interes == Decimal("1850000") * Decimal("0.1085") / Decimal(12)


def test_base_360_cuesta_mas_con_la_misma_tasa_nominal():
    """CLAUDE.md: 10.85 % en base 360 cuesta lo mismo que ~11.00 % en base /12."""
    monto = Decimal("1000000")
    base_12 = construir_tabla(LineaCredito(producto_limpio(), monto, 240), Decimal("1500000"))
    base_360 = construir_tabla(
        LineaCredito(
            producto_limpio(convencion_interes=ConvencionDias.DIAS_30_4166_360),
            monto,
            240,
        ),
        Decimal("1500000"),
    )
    diferencia = base_360.total_pagado - base_12.total_pagado
    assert Decimal("20000") < diferencia < Decimal("30000")


def test_tasa_normalizada_para_ordenar():
    tasa = Decimal("0.1085")
    assert tasa_normalizada(producto_limpio()) == tasa
    normalizada = tasa_normalizada(
        producto_limpio(convencion_interes=ConvencionDias.DIAS_30_4166_360)
    )
    assert abs(normalizada - Decimal("0.1100")) < Decimal("0.0001")



def test_catalogo_demo_muestra_el_efecto_de_la_base_de_dias():
    """
    Demo H y Demo I son Demo A con otra convención de días: misma tasa nominal,
    mismas comisiones y seguros. El comparativo debe ordenarlos A < I < H.
    """
    escenario = Escenario(
        valor_vivienda=Decimal("2500000"),
        enganche=Decimal("650000"),
        plazo_meses=240,
    )
    comparacion = comparar(escenario, CATALOGO_DEMO, momento=HOY)
    costo = {o.producto.id: o.costo_total for o in comparacion.opciones}
    tasa = {o.producto.id: o.producto.tasa_anual for o in comparacion.opciones}

    assert tasa["demo-a-fija"] == tasa["demo-h-base360"] == tasa["demo-i-base304"]
    assert costo["demo-a-fija"] < costo["demo-i-base304"] < costo["demo-h-base360"]
