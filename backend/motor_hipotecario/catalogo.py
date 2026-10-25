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

from .modelos import (
    AportacionExcedente,
    BaseSeguroDanos,
    ConceptoIVA,
    ConvencionDias,
    ProductoHipotecario,
    ReglaAportaciones,
    TasaVariable,
    TipoLinea,
)

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
        vigente_desde=date(2026, 8, 21),
        fuente="Cotizador BANAMEX.xlsm, hoja ADQUISICION, producto Hipoteca "
        "Perfiles (Calculos CF:DH, TablaPerfiles). Versión v.20260824, "
        "'Vigencia: Agosto 2026'. SIN escenario capturado: validado contra sus "
        "fórmulas y contra los factores al millar guardados (CR104:CR106).",
        notas="Tasa de Mercado abierto; con vinculación al banco baja hasta 9.05 %. "
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
]
