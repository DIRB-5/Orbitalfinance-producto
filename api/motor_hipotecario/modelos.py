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
from typing import Optional

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
    # Días reales del mes / 360 (Scotiabank, Banregio, Afirme) requiere fechas
    # de pago; entra junto con la base de amortización separada (corrección 3).


class TipoLinea(str, Enum):
    BANCARIO = "bancario"
    INFONAVIT = "infonavit"
    FOVISSSTE = "fovissste"


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

    # Comisión por apertura como fracción del monto del crédito
    comision_apertura: Decimal = Decimal("0")

    # Seguro de vida: tasa MENSUAL aplicada sobre el saldo insoluto
    seguro_vida_mensual: Decimal = Decimal("0")

    # Seguro de daños: tasa ANUAL aplicada sobre el valor del inmueble
    seguro_danos_anual: Decimal = Decimal("0")
    base_seguro_danos: BaseSeguroDanos = BaseSeguroDanos.VALOR_TOTAL

    # Proporción del valor que se considera construcción, cuando aplica
    factor_construccion: Decimal = Decimal("0.70")

    # Avalúo cobrado por la institución (entra al CAT). Los gastos notariales
    # NO entran al CAT porque los cobra un tercero, pero sí al costo total.
    avaluo: Dinero = Decimal("0")

    monto_minimo: Optional[Dinero] = None
    monto_maximo: Optional[Dinero] = None

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

    etiqueta: str = ""
    notas: str = ""

    @property
    def monto_credito(self) -> Dinero:
        return self.valor_vivienda - self.enganche

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
