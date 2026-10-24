// ---------------------------------------------------------------------------
// Fuente única de datos del prototipo.
//
// El catálogo y todos los cálculos vienen del motor en Python a través de la
// API (/api/catalogo, /api/comparar). El front formatea para desplegar; no
// hace aritmética financiera (CLAUDE.md).
//
// Los nombres de campo son los de la API (camelCase del motor).
// ---------------------------------------------------------------------------

export const HOY = new Date().toISOString().slice(0, 10);

// --- Organización ----------------------------------------------------------
// Vacía: se captura para cada organización que use la plataforma.
export const organizacion = {
  nombre: "Mi organización",
  logoTexto: "ORG",
  colorAcento: "#1B3A5C",
  modoMarcaDefault: "corporativa_asesor",
  retencionMeses: 24,
  asesores: [
    { id: "u-1", nombre: "Administrador", correo: "", rol: "Administrador", cedula: "", telefono: "" },
    { id: "u-2", nombre: "Asesor", correo: "", rol: "Asesor", cedula: "", telefono: "" },
  ],
};

export const asesorActual = organizacion.asesores[0];

// --- Taxonomía de productos ------------------------------------------------
// El motor hoy modela adquisición. Los demás subtipos quedan como próximos.
export const FAMILIAS = [
  {
    id: "hipotecario",
    nombre: "Hipotecario",
    descripcion: "Crédito con garantía inmobiliaria",
    subtipos: [
      { id: "adquisicion", nombre: "Adquisición", disponible: true, porDefecto: true },
      { id: "sustitucion", nombre: "Sustitución", disponible: false },
      { id: "liquidez", nombre: "Liquidez", disponible: false },
      { id: "terreno", nombre: "Adquisición de terreno", disponible: false },
      { id: "construccion", nombre: "Construcción", disponible: false },
      { id: "terreno-const", nombre: "Terreno + construcción", disponible: false },
    ],
  },
  { id: "pyme", nombre: "PyME", descripcion: "Crédito empresarial", subtipos: [] },
];

export function familiaDe(subtipo) {
  return subtipo === "pyme" ? "pyme" : "hipotecario";
}

// --- Escenarios de tasa de referencia --------------------------------------
export const ESCENARIOS_REFERENCIA = [
  { id: "conservador", nombre: "Conservador", TIIE_28: 0.0875 },
  { id: "base", nombre: "Base", TIIE_28: 0.1075, porDefecto: true },
  { id: "estres", nombre: "Estrés", TIIE_28: 0.1275 },
];

// Tasa anual resuelta de un producto para un escenario de referencia dado.
// Los productos fijos ignoran el escenario.
export function tasaResuelta(producto, escenarioRefId) {
  const t = producto.tasa || {};
  if (t.tipo !== "variable") return t.valor;
  const ref = ESCENARIOS_REFERENCIA.find((e) => e.id === (escenarioRefId || "base")) || ESCENARIOS_REFERENCIA[1];
  let tasa = (ref[t.referencia] || 0) + (t.spread || 0);
  if (t.piso !== null && t.piso !== undefined) tasa = Math.max(tasa, t.piso);
  if (t.techo !== null && t.techo !== undefined) tasa = Math.min(tasa, t.techo);
  return tasa;
}

export function etiquetaTasa(producto, escenarioRefId) {
  const t = producto.tasa || {};
  const r = tasaResuelta(producto, escenarioRefId);
  const p = (x) => (x * 100).toFixed(2) + "\u00A0%";
  if (t.tipo !== "variable") return p(r);
  return (t.referencia || "").replace("_", " ") + " + " + (t.spread * 100).toFixed(2) + " = " + p(r);
}

