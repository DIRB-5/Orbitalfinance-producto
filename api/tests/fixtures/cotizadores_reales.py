"""
Puntos de control extraídos de cotizadores bancarios reales.

ESTOS VALORES SON VERDAD DE CAMPO. No se recalculan ni se ajustan: salieron de
las tablas de amortización que el propio Excel de cada institución tenía
calculadas y guardadas. Si una prueba contra estos valores falla, el error está
en el motor, nunca en el fixture.

Cada escenario fue reproducido al centavo en los 240, 300 o 120 renglones de su
tabla completa, con saldo final exactamente en cero. El procedimiento y la
evidencia están en docs/validacion_modelos.md.

Para agregar un escenario nuevo se necesita un cotizador CON UN ESCENARIO
CAPTURADO Y GUARDADO. Los archivos en blanco no sirven: no tienen valores
calculados contra los cuales comparar.
"""

from decimal import Decimal as D

# ---------------------------------------------------------------------------
# HSBC — convención tasa/12
# ---------------------------------------------------------------------------
HSBC = {
    "institucion": "HSBC",
    "archivo": "hsbc_cicb.xlsm",
    "hoja": "Amortización",
    "convencion_interes": "tasa/12",
    "convencion_amortizacion": "tasa/12",
    "parametros": {
        "monto": D("2082500"),
        "tasa_anual": D("0.1175"),
        "plazo_meses": 240,
        "seguro_vida_mensual": D("0.00044"),      # 0.44 por millar sobre saldo
        "seguro_danos_mensual": D("777.63"),       # monto fijo
        "comision_mensual": D("290"),
        "comision_apertura_pct": D("0.01"),
        "avaluo": D("12470"),
    },
    # CAT: comisión de apertura COMPLETA, avalúo NETO de IVA
    "cat_esperado": D("0.13983928371930143"),
    "cat_desembolso_neto": D("2050925.00"),
    "cat_iva": {
        "capital_interes": "completo",
        "seguro_vida": "completo",          # exento de IVA
        "seguro_danos": "neto",             # ÷ 1.16
        "comision_mensual": "neto",         # ÷ 1.16
        "avaluo": "neto",                   # ÷ 1.16
        "comision_apertura": "completo",
    },
    # mes: (capital, interes, seguro_vida, pago_total, saldo_final)
    "renglones": {
        1:   (D("2177.0537441235465"),  D("20391.145833333332"), D("916.3"),
              D("24552.12957745688"),   D("2080322.9462558764")),
        12:  (D("2423.3645818235636"),  D("20144.834995633315"), D("905.2317342718632"),
              D("24541.061311728743"),  D("2054921.486036047")),
        60:  (D("3868.5152117281614"),  D("18699.684365728717"), D("840.2921995833842"),
              D("24476.121777040265"),  D("1905886.4838414178")),
        120: (D("6941.4667827374"),     D("15626.732794719479"), D("702.2055247329265"),
              D("24338.035102189806"),  D("1588980.1803375501")),
        240: (D("22349.3620738174"),    D("218.83750363948081"), D("9.833719312480502"),
              D("23645.66329676936"),   D("0")),
    },
}

