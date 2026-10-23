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
from pydantic.alias_generators import to_camel


class ModeloBase(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class EscenarioEntrada(ModeloBase):
    valor_vivienda: Decimal = Field(gt=0)
    enganche: Decimal = Field(ge=0)
    plazo_meses: int = Field(gt=0, le=480)
    gastos_notariales: Decimal = Field(default=Decimal("0"), ge=0)
    ingreso_mensual: Optional[Decimal] = Field(default=None, ge=0)
    factor_pago_ingreso: Decimal = Field(default=Decimal("0.30"), gt=0, le=1)
    fecha_primer_pago: Optional[date] = None


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


class CatalogoSalida(ModeloBase):
    productos: List[ProductoSalida]


class RenglonSalida(ModeloBase):
    mes: int
    fecha_pago: Optional[str]
    saldo_inicial: str
    interes: str
    capital: str
    seguro_vida: str
    seguro_danos: str
    comision_mensual: str
    pago_total: str
    saldo_final: str


class OpcionSalida(ModeloBase):
    producto_id: str
    elegible: bool
    motivos_rechazo: List[str]
    advertencias: List[str]
    monto_credito: str
    aforo: str
    plazo_calculado_meses: int
    comision_apertura: str
    avaluo: str
    gastos_notariales: str
    cat_estimado: str
    pago_primer_mes: str
    pago_ultimo_mes: str
    total_intereses: str
    total_seguros: str
    total_comision_mensual: str
    suma_mensualidades: str
    costo_total: str
    costo_financiero: str
    desembolso_inicial: str
    tabla: List[RenglonSalida]


class ComparacionSalida(ModeloBase):
    version_motor: str
    generado_en: str
    fecha_primer_pago: str
    opciones: List[OpcionSalida]
