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
/api                 FastAPI. Aquí vive el motor.
  motor_hipotecario/ Núcleo de cálculo. Puro, sin dependencias externas.
  tests/             55 pruebas. No deben bajar de ahí.
/web                 Front-end. Origen: prototipo de Claude Design.
/api/pdf             Render de presentaciones con Playwright.
```

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
(p. ej. `tests/fixtures/cotizadores_reales.py`). `catalogo_demo.py` conserva
por ahora sus nombres ficticios ("Institución Demo A", etc.).

### 6. Un escenario tiene N líneas de crédito, no una

`Escenario` trabaja con una colección de `LineaCredito` aunque hoy siempre haya
exactamente una. **No lo colapses a una sola línea "porque es más simple".**

Cofinanciamiento INFONAVIT / FOVISSSTE está diferido, pero es el caso típico del
mercado, no el excepcional. La colección existe para que agregarlo sea sumar un
elemento y no reescribir el motor, las tablas y el PDF.

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
Pydantic en `/api`.** No conviertas nombres a mano en endpoints, ni en el
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

**El orden por defecto es costo total**, no tasa ni mensualidad.

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

1. **Tasa escalonada por periodo.** Hay productos con tasa decreciente por año
   (p. ej. 11.85 % los primeros tres años bajando a 10.85 % desde el séptimo)
   manteniendo pago fijo, lo que amortiza más rápido y reduce el plazo efectivo.
   Requiere sustituir `tasa_anual` por un calendario de tasas y derivar
   `plazo_efectivo_meses`.

2. **Mensualidad creciente.** Productos que incrementan el pago un porcentaje
   anual fijo (p. ej. 2.6 %). Requiere un factor de crecimiento aplicado al pago.

3. **Comisión mensual fija.** Cargo recurrente que no es interés ni seguro.
   Entra al CAT y al costo total. Es un campo más en el flujo mensual.

4. **Cofinanciamiento INFONAVIT / FOVISSSTE.** Segunda línea de crédito con
   reglas propias. El modelo ya lo soporta estructuralmente.

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
`api/tests/fixtures/cotizadores_reales.py`.

Las cinco reglas siguientes salieron de ahí. **No son opiniones de diseño: son
cómo calculan los bancos.**

### 1. No redondear en la cadena de cálculo — HECHO

Ningún banco redondea valores intermedios. Mantienen precisión completa en toda
la tabla y redondean **solo al presentar**.

`construir_tabla` ya no redondea: la tabla sale con precisión completa y
`redondear()` queda solo para la capa de presentación (API, PDF), que **debe**
aplicarlo al desplegar. `test_hsbc_renglones` ya valida contra el motor.

### 2. La convención de conteo de días es atributo del producto — HECHO, salvo días reales

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

**Falta días reales / 360**: necesita fechas de pago y entra con la corrección 3.

### 3. La base de amortización puede diferir de la base de cobro

Banregio amortiza capital con `tasa/12` y cobra interés con días reales. El
resultado es que su producto de "pagos fijos" **no tiene pago fijo**: varía
$685 entre febrero y un mes de 31 días.

El modelo necesita dos campos separados, no uno.

### 4. El IVA se excluye del flujo del CAT por concepto, no de forma uniforme

| Concepto | En el flujo del CAT |
|---|---|
| Capital e interés | completo |
| Seguro de vida | completo (exento de IVA) |
| Seguro de daños | ÷ 1.16 |
| Comisión mensual | ÷ 1.16 |
| Avalúo | ÷ 1.16 |
| Comisión por apertura | **sin resolver** |

Esta tabla sale **solo de HSBC**. Santander no la sigue: su CAT únicamente se
reproduce con el seguro de daños y la comisión mensual **completos**, y la
comisión por apertura ÷ 1.16 (`test_santander_cat`). No se sabe si los montos
de su archivo ya vienen netos de IVA o si Santander los mete con IVA.

**El tratamiento del IVA está pendiente de resolución con riesgo, para todos los
conceptos salvo capital, interés y seguro de vida.** Hasta entonces, no lo
codifiques en duro: déjalo como parámetro del producto, por concepto.

El motor hoy mete todo a valor bruto, lo que sobreestima el CAT.

### 5. El seguro puede ser componente fijo más tasa sobre saldo

No solo una tasa. Banregio: `$81.52 + 0.00083 × saldo`. Además, Banamex aplica
extraprima por edad, condición médica y ocupación, así que la prima es función
del producto **y del solicitante**, no solo del producto.

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

- Corre `pytest` antes y después de tocar el motor. 55 pruebas, no deben bajar.
- Cambios al motor requieren prueba nueva que falle antes y pase después.
- No refactorices el motor "para limpiarlo" sin motivo funcional. Está escrito
  para leerse, no para ser corto.
- Si una regla de este archivo te estorba para resolver algo, dilo en la
  conversación en vez de rodearla.
