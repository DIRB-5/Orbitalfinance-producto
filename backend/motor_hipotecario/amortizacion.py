"""
Amortización por sistema francés (pago fijo de capital + interés).

El seguro de vida se calcula sobre saldo insoluto, por lo que el pago TOTAL
mensual no es fijo: baja mes a mes. Esta es la razón por la que comparar
créditos por "el pago mensual" es engañoso y hay que comparar costo total.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from .modelos import (
    AportacionExcedente,
    BaseSeguroDanos,
    Cofinanciamiento,
    ReglaAportaciones,
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
    fecha_pago: Optional[date] = None
    # Aportación patronal abonada a capital. No la paga el cliente.
    aportacion: Dinero = Decimal("0")


@dataclass(frozen=True)
class TablaAmortizacion:
    renglones: tuple[Renglon, ...]
    # El pago fijo. Sin seguros, salvo en productos con seguros_en_pago_fijo.
    pago_capital_interes: Dinero
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
    def total_aportaciones(self) -> Dinero:
        return sum((r.aportacion for r in self.renglones), Decimal("0"))

    @property
    def plazo_efectivo_meses(self) -> int:
        """Meses en que realmente se liquida; menor al plazo con tasa escalonada."""
        return len(self.renglones)

    @property
    def amortizacion_negativa(self) -> bool:
        """True si algún mes el pago no cubre el interés y el saldo sube."""
        return any(r.capital < 0 for r in self.renglones)

    @property
    def saldo_maximo(self) -> Dinero:
        return max([self.monto] + [r.saldo_final for r in self.renglones])

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


def tasa_periodica(
    tasa_anual: Decimal, convencion: ConvencionDias, dias: Optional[int] = None
) -> Decimal:
    """
    Tasa del periodo mensual según la convención de conteo de días. `dias` es
    obligatorio con días reales: los días del mes del pago.
    """
    if convencion is ConvencionDias.DIAS_REALES_360:
        if dias is None:
            raise ValueError("La convención de días reales necesita los días del periodo.")
        return tasa_anual * Decimal(dias) / Decimal(360)
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

    Días reales se normaliza con un año de 365 días.
    """
    if producto.convencion_interes is ConvencionDias.DIAS_REALES_360:
        return producto.tasa_anual * Decimal(365) / Decimal(360)
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
    if convencion is ConvencionDias.DIAS_REALES_360:
        raise ValueError(
            "El pago fijo no puede calcularse con días reales: define "
            "convencion_pago en el producto."
        )
    return _anualidad(monto, tasa_periodica(tasa_anual, convencion), plazo_meses)


def _anualidad(monto: Dinero, i: Decimal, plazo_meses: int) -> Decimal:
    if plazo_meses <= 0:
        raise ValueError("El plazo debe ser mayor a cero.")
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero.")

    # Caso tasa cero (aplica en algunos esquemas de vivienda social)
    if i == 0:
        return monto / Decimal(plazo_meses)

    factor = (Decimal(1) + i) ** Decimal(-plazo_meses)
    return monto * i / (Decimal(1) - factor)


def _anualidad_creciente(
    monto: Dinero, i: Decimal, plazo_meses: int, crecimiento_mensual: Decimal
) -> Decimal:
    """
    Primer pago de una mensualidad que crece `crecimiento_mensual` cada mes,
    tal que el valor presente de todos los pagos sea el monto:

        monto = Σ P · (1 + g)^(k−1) / (1 + i)^k,   k = 1..n

    Con crecimiento cero es la anualidad de siempre.
    """
    if crecimiento_mensual == 0:
        return _anualidad(monto, i, plazo_meses)
    if plazo_meses <= 0:
        raise ValueError("El plazo debe ser mayor a cero.")
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero.")

    suma = Decimal(0)
    termino = Decimal(1) / (Decimal(1) + i)
    razon = (Decimal(1) + crecimiento_mensual) / (Decimal(1) + i)
    for _ in range(plazo_meses):
        suma += termino
        termino *= razon
    return monto / suma


def _validar_crecimiento(producto: ProductoHipotecario) -> None:
    fases = producto.crecimiento_pago_mensual
    if not fases:
        return
    meses = [desde for desde, _ in fases]
    if meses[0] != 1 or any(b <= a for a, b in zip(meses, meses[1:])):
        raise ValueError(
            "Las fases de crecimiento deben empezar en el mes 1 y en meses crecientes."
        )


