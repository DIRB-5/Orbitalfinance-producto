"""
Comparación de un mismo escenario contra varias instituciones.

Este módulo es el que produce el objeto que consume la presentación. No
imprime, no formatea, no sabe qué es un PDF: devuelve datos.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from .amortizacion import TablaAmortizacion, construir_tabla, redondear
from .cat import calcular_cat
from .instituto import COFINAVIT, aportaciones_despues_de, tabla_credito_instituto
from .referencias import TIIE_BASE
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

    # True si el escenario traía cofinanciamiento que este producto no acepta
    # y se evaluó como la ruta sin instituto (mismo enganche propio, el banco
    # financia también lo que cubriría el instituto).
    alternativa_sin_cofinanciamiento: bool = False

    # Crédito del instituto en cofinanciamiento (Cofinavit), si lo hay. Las
    # aportaciones lo pagan primero; después van al crédito bancario.
    tabla_instituto: Optional[TablaAmortizacion] = None

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
    def total_aportaciones(self) -> Dinero:
        total = self.tabla.total_aportaciones
        if self.tabla_instituto is not None:
            total += self.tabla_instituto.total_aportaciones
        return total

    @property
    def costo_total(self) -> Dinero:
        """
        Todo lo que se paga a lo largo de la vida del crédito, excluyendo el
        enganche (que es patrimonio, no costo). Incluye las aportaciones
        patronales del cofinanciamiento: son dinero de la subcuenta del
        trabajador, aunque no salgan de su bolsillo cada mes.
        """
        pagado_instituto = (
            self.tabla_instituto.total_pagado if self.tabla_instituto is not None else Decimal("0")
        )
        return (
            self.tabla.total_pagado
            + pagado_instituto
            + self.total_aportaciones
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


def _acepta(producto: ProductoHipotecario, cofinanciamiento) -> bool:
    regla = producto.regla_aportaciones
    return regla is not None and regla.instituto is cofinanciamiento.instituto


def resolver_para_escenario(
    producto: ProductoHipotecario, escenario: Escenario, plazo: int
) -> ProductoHipotecario:
    """
    Condiciones que dependen del escenario: la tasa por plazo y aforo, y el
    avalúo por tabulador. Devuelve una copia con los valores resueltos (el
    snapshot queda reproducible) o el mismo producto si no hay nada que
    resolver.
    """
    cambios: dict = {}

    if producto.tabla_tasas:
        aforo = escenario.aforo
        for plazo_max, aforo_max, tasa in producto.tabla_tasas:
            if plazo <= plazo_max and aforo <= aforo_max:
                cambios["tasa_anual"] = tasa
                break

    if producto.tasa_variable is not None:
        tv = producto.tasa_variable
        tasa = (escenario.tiie if escenario.tiie is not None else TIIE_BASE) + tv.sobretasa
        if tv.techo is not None:
            tasa = min(tasa, tv.techo)
        if tv.piso is not None:
            tasa = max(tasa, tv.piso)
        cambios["tasas_escalonadas"] = ((tv.desde_mes, tasa),)
        cambios["recalcular_pago_al_cambiar_tasa"] = True

    if producto.tarifa_avaluo:
        valor = escenario.valor_vivienda
        tramo = None
        for desde, fijo, al_millar in producto.tarifa_avaluo:
            if valor >= desde:
                tramo = (fijo, al_millar)
        if tramo is not None:
            fijo, al_millar = tramo
            cambios["avaluo"] = (fijo + valor / Decimal(1000) * al_millar) * producto.avaluo_factor_iva

    return replace(producto, **cambios) if cambios else producto


def evaluar_producto(
    escenario: Escenario,
    producto: ProductoHipotecario,
    fecha_primer_pago: Optional[date] = None,
    momento: Optional[date] = None,
) -> ResultadoOpcion:
    """Evalúa un escenario contra un producto y devuelve el resultado completo."""

    cofi = escenario.cofinanciamiento
    if cofi is not None and not producto.requiere_cofinanciamiento and not _acepta(producto, cofi):
        # Ruta alternativa: la misma vivienda sin usar al instituto.
        resultado = evaluar_producto(
            replace(escenario, cofinanciamiento=None), producto, fecha_primer_pago, momento
        )
        aviso = (
            f"Alternativa sin cofinanciamiento: el producto no acepta "
            f"{cofi.instituto.value.upper()}. No usa la subcuenta ni el crédito del "
            f"instituto: el banco financia ${resultado.monto_credito:,.0f} y no hay "
            "aportaciones patronales."
        )
        return replace(
            resultado,
            advertencias=resultado.advertencias + (aviso,),
            alternativa_sin_cofinanciamiento=True,
        )

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

    if (
        producto.valor_minimo_inmueble is not None
        and escenario.valor_vivienda < producto.valor_minimo_inmueble
    ):
        motivos.append(
            f"El valor del inmueble está por debajo del mínimo del producto "
            f"(${producto.valor_minimo_inmueble:,.0f})."
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

    producto = resolver_para_escenario(producto, escenario, plazo_calculo)

    cofinanciamiento = escenario.cofinanciamiento
    if cofinanciamiento is not None:
        if not _acepta(producto, cofinanciamiento):
            # Solo llega aquí un producto exclusivo de otro instituto
            motivos.append(
                "El producto no acepta cofinanciamiento con "
                f"{cofinanciamiento.instituto.value.upper()}."
            )
            cofinanciamiento = None
    elif producto.requiere_cofinanciamiento:
        instituto = producto.regla_aportaciones.instituto.value.upper() if producto.regla_aportaciones else ""
        motivos.append(
            f"Producto exclusivo para derechohabientes de {instituto}: "
            "requiere capturar el cofinanciamiento."
        )

    momento = momento or date.today()
    linea = LineaCredito(producto=producto, monto=monto, plazo_meses=plazo_calculo)
    fecha = (
        fecha_primer_pago
        or escenario.fecha_primer_pago
        or primer_pago_por_defecto(
            momento,
            producto.dia_de_pago,
            producto.dia_corte_primer_pago,
            producto.cortes_de_pago,
            producto.recorrer_primer_pago_un_mes,
        )
    )
    disposicion = escenario.fecha_disposicion or momento

    # Crédito del instituto (Cofinavit): las aportaciones lo pagan primero y
    # el banco las recibe solo después de liquidarlo (Ley INFONAVIT 43 Bis).
    if (
        producto.requiere_credito_instituto
        and cofinanciamiento is not None
        and cofinanciamiento.monto_credito_instituto <= 0
    ):
        motivos.append(
            "El producto requiere crédito del instituto (Cofinavit); con solo la "
            "subcuenta aplica Apoyo Infonavit."
        )

    if (
        producto.excluye_credito_instituto
        and cofinanciamiento is not None
        and cofinanciamiento.monto_credito_instituto > 0
    ):
        motivos.append(
            "El producto no admite crédito del instituto: con crédito Infonavit "
            "aplica Cofinavit."
        )
        cofinanciamiento = replace(cofinanciamiento, monto_credito_instituto=Decimal("0"))

    tabla_instituto = None
    linea_banco = linea
    if cofinanciamiento is not None and cofinanciamiento.monto_credito_instituto > 0:
        if cofinanciamiento.monto_credito_instituto > COFINAVIT.monto_maximo:
            motivos.append(
                f"El crédito {COFINAVIT.producto} excede el máximo del instituto "
                f"(${COFINAVIT.monto_maximo:,.2f}, 325 UMA)."
            )
        regla = producto.regla_aportaciones
        tabla_instituto = tabla_credito_instituto(
            cofinanciamiento.monto_credito_instituto,
            plazo_calculo,
            regla,
            cofinanciamiento.salario_mensual,
            fecha,
        )
        regla_banco = aportaciones_despues_de(regla, tabla_instituto.plazo_efectivo_meses)
        linea_banco = replace(linea, producto=replace(producto, regla_aportaciones=regla_banco))

    tabla = construir_tabla(
        linea_banco, escenario.valor_vivienda, fecha, cofinanciamiento, fecha_disposicion=disposicion
    )

    # El CAT de los cotizadores excluye las aportaciones y usa un primer
    # periodo regular: se calcula sobre esa tabla.
    tabla_cat = tabla
    if tabla.total_aportaciones or producto.primer_periodo_dias_reales:
        tabla_cat = construir_tabla(
            linea,
            escenario.valor_vivienda,
            fecha,
            fecha_disposicion=None if producto.primer_periodo_dias_reales else disposicion,
        )

    if producto.tasa_variable is not None:
        tv = producto.tasa_variable
        tiie = escenario.tiie if escenario.tiie is not None else TIIE_BASE
        advertencias.append(
            f"Tasa variable desde el mes {tv.desde_mes}: {tv.referencia} supuesta de "
            f"{tiie * 100:.2f} % + {tv.sobretasa * 100:.2f} = "
            f"{producto.tasas_escalonadas[0][1] * 100:.2f} %"
            + (f" (techo {tv.techo * 100:.2f} %)" if tv.techo is not None else "")
            + ". El costo depende de la TIIE futura."
        )

    if tabla_instituto is not None:
        advertencias.append(
            f"Incluye el crédito {COFINAVIT.producto} de INFONAVIT por "
            f"${cofinanciamiento.monto_credito_instituto:,.0f} a "
            f"{COFINAVIT.tasa_anual * 100:.2f} %: pago de "
            f"${tabla_instituto.primer_pago:,.2f} por nómina, liquidado en "
            f"{tabla_instituto.plazo_efectivo_meses} meses con las aportaciones. "
            "Supuesto: pago fijo tipo anualidad; el instituto no publica su fórmula."
        )

    total_aportaciones = tabla.total_aportaciones + (
        tabla_instituto.total_aportaciones if tabla_instituto is not None else 0
    )
    if total_aportaciones:
        destino = (
            "primero pagan el crédito del instituto y luego se abonan a capital del banco"
            if tabla_instituto is not None
            else "se abonan a capital"
        )
        advertencias.append(
            f"Incluye ${total_aportaciones:,.0f} de aportaciones patronales de "
            f"{cofinanciamiento.instituto.value.upper()}: {destino}; el crédito bancario "
            f"se liquida en {tabla.plazo_efectivo_meses} meses. El CAT no las considera."
        )

    if tabla.amortizacion_negativa:
        motivos.append(
            "Con este plazo el pago inicial no cubre los intereses y el saldo "
            f"crecería hasta ${tabla.saldo_maximo:,.0f} antes de bajar "
            "(amortización negativa). Un plazo menor lo resolvería."
        )

    comision = redondear(producto.comision_apertura_para(monto))
    cat = calcular_cat(tabla_cat, producto)

    # --- Capacidad de pago -------------------------------------------------
    if escenario.ingreso_mensual:
        tope = escenario.ingreso_mensual * escenario.factor_pago_ingreso
        # Con crédito del instituto, la capacidad se mide con ambos pagos
        pago_inicial = tabla.primer_pago + (
            tabla_instituto.primer_pago if tabla_instituto is not None else 0
        )
        if pago_inicial > tope:
            motivos.append(
                f"El pago inicial (${pago_inicial:,.2f}) supera el "
                f"{escenario.factor_pago_ingreso:.0%} del ingreso comprobable "
                f"(${tope:,.2f})."
            )
        elif pago_inicial > tope * Decimal("0.85"):
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
        tabla_instituto=tabla_instituto,
    )


def primer_pago_por_defecto(
    momento: date,
    dia_de_pago: Optional[int] = None,
    dia_corte: Optional[int] = None,
    cortes: tuple = (),
    recorrer_un_mes: bool = False,
) -> date:
    """
    Día 1 del mes siguiente. Con `dia_de_pago`: ese día del mes siguiente
    (fin de mes + días), recorrido 30 días si `momento` cae en `dia_corte` o
    después.
    """
    if cortes:
        primero, segundo = cortes
        corte = primero if primero <= momento.day < segundo else segundo
        if momento.day > corte:
            return date(momento.year + (momento.month == 12), momento.month % 12 + 1, corte)
        return date(momento.year, momento.month, corte)
    if dia_de_pago is None:
        if momento.month == 12:
            return date(momento.year + 1, 1, 1)
        return date(momento.year, momento.month + 1, 1)
    siguiente = date(momento.year + (momento.month == 12), momento.month % 12 + 1, 1)
    fecha = siguiente - timedelta(days=1) + timedelta(days=dia_de_pago)
    if dia_corte is not None and momento.day >= dia_corte:
        if recorrer_un_mes:
            return date(fecha.year + (fecha.month == 12), fecha.month % 12 + 1, fecha.day)
        fecha += timedelta(days=30)
    return fecha


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

    # Sin fecha capturada, el primer pago y la disposición se derivan de la
    # fecha de la comparación; el snapshot guarda `generado_en`, así que el
    # cálculo es reproducible.
    opciones = tuple(evaluar_producto(escenario, p, momento=momento) for p in vigentes)

    snapshot = Snapshot(
        generado_en=momento,
        escenario=escenario,
        productos=tuple(vigentes),
        version_motor=VERSION_MOTOR,
        asesor_id=asesor_id,
        organizacion_id=organizacion_id,
    )

    return Comparacion(escenario=escenario, opciones=opciones, snapshot=snapshot)
