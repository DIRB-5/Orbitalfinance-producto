# Análisis de metodología de cálculo — cotizadores bancarios

**Preparado para:** Dirección de Riesgo
**Fecha:** 22 de octubre de 2026
**Alcance:** 24 archivos de cotización de 8 instituciones financieras mexicanas

---

## 1. Método

Los archivos son cotizadores en Excel con macros. Las hojas están protegidas, pero la
protección de hoja no es cifrado: las fórmulas son legibles íntegramente.

El análisis se hizo leyendo las fórmulas directamente del XML de cada libro, no
infiriendo el modelo a partir de entradas y salidas. En total se procesaron
aproximadamente 780,000 fórmulas. Cada afirmación de este documento está respaldada
por la fórmula literal que se cita entre comillas.

**Lo que este documento todavía no acredita:** no se ha reconstruido cada modelo en
código ni se ha verificado que nuestra reproducción empate renglón por renglón contra
el Excel original. Ese es el siguiente paso y es el que convierte "leímos las fórmulas"
en "reproducimos sus números". Las conclusiones aquí son de lectura de código, no de
replicación validada.

---

## 2. Resumen ejecutivo

| # | Hallazgo | Severidad |
|---|---|---|
| 1 | Coexisten **tres convenciones distintas de conteo de días**. Comparar tasas nominales entre instituciones sin normalizar produce un sesgo sistemático de ~1.39 % | **Alta** |
| 2 | El **CAT se construye igual en todas las instituciones**: TIR mensual anualizada por composición | Informativa |
| 3 | Las comisiones entran al flujo del CAT **netas de IVA** (divididas entre 1.16) | Media |
| 4 | El **seguro de vida no es una tasa plana**: lleva extraprima por edad, condición médica y ocupación | Media |
| 5 | Existen estructuras de producto (gracia, ministraciones, pago creciente, cofinanciamiento) que un modelo de amortización francesa simple no representa | Media |
| 6 | Un archivo del conjunto (`Comparador.xlsx`) no es un cotizador: no contiene fórmulas | Baja |

---

## 3. Hallazgo 1 — Convención de conteo de días

### 3.1 El problema

Para convertir una tasa anual en interés del periodo, las instituciones usan tres
convenciones distintas. Ninguna la declara en su material comercial.

| Convención | Factor mensual | Instituciones | Fórmula literal observada |
|---|---|---|---|
| `tasa / 12` | 0.0833333 × tasa | Banamex, HSBC, BX | `C127*$G$13/12` · `PMT(Q21/12,$E$15*12,-$J$9)` · `F7 = F6/12` |
| `tasa / 360 × 30.4166` | 0.0844906 × tasa | Santander | `L24*F9*30.4166/360` |
| `tasa / 360 × 30.4` | 0.0844444 × tasa | Banorte | `PMT(F2/360*30.4,C4,-C3)` · `J1/360*30.4` |
| `tasa / 360 × días reales` | variable | Scotiabank, Banregio, Afirme | `F23*E23/360*AI23` · `D10*U10*F10/360` · `N21*D21*E21/360` |

En las tres últimas, el divisor es 360 pero el multiplicador son días de un mes de
calendario. Como el año tiene 365 días y no 360, el resultado anualizado excede la
tasa nominal declarada.

### 3.2 Cuantificación

Tasa nominal de 10.85 %, equivalencia en base `/12`:

| Convención | Factor anual | 10.85 % equivale a |
|---|---|---|
| `/12` | 1.000000 | 10.8500 % |
| `30.4/360` (Banorte) | 1.013333 | **10.9947 %** |
| `30.4166/360` (Santander) | 1.013887 | **11.0007 %** |
| días reales / 360, año normal | 1.013889 | **11.0007 %** |
| días reales / 360, año bisiesto | 1.016667 | **11.0308 %** |

Sobre un crédito de **$1,850,000 a 10.85 % y 240 meses**:

| | Base `/12` | Base 360 | Diferencia |
|---|---|---|---|
| Pago mensual (capital + interés) | $18,906.99 | $19,096.33 | **+$189.34** |
| Intereses totales del periodo | $2,687,678 | $2,733,119 | **+$45,441** |

