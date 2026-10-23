"""
CATÁLOGO DE PRUEBA — DATOS FICTICIOS

Los productos de este módulo NO corresponden a condiciones reales de ninguna
institución. Existen únicamente para ejercitar el motor y las pruebas.

Deliberadamente NO se usan nombres de bancos reales: un número inventado
atribuido a una institución real es exactamente el tipo de error que destruye
la credibilidad de la herramienta si se filtra a una presentación.

Para producción, este módulo se reemplaza por la carga del catálogo curado,
con productos capturados de las condiciones publicadas por cada institución y
con el campo `fuente` apuntando al documento y fecha de donde salió cada dato.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .modelos import BaseSeguroDanos, ConvencionDias, ProductoHipotecario

_FUENTE = "DATO FICTICIO DE PRUEBA — reemplazar con condiciones publicadas"

PLAZOS_ESTANDAR = (60, 120, 180, 240)


CATALOGO_DEMO: list[ProductoHipotecario] = [
    ProductoHipotecario(
        id="demo-a-fija",
        institucion="Institución Demo A",
        nombre="Hipotecario Tasa Fija",
        tasa_anual=Decimal("0.1085"),
        plazos_meses=PLAZOS_ESTANDAR,
        aforo_max=Decimal("0.90"),
        comision_apertura=Decimal("0.0085"),
        seguro_vida_mensual=Decimal("0.00045"),
        seguro_danos_anual=Decimal("0.0035"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        avaluo=Decimal("9500"),
        monto_minimo=Decimal("300000"),
        vigente_desde=date(2026, 1, 1),
        fuente=_FUENTE,
    ),
    ProductoHipotecario(
        id="demo-b-fija",
        institucion="Institución Demo B",
        nombre="Crédito Casa Fija",
        tasa_anual=Decimal("0.1045"),
        plazos_meses=PLAZOS_ESTANDAR,
        aforo_max=Decimal("0.85"),
        comision_apertura=Decimal("0.0100"),
        seguro_vida_mensual=Decimal("0.00062"),
        seguro_danos_anual=Decimal("0.0042"),
        base_seguro_danos=BaseSeguroDanos.VALOR_TOTAL,
        avaluo=Decimal("11000"),
        monto_minimo=Decimal("250000"),
        vigente_desde=date(2026, 1, 1),
        fuente=_FUENTE,
        notas="Tasa más baja, pero seguros y comisión más altos. Ejemplo de "
        "por qué comparar por tasa es insuficiente.",
    ),
    ProductoHipotecario(
        id="demo-c-fija",
        institucion="Institución Demo C",
        nombre="Hipoteca Preferente",
        tasa_anual=Decimal("0.1120"),
        plazos_meses=(120, 180, 240),
        aforo_max=Decimal("0.95"),
        comision_apertura=Decimal("0.0000"),
        seguro_vida_mensual=Decimal("0.00038"),
        seguro_danos_anual=Decimal("0.0030"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        avaluo=Decimal("8000"),
        vigente_desde=date(2026, 1, 1),
        fuente=_FUENTE,
        notas="Sin comisión por apertura y aforo alto. Ejemplo de producto "
        "que gana en costo total pese a tener la tasa más alta.",
    ),
    ProductoHipotecario(
        id="demo-d-corto",
        institucion="Institución Demo D",
        nombre="Hipotecario Plazo Corto",
        tasa_anual=Decimal("0.0990"),
        plazos_meses=(60, 120, 180),
        aforo_max=Decimal("0.80"),
        comision_apertura=Decimal("0.0125"),
        seguro_vida_mensual=Decimal("0.00050"),
        seguro_danos_anual=Decimal("0.0038"),
        base_seguro_danos=BaseSeguroDanos.VALOR_TOTAL,
        avaluo=Decimal("10000"),
        vigente_desde=date(2026, 1, 1),
        fuente=_FUENTE,
        notas="No ofrece 240 meses. Ejemplo de producto que queda fuera por "
        "regla de elegibilidad, no por precio.",
    ),
    # Demo E y Demo F copian las condiciones de Demo A y solo cambian la
    # convención de días, para aislar su efecto en el comparativo.
    ProductoHipotecario(
        id="demo-e-base360",
        institucion="Institución Demo E",
        nombre="Hipotecario Base 360",
        tasa_anual=Decimal("0.1085"),
        convencion_interes=ConvencionDias.DIAS_30_4166_360,
        convencion_pago=ConvencionDias.DIAS_365_12_360,
        plazos_meses=PLAZOS_ESTANDAR,
        aforo_max=Decimal("0.90"),
        comision_apertura=Decimal("0.0085"),
        seguro_vida_mensual=Decimal("0.00045"),
        seguro_danos_anual=Decimal("0.0035"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        avaluo=Decimal("9500"),
        monto_minimo=Decimal("300000"),
        vigente_desde=date(2026, 1, 1),
        fuente=_FUENTE,
        notas="Misma tasa nominal que Demo A, en base 360 con dos factores "
        "(interés 30.4166/360, pago 365/12). Cuesta como ~11.00 % en base /12.",
    ),
    ProductoHipotecario(
        id="demo-f-base304",
        institucion="Institución Demo F",
        nombre="Hipotecario Base 30.4",
        tasa_anual=Decimal("0.1085"),
        convencion_interes=ConvencionDias.DIAS_30_4_360,
        plazos_meses=PLAZOS_ESTANDAR,
        aforo_max=Decimal("0.90"),
        comision_apertura=Decimal("0.0085"),
        seguro_vida_mensual=Decimal("0.00045"),
        seguro_danos_anual=Decimal("0.0035"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        avaluo=Decimal("9500"),
        monto_minimo=Decimal("300000"),
        vigente_desde=date(2026, 1, 1),
        fuente=_FUENTE,
        notas="Misma tasa nominal que Demo A, con interés en base 30.4/360.",
    ),
]


CATALOGO_DEMO_NEGOCIADO: list[ProductoHipotecario] = [
    ProductoHipotecario(
        id="demo-a-fija-negociado",
        institucion="Institución Demo A",
        nombre="Hipotecario Tasa Fija",
        tasa_anual=Decimal("0.1020"),
        plazos_meses=PLAZOS_ESTANDAR,
        aforo_max=Decimal("0.90"),
        comision_apertura=Decimal("0.0050"),
        seguro_vida_mensual=Decimal("0.00045"),
        seguro_danos_anual=Decimal("0.0035"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        avaluo=Decimal("9500"),
        monto_minimo=Decimal("300000"),
        vigente_desde=date(2026, 1, 1),
        fuente=_FUENTE,
        negociado_por="Grupo Inmobiliario Demo",
        notas="Ejemplo de override por organización: mejor tasa y comisión "
        "reducida por volumen.",
    ),
]