// --- Plantilla de la organización: páginas fijas del deck -------------------
// "Sobre nosotros" y "Contacto" se llenan por organización.
export const plantillaOrganizacion = {
  organizacionId: "",
  nombre: organizacion.nombre,
  colorAcento: "#1B3A5C",
  logoUrl: null,
  paginasFijas: [
    {
      id: "sobre-nosotros",
      titulo: "Sobre nosotros",
      activa: true,
      bloques: [],
    },
    {
      id: "siguientes-pasos",
      titulo: "Siguientes pasos",
      activa: true,
      bloques: [
        { tipo: "pasos", items: [
          { titulo: "Elegir la opción", texto: "Revisamos juntos el comparativo y decides con qué institución solicitar." },
          { titulo: "Integrar el expediente", texto: "Reúnes la documentación de la siguiente página. Nosotros la revisamos antes de presentarla." },
          { titulo: "Solicitud y análisis", texto: "La institución analiza el expediente y confirma monto, tasa y plazo. De 5 a 15 días hábiles." },
          { titulo: "Avalúo del inmueble", texto: "La institución asigna al valuador. El resultado puede ajustar el monto autorizado." },
          { titulo: "Firma en notaría", texto: "Se firma la escritura y el crédito. Aquí se cubre el desembolso inicial." },
        ] },
      ],
    },
    {
      id: "documentacion-requerida",
      titulo: "Documentación requerida",
      activa: true,
      bloques: [
        { tipo: "lista", titulo: "Identidad y domicilio", items: ["Identificación oficial vigente por ambos lados", "CURP y RFC", "Comprobante de domicilio no mayor a tres meses", "Acta de matrimonio, si aplica"] },
        { tipo: "lista", titulo: "Ingresos", items: ["Empleado: tres últimos recibos de nómina y estados de cuenta de tres meses", "Independiente: declaración anual y estados de cuenta de doce meses", "Constancia laboral con antigüedad, puesto e ingreso"] },
        { tipo: "lista", titulo: "Del inmueble", items: ["Escritura o título de propiedad del vendedor", "Predial y agua al corriente", "Datos de contacto del vendedor o desarrollador"] },
      ],
    },
    {
      id: "como-subir-documentos",
      titulo: "Cómo subir tus documentos",
      activa: true,
      bloques: [
        { tipo: "pasos", items: [
          { titulo: "Recibes un enlace", texto: "Te enviamos por correo un enlace personal al expediente. No hay que instalar nada." },
          { titulo: "Subes cada documento", texto: "Un archivo por concepto, en PDF o foto legible. Los estados de cuenta completos, sin recortes." },
          { titulo: "Revisamos y te avisamos", texto: "Marcamos lo que falta o no es legible. Solo presentamos el expediente cuando está completo." },
        ] },
        { tipo: "parrafo", texto: "Tus documentos se conservan durante el proceso y hasta 24 meses después, conforme a nuestra política de retención. Puedes solicitar su eliminación en cualquier momento." },
      ],
    },
    {
      id: "faqs",
      titulo: "Preguntas frecuentes",
      activa: true,
      bloques: [
        { tipo: "faq", items: [
          { p: "¿Qué es el CAT?", r: "El Costo Anual Total. Expresa en un solo porcentaje el costo del crédito incluyendo tasa, comisiones y seguros. Sirve para comparar entre instituciones: la tasa sola no alcanza. El CAT de esta propuesta es un cálculo propio conforme a la metodología de Banxico y está pendiente de validación contra el CAT publicado por cada institución." },
          { p: "¿Por qué mi mensualidad baja cada mes?", r: "Porque el seguro de vida se calcula sobre el saldo que aún debes. Conforme el saldo baja, esa parte del pago baja también. El pago al crédito se mantiene igual." },
          { p: "¿Qué significa mensualidad fija, decreciente o creciente?", r: "Fija: pagas lo mismo los veinte años. Decreciente: el pago baja con el tiempo, normalmente por el seguro de vida. Creciente: el pago sube un porcentaje cada año, lo que hace la mensualidad inicial más baja pero el costo total mayor." },
          { p: "¿Qué es una tasa variable?", r: "Una tasa que se recalcula periódicamente sobre una referencia de mercado, la TIIE a 28 días, más un margen fijo del banco. Si la TIIE sube, tu pago sube. Por eso la propuesta muestra el costo en tres escenarios de tasa, no en uno." },
          { p: "¿Conviene sustituir mi hipoteca actual?", r: "Depende de dos cosas distintas: cuánto baja el pago mensual y cuánto cuesta cambiarse. El punto de equilibrio es el mes en que el ahorro acumulado cubre ese costo. Si planeas conservar el crédito menos tiempo que eso, cambiarte no conviene." },
        ] },
      ],
    },
    {
      id: "contacto",
      titulo: "Contacto",
      activa: true,
      bloques: [],
    },
  ],
  contacto: { direccion: "", telefono: "", correo: "", horario: "" },
};

