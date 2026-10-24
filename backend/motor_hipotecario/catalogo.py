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
- El CAT reproduce el de cada cotizador con el tratamiento de IVA de esa
  institución (`cat_netos_de_iva`). HSBC y Santander lo tratan distinto y el
  criterio correcto está pendiente con riesgo: el CAT sigue siendo estimado.

Actualizar condiciones = cerrar la vigencia del producto y crear uno nuevo con
su propia fuente. Nunca editar en sitio (CLAUDE.md, regla 3).

Banregio es distinto: sus tasas salen de la tabla del cotizador por plazo y
aforo, y el avalúo de su tabulador, así que el comparador los resuelve para
cada escenario. Pero el archivo es de diciembre de 2023: sus tasas pueden
estar desactualizadas.

Pendientes:
  Scotiabank, Banamex — los cotizadores se recibieron sin escenario capturado
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .modelos import BaseSeguroDanos, ConceptoIVA, ConvencionDias, ProductoHipotecario

# Fecha en que se analizaron los cotizadores. Los archivos no traen fecha de
# vigencia de las condiciones.
_ANALIZADO = date(2026, 10, 22)

_SUPUESTOS = (
    "SUPUESTOS POR CONFIRMAR con la institución: aforo máximo de 90 % y plazos "
    "ofrecidos; no vienen en el cotizador."
)