Regla práctica: **por cada $1,000,000 a 20 años y 10.85 %, la base 360 cuesta
aproximadamente $24,563 más** que la base `/12`.

### 3.3 Implicación

El sesgo apunta siempre en la misma dirección: la base 360 siempre favorece a la
institución. Una tabla comparativa que ordene por tasa nominal **sin normalizar la
base de días está sistemáticamente mal ordenada**, y el error es de aproximadamente
15 puntos base, suficiente para invertir el orden entre productos cercanos.

Para el comparador, la recomendación es registrar la convención como atributo del
producto y presentar una **tasa normalizada equivalente** junto a la nominal.

---

## 4. Hallazgo 2 — Construcción del CAT

Todas las instituciones revisadas usan la misma estructura:

```
CAT = (1 + TIR(flujos mensuales))^12 − 1
```

Citas literales:

- **Banamex** — `Calculos!AX100`: `((IRR(BE106:BE346,0.0001)+1)^12)-1`
- **Santander** — `CAT!E20`: `(1+IRR(O24:O324,0.01))^12-1`
- **HSBC** — `Amortización!K17`: `((1+IRR(V20:V320))^(12))-1`

Es decir: se resuelve la tasa interna de retorno sobre el flujo **mensual** y se
anualiza por composición. Es matemáticamente equivalente a descontar con exponente
expresado en años, que es el método que usa nuestro motor.

**Composición del flujo inicial**, verificada en dos instituciones:

- **Banamex** — `Calculos!BE106`: `-AX107-AX64-IF(BE28<3,AX63,0)`
  donde `AX107` = monto dispuesto, `AX64` = comisión por apertura
  (`AX60*AX77`), `AX63` = gastos de investigación, condicionado.
- **Santander** — `CAT!O24`: `-L24+L10`, con `L10 = SUM(L5:L9)` compuesto de
  comisión de apertura, avalúo y otros cargos.

El flujo del periodo incluye pago de capital e interés, seguro de vida, seguro de
daños y comisión mensual. En Santander: `J25 = F25+G25+H25+I25`.

**Conclusión:** la metodología de CAT es homogénea en el mercado y coincide con la
nuestra. No es fuente de discrepancia.

---

## 5. Hallazgo 3 — Tratamiento del IVA en el CAT

Las comisiones entran al flujo del CAT **divididas entre 1.16**, es decir, netas de IVA.

- **Santander** — `CAT!L5`: `Cal!AB111/1.16` (comisión de apertura)
- **Santander** — `CAT!L8`: `Cal!AB113/1.16`
- **Santander** — `CAT!H25`: `Adm!$AA$11*$X$4/1.16` (seguro de daños)
- **Santander** — `CAT!I25`: `Cal!$AB$126/1.16` (comisión mensual)
- **Banamex** — `Calculos!AX63`: `VLOOKUP(...)/1.16`
- **HSBC** — `Tabla_Amortización_Redisponible`: `...+H21/1.16+$N$15`

En sentido inverso, BX multiplica por 1.16 al presentar cifras al usuario
(`Simulador CH BX+!K12`: `VResPlus!F27*1.16`), lo que confirma que el valor
almacenado internamente es neto y el IVA se agrega solo para despliegue.

**Que cuatro instituciones independientes apliquen el mismo tratamiento sugiere que
responde a la metodología regulatoria y no al criterio de cada emisor.**

**Punto a confirmar por el área de riesgo:** solicitamos validación contra la
disposición de Banxico aplicable, para determinar si el IVA debe excluirse del flujo
del CAT en todos los conceptos o solo en algunos. Nuestro motor actualmente incorpora
las comisiones a valor bruto, lo que produce un CAT sobreestimado frente al publicado.
Esta es, con alta probabilidad, la causa principal de la discrepancia que veníamos
observando.

---

## 6. Hallazgo 4 — Estructura del seguro de vida

El seguro de vida se calcula sobre **saldo insoluto**, lo que coincide con nuestro
modelo. Lo que no coincide es que la tasa aplicada **no es única**: depende del perfil
del acreditado.

Banamex — `Calculos!BC107`, simplificado:

```
IF(edad >= 65,            base * EXTRAPRIMAEDAD,
IF(condición_médica,      base * EXTRAPRIMAMEDICA,
IF(ocupación_de_riesgo,   base * EXTRAPRIMAOCUPACIONAL,
                          base * FACTORVIDA)))
```