// --- Escenario -------------------------------------------------------------
export const cliente = { nombre: "", correo: "", telefono: "" };

export const gastosNotarialesPctDefault = 0.07;

// Captura nueva: en blanco.
export const escenarioBase = {
  familia: "hipotecario",
  subtipo: "adquisicion",
  etiqueta: "",
  valorVivienda: 0,
  montoCredito: 0,
  enganche: 0,
  plazoMeses: 240,
  gastosNotariales: 0,
  ingresoMensual: 0,
  factorPagoIngreso: 0.35,
};

export const escenariosBase = {
  adquisicion: escenarioBase,
  sustitucion: { familia: "hipotecario", subtipo: "sustitucion", etiqueta: "", montoCredito: 0, plazoMeses: 0 },
  liquidez: { familia: "hipotecario", subtipo: "liquidez", etiqueta: "", montoCredito: 0, plazoMeses: 0 },
  terreno: { familia: "hipotecario", subtipo: "terreno", etiqueta: "", montoCredito: 0, plazoMeses: 0 },
  pyme: { familia: "pyme", subtipo: "pyme", etiqueta: "", montoCredito: 0, plazoMeses: 0 },
};

export const valorGarantiaDe = (e) => {
  if (e.subtipo === "adquisicion") return e.valorVivienda || 0;
  if (e.subtipo === "liquidez") return e.valorInmuebleGarantia || 0;
  if (e.subtipo === "terreno") return e.valorTerreno || 0;
  if (e.subtipo === "sustitucion") return e.valorInmueble || 0;
  return e.valorGarantia || 0;
};
export const aforo = (e) => {
  const v = valorGarantiaDe(e);
  return v ? (e.montoCredito || 0) / v : null;
};

// Escenarios trabajados (pantalla Escenarios). Sin persistencia todavía.
export const escenarios = [];

// --- Comunicación con la API ----------------------------------------------
const suscriptores = new Set();
function avisar() {
  suscriptores.forEach((fn) => fn());
}

// La interfaz se vuelve a dibujar cuando llega una respuesta de la API.
export function suscribir(fn) {
  suscriptores.add(fn);
  return () => suscriptores.delete(fn);
}

export let estadoApi = { catalogo: "pendiente", error: null };

const num = (x) => (x === null || x === undefined ? null : Number(x));

export const ETIQUETA_CONVENCION = {
  "tasa/12": "Tasa / 12",
  "tasa*30.4166/360": "Tasa × 30.4166 / 360",
  "tasa*30.4/360": "Tasa × 30.4 / 360",
  "(tasa/360)*(365/12)": "(Tasa / 360) × (365 / 12)",
  "tasa*dias_reales/360": "Tasa × días del mes / 360",
};

