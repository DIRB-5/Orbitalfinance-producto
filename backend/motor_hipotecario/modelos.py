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
    # El mayor entre valor × factor_construccion y el saldo insoluto del mes
    # (Banamex: 0.0003 × MAX(80 % del valor, saldo)).
    MAXIMO_CONSTRUCCION_SALDO = "maximo_construccion_saldo"


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
    # Días entre fechas de pago consecutivas / 360; el primer periodo cuenta
    # desde la disposición, inclusive (Afirme). Sirve también para el pago:
    # la cuota se calcula con los factores de cada periodo.
    DIAS_ENTRE_PAGOS_360 = "tasa*dias_entre_pagos/360"


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
    SEGURO_DESEMPLEO = "seguro_desempleo"
    INVESTIGACION = "investigacion"


class RequisitoCliente(str, Enum):
    """
    Condición que una oferta exige del cliente y que el asesor marca en el
    escenario si la cumple. Sin marcarla, la oferta no es elegible: así una
    condición especial no gana un comparativo que el cliente no puede tomar.
    """

    VINCULACION_SCOTIABANK = "vinculacion_scotiabank"
    PREMIUM_SCOTIABANK = "premium_scotiabank"
    ECOTECNOLOGIAS = "ecotecnologias"


DESCRIPCION_REQUISITO = {
    RequisitoCliente.VINCULACION_SCOTIABANK: "Vinculación con Scotiabank (campaña Vinculación)",
    RequisitoCliente.PREMIUM_SCOTIABANK: "Cliente Scotiabank Premium o Wealth Management",
    RequisitoCliente.ECOTECNOLOGIAS: "Obra con ecotecnologías (Hipoteca Green)",
}


class Destino(str, Enum):
    """Para qué es el crédito. El comparador solo compara productos del mismo destino."""

    ADQUISICION = "adquisicion"
    SUSTITUCION = "sustitucion"   # liquidar una hipoteca con otro banco
    LIQUIDEZ = "liquidez"         # efectivo con la vivienda en garantía
    TERRENO = "terreno"
    REMODELACION = "remodelacion"  # obra en la vivienda propia, sin hipoteca


@dataclass(frozen=True)
class CreditoActual:
    """
    La hipoteca que el cliente ya tiene, para evaluar una sustitución. El pago
    mensual es el que hoy paga (con seguros y comisiones).
    """

    saldo_insoluto: Decimal
    pago_mensual: Decimal
    plazo_remanente_meses: int
    tasa_anual: Optional[Decimal] = None
    penalizacion_prepago: Decimal = Decimal("0")
    institucion: str = ""
    # Crédito INFONAVIT/FOVISSSTE del cofinanciamiento actual, si lo hay. Su
    # pago es el descuento por nómina que hoy hace el cliente.
    credito_instituto: Optional["CreditoInstitutoActual"] = None


class TipoLinea(str, Enum):
    BANCARIO = "bancario"
    INFONAVIT = "infonavit"
    FOVISSSTE = "fovissste"


@dataclass(frozen=True)
class CreditoInstitutoActual:
    """
    Crédito del instituto en una hipoteca de cofinanciamiento que el cliente ya
    tiene. Solo montos: no se pide NSS (regla 7). El saldo va en pesos; si el
    estado de cuenta viene en VSM o UMA, se convierte fuera del motor.
    """

    instituto: TipoLinea
    saldo: Dinero
    pago_mensual: Dinero
    plazo_remanente_meses: int


@dataclass(frozen=True)
class RefinanciamientoInstituto:
    """
    El producto refinancia también el crédito del instituto en una línea aparte
    (Santander Mejoras Cofis, hoja Sustitución): misma tasa, plazo y pago que la
    principal, seguro de vida y comisión mensual; sin daños, avalúo, apertura ni
    IVA de intereses. El aforo y la base de los gastos financiables suman los
    dos créditos.
    """

    comision_mensual: Dinero                # 350 + IVA (Adm!Q6)


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


class BaseTopeGastos(str, Enum):
    """Sobre qué se mide el tope de gastos notariales financiables."""

    VALOR_INMUEBLE = "valor_inmueble"   # Banamex Perfiles / A tu Medida: 10 %
    MONTO_CREDITO = "monto_credito"     # Scotiabank 6 %, Banamex CTH 5 % del saldo


