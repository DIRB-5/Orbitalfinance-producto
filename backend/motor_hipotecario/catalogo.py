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

from .amortizacion import factores_crecientes
from dataclasses import replace

from .modelos import (
    AportacionExcedente,
    BaseTopeGastos,
    Destino,
    BaseSeguroDanos,
    FinanciamientoGastos,
    ConceptoIVA,
    ConvencionDias,
    ProductoHipotecario,
    ReglaAportaciones,
    RefinanciamientoInstituto,
    RequisitoCliente,
    TasaVariable,
    TipoLinea,
)

# Fecha en que se analizaron los cotizadores. Los archivos no traen fecha de
# vigencia de las condiciones.
_ANALIZADO = date(2026, 10, 22)

# Santander: el cotizador es el más reciente disponible (guardado 2026-10-23,
# etiqueta de versión 2025-6 Ro). Santander no publica tasas por destino.
_VIGENCIA_SANTANDER = (
    " Tasas del cotizador más reciente que tiene el broker (guardado el "
    "2026-10-23, aunque su versión dice 15 de diciembre de 2025). El sitio de "
    "Santander solo publica \"desde 9.90 %\" (Hipoteca Plus, consultado "
    "2026-10-25); confirmar con el ejecutivo antes de entregar una propuesta."
)

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
        # Cerrado: cargaba los montos del flujo del CAT (sin IVA) y el avalúo
        # como comisión por apertura. Lo sustituye santander-adquisicion-2025-12.
        vigente_hasta=date(2026, 10, 24),
        fuente="Cotizador Santander.xlsm, hoja CAT (escenario capturado: "
        "$1,770,000 a 300 meses). Analizado 2026-10-22.",
        notas=_SUPUESTOS + " El cotizador no trae avalúo. VERSIÓN CERRADA el "
        "2026-10-24: el pago mostrado omitía el IVA de daños y comisión, y los "
        "$7,000 son el avalúo, no comisión por apertura.",
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
    ProductoHipotecario(
        id="banorte-fovissste-para-todos-2026-02",
        institucion="Banorte",
        nombre="Hipoteca Fuerte — FOVISSSTE para todos",
        tasa_anual=Decimal("0.095"),                 # 'Tabla Parámetros'!D19, tasa única
        # Pago e interés a 30.4/360; el mes 1 cobra días reales desde la
        # cotización (Fecha Pago!L4) y paga el día 3 (B6).
        convencion_interes=ConvencionDias.DIAS_30_4_360,
        primer_periodo_dias_reales=True,
        dia_de_pago=3,
        dia_corte_primer_pago=30,                    # Fecha Pago!N2
        plazos_meses=(60, 120, 180, 240, 300),       # 'Tabla Parámetros'!W3:W7
        aforo_max=Decimal("0.95"),                   # 'Tabla Parámetros'!I51
        monto_minimo=Decimal("75000"),               # Fovissste!B6
        comision_apertura=Decimal("0"),              # H30: 0 % para FPT
        comision_mensual=Decimal("0"),               # W28: 0 para FPT
        seguro_vida_mensual=Decimal("0.0006"),       # Básico (R5); Amplio sería 0.0008583
        seguro_danos_anual=Decimal("0"),             # S3: 0 para FPT
        # Avalúo por tabulador sin IVA (L96:N104) más IVA (Simulador!L47)
        tarifa_avaluo=(
            (Decimal("0"), Decimal("3000"), Decimal("0")),
            (Decimal("1000000.01"), Decimal("5000"), Decimal("0")),
            (Decimal("3000000.01"), Decimal("8000"), Decimal("0")),
            (Decimal("5000000.01"), Decimal("15000"), Decimal("0")),
            (Decimal("7000000.01"), Decimal("17000"), Decimal("0")),
            (Decimal("10000000.01"), Decimal("25000"), Decimal("0")),
            (Decimal("20000000.01"), Decimal("30000"), Decimal("0")),
            (Decimal("30000000.01"), Decimal("0"), Decimal("1")),
        ),
        avaluo_factor_iva=Decimal("1.16"),
        # Tabla Fijos CAT!AC: avalúo sin IVA; vida completa; daños ÷ 1.16
        cat_netos_de_iva=frozenset({ConceptoIVA.AVALUO, ConceptoIVA.SEGURO_DANOS}),
        # AportPatFov: 10 % del salario por bimestre, sin tope, desde el mes 4;
        # se abona a capital y Banorte topa el capital al saldo.
        regla_aportaciones=ReglaAportaciones(
            instituto=TipoLinea.FOVISSSTE,
            porcentaje_salario=Decimal("0.10"),
            excedente=AportacionExcedente.LIMITAR,
        ),
        requiere_cofinanciamiento=True,
        vigente_desde=date(2026, 2, 3),
        fuente="Cotizador BANORTE_FOVISSSTE.xlsm, Hipoteca Fuerte, programa "
        "FOVISSSTE para todos (Simulador, Tabla Fijos, Tabla Fijos CAT, "
        "AportPatFov). Archivo guardado 2026-02-03; validado con su escenario "
        "capturado (tabla y CAT).",
        notas="Sin fecha de vigencia en el archivo (la oferta vinculante dura 20 "
        "días naturales). Seguro de vida Básico. Las aportaciones FOVISSSTE solo "
        "salen de fórmulas: el escenario del archivo no trae salario. Si una "
        "aportación excede el saldo, el archivo la pierde y descuenta el total "
        "del último pago; aquí se aplica solo lo que falta.",
    ),
    ProductoHipotecario(
        id="bx-cofinavit-2026-01",
        institucion="BX+",
        nombre="Crédito Hipotecario Cofinavit",
        # Tasa por aforo del crédito BX+ solo (Simulador!CC12): la primera
        # opción de cada tramo de VResPlus!H36:K50. El archivo ofrece otras
        # (p. ej. 9.35 % al 70 %) para "excelente historial crediticio".
        tasa_anual=Decimal("0.1030"),
        tabla_tasas=(
            (240, Decimal("0.70"), Decimal("0.0965")),
            (240, Decimal("0.80"), Decimal("0.0985")),
            (240, Decimal("0.85"), Decimal("0.1030")),
        ),
        convencion_interes=ConvencionDias.TASA_ENTRE_12,
        plazos_meses=tuple(range(12, 241, 12)),        # 1 a 20 años (D12)
        aforo_max=Decimal("0.85"),
        monto_minimo=Decimal("600000"),                  # AI15
        comision_apertura=Decimal("0.01"),               # D14, sin IVA
        comision_apertura_tope=Decimal("150000"),        # F32
        comision_mensual=Decimal("346.84"),              # 299 × 1.16 (F22)
        seguro_vida_mensual=Decimal("0.00065"),          # un asegurado (C53)
        # Daños 0.301‰ mensual × 1.16 sobre 70 % del valor (resto de la
        # República; Quintana Roo 0.52‰, Yucatán 0.34‰)
        seguro_danos_anual=Decimal("0.00418992"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        factor_construccion=Decimal("0.70"),
        tarifa_avaluo=(                                  # H20:J29, sin IVA
            (Decimal("0"), Decimal("1300"), Decimal("0")),
            (Decimal("600000.01"), Decimal("2000"), Decimal("0")),
            (Decimal("1000000.01"), Decimal("2700"), Decimal("0")),
            (Decimal("1500000.01"), Decimal("3400"), Decimal("0")),
            (Decimal("2000000.01"), Decimal("4600"), Decimal("0")),
            (Decimal("3000000.01"), Decimal("6000"), Decimal("0")),
            (Decimal("5000000.01"), Decimal("8750"), Decimal("0")),
            (Decimal("7000000.01"), Decimal("12500"), Decimal("0")),
            (Decimal("10000000.01"), Decimal("18000"), Decimal("0")),
            (Decimal("15000000.01"), Decimal("25000"), Decimal("0")),
        ),
        avaluo_factor_iva=Decimal("1.16"),
        # CAT (AJ): apertura completa; avalúo, daños y comisión sin IVA
        cat_netos_de_iva=frozenset(
            {ConceptoIVA.AVALUO, ConceptoIVA.SEGURO_DANOS, ConceptoIVA.COMISION_MENSUAL}
        ),
        # Aportaciones: el archivo no las modela. Monto según la regla de BX+
        # INFONAVIT (10 % del salario, tope 7,884.24, +3 % anual); por Ley
        # INFONAVIT 43 Bis pagan primero el crédito Cofinavit.
        regla_aportaciones=ReglaAportaciones(
            instituto=TipoLinea.INFONAVIT,
            porcentaje_salario=Decimal("0.10"),
            tope=Decimal("7884.24"),
            incremento_anual=Decimal("0.03"),
            excedente=AportacionExcedente.OMITIR,
        ),
        requiere_cofinanciamiento=True,
        requiere_credito_instituto=True,
        vigente_desde=date(2026, 1, 15),
        fuente="Cotizador BX+ COFI.xlsx (Simulador CH BX+, VResPlus). Archivo "
        "guardado 2026-01-15. SIN escenario capturado: validado contra sus "
        "fórmulas, no contra cifras del banco.",
        notas="Tasa: primera opción de cada tramo de aforo; BX+ ofrece tasas menores "
        "con excelente historial. Seguro de daños de la región 'resto de la "
        "República'. Vida para un asegurado. El archivo no trae vigencia.",
    ),
    ProductoHipotecario(
        id="bx-apoyo-infonavit-2026-01",
        institucion="BX+",
        nombre="Adquisición Apoyo Infonavit",
        # Tasa por aforo del crédito BX+ solo (Simulador!CC12): la primera
        # opción de cada tramo de VResPlus!H36:K50. El archivo ofrece otras
        # (p. ej. 9.35 % al 70 %) para "excelente historial crediticio".
        # En este archivo el tramo de 85 % devuelve error (C9 busca en
        # H36:K46): solo se ofrecen 70 % y 80 %.
        tasa_anual=Decimal("0.0985"),
        tabla_tasas=(
            (240, Decimal("0.70"), Decimal("0.0965")),
            (240, Decimal("0.80"), Decimal("0.0985")),
        ),
        convencion_interes=ConvencionDias.TASA_ENTRE_12,
        plazos_meses=tuple(range(12, 241, 12)),        # 1 a 20 años (D12)
        aforo_max=Decimal("0.80"),
        monto_minimo=Decimal("600000"),                  # AI15
        comision_apertura=Decimal("0.01"),               # D14, sin IVA
        comision_apertura_tope=Decimal("150000"),        # F32
        comision_mensual=Decimal("346.84"),              # 299 × 1.16 (F22)
        seguro_vida_mensual=Decimal("0.00065"),          # un asegurado (C53)
        # Daños 0.301‰ mensual × 1.16 sobre 70 % del valor (resto de la
        # República; Quintana Roo 0.52‰, Yucatán 0.34‰)
        seguro_danos_anual=Decimal("0.00418992"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        factor_construccion=Decimal("0.70"),
        tarifa_avaluo=(                                  # H20:J29, sin IVA
            (Decimal("0"), Decimal("1300"), Decimal("0")),
            (Decimal("600000.01"), Decimal("2000"), Decimal("0")),
            (Decimal("1000000.01"), Decimal("2700"), Decimal("0")),
            (Decimal("1500000.01"), Decimal("3400"), Decimal("0")),
            (Decimal("2000000.01"), Decimal("4600"), Decimal("0")),
            (Decimal("3000000.01"), Decimal("6000"), Decimal("0")),
            (Decimal("5000000.01"), Decimal("8750"), Decimal("0")),
            (Decimal("7000000.01"), Decimal("12500"), Decimal("0")),
            (Decimal("10000000.01"), Decimal("18000"), Decimal("0")),
            (Decimal("15000000.01"), Decimal("25000"), Decimal("0")),
        ),
        avaluo_factor_iva=Decimal("1.16"),
        # CAT (AJ): apertura completa; avalúo, daños y comisión sin IVA
        cat_netos_de_iva=frozenset(
            {ConceptoIVA.AVALUO, ConceptoIVA.SEGURO_DANOS, ConceptoIVA.COMISION_MENSUAL}
        ),
        # Simulador col. N: meses pares desde el 4, MIN(10 % salario,
        # 7,884.24), × 1.03 por año desde el mes 14; se omite si no cabe.
        regla_aportaciones=ReglaAportaciones(
            instituto=TipoLinea.INFONAVIT,
            porcentaje_salario=Decimal("0.10"),
            tope=Decimal("7884.24"),
            incremento_anual=Decimal("0.03"),
            excedente=AportacionExcedente.OMITIR,
        ),
        requiere_cofinanciamiento=True,
        excluye_credito_instituto=True,
        vigente_desde=date(2026, 1, 15),
        fuente="Cotizador BX+ INFONAVIT.xlsx (Simulador CH BX+, VResPlus). "
        "Archivo guardado 2026-01-15. SIN escenario capturado: validado contra "
        "sus fórmulas, aportaciones incluidas, no contra cifras del banco.",
        notas="Apoyo Infonavit: la subcuenta reduce el crédito y las aportaciones "
        "se abonan a capital; sin crédito del instituto. Tasa: primera opción de "
        "cada tramo de aforo. Daños de 'resto de la República'. Vida para un "
        "asegurado. El archivo no trae vigencia.",
    ),
    ProductoHipotecario(
        id="banamex-perfiles-mercado-abierto-2026-08",
        institucion="Banamex",
        nombre="Hipoteca Perfiles (Mercado abierto)",
        # Tasa por vinculación (Calculos!CO136:CO141): Mercado abierto 10.50 %
        # es la que aplica a cualquier cliente. Con relación con el banco:
        # Nómina/Portabilidad 9.25 %, Patrimonial/Privada 9.05 %, Oferta
        # preferente 10.25 %, Desarrollos o Tarjeta y depósitos 9.80 %.
        tasa_anual=Decimal("0.105"),
        convencion_interes=ConvencionDias.TASA_ENTRE_12,
        pago_por_millar_redondeado=True,                 # TablaPerfiles!S128
        plazos_meses=(120, 180, 240),                    # CN104:CQ106
        aforo_max=Decimal("0.90"),                       # CP116, perfil de riesgo muy bajo
        monto_minimo=Decimal("300000"),                  # CJ15
        monto_maximo=Decimal("20000000"),                # CJ16
        valor_minimo_inmueble=Decimal("750000"),         # CJ18; MacroPlaza 1,000,000
        comision_apertura=Decimal("0.01"),               # CH79, sin IVA
        seguro_vida_mensual=Decimal("0.000474"),         # AX16, sin extraprima
        seguro_danos_anual=Decimal("0.0036"),            # AX17: 0.0003 mensual
        base_seguro_danos=BaseSeguroDanos.MAXIMO_CONSTRUCCION_SALDO,
        factor_construccion=Decimal("0.80"),
        tarifa_avaluo=(                                  # DB69:DD74, IVA incluido
            (Decimal("0"), Decimal("3500"), Decimal("0")),
            (Decimal("1000000.01"), Decimal("5500"), Decimal("0")),
            (Decimal("3000000.01"), Decimal("7500"), Decimal("0")),
            (Decimal("5000000.01"), Decimal("10500"), Decimal("0")),
            (Decimal("8000000.01"), Decimal("15500"), Decimal("0")),
            # DD74: (valor − 10,000,000) × 1.05 / 1000 + 14,990
            (Decimal("15000000.01"), Decimal("4490"), Decimal("1.05")),
        ),
        # TablaPerfiles!AQ127: avalúo ÷ 1.16; apertura y seguros completos
        cat_netos_de_iva=frozenset({ConceptoIVA.AVALUO}),
        # Gastos notariales financiados hasta 10 % del valor (Calculos!CL67,
        # CJ67), dentro del aforo (CH97). La apertura (CH89) y el aforo de la
        # tasa (CH71) usan el crédito con gastos.
        financiamiento_gastos=FinanciamientoGastos(
            tope=Decimal("0.10"), base_tope=BaseTopeGastos.VALOR_INMUEBLE
        ),
        vigente_desde=date(2026, 8, 21),
        fuente="Cotizador BANAMEX.xlsm, hoja ADQUISICION, producto Hipoteca "
        "Perfiles (Calculos CF:DH, TablaPerfiles). Versión v.20260824, "
        "'Vigencia: Agosto 2026'. SIN escenario capturado: validado contra sus "
        "fórmulas y contra los factores al millar guardados (CR104:CR106).",
        notas="Tasa de Mercado abierto; con vinculación al banco baja hasta 9.05 %. "
        "Financia gastos notariales hasta 10 % del valor (no en Cofinavit). "
        "Seguro de vida sin extraprima (edad 65+ 0.1804 %, médica 0.0884 %, "
        "ocupacional 0.0604 %). Valor mínimo de 1,000,000 en CDMX, GDL y MTY. El "
        "avalúo es reembolsable según el banco, pero el cotizador lo incluye en "
        "el CAT.",
    ),
    ProductoHipotecario(
        id="scotiabank-7x5-adquisicion-2024-01",
        institucion="Scotiabank",
        nombre="Hipoteca 7x5 — Adquisición Tradicional",
        # Fija los primeros 5 años según plazo (Simulador!V63:V66); desde el
        # mes 61, TIIE + 4.5 con techo de 15 % (Tabla de amortizacion!P75).
        tasa_anual=Decimal("0.1075"),
        tabla_tasas=(
            (120, Decimal("0.75"), Decimal("0.10")),
            (240, Decimal("0.75"), Decimal("0.1075")),
        ),
        tasa_variable=TasaVariable(
            desde_mes=61, sobretasa=Decimal("0.045"), techo=Decimal("0.15")
        ),
        # Interés con días del mes / 360; pago al millar fijo (W63:W66) los
        # primeros 60 meses y reamortización mensual desde el 61.
        convencion_interes=ConvencionDias.DIAS_REALES_360,
        convencion_pago=ConvencionDias.TASA_ENTRE_12,
        factores_al_millar=(
            (120, Decimal("13.30")),
            (180, Decimal("11.32")),
            (240, Decimal("10.27")),
        ),
        reamortizar_mensual_desde=61,
        cortes_de_pago=(3, 17),                          # Tabla!AZ15
        # 5 años no se incluye: sin comisión por apertura y sin tramo variable
        plazos_meses=(120, 180, 240),
        aforo_max=Decimal("0.75"),                       # X33, enganche mínimo 25 %
        monto_minimo=Decimal("250000"),                  # Z33
        monto_maximo=Decimal("5000000"),                 # AA33
        valor_minimo_inmueble=Decimal("400000"),         # AB33
        comision_apertura=Decimal("0.0125"),             # V33, sin IVA
        seguro_vida_mensual=Decimal("0.0006"),           # AA43, vida y desempleo
        seguro_danos_anual=Decimal("0.00372"),           # AA44: 0.00031 mensual
        base_seguro_danos=BaseSeguroDanos.VALOR_TOTAL,
        tarifa_avaluo=(                                  # S93:U114, sin IVA
            (Decimal("0"), Decimal("1900"), Decimal("0")),
            (Decimal("500000.01"), Decimal("3300"), Decimal("0")),
            (Decimal("1000000.01"), Decimal("4500"), Decimal("0")),
            (Decimal("1500000.01"), Decimal("5750"), Decimal("0")),
            (Decimal("2000000.01"), Decimal("7000"), Decimal("0")),
            (Decimal("2500000.01"), Decimal("8200"), Decimal("0")),
            (Decimal("3000000.01"), Decimal("11000"), Decimal("0")),
            (Decimal("4000000.01"), Decimal("13900"), Decimal("0")),
            (Decimal("5000000.01"), Decimal("15500"), Decimal("0")),
            (Decimal("6000000.01"), Decimal("19000"), Decimal("0")),
            (Decimal("7000000.01"), Decimal("20000"), Decimal("0")),
            (Decimal("8000000.01"), Decimal("20100"), Decimal("0")),
            (Decimal("9000000.01"), Decimal("22500"), Decimal("0")),
            (Decimal("10000000.01"), Decimal("27000"), Decimal("0")),
            (Decimal("11000000.01"), Decimal("28000"), Decimal("0")),
            (Decimal("12000000.01"), Decimal("30000"), Decimal("0")),
            (Decimal("13000000.01"), Decimal("32000"), Decimal("0")),
            (Decimal("14000000.01"), Decimal("34000"), Decimal("0")),
            (Decimal("15000000.01"), Decimal("37000"), Decimal("0")),
            (Decimal("20000000.01"), Decimal("39000"), Decimal("0")),
            (Decimal("25000000.01"), Decimal("40000"), Decimal("0")),
        ),
        # CAT (AQ): sin IVA en ningún concepto
        cat_netos_de_iva=frozenset(),
        vigente_desde=date(2024, 1, 15),
        fuente="Cotizador SCOTIABANK Multiproducto 7x5.xlsm (Simulador, Tabla "
        "de amortizacion), versión v2024.01, guardado 2024-03-22; RECA "
        "0319-138-020519/15-00085-0124. SIN escenario capturado: validado contra "
        "sus fórmulas.",
        notas="TASAS DE MARZO DE 2024: confirmar vigencia con Scotiabank. Desde "
        "2025 los contratos nuevos no pueden referenciar la TIIE a 28 días "
        "(Banxico, Circular 3/2023): la versión vigente del 7x5 debe usar TIIE de "
        "Fondeo u otra tasa, quizá con otro margen. Tasa "
        "variable desde el mes 61 (TIIE + 4.5, techo 15 %): el costo depende del "
        "escenario de TIIE. Los factores al millar vienen escritos en el archivo. "
        "Aplica a IR 1 y 2 si el aforo pasa de 65 %. Seguros sin IVA en el archivo.",
    ),
    ProductoHipotecario(
        id="banamex-a-tu-medida-mercado-abierto-2026-08",
        institucion="Banamex",
        nombre="La Hipoteca a tu Medida (Mercado abierto)",
        tasa_anual=Decimal("0.105"),                     # CL48 = CO144, como Perfiles
        convencion_interes=ConvencionDias.TASA_ENTRE_12,
        # Pago = monto original × factor del año / 1000 (TablaATM!U129). Año 1
        # de la tabla del archivo (DJ80:DJ91, 8.88 a 10.50 %); luego × 1.02
        # redondeado a 6 decimales (DK103:DK202). Liquida en el mes 233.
        factores_al_millar_anuales=factores_crecientes(Decimal("8.88"), Decimal("0.02"), 20),
        plazos_meses=(240,),                             # CM7: solo 20 años
        aforo_max=Decimal("0.90"),
        monto_minimo=Decimal("300000"),
        monto_maximo=Decimal("7999999.99"),              # CO48: 8 millones o más, excepción
        valor_minimo_inmueble=Decimal("750000"),
        comision_apertura=Decimal("0.01"),               # CK79, sin IVA
        seguro_vida_mensual=Decimal("0.000474"),
        seguro_danos_anual=Decimal("0.0036"),
        base_seguro_danos=BaseSeguroDanos.MAXIMO_CONSTRUCCION_SALDO,
        factor_construccion=Decimal("0.80"),
        tarifa_avaluo=(
            (Decimal("0"), Decimal("3500"), Decimal("0")),
            (Decimal("1000000.01"), Decimal("5500"), Decimal("0")),
            (Decimal("3000000.01"), Decimal("7500"), Decimal("0")),
            (Decimal("5000000.01"), Decimal("10500"), Decimal("0")),
            (Decimal("8000000.01"), Decimal("15500"), Decimal("0")),
            (Decimal("15000000.01"), Decimal("4490"), Decimal("1.05")),
        ),
        cat_netos_de_iva=frozenset({ConceptoIVA.AVALUO}),  # TablaATM!AS127
        # Como Perfiles: gastos notariales hasta 10 % del valor (Calculos!CL67)
        financiamiento_gastos=FinanciamientoGastos(
            tope=Decimal("0.10"), base_tope=BaseTopeGastos.VALOR_INMUEBLE
        ),
        vigente_desde=date(2026, 8, 21),
        fuente="Cotizador BANAMEX.xlsm, hoja ADQUISICION, producto La Hipoteca a "
        "tu Medida (Calculos CL, DH103:DK202, TablaATM). Versión v.20260824. SIN "
        "escenario capturado: validado contra sus fórmulas y contra los factores "
        "por año guardados.",
        notas="Pago creciente 2 % anual sobre el monto original, solo a 20 años. "
        "Financia gastos notariales hasta 10 % del valor (no en Cofinavit). "
        "Tasa de Mercado abierto; con vinculación baja hasta 9.05 % (factor año 1 "
        "7.931667). Edad máxima del solicitante 59 años. Créditos de 8 millones o "
        "más requieren excepción.",
    ),
    ProductoHipotecario(
        id="bx-tradicional-2023-03",
        institucion="BX+",
        nombre="Crédito Hipotecario Tradicional",
        # Tasa por aforo del crédito BX+ solo (Simulador!CC12): la primera
        # opción de cada tramo de VResPlus!H36:K50. El archivo ofrece otras
        # (p. ej. 9.35 % al 70 %) para "excelente historial crediticio".
        tasa_anual=Decimal("0.11"),
        tabla_tasas=(
            (240, Decimal("0.70"), Decimal("0.102")),
            (240, Decimal("0.80"), Decimal("0.105")),
            (240, Decimal("0.85"), Decimal("0.11")),
        ),
        convencion_interes=ConvencionDias.TASA_ENTRE_12,
        plazos_meses=tuple(range(12, 241, 12)),        # 1 a 20 años (D12)
        aforo_max=Decimal("0.85"),
        monto_minimo=Decimal("600000"),                  # AI15
        comision_apertura=Decimal("0.01"),               # D14, sin IVA
        comision_apertura_tope=Decimal("150000"),        # F32
        comision_mensual=Decimal("346.84"),              # 299 × 1.16 (F22)
        seguro_vida_mensual=Decimal("0.00065"),          # un asegurado (C53)
        # Daños 0.301‰ mensual × 1.16 sobre 70 % del valor (resto de la
        # República; Quintana Roo 0.52‰, Yucatán 0.34‰)
        seguro_danos_anual=Decimal("0.00418992"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        factor_construccion=Decimal("0.70"),
        tarifa_avaluo=(                                  # H20:J29, sin IVA
            (Decimal("0"), Decimal("1300"), Decimal("0")),
            (Decimal("600000.01"), Decimal("2000"), Decimal("0")),
            (Decimal("1000000.01"), Decimal("2700"), Decimal("0")),
            (Decimal("1500000.01"), Decimal("3400"), Decimal("0")),
            (Decimal("2000000.01"), Decimal("4600"), Decimal("0")),
            (Decimal("3000000.01"), Decimal("6000"), Decimal("0")),
            (Decimal("5000000.01"), Decimal("8750"), Decimal("0")),
            (Decimal("7000000.01"), Decimal("12500"), Decimal("0")),
            (Decimal("10000000.01"), Decimal("18000"), Decimal("0")),
            (Decimal("15000000.01"), Decimal("25000"), Decimal("0")),
        ),
        avaluo_factor_iva=Decimal("1.16"),
        # CAT (AJ): apertura completa; avalúo, daños y comisión sin IVA
        cat_netos_de_iva=frozenset(
            {ConceptoIVA.AVALUO, ConceptoIVA.SEGURO_DANOS, ConceptoIVA.COMISION_MENSUAL}
        ),
        vigente_desde=date(2023, 3, 28),
        fuente="Cotizador BX+ TRADICIONAL.xlsx (Simulador CH BX+, VResPlus), "
        "guardado 2023-03-28. SIN escenario capturado: validado contra sus "
        "fórmulas, no contra cifras del banco.",
        notas="TASAS DE MARZO DE 2023: confirmar vigencia con BX+. Tasa: primera "
        "opción de cada tramo de aforo (10.20 % / 10.50 % / 11.00 %); el archivo "
        "ofrece también 10.80 % y 11.50 %. Aforo mayor a 80 % sujeto a "
        "autorización. Daños de 'resto de la República'. Vida para un asegurado.",
    ),
    ProductoHipotecario(
        id="banorte-hipoteca-fuerte-2026-06",
        institucion="Banorte",
        nombre="Hipoteca Fuerte",
        # Tasa por perfil según la evaluación del crédito ('Tabla Parámetros'
        # D3:D5): Premium 8.80 %, Mínima 9.75 %, Baja 10.80 %. Se usa Mínima,
        # la de referencia del producto (Sheet1!AB2).
        tasa_anual=Decimal("0.0975"),
        convencion_interes=ConvencionDias.DIAS_30_4_360,
        primer_periodo_dias_reales=True,
        dia_de_pago=3,
        dia_corte_primer_pago=30,
        plazos_meses=tuple(range(60, 241, 12)),          # W3:W18
        aforo_max=Decimal("0.90"),                       # I47
        monto_minimo=Decimal("75000"),                   # C92 (no lo valida el archivo)
        valor_minimo_inmueble=Decimal("350000"),         # C91 (idem)
        comision_apertura=Decimal("0.01"),               # J30, sin IVA
        comision_mensual=Decimal("299"),                 # comisión diferida, sin IVA
        seguro_vida_mensual=Decimal("0.0006"),           # Básico (R5)
        seguro_danos_anual=Decimal("0.00336"),           # S5: 0.00028 mensual
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        factor_construccion=Decimal("0.70"),             # valor destructible N13
        tarifa_avaluo=(
            (Decimal("0"), Decimal("3000"), Decimal("0")),
            (Decimal("1000000.01"), Decimal("5000"), Decimal("0")),
            (Decimal("3000000.01"), Decimal("8000"), Decimal("0")),
            (Decimal("5000000.01"), Decimal("15000"), Decimal("0")),
            (Decimal("7000000.01"), Decimal("17000"), Decimal("0")),
            (Decimal("10000000.01"), Decimal("25000"), Decimal("0")),
            (Decimal("20000000.01"), Decimal("30000"), Decimal("0")),
            (Decimal("30000000.01"), Decimal("0"), Decimal("1")),
        ),
        avaluo_factor_iva=Decimal("1.16"),
        # Tabla Fijos CAT!AC: avalúo sin IVA, daños ÷ 1.16; vida y comisión
        # diferida completas; apertura completa.
        cat_netos_de_iva=frozenset({ConceptoIVA.AVALUO, ConceptoIVA.SEGURO_DANOS}),
        vigente_desde=date(2026, 6, 15),
        fuente="Cotizador BANORTE_SIMULADOR_UNIVERSAL.xlsm, Hipoteca Fuerte, "
        "programa Tradicional (Simulador, Tabla Fijos, Tabla Fijos CAT). Guardado "
        "2026-06-15; validado con su escenario capturado (perfil Premium 8.80 %, "
        "tabla y CAT).",
        notas="La tasa depende del perfil que asigne Banorte tras evaluar el crédito: "
        "8.80 % / 9.75 % / 10.80 %; aquí la de referencia 9.75 %. Seguro de vida "
        "Básico (Amplio 0.0858 %). Primer mes irregular desde la cotización.",
    ),
    ProductoHipotecario(
        id="afirme-adquisicion-2026-07",
        institucion="Afirme",
        nombre="Multiproductos — Adquisición (pagos fijos)",
        # 'Parametro Destino'!B32:F43, calificación A-BB sin nómina Afirme:
        # 10.05 % con aforo ≤ 80 %, 10.60 % arriba (15 y 20 años). Con nómina y
        # hasta 5 millones a 15 años: 9.80 % / 9.80 %; calificación AA desde 9.60 %.
        tasa_anual=Decimal("0.106"),
        tabla_tasas=(
            (240, Decimal("0.80"), Decimal("0.1005")),
            (240, Decimal("0.90"), Decimal("0.106")),
        ),
        # Interés y cuota con días entre fechas de pago (día 4); el mes 1 solo
        # paga intereses y la vida va dentro de la cuota (TAF!F:O).
        convencion_interes=ConvencionDias.DIAS_ENTRE_PAGOS_360,
        convencion_pago=ConvencionDias.DIAS_ENTRE_PAGOS_360,
        primer_pago_solo_intereses=True,
        vida_en_pago_fijo=True,
        dia_de_pago=4,
        dia_corte_primer_pago=20,                        # TAF!C10: apertura > 19
        recorrer_primer_pago_un_mes=True,
        plazos_meses=tuple(range(60, 241, 12)),          # 5 a 20 años
        aforo_max=Decimal("0.90"),                       # E10, tasas ≥ 9.5 %
        monto_minimo=Decimal("200000"),                  # C9 (informativo en el archivo)
        comision_apertura=Decimal("0.01"),               # D14: 0 % con nómina ≤ 15 años
        # Comisión 399 + IVA más seguro de interiores 98 (IVA incluido): ambos
        # entran al CAT sin IVA (399 + 84.48).
        comision_mensual=Decimal("560.84"),
        seguro_vida_mensual=Decimal("0.0008"),           # FACTOR_SEG_DEUD
        # Daños: 0.7·valor·1.1·1.0802/12000, más IVA
        seguro_danos_anual=Decimal("0.0013783352"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        factor_construccion=Decimal("0.70"),
        seguro_desempleo_pct=Decimal("0.0098"),          # C35, más IVA
        seguro_desempleo_con_iva=True,
        # Avalúo al millar sin mínimo, como lo usa el CAT (TAF!K7)
        tarifa_avaluo=(
            (Decimal("0"), Decimal("0"), Decimal("3")),
            (Decimal("1000000.01"), Decimal("0"), Decimal("2.5")),
            (Decimal("5000000.01"), Decimal("0"), Decimal("2")),
            (Decimal("10000000.01"), Decimal("0"), Decimal("1.75")),
            (Decimal("20000000.01"), Decimal("0"), Decimal("1.5")),
        ),
        cat_netos_de_iva=frozenset({
            ConceptoIVA.COMISION_MENSUAL, ConceptoIVA.SEGURO_DANOS, ConceptoIVA.SEGURO_DESEMPLEO,
        }),
        vigente_desde=date(2026, 7, 6),
        fuente="Cotizador AFIRME_MULTIPRODUCTOS.xlsm (Simulación, Parametro Destino, "
        "Parametros Fijo, Tabla Amortización Fijo), versión BAF-040-2607-06, "
        "guardado 2026-07-06; validado con su escenario capturado (tabla y CAT).",
        notas="Tasa por calificación del banco (AA / A-BB / B-CC-C): aquí A-BB sin "
        "nómina Afirme. Con nómina Afirme baja la tasa y la apertura es 0 % a 15 "
        "años o menos. El primer mes paga solo intereses. Incluye seguro de "
        "desempleo (0.98 % del pago) e interiores ($98). El avalúo mostrado al "
        "cliente tiene mínimo (p. ej. $2,000); el CAT usa el factor sin mínimo.",
    ),
]


# ---------------------------------------------------------------------------
# Sustitución de hipoteca: variantes de los productos de adquisición
# ---------------------------------------------------------------------------
_POR_ID = {p.id: p for p in CATALOGO}

# Santander Adquisición corregido (nueva versión de santander-2026-10)
CATALOGO.append(
    replace(
        _POR_ID["santander-2026-10"],
        id="santander-adquisicion-2025-12",
        nombre="Crédito hipotecario Adquisición (mercado abierto)",
        # Oferta "Ninguno", perfiles 4–5 (Adm!CA8:CA9); perfil 3: 10.95 %,
        # 2: 12.25 %, 1: 13.25 %. La oferta Asalariados y Hipoteca Plus bajan
        # la tasa con nómina (el escenario capturado usa 9.5 %).
        tasa_anual=Decimal("0.1025"),
        # Adm!E112: 7 a 15 años y 20; 25 años solo con oferta Asalariados
        plazos_meses=tuple(range(84, 181, 12)) + (240,),
        aforo_max=Decimal("0.90"),                       # perfil 4–5 asalariado (EH8:EH9)
        monto_minimo=Decimal("100000"),                  # Adm!Z3
        valor_minimo_inmueble=Decimal("250000"),         # Adm!AA3
        comision_apertura=Decimal("0"),                  # Adm!B112 vacía → P4 = 0
        comision_apertura_monto=None,
        comision_mensual=Decimal("406"),                 # 350 + IVA (C112, Captura!J88)
        # Daños: valor × 0.70 × 0.0003 mensual, IVA incluido (Captura!I88)
        seguro_danos_monto_mensual=None,
        seguro_danos_anual=Decimal("0.0036"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        factor_construccion=Decimal("0.70"),
        # Avalúo por tabulador del valor, IVA incluido (Adm!L7:N21, K4)
        tarifa_avaluo=(
            (Decimal("0"), Decimal("2000"), Decimal("0")),
            (Decimal("500000.01"), Decimal("3000"), Decimal("0")),
            (Decimal("1000000.01"), Decimal("4500"), Decimal("0")),
            (Decimal("1500000.01"), Decimal("6000"), Decimal("0")),
            (Decimal("2000000.01"), Decimal("7000"), Decimal("0")),
            (Decimal("2500000.01"), Decimal("9000"), Decimal("0")),
            (Decimal("3000000.01"), Decimal("10000"), Decimal("0")),
            (Decimal("3500000.01"), Decimal("11000"), Decimal("0")),
            (Decimal("4000000.01"), Decimal("13500"), Decimal("0")),
            (Decimal("4500000.01"), Decimal("14000"), Decimal("0")),
            (Decimal("5500000.01"), Decimal("17000"), Decimal("0")),
            (Decimal("6000000.01"), Decimal("19000"), Decimal("0")),
            (Decimal("6500000.01"), Decimal("20000"), Decimal("0")),
            (Decimal("8000000.01"), Decimal("22000"), Decimal("0")),
            (Decimal("10000000.01"), Decimal("24000"), Decimal("0")),
        ),
        # CAT!L5, H25, I25: avalúo, daños y comisión ÷ 1.16 (como HSBC)
        cat_netos_de_iva=frozenset({
            ConceptoIVA.AVALUO, ConceptoIVA.SEGURO_DANOS, ConceptoIVA.COMISION_MENSUAL,
        }),
        vigente_desde=date(2026, 10, 25),
        vigente_hasta=None,
        fuente="Cotizador Santander.xlsm (Adm, Cal, Captura, CAT), versión 2025-6 Ro "
        "(15 diciembre 2025). Validado con su escenario capturado ($1,770,000 a 300 "
        "meses, oferta Asalariados 9.5 %): pago al cliente (Captura!L88) y CAT "
        "(CAT!E20).",
        notas="Tasa de mercado abierto (oferta Ninguno) para perfiles 4 y 5; perfil 3 "
        "10.95 %, 2 12.25 %, 1 13.25 %. Con nómina (Asalariados, Hipoteca Plus) baja "
        "la tasa y se abre el plazo de 25 años. Aforo de 90 % para asalariados "
        "perfil 4–5 (75 % a 85 % en los demás). Seguro de vida para dos "
        "intervinientes. Sustituye a santander-2026-10 (cerrado el 2026-10-24)."
        + _VIGENCIA_SANTANDER,
    )
)
_POR_ID = {p.id: p for p in CATALOGO}

CATALOGO += [
    replace(
        _POR_ID["banregio-adquisicion-2023-12"],
        id="banregio-mejora-hipoteca-2023-12",
        nombre="Mejora de Hipoteca (pagos fijos)",
        destino=Destino.SUSTITUCION,
        # Mismas tasas (TablaTasas, filas de Mejora) y mecánica que adquisición
        fuente="Cotizador BANREGIO MULTIPRODUCTO.xlsm, producto 4 Mejora de "
        "Hipoteca (TablaTasas, Param, TablAmoPagosFijos). Archivo guardado "
        "2023-12-01; validado con su escenario capturado, que es de este producto.",
        notas="TASAS DE DICIEMBRE DE 2023: confirmar vigencia con Banregio. Solo "
        "pagos fijos. Seguro de vida con desempleo (titular asalariado).",
    ),
    replace(
        _POR_ID["banamex-perfiles-mercado-abierto-2026-08"],
        id="banamex-cambia-tu-hipoteca-mercado-abierto-2026-08",
        nombre="Cambia tu Hipoteca (Mercado abierto)",
        destino=Destino.SUSTITUCION,
        tasa_anual=Decimal("0.102"),                     # BG20, Mercado abierto
        comision_apertura=Decimal("0"),                  # AX77 = 0
        # Derechos e impuestos financiados hasta 5 % del saldo (AY76, AX76),
        # dentro del aforo (AX58); apertura sobre el total (AX64).
        financiamiento_gastos=FinanciamientoGastos(
            tope=Decimal("0.05"), base_tope=BaseTopeGastos.MONTO_CREDITO
        ),
        # Avalúo gratis abajo de 15 millones; arriba, BP9 (IVA incluido)
        tarifa_avaluo=(
            (Decimal("0"), Decimal("0"), Decimal("0")),
            (Decimal("15000000.01"), Decimal("-11010"), Decimal("1.05")),
        ),
        fuente="Cotizador BANAMEX.xlsm, hoja Cambia Tu Hipoteca (Calculos AW:CA, "
        "TablaCTH). Versión v.20260824. SIN escenario capturado: validado contra "
        "sus fórmulas.",
        notas="Tasa de Mercado abierto; con vinculación 8.95 %–9.50 %. Sin comisión "
        "por apertura y avalúo gratis abajo de 15 millones. Financia derechos e "
        "impuestos hasta 5 % del saldo; SUPUESTO: el tope se aplica a todos los "
        "gastos notariales del escenario. El modo "
        "'Mantener mensualidad' (pagar lo mismo y acortar plazo) no se modela.",
    ),
    replace(
        _POR_ID["bx-cofinavit-2026-01"],
        id="bx-mejora-tu-hipoteca-2026-01",
        nombre="Mejora tu Hipoteca",
        destino=Destino.SUSTITUCION,
        comision_apertura=Decimal("0"),                  # D14
        comision_apertura_tope=None,
        monto_minimo=Decimal("400000"),                  # D22, sin los gastos (AI15)
        # Gastos notariales financiados sin tope porcentual (D29, H25):
        # VResPlus!F11 = D22 + H25; aforo y tramo de tasa con los gastos.
        financiamiento_gastos=FinanciamientoGastos(tope=None),
        regla_aportaciones=None,
        requiere_cofinanciamiento=False,
        requiere_credito_instituto=False,
        fuente="Cotizador BX+ MEJORA TU HIPOTECA.xlsx (Simulador CH BX+, VResPlus), "
        "guardado 2026-01-15. SIN escenario capturado: validado contra sus fórmulas.",
        notas="Mismas tasas por aforo que Cofinavit (primera opción de cada tramo). "
        "Sin comisión por apertura. Financia gastos notariales sin tope porcentual; "
        "SUPUESTO: hasta el aforo máximo (el archivo solo avisa si lo rebasa). Daños de 'resto de la República'. Vida para un asegurado.",
    ),
]

CATALOGO += [
    replace(
        _POR_ID["banorte-hipoteca-fuerte-2026-06"],
        id="banorte-mejora-hipoteca-2026-06",
        nombre="Mejora de Hipoteca",
        destino=Destino.SUSTITUCION,
        comision_apertura=Decimal("0"),                  # Carátula!L26
        comision_investigacion=Decimal("750"),           # gastos de aprobación (L30)
        aforo_max=Decimal("0.85"),                       # Catálogos!K16
        cat_netos_de_iva=frozenset(
            {ConceptoIVA.AVALUO, ConceptoIVA.SEGURO_DANOS, ConceptoIVA.INVESTIGACION}
        ),
        fuente="Cotizador BANORTE_MEJORA_MAS_LIQUIDEZ.xlsx, tabla de Mejora de "
        "Hipoteca (Carátula, CAT). Guardado 2026-06-09; validado con su escenario "
        "capturado (perfil 8.80 %, tabla y CAT).",
        notas="Tasa por perfil 8.80 % / 9.75 % / 10.80 %; aquí la de referencia "
        "9.75 %. Sin comisión por apertura; gastos de aprobación $750. Primer mes "
        "irregular desde la cotización.",
    ),
    replace(
        _POR_ID["scotiabank-7x5-adquisicion-2024-01"],
        id="scotiabank-7x5-pasivo-hipotecario-2024-01",
        nombre="Hipoteca 7x5 — Pasivo Hipotecario",
        destino=Destino.SUSTITUCION,
        comision_apertura=Decimal("0.015"),              # S33:AE38, programa 4
        # Gastos notariales financiados hasta 6 % del crédito dentro del aforo
        # (Simulador!I29); la comisión sigue sobre el crédito sin gastos (O32).
        financiamiento_gastos=FinanciamientoGastos(
            tope=Decimal("0.06"), apertura_y_aforo_sobre_total=False
        ),
        monto_minimo=Decimal("125000"),
        valor_minimo_inmueble=None,
        tarifa_avaluo=(),                                # O31 = 0
        avaluo=Decimal("0"),
        fuente="Cotizador SCOTIABANK Pago de pasivos 7x5.xlsm, programa 4 Pasivo "
        "Hipotecario (mismo motor que Multiproducto 7x5). v2024.01, guardado "
        "2024-03-22. SIN escenario capturado: validado contra sus fórmulas.",
        notas="TASAS DE MARZO DE 2024 y referencia TIIE 28 que ya no se permite en "
        "contratos nuevos: confirmar condiciones con Scotiabank. Apertura 1.5 %, "
        "sin avalúo; financia gastos notariales hasta 6 % del crédito.",
    ),
    ProductoHipotecario(
        id="afirme-terreno-90-2026-09",
        institucion="Afirme",
        nombre="Terreno 90",
        destino=Destino.TERRENO,
        tasa_anual=Decimal("0.108"),                     # 'Parametro Destino'!M38
        convencion_interes=ConvencionDias.DIAS_ENTRE_PAGOS_360,
        convencion_pago=ConvencionDias.DIAS_ENTRE_PAGOS_360,
        primer_pago_solo_intereses=True,
        vida_en_pago_fijo=True,
        dia_de_pago=4,
        dia_corte_primer_pago=20,
        recorrer_primer_pago_un_mes=True,
        plazos_meses=tuple(range(60, 181, 12)),          # 5 a 15 años
        aforo_max=Decimal("0.90"),
        monto_minimo=Decimal("200000"),
        comision_apertura=Decimal("0.01"),
        comision_mensual=Decimal("462.84"),              # 399 + IVA, sin interiores
        seguro_vida_mensual=Decimal("0.0008"),
        seguro_desempleo_pct=Decimal("0.0098"),
        seguro_desempleo_con_iva=True,
        tarifa_avaluo=(
            (Decimal("0"), Decimal("0"), Decimal("3")),
            (Decimal("1000000.01"), Decimal("0"), Decimal("2.5")),
            (Decimal("5000000.01"), Decimal("0"), Decimal("2")),
            (Decimal("10000000.01"), Decimal("0"), Decimal("1.75")),
            (Decimal("20000000.01"), Decimal("0"), Decimal("1.5")),
        ),
        cat_netos_de_iva=frozenset({ConceptoIVA.COMISION_MENSUAL, ConceptoIVA.SEGURO_DESEMPLEO}),
        vigente_desde=date(2026, 9, 23),
        fuente="Cotizador AFIRME_TERRENO_90.xlsm (Tabla Amortización Fijo, Tabla "
        "Fijo), versión BAF-040-2607-06, guardado 2026-09-23; validado con su "
        "escenario capturado (tabla y CAT de los pagos cobrados).",
        notas="El CAT que publica el archivo (15.85 % en su ejemplo) incluye seguro "
        "de daños e interiores que el pago no cobra; aquí el CAT es el de lo "
        "cobrado (15.04 %). Primer mes solo intereses. Desempleo 0.98 % del pago.",
    ),
    replace(
        _POR_ID["banregio-adquisicion-2023-12"],
        id="banregio-terreno-2023-12",
        nombre="Terreno (pagos fijos)",
        destino=Destino.TERRENO,
        # TablaTasas productos 6 / 8 por plazo y aforo
        tasa_anual=Decimal("0.115"),
        tabla_tasas=(
            (120, Decimal("0.70"), Decimal("0.1005")),
            (120, Decimal("0.90"), Decimal("0.1065")),
            (180, Decimal("0.70"), Decimal("0.1065")),
            (180, Decimal("0.90"), Decimal("0.1135")),
            (240, Decimal("0.70"), Decimal("0.11")),
            (240, Decimal("0.90"), Decimal("0.115")),
        ),
        seguro_danos_anual=Decimal("0"),                 # X8 = "No" para 6 / 8
        valor_minimo_inmueble=Decimal("500000"),         # CM13 (Terreno Plus 700,000)
        fuente="Cotizador BANREGIO MULTIPRODUCTO.xlsm, producto 6 Terreno (TablaTasas, "
        "Param, TablAmoPagosFijos). Archivo guardado 2023-12-01. Sin escenario "
        "capturado de terreno: misma mecánica validada que adquisición, sin daños.",
        notas="TASAS DE DICIEMBRE DE 2023: confirmar vigencia con Banregio. Sin seguro "
        "de daños. Seguro de vida con desempleo (titular asalariado).",
    ),
    replace(
        _POR_ID["banorte-hipoteca-fuerte-2026-06"],
        id="banorte-terreno-urbanizado-2026-06",
        nombre="Terreno Urbanizado",
        destino=Destino.TERRENO,
        tasa_anual=Decimal("0.1068"),                    # 'Tabla Parámetros'!C15
        tabla_tasas=(
            (120, Decimal("0.70"), Decimal("0.1018")),
            (180, Decimal("0.70"), Decimal("0.1068")),
        ),
        plazos_meses=tuple(range(60, 181, 12)),
        aforo_max=Decimal("0.70"),                       # I64
        comision_apertura=Decimal("0"),                  # H38 (la documentación dice 1.5 %)
        comision_mensual=Decimal("250"),
        comision_investigacion=Decimal("500"),           # Y23, IVA incluido
        seguro_danos_anual=Decimal("0"),
        cat_netos_de_iva=frozenset({ConceptoIVA.AVALUO, ConceptoIVA.INVESTIGACION}),
        valor_minimo_inmueble=None,
        monto_minimo=None,
        fuente="Cotizador BANORTE_SIMULADOR_UNIVERSAL.xlsm, destino Terreno Urbanizado. "
        "Guardado 2026-06-15. Sin escenario capturado de terreno: mecánica de "
        "Hipoteca Fuerte (validada) con los parámetros de terreno.",
        notas="Apertura 0 % según la fórmula; las tablas de documentación del archivo "
        "dicen 1.5 %. El resumen del archivo suma IVA de intereses a la mensualidad "
        "pero la tabla y el CAT no; aquí sin IVA. Sin seguro de daños.",
    ),
]


# ---------------------------------------------------------------------------
# Liquidez: efectivo con la vivienda en garantía. Ningún cotizador trae un
# escenario de liquidez capturado: mecánica validada de cada banco con los
# parámetros de liquidez de su archivo.
# ---------------------------------------------------------------------------
CATALOGO += [
    replace(
        _POR_ID["banorte-hipoteca-fuerte-2026-06"],
        id="banorte-liquidez-2026-06",
        nombre="Liquidez",
        destino=Destino.LIQUIDEZ,
        tasa_anual=Decimal("0.1299"),                    # 'Tabla Parámetros'!C14
        plazos_meses=tuple(range(60, 181, 12)),
        aforo_max=Decimal("0.70"),                       # I63
        comision_apertura=Decimal("0.0174"),             # 1.5 % + IVA (L46)
        comision_mensual=Decimal("360"),
        comision_investigacion=Decimal("500"),
        iva_sobre_intereses=True,                        # Tabla Fijos!I: siempre en liquidez
        cat_netos_de_iva=frozenset({
            ConceptoIVA.AVALUO, ConceptoIVA.SEGURO_DANOS, ConceptoIVA.INVESTIGACION,
            ConceptoIVA.COMISION_APERTURA,
        }),
        fuente="Cotizador BANORTE_SIMULADOR_UNIVERSAL.xlsm, destino Liquidez. Guardado "
        "2026-06-15. Sin escenario capturado: mecánica validada de Hipoteca Fuerte "
        "con los parámetros de liquidez.",
        notas="IVA sobre intereses en el pago (no en el CAT). Apertura 1.5 % + IVA, "
        "comisión diferida $360, gastos de aprobación $500.",
    ),
    replace(
        _POR_ID["banamex-perfiles-mercado-abierto-2026-08"],
        id="banamex-liquidez-mercado-abierto-2026-08",
        nombre="Hipoteca de Liquidez (Mercado abierto)",
        destino=Destino.LIQUIDEZ,
        financiamiento_gastos=None,                      # EK5 sin uso
        tasa_anual=Decimal("0.13"),                      # DX84:DY87, Mercado abierto
        aforo_max=Decimal("0.65"),                       # ED85:ED87
        monto_maximo=Decimal("8000000"),                 # DR16
        comision_apertura=Decimal("0.0116"),             # 1 % + IVA (DR67)
        iva_sobre_intereses=True,
        iva_intereses_inflacion=Decimal("0.04"),         # TablaLiquidez!AE
        cat_netos_de_iva=frozenset({ConceptoIVA.AVALUO, ConceptoIVA.COMISION_APERTURA}),
        fuente="Cotizador BANAMEX.xlsm, hoja Liquidez (Calculos DQ:EQ, TablaLiquidez). "
        "Versión v.20260824. SIN escenario capturado: mecánica validada de Perfiles "
        "con los parámetros de liquidez.",
        notas="Tasa de Mercado abierto; con vinculación 11.75 %–12.25 %. IVA solo sobre "
        "el interés real (inflación de 4 %), en el pago y no en el CAT. Ingreso "
        "mínimo $35,000 (no modelado).",
    ),
    replace(
        _POR_ID["bx-tradicional-2023-03"],
        id="bx-liquidez-2022-10",
        nombre="Liquidez",
        destino=Destino.LIQUIDEZ,
        tasa_anual=Decimal("0.147"),                     # VResPlus!I44 (o 14.90 %)
        tabla_tasas=(),
        plazos_meses=tuple(range(12, 121, 12)),          # 1 a 10 años
        aforo_max=Decimal("0.50"),                       # D14
        monto_minimo=Decimal("500000"),
        monto_maximo=Decimal("4000000"),
        valor_minimo_inmueble=Decimal("2500000"),        # D19
        comision_apertura=Decimal("0.0232"),             # 2 % + IVA, sin tope (F31, F33)
        comision_apertura_tope=None,
        cat_netos_de_iva=frozenset({
            ConceptoIVA.AVALUO, ConceptoIVA.SEGURO_DANOS, ConceptoIVA.COMISION_MENSUAL,
            ConceptoIVA.COMISION_APERTURA,
        }),
        vigente_desde=date(2022, 10, 25),
        fuente="Cotizador BX+ LIQUIDEZ.xlsx (Simulador M_A, VResPlus), guardado "
        "2022-10-25. SIN escenario capturado: validado contra sus fórmulas.",
        notas="TASAS DE OCTUBRE DE 2022: confirmar vigencia con BX+. Sin IVA de "
        "intereses en el pago. Valor mínimo del inmueble $2.5 millones.",
    ),
    replace(
        _POR_ID["banregio-adquisicion-2023-12"],
        id="banregio-liquidez-2023-12",
        nombre="Liquidez",
        destino=Destino.LIQUIDEZ,
        tasa_anual=Decimal("0.13"),
        tabla_tasas=(                                    # TablaTasas D31 / D46 / D61
            (120, Decimal("0.50"), Decimal("0.1225")),
            (180, Decimal("0.50"), Decimal("0.125")),
            (240, Decimal("0.50"), Decimal("0.13")),
        ),
        aforo_max=Decimal("0.50"),
        iva_sobre_intereses=True,                        # G = interés × 1.16 (A2 = 15)
        iva_intereses_en_cat=True,                       # AA usa G
        fuente="Cotizador BANREGIO MULTIPRODUCTO.xlsm, producto 15 Liquidez. Archivo "
        "guardado 2023-12-01. Sin escenario capturado de liquidez: misma mecánica "
        "validada que adquisición, con IVA de intereses.",
        notas="TASAS DE DICIEMBRE DE 2023: confirmar vigencia con Banregio. El IVA de "
        "intereses entra al pago y al CAT. El archivo divide todos los seguros entre "
        "1.16 en el CAT de liquidez (probable error); aquí solo el de daños.",
    ),
    replace(
        _POR_ID["scotiabank-7x5-adquisicion-2024-01"],
        id="scotiabank-liquidez-libre-7x5-2024-01",
        nombre="Liquidez Libre 7x5",
        destino=Destino.LIQUIDEZ,
        tasa_anual=Decimal("0.14"),                      # AA59
        tabla_tasas=(),
        tasa_variable=None,
        reamortizar_mensual_desde=None,
        factores_al_millar=((60, Decimal("23.4")),),
        plazos_meses=(60,),
        aforo_max=Decimal("0.75"),
        monto_minimo=Decimal("100000"),
        monto_maximo=Decimal("2500000"),
        valor_minimo_inmueble=Decimal("1000000"),
        comision_apertura=Decimal("0"),
        iva_sobre_intereses=True,
        tarifa_avaluo=(                                  # tarifa TopUp / LiqLibre
            (Decimal("0"), Decimal("1253"), Decimal("0")),
            (Decimal("500000.01"), Decimal("1740"), Decimal("0")),
            (Decimal("1000000.01"), Decimal("2784"), Decimal("0")),
            (Decimal("2000000.01"), Decimal("4663"), Decimal("0")),
            (Decimal("3000000.01"), Decimal("5000"), Decimal("0")),
        ),
        fuente="Cotizador SCOTIABANK Liquidez Libre 7x5.xlsm (motor 7x5). v2024.01, "
        "guardado 2024-03-22. SIN escenario capturado: validado contra sus fórmulas.",
        notas="TASAS DE MARZO DE 2024: confirmar vigencia con Scotiabank. Solo 5 años, "
        "tasa fija. IVA de intereses en el pago, no en el CAT. Valora y Pagos "
        "Oportunos están aparte (Liquidez Libre).",
    ),
]


# ---------------------------------------------------------------------------
# Scotiabank Valora y Pagos Oportunos (tasa fija, sin tramo variable)
# ---------------------------------------------------------------------------
# Comparten el motor del 7x5: interés con días del mes / 360, pago al millar
# escrito en el archivo, cortes de pago 3 y 17, vida 0.6 al millar sobre saldo
# y daños 0.31 al millar mensual sobre el valor. El pago no se recalcula: al
# bajar la tasa (Pagos Oportunos) o crecer el pago (Valora) el crédito se
# liquida antes del plazo. Ninguno de los dos archivos trae escenario
# capturado: validados contra sus fórmulas.

_SCOTIA_PASIVOS = replace(
    next(p for p in CATALOGO if p.id == "scotiabank-7x5-pasivo-hipotecario-2024-01"),
    tasa_anual=Decimal("0.1025"),
    tabla_tasas=(),
    tasa_variable=None,
    reamortizar_mensual_desde=None,
    aforo_max=Decimal("0.95"),                           # Simulador!V10
    comision_apertura=Decimal("0"),                      # V12
    monto_minimo=None,
    monto_maximo=None,
    valor_minimo_inmueble=None,                          # F11 apunta a V5, vacía
)

_SCOTIA_LIQUIDEZ = replace(
    next(p for p in CATALOGO if p.id == "scotiabank-liquidez-libre-7x5-2024-01"),
    aforo_max=Decimal("0.70"),                           # V34
    comision_apertura=Decimal("0.0232"),                 # 2 % + IVA (T34)
    cat_netos_de_iva=frozenset({ConceptoIVA.COMISION_APERTURA}),  # CAT sin IVA
)


def _po_liquidez(plazo, factor, tasas, columna):
    """Liquidez Libre Pagos Oportunos: la tasa baja cada año hasta el quinto."""
    return replace(
        _SCOTIA_LIQUIDEZ,
        id=f"scotiabank-liquidez-libre-pagos-oportunos-{plazo // 12}-2024-01",
        nombre=f"Liquidez Libre Pagos Oportunos {plazo // 12} años",
        tasa_anual=tasas[0],
        tasas_escalonadas=tuple(zip((13, 25, 37, 49), tasas[1:])),
        factores_al_millar=((plazo, factor),),
        plazos_meses=(plazo,),
        fuente="Cotizador SCOTIABANK Liquidez Libre.xlsm, hojas Simulador Pagos "
        f"Oportunos y Tabla Pagos Oportunos (tasas {columna}, factor AC34:AE34). "
        "v2024.01, RECA 0319-138-027734/14-00093-0124 (2024-01-15). SIN escenario "
        "capturado: validado contra sus fórmulas.",
        notas="TASAS DE ENERO DE 2024: confirmar vigencia con Scotiabank. La tasa "
        "baja cada año suponiendo pagos puntuales, como en el cotizador; con atrasos "
        "no baja. IVA de intereses en el pago, no en el CAT."
        + (" SUPUESTO: no se cobra la «Com. Aut. Dif.» de $580 mensuales que la hoja "
           "suma al pago solo a 10 años (Z62) y deja fuera del CAT; parece residuo "
           "de una versión anterior. Confirmar con Scotiabank." if plazo == 120 else ""),
    )


CATALOGO += [
    replace(
        _SCOTIA_PASIVOS,
        id="scotiabank-pasivos-pagos-oportunos-2024-01",
        nombre="Pago de Pasivos — Pagos Oportunos",
        # La tasa baja cada año: 10.25, 10.05, 9.85, 9.65 y 9.50 % desde el
        # quinto (Simulador!Z16:AD23, igual en los cuatro plazos).
        tasas_escalonadas=(
            (13, Decimal("0.1005")),
            (25, Decimal("0.0985")),
            (37, Decimal("0.0965")),
            (49, Decimal("0.095")),
        ),
        factores_al_millar=(                             # N13:Q13
            (84, Decimal("16.82")),
            (120, Decimal("13.45")),
            (180, Decimal("11.00")),
            (240, Decimal("9.92")),
        ),
        plazos_meses=(84, 120, 180, 240),
        fuente="Cotizador SCOTIABANK Pago de pasivos.xlsm, hojas Simulador y "
        "POport. 7/10/15/20. v2024.01, RECA 0319-138-007480/24-00073-0124 "
        "(2024-01-15), guardado 2024-03-22. SIN escenario capturado: validado "
        "contra sus fórmulas.",
        notas="TASAS DE ENERO DE 2024: confirmar vigencia con Scotiabank. La tasa "
        "baja cada año suponiendo pagos puntuales, como en el cotizador. Sin "
        "apertura ni avalúo. Financia gastos notariales hasta 6 % del saldo dentro "
        "del 95 % (Simulador!F22).",
    ),
    replace(
        _SCOTIA_PASIVOS,
        id="scotiabank-pasivos-valora-2024-01",
        nombre="Pago de Pasivos — Valora",
        # Opción 1 (AA49:AK49), la única que deja elegir el simulador (AA57):
        # su tasa es el piso de la reducción, así que queda fija.
        factores_al_millar=(
            (120, Decimal("12.38")),
            (180, Decimal("9.93")),
            (240, Decimal("8.86")),
        ),
        crecimiento_pago_anual=Decimal("0.026"),         # J24 = D13
        plazos_meses=(120, 180, 240),
        fuente="Cotizador SCOTIABANK Pago de pasivos.xlsm, hojas Simulador y "
        "Valora 10/15/20. v2024.01, RECA 0319-138-007481/24-00074-0124 "
        "(2024-01-15), guardado 2024-03-22. SIN escenario capturado: validado "
        "contra sus fórmulas.",
        notas="TASAS DE ENERO DE 2024: confirmar vigencia con Scotiabank. Tasa fija "
        "10.25 %; el pago sube 2.6 % cada aniversario y el crédito se liquida antes "
        "del plazo. Sin apertura ni avalúo. Financia gastos notariales hasta 6 % "
        "del saldo dentro del 95 % (Simulador!F22).",
    ),
    _po_liquidez(84, Decimal("19.43"), (
        Decimal("0.15"), Decimal("0.148"), Decimal("0.146"), Decimal("0.144"), Decimal("0.1425"),
    ), "AC35:AC39"),
    _po_liquidez(120, Decimal("16.34"), (
        Decimal("0.151"), Decimal("0.149"), Decimal("0.147"), Decimal("0.145"), Decimal("0.1435"),
    ), "AD35:AD39"),
    _po_liquidez(180, Decimal("14.51"), (
        Decimal("0.155"), Decimal("0.153"), Decimal("0.151"), Decimal("0.149"), Decimal("0.1475"),
    ), "AE35:AE39"),
    replace(
        _SCOTIA_LIQUIDEZ,
        id="scotiabank-liquidez-libre-valora-2024-01",
        nombre="Liquidez Libre Valora",
        # SUPUESTO: la opción de tasa más alta (15.5 %, Z16 / AF16). La elige
        # el usuario entre 14.5, 15 y 15.5 %; sin regla en el archivo que la
        # asigne, se toma la conservadora. Baja 0.25 pp cada año desde el mes
        # 37 hasta el piso de 14.5 % (Tabla Valora!AH51, AO3).
        tasa_anual=Decimal("0.155"),
        tasas_escalonadas=(
            (37, Decimal("0.1525")),
            (49, Decimal("0.15")),
            (61, Decimal("0.1475")),
            (73, Decimal("0.145")),
        ),
        factores_al_millar=(
            (120, Decimal("15.80")),                     # AG16
            (180, Decimal("13.58")),                     # AA16
        ),
        crecimiento_pago_anual=Decimal("0.015"),         # AB16 / AH16
        plazos_meses=(120, 180),
        fuente="Cotizador SCOTIABANK Liquidez Libre.xlsm, hojas Simulador Valora y "
        "Tabla Valora. v2024.01, RECA 0319-138-027732/14-00091-0124 (2024-01-15). "
        "SIN escenario capturado: validado contra sus fórmulas.",
        notas="TASAS DE ENERO DE 2024: confirmar vigencia con Scotiabank. SUPUESTO: "
        "tasa inicial 15.5 %, la más alta de las tres que ofrece el simulador (14.5, "
        "15 y 15.5 %, con PTI de 35, 30 y 20 %); confirmar con Scotiabank cómo la "
        "asigna. El pago sube 1.5 % cada aniversario y la tasa baja 0.25 pp por año "
        "desde el cuarto, con pagos puntuales; el crédito se liquida antes del plazo. "
        "IVA de intereses en el pago, no en el CAT.",
    ),
]


# ---------------------------------------------------------------------------
# Afirme Tu Casa 2: adquisición con gastos financiados y garantía adicional
# ---------------------------------------------------------------------------
CATALOGO += [
    replace(
        next(p for p in CATALOGO if p.id == "afirme-adquisicion-2026-07"),
        id="afirme-tu-casa-2-2026-07",
        nombre="Multiproductos — Tu Casa 2 (gastos financiados)",
        # 'Parametro Destino'!B98:F109 = las de adquisición; el crédito nunca
        # pasa de 80 % (C20), así que solo aplica el primer tramo.
        tasa_anual=Decimal("0.1005"),
        tabla_tasas=((240, Decimal("0.80"), Decimal("0.1005")),),
        aforo_max=Decimal("0.80"),                       # sobre vivienda + garantía
        acepta_garantia_adicional=True,
        requiere_garantia_o_gastos_financiados=True,
        # F3 = MIN(80 % de (H22+H23), H22 + M23): financia notariales, avalúos
        # y la apertura (1 % del total, L4).
        financiamiento_gastos=FinanciamientoGastos(tope=None, incluye_apertura_y_avaluo=True),
        fuente="Cotizador AFIRME_MULTIPRODUCTOS.xlsm, destino TU CASA2 (código 8; "
        "Parametro Destino F3:H1, M20:M23, Simulación H22:H25, M38:M45), versión "
        "BAF-040-2607-06, guardado 2026-07-06. SIN escenario capturado: tabla y CAT "
        "con la mecánica de adquisición (validada con su escenario capturado).",
        notas="Mismas tasas que Adquisición (A-BB sin nómina), aforo de 80 % sobre la "
        "vivienda más un inmueble adicional en garantía; con la garantía el crédito "
        "puede cubrir notariales, avalúos y la apertura. SUPUESTOS que corrigen la "
        "hoja: el seguro de daños se cobra sobre la vivienda comprada (la hoja lo "
        "cobra sobre la garantía, H23) y un avalúo por inmueble (la hoja cobra dos "
        "veces el de la garantía); se financian los notariales capturados, no la "
        "estimación del banco (5 % del valor más 75 % de eso sobre la garantía). No "
        "se cobra el trámite CUV ($301.60 con aforo > 79.99 %).",
    ),
]


# ---------------------------------------------------------------------------
# Santander Sustitución con línea de gastos
# ---------------------------------------------------------------------------
CATALOGO += [
    replace(
        _POR_ID["santander-adquisicion-2025-12"],
        id="santander-sustitucion-2025-12",
        nombre="Sustitución de hipoteca",
        destino=Destino.SUSTITUCION,
        # Perfil 3 a 5, oferta "Ninguno" (Adm!CG7:CG9); perfiles 1–2: 12.10 %
        tasa_anual=Decimal("0.111"),
        plazos_meses=tuple(range(84, 241, 12)),          # Adm!E116
        aforo_max=Decimal("0.90"),                       # perfil 4–5 asalariado (EK8:EK9)
        monto_minimo=Decimal("100000"),                  # Adm!Z3
        valor_minimo_inmueble=Decimal("250000"),         # Adm!AA3
        comision_apertura=Decimal("0"),                  # Adm!B116 → P4
        comision_apertura_monto=None,
        avaluo=Decimal("3000.0036"),                     # Cal!C111 = 2,586.21 × 1.16
        tarifa_avaluo=(),
        comision_mensual=Decimal("406"),                 # 350 + IVA (Cal!C126)
        seguro_vida_mensual=Decimal("0.0008254"),        # dos intervinientes (Adm!T8)
        # Daños: valor × 0.70 × 0.0003 mensual, IVA incluido (Adm!AA11·X4)
        seguro_danos_monto_mensual=None,
        seguro_danos_anual=Decimal("0.0036"),
        base_seguro_danos=BaseSeguroDanos.VALOR_CONSTRUCCION,
        factor_construccion=Decimal("0.70"),
        # CAT!L5, H25, I25: avalúo, daños y comisión ÷ 1.16
        cat_netos_de_iva=frozenset({
            ConceptoIVA.AVALUO, ConceptoIVA.SEGURO_DANOS, ConceptoIVA.COMISION_MENSUAL,
        }),
        # "Financiamiento de gastos": 7 % del crédito en una línea aparte,
        # todo o nada por aforo (Cal!C47); misma tasa y pago, vida e IVA de
        # intereses (Liquidez!D18:K18); CAT propio (CAT!AB20).
        financiamiento_gastos=FinanciamientoGastos(
            tope=Decimal("0.07"), linea_separada=True, excede_aforo_cancela=True
        ),
        # "Para cambiar tu hipoteca de otro Banco a Santander" (santander.com.mx,
        # Hipoteca Plus); la propia se mejora con Mejora de Condiciones.
        excluye_credito_actual_propio=True,
        vigente_desde=date(2025, 12, 15),
        fuente="Cotizador Santander.xlsm, destino Sustitución (Adm, Cal, Liquidez, "
        "CAT), versión 2025-6 Ro (15 diciembre 2025). SIN escenario capturado: "
        "validado contra sus fórmulas con una réplica que reproduce el escenario "
        "guardado de adquisición.",
        notas="Tasa de mercado abierto para perfiles 3 a 5; perfiles 1–2 pagan 12.10 %, "
        "y con Hipoteca Plus (nómina, tarjeta y seguros) baja hasta 9.30 %. Aforo de "
        "90 % para asalariados perfil 4–5 (75 % a 85 % en los demás). Seguro de vida "
        "para dos intervinientes. Los gastos se financian en un segundo crédito: "
        "SUPUESTO, el mínimo entre los gastos del escenario y el 7 % (el cotizador "
        "financia el 7 % fijo). No aplica a hipotecas que ya son de Santander: para "
        "esas está Mejora de Condiciones." + _VIGENCIA_SANTANDER,
    ),
]
CATALOGO.append(
    replace(
        next(p for p in CATALOGO if p.id == "santander-sustitucion-2025-12"),
        id="santander-mejora-condiciones-2025-12",
        nombre="Mejora de Condiciones",
        # Misma mecánica que Sustitución (Cal, Liquidez, CAT) con las tasas de
        # Adquisición: oferta Ninguno, perfiles 4–5 (Adm!CD8:CD9)
        tasa_anual=Decimal("0.1025"),
        monto_minimo=Decimal("200000"),                  # Adm!Z9
        excluye_credito_actual_propio=False,
        # "Para mejorar las condiciones de tu hipoteca actual con Santander"
        solo_credito_actual_propio=True,
        # Origen Cofinanciamiento (Adm!C22, hoja Sustitución): el saldo
        # INFONAVIT/FOVISSSTE en un tercer crédito, comisión 350 + IVA (Q6)
        refinanciamiento_instituto=RefinanciamientoInstituto(comision_mensual=Decimal("406")),
        fuente="Cotizador Santander.xlsm, destino Mejora de Condiciones (Adm, Cal, "
        "Liquidez, CAT), versión 2025-6 Ro (15 diciembre 2025). A quién aplica: "
        "santander.com.mx, Hipoteca Plus, consultado 2026-10-25. SIN escenario "
        "capturado: validado contra sus fórmulas.",
        notas="Solo para quien ya tiene su hipoteca con Santander. Tasa de mercado "
        "abierto para perfiles 4 y 5 (perfil 3 10.95 %, 2 12.25 %, 1 13.25 %); con "
        "Hipoteca Plus baja hasta 9.25 %. Sin apertura y avalúo de $2,586.21 + IVA, "
        "como en el cotizador; un comparador externo sin fecha reporta apertura de "
        "1 % + IVA: confirmar con Santander. Financia gastos en un segundo crédito "
        "como Sustitución. Si la hipoteca actual es de cofinanciamiento, refinancia "
        "también el crédito INFONAVIT/FOVISSSTE en un tercer crédito con la misma "
        "tasa y plazo (Mejoras Cofis); el aforo y el 7 % de gastos se miden sobre "
        "los dos. CORRECCIONES a la hoja: el pago de esa línea se toma fijo (la hoja "
        "lo hace crecer cada año en pagos fijos, Sustitución!X19, pero su CAT no) y "
        "si los dos créditos rebasan el aforo no es elegible (la hoja recorta el "
        "crédito bancario)." + _VIGENCIA_SANTANDER,
    )
)


# ---------------------------------------------------------------------------
# Scotiabank Credirenovación: remodelación de la vivienda propia (modo 1)
# ---------------------------------------------------------------------------
# Mismo motor que Valora y Pagos Oportunos de Pago de pasivos: interés con días
# del mes / 360, pago al millar que no se recalcula (se liquida antes del
# plazo), cortes 3 y 17, vida 0.6 y daños 0.31 al millar mensual sobre el valor
# actual. Sin IVA de intereses. Costos iniciales completos en el CAT: apertura
# 1 % (solo campaña Ninguna), avalúo por el tabulador del 7x5 (no en Premium) y
# dictamen técnico de 1 % con mínimo 1,500 y máximo 18,000 (no en Green).
# Compra + remodelación, pasivo + remodelación y segunda hipoteca no se modelan.

_CREDIRENOVACION = replace(
    next(p for p in CATALOGO if p.id == "scotiabank-pasivos-valora-2024-01"),
    destino=Destino.REMODELACION,
    financiamiento_gastos=None,                          # solo en el modo 3
    tarifa_avaluo=_POR_ID["scotiabank-7x5-adquisicion-2024-01"].tarifa_avaluo,  # S74:U95
    avaluo=Decimal("0"),
    comision_apertura=Decimal("0"),
    dictamen_tecnico_pct=Decimal("0.01"),                # E72, Y88:AA88
    dictamen_tecnico_minimo=Decimal("1500"),
    dictamen_tecnico_maximo=Decimal("18000"),
    aforo_max=Decimal("0.80"),                           # W9: 80 % del valor actual
    # Ingresos requeridos = erogación inicial (capital + interés) / PTI (E66):
    # 35 % (AC9:AC12), 55 % en Green y en Pasivo + Renovación; mínimo $20,000 (C31)
    factor_pago_ingreso_max=Decimal("0.35"),
    ingreso_minimo=Decimal("20000"),
    max_ministraciones=3,                                # 'Tabla Valora'!B11:B13
    tasas_escalonadas=(),
    crecimiento_pago_anual=None,
    vigente_desde=date(2025, 4, 10),
)

# (clave, nombre, tasa Valora, piso, factores 10/15/20, crecimiento,
#  tasa PO, factores PO 7/10/15/20)
_CAMPANAS_CREDIRENOVACION = (
    ("ninguna", "Ninguna", "0.125", "0.12", ("14.06", "11.78", "10.84"), "0.017",
     "0.13", ("18.38", "15.05", "12.79", "11.86")),
    ("vinculacion", "Vinculación", "0.1075", "0.1075", ("12.75", "10.33", "9.30"), "0.024",
     "0.1075", ("17.10", "13.73", "11.32", "10.27")),
    ("green", "Hipoteca Green", "0.105", "0.105", ("12.60", "10.13", "9.08"), "0.025",
     "0.105", ("16.95", "13.60", "11.16", "10.10")),
    ("premium", "Premium / WM", "0.0975", "0.0975", ("12.12", "9.64", "8.54"), "0.026",
     "0.0975", ("16.55", "13.16", "10.70", "9.59")),
)

_REQUISITO_CAMPANA = {
    "ninguna": "Condición pública, sin vinculación. Apertura de 1 %. SUPUESTO: la "
    "opción de tasa de calificación \"1\" (12.50 %, baja a 12 % desde el año 4); "
    "con calificación \"1+\" es 12 % fija.",
    "vinculacion": "Requiere vinculación con el banco; el cotizador no define el "
    "criterio (nómina, productos): confirmarlo con el ejecutivo. Sin apertura.",
    "green": "Para obra con ecotecnologías: aforo de 95 %, sin dictamen técnico ni "
    "apertura.",
    "premium": "Para clientes Premium o Wealth Management: sin apertura ni avalúo.",
}

# Campañas con condición: solo elegibles si el escenario la marca ('Simulador
# Valora'!AB18, 'Simulador Pagos Oportunos'!T25)
_REQUISITOS_CAMPANA = {
    "ninguna": frozenset(),
    "vinculacion": frozenset({RequisitoCliente.VINCULACION_SCOTIABANK}),
    "green": frozenset({RequisitoCliente.ECOTECNOLOGIAS}),
    "premium": frozenset({RequisitoCliente.PREMIUM_SCOTIABANK}),
}


def _credirenovacion(clave, nombre, esquema, **cambios):
    green = clave == "green"
    return replace(
        _CREDIRENOVACION,
        id=f"scotiabank-credirenovacion-{esquema}-{clave}-2025-04",
        nombre=f"Credirenovación {'Valora' if esquema == 'valora' else 'Pagos Oportunos'} — {nombre}",
        comision_apertura=Decimal("0.01") if clave == "ninguna" else Decimal("0"),
        tarifa_avaluo=() if clave == "premium" else _CREDIRENOVACION.tarifa_avaluo,
        dictamen_tecnico_pct=Decimal("0") if green else Decimal("0.01"),
        aforo_max=Decimal("0.95") if green else Decimal("0.80"),
        factor_pago_ingreso_max=Decimal("0.55") if green else Decimal("0.35"),
        requisitos_cliente=_REQUISITOS_CAMPANA[clave],
        fuente="Cotizador SCOTIABANK Credirenovación.xlsm, modo 1 Renovación (remodelar "
        f"la vivienda propia), hojas Simulador {'Valora' if esquema == 'valora' else 'Pagos Oportunos'} "
        "y Tabla, versión v2025.04 (guardado 2025-04-11); RECA expedidos 2024-01-15. SIN "
        "escenario capturado: validado contra sus fórmulas.",
        notas="TASAS DE ABRIL DE 2025: confirmar vigencia con Scotiabank. Crédito para "
        "remodelar, entregado por avance de obra (aquí se supone disponible desde el mes "
        "1). La tasa baja suponiendo pagos puntuales, como en el cotizador. "
        + _REQUISITO_CAMPANA[clave],
        **cambios,
    )


CATALOGO += [
    _credirenovacion(
        clave, nombre, "valora",
        tasa_anual=Decimal(tasa),
        # 'Tabla Valora'!AH56: −0.25 pp cada año desde el mes 37 hasta el piso
        tasas_escalonadas=tuple(
            (37 + 12 * k, max(Decimal(tasa) - Decimal("0.0025") * (k + 1), Decimal(piso)))
            for k in range(int((Decimal(tasa) - Decimal(piso)) / Decimal("0.0025")))
        ),
        factores_al_millar=tuple(zip((120, 180, 240), (Decimal(f) for f in factores))),
        crecimiento_pago_anual=Decimal(crec),
        plazos_meses=(120, 180, 240),
    )
    for clave, nombre, tasa, piso, factores, crec, _, _ in _CAMPANAS_CREDIRENOVACION
] + [
    _credirenovacion(
        clave, nombre, "pagos-oportunos",
        tasa_anual=Decimal(tasa_po),
        # Tabla Pagos Oportunos!AH32:AH68: −0.20 pp en los meses 13, 25 y 37,
        # −0.15 pp en el 49. SUPUESTO: a 15 y 20 años se usan los valores de la
        # campaña; la hoja usa por error los de Ninguna (W36:X37 constantes).
        tasas_escalonadas=(
            (13, Decimal(tasa_po) - Decimal("0.002")),
            (25, Decimal(tasa_po) - Decimal("0.004")),
            (37, Decimal(tasa_po) - Decimal("0.006")),
            (49, Decimal(tasa_po) - Decimal("0.0075")),
        ),
        factores_al_millar=tuple(zip((84, 120, 180, 240), (Decimal(f) for f in factores_po))),
        plazos_meses=(84, 120, 180, 240),
    )
    for clave, nombre, _, _, _, _, tasa_po, factores_po in _CAMPANAS_CREDIRENOVACION
]

# Modo 2, Compra + Renovación: un solo crédito por compra + obra ('Simulador
# Valora'!H31 = H29 + H30), mismas tasas y factores que el modo 1, aforo sobre
# el valor proyectado C30 = compra + obra (H28). Avalúo sobre el valor
# proyectado; apertura y dictamen sobre el total. RECA Valora 0319-138-007460,
# PO 0319-138-007458.
_RECA_COMPRA = {"valora": "0319-138-007460/25-00058-0124", "pagos-oportunos": "0319-138-007458/25-00057-0124"}
CATALOGO += [
    replace(
        p,
        id=p.id.replace("credirenovacion-", "credirenovacion-compra-"),
        nombre=p.nombre.replace("Credirenovación", "Credirenovación Compra + Remodelación"),
        destino=Destino.ADQUISICION,
        financia_remodelacion=True,
        # Supervisión de uso de recursos (dictamen) sobre la obra, máximo
        # $6,600 en Adquisición + Renovación (folleto 'Renovación', julio 2026,
        # p. 18; tarifa AC94 "sobre el monto del presupuesto de obra"). La
        # fórmula E72 lo cobra sobre compra + obra: se corrige.
        dictamen_sobre_obra=True,
        dictamen_tecnico_maximo=Decimal("6600"),
        fuente=p.fuente.replace("modo 1 Renovación (remodelar la vivienda propia)",
                                "modo 2 Compra + Renovación")
        + f" RECA {_RECA_COMPRA['valora' if '-valora-' in p.id else 'pagos-oportunos']}.",
        notas=p.notas + " Compra y obra en un solo crédito, con el aforo sobre la "
        "vivienda más la obra. CORRECCIÓN a la hoja: el seguro de daños se cobra sobre "
        "ese valor proyectado; la hoja suma otra vez la obra (E60 = C30 + H30). El "
        "dictamen técnico se cobra sobre la obra con máximo de $6,600, como dice el folleto "
        "'Renovación' de julio 2026 (la hoja lo cobra sobre compra + obra). No financia "
        "gastos notariales ni acepta cofinanciamiento.",
    )
    for p in list(CATALOGO)
    if p.id.startswith("scotiabank-credirenovacion-") and p.destino is Destino.REMODELACION
]

# Modo 3, Pasivo + Renovación: sustituye la hipoteca de otro banco y financia
# la obra en el mismo crédito (H31 = saldo + obra). Aforo de 95 % sobre el
# valor proyectado (X11, H28), obra hasta 35 % del valor actual (validación de
# H30). Sin apertura, avalúo ni dictamen (E68, E70, E72). Green no aplica.
# Valora financia gastos notariales hasta 6 % de saldo + obra dentro del 95 %
# (L35); Pagos Oportunos no (H50 = H31).
_RECA_PASIVO = {"valora": "0319-138-007463/25-00060-0124", "pagos-oportunos": "0319-138-007462/24-00059-0124"}
CATALOGO += [
    replace(
        p,
        id=p.id.replace("credirenovacion-compra-", "credirenovacion-pasivo-"),
        nombre=p.nombre.replace("Compra + Remodelación", "Pasivo + Remodelación"),
        destino=Destino.SUSTITUCION,
        excluye_credito_actual_propio=True,
        aforo_max=Decimal("0.95"),
        remodelacion_max_pct_valor=Decimal("0.35"),
        factor_pago_ingreso_max=Decimal("0.55"),         # AC11
        max_ministraciones=0,                            # liquida el saldo al firmar
        comision_apertura=Decimal("0"),
        tarifa_avaluo=(),
        avaluo=Decimal("0"),
        dictamen_tecnico_pct=Decimal("0"),
        financiamiento_gastos=(
            FinanciamientoGastos(tope=Decimal("0.06"), apertura_y_aforo_sobre_total=False)
            if "-valora-" in p.id else None
        ),
        fuente=p.fuente.replace("modo 2 Compra + Renovación", "modo 3 Pasivo + Renovación")
        .split(" RECA 0319")[0]
        + f" RECA {_RECA_PASIVO['valora' if '-valora-' in p.id else 'pagos-oportunos']}.",
        notas="TASAS DE ABRIL DE 2025: confirmar vigencia con Scotiabank. Trae la hipoteca "
        "de otro banco y financia la obra en el mismo crédito (hasta 35 % del valor "
        "actual), con aforo de 95 % sobre la vivienda más la obra. Sin apertura, avalúo "
        "ni dictamen. La tasa baja suponiendo pagos puntuales. "
        + ("Financia gastos notariales hasta 6 % de saldo + obra; SUPUESTO: el mínimo "
           "entre los gastos del escenario y ese 6 % (la hoja financia siempre el 6 %). "
           if "-valora-" in p.id else "No financia gastos notariales. ")
        + "CORRECCIONES a la hoja: el seguro de daños se cobra sobre el valor proyectado "
        "(la hoja suma otra vez la obra) y si saldo + obra rebasan el aforo no es "
        "elegible (la hoja recorta el crédito y puede no cubrir el saldo). "
        + p.notas.split("La tasa baja suponiendo pagos puntuales, como en el cotizador. ")[1]
        .split(" Compra y obra")[0].replace(" Apertura de 1 %.", ""),
    )
    for p in list(CATALOGO)
    if p.id.startswith("scotiabank-credirenovacion-compra-") and "-green-" not in p.id
]

# Modo 4, 2a Hipoteca con SB: la vivienda ya tiene hipoteca con Scotiabank, que
# no se refinancia; el crédito nuevo es solo la obra (H30). Lo indican el
# resumen ('Simulador Valora'!E56, E58), los ingresos (E66), el seguro de
# daños en 0 (E60), la línea autorizada de PO ('Tabla PO'!H9 = H30), la Oferta
# ("Remodelación de vivienda") y el RECA ("Renovación 2° Hipoteca"). Aforo de
# 80 % combinado: saldo vigente + obra sobre valor + obra (H28, C33). Green no
# aplica (T12).
_RECA_SEGUNDA = {"valora": "0319-138-007456/24-00056-0124", "pagos-oportunos": "0319-138-007454/24-00055-0124"}
CATALOGO += [
    replace(
        p,
        id=p.id.replace("credirenovacion-", "credirenovacion-2a-hipoteca-"),
        nombre=p.nombre.replace("Credirenovación", "Credirenovación 2a Hipoteca"),
        segunda_hipoteca=True,
        seguro_danos_anual=Decimal("0"),
        fuente=p.fuente.replace("modo 1 Renovación (remodelar la vivienda propia)",
                                "modo 4 2a Hipoteca con SB")
        + f" RECA {_RECA_SEGUNDA['valora' if '-valora-' in p.id else 'pagos-oportunos']}.",
        notas=p.notas + " Para quien ya tiene su hipoteca con Scotiabank: la hipoteca "
        "vigente se queda y el crédito nuevo es solo la obra; el aforo de 80 % suma el "
        "saldo vigente sobre la vivienda más la obra. Sin seguro de daños (lo cubre la "
        "primera hipoteca). CORRECCIONES a la hoja: su tabla, su CAT, la apertura y el "
        "dictamen toman saldo vigente + obra, contra el resto del archivo; aquí solo la "
        "obra. Si saldo + obra rebasan el aforo no es elegible (la hoja solo avisa). "
        "La capacidad de pago suma el pago de la hipoteca vigente (la hoja no lo pide).",
    )
    for p in list(CATALOGO)
    if p.id.startswith("scotiabank-credirenovacion-")
    and p.destino is Destino.REMODELACION
    and "-green-" not in p.id
]

# El modo 1 es para vivienda sin hipoteca. Se marca al final para que no lo
# hereden los productos derivados de él (modos 2, 3 y 4).
CATALOGO[:] = [
    replace(p, excluye_vivienda_con_hipoteca=True)
    if p.id.startswith("scotiabank-credirenovacion-") and p.destino is Destino.REMODELACION
    and not p.segunda_hipoteca
    else p
    for p in CATALOGO
]



# ---------------------------------------------------------------------------
# Credirenovación, versión con el folleto oficial "Renovación" (julio 2026)
# ---------------------------------------------------------------------------
# Las versiones -2025-04 (cotizador v2025.04) se cierran y las sustituyen las
# -2026-07, con lo que el folleto FES_Renovacion (julio 2026) cambia:
#   - montos: mínimo 150,000 (Renovación), 250,000 (Compra + Renovación),
#     125,000 (Pago de pasivos + Renovación); máximo 10 millones (pp. 4–6);
#   - entregas por avance de obra: 50 % a la firma y el resto al 80 % de avance
#     (pp. 4–6);
#   - avalúo de Pago de pasivos + Renovación con su propia columna de tarifas
#     (p. 18).
# Tasas, factores al millar, apertura, dictamen y seguros coinciden con el
# cotizador y no cambian.
_FOLLETO_RENOVACION = (
    "Folleto Scotiabank 'Renovación' (FES_Renovacion, julio 2026; "
    "cdn.aglty.io/scotia-bank-mexico/spanish/pdf/personas/creditos/creditos/FES_Renovacion.pdf)"
)
_AVALUO_PASIVO_RENOVACION = (                            # folleto p. 18
    (Decimal("0"), Decimal("1253"), Decimal("0")),
    (Decimal("500000.01"), Decimal("1740"), Decimal("0")),
    (Decimal("1000000.01"), Decimal("2784"), Decimal("0")),
    (Decimal("2000000.01"), Decimal("4663"), Decimal("0")),
    (Decimal("3000000.01"), Decimal("5000"), Decimal("0")),
)


def _credirenovacion_2026(p):
    pasivo = "-pasivo-" in p.id
    compra = "-compra-" in p.id
    segunda = p.segunda_hipoteca
    if pasivo:
        minimo = Decimal("125000")
    elif compra:
        minimo = Decimal("250000")
    else:
        minimo = Decimal("150000")
    return replace(
        p,
        id=p.id.replace("-2025-04", "-2026-07"),
        monto_minimo=minimo,
        monto_maximo=Decimal("10000000"),
        max_ministraciones=0 if pasivo else 2,
        ministracion_inicial_pct=None if pasivo else Decimal("0.50"),
        tarifa_avaluo=_AVALUO_PASIVO_RENOVACION if pasivo else p.tarifa_avaluo,
        vigente_desde=date(2026, 10, 26),
        vigente_hasta=None,
        fuente=p.fuente + " Montos, entregas y avalúo de " + _FOLLETO_RENOVACION + ".",
        notas=p.notas.replace("TASAS DE ABRIL DE 2025", "TASAS DEL COTIZADOR DE ABRIL DE "
                              "2025, dentro de los rangos del folleto de julio 2026")
        + (" Entrega por avance de obra: 50 % a la firma y el resto al 80 % de avance "
           "(si la obra no toca la estructura, todo a la firma)." if not pasivo else "")
        + (" SUPUESTO: avalúo con la columna de Pago de pasivos + Renovación del folleto "
           "sobre el valor proyectado; el cotizador no lo cobra." if pasivo else "")
        + (" SUPUESTO: monto mínimo de $150,000 como Renovación (el folleto no lo da para "
           "2da hipoteca)." if segunda else ""),
    )


_CREDIRENOVACION_2025 = [
    p for p in CATALOGO if p.id.startswith("scotiabank-credirenovacion-") and p.id.endswith("-2025-04")
]
CATALOGO[:] = [
    replace(p, vigente_hasta=date(2026, 10, 25),
            notas=p.notas + " VERSIÓN CERRADA el 2026-10-25: la sustituye la -2026-07 "
            "con montos, entregas y avalúo del folleto de julio 2026.")
    if p in _CREDIRENOVACION_2025 else p
    for p in CATALOGO
] + [_credirenovacion_2026(p) for p in _CREDIRENOVACION_2025]


# ---------------------------------------------------------------------------
# Avalúo de Pago de pasivos según el documento de comisiones (julio 2026)
# ---------------------------------------------------------------------------
# El documento oficial de comisiones hipotecarias de Scotiabank (julio 2026,
# p. 4) pone la tarifa reducida de avalúo en la columna "Pago de Pasivos,
# Liquidez Libre" y a "Renovación + Pago de Pasivos" en la tarifa normal. El
# folleto "Renovación" (p. 18) rotula la reducida como "Pago de pasivos +
# Renovación" y los cotizadores no cobran avalúo. Se toma el documento de
# comisiones (la divulgación formal) mientras Scotiabank lo confirma:
#   - Credirenovación Pasivo + Remodelación: tarifa normal ($1,900 a $27,000).
#     Su versión -2026-07 con la reducida se retira el mismo día que se publicó.
#   - Pago de pasivos 7x5, Valora y Pagos Oportunos: tarifa reducida (antes $0).
_COMISIONES_HIPOTECARIO = (
    "Documento Scotiabank de comisiones de crédito hipotecario (julio 2026; "
    "cdn.aglty.io/scotia-bank-mexico/pdf/personas/creditos/comisiones-hipotecario.pdf), p. 4"
)
_AVALUO_PAGO_DE_PASIVOS = (                              # comisiones p. 4
    (Decimal("0"), Decimal("1253"), Decimal("0")),
    (Decimal("500000.01"), Decimal("1750"), Decimal("0")),
    (Decimal("1000000.01"), Decimal("2784"), Decimal("0")),
    (Decimal("2000000.01"), Decimal("4663"), Decimal("0")),
    (Decimal("3000000.01"), Decimal("5000"), Decimal("0")),
)
_TARIFA_NORMAL_SCOTIABANK = next(
    p for p in CATALOGO if p.id == "scotiabank-7x5-adquisicion-2024-01"
).tarifa_avaluo
_PASIVO_RENOVACION_RETIRADO = [
    p for p in CATALOGO if p.id.startswith("scotiabank-credirenovacion-pasivo-") and p.id.endswith("-2026-07")
]
_PAGO_DE_PASIVOS_2024 = [
    p for p in CATALOGO if p.id in (
        "scotiabank-7x5-pasivo-hipotecario-2024-01",
        "scotiabank-pasivos-pagos-oportunos-2024-01",
        "scotiabank-pasivos-valora-2024-01",
    )
]
_NOTA_AVALUO = (
    " Avalúo: el documento de comisiones de julio 2026 y el folleto 'Renovación' "
    "no coinciden para Pago de pasivos + Renovación; confirmar con Scotiabank."
)
CATALOGO[:] = [
    replace(p, vigente_hasta=date(2026, 10, 25),
            notas=p.notas + " RETIRADA el día de su publicación (2026-10-26): el documento "
            "de comisiones pone a Renovación + Pago de Pasivos en la tarifa normal de avalúo.")
    if p in _PASIVO_RENOVACION_RETIRADO
    else replace(p, vigente_hasta=date(2026, 10, 25),
                 notas=p.notas + " VERSIÓN CERRADA el 2026-10-25: la sustituye la -2026-07 "
                 "con el avalúo del documento de comisiones de julio 2026.")
    if p in _PAGO_DE_PASIVOS_2024
    else p
    for p in CATALOGO
] + [
    replace(
        p,
        id=p.id.replace("-2026-07", "-2026-07-v2"),
        tarifa_avaluo=_TARIFA_NORMAL_SCOTIABANK,
        vigente_desde=date(2026, 10, 26),
        vigente_hasta=None,
        fuente=p.fuente + " Avalúo con la tarifa normal de " + _COMISIONES_HIPOTECARIO + ".",
        notas=p.notas.replace(
            " SUPUESTO: avalúo con la columna de Pago de pasivos + Renovación del folleto "
            "sobre el valor proyectado; el cotizador no lo cobra.",
            " Avalúo con la tarifa normal sobre el valor proyectado.",
        ) + _NOTA_AVALUO,
    )
    for p in _PASIVO_RENOVACION_RETIRADO
] + [
    replace(
        p,
        id=p.id.replace("-2024-01", "-2026-07"),
        tarifa_avaluo=_AVALUO_PAGO_DE_PASIVOS,
        avaluo=Decimal("0"),
        vigente_desde=date(2026, 10, 26),
        vigente_hasta=None,
        fuente=p.fuente + " Avalúo de " + _COMISIONES_HIPOTECARIO + ".",
        notas=p.notas.replace("Sin apertura ni avalúo.", "Sin apertura.")
        .replace("sin avalúo;", "")
        + " Avalúo con la tarifa reducida de Pago de pasivos del documento de comisiones "
        "de julio 2026 ($1,253 a $5,000; arriba de 11 millones, SUPUESTO $5,000); el "
        "cotizador no lo cobraba.",
    )
    for p in _PAGO_DE_PASIVOS_2024
]


# ---------------------------------------------------------------------------
# Pago de pasivos Valora y Pagos Oportunos con las tasas de julio 2026
# ---------------------------------------------------------------------------
# El documento de comisiones de julio 2026 (pp. 1–2) publica para "Pago de
# Pasivos" la misma tabla que Renovación: Valora de 12 % a 14 % con factores
# 13.63–15.30 (10 años), 11.32–13.04 (15) y 10.36–12.13 (20); Pagos Oportunos
# 13.00 / 12.80 / 12.60 / 12.40 / 12.25 % con factores 18.38 / 15.05 / 12.79 /
# 11.86. Coinciden con Credirenovación (cotizador v2025.04), así que se toman
# su mecánica y su opción de tasa: Valora 12.50 % (la conservadora, como en
# Credirenovación), bajando 0.25 pp por año desde el mes 37 hasta 12 %, pago
# +1.7 % anual. Las -2026-07 de hoy (tasas de enero 2024) se retiran el mismo
# día. Comisión 0 %, aforo 95 %, gastos financiados 6 % y avalúo reducido igual.
_PASIVOS_TASAS_2024 = [
    p for p in CATALOGO
    if p.id in ("scotiabank-pasivos-valora-2026-07", "scotiabank-pasivos-pagos-oportunos-2026-07")
]
_TASAS_PASIVOS_2026 = (
    "Tasas y factores de " + _COMISIONES_HIPOTECARIO.replace("p. 4", "pp. 1–2")
    + "; mecánica de Valora y Pagos Oportunos validada contra las fórmulas de Credirenovación."
)


def _pasivos_2026(p):
    valora = "-valora-" in p.id
    if valora:
        cambios = dict(
            tasa_anual=Decimal("0.125"),
            tasas_escalonadas=((37, Decimal("0.1225")), (49, Decimal("0.12"))),
            factores_al_millar=((120, Decimal("14.06")), (180, Decimal("11.78")), (240, Decimal("10.84"))),
            crecimiento_pago_anual=Decimal("0.017"),
        )
        tasa = ("Tasa inicial 12.50 % (SUPUESTO: el documento da un rango de 12 % a 14 % según "
                "el estudio de crédito; se toma la opción conservadora de Credirenovación), "
                "baja a 12 % desde el año 4 con pagos puntuales; el pago sube 1.7 % cada "
                "aniversario y el crédito se liquida antes del plazo.")
    else:
        cambios = dict(
            tasa_anual=Decimal("0.13"),
            tasas_escalonadas=(
                (13, Decimal("0.128")), (25, Decimal("0.126")),
                (37, Decimal("0.124")), (49, Decimal("0.1225")),
            ),
            factores_al_millar=(
                (84, Decimal("18.38")), (120, Decimal("15.05")),
                (180, Decimal("12.79")), (240, Decimal("11.86")),
            ),
        )
        tasa = ("La tasa baja cada año de 13 % a 12.25 % suponiendo pagos puntuales, como "
                "en el cotizador; el crédito se liquida antes del plazo.")
    return replace(
        p,
        id=p.id + "-v2",
        vigente_desde=date(2026, 10, 26),
        vigente_hasta=None,
        fuente=p.fuente + " " + _TASAS_PASIVOS_2026,
        notas="TASAS DE JULIO DE 2026 (documento de comisiones). " + tasa + " Sin apertura. "
        "Financia gastos notariales hasta 6 % del saldo dentro del 95 % (cotizador "
        "v2024.01). Avalúo con la tarifa reducida de Pago de pasivos del documento de "
        "comisiones ($1,253 a $5,000; arriba de 11 millones, SUPUESTO $5,000)." + _NOTA_AVALUO,
        **cambios,
    )


CATALOGO[:] = [
    replace(p, vigente_hasta=date(2026, 10, 25),
            notas=p.notas + " RETIRADA el día de su publicación (2026-10-26): conservaba las "
            "tasas de enero 2024; la sustituye la -v2 con las de julio 2026.")
    if p in _PASIVOS_TASAS_2024 else p
    for p in CATALOGO
] + [_pasivos_2026(p) for p in _PASIVOS_TASAS_2024]


# ---------------------------------------------------------------------------
# Liquidez Libre con el documento de comisiones de julio 2026
# ---------------------------------------------------------------------------
# El documento (pp. 1–4) confirma tasas, factores y comisión de Liquidez Libre
# (7x5, Valora y Pagos Oportunos) y pone su avalúo en la columna de Pago de
# pasivos: el tramo de $500,001 a $1,000,000 cuesta $1,750 (el cotizador
# v2024.01 decía $1,740). Lo demás no cambia.
_LIQUIDEZ_LIBRE_2024 = [
    p for p in CATALOGO if p.id.startswith("scotiabank-liquidez-libre-") and p.id.endswith("-2024-01")
]
CATALOGO[:] = [
    replace(p, vigente_hasta=date(2026, 10, 25),
            notas=p.notas + " VERSIÓN CERRADA el 2026-10-25: la sustituye la -2026-07 con "
            "el avalúo del documento de comisiones de julio 2026.")
    if p in _LIQUIDEZ_LIBRE_2024 else p
    for p in CATALOGO
] + [
    replace(
        p,
        id=p.id.replace("-2024-01", "-2026-07"),
        tarifa_avaluo=_AVALUO_PAGO_DE_PASIVOS,
        vigente_desde=date(2026, 10, 26),
        vigente_hasta=None,
        fuente=p.fuente + " Tasas, factores, comisión y avalúo confirmados con "
        + _COMISIONES_HIPOTECARIO.replace("p. 4", "pp. 1–4") + ".",
        notas=p.notas.replace(
            "TASAS DE MARZO DE 2024: confirmar vigencia con Scotiabank.",
            "TASAS DEL COTIZADOR DE 2024, IGUALES EN EL DOCUMENTO DE COMISIONES DE JULIO 2026.",
        ).replace(
            "TASAS DE ENERO DE 2024: confirmar vigencia con Scotiabank.",
            "TASAS DEL COTIZADOR DE 2024, IGUALES EN EL DOCUMENTO DE COMISIONES DE JULIO 2026.",
        ) + " Avalúo con la tarifa de Pago de pasivos y Liquidez Libre del documento de "
        "comisiones ($1,253 a $5,000; $1,750 de $500,001 a $1,000,000).",
    )
    for p in _LIQUIDEZ_LIBRE_2024
]


# ---------------------------------------------------------------------------
# Supervisión de uso de recursos en Pasivo + Remodelación (julio 2026)
# ---------------------------------------------------------------------------
# El "dictamen técnico" del cotizador es la comisión "Contratación -
# supervisión de uso de recursos": estudio previo y visitas que definen los
# avances de obra (folleto 'Renovación', p. 16). El documento de comisiones
# de julio 2026 (p. 4) la cobra en toda la columna de Renovación, incluida
# Renovación + Pago de Pasivos: 1 %, máximo $18,000 (el máximo de $6,600 es
# solo de Adquisición + Renovación, folleto p. 18). La tarifa del cotizador
# (Simulador Valora!AC92:AD96) dice lo mismo: "Renovación todas sus
# modalidades", 1 % del presupuesto de obra, mínimo 1,500 y máximo 18,000;
# solo su fórmula E72 la pone en 0 para el modo 3. El contrato RECA de
# Renovación y Pago de Pasivos la pacta (Décima Tercera b). Las -2026-07-v2
# de Pasivo + Remodelación se cierran el 2026-10-26 y las sustituyen las -v3.
_PASIVO_RENOVACION_SIN_SUPERVISION = [
    p for p in CATALOGO
    if p.id.startswith("scotiabank-credirenovacion-pasivo-") and p.id.endswith("-2026-07-v2")
]
CATALOGO[:] = [
    replace(p, vigente_hasta=date(2026, 10, 26),
            notas=p.notas + " VERSIÓN CERRADA el 2026-10-26: no cobraba la supervisión de uso "
            "de recursos; la sustituye la -v3.")
    if p in _PASIVO_RENOVACION_SIN_SUPERVISION else p
    for p in CATALOGO
] + [
    replace(
        p,
        id=p.id.replace("-2026-07-v2", "-2026-07-v3"),
        dictamen_tecnico_pct=Decimal("0.01"),
        dictamen_tecnico_minimo=Decimal("1500"),
        dictamen_tecnico_maximo=Decimal("18000"),
        dictamen_sobre_obra=True,
        vigente_desde=date(2026, 10, 27),
        vigente_hasta=None,
        fuente=p.fuente + " Supervisión de uso de recursos de "
        + _COMISIONES_HIPOTECARIO + " y de la tarifa del cotizador (Simulador Valora!AC92:AD96).",
        notas=p.notas.replace("Sin apertura, avalúo ni dictamen.", "Sin apertura.")
        + " Supervisión de uso de recursos (dictamen técnico): 1 % de la obra, mínimo "
        "$1,500 y máximo $18,000, de contado a la firma y dentro del CAT como en los otros "
        "modos; la fórmula del cotizador no la cobraba en este modo, aunque su tarifa y el "
        "documento de comisiones sí. SUPUESTO: se cobra una vez sobre toda la obra; el "
        "documento dice que va «en función de la ministración que corresponda».",
    )
    for p in _PASIVO_RENOVACION_SIN_SUPERVISION
]


# ---------------------------------------------------------------------------
# Contratos de adhesión vigentes en el RECA (CONDUSEF), consultados 2026-10-26
# ---------------------------------------------------------------------------
# Los cotizadores citan los registros de enero 2024; todos los contratos
# hipotecarios de Scotiabank se volvieron a registrar el 19-01-2026
# (registros.condusef.gob.mx/reca). Solo se agrega la cita a las versiones
# vigentes: es procedencia, no condición, y las cerradas conservan la de su
# tiempo. Los contratos dejan en blanco tasas y montos de comisiones (se llenan
# en la carátula), así que no cambian ningún parámetro. El orden importa: el
# primer prefijo que coincide gana.
_RECA_VIGENTE = (
    ("scotiabank-credirenovacion-compra-valora-", "0319-138-007460/28-03314-1225", "Renovación y Adquisición Valora"),
    ("scotiabank-credirenovacion-compra-pagos-oportunos-", "0319-138-007458/28-03313-1225", "Renovación y Adquisición Pagos Oportunos"),
    ("scotiabank-credirenovacion-pasivo-valora-", "0319-138-007463/27-03317-1225", "Renovación y Pago de Pasivos Valora"),
    ("scotiabank-credirenovacion-pasivo-pagos-oportunos-", "0319-138-007462/26-03315-1225", "Renovación y Pago de Pasivos Pagos Oportunos"),
    ("scotiabank-credirenovacion-2a-hipoteca-valora-", "0319-138-007456/27-03312-1225", "Renovación 2° Hipoteca Valora"),
    ("scotiabank-credirenovacion-2a-hipoteca-pagos-oportunos-", "0319-138-007454/27-03311-1225", "Renovación 2° Hipoteca Pagos Oportunos"),
    ("scotiabank-credirenovacion-valora-", "0319-138-007452/29-03310-1225", "Renovación Valora"),
    ("scotiabank-credirenovacion-pagos-oportunos-", "0319-138-007450/29-03309-1225", "Renovación Pagos Oportunos"),
    ("scotiabank-pasivos-valora-", "0319-138-007481/26-03331-1225", "Pago de Pasivos Valora"),
    ("scotiabank-pasivos-pagos-oportunos-", "0319-138-007480/26-03330-1225", "Pago de Pasivos Pagos Oportunos"),
    ("scotiabank-7x5-pasivo-hipotecario-", "0319-138-038243/05-03345-1225", "Pago de Pasivo Hipoteca 7 x 5"),
    ("scotiabank-7x5-adquisicion-", "0319-138-020519/18-03342-1225", "Adquisición Hipoteca 7 x 5"),
    ("scotiabank-liquidez-libre-valora-", "0319-138-027732/16-03349-1225", "Crediliquidez Libre Valora"),
    ("scotiabank-liquidez-libre-pagos-oportunos-", "0319-138-027734/16-03351-1225", "Crediliquidez Libre Pagos Oportunos"),
    ("scotiabank-liquidez-libre-7x5-", "0319-138-027733/16-03350-1225", "Crediliquidez Libre Hipoteca 7x5"),
)


def _reca_vigente(producto_id):
    return next(((r, n) for prefijo, r, n in _RECA_VIGENTE if producto_id.startswith(prefijo)), None)


def _con_reca_vigente(p):
    registro, nombre = _reca_vigente(p.id)
    notas = p.notas
    if p.id.startswith("scotiabank-credirenovacion-pasivo-"):
        # Cláusula Décima Tercera c) del contrato, leída en el RECA.
        notas += (" El contrato RECA pacta el avalúo como «gastos de preoriginación - "
                  "avalúo hipotecario» con el monto en blanco: confirma que se cobra, no "
                  "cuánto.")
    return replace(
        p,
        fuente=p.fuente + f" Contrato vigente en el RECA: «{nombre}» {registro}, "
        "registrado 2026-01-19 (consultado 2026-10-26).",
        notas=notas,
    )


CATALOGO[:] = [
    _con_reca_vigente(p) if p.vigente_hasta is None and _reca_vigente(p.id) else p
    for p in CATALOGO
]
