"""
Comparación de un mismo escenario contra varias instituciones.

Este módulo es el que produce el objeto que consume la presentación. No
imprime, no formatea, no sabe qué es un PDF: devuelve datos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from .amortizacion import TablaAmortizacion, construir_tabla, redondear
from .cat import calcular_cat
from .modelos import (
    Dinero,
    Escenario,
    LineaCredito,
    ProductoHipotecario,
    Snapshot,
)

VERSION_MOTOR = "0.1.0"


@dataclass(frozen=True)
class ResultadoOpcion:
    """Resultado del escenario evaluado contra UN producto."""

    producto: ProductoHipotecario
    tabla: TablaAmortizacion

    monto_credito: Dinero
    comision_apertura: Dinero
    avaluo: Dinero
    gastos_notariales: Dinero

    cat_estimado: Decimal

    elegible: bool
    motivos_rechazo: tuple[str, ...]
    advertencias: tuple[str, ...]

    @property
    def desembolso_inicial(self) -> Dinero:
        """Lo que el cliente saca de su bolsillo el día de la firma."""
        return (
            self.enganche + self.comision_apertura + self.avaluo + self.gastos_notariales
        )

    enganche: Dinero = Decimal("0")

    @property
    def pago_primer_mes(self) -> Dinero:
        return self.tabla.primer_pago

    @property
    def pago_ultimo_mes(self) -> Dinero:
        return self.tabla.ultimo_pago

    @property
    def total_intereses(self) -> Dinero:
        return self.tabla.total_intereses

    @property
    def total_seguros(self) -> Dinero:
        return self.tabla.total_seguros

    @property
    def costo_total(self) -> Dinero:
        """
        Todo lo que el cliente desembolsa a lo largo de la vida del crédito,
        excluyendo el enganche (que es patrimonio, no costo).
        """
        return (
            self.tabla.total_pagado
            + self.comision_apertura
            + self.avaluo
            + self.gastos_notariales
        )

    @property
    def costo_financiero(self) -> Dinero:
        """Costo total menos el capital devuelto. Lo que 'cuesta' el crédito."""
        return self.costo_total - self.monto_credito


@dataclass(frozen=True)
class Comparacion:
    escenario: Escenario
    opciones: tuple[ResultadoOpcion, ...]
    snapshot: Snapshot

    @property
    def elegibles(self) -> tuple[ResultadoOpcion, ...]:
        return tuple(o for o in self.opciones if o.elegible)

    def ordenadas_por_costo(self) -> tuple[ResultadoOpcion, ...]:
        return tuple(sorted(self.elegibles, key=lambda o: o.costo_total))

    def ordenadas_por_pago(self) -> tuple[ResultadoOpcion, ...]:
        return tuple(sorted(self.elegibles, key=lambda o: o.pago_primer_mes))

    def ordenadas_por_cat(self) -> tuple[ResultadoOpcion, ...]:
        return tuple(sorted(self.elegibles, key=lambda o: o.cat_estimado))

    @property
    def mejor_por_costo(self) -> Optional[ResultadoOpcion]:
        ordenadas = self.ordenadas_por_costo()
        return ordenadas[0] if ordenadas else None

    @property
    def ahorro_vs_peor(self) -> Dinero:
        """
        Diferencia de costo total entre la mejor y la peor opción elegible.
        Es el número que justifica que exista la herramienta.
        """
        ordenadas = self.ordenadas_por_costo()
        if len(ordenadas) < 2:
            return Decimal("0")
        return ordenadas[-1].costo_total - ordenadas[0].costo_total


def evaluar_producto(
    escenario: Escenario,
    producto: ProductoHipotecario,
    fecha_primer_pago: Optional[date] = None,
) -> ResultadoOpcion:
    """Evalúa un escenario contra un producto y devuelve el resultado completo."""

    monto = escenario.monto_credito
    plazo = escenario.plazo_meses

    motivos: list[str] = []
    advertencias: list[str] = []

    # --- Reglas de elegibilidad -------------------------------------------
    if escenario.aforo > producto.aforo_max:
        motivos.append(
            f"El aforo solicitado ({escenario.aforo:.1%}) supera el máximo del "
            f"producto ({producto.aforo_max:.1%}). Se requiere más enganche."
        )

    if plazo not in producto.plazos_meses:
        motivos.append(
            f"El plazo de {plazo} meses no está disponible. "
            f"Plazos ofrecidos: {', '.join(str(p) for p in producto.plazos_meses)}."
        )

    if producto.monto_minimo is not None and monto < producto.monto_minimo:
        motivos.append(
            f"El monto está por debajo del mínimo del producto "
            f"(${producto.monto_minimo:,.0f})."
        )

    if producto.monto_maximo is not None and monto > producto.monto_maximo:
        motivos.append(
            f"El monto excede el máximo del producto "
            f"(${producto.monto_maximo:,.0f})."
        )

    # --- Cálculo -----------------------------------------------------------
    # Se calcula aunque no sea elegible: el asesor necesita poder mostrarle al
    # cliente cuánto enganche adicional le abriría esta opción.
    plazo_calculo = plazo if plazo in producto.plazos_meses else max(
        (p for p in producto.plazos_meses if p <= plazo),
        default=min(producto.plazos_meses),
    )

    linea = LineaCredito(producto=producto, monto=monto, plazo_meses=plazo_calculo)
    tabla = construir_tabla(
        linea,
        escenario.valor_vivienda,
        fecha_primer_pago or escenario.fecha_primer_pago or primer_pago_por_defecto(date.today()),
    )

    if tabla.amortizacion_negativa:
        motivos.append(
            "Con este plazo el pago inicial no cubre los intereses y el saldo "
            f"crecería hasta ${tabla.saldo_maximo:,.0f} antes de bajar "
            "(amortización negativa). Un plazo menor lo resolvería."
        )

    comision = redondear(producto.comision_apertura_para(monto))
    cat = calcular_cat(tabla, producto)

    # --- Capacidad de pago -------------------------------------------------
    if escenario.ingreso_mensual:
        tope = escenario.ingreso_mensual * escenario.factor_pago_ingreso
        if tabla.primer_pago > tope:
            motivos.append(
                f"El pago inicial (${tabla.primer_pago:,.2f}) supera el "
                f"{escenario.factor_pago_ingreso:.0%} del ingreso comprobable "
                f"(${tope:,.2f})."
            )
        elif tabla.primer_pago > tope * Decimal("0.85"):
            advertencias.append(
                "El pago se acerca al límite de capacidad de pago. El banco "
                "podría requerir un coacreditado."
            )

    if producto.negociado_por:
        advertencias.append(
            f"Condición negociada por {producto.negociado_por}. "
            "Sujeta a confirmación con la institución."
        )

    return ResultadoOpcion(
        producto=producto,
        tabla=tabla,
        monto_credito=monto,
        comision_apertura=comision,
        avaluo=producto.avaluo,
        gastos_notariales=escenario.gastos_notariales,
        cat_estimado=cat,
        elegible=not motivos,
        motivos_rechazo=tuple(motivos),
        advertencias=tuple(advertencias),
        enganche=escenario.enganche,
    )


def primer_pago_por_defecto(momento: date) -> date:
    """Día 1 del mes siguiente."""
    if momento.month == 12:
        return date(momento.year + 1, 1, 1)
    return date(momento.year, momento.month + 1, 1)


def comparar(
    escenario: Escenario,
    productos: list[ProductoHipotecario],
    momento: Optional[date] = None,
    asesor_id: str = "",
    organizacion_id: str = "",
) -> Comparacion:
    """
    Compara un escenario contra el catálogo vigente y devuelve el resultado
    junto con el snapshot que debe persistirse.
    """
    errores = escenario.validar()
    if errores:
        raise ValueError("Escenario inválido: " + " ".join(errores))

    momento = momento or date.today()
    vigentes = [p for p in productos if p.vigente_en(momento)]

    if not vigentes:
        raise ValueError(
            f"No hay productos vigentes al {momento.isoformat()} en el catálogo."
        )

    # Sin fecha capturada se usa el día 1 del mes siguiente a la comparación;
    # el snapshot guarda `generado_en`, así que el cálculo es reproducible.
    fecha_primer_pago = escenario.fecha_primer_pago or primer_pago_por_defecto(momento)
    opciones = tuple(evaluar_producto(escenario, p, fecha_primer_pago) for p in vigentes)

    snapshot = Snapshot(
        generado_en=momento,
        escenario=escenario,
        productos=tuple(vigentes),
        version_motor=VERSION_MOTOR,
        asesor_id=asesor_id,
        organizacion_id=organizacion_id,
    )

    return Comparacion(escenario=escenario, opciones=opciones, snapshot=snapshot)