# Tabulador de avalúo de Banregio (Param!AZ8:BE17): (valor desde, fijo, al millar)
_TARIFA_AVALUO_BANREGIO = (
    (Decimal("0"), Decimal("2174"), Decimal("0")),
    (Decimal("800000"), Decimal("0"), Decimal("2.7")),
    (Decimal("2000000"), Decimal("0"), Decimal("2.5")),
    (Decimal("3000000"), Decimal("0"), Decimal("2.4")),
    (Decimal("4000000"), Decimal("0"), Decimal("2.35")),
    (Decimal("5000000"), Decimal("0"), Decimal("2.3")),
    (Decimal("6000000"), Decimal("0"), Decimal("2.25")),
    (Decimal("7000000"), Decimal("0"), Decimal("2.2")),
    (Decimal("8000000"), Decimal("0"), Decimal("2.1")),
    (Decimal("9000000"), Decimal("0"), Decimal("2.0")),
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
        # Amortización!V20 y V21: daños, comisión mensual y avalúo ÷ 1.16;
        # apertura completa.
        cat_netos_de_iva=frozenset(
            {ConceptoIVA.SEGURO_DANOS, ConceptoIVA.COMISION_MENSUAL, ConceptoIVA.AVALUO}
        ),
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
        # CAT!L5: solo la apertura ÷ 1.16; daños y comisión mensual completos.
        cat_netos_de_iva=frozenset({ConceptoIVA.COMISION_APERTURA}),
        vigente_desde=_ANALIZADO,
        fuente="Cotizador Santander.xlsm, hoja CAT (escenario capturado: "
        "$1,770,000 a 300 meses). Analizado 2026-10-22.",
        notas=_SUPUESTOS + " El cotizador no trae avalúo.",
    ),
    ProductoHipotecario(
        id="banregio-adquisicion-2023-12",
        institucion="Banregio",
        nombre="Adquisición Tradicional (pagos fijos)",
        # Referencia del catálogo: la tasa más alta. El comparador usa la de
        # `tabla_tasas` según plazo y aforo del escenario (TablaTasas!E17:I47).
        tasa_anual=Decimal("0.110"),
        tabla_tasas=(
            (120, Decimal("0.70"), Decimal("0.096")),
            (120, Decimal("0.90"), Decimal("0.102")),
            (180, Decimal("0.70"), Decimal("0.102")),
            (180, Decimal("0.90"), Decimal("0.109")),
            (240, Decimal("0.70"), Decimal("0.105")),
            (240, Decimal("0.90"), Decimal("0.110")),
        ),
        # Interés con días reales, capital con tasa/12, seguros dentro del pago
        convencion_interes=ConvencionDias.DIAS_REALES_360,
        convencion_pago=ConvencionDias.TASA_ENTRE_12,
        convencion_amortizacion=ConvencionDias.TASA_ENTRE_12,
        seguros_en_pago_fijo=True,
        plazos_meses=tuple(range(12, 241, 12)),  # 1 a 20 años (Param!CF52:CF71)
        aforo_max=Decimal("0.90"),                # TablaTasas!D13
        valor_minimo_inmueble=Decimal("500000"),  # Param!CM8
        # Jumbo (+0.5 % desde 10 millones) no modelado: se excluye
        monto_maximo=Decimal("9999999.99"),
        comision_apertura=Decimal("0.015"),       # Param!AL8
        comision_mensual=Decimal("250"),          # Param!AK8, IVA incluido
        # Vida 0.424‰ + ITP 0.106‰ + desempleo 0.3‰ sobre saldo (Param!D12:D14)
        seguro_vida_mensual=Decimal("0.00083"),
        # Daños 0.074364‰ mensual × 1.16 sobre 70 % del valor (Param!D8, D9)
        seguro_danos_anual=Decimal("0.00103514688"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        factor_construccion=Decimal("0.70"),
        # Tabulador de avalúo (Param!AZ8:BE17), IVA incluido
        tarifa_avaluo=_TARIFA_AVALUO_BANREGIO,
        avaluo_factor_iva=Decimal("1.16"),
        # TablAmoPagosFijos!AA8, AA10: apertura completa; avalúo, comisión
        # mensual y daños ÷ 1.16; vida, ITP y desempleo completos.
        cat_netos_de_iva=frozenset(
            {ConceptoIVA.AVALUO, ConceptoIVA.COMISION_MENSUAL, ConceptoIVA.SEGURO_DANOS}
        ),
        vigente_desde=date(2023, 12, 1),
        fuente="Cotizador BANREGIO MULTIPRODUCTO.xlsm, producto 1 Adquisición "
        "Tradicional (TablaTasas, Param, TablAmoPagosFijos). Archivo guardado "
        "2023-12-01; validado con su escenario de Mejora de Hipoteca, que usa "
        "las mismas tasas y mecánica.",
        notas="TASAS DE DICIEMBRE DE 2023: confirmar vigencia con Banregio. "
        "Seguro de vida incluye desempleo (titular asalariado); sin desempleo "
        "sería 0.53‰. Se modela la opción de 1.5 % de apertura sin "
        "penalización por prepago. No incluye créditos Jumbo (10 millones o más).",
    ),
    ProductoHipotecario(
        id="banregio-adquisicion-crecientes-2023-12",
        institucion="Banregio",
        nombre="Adquisición Tradicional (pagos crecientes)",
        # El cotizador fija el plazo en 20 años: solo se ofrece a 240 meses,
        # con la tasa del tramo de 20 años según aforo.
        tasa_anual=Decimal("0.110"),
        tabla_tasas=(
            (240, Decimal("0.70"), Decimal("0.105")),
            (240, Decimal("0.90"), Decimal("0.110")),
        ),
        convencion_interes=ConvencionDias.DIAS_REALES_360,
        convencion_pago=ConvencionDias.TASA_ENTRE_12,
        convencion_amortizacion=ConvencionDias.TASA_ENTRE_12,
        # TablAmoPagosCrec: el pago base crece cada mes; en el mes 73 se
        # recalcula sobre el saldo (Param!CU9 = −0.0011, CU10 = 0.0017).
        # Seguros y comisión van fuera del pago base.
        crecimiento_pago_mensual=(
            (1, Decimal(1) / Decimal("0.9989") - 1),
            (73, Decimal("0.0017")),
        ),
        plazos_meses=(240,),
        aforo_max=Decimal("0.90"),
        valor_minimo_inmueble=Decimal("500000"),
        monto_maximo=Decimal("9999999.99"),
        comision_apertura=Decimal("0.015"),
        comision_mensual=Decimal("250"),
        # En pagos crecientes el desempleo se cobra siempre (Z10 sin condición)
        seguro_vida_mensual=Decimal("0.00083"),
        seguro_danos_anual=Decimal("0.00103514688"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        factor_construccion=Decimal("0.70"),
        tarifa_avaluo=_TARIFA_AVALUO_BANREGIO,
        avaluo_factor_iva=Decimal("1.16"),
        # TablAmoPagosCrec!BH8, BH10: mismo tratamiento de IVA que pagos fijos
        cat_netos_de_iva=frozenset(
            {ConceptoIVA.AVALUO, ConceptoIVA.COMISION_MENSUAL, ConceptoIVA.SEGURO_DANOS}
        ),
        vigente_desde=date(2023, 12, 1),
        fuente="Cotizador BANREGIO MULTIPRODUCTO.xlsm, producto 1 Adquisición "
        "Tradicional, hoja TablAmoPagosCrec. Archivo guardado 2023-12-01; "
        "validado con su escenario capturado (tabla y CAT).",
        notas="TASAS DE DICIEMBRE DE 2023: confirmar vigencia con Banregio. "
        "Solo a 20 años: el cotizador fija ese plazo para pagos crecientes. "
        "El escenario del archivo usaba la tasa de 10 años; aquí se aplica la "
        "de 20. No incluye créditos Jumbo (10 millones o más).",
    ),
]
