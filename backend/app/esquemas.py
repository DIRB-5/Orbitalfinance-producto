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

from pydantic import BaseModel, ConfigDict, Field

from motor_hipotecario.modelos import TipoLinea
from pydantic.alias_generators import to_camel


class ModeloBase(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CofinanciamientoEntrada(ModeloBase):
    instituto: TipoLinea
    salario_mensual: Decimal = Field(ge=0)
    monto_credito_instituto: Decimal = Field(default=Decimal("0"), ge=0)
    saldo_subcuenta: Decimal = Field(default=Decimal("0"), ge=0)


class EscenarioEntrada(ModeloBase):
    valor_vivienda: Decimal = Field(gt=0)
    enganche: Decimal = Field(ge=0)
    plazo_meses: int = Field(gt=0, le=480)
    gastos_notariales: Decimal = Field(default=Decimal("0"), ge=0)
    ingreso_mensual: Optional[Decimal] = Field(default=None, ge=0)
    factor_pago_ingreso: Decimal = Field(default=Decimal("0.30"), gt=0, le=1)
    fecha_primer_pago: Optional[date] = None
    fecha_disposicion: Optional[date] = None
    cofinanciamiento: Optional[CofinanciamientoEntrada] = None
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


class ProductoSalida(ModeloBase):
    id: str
    institucion: str
    nombre: str
    tipo: str
    tasa_anual: str
    tasa_normalizada: str
    convencion_interes: str
    convencion_pago: str
    convencion_amortizacion: str
    seguros_en_pago_fijo: bool
    crecimiento_pago_mensual: List[FaseCrecimientoSalida]
    factores_al_millar_anuales: List[str]
    tasas_escalonadas: List[EscalonSalida]
    recalcular_pago_al_cambiar_tasa: bool
    regla_aportaciones: Optional[ReglaAportacionesSalida]
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


class CatalogoSalida(ModeloBase):
    productos: List[ProductoSalida]
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
    pago_total: str
    saldo_final: str


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
    avaluo: str
    gastos_notariales: str
    cat_estimado: str
    pago_primer_mes: str
    pago_ultimo_mes: str
    total_intereses: str
    total_seguros: str
    total_comision_mensual: str
    total_aportaciones: str
    credito_instituto: Optional[CreditoInstitutoSalida]
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