// Producto de la API → forma que usa la interfaz.
function adaptarProducto(p) {
  return {
    id: p.id,
    familia: "hipotecario",
    subtipo: "adquisicion",
    institucion: p.institucion,
    nombre: p.nombre,
    tasa: { tipo: "fija", valor: num(p.tasaAnual), referencia: null, spread: null, piso: null, techo: null },
    tasaNormalizada: num(p.tasaNormalizada),
    convencionInteres: p.convencionInteres,
    convencionPago: p.convencionPago,
    convencionAmortizacion: p.convencionAmortizacion,
    segurosEnPagoFijo: p.segurosEnPagoFijo,
    plazosMeses: p.plazosMeses,
    aforoMax: num(p.aforoMax),
    comisionApertura: num(p.comisionApertura),
    comisionAperturaMonto: num(p.comisionAperturaMonto),
    comisionMensual: num(p.comisionMensual),
    crecimientoPago: (p.crecimientoPagoMensual || []).map((f) => ({ desdeMes: f.desdeMes, mensual: num(f.crecimientoMensual) })),
    tasasEscalonadas: (p.tasasEscalonadas || []).map((e) => ({ desdeMes: e.desdeMes, tasaAnual: num(e.tasaAnual) })),
    recalcularPagoAlCambiarTasa: !!p.recalcularPagoAlCambiarTasa,
    seguroVidaMensual: num(p.seguroVidaMensual),
    seguroDanosAnual: num(p.seguroDanosAnual),
    seguroDanosMontoMensual: num(p.seguroDanosMontoMensual),
    baseSeguroDanos: p.baseSeguroDanos,
    factorConstruccion: num(p.factorConstruccion),
    avaluo: num(p.avaluo),
    catNetosDeIva: p.catNetosDeIva || [],
    tablaTasas: (p.tablaTasas || []).map((t) => ({ plazoMaxMeses: t.plazoMaxMeses, aforoMax: num(t.aforoMax), tasaAnual: num(t.tasaAnual) })),
    tieneTarifaAvaluo: !!p.tieneTarifaAvaluo,
    valorMinimoInmueble: num(p.valorMinimoInmueble),
    requiereCofinanciamiento: !!p.requiereCofinanciamiento,
    institutoCofinanciamiento: p.reglaAportaciones ? p.reglaAportaciones.instituto.toUpperCase() : null,
    montoMinimo: num(p.montoMinimo),
    montoMaximo: num(p.montoMaximo),
    vigenteDesde: p.vigenteDesde,
    vigenteHasta: p.vigenteHasta,
    fuente: p.fuente,
    notas: p.notas,
    negociadoPor: p.negociadoPor,
    penalizacionPrepago: "",
  };
}

// Se llena con /api/catalogo. Se muta en sitio para que las referencias
// existentes vean el catálogo cargado.
export const productos = [];

export async function cargarCatalogo() {
  try {
    const r = await fetch("/api/catalogo");
    if (!r.ok) throw new Error("La API respondió " + r.status);
    const datos = await r.json();
    productos.splice(0, productos.length, ...datos.productos.map(adaptarProducto));
    estadoApi = { catalogo: "listo", error: null };
  } catch (e) {
    estadoApi = { catalogo: "error", error: String(e.message || e) };
    console.error("No se pudo cargar el catálogo:", e);
  }
  avisar();
}

// Fecha más reciente de las condiciones del catálogo, para el aviso legal.
export function fechaCondiciones() {
  const fechas = productos.map((p) => p.vigenteDesde).filter(Boolean).sort();
  return fechas.length ? fechas[fechas.length - 1] : HOY;
}

const ETIQUETA_CONCEPTO_IVA = {
  comision_apertura: "comisión por apertura",
  avaluo: "avalúo",
  seguro_danos: "seguro de daños",
  comision_mensual: "comisión mensual",
};

export function conceptosNetosDeIva(producto) {
  const lista = (producto.catNetosDeIva || []).map((c) => ETIQUETA_CONCEPTO_IVA[c] || c);
  return lista.length ? lista.join(", ") : "Ninguno (todo con IVA)";
}

export function descripcionEscalones(producto) {
  const e = producto.tasasEscalonadas || [];
  if (!e.length) return "Tasa única";
  const pct = (x) => (x * 100).toFixed(2) + "\u00A0%";
  const tramos = [pct(producto.tasa.valor) + " desde el mes 1"].concat(
    e.map((x) => pct(x.tasaAnual) + " desde el mes " + x.desdeMes)
  );
  return tramos.join("; ") + (producto.recalcularPagoAlCambiarTasa ? ". El pago se recalcula." : ". Pago fijo: se liquida antes.");
}

