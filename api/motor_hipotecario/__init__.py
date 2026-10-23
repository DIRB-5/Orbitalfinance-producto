"""Motor de cálculo hipotecario. Núcleo puro: sin UI, sin base de datos."""

from .amortizacion import TablaAmortizacion, construir_tabla, pago_frances
from .cat import calcular_cat, tasa_efectiva_anual
from .comparador import VERSION_MOTOR, Comparacion, ResultadoOpcion, comparar
from .modelos import Escenario, LineaCredito, ProductoHipotecario, Snapshot

__all__ = [
    "TablaAmortizacion",
    "construir_tabla",
    "pago_frances",
    "calcular_cat",
    "tasa_efectiva_anual",
    "comparar",
    "Comparacion",
    "ResultadoOpcion",
    "VERSION_MOTOR",
    "Escenario",
    "LineaCredito",
    "ProductoHipotecario",
    "Snapshot",
]
