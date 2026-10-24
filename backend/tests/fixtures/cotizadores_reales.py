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
        # Añadidos al releer el archivo (HojaMaestra, Param, TablaTasas):
        "producto": "Mejora de Hipoteca (código 4), Pagos Fijos",
        "valor_inmueble": D("1350000"),                 # HojaMaestra!C7
        # Daños: valor × 70 % × 0.074364‰ × 1.16 mensual (X10). seguro_fijo
        # de arriba es ese valor cortado a 4 decimales (81.5178168).
        "seguro_danos_factor_construccion": D("0.7"),   # Param!D9
        "seguro_danos_tasa_anual": D("0.00103514688"),  # 0.074364/1000 × 1.16 × 12
        # Vida 0.424‰ + ITP 0.106‰ + desempleo 0.3‰ (Titular asalariado)
        "comision_apertura_pct": D("0.015"),            # Param!AL8, sin IVA
        "avaluo": D("4228.2"),                          # 2.7‰ × valor × 1.16
    },
    # CAT: apertura completa; avalúo, comisión mensual y daños ÷ 1.16;
    # vida/ITP/desempleo completos. TablAmoPagosFijos!O7 "CAT sin IVA".
    "cat_esperado": D("0.12916475266745042"),
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

# ---------------------------------------------------------------------------
# Banregio — pagos crecientes (hoja TablAmoPagosCrec del mismo archivo)
# ---------------------------------------------------------------------------
# Mismo monto, tasa, valor, fecha y seguros que BANREGIO. Diferencias:
#   - Plazo fijo de 240 meses en las fórmulas (no sigue HojaMaestra!C4); la
#     tasa 10.20 % es la del tramo de 10 años: el archivo mezcla ambos.
#   - El pago base (capital + interés a tasa/12) crece CADA MES, en dos fases:
#       meses 1-72:  ÷ (1 − 0.0011)   (Param!CU9 = −0.0011, AC = AC_prev/0.9989)
#       mes 73:      se recalcula sobre el saldo y los 168 meses restantes
#       meses 73+:   × 1.0017         (Param!CU10)
#     En cada fase el pago inicial es la anualidad creciente que liquida el
#     saldo en el plazo restante (AB10, AB82).
#   - Seguros y comisión van fuera del pago base (no crecen).
#   - El seguro de desempleo se cobra siempre (sin la condición de fijos).
BANREGIO_CRECIENTE = {
    "institucion": "Banregio",
    "archivo": "BANREGIO_MULTIPRODUCTO.xlsm",
    "hoja": "TablAmoPagosCrec",
    "parametros": {
        "monto": D("1215000"),
        "tasa_anual": D("0.1020"),
        "plazo_meses": 240,
        "fecha_primer_pago": "2023-12-01",
        "valor_inmueble": D("1350000"),
        "seguro_tasa_saldo": D("0.00083"),
        "seguro_danos_factor_construccion": D("0.7"),
        "seguro_danos_tasa_anual": D("0.00103514688"),
        "comision_mensual": D("250"),
        "comision_apertura_pct": D("0.015"),
        "avaluo": D("4228.2"),
        "fase_1_divisor": D("0.9989"),     # 1 + Param!CU9
        "fase_2_desde_mes": 73,
        "fase_2_factor": D("1.0017"),      # 1 + Param!CU10
    },
    "cat_esperado": D("0.12622154700526034"),  # O7
    # mes: (fecha, saldo_inicial, interes, capital, seguros, pago_total, saldo_final)
    "renglones": {
        1: ("2023-12-01", D("1215000"), D("10671.749999999998"), D("513.76987179268326"),
            D("1089.9678168"), D("12525.487688592682"), D("1214486.2301282072")),
        2: ("2024-01-01", D("1214486.2301282072"), D("10667.23738795942"), D("530.0754449440592"),
            D("1089.5413878064119"), D("12536.854220709891"), D("1213956.1546832633")),
        12: ("2024-11-01", D("1208426.2514980787"), D("10271.62313773367"), D("701.69602616366501"),
             D("1084.5116055434053"), D("12307.830769440739"), D("1207724.5554719151")),
        13: ("2024-12-01", D("1207724.5554719151"), D("10607.847345561655"), D("719.74438580410424"),
             D("1083.9291978416895"), D("12661.520929207449"), D("1207004.811086111")),
        24: ("2025-11-01", D("1198777.3110131787"), D("10189.607143612018"), D("929.60083351658795"),
             D("1076.5029849409384"), D("12445.710962069545"), D("1197847.7101796621")),
        25: ("2025-12-01", D("1197847.7101796621"), D("10521.095721078031"), D("949.74703843393581"),
             D("1075.7314162491195"), D("12796.574175761087"), D("1196897.9631412281")),
        60: ("2028-11-01", D("1151201.9408350645"), D("9785.2164970980466"), D("1783.3988417346773"),
             D("1037.0154276931037"), D("12855.630766525828"), D("1149418.5419933298")),
        72: ("2029-11-01", D("1127903.5262416091"), D("9587.1799730536786"), D("2135.238562177823"),
             D("1017.6777435805355"), D("12990.096278812038"), D("1125768.2876794313")),
        73: ("2029-12-01", D("1125768.2876794313"), D("9887.9981267843377"), D("1703.6683208809227"),
             D("1015.9054955739279"), D("12857.571943239189"), D("1124064.6193585503")),
        120: ("2033-11-01", D("1003629.1702317928"), D("8530.8479469702397"), D("3678.6714493484124"),
              D("914.53002809238808"), D("13374.04942441104"), D("999950.4987824444")),
        121: ("2033-12-01", D("999950.4987824444"), D("8782.8985476391372"), D("3730.6963396416159"),
              D("911.47673078942876"), D("13675.071618070182"), D("996219.80244280281")),
        240: ("2043-11-01", D("14843.746177573685"), D("126.17184250937632"), D("14843.746177573685"),
              D("93.838126127386147"), D("15313.756146210448"), D("0")),
    },
}

TODOS = [HSBC, SANTANDER, BANREGIO, BANREGIO_CRECIENTE]

# ---------------------------------------------------------------------------
# Instituciones sin escenario capturado — no validables hoy
# ---------------------------------------------------------------------------
SIN_ESCENARIO = {
    "Scotiabank": "Los ocho cotizadores se distribuyen en blanco.",
    "Banamex": "Tablas en estado #VALUE! / #REF!. Relevante porque es el único "
               "que redondea el factor por millar hacia arriba.",
}
