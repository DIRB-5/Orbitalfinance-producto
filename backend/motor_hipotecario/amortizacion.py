"""
Amortización por sistema francés (pago fijo de capital + interés).

El seguro de vida se calcula sobre saldo insoluto, por lo que el pago TOTAL
mensual no es fijo: baja mes a mes. Esta es la razón por la que comparar
créditos por "el pago mensual" es engañoso y hay que comparar costo total.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .modelos import (
    BaseSeguroDanos,
    ConvencionDias,
    Dinero,
    LineaCredito,
    ProductoHipotecario,
)

CENTAVO = Decimal("0.01")


def redondear(valor: Decimal) -> Decimal:
    """
    Redondeo a centavos, medio hacia arriba (criterio bancario habitual).

    Solo para la capa de presentación. Los bancos no redondean valores
    intermedios: la tabla se construye con precisión completa y se redondea al
    desplegar (docs/validacion_modelos.md, 3.4).
    """
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Renglon:
    mes: int
    saldo_inicial: Dinero
    interes: Dinero
    capital: Dinero
    seguro_vida: Dinero
    seguro_danos: Dinero
    comision_mensual: Dinero
    pago_total: Dinero
    saldo_final: Dinero


@dataclass(frozen=True)
class TablaAmortizacion:
    renglones: tuple[Renglon, ...]
    pago_capital_interes: Dinero  # el pago fijo, sin seguros
    monto: Dinero
    tasa_anual: Decimal
    plazo_meses: int

    @property
    def total_intereses(self) -> Dinero:
        return sum((r.interes for r in self.renglones), Decimal("0"))

    @property
    def total_seguros(self) -> Dinero:
        return sum(
            (r.seguro_vida + r.seguro_danos for r in self.renglones), Decimal("0")
        )

    @property
    def total_comision_mensual(self) -> Dinero:
        return sum((r.comision_mensual for r in self.renglones), Decimal("0"))

    @property
    def total_pagado(self) -> Dinero:
        return sum((r.pago_total for r in self.renglones), Decimal("0"))

    @property
    def primer_pago(self) -> Dinero:
        return self.renglones[0].pago_total

    @property
    def ultimo_pago(self) -> Dinero:
        return self.renglones[-1].pago_total

    def saldo_al_mes(self, mes: int) -> Dinero:
        """Saldo insoluto al cierre del mes indicado. Útil para prepagos."""
        if mes <= 0:
            return self.monto
        return self.renglones[min(mes, len(self.renglones)) - 1].saldo_final


def tasa_periodica(tasa_anual: Decimal, convencion: ConvencionDias) -> Decimal:
    """Tasa del periodo mensual según la convención de conteo de días."""
    if convencion is ConvencionDias.TASA_ENTRE_12:
        return tasa_anual / Decimal(12)
    if convencion is ConvencionDias.DIAS_30_4166_360:
        return tasa_anual * Decimal("30.4166") / Decimal(360)
    if convencion is ConvencionDias.DIAS_30_4_360:
        return tasa_anual * Decimal("30.4") / Decimal(360)
    if convencion is ConvencionDias.DIAS_365_12_360:
        # 365/12 es periódico (30.41666…), distinto de la constante 30.4166
        return tasa_anual / Decimal(360) * (Decimal(365) / Decimal(12))
    raise ValueError(f"Convención de días no soportada: {convencion}")


def tasa_normalizada(producto: ProductoHipotecario) -> Decimal:
    """
    Tasa anual equivalente en base /12, usada SOLO para ordenar productos con
    convenciones distintas. Al presentar se muestra la tasa nominal del
    contrato y, por separado, esta.
    """
    return tasa_periodica(producto.tasa_anual, producto.convencion_interes) * 12


def pago_frances(
    monto: Dinero,
    tasa_anual: Decimal,
    plazo_meses: int,
    convencion: ConvencionDias = ConvencionDias.TASA_ENTRE_12,
) -> Decimal:
    """
    Pago mensual fijo de capital + interés.

        pago = P · i / (1 − (1 + i)^−n)

    Se devuelve SIN redondear, igual que el resto de la tabla.
    """
    if plazo_meses <= 0:
        raise ValueError("El plazo debe ser mayor a cero.")
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero.")

    i = tasa_periodica(tasa_anual, convencion)

    # Caso tasa cero (aplica en algunos esquemas de vivienda social)
    if i == 0:
        return monto / Decimal(plazo_meses)

    factor = (Decimal(1) + i) ** Decimal(-plazo_meses)
    return monto * i / (Decimal(1) - factor)


def _seguro_danos_mensual(
    producto: ProductoHipotecario, valor_vivienda: Dinero
) -> Decimal:
    if producto.seguro_danos_monto_mensual is not None:
        return producto.seguro_danos_monto_mensual
    if producto.seguro_danos_anual == 0:
        return Decimal("0")

    base = valor_vivienda
    if producto.base_seguro_danos is BaseSeguroDanos.VALOR_CONSTRUCCION:
        base = valor_vivienda * producto.factor_construccion

    return base * producto.seguro_danos_anual / Decimal(12)


def construir_tabla(
    linea: LineaCredito,
    valor_vivienda: Dinero,
) -> TablaAmortizacion:
    """
    Construye la tabla completa, con precisión completa en cada renglón.

    No se redondea nada aquí: redondear cada renglón a centavos acumula hasta
    $32 de desviación contra los cotizadores bancarios a 25 años. El redondeo
    ocurre solo al presentar (ver `redondear`).

    El último renglón liquida el saldo remanente para que cierre exactamente en
    cero; sin redondeo intermedio ese remanente es del orden de 1e-20.
    """
    monto = linea.monto
    tasa = linea.producto.tasa_anual
    plazo = linea.plazo_meses
    producto = linea.producto
    i = tasa_periodica(tasa, producto.convencion_interes)
    convencion_pago = producto.convencion_pago or producto.convencion_interes

    # Si el pago y el interés usan convenciones distintas (Santander), el
    # último renglón absorbe la diferencia acumulada.
    pago_fijo = pago_frances(monto, tasa, plazo, convencion_pago)
    danos = _seguro_danos_mensual(producto, valor_vivienda)
    comision_mensual = producto.comision_mensual

    renglones: list[Renglon] = []
    saldo = monto

    for mes in range(1, plazo + 1):
        saldo_inicial = saldo
        interes = saldo_inicial * i
        vida = saldo_inicial * linea.producto.seguro_vida_mensual

        if mes == plazo:
            # Pago final: liquida todo el saldo remanente
            capital = saldo_inicial
        else:
            capital = pago_fijo - interes
            # Blindaje: si la tasa fuera tan alta que el pago no cubre el
            # interés, la tabla nunca amortizaría. Se detecta en vez de
            # producir una tabla silenciosamente incorrecta.
            if capital <= 0:
                raise ValueError(
                    f"El pago mensual no cubre los intereses del mes {mes}. "
                    "Revisa tasa y plazo del producto."
                )
            capital = min(capital, saldo_inicial)

        saldo_final = saldo_inicial - capital
        pago_total = capital + interes + vida + danos + comision_mensual

        renglones.append(
            Renglon(
                mes=mes,
                saldo_inicial=saldo_inicial,
                interes=interes,
                capital=capital,
                seguro_vida=vida,
                seguro_danos=danos,
                comision_mensual=comision_mensual,
                pago_total=pago_total,
                saldo_final=saldo_final,
            )
        )
        saldo = saldo_final

    return TablaAmortizacion(
        renglones=tuple(renglones),
        pago_capital_interes=pago_fijo,
        monto=monto,
        tasa_anual=tasa,
        plazo_meses=plazo,
    )