@dataclass(frozen=True)
class FinanciamientoGastos:
    """
    El producto permite sumar los gastos notariales al crédito. Lo financiado
    es el mínimo entre los gastos del escenario, el tope (fracción de la base;
    None = sin tope porcentual, BX+ Mejora) y lo que cabe en el aforo máximo.
    Se suma al capital: genera intereses y seguro de vida sobre saldo.
    """

    tope: Optional[Decimal]
    base_tope: BaseTopeGastos = BaseTopeGastos.MONTO_CREDITO
    # True (Banamex, BX+): la comisión por apertura y el aforo que define la
    # tasa usan el crédito con gastos. False (Scotiabank): usan el crédito sin
    # gastos (Simulador!J18 = F15 × V12); el CAT sí parte del crédito total.
    apertura_y_aforo_sobre_total: bool = True
    # True (Afirme Tu Casa 2): además de los notariales financia el avalúo y la
    # propia comisión por apertura, que se cobra sobre el total.
    incluye_apertura_y_avaluo: bool = False
    # True (Santander Sustitución): los gastos van en un segundo crédito con la
    # misma tasa, plazo y pago, solo seguro de vida e IVA sobre intereses, y
    # su propio CAT (Liquidez!D:K, CAT!AB20). El crédito principal no cambia.
    linea_separada: bool = False
    # True (Santander, Cal!C47): si crédito + tope rebasa el aforo máximo no se
    # financia nada, en vez de recortar a lo que cabe.
    excede_aforo_cancela: bool = False


