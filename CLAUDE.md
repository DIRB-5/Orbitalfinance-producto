# CLAUDE.md

Contexto del proyecto. Léelo completo antes de tocar código.

## Qué es esto

Plataforma SaaS mexicana para comparación de créditos hipotecarios. La usan
asesores de grupos de brokers inmobiliarios y de crédito para comparar
opciones de financiamiento entre instituciones y generar una presentación con
marca para su cliente final.

Jerarquía del dominio: **organización → asesor → cliente final**.
Los registros de cliente pertenecen a la **organización**, no al asesor, con el
asesor como responsable asignado. Esa regla es deliberada: quien paga la
suscripción es la brokerage, y el asesor rota.

## Estructura

```
/backend
  motor_hipotecario/ Núcleo de cálculo. Puro, sin dependencias externas.
    catalogo.py      Catálogo real por destino (adquisición, sustitución, terreno,
                     liquidez) de 8 instituciones.
    referencias.py   Escenarios de TIIE (conservador/base/estrés) con su fuente.
  app/               FastAPI: /api/catalogo, /api/comparar. Capa delgada.
  tests/             314 pruebas. No deben bajar de ahí.
    fixtures/catalogo_prueba.py   Catálogo ficticio, solo para pruebas.
/api/index.py        Entrada de Vercel. ÚNICO .py en /api: Vercel convierte
                     cada .py de esa carpeta en una función.
/index.html, *.dc.html, src/data/   Prototipo (Claude Design). Lee la API;
                     src/data/datos.js es su única fuente de datos.
vercel.json, requirements.txt, .python-version, .vercelignore   Despliegue.
```

Pruebas: `cd backend && python -m pytest tests/ -q` (las de la API necesitan
`fastapi` y `httpx`; sin ellas se omiten).

---

## Reglas que no se negocian

Estas existen porque cada una costó una decisión razonada. Si crees que una
está mal, dilo antes de cambiarla; no la cambies en silencio.

### 1. `Decimal` en todo el motor. Nunca `float`.

En una tabla de amortización de 240 renglones los errores de punto flotante se
acumulan y el saldo final no cierra en cero. Hay una prueba dedicada a esto
(`test_saldo_final_es_exactamente_cero`).

Si ves código financiero con `float`, es un bug, no una simplificación.

### 2. El motor no tiene dependencias externas

`motor_hipotecario/` usa solo biblioteca estándar. Es intencional: es la pieza
auditable del sistema y quiero poder leerla completa sin seguir cadenas de
paquetes. No metas numpy, pandas ni bibliotecas financieras ahí.

FastAPI, Playwright y todo lo demás viven fuera del motor.

### 3. Los productos bancarios se versionan, no se editan

Cada `ProductoHipotecario` tiene `vigente_desde` / `vigente_hasta`.
**Actualizar condiciones = cerrar la vigencia del producto anterior y crear uno
nuevo.** Nunca un `UPDATE` sobre los campos de tasa, comisión o seguros.

Razón: si un asesor entregó una propuesta en marzo y el cliente reclama en
agosto, tenemos que poder reproducir ese cálculo exacto. Cada comparación
guarda un `Snapshot` con **copia** de los parámetros, no una referencia viva al
catálogo.

### 4. El CAT siempre se rotula como estimado

Nuestro cálculo sigue la metodología general de Banxico, pero cada institución
publica su CAT con supuestos propios. Hasta que se valide producto por producto
contra el CAT publicado, **cualquier superficie que muestre CAT debe incluir la
palabra "estimado"**: UI, PDF, API, exportaciones.

Quitar esa etiqueta es un problema regulatorio y de credibilidad, no un detalle
de copy.

### 5. Se permiten nombres de bancos reales

Los datos de prueba y los fixtures pueden usar nombres de instituciones reales
(p. ej. `tests/fixtures/cotizadores_reales.py`). El catálogo de prueba
(`tests/fixtures/catalogo_prueba.py`) conserva nombres ficticios porque sus
números son inventados.

