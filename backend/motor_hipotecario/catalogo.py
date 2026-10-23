"""
Catálogo de productos con condiciones de instituciones reales.

Cada producto sale de un cotizador oficial de la institución, reproducido al
centavo (docs/validacion_modelos.md). `tests/test_catalogo.py` verifica que el
producto siga reproduciendo su archivo.

LÍMITES DE ESTOS DATOS — léelos antes de usarlos frente a un cliente:

- La tasa, las comisiones y los seguros son los del escenario capturado en el
  cotizador. La tasa final depende del perfil, el aforo y el plazo, y la
  institución puede haberla cambiado desde que se generó el archivo.
- El seguro de daños es el monto mensual del escenario del archivo, no la
  tarifa de la aseguradora: no escala con el valor del inmueble.
- El aforo máximo y los plazos ofrecidos NO vienen en los cotizadores. Son
  supuestos marcados en `notas` y hay que confirmarlos con cada institución.
- Ninguno de los dos productos tiene aún el CAT validado por el motor: HSBC y
  Santander tratan el IVA distinto y el criterio está pendiente con riesgo.

Actualizar condiciones = cerrar la vigencia del producto y crear uno nuevo con
su propia fuente. Nunca editar en sitio (CLAUDE.md, regla 3).

Pendientes:
  Banregio  — el motor ya lo reproduce; faltan la comisión por apertura y el
              avalúo, que no se extrajeron del cotizador. Sin ellos saldría
              artificialmente barato frente a los demás.
  Scotiabank, Banamex — los cotizadores se recibieron sin escenario capturado
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .modelos import ConvencionDias, ProductoHipotecario

# Fecha en que se analizaron los cotizadores. Los archivos no traen fecha de
# vigencia de las condiciones.
_ANALIZADO = date(2026, 10, 22)

_SUPUESTOS = (
    "SUPUESTOS POR CONFIRMAR con la institución: aforo máximo de 90 % y plazos "
    "ofrecidos; no vienen en el cotizador."
)


CATALOGO: list[ProductoHipotecario] = [
    ProductoHipotecario(
        id="hsbc-cicb-2026-10",
        institucion="HSBC",
        nombre="Crédito hipotecario (cotizador CICB)",
        tasa_anual=Decimal("0.1175"),
        convencion_interes=ConvencionDias.TASA_ENTRE_12,
        plazos_meses=(60, 120, 180, 240),
        aforo_max=Decimal("0.90"),
        comision_apertura=Decimal("0.01"),
        comision_mensual=Decimal("290"),
        seguro_vida_mensual=Decimal("0.00044"),
        seguro_danos_monto_mensual=Decimal("777.63"),
        avaluo=Decimal("12470"),
        vigente_desde=_ANALIZADO,
        fuente="Cotizador hsbc_cicb.xlsm, hoja Amortización (escenario capturado: "
        "$2,082,500 a 240 meses). Analizado 2026-10-22.",
        notas=_SUPUESTOS,
    ),
    ProductoHipotecario(
        id="santander-2026-10",
        institucion="Santander",
        nombre="Crédito hipotecario (cotizador Santander)",
        tasa_anual=Decimal("0.095"),
        convencion_interes=ConvencionDias.DIAS_30_4166_360,
        convencion_pago=ConvencionDias.DIAS_365_12_360,
        plazos_meses=(60, 120, 180, 240, 300),
        aforo_max=Decimal("0.90"),
        # El archivo la guarda neta de IVA (6,034.48); se captura el monto que
        # paga el cliente.
        comision_apertura_monto=Decimal("7000"),
        comision_mensual=Decimal("350"),
        seguro_vida_mensual=Decimal("0.0008254"),
        seguro_danos_monto_mensual=Decimal("380.17"),
        vigente_desde=_ANALIZADO,
        fuente="Cotizador Santander.xlsm, hoja CAT (escenario capturado: "
        "$1,770,000 a 300 meses). Analizado 2026-10-22.",
        notas=_SUPUESTOS + " El cotizador no trae avalúo.",
    ),
]
