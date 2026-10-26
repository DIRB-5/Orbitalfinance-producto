"""
Comparación de un mismo escenario contra varias instituciones.

Este módulo es el que produce el objeto que consume la presentación. No
imprime, no formatea, no sabe qué es un PDF: devuelve datos.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from .amortizacion import TablaAmortizacion, construir_tabla, redondear
from .cat import calcular_cat
from .instituto import COFINAVIT, aportaciones_despues_de, tabla_credito_instituto
from .referencias import TIIE_BASE
from .modelos import (
    BaseTopeGastos,
    ConceptoIVA,
    CreditoActual,
    CreditoInstitutoActual,
    Destino,
    Dinero,
    Escenario,
    LineaCredito,
    ProductoHipotecario,
    Snapshot,
)

VERSION_MOTOR = "0.1.0"

# Destinos en que el cliente compra y paga enganche. En sustitución y liquidez
# el inmueble ya es suyo: la diferencia contra el crédito es patrimonio que no
# sale de su bolsillo.
DESTINOS_CON_ENGANCHE = (Destino.ADQUISICION, Destino.TERRENO)


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
    def comision_investigacion(self) -> Dinero:
        return self.producto.comision_investigacion

    @property
    def dictamen_tecnico(self) -> Dinero:
        return self.producto.dictamen_tecnico_para(self.monto_credito)

    @property
    def gastos_de_contado(self) -> Dinero:
        """Gastos notariales que el cliente paga el día de la firma."""
        return max(Decimal("0"), self.gastos_notariales - self.gastos_financiados)

    @property
    def originacion_financiada(self) -> Dinero:
        """Avalúo y apertura que van en el crédito (Afirme Tu Casa 2)."""
        return max(Decimal("0"), self.gastos_financiados - self.gastos_notariales)

    @property
    def _gastos_iniciales_de_contado(self) -> Dinero:
        """Apertura, avalúo, notaría e investigación menos lo financiado."""
        return (
            self.comision_apertura + self.avaluo + self.gastos_notariales
            + self.comision_investigacion + self.dictamen_tecnico - self.gastos_financiados
        )

    @property
    def desembolso_inicial(self) -> Dinero:
        """Lo que el cliente saca de su bolsillo el día de la firma."""
        return self.enganche + self._gastos_iniciales_de_contado

    enganche: Dinero = Decimal("0")

    # Parte de los gastos notariales que el banco sumó al crédito. Ya está en
    # `monto_credito` y se paga con la tabla: no se vuelve a sumar al costo.
    gastos_financiados: Dinero = Decimal("0")

    # Presupuesto de obra incluido en `monto_credito` (Credirenovación modo 2)
    remodelacion_financiada: Dinero = Decimal("0")

    # Segundo crédito con los gastos (Santander) y su CAT, si lo hay. Sus
    # pagos se suman a la mensualidad y su costo al costo total.
    tabla_gastos: Optional[TablaAmortizacion] = None
    cat_gastos_estimado: Optional[Decimal] = None

    # Crédito del instituto refinanciado en una línea aparte (Santander Mejoras
    # Cofis). Como la de gastos: suma a la mensualidad y al costo total.
    tabla_instituto_refinanciado: Optional[TablaAmortizacion] = None
    cat_instituto_refinanciado_estimado: Optional[Decimal] = None

    @property
    def _lineas_adicionales(self) -> tuple:
        return tuple(
            t for t in (self.tabla_gastos, self.tabla_instituto_refinanciado) if t is not None
        )

    def _pago_actual(self, mes: int) -> Dinero:
        """Lo que hoy paga el cliente en `mes`: el bancario y, si este producto lo
        refinancia, el del instituto (cada uno mientras dure su plazo)."""
        actual = self.credito_actual
        pago = actual.pago_mensual if mes <= actual.plazo_remanente_meses else Decimal("0")
        instituto = actual.credito_instituto
        if self.tabla_instituto_refinanciado is not None and instituto is not None:
            if mes <= instituto.plazo_remanente_meses:
                pago += instituto.pago_mensual
        return pago

    # True si el escenario traía cofinanciamiento que este producto no acepta
    # y se evaluó como la ruta sin instituto (mismo enganche propio, el banco
    # financia también lo que cubriría el instituto).
    alternativa_sin_cofinanciamiento: bool = False

    # Crédito del instituto en cofinanciamiento (Cofinavit), si lo hay. Las
    # aportaciones lo pagan primero; después van al crédito bancario.
    tabla_instituto: Optional[TablaAmortizacion] = None

    # Hipoteca actual del cliente, en una sustitución.
    credito_actual: Optional[CreditoActual] = None

    # --- Sustitución: contra quedarse con el crédito actual -----------------

    @property
    def costo_de_cambiarse(self) -> Optional[Dinero]:
        """Lo que cuesta cambiarse hoy: apertura, avalúo, notaría y penalización."""
        if self.credito_actual is None:
            return None
        return self._gastos_iniciales_de_contado + self.credito_actual.penalizacion_prepago

    @property
    def ahorro_mensual(self) -> Optional[Dinero]:
        if self.credito_actual is None:
            return None
        return self._pago_actual(1) - self.pago_regular_inicial

    @property
    def serie_ahorro(self) -> tuple:
        """Ahorro acumulado mes a mes contra quedarse, partiendo del costo de cambiarse."""
        if self.credito_actual is None:
            return ()
        actual = self.credito_actual
        renglones = self.tabla.renglones
        acumulado = -self.costo_de_cambiarse
        serie = []
        meses = [actual.plazo_remanente_meses, len(renglones)]
        if actual.credito_instituto is not None:
            meses.append(actual.credito_instituto.plazo_remanente_meses)
        meses += [len(t.renglones) for t in self._lineas_adicionales]
        for mes in range(1, max(meses) + 1):
            pago_actual = self._pago_actual(mes)
            pago_nuevo = renglones[mes - 1].pago_total if mes <= len(renglones) else 0
            for t in self._lineas_adicionales:
                if mes <= len(t.renglones):
                    pago_nuevo += t.renglones[mes - 1].pago_total
            acumulado += pago_actual - pago_nuevo
            serie.append(acumulado)
        return tuple(serie)

    @property
    def punto_equilibrio_mes(self) -> Optional[int]:
        """Mes en que el ahorro acumulado cubre el costo de cambiarse."""
        for mes, acumulado in enumerate(self.serie_ahorro, start=1):
            if acumulado >= 0:
                return mes
        return None

    @property
    def ahorro_neto(self) -> Optional[Dinero]:
        serie = self.serie_ahorro
        return serie[-1] if serie else None

    def _con_gastos(self, atributo: str) -> Dinero:
        """Pago del crédito principal más el de las líneas adicionales."""
        pago = getattr(self.tabla, atributo)
        for t in self._lineas_adicionales:
            pago += getattr(t, atributo)
        return pago

    @property
    def pago_primer_mes(self) -> Dinero:
        return self._con_gastos("primer_pago")

    @property
    def pago_ultimo_mes(self) -> Dinero:
        return self._con_gastos("ultimo_pago")

    @property
    def pago_regular_inicial(self) -> Dinero:
        return self._con_gastos("pago_regular_inicial")

    @property
    def pago_regular_final(self) -> Dinero:
        return self._con_gastos("pago_regular_final")

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
        pagado_gastos = sum((t.total_pagado for t in self._lineas_adicionales), Decimal("0"))
        return (
            self.tabla.total_pagado
            + pagado_instituto
            + pagado_gastos
            + self.total_aportaciones
            + self._gastos_iniciales_de_contado
        )

    @property
    def costo_financiero(self) -> Dinero:
        """
        Costo total menos el capital del crédito sin gastos financiados. Lo que
        'cuesta' el crédito, con la notaría incluida en todas las opciones, se
        pague de contado, en el crédito o en una línea aparte.
        """
        capital = self.monto_credito
        if self.tabla_gastos is None:
            capital -= self.gastos_financiados
        if self.tabla_instituto_refinanciado is not None:
            capital += self.tabla_instituto_refinanciado.monto
        return self.costo_total - capital


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


def _normalizado(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_acentos.lower().split())


def credito_actual_es_propio(escenario: Escenario, producto: ProductoHipotecario) -> Optional[bool]:
    """
    ¿La hipoteca actual ya es del banco del producto? None si no se capturó la
    institución. Compara sin mayúsculas ni acentos y acepta nombres largos
    ("Banco Santander México" es Santander).
    """
    actual = escenario.credito_actual
    if actual is None or not actual.institucion.strip():
        return None
    return _normalizado(producto.institucion) in _normalizado(actual.institucion)


def credito_instituto_refinanciado(
    escenario: Escenario, producto: ProductoHipotecario
) -> Optional[CreditoInstitutoActual]:
    """El crédito del instituto que este producto refinancia, si lo hay."""
    actual = escenario.credito_actual
    if producto.refinanciamiento_instituto is None or actual is None:
        return None
    return actual.credito_instituto


def obra_financiada(escenario: Escenario, producto: ProductoHipotecario) -> Dinero:
    """Presupuesto de obra que el producto suma al crédito (Credirenovación)."""
    return escenario.monto_remodelacion if producto.financia_remodelacion else Decimal("0")


def valor_proyectado(escenario: Escenario, producto: ProductoHipotecario) -> Dinero:
    """Valor de la vivienda con la obra que financia el producto: base del
    avalúo y del seguro de daños ('Simulador Valora'!C30 = C28 + C29)."""
    return escenario.valor_vivienda + obra_financiada(escenario, producto)


def valor_garantia(escenario: Escenario, producto: ProductoHipotecario) -> Dinero:
    """Valor sobre el que se mide el aforo: la vivienda (con la obra que se
    financia), más el inmueble adicional en garantía si el producto lo acepta
    (Afirme Tu Casa 2)."""
    valor = valor_proyectado(escenario, producto)
    if producto.acepta_garantia_adicional:
        return valor + escenario.valor_garantia_adicional
    return valor


def _avaluo_por_tarifa(producto: ProductoHipotecario, valor: Dinero) -> Optional[Dinero]:
    tramo = None
    for desde, fijo, al_millar in producto.tarifa_avaluo:
        if valor >= desde:
            tramo = (fijo, al_millar)
    if tramo is None:
        return None
    fijo, al_millar = tramo
    return (fijo + valor / Decimal(1000) * al_millar) * producto.avaluo_factor_iva


def resolver_para_escenario(
    producto: ProductoHipotecario,
    escenario: Escenario,
    plazo: int,
    aforo: Optional[Decimal] = None,
) -> ProductoHipotecario:
    """
    Condiciones que dependen del escenario: la tasa por plazo y aforo, y el
    avalúo por tabulador. Devuelve una copia con los valores resueltos (el
    snapshot queda reproducible) o el mismo producto si no hay nada que
    resolver. `aforo` sustituye al del escenario para elegir el tramo de tasa
    (con gastos financiados o garantía adicional).
    """
    cambios: dict = {}

    if producto.tabla_tasas:
        aforo = escenario.aforo if aforo is None else aforo
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
        avaluo = _avaluo_por_tarifa(producto, valor_proyectado(escenario, producto))
        if avaluo is not None:
            cambios["avaluo"] = avaluo
        if producto.acepta_garantia_adicional and escenario.valor_garantia_adicional > 0:
            # Un avalúo más, del inmueble adicional
            extra = _avaluo_por_tarifa(producto, escenario.valor_garantia_adicional) or Decimal("0")
            cambios["avaluo"] = cambios.get("avaluo", producto.avaluo) + extra

    return replace(producto, **cambios) if cambios else producto


def gastos_financiables(escenario: Escenario, producto: ProductoHipotecario) -> Dinero:
    """
    Gastos notariales que el producto suma al crédito: el mínimo entre los
    gastos del escenario, su tope y lo que cabe en el aforo máximo. Cero si el
    escenario no pide financiarlos o el producto no lo permite.
    """
    regla = producto.financiamiento_gastos
    if regla is None or not escenario.financiar_gastos_notariales:
        return Decimal("0")
    instituto = credito_instituto_refinanciado(escenario, producto)
    # Santander Mejoras Cofis: el 7 % y el aforo sobre los dos créditos (Cal!C44)
    base = (
        escenario.monto_credito + obra_financiada(escenario, producto)
        + (instituto.saldo if instituto else Decimal("0"))
    )
    financiado = escenario.gastos_notariales
    if regla.incluye_apertura_y_avaluo:
        # Notariales, avalúo y la apertura sobre el total. Con apertura en
        # porcentaje simple: total = (base + notariales + avalúo) / (1 − c).
        fijos = financiado + producto.avaluo
        c = producto.comision_apertura
        if producto.comision_apertura_monto is None and producto.comision_apertura_tope is None:
            financiado = (base + fijos) / (Decimal(1) - c) - base
        else:
            financiado = fijos + producto.comision_apertura_para(base + fijos)
    holgura = producto.aforo_max * valor_garantia(escenario, producto) - base
    if regla.tope is not None:
        sobre = escenario.valor_vivienda if regla.base_tope is BaseTopeGastos.VALOR_INMUEBLE else base
        if regla.excede_aforo_cancela and regla.tope * sobre > holgura:
            return Decimal("0")
        financiado = min(financiado, regla.tope * sobre)
    return max(Decimal("0"), min(financiado, holgura))


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

    obra = obra_financiada(escenario, producto)
    monto_base = escenario.monto_credito + obra
    plazo = escenario.plazo_meses
    valor_tabla = valor_proyectado(escenario, producto)
    valor_en_garantia = valor_garantia(escenario, producto)
    refinanciado = credito_instituto_refinanciado(escenario, producto)
    saldo_instituto = refinanciado.saldo if refinanciado else Decimal("0")
    aforo_base = (
        (monto_base + saldo_instituto) / valor_en_garantia if valor_en_garantia else Decimal("0")
    )

    motivos: list[str] = []
    advertencias: list[str] = []

    # Se calcula aunque no sea elegible: el asesor necesita poder mostrarle al
    # cliente cuánto enganche adicional le abriría esta opción.
    plazo_calculo = plazo if plazo in producto.plazos_meses else max(
        (p for p in producto.plazos_meses if p <= plazo),
        default=min(producto.plazos_meses),
    )

    # --- Gastos notariales financiados --------------------------------------
    # Con el avalúo del escenario ya resuelto (Tu Casa 2 también lo financia)
    financiado = gastos_financiables(
        escenario, resolver_para_escenario(producto, escenario, plazo_calculo)
    )
    regla_gastos = producto.financiamiento_gastos
    linea_separada = regla_gastos is not None and regla_gastos.linea_separada
    monto = monto_base + (Decimal("0") if linea_separada else financiado)
    sobre_total = regla_gastos is not None and regla_gastos.apertura_y_aforo_sobre_total
    if financiado:
        conceptos = (
            "gastos notariales, avalúo y comisión por apertura"
            if regla_gastos.incluye_apertura_y_avaluo else "gastos notariales"
        )
        advertencias.append(
            f"El banco financia ${financiado:,.2f} de {conceptos} en un segundo crédito "
            "con la misma tasa y plazo, seguro de vida e IVA sobre intereses; la "
            "mensualidad mostrada suma ambos."
            if linea_separada else
            f"El banco financia ${financiado:,.2f} de {conceptos}: se suman al "
            "crédito y generan intereses y seguro de vida."
        )
    if escenario.financiar_gastos_notariales and financiado < escenario.gastos_notariales:
        advertencias.append(
            f"Se pagan de contado ${escenario.gastos_notariales - financiado:,.2f} de "
            "gastos notariales: "
            + ("el producto no los financia." if regla_gastos is None
               else "es lo que excede su tope de financiamiento o su aforo máximo.")
        )
    if producto.acepta_garantia_adicional and escenario.valor_garantia_adicional > 0:
        advertencias.append(
            f"El aforo se mide sobre la vivienda más el inmueble adicional en garantía "
            f"(${escenario.valor_garantia_adicional:,.0f}): ambos quedan hipotecados."
        )

    # --- Reglas de elegibilidad -------------------------------------------
    if aforo_base > producto.aforo_max:
        motivos.append(
            f"El aforo solicitado ({aforo_base:.1%}) supera el máximo del "
            f"producto ({producto.aforo_max:.1%}). "
            + ("Se requiere más enganche." if escenario.destino in DESTINOS_CON_ENGANCHE
               else "El monto pedido excede lo que presta sobre el valor del inmueble.")
        )

    if producto.requiere_garantia_o_gastos_financiados and not (
        escenario.financiar_gastos_notariales or escenario.valor_garantia_adicional > 0
    ):
        motivos.append(
            "El producto sirve para dejar un inmueble adicional en garantía o financiar "
            "los gastos; sin eso aplica el crédito de adquisición del mismo banco."
        )

    propio = credito_actual_es_propio(escenario, producto)
    if producto.solo_credito_actual_propio and not propio:
        motivos.append(
            f"Solo mejora hipotecas que ya son de {producto.institucion}"
            + (": captura la institución del crédito actual." if propio is None
               else "; para traer una de otro banco aplica su producto de sustitución.")
        )
    if producto.excluye_credito_actual_propio and propio:
        motivos.append(
            f"La hipoteca actual ya es de {producto.institucion}: aplica su Mejora de "
            "Condiciones, no la sustitución."
        )

    if escenario.monto_remodelacion > 0 and not producto.financia_remodelacion:
        motivos.append(
            f"El producto no financia remodelación: el presupuesto de obra "
            f"(${escenario.monto_remodelacion:,.0f}) quedaría fuera del crédito."
        )
    if producto.financia_remodelacion and escenario.monto_remodelacion <= 0:
        motivos.append(
            "El producto es para compra con remodelación: captura el presupuesto de obra."
        )

    if plazo not in producto.plazos_meses:
        motivos.append(
            f"El plazo de {plazo} meses no está disponible. "
            f"Plazos ofrecidos: {', '.join(str(p) for p in producto.plazos_meses)}."
        )

    if producto.monto_minimo is not None and monto_base < producto.monto_minimo:
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
    # Banamex, BX+ y Afirme eligen el tramo de tasa con el aforo que incluye
    # los gastos; Scotiabank, sin ellos.
    aforo_tasa = (
        ((monto if sobre_total else monto_base) + saldo_instituto) / valor_en_garantia
        if valor_en_garantia else None
    )
    producto = resolver_para_escenario(producto, escenario, plazo_calculo, aforo=aforo_tasa)

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
        linea_banco, valor_tabla, fecha, cofinanciamiento, fecha_disposicion=disposicion
    )

    # El CAT de los cotizadores excluye las aportaciones y usa un primer
    # periodo regular: se calcula sobre esa tabla.
    tabla_cat = tabla
    if tabla.total_aportaciones or producto.primer_periodo_dias_reales:
        tabla_cat = construir_tabla(
            linea,
            valor_tabla,
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

    monto_comision = monto if (sobre_total or not financiado) else monto_base

    # Línea de gastos aparte (Santander): sin daños, comisiones ni avalúo
    tabla_gastos = None
    cat_gastos = None
    if linea_separada and financiado:
        producto_gastos = replace(
            producto,
            comision_mensual=Decimal("0"),
            seguro_danos_anual=Decimal("0"),
            seguro_danos_monto_mensual=None,
            seguro_desempleo_pct=Decimal("0"),
            avaluo=Decimal("0"),
            tarifa_avaluo=(),
            comision_apertura=Decimal("0"),
            comision_apertura_monto=None,
            comision_investigacion=Decimal("0"),
            dictamen_tecnico_pct=Decimal("0"),
            iva_sobre_intereses=True,
            iva_intereses_en_cat=False,
            financiamiento_gastos=None,
        )
        tabla_gastos = construir_tabla(
            LineaCredito(producto=producto_gastos, monto=financiado, plazo_meses=plazo_calculo),
            valor_tabla, fecha, fecha_disposicion=disposicion,
        )
        cat_gastos = calcular_cat(tabla_gastos, producto_gastos)

    # Crédito del instituto refinanciado (Santander Mejoras Cofis): vida y
    # comisión mensual (÷ 1.16 en el CAT, CAT!BB), sin daños ni IVA de intereses
    tabla_refinanciada = None
    cat_refinanciado = None
    if refinanciado is not None:
        producto_instituto = replace(
            producto,
            comision_mensual=producto.refinanciamiento_instituto.comision_mensual,
            seguro_danos_anual=Decimal("0"),
            seguro_danos_monto_mensual=None,
            seguro_desempleo_pct=Decimal("0"),
            avaluo=Decimal("0"),
            tarifa_avaluo=(),
            comision_apertura=Decimal("0"),
            comision_apertura_monto=None,
            comision_investigacion=Decimal("0"),
            dictamen_tecnico_pct=Decimal("0"),
            iva_sobre_intereses=False,
            iva_intereses_en_cat=False,
            financiamiento_gastos=None,
            refinanciamiento_instituto=None,
            cat_netos_de_iva=frozenset({ConceptoIVA.COMISION_MENSUAL}),
        )
        tabla_refinanciada = construir_tabla(
            LineaCredito(producto=producto_instituto, monto=refinanciado.saldo, plazo_meses=plazo_calculo),
            valor_tabla, fecha, fecha_disposicion=disposicion,
        )
        cat_refinanciado = calcular_cat(tabla_refinanciada, producto_instituto)
        advertencias.append(
            f"Refinancia también el crédito {refinanciado.instituto.value.upper()} "
            f"(${refinanciado.saldo:,.2f}) en un tercer crédito con la misma tasa y plazo. "
            "Al salir del instituto, las aportaciones patronales dejan de pagar ese "
            "crédito y vuelven a la subcuenta de vivienda."
        )
    comision = redondear(producto.comision_apertura_para(monto_comision))
    cat = calcular_cat(tabla_cat, producto, monto_comision=monto_comision)

    # --- Capacidad de pago -------------------------------------------------
    if escenario.ingreso_mensual:
        tope = escenario.ingreso_mensual * escenario.factor_pago_ingreso
        # Con el pago regular (no un primer mes irregular) y, con crédito del
        # instituto, con ambos pagos.
        pago_inicial = tabla.pago_regular_inicial + (
            tabla_instituto.pago_regular_inicial if tabla_instituto is not None else 0
        ) + (tabla_gastos.pago_regular_inicial if tabla_gastos is not None else 0) + (
            tabla_refinanciada.pago_regular_inicial if tabla_refinanciada is not None else 0
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
        enganche=escenario.enganche if escenario.destino in DESTINOS_CON_ENGANCHE else Decimal("0"),
        gastos_financiados=financiado,
        remodelacion_financiada=obra,
        tabla_gastos=tabla_gastos,
        cat_gastos_estimado=cat_gastos,
        tabla_instituto_refinanciado=tabla_refinanciada,
        cat_instituto_refinanciado_estimado=cat_refinanciado,
        tabla_instituto=tabla_instituto,
        credito_actual=escenario.credito_actual,
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
    # Solo productos del destino del escenario (adquisición, sustitución, ...)
    del_destino = [p for p in vigentes if p.destino is escenario.destino]
    opciones = tuple(evaluar_producto(escenario, p, momento=momento) for p in del_destino)

    snapshot = Snapshot(
        generado_en=momento,
        escenario=escenario,
        productos=tuple(vigentes),
        version_motor=VERSION_MOTOR,
        asesor_id=asesor_id,
        organizacion_id=organizacion_id,
    )

    return Comparacion(escenario=escenario, opciones=opciones, snapshot=snapshot)
