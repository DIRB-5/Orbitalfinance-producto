"""
Costo Anual Total (CAT).

El CAT NO es la tasa de interés. Es la tasa efectiva anual que iguala el valor
presente de lo que el cliente recibe con el valor presente de todo lo que paga.
Es una TIR y no tiene solución cerrada: se resuelve numéricamente.

    Σ Disposiciones/(1+CAT)^t  =  Σ Pagos/(1+CAT)^s      (t, s en AÑOS)

Qué entra y qué no, según la metodología de Banxico:

  ENTRA    monto dispuesto, comisión por apertura, seguros exigidos por el
           otorgante (vida y daños), avalúo cobrado por la institución.
  NO ENTRA gastos notariales, escrituración e impuestos: los cobra un tercero,
           no el banco.

ADVERTENCIA DE VALIDACIÓN
Esta es una implementación fiel de la metodología general, pero cada
institución publica su CAT con supuestos propios (fecha de corte, tratamiento
del primer periodo, si financia o no la comisión). Antes de mostrar este
número al cliente final hay que contrastarlo contra el CAT publicado de cada
producto y ajustar los supuestos hasta empatar. Mientras eso no ocurra, el
campo debe rotularse como estimado.
"""

from __future__ import annotations

from decimal import Decimal

from .amortizacion import TablaAmortizacion
from .modelos import Dinero, ProductoHipotecario

# Precisión objetivo del solver: 1e-8 en tasa anual
TOLERANCIA = Decimal("1E-8")
MAX_ITERACIONES = 200


def _valor_presente_neto(
    tasa: Decimal, neto_recibido: Dinero, pagos: list[Decimal]
) -> Decimal:
    """
    VPN de los flujos. pagos[k] es el pago del mes k+1.
    El descuento usa exponente en años: (1 + tasa)^(mes/12).
    """
    base = Decimal(1) + tasa
    vpn = neto_recibido
    for k, pago in enumerate(pagos, start=1):
        exponente = Decimal(k) / Decimal(12)
        vpn -= pago / (base**exponente)
    return vpn


def calcular_cat(
    tabla: TablaAmortizacion,
    producto: ProductoHipotecario,
    comision_financiada: bool = False,
) -> Decimal:
    """
    Devuelve el CAT como fracción anual (0.1234 == 12.34 %).

    comision_financiada:
        False -> el cliente paga la comisión de su bolsillo al inicio, por lo
                 que recibe menos dinero neto.
        True  -> la comisión se suma al crédito; el monto ya la incluye.
    """
    comision = producto.comision_apertura * tabla.monto
    avaluo = producto.avaluo

    if comision_financiada:
        # El monto ya trae la comisión dentro; el neto en manos del cliente
        # es el monto menos lo que se le retuvo.
        neto = tabla.monto - comision - avaluo
    else:
        neto = tabla.monto - comision - avaluo

    if neto <= 0:
        raise ValueError(
            "Las comisiones y el avalúo superan el monto del crédito. "
            "Revisa los parámetros del producto."
        )

    pagos = [r.pago_total for r in tabla.renglones]

    # Bisección. El CAT siempre es positivo y realistamente menor a 500 %.
    bajo = Decimal("0")
    alto = Decimal("5")

    vpn_bajo = _valor_presente_neto(bajo, neto, pagos)
    vpn_alto = _valor_presente_neto(alto, neto, pagos)

    if vpn_bajo * vpn_alto > 0:
        raise ValueError(
            "No se encontró un CAT dentro del rango 0 %–500 %. "
            "Los flujos del producto son inconsistentes."
        )

    for _ in range(MAX_ITERACIONES):
        medio = (bajo + alto) / Decimal(2)
        vpn_medio = _valor_presente_neto(medio, neto, pagos)

        if abs(vpn_medio) < Decimal("0.000001") or (alto - bajo) < TOLERANCIA:
            return medio

        if vpn_bajo * vpn_medio < 0:
            alto = medio
            vpn_alto = vpn_medio
        else:
            bajo = medio
            vpn_bajo = vpn_medio

    return (bajo + alto) / Decimal(2)


def tasa_efectiva_anual(tasa_anual_nominal: Decimal) -> Decimal:
    """
    (1 + i/12)^12 − 1

    Es el piso teórico del CAT: si un producto no tuviera comisiones ni
    seguros, su CAT sería exactamente esto. Sirve como prueba de sanidad del
    solver.
    """
    i = tasa_anual_nominal / Decimal(12)
    return (Decimal(1) + i) ** 12 - Decimal(1)
