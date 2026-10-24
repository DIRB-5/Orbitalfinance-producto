"""
Crédito del instituto en un cofinanciamiento (INFONAVIT Cofinavit).

Ningún cotizador bancario calcula esta parte: las condiciones salen de fuentes
oficiales. Lo que el instituto no publica se marca como supuesto.

Fuentes (consultadas 2026-10-24):
  - Condiciones Generales de Contratación INFONAVIT v1.1, DOF 05/12/2025,
    Apartado C.2 (Cofinavit): tasa fija de 10.45 % en pesos para todos los
    niveles salariales, plazo de 1 a 30 años, sin comisiones para créditos
    otorgados desde mayo de 2024, seguro de vida a cargo del instituto.
  - Portal Infonavit "Quiero comprar": monto máximo Cofinavit
    $1,159,022.80 (325 UMA mensuales de 2026).
  - Ley del INFONAVIT, art. 43 Bis: en cofinanciamiento, las aportaciones
    posteriores pagan primero el crédito del instituto; liquidado éste, se
    envían al crédito bancario.

SUPUESTO: el instituto solo dice "pagos fijos conforme al contrato". Se usa
una anualidad a tasa/12 sobre el plazo del escenario.

FOVISSSTE no tiene hoy crédito propio en cofinanciamiento bancario (FOVISSSTE
para Todos solo usa la subcuenta; Alia2 no está en el programa 2026).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Optional

from .amortizacion import TablaAmortizacion, construir_tabla
from .modelos import (
    AportacionExcedente,
    Cofinanciamiento,
    LineaCredito,
    ProductoHipotecario,
    ReglaAportaciones,
    TipoLinea,
)


@dataclass(frozen=True)
class CondicionesInstituto:
    instituto: TipoLinea
    producto: str
    tasa_anual: Decimal
    monto_maximo: Decimal
    plazo_max_meses: int
    fuente: str


COFINAVIT = CondicionesInstituto(
    instituto=TipoLinea.INFONAVIT,
    producto="Cofinavit",
    tasa_anual=Decimal("0.1045"),
    monto_maximo=Decimal("1159022.80"),
    plazo_max_meses=360,
    fuente="Condiciones Generales de Contratación INFONAVIT v1.1, DOF 05/12/2025 "
    "(Apartado C.2); monto máximo de 325 UMA 2026 según el portal Infonavit, "
    "consultado 2026-10-24.",
)


def tabla_credito_instituto(
    monto: Decimal,
    plazo_meses: int,
    regla: Optional[ReglaAportaciones],
    salario: Decimal,
    fecha_primer_pago: Optional[date] = None,
    condiciones: CondicionesInstituto = COFINAVIT,
) -> TablaAmortizacion:
    """
    Tabla del crédito del instituto: pago fijo (supuesto: anualidad a tasa/12)
    y, si hay regla, las aportaciones abonadas a capital hasta liquidarlo.
    """
    producto = ProductoHipotecario(
        id=f"{condiciones.instituto.value}-{condiciones.producto.lower()}",
        institucion=condiciones.instituto.value.upper(),
        nombre=condiciones.producto,
        tasa_anual=condiciones.tasa_anual,
        plazos_meses=(plazo_meses,),
        aforo_max=Decimal("1"),
        regla_aportaciones=(
            replace(regla, instituto=condiciones.instituto, excedente=AportacionExcedente.LIMITAR)
            if regla is not None
            else None
        ),
    )
    cofinanciamiento = (
        Cofinanciamiento(instituto=condiciones.instituto, salario_mensual=salario)
        if regla is not None
        else None
    )
    return construir_tabla(
        LineaCredito(producto, monto, plazo_meses),
        Decimal("0"),
        fecha_primer_pago,
        cofinanciamiento,
    )


def aportaciones_despues_de(regla: ReglaAportaciones, mes_liquidacion: int) -> ReglaAportaciones:
    """
    La misma regla, pero empezando en el primer mes de aportación posterior a
    la liquidación del crédito del instituto (conserva el calendario).
    """
    mes = max(regla.mes_inicio, mes_liquidacion + 1)
    while (mes - regla.mes_inicio) % regla.cada_meses:
        mes += 1
    return replace(regla, mes_inicio=mes)