def _sumar_meses(fecha: date, meses: int) -> date:
    total = fecha.month - 1 + meses
    anio, mes = fecha.year + total // 12, total % 12 + 1
    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))


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


def aportacion_patronal(regla: ReglaAportaciones, salario: Dinero, mes: int) -> Decimal:
    """Aportación que el instituto abona en `mes` (0 si ese mes no hay)."""
    if mes < regla.mes_inicio or (mes - regla.mes_inicio) % regla.cada_meses:
        return Decimal("0")
    base = regla.porcentaje_salario * salario
    if regla.tope is not None:
        base = min(base, regla.tope)
    if regla.incremento_anual:
        base *= (Decimal(1) + regla.incremento_anual) ** ((mes - 1) // 12)
    return base


def _validar_escalones(producto: ProductoHipotecario) -> None:
    escalones = producto.tasas_escalonadas
    if not escalones:
        return
    if producto.crecimiento_pago_mensual:
        raise ValueError("La tasa escalonada no se combina con mensualidad creciente.")
    meses = [desde for desde, _ in escalones]
    if meses[0] < 2 or any(b <= a for a, b in zip(meses, meses[1:])):
        raise ValueError(
            "Los escalones de tasa deben empezar después del mes 1 y en meses crecientes."
        )
    if not producto.recalcular_pago_al_cambiar_tasa:
        tasas = [producto.tasa_anual] + [t for _, t in escalones]
        if any(b > a for a, b in zip(tasas, tasas[1:])):
            raise ValueError(
                "Con pago fijo la tasa no puede subir: el pago calculado a la "
                "tasa inicial no amortizaría. Usa recalcular_pago_al_cambiar_tasa."
            )


def _tasa_del_mes(producto: ProductoHipotecario, mes: int) -> Decimal:
    tasa = producto.tasa_anual
    for desde, tasa_escalon in producto.tasas_escalonadas:
        if mes >= desde:
            tasa = tasa_escalon
    return tasa


def construir_tabla(
    linea: LineaCredito,
    valor_vivienda: Dinero,
    fecha_primer_pago: Optional[date] = None,
    cofinanciamiento: Optional[Cofinanciamiento] = None,
) -> TablaAmortizacion:
    """
    Construye la tabla completa, con precisión completa en cada renglón.

    No se redondea nada aquí: redondear cada renglón a centavos acumula hasta
    $32 de desviación contra los cotizadores bancarios a 25 años. El redondeo
    ocurre solo al presentar (ver `redondear`).

    El último renglón liquida el saldo remanente para que cierre exactamente en
    cero; sin redondeo intermedio ese remanente es del orden de 1e-20.

    `fecha_primer_pago` es obligatoria con días reales; con las demás
    convenciones solo sirve para fechar los renglones.

    Con tasa escalonada y pago fijo la tabla puede terminar antes del plazo:
    el último renglón es el que deja el saldo en cero.

    Con `cofinanciamiento` y un producto con `regla_aportaciones`, las
    aportaciones patronales se abonan a capital: el pago del cliente no cambia
    y el plazo se acorta.
    """
    monto = linea.monto
    tasa = linea.producto.tasa_anual
    plazo = linea.plazo_meses
    producto = linea.producto
    convencion_interes = producto.convencion_interes
    convencion_pago = producto.convencion_pago or convencion_interes
    convencion_amortizacion = producto.convencion_amortizacion

    dias_reales = convencion_interes is ConvencionDias.DIAS_REALES_360
    if dias_reales and fecha_primer_pago is None:
        raise ValueError(
            "El producto cobra interés con días reales: se necesita la fecha "
            "del primer pago."
        )
    if convencion_amortizacion is ConvencionDias.DIAS_REALES_360:
        raise ValueError("La base de amortización no puede ser días reales.")
    _validar_escalones(producto)
    _validar_crecimiento(producto)
    inicios_de_escalon = {desde for desde, _ in producto.tasas_escalonadas}
    regla = producto.regla_aportaciones if cofinanciamiento else None

    danos = _seguro_danos_mensual(producto, valor_vivienda)
    comision_mensual = producto.comision_mensual

    if convencion_pago is ConvencionDias.DIAS_REALES_360:
        raise ValueError(
            "El pago fijo no puede calcularse con días reales: define "
            "convencion_pago en el producto."
        )

    # Si el pago y el interés usan convenciones distintas (Santander), el
    # último renglón absorbe la diferencia acumulada.
    fases_crecimiento = dict(producto.crecimiento_pago_mensual)
    crece = bool(fases_crecimiento)
    crecimiento = fases_crecimiento.get(1, Decimal(0))
    i_pago = tasa_periodica(tasa, convencion_pago)
    seguros_en_pago = Decimal(0)
    if producto.seguros_en_pago_fijo:
        # Los seguros van dentro del pago: anualidad con la tasa del seguro de
        # vida sumada a la del periodo, más el seguro de daños.
        i_pago += producto.seguro_vida_mensual
        seguros_en_pago = danos
    anualidad = _anualidad_creciente(monto, i_pago, plazo, crecimiento)
    pago_fijo = anualidad + seguros_en_pago
    pago_fijo_inicial = pago_fijo

    renglones: list[Renglon] = []
    saldo = monto

    for mes in range(1, plazo + 1):
        saldo_inicial = saldo
        fecha = _sumar_meses(fecha_primer_pago, mes - 1) if fecha_primer_pago else None
        dias = calendar.monthrange(fecha.year, fecha.month)[1] if dias_reales else None
        tasa = _tasa_del_mes(producto, mes)

        if mes in inicios_de_escalon and producto.recalcular_pago_al_cambiar_tasa:
            # Nuevo pago sobre el saldo y los meses que faltan, a la nueva tasa
            i_pago = tasa_periodica(tasa, convencion_pago)
            if producto.seguros_en_pago_fijo:
                i_pago += producto.seguro_vida_mensual
            anualidad = _anualidad(saldo_inicial, i_pago, plazo - mes + 1)
            pago_fijo = anualidad + seguros_en_pago

        interes = saldo_inicial * tasa_periodica(tasa, convencion_interes, dias)
        vida = saldo_inicial * producto.seguro_vida_mensual

        # Interés que se descuenta del pago para obtener el capital. Si la base
        # de amortización difiere de la de cobro, no es el interés cobrado.
        interes_amortizacion = interes
        if convencion_amortizacion is not None:
            interes_amortizacion = saldo_inicial * tasa_periodica(tasa, convencion_amortizacion)

        pago_del_mes = pago_fijo
        if crece:
            if mes in fases_crecimiento and mes > 1:
                # Nueva fase: se recalcula sobre el saldo y el plazo restante
                crecimiento = fases_crecimiento[mes]
                anualidad = _anualidad_creciente(saldo_inicial, i_pago, plazo - mes + 1, crecimiento)
            elif mes > 1:
                anualidad *= Decimal(1) + crecimiento
            pago_del_mes = anualidad + seguros_en_pago

        if mes == plazo:
            # Pago final: liquida todo el saldo remanente
            capital = saldo_inicial
        else:
            disponible = pago_del_mes - (vida + danos if producto.seguros_en_pago_fijo else 0)
            capital = disponible - interes_amortizacion
            # Blindaje: con pago fijo, un pago que no cubre el interés nunca
            # amortizaría; se detecta en vez de producir una tabla
            # silenciosamente incorrecta. Con pago creciente es amortización
            # negativa: la tabla cierra igual y el comparador la rechaza.
            if capital <= 0 and not crece:
                raise ValueError(
                    f"El pago mensual no cubre los intereses del mes {mes}. "
                    "Revisa tasa y plazo del producto."
                )
            capital = min(capital, saldo_inicial)

        aportacion = Decimal("0")
        if regla is not None and mes < plazo:
            aportacion = aportacion_patronal(regla, cofinanciamiento.salario_mensual, mes)
            pendiente = saldo_inicial - capital
            if aportacion > pendiente:
                if regla.excedente is AportacionExcedente.OMITIR:
                    aportacion = Decimal("0")
                else:
                    aportacion = pendiente

        saldo_final = saldo_inicial - capital - aportacion
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
                fecha_pago=fecha,
                aportacion=aportacion,
            )
        )
        saldo = saldo_final
        if saldo == 0:
            break  # se liquidó antes del plazo (tasa escalonada o aportaciones)

    return TablaAmortizacion(
        renglones=tuple(renglones),
        pago_capital_interes=pago_fijo_inicial,
        monto=monto,
        tasa_anual=producto.tasa_anual,
        plazo_meses=plazo,
    )