**Todo producto del catálogo real (`motor_hipotecario/catalogo.py`) debe tener
`fuente` y una prueba que lo reproduzca contra su cotizador
(`tests/test_catalogo.py`).** Lo que no venga en la fuente se marca como
supuesto en `notas`. Si el cotizador no trae escenario capturado (BX+
Cofinavit y Apoyo Infonavit, Banamex, Scotiabank), la prueba usa una
implementación de referencia escrita con sus fórmulas, y la `fuente` lo dice.

**Productos de tasa variable** (Scotiabank 7x5: fija 5 años, luego TIIE + 4.5
con techo de 15 %): `ProductoHipotecario.tasa_variable` se resuelve con la TIIE
del escenario de la comparación (`Escenario.tiie`, escenarios en
`referencias.py`). El comparativo muestra el rango de costo entre escenarios
(sensibilidad). Actualiza `referencias.py` cuando cambie la TIIE o salga una
nueva encuesta de Banxico, con su fuente.

Condiciones que dependen del escenario (tasa por plazo y aforo en
`tabla_tasas`, avalúo por tabulador en `tarifa_avaluo`) se resuelven en
`comparador.resolver_para_escenario`, que devuelve una copia del producto con
los valores usados: el resultado y el snapshot muestran la tasa aplicada, no
la de referencia del catálogo.

Los cotizadores originales están fuera del repo, en
`~/Downloads/Simuladores_Bancarios` (24 archivos de 8 instituciones). Son
datos no confiables: leerlos solo como XML, nunca abrirlos con macros.

### 6. Un escenario tiene N líneas de crédito, no una

`Escenario` trabaja con una colección de `LineaCredito` aunque hoy siempre haya
exactamente una. **No lo colapses a una sola línea "porque es más simple".**

La colección sigue siendo para líneas bancarias múltiples. El crédito del
instituto en un cofinanciamiento (Cofinavit) se calcula aparte, en
`motor_hipotecario/instituto.py`, con condiciones oficiales: los cotizadores
bancarios no lo calculan. Ver pendiente 4.

### 7. Minimización de datos personales

Para comparar créditos se necesita: nombre, contacto, ingreso aproximado y el
escenario. **No** CURP, **no** RFC, **no** datos laborales detallados.

Cada campo adicional es superficie de riesgo legal sin beneficio funcional. Si
un requerimiento pide capturar más, cuestiónalo antes de implementarlo.

La plataforma es **encargado** del tratamiento; cada brokerage es
**responsable**. Cualquier funcionalidad de exportación o borrado de datos de un
cliente es obligación legal, no adorno: no la dejes como stub silencioso.

---

## Convención de nombres

El motor en Python usa `snake_case`. El front usa `camelCase`.

