# Validación de modelos — resultados de la reconstrucción

**Preparado para:** Dirección de Riesgo
**Fecha:** 22 de octubre de 2026
**Complementa:** `analisis_cotizadores.md`

---

## 1. Qué se hizo y cómo se acredita

Se reconstruyeron en código los modelos de cálculo de cuatro instituciones
representativas de cada convención de conteo de días, y se compararon contra los
**valores calculados que cada archivo de Excel tiene almacenados en caché**.

El criterio de validación es estricto: la reconstrucción se considera correcta
únicamente si cada renglón de la tabla de amortización coincide al centavo con el
valor que el propio Excel calculó, y si el saldo cierra exactamente en cero.

---

## 2. Resultado

| Institución | Convención | Escenario del archivo | Renglones | Resultado |
|---|---|---|---|---|
| **Santander** | `tasa/360 × 30.4166` | $1,770,000 @ 9.50 %, 300 meses | 300 | **300/300 exactos** |
| **HSBC** | `tasa/12` | $2,082,500 @ 11.75 %, 240 meses | 240 | **240/240 exactos** |
| **Banregio** | días reales / 360 | $1,215,000 @ 10.20 %, 120 meses | 120 | **120/120 exactos** |
| Scotiabank | días reales / 360 | — | — | No validable (ver 2.1) |
| Banamex | `tasa/12` | — | — | No validable (ver 2.1) |

En los tres casos validados, la diferencia máxima en toda la tabla fue de **$0.0024
o menos**, el saldo final cerró en **$0.00 exacto**, y el CAT reconstruido coincidió
con el del archivo.

### 2.1 Archivos no validables

Los cotizadores de **Scotiabank** (los ocho) y de **Banamex** se distribuyen sin
escenario capturado: sus tablas de amortización están vacías o en estado de error
(`#VALUE!`, `#REF!`). No hay valores calculados contra los cuales comparar.

Esto no impide leer sus fórmulas —el análisis metodológico del documento anterior
sigue siendo válido— pero **no podemos acreditar que reproducimos sus números**.
Para cerrar ese hueco se necesita que alguien capture un escenario en cada uno y
nos devuelva el archivo guardado. Es trabajo de minutos y convendría pedirlo.

---

## 3. Hallazgos nuevos surgidos de la validación

Estos no se detectaron leyendo fórmulas: aparecieron al intentar reproducir los
números y no lograrlo.

### 3.1 Santander usa dos factores distintos dentro del mismo modelo

- El **pago** se calcula con `(tasa/360)*(365/12)`, donde `365/12` es un decimal
  periódico: 30.416666…
- El **interés del periodo** se calcula con la constante truncada `30.4166/360`

La diferencia entre ambos factores es de **1.759 × 10⁻⁸ mensual**. En pesos es
irrelevante. Pero si no se replica exactamente, la tabla no empata y el error se
acumula hasta $32 al final del plazo, lo que lleva a buscar la causa donde no está.

Se documenta porque cualquiera que intente replicar el modelo de Santander va a
tropezar con esto.

### 3.2 La regla del IVA es por concepto, no uniforme

En el documento anterior se reportó que las comisiones entran al CAT netas de IVA.
La reconstrucción de HSBC permite precisar la regla, porque su flujo de CAT se
reprodujo con **coincidencia exacta a diez decimales**:

| Concepto | Tratamiento en el flujo del CAT |
|---|---|
| Capital e interés | Completo |
| **Seguro de vida** | **Completo** |
| Seguro de daños | Neto de IVA (÷ 1.16) |
| Comisión mensual | Neto de IVA (÷ 1.16) |
| Avalúo | Neto de IVA (÷ 1.16) |
| **Comisión por apertura** | **Completa** |

Verificación numérica, HSBC:

```
Desembolso inicial del CAT  = 2,082,500 − 20,825 − 12,470/1.16 = −2,050,925.00
Archivo (Amortización!V20)  = −2,050,925.00                      ✓ exacto

Flujo del mes 1 = 22,568.1995 + 916.30 + 777.63/1.16 + 290/1.16 = 24,404.87026711
Archivo (Amortización!V21)                                      = 24,404.87026711205  ✓

CAT reconstruido = 13.9839283719 %
Archivo (K17)    = 13.9839283719 %     diferencia: 0.00000000 puntos base
```

La lógica aparente es que **se excluye el IVA solo de los conceptos que lo causan**.
El seguro de vida entra completo porque está exento; el de daños, el avalúo y las
comisiones mensuales entran netos porque lo causan.

**Discrepancia entre instituciones:** HSBC mete la comisión por apertura **completa**,
mientras que Santander la divide entre 1.16 (`CAT!L5 = Cal!AB111/1.16`). Es el único
concepto donde dos instituciones difieren en el tratamiento. Convendría que riesgo
determine cuál es el correcto, porque afecta el CAT publicado de cada una.

### 3.3 Banregio: amortiza con una convención y cobra con otra

Es el hallazgo más consecuente de esta etapa.

Banregio calcula las dos cosas con bases distintas:

- **Amortización de capital** — `AI10`: `AH10 - M10 - (D10*(F10*100)/1200)`
  El divisor 1200 sobre la tasa en porcentaje equivale a **`tasa/12`**