export function descripcionTablaTasas(producto) {
  const t = producto.tablaTasas || [];
  if (!t.length) return "Tasa única";
  const pct = (x) => (x * 100).toFixed(2) + "\u00A0%";
  return t.map((x) => "hasta " + x.plazoMaxMeses + " meses y aforo " + pct(x.aforoMax) + ": " + pct(x.tasaAnual)).join("; ");
}

export function tasaNormalizada(producto) {
  return producto.tasaNormalizada;
}

export function descripcionCrecimiento(producto) {
  const f = producto.crecimientoPago || [];
  if (!f.length) return "Pago fijo";
  return f.map((x) => (x.mensual * 100).toFixed(4) + "\u00A0% mensual desde el mes " + x.desdeMes).join("; ")
    + (f.length > 1 ? ". Al cambiar de fase el pago se recalcula sobre el saldo." : "");
}

export function comportamientoMensualidad(producto) {
  if ((producto.crecimientoPago || []).length) return "Creciente";
  return producto.seguroVidaMensual > 0 ? "Decreciente" : "Fija";
}

// Opción de la API → forma que usa la interfaz.
function adaptarOpcion(o, escenario) {
  const delCatalogo = productos.find((p) => p.id === o.productoId);
  // La tasa y el avalúo pueden depender del escenario (tabla por plazo y
  // aforo, tabulador de avalúo): se muestran los que usó el motor.
  const producto = delCatalogo && Object.assign({}, delCatalogo, {
    tasa: Object.assign({}, delCatalogo.tasa, { valor: num(o.tasaAnual) }),
    tasaNormalizada: num(o.tasaNormalizada),
    avaluo: num(o.avaluo),
  });
  const elegible = o.elegible;
  const v = (x) => (elegible ? num(x) : null);
  return {
    producto,
    familia: "hipotecario",
    subtipo: "adquisicion",
    tasaAnual: producto ? producto.tasa.valor : null,
    tasaVariable: false,
    montoCredito: num(o.montoCredito),
    aforo: num(o.aforo),
    comisionApertura: num(o.comisionApertura),
    totalComisionMensual: v(o.totalComisionMensual),
    totalAportaciones: v(o.totalAportaciones),
    avaluo: num(o.avaluo),
    gastosNotariales: num(o.gastosNotariales),
    penalizacionSalida: 0,
    catEstimado: v(o.catEstimado),
    pagoPrimerMes: v(o.pagoPrimerMes),
    pagoUltimoMes: v(o.pagoUltimoMes),
    totalIntereses: v(o.totalIntereses),
    totalSeguros: v(o.totalSeguros),
    sumaMensualidades: v(o.sumaMensualidades),
    plazoEfectivoMeses: elegible ? o.plazoEfectivoMeses : null,
    costoTotal: v(o.costoTotal),
    costoFinanciero: v(o.costoFinanciero),
    desembolsoInicial: num(o.desembolsoInicial),
    costoDeCambiarse: null,
    elegible,
    motivosRechazo: o.motivosRechazo,
    advertencias: o.advertencias,
    tabla: elegible
      ? o.tabla.map((r) => ({
          mes: r.mes,
          fechaPago: r.fechaPago,
          saldoInicial: num(r.saldoInicial),
          capital: num(r.capital),
          interes: num(r.interes),
          seguroVida: num(r.seguroVida),
          seguroDanos: num(r.seguroDanos),
          comisionMensual: num(r.comisionMensual),
          aportacion: num(r.aportacion),
          pagoTotal: num(r.pagoTotal),
          saldoFinal: num(r.saldoFinal),
        }))
      : [],
  };
}

