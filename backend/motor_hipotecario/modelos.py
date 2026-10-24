"""
Modelos de dominio del motor hipotecario.

Decisiones de diseño relevantes:

1. Todo el dinero se maneja con Decimal, nunca float. Los errores de punto
   flotante en tablas de amortización de 240 renglones se acumulan y producen
   saldos finales distintos de cero.

2. ProductoHipotecario es inmutable y tiene vigencia. El catálogo nunca se
   edita en sitio: se cierra la vigencia del producto anterior y se crea uno
   nuevo. Esto permite reproducir exactamente una presentación entregada hace
   seis meses.

3. Escenario contiene una LISTA de líneas de crédito aunque la v1 siempre use
   exactamente una. Cuando entre cofinanciamiento INFONAVIT / FOVISSSTE se
   agrega un elemento a la lista, no se reescribe el motor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import FrozenSet, Optional, Tuple

# Alias semántico. Las tasas se expresan como fracción: 0.1085 == 10.85 %
Tasa = Decimal
Dinero = Decimal


class BaseSeguroDanos(str, Enum):
    """Sobre qué valor cobra el banco el seguro de daños."""

    VALOR_TOTAL = "valor_total"
    VALOR_CONSTRUCCION = "valor_construccion"


class ConvencionDias(str, Enum):
    """
    Cómo convierte la institución la tasa anual en tasa del periodo mensual.

    Con la misma tasa nominal producen costos distintos: 10.85 % en base 360
    cuesta lo mismo que ~11.00 % en base /12. Ver docs/validacion_modelos.md.
    """

    TASA_ENTRE_12 = "tasa/12"                  # HSBC, Banamex, BX
    DIAS_30_4166_360 = "tasa*30.4166/360"      # Santander (interés)
    DIAS_30_4_360 = "tasa*30.4/360"            # Banorte
    DIAS_365_12_360 = "(tasa/360)*(365/12)"    # Santander (pago)
    # Días del mes de cada pago / 360 (Scotiabank, Banregio, Afirme). Necesita
    # fechas de pago y solo aplica al interés cobrado: el pago fijo requiere
    # una tasa por periodo única.
    DIAS_REALES_360 = "tasa*dias_reales/360"


class ConceptoIVA(str, Enum):
    """
    Conceptos que causan IVA y que una institución puede meter al flujo del
    CAT netos (÷ 1.16). Capital, interés y seguro de vida entran siempre
    completos. Ver CLAUDE.md, corrección 4: el criterio correcto está
    pendiente con riesgo, por eso es parámetro del producto.
    """

    COMISION_APERTURA = "comision_apertura"
    AVALUO = "avaluo"
    SEGURO_DANOS = "seguro_danos"
    COMISION_MENSUAL = "comision_mensual"


class TipoLinea(str, Enum):
    BANCARIO = "bancario"
    INFONAVIT = "infonavit"
    FOVISSSTE = "fovissste"


class AportacionExcedente(str, Enum):
    """Qué hace el banco si una aportación excede el saldo pendiente."""

    OMITIR = "omitir"    # BX+: no la aplica
    LIMITAR = "limitar"  # Banorte: aplica solo lo que falta para liquidar


@dataclass(frozen=True)
class ReglaAportaciones:
    """
    Cómo aplica un producto bancario de cofinanciamiento las aportaciones
    patronales del instituto: abonos a capital que acortan el plazo, sin
    cambiar el pago del cliente.

    Monto de cada abono = min(porcentaje × salario, tope), creciendo
    `incremento_anual` en cada aniversario (el tope aplica al primer año).
    Se abona en los meses mes_inicio, mes_inicio + cada_meses, ...

    Referencias (solo fórmulas: ningún cotizador trae un escenario con
    aportaciones capturadas):
      BX+ INFONAVIT     10 % del salario, tope 7,884.24, +3 % anual, OMITIR
      Banorte FOVISSSTE 10 % (5 % × 2 meses), sin tope, sin incremento
      Banorte Apoyo     10 %, tope 8,598.64 (UMA), sin incremento
    """

    instituto: "TipoLinea"
    porcentaje_salario: Decimal
    tope: Optional[Decimal] = None
    incremento_anual: Decimal = Decimal("0")
    mes_inicio: int = 4
    cada_meses: int = 2
    excedente: AportacionExcedente = AportacionExcedente.LIMITAR


@dataclass(frozen=True)
class Cofinanciamiento:
    """
    Lo que el instituto aporta al escenario del cliente. El crédito del
    instituto y el saldo de la subcuenta reducen el crédito bancario (como en
    los cotizadores, no se modelan como una línea con tabla propia); el
    salario es la base de las aportaciones patronales.
    """

    instituto: "TipoLinea"
    salario_mensual: Decimal
    monto_credito_instituto: Decimal = Decimal("0")
    saldo_subcuenta: Decimal = Decimal("0")


@dataclass(frozen=True)
class ProductoHipotecario:
    """
    Condiciones de un producto de crédito hipotecario en un periodo de vigencia.

    IMPORTANTE: los valores de tasa, comisión y seguros son los parámetros
    publicados o negociados. El motor no los inventa ni los estima.
    """

    id: str
    institucion: str
    nombre: str

    # Tasa de interés anual fija, como fracción (0.1085 == 10.85 %)
    tasa_anual: Tasa

    # Plazos ofrecidos en meses
    plazos_meses: tuple[int, ...]

    # Aforo máximo (LTV). 0.90 significa que financia hasta el 90 % del valor
    aforo_max: Decimal

    # Convención con que se calcula el interés de cada mes
    convencion_interes: ConvencionDias = ConvencionDias.TASA_ENTRE_12

    # Convención con que se calcula el pago fijo. None = la misma del interés.
    # Santander usa una distinta para cada cosa.
    convencion_pago: Optional[ConvencionDias] = None

    # Convención del interés que se descuenta del pago para obtener el capital
    # amortizado. None = el interés cobrado. Banregio cobra con días reales
    # pero amortiza con tasa/12, así que su pago total varía con el calendario.
    convencion_amortizacion: Optional[ConvencionDias] = None

    # True si los seguros van dentro del pago fijo: el pago se calcula con la
    # tasa del seguro de vida sumada a la del periodo, más el seguro de daños,
    # y el capital es lo que queda después de seguros e interés (Banregio).
    seguros_en_pago_fijo: bool = False

    # Primer periodo irregular (Banorte): el mes 1 cobra interés por los días
    # reales desde la disposición hasta el primer pago, inclusive, y prorratea
    # el seguro de vida a días/30. El capital del mes 1 sigue siendo el del
    # pago regular. El CAT se calcula sobre la tabla regular.
    primer_periodo_dias_reales: bool = False

    # Día del mes en que se paga. None = día 1 del mes siguiente a la
    # comparación. Con día de pago, el primer pago es ese día del mes
    # siguiente; si la disposición cae en `dia_corte_primer_pago` o después,
    # se recorre 30 días (Banorte: día 3, corte 30; Fecha Pago!K4).
    dia_de_pago: Optional[int] = None
    dia_corte_primer_pago: Optional[int] = None

    # Producto exclusivo de cofinanciamiento (p. ej. FOVISSSTE para todos):
    # sin cofinanciamiento del instituto de su regla, no es elegible.
    requiere_cofinanciamiento: bool = False

    # Además requiere crédito del instituto (Cofinavit); con solo subcuenta
    # el producto que aplica es otro (Apoyo Infonavit).
    requiere_credito_instituto: bool = False

    # No admite crédito del instituto (Apoyo Infonavit: solo subcuenta y
    # aportaciones); con crédito, el producto que aplica es Cofinavit.
    excluye_credito_instituto: bool = False

    # Mensualidad creciente: ((mes desde el que aplica, crecimiento mensual),
    # ...). El pago base (capital + interés) se multiplica por
    # (1 + crecimiento) cada mes. Al inicio de cada fase el pago se recalcula
    # sobre el saldo para liquidar en los meses restantes con ese ritmo. La
    # primera fase empieza en el mes 1. Vacío = pago fijo.
    # Validado contra Banregio TablAmoPagosCrec: ((1, 1/0.9989 − 1), (73, 0.0017)).
    crecimiento_pago_mensual: Tuple[Tuple[int, Decimal], ...] = ()

    # Tasa escalonada: ((mes desde el que aplica, tasa anual), ...). Antes del
    # primer escalón aplica `tasa_anual`. Vacío = tasa única.
    # Con `recalcular_pago_al_cambiar_tasa` en False el pago se calcula con la
    # tasa inicial y se mantiene: si la tasa baja, el crédito se liquida antes
    # del plazo (plazo efectivo menor). En True el pago se recalcula al cambiar
    # la tasa sobre el saldo y el plazo restante (Banamex, TablaCTH!S128).
    # SIN VALIDAR contra un cotizador.
    tasas_escalonadas: Tuple[Tuple[int, Decimal], ...] = ()
    recalcular_pago_al_cambiar_tasa: bool = False

    # Producto de cofinanciamiento: cómo abona las aportaciones patronales.
    # None = no acepta cofinanciamiento.
    regla_aportaciones: Optional[ReglaAportaciones] = None

    # Comisión por apertura como fracción del monto del crédito
    comision_apertura: Decimal = Decimal("0")

    # Comisión por apertura como monto fijo. Si se define, sustituye a la
    # fracción (hay instituciones que cobran una cantidad fija).
    comision_apertura_monto: Optional[Dinero] = None

    # Tope de la comisión por apertura cuando es fracción (BX+: $150,000).
    comision_apertura_tope: Optional[Dinero] = None

    # Comisión mensual fija: cargo recurrente que no es interés ni seguro.
    # Entra al pago, al costo total y al CAT.
    comision_mensual: Dinero = Decimal("0")

    # Seguro de vida: tasa MENSUAL aplicada sobre el saldo insoluto
    seguro_vida_mensual: Decimal = Decimal("0")

    # Seguro de daños: tasa ANUAL aplicada sobre el valor del inmueble
    seguro_danos_anual: Decimal = Decimal("0")
    base_seguro_danos: BaseSeguroDanos = BaseSeguroDanos.VALOR_TOTAL

    # Seguro de daños como monto mensual fijo. Si se define, sustituye a la
    # tasa: es lo que se conoce cuando el dato sale de un cotizador y no de la
    # tarifa de la aseguradora.
    seguro_danos_monto_mensual: Optional[Dinero] = None

    # Proporción del valor que se considera construcción, cuando aplica
    factor_construccion: Decimal = Decimal("0.70")

    # Avalúo cobrado por la institución (entra al CAT). Los gastos notariales
    # NO entran al CAT porque los cobra un tercero, pero sí al costo total.
    avaluo: Dinero = Decimal("0")

    # Conceptos que entran al flujo del CAT netos de IVA. Vacío = todo con IVA.
    # Solo afecta al CAT: el costo total siempre lleva lo que paga el cliente.
    cat_netos_de_iva: FrozenSet[ConceptoIVA] = frozenset()

    monto_minimo: Optional[Dinero] = None
    monto_maximo: Optional[Dinero] = None

    # Valor mínimo del inmueble que acepta la institución.
    valor_minimo_inmueble: Optional[Dinero] = None

    # Tasa según plazo y aforo: ((plazo máximo en meses, aforo máximo, tasa),
    # ...), ordenada de menor a mayor; aplica el primer renglón que cubre el
    # escenario. Si se define, `tasa_anual` es solo la referencia del
    # catálogo (la más alta) y el comparador usa la del escenario.
    tabla_tasas: Tuple[Tuple[int, Decimal, Decimal], ...] = ()

    # Tabulador de avalúo: ((valor desde, monto fijo, al millar), ...),
    # ordenado por valor. Avalúo = (fijo + valor / 1000 × al millar) ×
    # avaluo_factor_iva. Si se define, sustituye a `avaluo`.
    tarifa_avaluo: Tuple[Tuple[Decimal, Decimal, Decimal], ...] = ()
    avaluo_factor_iva: Decimal = Decimal("1")

    tipo: TipoLinea = TipoLinea.BANCARIO

    # Versionado
    vigente_desde: date = date(2000, 1, 1)
    vigente_hasta: Optional[date] = None

    # Trazabilidad: de dónde salió este dato y quién lo capturó
    fuente: str = ""
    notas: str = ""

    # Marca de condición negociada por una organización específica
    negociado_por: Optional[str] = None

    def vigente_en(self, momento: date) -> bool:
        if momento < self.vigente_desde:
            return False
        if self.vigente_hasta is not None and momento > self.vigente_hasta:
            return False
        return True

    def comision_apertura_para(self, monto: Dinero) -> Dinero:
        if self.comision_apertura_monto is not None:
            return self.comision_apertura_monto
        comision = self.comision_apertura * monto
        if self.comision_apertura_tope is not None:
            comision = min(comision, self.comision_apertura_tope)
        return comision

    @property
    def etiqueta(self) -> str:
        base = f"{self.institucion} — {self.nombre}"
        if self.negociado_por:
            return f"{base} (condición negociada)"
        return base


@dataclass(frozen=True)
class LineaCredito:
    """
    Una línea de crédito dentro de un escenario.

    En v1 siempre hay una. En cofinanciamiento habrá dos o tres con reglas
    distintas y el comparador simplemente suma sus flujos.
    """

    producto: ProductoHipotecario
    monto: Dinero
    plazo_meses: int


@dataclass
class Escenario:
    """
    El planteamiento del cliente final: qué vivienda, cuánto pone de enganche,
    a qué plazo. Es lo que el asesor captura una sola vez para comparar contra
    todas las instituciones.
    """

    valor_vivienda: Dinero
    enganche: Dinero
    plazo_meses: int

    # Gastos de escrituración y notariales estimados. No entran al CAT
    # (los cobra un tercero) pero sí al desembolso inicial del cliente.
    gastos_notariales: Dinero = Decimal("0")

    # Ingreso mensual comprobable, para evaluar capacidad de pago
    ingreso_mensual: Optional[Dinero] = None

    # Proporción máxima del ingreso que puede destinarse al pago
    factor_pago_ingreso: Decimal = Decimal("0.30")

    # Fecha del primer pago. Solo la usan los productos con días reales; si no
    # se captura, el comparador usa el día 1 del mes siguiente a la comparación.
    fecha_primer_pago: Optional[date] = None

    # Fecha de disposición del crédito. Solo la usan los productos con primer
    # periodo irregular; si no se captura, es la fecha de la comparación.
    fecha_disposicion: Optional[date] = None

    # Cofinanciamiento INFONAVIT / FOVISSSTE, si aplica.
    cofinanciamiento: Optional[Cofinanciamiento] = None

    etiqueta: str = ""
    notas: str = ""

    @property
    def monto_credito(self) -> Dinero:
        """Crédito bancario: lo que no cubren el enganche ni el instituto."""
        monto = self.valor_vivienda - self.enganche
        if self.cofinanciamiento:
            monto -= (
                self.cofinanciamiento.monto_credito_instituto
                + self.cofinanciamiento.saldo_subcuenta
            )
        return monto

    @property
    def aforo(self) -> Decimal:
        """LTV solicitado."""
        if self.valor_vivienda == 0:
            return Decimal("0")
        return self.monto_credito / self.valor_vivienda

    def validar(self) -> list[str]:
        errores: list[str] = []
        if self.valor_vivienda <= 0:
            errores.append("El valor de la vivienda debe ser mayor a cero.")
        if self.enganche < 0:
            errores.append("El enganche no puede ser negativo.")
        if self.enganche >= self.valor_vivienda:
            errores.append("El enganche no puede cubrir el valor total del inmueble.")
        if self.plazo_meses <= 0:
            errores.append("El plazo debe ser mayor a cero meses.")
        if (
            self.cofinanciamiento
            and self.cofinanciamiento.instituto is TipoLinea.FOVISSSTE
            and self.cofinanciamiento.monto_credito_instituto > 0
        ):
            errores.append(
                "FOVISSSTE no otorga crédito propio en cofinanciamiento con banca: "
                "FOVISSSTE para Todos solo usa la subcuenta."
            )
        if self.enganche < self.valor_vivienda and self.monto_credito <= 0:
            errores.append(
                "El enganche y el cofinanciamiento cubren el valor del inmueble: "
                "no queda crédito bancario."
            )
        return errores


@dataclass(frozen=True)
class Snapshot:
    """
    Congelamiento de los parámetros usados en una comparación entregada.

    Cuando el asesor genera la presentación, se guarda esto y NO una referencia
    viva al catálogo. Si el cliente reclama en agosto una propuesta de marzo,
    se reproduce el cálculo exacto.
    """

    generado_en: date
    escenario: Escenario
    productos: tuple[ProductoHipotecario, ...]
    version_motor: str
    asesor_id: str = ""
    organizacion_id: str = ""