Hay extraprima por edad a partir de los 65 años, por condición médica declarada y por
ocupación de riesgo. La fórmula incluye además un tope:
`MAX(BC90*AX17, AX42*0.8*AX17)`.

**Implicación:** el costo total de un mismo producto varía por perfil del acreditado.
Ningún comparativo del mercado refleja esto hoy. Para el comparador significa que la
prima no puede modelarse como un parámetro único del producto; es función del producto
y del solicitante.

### Seguro de daños

Se confirma la distinción entre base de cálculo sobre valor total y sobre valor de
construcción. BX la implementa como una opción explícita — `VResPlus!V7`:
`IF('Simulador CH BX+'!$D$11="Valor Destructible", ...)`. Nuestro modelo ya contempla
ambas bases.

---

## 7. Hallazgo 5 — Estructuras de producto no estándar

Los siguientes mecanismos están presentes en los cotizadores y no se representan con
un modelo de amortización francesa de pago fijo:

| Mecanismo | Institución | Evidencia |
|---|---|---|
| **Periodo de gracia** | Afirme | `IF(B21 < MESES_GRACIA, 0, ...)` en `Tabla Amortización Liquidez` |
| **Ministraciones** | Banregio | Hoja `TablAmoPagosFijosMinist` |
| | HSBC | `Simul_ConstruRemo`: `IF(AN61="Ministración", G61*S61/12, ...)` |
| **Pago creciente** | Santander | `CAT!F26`: `MIN(L24+D26, F25*(1+S26))` |
| | Banregio | Hoja `TablAmoPagosCrec` |
| | Afirme | Hojas `Parametros Crec`, `Tabla Crec` |
| | Scotiabank | `Tabla 7x5`: `...*(1+Z77)` |
| **Tasa escalonada** | Banamex | `TablaCTH!S128`: recalcula el pago cuando `G128<>G127` (cambia la tasa) |
| **Cofinanciamiento** | Banorte, BX | Archivos `BANORTE_FOVISSSTE`, `BX_COFI`, `BX_INFONAVIT`; hoja `COFINAVIT` |
| **Seguro de deudor capitalizado** | Afirme | `1 + D21*F21/360 + FACTOR_SEG_DEUD` — la prima se incorpora al factor de capitalización |

Este último caso de Afirme merece atención: el seguro no se suma como concepto
separado del pago, sino que se incorpora al factor que capitaliza el saldo. Cambia
la mecánica de la tabla, no solo su monto.

---

## 8. Riesgos de modelo identificados

**8.1 Comparabilidad entre instituciones.** Dado el hallazgo 1, cualquier
comparativo que ordene por tasa nominal está sesgado. El riesgo no es de cálculo
sino de recomendación: puede llevar a sugerir un producto más caro como si fuera
el más barato.

**8.2 Plazo efectivo distinto del plazo contratado.** En productos con tasa
escalonada decreciente y pago fijo, el crédito amortiza más rápido de lo que indica
el plazo nominal. Comparar sumas de mensualidades entre productos con plazos
efectivos distintos no es válido sin normalizar.

**8.3 Redondeo por millar.** Banamex calcula el pago sobre una base de $1,000 y
redondea hacia arriba antes de escalar: `ROUNDUP(PMT($G$13/12, n, -1000), 2)` y
después `C127*factor/1000`. El redondeo hacia arriba es sistemáticamente favorable
a la institución. **Se cuantificó y el efecto es inmaterial**: en el escenario de
prueba, $1.75 sobre 240 meses. Se documenta para cerrar el punto.

**8.4 Celdas con error en los archivos de origen.** Varios libros contienen celdas
en estado `#REF!`, `#N/A`, `#DIV/0!` y `#VALUE!` en sus tablas de amortización
(observado en Afirme y Banamex). Puede tratarse de ramas inactivas del modelo o de
errores reales. **Requiere revisión antes de tomar cualquier cifra de esos archivos
como referencia.**

---

## 9. Implicaciones para nuestro motor de cálculo

