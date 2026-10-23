"""Motor de cálculo hipotecario. Núcleo puro: sin UI, sin base de datos."""

from .amortizacion import (
    TablaAmortizacion,
    construir_tabla,
    pago_frances,
    tasa_normalizada,
    tasa_periodica,
)
from .cat import calcular_cat, tasa_efectiva_anual
from .comparador import VERSION_MOTOR, Comparacion, ResultadoOpcion, comparar
from .modelos import (
    ConvencionDias,
    Escenario,
    LineaCredito,
    ProductoHipotecario,
    Snapshot,
)

__all__ = [
    "TablaAmortizacion",
    "construir_tabla",
    "pago_frances",
    "tasa_periodica",
    "tasa_normalizada",
    "calcular_cat",
    "tasa_efectiva_anual",
    "comparar",
    "Comparacion",
    "ResultadoOpcion",
    "VERSION_MOTOR",
    "ConvencionDias",
    "Escenario",
    "LineaCredito",
    "ProductoHipotecario",
    "Snapshot",
]