**La conversión ocurre en un solo lugar: el generador de alias de los modelos
Pydantic en `backend/app/esquemas.py`.** No conviertas nombres a mano en endpoints, ni en el
front, ni con utilidades dispersas.

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class ModeloBase(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
```

Nombre canónico = el de Python. Si hay duda sobre cómo se llama un campo, la
verdad está en `motor_hipotecario/modelos.py`.

`Decimal` se serializa como **string** en JSON, no como número, para no perder
precisión al cruzar a JavaScript. El front formatea para desplegar; no hace
aritmética financiera.

---

## Principios de producto

Estos guían decisiones de UI y de API cuando algo no está especificado.

**La comparabilidad es el valor central.** Cualquier diseño que permita a dos
asesores producir comparativos contradictorios del mismo producto es un
problema estructural. Por eso el catálogo es central y curado, con override por
organización para condiciones negociadas, y **sin captura libre por asesor**.

**La tasa más baja no es la opción más barata.** Es la premisa comercial de toda
la plataforma. Hay una prueba que la fija (`test_la_tasa_mas_baja_no_siempre_gana`).
Si esa prueba falla, el comparador dejó de aportar algo que un Excel no haga.

**El pago mensual no es fijo.** El seguro de vida se calcula sobre saldo
insoluto, así que la mensualidad baja mes a mes. Nunca presentes "la
mensualidad" como un número único sin mostrar el rango.

**La mensualidad que se presenta es el pago regular** (`pago_regular_inicial`
/ `pago_regular_final`): sin el primer periodo irregular (Banorte, Afirme) ni
el pago de cierre (Banamex). El primer pago real se muestra aparte, con sus
días. La capacidad de pago se mide con el pago regular.

**El orden por defecto es costo total**, no tasa ni mensualidad.

**Cada producto tiene un destino** (`Destino`: adquisición, sustitución,
liquidez, terreno) y el comparador solo compara productos del destino del
escenario. En sustitución el escenario trae `CreditoActual` y cada opción
calcula ahorro mensual, costo de cambiarse, punto de equilibrio y ahorro neto
contra quedarse. Solo adquisición y terreno llevan enganche en el desembolso
inicial: en sustitución y liquidez el inmueble ya es del cliente. Algunos
productos dependen del banco del crédito actual (`CreditoActual.institucion`):
`solo_credito_actual_propio` (Santander Mejora de Condiciones, "tu hipoteca
actual con Santander") y `excluye_credito_actual_propio` (Santander
Sustitución, "de otro banco"); sin institución capturada, el primero no es
elegible y el segundo sí.

**En liquidez el banco cobra IVA sobre los intereses** (no hay exención por
casa habitación). `iva_sobre_intereses` lo suma al pago; con
`iva_intereses_inflacion` el IVA se calcula sobre el interés real (Banregio).
Si va o no al CAT lo decide `iva_intereses_en_cat`, por producto, porque cada
cotizador lo trata distinto. Ningún producto de liquidez tiene escenario
capturado: están validados por fórmula, no al centavo.

**Gastos notariales financiados.** `Escenario.financiar_gastos_notariales`
pide a todos los bancos el mismo monto (`gastos_notariales`); cada producto
con `financiamiento_gastos` suma al crédito el mínimo entre los gastos, su
tope (Banamex 10 % del valor o 5 % del saldo, Scotiabank 6 % del saldo, BX+
Mejora sin tope) y lo que cabe en su aforo máximo. Lo demás se paga de
contado. Lo financiado genera intereses y seguro sobre saldo; el CAT parte del
crédito total (no resta la notaría, como los cotizadores) y el costo total no
lo cuenta dos veces. Scotiabank cobra la apertura y elige tasa sin los gastos
(`apertura_y_aforo_sobre_total=False`). Ningún cotizador trae un escenario con
gastos financiados: validado contra sus fórmulas. Dos variantes más:
- Santander Sustitución (`linea_separada`): los gastos van en un segundo
  crédito con la misma tasa, plazo y pago, solo vida e IVA sobre intereses,
  y CAT propio (`tabla_gastos`, `cat_gastos_estimado`); todo o nada si el 7 %
  no cabe en el aforo (`excede_aforo_cancela`). La mensualidad, la capacidad
  de pago, el costo total y el ahorro de sustitución suman ambas líneas; el
  CAT principal no incluye la línea de gastos.
- Afirme Tu Casa 2 (`incluye_apertura_y_avaluo`, `acepta_garantia_adicional`):
  el aforo de 80 % se mide sobre la vivienda más un inmueble adicional en
  garantía (`Escenario.valor_garantia_adicional`, solo el valor) y el crédito
  cubre notariales, avalúos y la propia apertura: total = (base + notariales +
  avalúo) / (1 − apertura).

**Las opciones no elegibles se muestran con su motivo**, no se ocultan. El
asesor necesita poder decirle al cliente qué enganche adicional le abriría esa
opción.

---

## La presentación

Arquitectura: **páginas fijas de plantilla + páginas generadas por el motor**.

- Fijas (editables por organización): sobre nosotros, siguientes pasos,
  documentación requerida, cómo subir documentos, FAQs, contacto.
- Generadas: portada, resumen del escenario, comparativo, detalle por
  institución, aviso legal.
- Automática: índice.

Formato: **16:9 horizontal**, 1280×720. Render HTML + CSS con Playwright.

La página de **aviso legal es obligatoria y no desactivable**. Debe incluir
fecha de generación, fecha de vigencia de las condiciones, que la comparación
es informativa y no una oferta, que el CAT es estimado, y que la tasa final
depende del análisis de riesgo de cada institución.

**PPTX es exportación secundaria, no el entregable oficial.** Convierte los
números en texto editable a mano; un asesor que "ajusta" una mensualidad en
PowerPoint produce un documento con la marca de la organización y datos falsos.
Si se implementa, va con advertencia explícita.

---

## Pendientes conocidos del motor

Estos son productos reales del mercado mexicano que el motor **todavía no
modela**. Si te topas con ellos, no improvises: son extensiones diseñadas, no
parches.

1. **Tasa escalonada por periodo — HECHO, VALIDADO POR FÓRMULA contra
   Scotiabank Pagos Oportunos (sin escenario capturado).** `tasas_escalonadas`
   en el producto: ((mes desde el que aplica, tasa anual), ...); antes del primer
   escalón aplica `tasa_anual`. Dos mecánicas, por producto:
   - pago fijo calculado a la tasa inicial (`recalcular_pago_al_cambiar_tasa`
     en False): si la tasa baja, el crédito se liquida antes. La tabla termina
     en el mes en que el saldo llega a cero y `plazo_efectivo_meses` lo expone.
     No admite tasas que suben.
   - pago recalculado al cambiar la tasa, sobre saldo y plazo restante (True),
     como Banamex `TablaCTH!S128`.
   No se combina con mensualidad creciente. Sí con `crecimiento_pago_anual`
   (pago al millar que sube cada aniversario sin recalcularse, Scotiabank
   Valora), con pago fijo. Los dos esquemas de Scotiabank suponen pagos
   puntuales, como sus cotizadores: con atrasos la tasa no baja. Ojo al comparar: con plazos
   efectivos distintos la suma de pagos favorece al crédito más corto aunque
   pague más al mes (riesgo 8.2 del análisis); el prototipo ya avisa cuando los
   plazos difieren.

2. **Mensualidad creciente — HECHO Y VALIDADO contra Banregio.**
   `crecimiento_pago_mensual` en el producto: ((mes desde, crecimiento
   mensual), ...). El pago base (capital + interés) crece cada mes; al inicio
   de cada fase se recalcula sobre el saldo para liquidar en el plazo
   restante. Seguros y comisión van fuera y no crecen. Banregio
   (`TablAmoPagosCrec`): ((1, 1/0.9989 − 1), (73, 0.0017)), reproducido a
   1e-8 en los renglones de control y su CAT a 1e-7
   (`test_banregio_creciente_*`). Ojo: ese archivo fija el plazo en 240 meses
   y la fase en el mes 73 sin importar el plazo capturado.
   Si el pago inicial no cubre el interés (amortización negativa), el producto
   es **no elegible** para ese escenario, con el motivo.

3. **Comisión mensual fija — HECHO.** `comision_mensual` en el producto; entra
   al pago, al costo total y al CAT (a valor bruto mientras se resuelve el IVA).
   También se agregaron `comision_apertura_monto` y `seguro_danos_monto_mensual`
   para conceptos que el cotizador da como monto fijo.

4. **Cofinanciamiento INFONAVIT / FOVISSSTE — HECHO como en los cotizadores,
   SIN VALIDAR con números.** `Escenario.cofinanciamiento` (instituto, salario,
   crédito del instituto, subcuenta): el crédito y la subcuenta reducen el
   monto bancario. `ProductoHipotecario.regla_aportaciones`: cómo abona el
   banco las aportaciones patronales (% del salario, tope, incremento anual,
   cada 2 meses desde el mes 4, omitir o limitar si exceden el saldo). Los
   abonos acortan el plazo sin cambiar el pago del cliente.
   - El CAT se calcula sin aportaciones, como en los tres cotizadores.
   - El costo total SÍ las incluye: son dinero de la subcuenta del trabajador.
     Decisión de producto pendiente de confirmar con riesgo.
   - Un producto sin regla, o con regla de otro instituto, se evalúa como
     **alternativa sin cofinanciamiento**: mismo enganche propio, el banco
     financia también lo que cubrirían el crédito del instituto y la subcuenta,
     sin aportaciones (`alternativa_sin_cofinanciamiento`). Los productos
     exclusivos (`requiere_cofinanciamiento`) no tienen alternativa.
   - **Crédito del instituto (INFONAVIT Cofinavit)**, `instituto.py`: 10.45 %
     fijo en pesos, sin comisiones, máximo $1,159,022.80 (325 UMA 2026), según
     Condiciones Generales INFONAVIT v1.1 (DOF 05/12/2025). SUPUESTO: pago fijo
     tipo anualidad a tasa/12 sobre el plazo del escenario (el instituto no
     publica su fórmula; coincide con el bloque informativo de Banorte). Por
     Ley INFONAVIT art. 43 Bis, las aportaciones pagan PRIMERO ese crédito y
     después el bancario. El costo total suma ambos pagos y las aportaciones;
     la capacidad de pago se mide con ambos pagos.
   - FOVISSSTE no tiene crédito propio en cofinanciamiento con banca (programa
     2026): un escenario FOVISSSTE con crédito del instituto es inválido.
   - La subcuenta usada como enganche no cuenta como costo en ninguna ruta.
     Criterio pendiente con riesgo.
   - El salario es "ingreso aproximado" (regla 7): no se pide NSS ni CURP.
   - En el prototipo, la sección "Cofinanciamiento" del escenario de
     adquisición: el "Monto del crédito" es el bancario y el enganche del
     cliente ya descuenta crédito del instituto y subcuenta.
   Ningún cotizador trae un escenario con aportaciones capturadas: la mecánica
   sale de las fórmulas. No se modelan el tope de aforo combinado (BX+: banco +
   instituto ≤ 90 %) ni el modo "Mensualidad" de BX+ (recalcular el pago).

**Gate obligatorio antes de cualquier release a cliente final:** validar el CAT
calculado contra el CAT publicado de al menos tres o cuatro instituciones
reales, y convertir cada caso en una prueba de regresión. **Parcialmente
cumplido**: hay tres instituciones reproducidas al centavo (ver siguiente
sección).

---

## Correcciones derivadas de cotizadores bancarios reales

Se analizaron 24 cotizadores en Excel de 8 instituciones y se reprodujeron tres
modelos al centavo contra sus propias tablas. Evidencia en
`docs/validacion_modelos.md`; valores de referencia en
`backend/tests/fixtures/cotizadores_reales.py`.

Las cinco reglas siguientes salieron de ahí. **No son opiniones de diseño: son
cómo calculan los bancos.**

### 1. No redondear en la cadena de cálculo — HECHO

Ningún banco redondea valores intermedios. Mantienen precisión completa en toda
la tabla y redondean **solo al presentar**.

`construir_tabla` ya no redondea: la tabla sale con precisión completa y
`redondear()` queda solo para la capa de presentación (API, PDF), que **debe**
aplicarlo al desplegar. `test_hsbc_renglones` ya valida contra el motor.

### 2. La convención de conteo de días es atributo del producto — HECHO

Existen cuatro en el mercado y producen resultados distintos con la misma tasa
nominal:

```
tasa / 12                        HSBC, Banamex, BX
tasa * 30.4166 / 360             Santander
tasa * 30.4 / 360                Banorte
tasa * dias_reales_del_mes / 360 Scotiabank, Banregio, Afirme
```

Una tasa de 10.85 % en base 360 cuesta lo mismo que 11.00 % en base `/12`:
~$24,563 más por cada millón a 20 años. **Comparar tasas nominales sin
normalizar la base ordena mal el comparativo.**

Al presentar, mostrar la tasa nominal del contrato y, por separado, una tasa
normalizada equivalente usada solo para ordenar.

Implementado como `ConvencionDias` con dos campos en `ProductoHipotecario`:
`convencion_interes` y `convencion_pago` (None = la misma). Santander usa una
distinta para cada cosa: `tasa*30.4166/360` para el interés y
`(tasa/360)*(365/12)` para el pago. `tasa_normalizada()` da la tasa para
ordenar. `test_santander_renglones` ya valida contra el motor.

Días reales / 360 (`DIAS_REALES_360`) solo aplica al interés cobrado y
necesita `fecha_primer_pago`. Si el escenario no la trae, el comparador usa el
día 1 del mes siguiente a la comparación (reproducible desde el snapshot).

### 3. La base de amortización puede diferir de la base de cobro

Banregio amortiza capital con `tasa/12` y cobra interés con días reales. El
resultado es que su producto de "pagos fijos" **no tiene pago fijo**: varía
$685 entre febrero y un mes de 31 días.

**HECHO.** `convencion_amortizacion` en el producto (None = la de cobro) y
`seguros_en_pago_fijo` para productos cuyo pago fijo incluye los seguros: el
pago es la anualidad con la tasa del seguro de vida sumada a la del periodo,
más el seguro de daños. `test_banregio_renglones` ya valida contra el motor.

### 4. El IVA se excluye del flujo del CAT por concepto, no de forma uniforme — HECHO como parámetro

| Concepto | En el flujo del CAT |
|---|---|
| Capital e interés | completo |
| Seguro de vida | completo (exento de IVA) |
| Seguro de daños | ÷ 1.16 |
| Comisión mensual | ÷ 1.16 |
| Avalúo | ÷ 1.16 |
| Comisión por apertura | **sin resolver** |

La tabla sale de HSBC y Santander la sigue igual: los montos de su hoja CAT
ya vienen sin IVA (daños 441 / 1.16, comisión 406 / 1.16, y los 7,000 / 1.16
son el avalúo, no apertura; su apertura es 0). Se aclaró al analizar sus
hojas Adm, Cal y Captura; `santander-2026-10` cargaba los montos sin IVA y
el avalúo como apertura, así que se cerró y lo sustituye
`santander-adquisicion-2025-12` (`test_santander_adquisicion_*`). Ningún
cotizador analizado resuelve la comisión por apertura.

**El tratamiento del IVA está pendiente de resolución con riesgo, para todos los
conceptos salvo capital, interés y seguro de vida.** Hasta entonces, no lo
codifiques en duro: déjalo como parámetro del producto, por concepto.

**Implementado así:** `cat_netos_de_iva` en el producto, un conjunto de
`ConceptoIVA` (apertura, avalúo, daños, comisión mensual) que entran al CAT
÷ 1.16. Vacío = todo con IVA, que sobreestima el CAT. Capital, interés y seguro
de vida entran siempre completos. Solo afecta al CAT, nunca al costo total.
HSBC y Santander en el catálogo usan el tratamiento de su propio cotizador, y
`test_hsbc_cat_desde_motor` / `test_santander_adquisicion_cobra_lo_que_cobra_el_cotizador`
lo validan.

Consecuencia a vigilar: dos productos del mismo comparativo pueden tener su CAT
calculado con criterios de IVA distintos. Es lo que publica cada banco, pero no
es una base homogénea. Cuando riesgo decida, se aplica un solo criterio a todo
el catálogo cambiando el parámetro, no el motor.

### 5. El seguro puede ser componente fijo más tasa sobre saldo

No solo una tasa. Banregio: `$81.52 + 0.00083 × saldo`. Además, Banamex aplica
extraprima por edad, condición médica y ocupación, así que la prima es función
del producto **y del solicitante**, no solo del producto.

**Parcial.** El componente fijo más tasa se representa con
`seguro_danos_monto_mensual` (fijo) y `seguro_vida_mensual` (sobre saldo); el
cotizador de Banregio solo da la suma, así que la división entre vida y daños
es un supuesto que no cambia ningún resultado. La extraprima por perfil del
solicitante sigue pendiente.

### Las pruebas de `test_cotizadores_reales.py` son el contrato

Reproducen HSBC (240 renglones), Santander (300) y Banregio (120) contra valores
reales. Hoy validan implementaciones de referencia dentro del propio archivo de
prueba.

**Conforme implementes cada corrección, sustituye la función `_construir_*`
correspondiente por una llamada al motor.** Ese es el objetivo. No borres las
funciones de referencia: sirven de contraste si el motor empieza a divergir.

Si una de estas pruebas falla después de un cambio tuyo, el cambio rompió la
compatibilidad con una institución real. El fixture no se ajusta para que pase.

---

## Cómo trabajar aquí

- Corre `pytest` antes y después de tocar el motor. 314 pruebas, no deben bajar.
- Cambios al motor requieren prueba nueva que falle antes y pase después.
- No refactorices el motor "para limpiarlo" sin motivo funcional. Está escrito
  para leerse, no para ser corto.
- Si una regla de este archivo te estorba para resolver algo, dilo en la
  conversación en vez de rodearla.