# ---------------------------------------------------------------------------
# Santander — convención tasa/360 x 30.4166
# ---------------------------------------------------------------------------
# OJO: dos factores distintos dentro del mismo modelo.
#   pago    -> (tasa/360) * (365/12)        365/12 periódico: 30.41666...
#   interés -> tasa * 30.4166/360           constante truncada
# La diferencia es 1.759e-8 mensual. Si no se replica, la tabla no empata.
SANTANDER = {
    "institucion": "Santander",
    "archivo": "Santander.xlsm",
    "hoja": "CAT",
    "convencion_interes": "tasa * 30.4166/360",
    "convencion_pago": "(tasa/360) * (365/12)",
    "parametros": {
        "monto": D("1770000"),
        "tasa_anual": D("0.095"),
        "plazo_meses": 300,
        "seguro_vida_mensual": D("0.0008254"),
        "seguro_danos_mensual": D("380.17"),
        "comision_mensual": D("350"),
        "comision_apertura": D("6034.48275862069"),   # ya neta de IVA en el archivo
    },
    "cat_esperado": D("0.11847260599095755"),
    "tolerancia_cat_pb": D("0.001"),
    # mes: (interes, capital, seguro_vida, pago_total, saldo_final)
    "renglones": {
        1:   (D("14207.086916666667"), D("1419.9957631840516"), D("1460.958"),
              D("17818.213093643823"), D("1768580.004236816")),
        12:  (D("14076.556943231619"), D("1550.5257366191"),    D("1447.535205443432"),
              D("17804.790299087257"), D("1752187.3049435748")),
        60:  (D("13351.279619394096"), D("2275.803060456623"),  D("1372.952730183428"),
              D("17730.20782382725"),  D("1661102.837820847")),
        180: (D("9687.253964329499"),  D("5939.82871552122"),   D("996.1698172350916"),
              D("17353.424910878915"), D("1200953.577190817")),
        300: (D("124.17481283539253"), D("15470.40712905083"),  D("12.769274044318555"),
              D("16337.523629723642"), D("0")),
    },
}

# ---------------------------------------------------------------------------
# Banregio — días reales/360 para el interés, tasa/12 para la amortización
# ---------------------------------------------------------------------------
# Producto "pagos fijos" cuyo pago NO es fijo: varía con los días del mes.
# En este escenario va de $16,862.13 (febrero) a $17,547.48 (meses de 31 días).
BANREGIO = {
    "institucion": "Banregio",
    "archivo": "BANREGIO_MULTIPRODUCTO.xlsm",
    "hoja": "TablAmoPagosFijos",
    "convencion_interes": "tasa * dias_reales_del_mes / 360",
    "convencion_amortizacion": "tasa/12",
    "parametros": {
        "monto": D("1215000"),
        "tasa_anual": D("0.1020"),
        "plazo_meses": 120,
        "fecha_primer_pago": "2023-12-01",
        "pago_base_fijo": D("16953.2283"),      # incluye el seguro
        "seguro_fijo": D("81.5178"),
        "seguro_tasa_saldo": D("0.00083"),
        "comision_mensual": D("250"),
    },
    # mes: (fecha, saldo_inicial, interes, amortizacion, seguros, pago_total)
    "renglones": {
        1:   ("2023-12-01", D("1215000"),           D("10671.749999999998"),
              D("5535.760519107833"),  D("1089.9678168"),       D("17547.478335907832")),
        12:  ("2024-11-01", D("1151184.9450441587"), D("9785.072032875349"),
              D("6131.154981845832"),  D("1037.0013211866517"), D("17203.228335907832")),
        60:  ("2028-11-01", D("782078.6080832311"),  D("6647.668168707465"),
              D("9574.917105691286"),  D("730.6430615090818"),  D("17203.228335907832")),
        120: ("2033-11-01", D("16715.75254784692"),  D("142.0838966566988"),
              D("16715.75254783642"),  D("95.39189141471294"),  D("17203.228335907832")),
    },
    # El pago varía por duración del mes. Comparación dentro del primer año,
    # donde el saldo es casi el mismo y la única variable son los días:
    "pago_dic_2023": D("17547.4783"),   # mes 1,  31 días
    "pago_feb_2024": D("16862.1299"),   # mes 3,  29 días
    "variacion_primer_anio": D("685"),  # diferencia mínima esperada
}

TODOS = [HSBC, SANTANDER, BANREGIO]

# ---------------------------------------------------------------------------
# Instituciones sin escenario capturado — no validables hoy
# ---------------------------------------------------------------------------
SIN_ESCENARIO = {
    "Scotiabank": "Los ocho cotizadores se distribuyen en blanco.",
    "Banamex": "Tablas en estado #VALUE! / #REF!. Relevante porque es el único "
               "que redondea el factor por millar hacia arriba.",
}