- **Interés cobrado** — `G10`: `D10*F10*AV10/360`
  donde `AV10` = `DAY(DATE(YEAR(C10),MONTH(C10)+1,1)-1)` = **días reales del mes**

Consecuencia: aunque el producto se llama "pagos fijos", **el pago que el cliente
realiza varía mes con mes según la duración del calendario**. En el escenario del
archivo:

| Mes | Días | Pago |
|---|---|---|
| Diciembre | 31 | $17,547.48 |
| Enero | 31 | $17,545.91 |
| **Febrero 2024** | **29** | **$16,862.13** |
| Marzo | 31 | $17,542.73 |
| Abril | 30 | $17,203.23 |

**Variación de $685 entre el mes más caro y el más barato.** Un cliente que compare
productos por "mensualidad" está comparando una cifra que en este producto no es
única.

Reconstrucción validada: 120/120 renglones exactos, diferencia máxima $0.000000,
saldo final $0.00.

El seguro se descompone en $81.52 fijo más 0.00083 mensual sobre saldo insoluto,
y está incorporado dentro del pago base fijo, no sumado por fuera.

### 3.4 Los bancos no redondean en la cadena de cálculo

Ninguno de los tres modelos validados redondea valores intermedios. Excel mantiene
precisión completa en toda la tabla y el redondeo a centavos ocurre **únicamente al
desplegar**.

Esto se detectó porque la primera reconstrucción, que redondeaba cada renglón a
centavos como haría un sistema transaccional, acumulaba una desviación promedio de
$1.06 en el saldo y llegaba a $32 de diferencia al final del plazo. Al eliminar el
redondeo intermedio, la coincidencia pasó a ser exacta.

**Implicación para nuestro motor:** actualmente redondeamos cada renglón a centavos.
Para empatar con los cotizadores bancarios hay que conservar precisión completa en la
cadena y redondear solo en la presentación. Es un cambio acotado pero toca la
construcción de la tabla.

---

## 4. Resumen de convenciones confirmadas por reproducción

| Institución | Interés del periodo | Base de amortización | Estado |
|---|---|---|---|
| HSBC | `saldo × tasa / 12` | misma | Verificado |
| Santander | `saldo × tasa × 30.4166 / 360` | `(tasa/360)×(365/12)` | Verificado |
| Banregio | `saldo × tasa × días_reales / 360` | `tasa / 12` | Verificado |
| Scotiabank | `saldo × tasa × días / 360` (por fórmula) | — | Sin reproducir |
| Banamex | `saldo × tasa / 12` (por fórmula) | factor por millar redondeado hacia arriba | Sin reproducir |

---

## 5. Correcciones al motor derivadas de esta etapa

| # | Corrección | Origen |
|---|---|---|
| 1 | Eliminar el redondeo a centavos en la cadena; redondear solo al presentar | 3.4 |
| 2 | Convención de días como atributo del producto, con las tres variantes | 2 |
| 3 | Permitir base de amortización distinta de la base de cobro de interés | 3.3 |
| 4 | Excluir IVA del flujo del CAT por concepto, no de forma uniforme | 3.2 |
| 5 | Seguro como componente fijo más tasa sobre saldo, no solo tasa | 3.3 |

Las cinco son acotadas. Ninguna obliga a rediseñar el motor.

---

## 6. Pendientes

1. **Solicitar cotizadores de Scotiabank y Banamex con un escenario capturado.**
   Sin eso no podemos acreditar reproducción de dos de las ocho instituciones, y
   Banamex es relevante porque es el único que redondea el factor por millar hacia
   arriba.

2. **Definir el tratamiento correcto de la comisión por apertura en el CAT.**
   HSBC y Santander difieren. Es la única discrepancia metodológica detectada entre
   instituciones.

3. **Validar los productos no estándar**: pago creciente (hoja `TablAmoPagosCrec` de
   Banregio tiene datos capturados), ministraciones y cofinanciamiento. Esta etapa
   cubrió únicamente pagos fijos.

---

## Anexo — Evidencia de las tres validaciones

```
SANTANDER — $1,770,000 @ 9.50 %, 300 meses
  interés      300/300 renglones al centavo
  capital      300/300 renglones al centavo
  s.vida       300/300 renglones al centavo
  pago total   300/300 renglones al centavo
  saldo        300/300 renglones al centavo
  diferencia máxima $0.002414   ·   saldo final $0.000000
  CAT reconstruido 11.84725849 %  ·  archivo 11.84726060 %  ·  dif 0.0002 pb

HSBC — $2,082,500 @ 11.75 %, 240 meses
  capital      240/240 renglones al centavo
  interés      240/240 renglones al centavo
  s.vida       240/240 renglones al centavo
  pago total   240/240 renglones al centavo
  saldo        240/240 renglones al centavo
  diferencia máxima $0.000000   ·   saldo final $0.000000
  CAT reconstruido 13.9839283719 %  ·  archivo 13.9839283719 %  ·  dif 0.00000000 pb

BANREGIO — $1,215,000 @ 10.20 %, 120 meses
  interés        120/120 renglones al centavo
  amortización   120/120 renglones al centavo
  seguros        120/120 renglones al centavo
  pago           120/120 renglones al centavo
  diferencia máxima $0.000000   ·   saldo final $0.00
```
