"""
Esquemas de entrada y salida de la API.

Aquí, y solo aquí, ocurre la conversión snake_case → camelCase (CLAUDE.md,
convención de nombres). El dinero sale como string redondeado a centavos: es la
capa de presentación del motor, que calcula con precisión completa.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from motor_hipotecario.modelos import Destino, RequisitoCliente, TipoLinea
from pydantic.alias_generators import to_camel


class ModeloBase(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CofinanciamientoEntrada(ModeloBase):
    instituto: TipoLinea
    salario_mensual: Decimal = Field(ge=0)
    monto_credito_instituto: Decimal = Field(default=Decimal("0"), ge=0)
    saldo_subcuenta: Decimal = Field(default=Decimal("0"), ge=0)


class MinistracionEntrada(ModeloBase):
    """Entrega por avance de obra: mes desde la firma y monto en pesos."""

    mes: int = Field(ge=1, le=480)
    monto: Decimal = Field(gt=0)


class CreditoInstitutoActualEntrada(ModeloBase):
    """Crédito INFONAVIT/FOVISSSTE de la hipoteca actual. Saldo en pesos."""

    instituto: TipoLinea
    saldo: Decimal = Field(gt=0)
    pago_mensual: Decimal = Field(ge=0)
    plazo_remanente_meses: int = Field(gt=0, le=480)

    @field_validator("instituto")
    @classmethod
    def _solo_instituto(cls, v: TipoLinea) -> TipoLinea:
        if v is TipoLinea.BANCARIO:
            raise ValueError("El crédito del instituto es INFONAVIT o FOVISSSTE.")
        return v


class CreditoActualEntrada(ModeloBase):
    saldo_insoluto: Decimal = Field(gt=0)
    pago_mensual: Decimal = Field(gt=0)
    plazo_remanente_meses: int = Field(gt=0, le=480)
    tasa_anual: Optional[Decimal] = Field(default=None, ge=0)
    penalizacion_prepago: Decimal = Field(default=Decimal("0"), ge=0)
    institucion: str = ""
    credito_instituto: Optional[CreditoInstitutoActualEntrada] = None


class EscenarioEntrada(ModeloBase):
    valor_vivienda: Decimal = Field(gt=0)
    enganche: Decimal = Field(ge=0)
    plazo_meses: int = Field(gt=0, le=480)
    gastos_notariales: Decimal = Field(default=Decimal("0"), ge=0)
    # Pedir a cada banco que lo permita sumar los gastos al crédito
    financiar_gastos_notariales: bool = False
    # Valor de otro inmueble en garantía (Afirme Tu Casa 2). Solo el valor.
    valor_garantia_adicional: Decimal = Field(default=Decimal("0"), ge=0)
    # Presupuesto de obra para remodelar la vivienda que se compra
    monto_remodelacion: Decimal = Field(default=Decimal("0"), ge=0)
    # Condiciones especiales que cumple el cliente (campañas que las exigen)
    condiciones_cliente: List[RequisitoCliente] = []
    # Entrega del crédito por avance de obra; vacío = todo al firmar
    ministraciones: List[MinistracionEntrada] = []
    ingreso_mensual: Optional[Decimal] = Field(default=None, ge=0)
    factor_pago_ingreso: Decimal = Field(default=Decimal("0.30"), gt=0, le=1)
    fecha_primer_pago: Optional[date] = None
    fecha_disposicion: Optional[date] = None
    cofinanciamiento: Optional[CofinanciamientoEntrada] = None
    destino: Destino = Destino.ADQUISICION
    credito_actual: Optional[CreditoActualEntrada] = None
    # Escenario de TIIE para productos de tasa variable
    escenario_tasa: str = Field(default="base", pattern="^(conservador|base|estres)$")


class EscalonSalida(ModeloBase):
    desde_mes: int
    tasa_anual: str


class FaseCrecimientoSalida(ModeloBase):
    desde_mes: int
    crecimiento_mensual: str


class TramoTasaSalida(ModeloBase):
    plazo_max_meses: int
    aforo_max: str
    tasa_anual: str


class ReglaAportacionesSalida(ModeloBase):
    instituto: str
    porcentaje_salario: str
    tope: Optional[str]
    incremento_anual: str
    mes_inicio: int
    cada_meses: int
    excedente: str


class TasaVariableSalida(ModeloBase):
    desde_mes: int
    referencia: str
    sobretasa: str
    techo: Optional[str]


class FinanciamientoGastosSalida(ModeloBase):
    tope: Optional[str]
    base_tope: str
    apertura_y_aforo_sobre_total: bool
    incluye_apertura_y_avaluo: bool
    linea_separada: bool


class ProductoSalida(ModeloBase):
    id: str
    institucion: str
    nombre: str
    tipo: str
    destino: str
    tasa_anual: str
    tasa_normalizada: str
    convencion_interes: str
    convencion_pago: str
    convencion_amortizacion: str
    seguros_en_pago_fijo: bool
    crecimiento_pago_mensual: List[FaseCrecimientoSalida]
    factores_al_millar_anuales: List[str]
    crecimiento_pago_anual: Optional[str]
    tasas_escalonadas: List[EscalonSalida]
    recalcular_pago_al_cambiar_tasa: bool
    regla_aportaciones: Optional[ReglaAportacionesSalida]
    financiamiento_gastos: Optional[FinanciamientoGastosSalida]
    acepta_garantia_adicional: bool
    financia_remodelacion: bool
    factor_pago_ingreso_max: Optional[str]
    ingreso_minimo: Optional[str]
    requisitos_cliente: List[str]
    max_ministraciones: int
    # Dictamen técnico de la obra (remodelación): fracción con mínimo y máximo
    dictamen_tecnico_pct: str
    dictamen_tecnico_minimo: str
    dictamen_tecnico_maximo: Optional[str]
    requiere_cofinanciamiento: bool
    dia_de_pago: Optional[int]
    primer_periodo_dias_reales: bool
    tabla_tasas: List[TramoTasaSalida]
    tasa_variable: Optional[TasaVariableSalida]
    tiene_tarifa_avaluo: bool
    valor_minimo_inmueble: Optional[str]
    plazos_meses: List[int]
    aforo_max: str
    comision_apertura: str
    comision_apertura_monto: Optional[str]
    comision_mensual: str
    seguro_vida_mensual: str
    seguro_danos_anual: str
    seguro_danos_monto_mensual: Optional[str]
    base_seguro_danos: str
    factor_construccion: str
    avaluo: str
    cat_netos_de_iva: List[str]
    monto_minimo: Optional[str]
    monto_maximo: Optional[str]
    vigente_desde: str
    vigente_hasta: Optional[str]
    fuente: str
    notas: str
    negociado_por: Optional[str]


class EscenarioTasaSalida(ModeloBase):
    id: str
    nombre: str
    tiie: str


class RequisitoSalida(ModeloBase):
    id: str
    descripcion: str


class CatalogoSalida(ModeloBase):
    productos: List[ProductoSalida]
    requisitos_cliente: List[RequisitoSalida]
    escenarios_tiie: List[EscenarioTasaSalida]
    fuente_tiie: str


class RenglonSalida(ModeloBase):
    mes: int
    fecha_pago: Optional[str]
    saldo_inicial: str
    interes: str
    capital: str
    seguro_vida: str
    seguro_danos: str
    comision_mensual: str
    aportacion: str
    seguro_desempleo: str
    iva_intereses: str
    disposicion: str
    pago_total: str
    saldo_final: str


class LineaGastosSalida(ModeloBase):
    """Segundo crédito con los gastos notariales (Santander Sustitución)."""

    monto: str
    tasa_anual: str
    pago_mensual: str
    total_pagado: str
    total_intereses: str
    total_iva_intereses: str
    cat_estimado: str


class LineaInstitutoSalida(ModeloBase):
    """Crédito del instituto refinanciado en una línea aparte (Santander)."""

    instituto: str
    monto: str
    tasa_anual: str
    pago_mensual: str
    total_pagado: str
    total_intereses: str
    cat_estimado: str


class CreditoInstitutoSalida(ModeloBase):
    instituto: str
    producto: str
    monto: str
    tasa_anual: str
    pago_mensual: str
    plazo_efectivo_meses: int
    total_pagado: str
    total_aportaciones: str
    fuente: str


class OpcionSalida(ModeloBase):
    producto_id: str
    tasa_variable: bool
    alternativa_sin_cofinanciamiento: bool
    tasa_anual: str
    tasa_normalizada: str
    elegible: bool
    motivos_rechazo: List[str]
    advertencias: List[str]
    monto_credito: str
    aforo: str
    plazo_calculado_meses: int
    plazo_efectivo_meses: int
    comision_apertura: str
    comision_investigacion: str
    dictamen_tecnico: str
    avaluo: str
    gastos_notariales: str
    gastos_financiados: str
    gastos_de_contado: str
    remodelacion_financiada: str
    # Ingreso mensual que pide la opción (pago inicial / PTI, y el mínimo)
    ingreso_requerido: Optional[str]
    linea_gastos: Optional[LineaGastosSalida]
    linea_instituto: Optional[LineaInstitutoSalida]
    cat_estimado: str
    pago_primer_mes: str
    pago_ultimo_mes: str
    # Pago regular: el primero y el último completos (sin periodo irregular
    # ni pago de cierre). Es el que se presenta como mensualidad.
    pago_regular_inicial: str
    pago_regular_final: str
    primer_pago_irregular: bool
    dias_primer_periodo: Optional[int]
    total_intereses: str
    total_seguros: str
    total_comision_mensual: str
    total_aportaciones: str
    credito_instituto: Optional[CreditoInstitutoSalida]
    # Sustitución: contra quedarse con el crédito actual
    costo_de_cambiarse: Optional[str]
    ahorro_mensual: Optional[str]
    punto_equilibrio_mes: Optional[int]
    ahorro_neto: Optional[str]
    serie_ahorro: List[str]
    suma_mensualidades: str
    costo_total: str
    costo_financiero: str
    desembolso_inicial: str
    tabla: List[RenglonSalida]


class ComparacionSalida(ModeloBase):
    version_motor: str
    escenario_tasa: str
    tiie: str
    generado_en: str
    fecha_primer_pago: str
    opciones: List[OpcionSalida]