| Componente | Estado | Acción |
|---|---|---|
| Amortización francesa | Correcto | Ninguna |
| CAT por TIR anualizada | Correcto | Ninguna |
| Seguro de vida sobre saldo insoluto | Correcto en estructura | Agregar multiplicadores por perfil |
| Seguro de daños, base configurable | Correcto | Ninguna |
| **Convención de conteo de días** | **No implementado** | Agregar como atributo del producto |
| **IVA en el flujo del CAT** | **No implementado** | Excluir, sujeto a confirmación regulatoria |
| Tasa escalonada | No implementado | Calendario de tasas por periodo |
| Pago creciente | No implementado | Factor de crecimiento anual |
| Comisión mensual fija | No implementado | Concepto adicional en el flujo |
| Periodo de gracia y ministraciones | No implementado | Requiere rediseño de la construcción de tabla |
| Cofinanciamiento | Modelado estructuralmente | Implementar reglas por instituto |

Los dos primeros renglones en negritas son los que explican por qué nuestro CAT no
empataba con el publicado. Son correcciones acotadas.

---

## 10. Preguntas para la Dirección de Riesgo

1. **¿El IVA se excluye del flujo del CAT en todos los conceptos o solo en
   comisiones?** Cuatro instituciones lo excluyen; necesitamos la base normativa
   para replicarlo con fundamento y no por imitación.

2. **¿Qué convención de conteo de días debe usar nuestro comparador por defecto?**
   Proponemos conservar la del producto para el cálculo y exponer una tasa
   normalizada en base `/12` únicamente para efectos de ordenamiento.

3. **¿Se considera aceptable presentar al cliente final una tasa normalizada
   equivalente?** Es informativamente correcto pero no es la tasa contractual, y
   conviene definir cómo rotularla.

4. **¿Cómo se desea tratar la extraprima del seguro de vida** cuando el perfil del
   acreditado aún no se conoce en la etapa de cotización?

5. **¿Los cotizadores recibidos son los oficiales vigentes de cada institución?**
   Varios contienen celdas en error. Confirmarlo determina cuánta autoridad tienen
   estos hallazgos.

---

## Anexo — Inventario de archivos

| Institución | Archivos | Producto / observación |
|---|---|---|
| **Banamex** | `BANAMEX.xlsm` | 16 hojas: Adquisición, Cambia tu Hipoteca, Liquidez, CTH + Liquidez |
| **Banorte** | `BANORTE_SIMULADOR_UNIVERSAL.xlsm` | 30 hojas, incluye COFINAVIT y notariales por estado |
| | `BANORTE_FOVISSSTE.xlsm` | 28 hojas, cofinanciamiento |
| | `BANORTE_MEJORA_MAS_LIQUIDEZ.xlsx` | Sustitución + liquidez, con hoja CAT y de prepagos |
| **Banregio** | `BANREGIO_MULTIPRODUCTO.xlsm` | Pagos fijos, crecientes y con ministraciones |
| **BX** | `BX_TRADICIONAL`, `BX_LIQUIDEZ`, `BX_MEJORA_TU_HIPOTECA`, `BX_COFI`, `BX_INFONAVIT` | Estructura común de 2 hojas |
| **Afirme** | `AFIRME_MULTIPRODUCTOS.xlsm`, `AFIRME_TERRENO_90.xlsm` | Liquidez, fijo y creciente; periodo de gracia |
| **HSBC** | `HSBC_full.xlsm` | 18 hojas, incluye construcción y remodelación |
| | `hsbc_cicb.xlsm` | 4 hojas |
| **Scotiabank** | `SCOTIABANK_Pago_de_pasivos` (×2), `Liquidez_Libre` (×2), `Multiproducto_7x5`, `Preventa_7x5`, `Credirenovacion`, `Construccion` | Variantes Valora, Pagos Oportunos y 7x5 |
| — | `Comparador.xlsx` | **No es cotizador**: 1 hoja, 0 fórmulas |

---

## Siguiente paso propuesto

Reconstruir en código los modelos de cuatro instituciones representativas de cada
convención de días — Banamex (`/12`), Santander (`30.4166/360`), Scotiabank (días
reales) y Banregio (días reales con pago creciente) — y validar la reproducción
renglón por renglón contra el Excel original. Si no empata al centavo, el modelo no
está entendido.

Cada caso validado se convierte en una prueba de regresión permanente del motor.