@dataclass(frozen=True)
class TasaVariable:
    """
    Tasa referenciada desde `desde_mes`: referencia + sobretasa, con techo y
    piso opcionales. El valor de la referencia lo pone el escenario de la
    comparación (`Escenario.tiie`), no el producto.
    """

    desde_mes: int
    sobretasa: Decimal
    techo: Optional[Decimal] = None
    piso: Optional[Decimal] = None
    referencia: str = "TIIE"


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

    # Pago = monto × factor al millar / 1000, con el factor redondeado hacia
    # arriba a centavos (Banamex: ROUNDUP(PMT(tasa/12, n, −1000), 2)). El
    # último pago sale menor.
    pago_por_millar_redondeado: bool = False

    # Primer pago solo de intereses (y seguros/comisiones); el capital se
    # amortiza en los meses restantes (Afirme, pago 0).
    primer_pago_solo_intereses: bool = False

    # El seguro de vida va dentro de la cuota fija (el de daños, no): capital
    # = cuota − interés − vida (Afirme).
    vida_en_pago_fijo: bool = False

    # Seguro de desempleo como porcentaje del pago del mes (capital, interés,
    # seguros y comisiones), con IVA si aplica (Afirme: 0.98 %).
    seguro_desempleo_pct: Decimal = Decimal("0")
    seguro_desempleo_con_iva: bool = False

    # IVA sobre intereses (créditos de liquidez): se cobra en el pago, aparte
    # del pago fijo (no amortiza). Con `iva_intereses_inflacion` se cobra solo
    # sobre el interés real: (1 + i) / (1 + inflación/12) − 1 (Banamex, 4 %).
    # Entra al CAT solo si `iva_intereses_en_cat` (Banregio sí; los demás no).
    iva_sobre_intereses: bool = False
    iva_intereses_inflacion: Optional[Decimal] = None
    iva_intereses_en_cat: bool = False

    # Factores de pago al millar fijos por plazo ((plazo, factor), ...): el
    # pago es monto × factor / 1000 (Scotiabank los trae escritos a mano).
    factores_al_millar: Tuple[Tuple[int, Decimal], ...] = ()

    # Factores al millar por año (año 1, año 2, ...): el pago del año es el
    # monto ORIGINAL × factor / 1000 y cambia en los meses 13, 25, ... El
    # último factor se usa para los años restantes (Banamex La Hipoteca a tu
    # Medida: año 1 de su tabla, luego × 1.02 redondeado a 6 decimales).
    factores_al_millar_anuales: Tuple[Decimal, ...] = ()

    # El pago (capital + interés) se multiplica por (1 + crecimiento) en cada
    # aniversario (meses 13, 25, ...) sin recalcularse sobre el saldo, así que
    # el crédito se liquida antes del plazo (Scotiabank Valora: 2.6 % en Pago
    # de pasivos, 1.5 % en Liquidez Libre). Se combina con factores al millar
    # por plazo y con tasa escalonada de pago fijo.
    crecimiento_pago_anual: Optional[Decimal] = None

    # Desde este mes el pago se recalcula CADA mes sobre el saldo, los meses
    # restantes y la tasa del periodo con su convención de días (Scotiabank
    # 7x5 desde el mes 61).
    reamortizar_mensual_desde: Optional[int] = None

    # Tasa variable referenciada (Scotiabank 7x5: TIIE + 4.5 desde el mes 61,
    # techo 15 %). Se resuelve con la TIIE del escenario.
    tasa_variable: Optional[TasaVariable] = None

    # Días de corte del primer pago (Scotiabank: 3 o 17): se usa el primero si
    # la cotización cae entre ese día y el anterior al segundo; si no, el
    # segundo. Si el corte ya pasó en el mes, el primer pago es el mes siguiente.
    cortes_de_pago: Tuple[int, ...] = ()

    # Primer periodo irregular (Banorte): el mes 1 cobra interés por los días
    # reales desde la disposición hasta el primer pago, inclusive, y prorratea
    # los seguros de vida y daños a días/30. El capital del mes 1 sigue siendo el del
    # pago regular. El CAT se calcula sobre la tabla regular.
    primer_periodo_dias_reales: bool = False

    # Día del mes en que se paga. None = día 1 del mes siguiente a la
    # comparación. Con día de pago, el primer pago es ese día del mes
    # siguiente; si la disposición cae en `dia_corte_primer_pago` o después,
    # se recorre 30 días (Banorte: día 3, corte 30; Fecha Pago!K4).
    dia_de_pago: Optional[int] = None
    dia_corte_primer_pago: Optional[int] = None
    # Con corte, recorre el primer pago un mes completo en vez de 30 días
    # (Afirme: si la apertura es el día 20 o después).
    recorrer_primer_pago_un_mes: bool = False

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

    # Gastos notariales que el banco suma al crédito si el escenario lo pide.
    # None = no los financia: se pagan de contado.
    financiamiento_gastos: Optional[FinanciamientoGastos] = None

    # El aforo se mide sobre la vivienda más el inmueble adicional que el
    # cliente deja en garantía (Afirme Tu Casa 2). Se cobra un avalúo por cada
    # inmueble. Los productos que no la aceptan la ignoran.
    acepta_garantia_adicional: bool = False
    # Solo tiene sentido con garantía adicional o gastos financiados; sin
    # ninguno es igual a otro producto del banco (Tu Casa 2 = Adquisición).
    requiere_garantia_o_gastos_financiados: bool = False

    # Compra con remodelación en un solo crédito (Scotiabank Credirenovación
    # modo 2): el crédito suma el presupuesto de obra y el aforo, el avalúo
    # y el seguro de daños se miden sobre el valor proyectado (compra + obra).
    # Solo aplica con presupuesto de obra en el escenario.
    financia_remodelacion: bool = False
    # Tope de la obra como fracción del valor actual del inmueble
    # (Credirenovación Pasivo + Renovación: 35 %, validación de H30).
    remodelacion_max_pct_valor: Optional[Decimal] = None

    # Segunda hipoteca para remodelar (Credirenovación modo 4): la vivienda ya
    # tiene hipoteca con el mismo banco (`Escenario.credito_actual`), que NO se
    # refinancia. El crédito es solo la obra; el aforo suma el saldo vigente
    # sobre valor + obra, y el avalúo se mide sobre valor + obra.
    segunda_hipoteca: bool = False
    # Solo para vivienda sin hipoteca (Credirenovación modo 1).
    excluye_vivienda_con_hipoteca: bool = False

    # Regla de capacidad de pago del banco, si la publica: el pago inicial de
    # capital e interés (sin seguros) no debe pasar de esta fracción del
    # ingreso, en lugar de la del escenario (Scotiabank Credirenovación:
    # 'Simulador Valora'!E66 = E56 / PTI, 35 % o 55 %). Más el ingreso mínimo.
    factor_pago_ingreso_max: Optional[Decimal] = None
    ingreso_minimo: Optional[Dinero] = None

    # Condiciones que la oferta exige del cliente (campañas especiales). Solo
    # es elegible si el escenario las marca todas.
    requisitos_cliente: FrozenSet[RequisitoCliente] = frozenset()

    # Cuántas entregas por avance de obra admite (Credirenovación: 3). 0 = el
    # crédito se entrega completo al firmar.
    max_ministraciones: int = 0

    # Sustitución según el banco del crédito actual (`CreditoActual.institucion`):
    # solo para hipotecas que ya son del mismo banco (Santander Mejora de
    # Condiciones) o solo para traerlas de otro (Santander Sustitución).
    solo_credito_actual_propio: bool = False
    excluye_credito_actual_propio: bool = False

    # Refinancia también el crédito del instituto del cofinanciamiento actual
    # (`CreditoActual.credito_instituto`). None = solo el bancario.
    refinanciamiento_instituto: Optional[RefinanciamientoInstituto] = None

    # Comisión por apertura como fracción del monto del crédito
    comision_apertura: Decimal = Decimal("0")

    # Comisión por apertura como monto fijo. Si se define, sustituye a la
    # fracción (hay instituciones que cobran una cantidad fija).
    comision_apertura_monto: Optional[Dinero] = None

    # Tope de la comisión por apertura cuando es fracción (BX+: $150,000).
    comision_apertura_tope: Optional[Dinero] = None

    # Comisión de investigación o "gastos de aprobación": cargo único al
    # contratar, como lo paga el cliente (Banorte: 750 en Mejora, 500 en
    # Terreno y Liquidez). Entra al desembolso, al costo total y al CAT.
    comision_investigacion: Dinero = Decimal("0")

    # Dictamen técnico (Scotiabank Credirenovación): cargo único por verificar
    # la obra, fracción del crédito con mínimo y máximo. Entra completo al
    # desembolso, al costo total y al CAT.
    dictamen_tecnico_pct: Decimal = Decimal("0")
    dictamen_tecnico_minimo: Dinero = Decimal("0")
    dictamen_tecnico_maximo: Optional[Dinero] = None

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
    destino: "Destino" = None  # se fija en __post_init__ (ADQUISICION)

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

    def __post_init__(self):
        if self.destino is None:
            object.__setattr__(self, "destino", Destino.ADQUISICION)

    def dictamen_tecnico_para(self, monto: Dinero) -> Dinero:
        if not self.dictamen_tecnico_pct:
            return Decimal("0")
        dictamen = max(self.dictamen_tecnico_pct * monto, self.dictamen_tecnico_minimo)
        if self.dictamen_tecnico_maximo is not None:
            dictamen = min(dictamen, self.dictamen_tecnico_maximo)
        return dictamen

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

    # El cliente quiere financiar los gastos notariales. Cada producto que lo
    # permite suma al crédito lo que su regla deja; en los demás se pagan de
    # contado. Se pide el mismo monto a todos para que sean comparables.
    financiar_gastos_notariales: bool = False

    # Valor de otro inmueble que el cliente ofrece en garantía. Solo el valor:
    # no se piden datos del inmueble (regla 7).
    valor_garantia_adicional: Dinero = Decimal("0")

    # Presupuesto de obra para remodelar la vivienda que se compra. Solo lo
    # financian los productos con `financia_remodelacion`; para los demás
    # queda fuera y no son elegibles.
    monto_remodelacion: Dinero = Decimal("0")

    # Condiciones especiales que el cliente cumple (vinculación, segmento,
    # tipo de obra). Las ofertas que las exigen solo aplican si están aquí.
    condiciones_cliente: FrozenSet[RequisitoCliente] = frozenset()

    # Entrega del crédito por avance de obra: ((mes, monto), ...) desde la
    # firma; la primera en el mes 1 y la suma igual al crédito. Vacío = todo
    # al firmar. Del escenario, para comparar todas las opciones con el mismo
    # calendario de obra.
    ministraciones: Tuple[Tuple[int, Dinero], ...] = ()

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

    # TIIE supuesta para productos de tasa variable (escenario de la
    # comparación). None = escenario base de motor_hipotecario.referencias.
    tiie: Optional[Decimal] = None

    # Para qué es el crédito, y la hipoteca actual si es sustitución.
    destino: Destino = Destino.ADQUISICION
    credito_actual: Optional[CreditoActual] = None

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
        if self.destino is Destino.SUSTITUCION and self.credito_actual is None:
            errores.append("La sustitución requiere los datos del crédito actual.")
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