// Resultados de /api/comparar por escenario. La interfaz pide los resultados
// de forma síncrona al dibujar: si no están, se piden y se vuelve a dibujar
// cuando llegan.
const resultados = new Map();

function cuerpoComparacion(escenario) {
  if (escenario.subtipo !== "adquisicion") return null;
  const valor = escenario.valorVivienda || 0;
  const monto = escenario.montoCredito || 0;
  // El enganche ya descuenta lo que cubre el instituto (crédito + subcuenta).
  const enganche = escenario.enganche === undefined ? valor - monto : escenario.enganche;
  if (valor <= 0 || monto <= 0 || enganche < 0 || !escenario.plazoMeses) return null;
  const cofi = escenario.cofinanciamiento;
  return {
    valorVivienda: String(valor),
    enganche: String(enganche),
    plazoMeses: escenario.plazoMeses,
    gastosNotariales: String(escenario.gastosNotariales || 0),
    ingresoMensual: escenario.ingresoMensual ? String(escenario.ingresoMensual) : null,
    factorPagoIngreso: String(escenario.factorPagoIngreso || 0.3),
    cofinanciamiento: cofi ? {
      instituto: cofi.instituto,
      salarioMensual: String(cofi.salarioMensual || 0),
      montoCreditoInstituto: String(cofi.montoCreditoInstituto || 0),
      saldoSubcuenta: String(cofi.saldoSubcuenta || 0),
    } : null,
  };
}

export function estadoComparacion(escenario) {
  const cuerpo = cuerpoComparacion(escenario);
  if (!cuerpo) return "incompleto";
  const r = resultados.get(JSON.stringify(cuerpo));
  return r ? r.estado : "pendiente";
}

export function evaluarEscenario(escenario, escenarioRefId, ids) {
  const cuerpo = cuerpoComparacion(escenario);
  if (!cuerpo || !productos.length) return [];
  const clave = JSON.stringify(cuerpo);
  const guardado = resultados.get(clave);

  if (!guardado) {
    resultados.set(clave, { estado: "calculando", opciones: [] });
    fetch("/api/comparar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: clave,
    })
      .then((r) => r.json().then((datos) => ({ ok: r.ok, datos })))
      .then(({ ok, datos }) => {
        if (!ok) throw new Error(datos.detail || "Error de la API");
        resultados.set(clave, { estado: "listo", opciones: datos.opciones });
      })
      .catch((e) => {
        resultados.set(clave, { estado: "error", opciones: [], error: String(e.message || e) });
        console.error("No se pudo comparar el escenario:", e);
      })
      .then(avisar);
    return [];
  }

  const opciones = guardado.opciones
    .map((o) => adaptarOpcion(o, escenario))
    .filter((o) => o.producto && (!ids || ids.includes(o.producto.id)));
  return opciones;
}

// Sustitución todavía no la modela el motor.
export function evaluarSustitucion() {
  return { lineaBase: null, opciones: [] };
}

// Solo aplica a productos de tasa variable; el catálogo actual no tiene.
export function sensibilidad() {
  return null;
}

export const avisoLegal = [
  "Esta comparación es informativa y no constituye una oferta de crédito, una preaprobación ni un compromiso de otorgamiento por parte de ninguna institución.",
  "El CAT mostrado es un cálculo propio conforme a la metodología publicada por el Banco de México y está pendiente de validación contra el CAT publicado por cada institución.",
  "En los productos de tasa variable el costo total depende del comportamiento futuro de la TIIE. Las cifras corresponden al escenario de tasa señalado y no son una previsión.",
  "La tasa final depende del análisis de riesgo que cada institución realice sobre el expediente del solicitante y puede diferir de la tasa publicada que aquí se compara.",
  "Las tasas, comisiones, seguros y requisitos pueden cambiar sin previo aviso. Las cifras corresponden a las condiciones vigentes en la fecha de consulta indicada en esta página.",
  "Los gastos notariales, impuestos y derechos de registro son estimados y varían por notaría y municipio. El avalúo puede modificar el monto autorizado.",
];
