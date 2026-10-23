// ---------------------------------------------------------------------------
// Fuente única de datos del prototipo.
// Los nombres de campo corresponden al motor de cálculo en Python.
// No traducir ni renombrar: la respuesta real de la API debe embonar aquí.
// ---------------------------------------------------------------------------

export const organizacion = {
  nombre: "Grupo Inmobiliario Demo",
  logoTexto: "GID",
  colorAcento: "#1B3A5C",
  modoMarcaDefault: "corporativa_asesor",
  retencionMeses: 24,
  asesores: [
    { id: "u-1", nombre: "Mariana Cortés Villalba", correo: "mariana.cortes@demo.mx", rol: "Administrador", cedula: "AC-04821", telefono: "(722) 118-4407" },
    { id: "u-2", nombre: "Rodrigo Serna Aguilar", correo: "rodrigo.serna@demo.mx", rol: "Asesor", cedula: "AC-07514", telefono: "(722) 229-0117" },
    { id: "u-3", nombre: "Paulina Escobedo Rangel", correo: "paulina.escobedo@demo.mx", rol: "Asesor", cedula: "AC-09033", telefono: "(722) 887-1440" },
    { id: "u-4", nombre: "Iván Lozano Treviño", correo: "ivan.lozano@demo.mx", rol: "Asesor", cedula: "AC-01277", telefono: "(811) 934-5560" },
  ],
};

export const asesorActual = organizacion.asesores[0];

// --- Taxonomía de productos ------------------------------------------------
export const FAMILIAS = [
  {
    id: "hipotecario",
    nombre: "Hipotecario",
    descripcion: "Crédito con garantía inmobiliaria",
    subtipos: [
      { id: "adquisicion", nombre: "Adquisición", disponible: true, porDefecto: true },
      { id: "sustitucion", nombre: "Sustitución", disponible: true },
      { id: "liquidez", nombre: "Liquidez", disponible: true },
      { id: "terreno", nombre: "Adquisición de terreno", disponible: true },
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
export const plantillaOrganizacion = {
  organizacionId: "org-demo",
  nombre: "Grupo Inmobiliario Demo",
  colorAcento: "#1B3A5C",
  logoUrl: null,
  paginasFijas: [
    {
      id: "sobre-nosotros",
      titulo: "Sobre nosotros",
      activa: true,
      bloques: [
        { tipo: "parrafo", texto: "Somos una correduría inmobiliaria y de crédito con operación en el Estado de México, Querétaro y la Ciudad de México. Acompañamos al cliente desde la comparación de opciones hasta la firma en notaría." },
        { tipo: "cifras", items: [
          { valor: "14 años", etiqueta: "de operación" },
          { valor: "9", etiqueta: "instituciones en catálogo" },
          { valor: "Sin costo", etiqueta: "para el cliente: la institución paga la comisión" },
        ] },
        { tipo: "parrafo", texto: "No cobramos al cliente por la gestión. Nuestro ingreso proviene de la institución que otorga el crédito, y comparamos el catálogo completo, no solo a quien nos paga más." },
      ],
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
  contacto: {
    direccion: "Av. Ejemplo 123, Toluca, Estado de México",
    telefono: "(722) 000-0000",
    correo: "contacto@grupodemo.mx",
    horario: "Lunes a viernes, 9:00 a 18:00",
  },
};

// --- Escenarios capturados por el asesor -----------------------------------
// Forma base común: familia, subtipo, cliente, etiqueta, montoCredito,
// plazoMeses. Los campos restantes dependen del subtipo.
export const cliente = {
  nombre: "Alejandra Ruiz Mendoza",
  correo: "alejandra.ruiz@correo.mx",
  telefono: "(722) 118-4407",
};

export const escenarioBase = {
  familia: "hipotecario",
  subtipo: "adquisicion",
  etiqueta: "Casa en Metepec",
  valorVivienda: 2500000,
  montoCredito: 1850000,
  enganche: 650000,
  plazoMeses: 240,
  gastosNotariales: 140000,
  ingresoMensual: 90000,
  factorPagoIngreso: 0.35,
};

// Escenario semilla por subtipo: los que ya corrió el motor.
export const escenariosBase = {
  adquisicion: escenarioBase,
  sustitucion: {
    familia: "hipotecario",
    subtipo: "sustitucion",
    etiqueta: "Sustitución casa en Toluca",
    institucionActual: "Institución Demo F",
    saldoInsoluto: 1420000,
    tasaActual: 0.1260,
    pagoMensualActual: 19342.47,
    plazoRemanenteMeses: 168,
    penalizacionPrepago: 0,
    valorInmueble: 2600000,
    montoCredito: 1420000,
    plazoNuevoMeses: 168,
    plazoMeses: 168,
    gastosNotariales: 85000,
    ingresoMensual: 90000,
    factorPagoIngreso: 0.35,
  },
  liquidez: {
    familia: "hipotecario",
    subtipo: "liquidez",
    etiqueta: "Liquidez sobre casa en Metepec",
    valorInmuebleGarantia: 3500000,
    montoCredito: 1400000,
    plazoMeses: 120,
    destino: "Consolidación de deuda",
    gastosNotariales: 95000,
    ingresoMensual: 90000,
    factorPagoIngreso: 0.35,
  },
  terreno: {
    familia: "hipotecario",
    subtipo: "terreno",
    etiqueta: "Terreno en Almoloya",
    valorTerreno: 1200000,
    montoCredito: 720000,
    enganche: 480000,
    plazoMeses: 120,
    serviciosUrbanizacion: "Con servicios",
    gastosNotariales: 78000,
    ingresoMensual: 90000,
    factorPagoIngreso: 0.35,
  },
  pyme: {
    familia: "pyme",
    subtipo: "pyme",
    etiqueta: "Capital de trabajo 2026",
    montoCredito: 2000000,
    plazoMeses: 48,
    destino: "Capital de trabajo",
    ventasAnuales: 18000000,
    antiguedadEmpresaAnios: 6,
    garantia: "Sin garantía",
    valorGarantia: null,
    modalidad: "Crédito simple",
  },
};

// Valor por defecto para una captura nueva.
export const gastosNotarialesPctDefault = 0.07;

// Derivados: se calculan, nunca se guardan
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

// --- Lista de escenarios trabajados (pantalla Escenarios) ------------------
export const escenarios = [
  { id: "esc-1", cliente: "Alejandra Ruiz Mendoza", etiqueta: "Casa en Metepec", subtipo: "adquisicion", montoCredito: 1850000, fecha: "2026-01-15", estado: "Borrador", escenario: escenarioBase },
  { id: "esc-2", cliente: "Héctor Ibarra Quiroz", etiqueta: "Sustitución casa en Toluca", subtipo: "sustitucion", montoCredito: 1420000, fecha: "2026-01-14", estado: "Borrador", escenario: escenariosBase.sustitucion },
  { id: "esc-3", cliente: "Familia Zamudio Peña", etiqueta: "Liquidez sobre casa en Metepec", subtipo: "liquidez", montoCredito: 1400000, fecha: "2026-01-12", estado: "Presentación entregada", escenario: escenariosBase.liquidez },
  { id: "esc-4", cliente: "Ximena Del Valle Ocampo", etiqueta: "Terreno en Almoloya", subtipo: "terreno", montoCredito: 720000, fecha: "2026-01-09", estado: "Borrador", escenario: escenariosBase.terreno },
  { id: "esc-5", cliente: "Mecánica Bustamante, S.A.", etiqueta: "Capital de trabajo 2026", subtipo: "pyme", montoCredito: 2000000, fecha: "2026-01-08", estado: "Presentación entregada", escenario: escenariosBase.pyme },
  { id: "esc-6", cliente: "Norma Aguirre Salgado", etiqueta: "Depto. Coyoacán, remodelado", subtipo: "adquisicion", montoCredito: 1425000, fecha: "2026-01-05", estado: "Borrador" },
  { id: "esc-7", cliente: "Sergio Villaseñor Pardo", etiqueta: "Casa en Cholul, Mérida", subtipo: "adquisicion", montoCredito: 2790000, fecha: "2025-12-19", estado: "Presentación entregada" },
];

// --- Catálogo --------------------------------------------------------------
const comun = {
  // Convención de días: cómo pasa la tasa anual a tasa mensual. Ver
  // ConvencionDias en api/motor_hipotecario/modelos.py.
  convencionInteres: "tasa/12",
  convencionPago: null, // null = la misma del interés
  comisionMensual: 0,
  crecimientoMensualidadAnual: 0,
  montoMaximo: null,
  notas: "",
  negociadoPor: null,
  penalizacionPrepago: "Sin penalización por pago anticipado.",
};

export const productos = [
  // ---------------- Hipotecario › Adquisición ----------------
  Object.assign({}, comun, {
    id: "demo-a-fija", familia: "hipotecario", subtipo: "adquisicion",
    institucion: "Institución Demo A", nombre: "Hipotecario Tasa Fija",
    tasa: { tipo: "fija", valor: 0.1085, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [60, 120, 180, 240], aforoMax: 0.90,
    comisionApertura: 0.0085, seguroVidaMensual: 0.00045, seguroDanosAnual: 0.0035,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0.70,
    avaluo: 9500, gastosInvestigacion: 3500, montoMinimo: 300000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-15",
  }),
  Object.assign({}, comun, {
    id: "demo-b-casa-fija", familia: "hipotecario", subtipo: "adquisicion",
    institucion: "Institución Demo B", nombre: "Crédito Casa Fija",
    tasa: { tipo: "fija", valor: 0.1045, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [120, 180, 240], aforoMax: 0.85,
    comisionApertura: 0.0115, seguroVidaMensual: 0.00064, seguroDanosAnual: 0.0040,
    baseSeguroDanos: "valor_total", factorConstruccion: 0.70,
    avaluo: 11200, gastosInvestigacion: 4200, montoMinimo: 400000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-14",
    notas: "El seguro de daños se calcula sobre valor total del inmueble.",
  }),
  Object.assign({}, comun, {
    id: "demo-c-preferente", familia: "hipotecario", subtipo: "adquisicion",
    institucion: "Institución Demo C", nombre: "Hipoteca Preferente",
    tasa: { tipo: "fija", valor: 0.1120, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [60, 120, 180, 240], aforoMax: 0.85,
    comisionApertura: 0.0125, seguroVidaMensual: 0.00035, seguroDanosAnual: 0.0035,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0.70,
    avaluo: 12500, gastosInvestigacion: 3900, montoMinimo: 350000,
    vigenteDesde: "2025-11-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-10",
  }),
  Object.assign({}, comun, {
    id: "demo-d-plazo-corto", familia: "hipotecario", subtipo: "adquisicion",
    institucion: "Institución Demo D", nombre: "Hipotecario Plazo Corto",
    tasa: { tipo: "fija", valor: 0.0990, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [60, 120, 180], aforoMax: 0.90,
    comisionApertura: 0.0075, seguroVidaMensual: 0.00045, seguroDanosAnual: 0.0035,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0.70,
    avaluo: 8900, gastosInvestigacion: 3200, montoMinimo: 300000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-15",
  }),
  // Demo H y Demo I copian las condiciones de Demo A y solo cambian la base
  // de días, para mostrar su efecto en el comparativo.
  Object.assign({}, comun, {
    id: "demo-h-base360", familia: "hipotecario", subtipo: "adquisicion",
    institucion: "Institución Demo H", nombre: "Hipotecario Base 360",
    tasa: { tipo: "fija", valor: 0.1085, referencia: null, spread: null, piso: null, techo: null },
    convencionInteres: "tasa*30.4166/360", convencionPago: "(tasa/360)*(365/12)",
    plazosMeses: [60, 120, 180, 240], aforoMax: 0.90,
    comisionApertura: 0.0085, seguroVidaMensual: 0.00045, seguroDanosAnual: 0.0035,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0.70,
    avaluo: 9500, gastosInvestigacion: 3500, montoMinimo: 300000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Producto ilustrativo: condiciones de Demo A en base 360",
    notas: "Misma tasa nominal que Demo A; en base 360 cuesta como ~11.00 % en base /12.",
  }),
  Object.assign({}, comun, {
    id: "demo-i-base304", familia: "hipotecario", subtipo: "adquisicion",
    institucion: "Institución Demo I", nombre: "Hipotecario Base 30.4",
    tasa: { tipo: "fija", valor: 0.1085, referencia: null, spread: null, piso: null, techo: null },
    convencionInteres: "tasa*30.4/360",
    plazosMeses: [60, 120, 180, 240], aforoMax: 0.90,
    comisionApertura: 0.0085, seguroVidaMensual: 0.00045, seguroDanosAnual: 0.0035,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0.70,
    avaluo: 9500, gastosInvestigacion: 3500, montoMinimo: 300000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Producto ilustrativo: condiciones de Demo A en base 30.4/360",
    notas: "Misma tasa nominal que Demo A, con interés en base 30.4/360.",
  }),
  Object.assign({}, comun, {
    id: "demo-a-fija-convenio-gid", familia: "hipotecario", subtipo: "adquisicion",
    institucion: "Institución Demo A", nombre: "Hipotecario Tasa Fija — Convenio",
    tasa: { tipo: "fija", valor: 0.1020, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [60, 120, 180, 240], aforoMax: 0.90,
    comisionApertura: 0.0060, seguroVidaMensual: 0.00045, seguroDanosAnual: 0.0035,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0.70,
    avaluo: 9500, gastosInvestigacion: 3500, montoMinimo: 300000,
    vigenteDesde: "2026-01-01", vigenteHasta: "2026-06-30",
    fuente: "Convenio firmado con la organización, 2026-01-02",
    notas: "Aplica solo a clientes referidos por la organización.",
    negociadoPor: "Grupo Inmobiliario Demo",
  }),
  Object.assign({}, comun, {
    id: "demo-c-preferente-2025", familia: "hipotecario", subtipo: "adquisicion",
    institucion: "Institución Demo C", nombre: "Hipoteca Preferente (versión anterior)",
    tasa: { tipo: "fija", valor: 0.1195, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [60, 120, 180, 240], aforoMax: 0.80,
    comisionApertura: 0.0125, seguroVidaMensual: 0.00035, seguroDanosAnual: 0.0035,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0.70,
    avaluo: 12500, gastosInvestigacion: 3900, montoMinimo: 350000,
    vigenteDesde: "2025-04-01", vigenteHasta: "2025-10-31",
    fuente: "Condiciones publicadas, consultadas 2025-04-03",
    notas: "Cerrada por cambio de tasa. Se conserva para reproducir presentaciones entregadas.",
  }),

  // ---------------- Hipotecario › Sustitución ----------------
  Object.assign({}, comun, {
    id: "demo-a-sustitucion", familia: "hipotecario", subtipo: "sustitucion",
    institucion: "Institución Demo A", nombre: "Sustitución Hipotecaria",
    tasa: { tipo: "fija", valor: 0.1085, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [60, 120, 168, 180, 240], aforoMax: 0.85,
    comisionApertura: 0.0085, seguroVidaMensual: 0.00045, seguroDanosAnual: 0.0035,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0.70,
    avaluo: 9500, gastosInvestigacion: 3500, montoMinimo: 300000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-15",
  }),
  Object.assign({}, comun, {
    id: "demo-c-mejora", familia: "hipotecario", subtipo: "sustitucion",
    institucion: "Institución Demo C", nombre: "Mejora tu Crédito",
    tasa: { tipo: "fija", valor: 0.1120, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [60, 120, 168, 180, 240], aforoMax: 0.85,
    comisionApertura: 0, seguroVidaMensual: 0.00035, seguroDanosAnual: 0.0035,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0.70,
    avaluo: 8000, gastosInvestigacion: 0, montoMinimo: 300000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-13",
    notas: "Sin comisión por apertura en sustitución de hipoteca.",
  }),
  Object.assign({}, comun, {
    id: "demo-b-cambia", familia: "hipotecario", subtipo: "sustitucion",
    institucion: "Institución Demo B", nombre: "Cambia tu Hipoteca",
    tasa: { tipo: "fija", valor: 0.1045, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [120, 168, 180, 240], aforoMax: 0.80,
    comisionApertura: 0.0100, seguroVidaMensual: 0.00064, seguroDanosAnual: 0.0040,
    baseSeguroDanos: "valor_total", factorConstruccion: 0.70,
    avaluo: 11000, gastosInvestigacion: 4200, montoMinimo: 400000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-14",
  }),

  // ---------------- Hipotecario › Liquidez ----------------
  Object.assign({}, comun, {
    id: "demo-a-liquidez", familia: "hipotecario", subtipo: "liquidez",
    institucion: "Institución Demo A", nombre: "Liquidez con Garantía",
    tasa: { tipo: "fija", valor: 0.1495, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [60, 120, 180], aforoMax: 0.50,
    comisionApertura: 0.0250, seguroVidaMensual: 0.00045, seguroDanosAnual: 0.0035,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0.70,
    avaluo: 9500, gastosInvestigacion: 3500, montoMinimo: 300000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-15",
  }),
  Object.assign({}, comun, {
    id: "demo-b-liquidez", familia: "hipotecario", subtipo: "liquidez",
    institucion: "Institución Demo B", nombre: "Crédito Liquidez Patrimonial",
    tasa: { tipo: "fija", valor: 0.1420, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [60, 120, 180], aforoMax: 0.45,
    comisionApertura: 0.0300, seguroVidaMensual: 0.00064, seguroDanosAnual: 0.0040,
    baseSeguroDanos: "valor_total", factorConstruccion: 0.70,
    avaluo: 11200, gastosInvestigacion: 4200, montoMinimo: 400000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-14",
  }),
  Object.assign({}, comun, {
    id: "demo-e-liquidez", familia: "hipotecario", subtipo: "liquidez",
    institucion: "Institución Demo E", nombre: "Hipoteca Liquidez",
    tasa: { tipo: "fija", valor: 0.1560, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [60, 120, 180], aforoMax: 0.60,
    comisionApertura: 0.0200, seguroVidaMensual: 0.00040, seguroDanosAnual: 0.0035,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0.70,
    avaluo: 10400, gastosInvestigacion: 3800, montoMinimo: 350000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-12",
  }),

  // ---------------- Hipotecario › Adquisición de terreno ----------------
  // Sin seguro de daños: un terreno baldío no tiene construcción que asegurar.
  Object.assign({}, comun, {
    id: "demo-b-terreno", familia: "hipotecario", subtipo: "terreno",
    institucion: "Institución Demo B", nombre: "Adquisición de Terreno",
    tasa: { tipo: "fija", valor: 0.1310, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [60, 120, 180], aforoMax: 0.70,
    comisionApertura: 0.0250, seguroVidaMensual: 0.00064, seguroDanosAnual: 0,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0,
    avaluo: 11500, gastosInvestigacion: 4200, montoMinimo: 200000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-14",
  }),
  Object.assign({}, comun, {
    id: "demo-a-terreno", familia: "hipotecario", subtipo: "terreno",
    institucion: "Institución Demo A", nombre: "Crédito Terreno",
    tasa: { tipo: "fija", valor: 0.1385, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [60, 120, 180], aforoMax: 0.70,
    comisionApertura: 0.0150, seguroVidaMensual: 0.00045, seguroDanosAnual: 0,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0,
    avaluo: 9000, gastosInvestigacion: 3500, montoMinimo: 200000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-15",
  }),
  Object.assign({}, comun, {
    id: "demo-e-terreno", familia: "hipotecario", subtipo: "terreno",
    institucion: "Institución Demo E", nombre: "Terreno Patrimonial",
    tasa: { tipo: "fija", valor: 0.1450, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [60, 120, 180], aforoMax: 0.65,
    comisionApertura: 0, seguroVidaMensual: 0.00040, seguroDanosAnual: 0,
    baseSeguroDanos: "valor_construccion", factorConstruccion: 0,
    avaluo: 8500, gastosInvestigacion: 0, montoMinimo: 200000,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-12",
    notas: "Sin comisión por apertura.",
  }),

  // ---------------- PyME ----------------
  Object.assign({}, comun, {
    id: "demo-b-impulso-pyme", familia: "pyme", subtipo: "pyme",
    institucion: "Institución Demo B", nombre: "Impulso PyME",
    tasa: { tipo: "variable", valor: null, referencia: "TIIE_28", spread: 0.045, piso: null, techo: null },
    plazosMeses: [12, 24, 36, 48, 60], aforoMax: null,
    comisionApertura: 0.0150, seguroVidaMensual: 0, seguroDanosAnual: 0,
    avaluo: 0, gastosInvestigacion: 0, montoMinimo: 250000,
    ventasAnualesMinimas: 5000000, antiguedadMinimaAnios: 2,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-15",
  }),
  Object.assign({}, comun, {
    id: "demo-g-capital-trabajo", familia: "pyme", subtipo: "pyme",
    institucion: "Institución Demo G", nombre: "Capital de Trabajo",
    tasa: { tipo: "variable", valor: null, referencia: "TIIE_28", spread: 0.0575, piso: null, techo: null },
    plazosMeses: [12, 24, 36, 48, 60], aforoMax: null,
    comisionApertura: 0.0100, seguroVidaMensual: 0, seguroDanosAnual: 0,
    avaluo: 0, gastosInvestigacion: 0, montoMinimo: 200000,
    ventasAnualesMinimas: 4000000, antiguedadMinimaAnios: 2,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-11",
  }),
  Object.assign({}, comun, {
    id: "demo-a-pyme-simple", familia: "pyme", subtipo: "pyme",
    institucion: "Institución Demo A", nombre: "Crédito Simple PyME",
    tasa: { tipo: "fija", valor: 0.1750, referencia: null, spread: null, piso: null, techo: null },
    plazosMeses: [12, 24, 36, 48, 60], aforoMax: null,
    comisionApertura: 0.0200, seguroVidaMensual: 0, seguroDanosAnual: 0,
    avaluo: 0, gastosInvestigacion: 0, montoMinimo: 300000,
    ventasAnualesMinimas: 8000000, antiguedadMinimaAnios: 3,
    vigenteDesde: "2026-01-01", vigenteHasta: null,
    fuente: "Condiciones publicadas, consultadas 2026-01-15",
  }),
];

// --- Convención de días ----------------------------------------------------
// Factor que multiplica la tasa anual para obtener la tasa del mes.
const FACTOR_CONVENCION = {
  "tasa/12": 1 / 12,
  "tasa*30.4166/360": 30.4166 / 360,
  "tasa*30.4/360": 30.4 / 360,
  "(tasa/360)*(365/12)": 365 / 12 / 360,
};

export const ETIQUETA_CONVENCION = {
  "tasa/12": "Tasa / 12",
  "tasa*30.4166/360": "Tasa × 30.4166 / 360",
  "tasa*30.4/360": "Tasa × 30.4 / 360",
  "(tasa/360)*(365/12)": "(Tasa / 360) × (365 / 12)",
};

export function tasaPeriodica(tasaAnual, convencion) {
  return tasaAnual * FACTOR_CONVENCION[convencion || "tasa/12"];
}

// Tasa equivalente en base /12. Solo para ordenar; al cliente se le muestra
// la tasa nominal del contrato.
export function tasaNormalizada(producto, escenarioRefId) {
  return tasaPeriodica(tasaResuelta(producto, escenarioRefId), producto.convencionInteres) * 12;
}

// --- Tabla de amortización -------------------------------------------------
// SUSTITUIR: el motor real devuelve esta tabla. Aquí se construye con la
// fórmula de pago fijo para que el prototipo tenga datos consistentes.
export function generarTabla(producto, escenario, plazoMeses, escenarioRefId) {
  const monto = escenario.montoCredito || 0;
  const plazo = plazoMeses || escenario.plazoMeses;
  const tasa = tasaResuelta(producto, escenarioRefId);
  const i = tasaPeriodica(tasa, producto.convencionInteres);
  const iPago = tasaPeriodica(tasa, producto.convencionPago || producto.convencionInteres);
  const pagoFijo = (monto * iPago) / (1 - Math.pow(1 + iPago, -plazo));
  const valorGarantia = valorGarantiaDe(escenario);

  let seguroDanos = 0;
  if (producto.seguroDanosAnual) {
    seguroDanos = producto.baseSeguroDanos === "valor_construccion"
      ? (valorGarantia * producto.factorConstruccion * producto.seguroDanosAnual) / 12
      : (valorGarantia * producto.seguroDanosAnual) / 12;
  }
  const comisionMensual = producto.comisionMensual || 0;

  const tabla = [];
  let saldoInicial = monto;
  for (let mes = 1; mes <= plazo; mes++) {
    const interes = saldoInicial * i;
    const capital = mes === plazo ? saldoInicial : pagoFijo - interes;
    const seguroVida = saldoInicial * (producto.seguroVidaMensual || 0);
    const pagoTotal = capital + interes + seguroVida + seguroDanos + comisionMensual;
    const saldoFinal = mes === plazo ? 0 : saldoInicial - capital;
    tabla.push({ mes, saldoInicial, capital, interes, seguroVida, seguroDanos, comisionMensual, pagoTotal, saldoFinal });
    saldoInicial = saldoFinal;
  }
  return tabla;
}

// Comportamiento de la mensualidad, derivado del producto.
export function comportamientoMensualidad(producto) {
  if ((producto.crecimientoMensualidadAnual || 0) > 0) {
    return "Creciente " + (producto.crecimientoMensualidadAnual * 100).toFixed(2) + "\u00A0% al año";
  }
  if (producto.tasa && producto.tasa.tipo === "variable") return "Variable según TIIE";
  return producto.seguroVidaMensual > 0 ? "Decreciente" : "Fija";
}

// --- Evaluación de un escenario contra un producto -------------------------
// SUSTITUIR: el motor real devuelve este objeto completo.
export function evaluar(producto, escenario, escenarioRefId) {
  const montoCred = escenario.montoCredito || 0;
  const valorGarantia = valorGarantiaDe(escenario);
  const af = valorGarantia ? montoCred / valorGarantia : null;
  const plazo = escenario.plazoMeses;
  const motivosRechazo = [];
  const advertencias = [];

  if (!producto.plazosMeses.includes(plazo)) {
    motivosRechazo.push(
      `El plazo de ${plazo} meses no está disponible. Plazos ofrecidos: ${producto.plazosMeses.join(", ")}.`
    );
  }
  if (producto.aforoMax !== null && producto.aforoMax !== undefined && af !== null && af > producto.aforoMax) {
    motivosRechazo.push(
      `El aforo requerido supera el máximo del producto, que es ${(producto.aforoMax * 100).toFixed(2)} %. Se necesita un monto menor o una garantía de mayor valor.`
    );
  }
  if (montoCred < producto.montoMinimo) {
    motivosRechazo.push(`El monto solicitado es menor al mínimo del producto, que es $${producto.montoMinimo.toLocaleString("es-MX")}.`);
  }
  if (producto.ventasAnualesMinimas && (escenario.ventasAnuales || 0) < producto.ventasAnualesMinimas) {
    motivosRechazo.push(`Las ventas anuales capturadas están por debajo del mínimo del producto, que es $${producto.ventasAnualesMinimas.toLocaleString("es-MX")}.`);
  }
  if (producto.antiguedadMinimaAnios && (escenario.antiguedadEmpresaAnios || 0) < producto.antiguedadMinimaAnios) {
    motivosRechazo.push(`La empresa requiere al menos ${producto.antiguedadMinimaAnios} años de antigüedad comprobable.`);
  }
  if (producto.negociadoPor) {
    advertencias.push(`Condición negociada por ${producto.negociadoPor}. Sujeta a confirmación con la institución.`);
  }
  if (producto.tasa && producto.tasa.tipo === "variable") {
    advertencias.push("Tasa variable referenciada a TIIE 28. El costo total mostrado depende del escenario de tasa seleccionado.");
  }

  const elegible = motivosRechazo.length === 0;
  const tabla = elegible ? generarTabla(producto, escenario, plazo, escenarioRefId) : [];
  const suma = (campo) => tabla.reduce((acc, r) => acc + r[campo], 0);
  const totalIntereses = suma("interes");
  const totalSeguros = suma("seguroVida") + suma("seguroDanos");
  const totalComisionMensual = suma("comisionMensual");
  const sumaMensualidades = suma("pagoTotal");
  const comisionApertura = montoCred * producto.comisionApertura;
  const avaluo = producto.avaluo || 0;
  const gastosNotariales = escenario.gastosNotariales || 0;
  const enganche = escenario.enganche || 0;
  // Penalización por prepago del crédito que se sustituye, no del nuevo.
  const penalizacionSalida = escenario.subtipo === "sustitucion"
    ? (escenario.saldoInsoluto || 0) * (escenario.penalizacionPrepago || 0)
    : 0;

  if (escenario.ingresoMensual && escenario.factorPagoIngreso && elegible && tabla.length) {
    const capacidad = escenario.ingresoMensual * escenario.factorPagoIngreso;
    if (tabla[0].pagoTotal > capacidad) {
      advertencias.push(
        `El primer pago excede el factor de pago sobre ingreso capturado (${(escenario.factorPagoIngreso * 100).toFixed(2)} % del ingreso).`
      );
    }
  }

  const costoTotal = elegible
    ? montoCred + totalIntereses + totalSeguros + totalComisionMensual + comisionApertura + avaluo + gastosNotariales
    : null;

  return {
    producto,
    familia: producto.familia,
    subtipo: producto.subtipo,
    tasaAnual: tasaResuelta(producto, escenarioRefId),
    tasaVariable: !!(producto.tasa && producto.tasa.tipo === "variable"),
    montoCredito: montoCred,
    aforo: af,
    comisionApertura,
    totalComisionMensual: elegible ? totalComisionMensual : null,
    avaluo,
    gastosNotariales,
    penalizacionSalida,
    catEstimado: elegible ? (catEstimadoSemilla[producto.id] ?? null) : null,
    pagoPrimerMes: elegible ? tabla[0].pagoTotal : null,
    pagoUltimoMes: elegible ? tabla[tabla.length - 1].pagoTotal : null,
    totalIntereses: elegible ? totalIntereses : null,
    totalSeguros: elegible ? totalSeguros : null,
    sumaMensualidades: elegible ? sumaMensualidades : null,
    plazoEfectivoMeses: elegible ? tabla.length : null,
    costoTotal,
    costoFinanciero: elegible ? costoTotal - montoCred : null,
    desembolsoInicial: enganche + comisionApertura + avaluo + gastosNotariales,
    costoDeCambiarse: elegible ? comisionApertura + avaluo + gastosNotariales + penalizacionSalida : null,
    elegible,
    motivosRechazo,
    advertencias,
    tabla,
  };
}

// CAT estimado por producto — lo calcula el motor con metodología Banxico.
// SUSTITUIR: viene en resultadoOpcion.catEstimado.
export const catEstimadoSemilla = {
  "demo-a-fija": 0.1269,
  "demo-b-casa-fija": 0.1284,
  "demo-c-preferente": 0.1276,
  "demo-a-fija-convenio-gid": 0.1191,
  "demo-h-base360": 0.1286,
  "demo-i-base304": 0.1285,
  "demo-d-plazo-corto": null,
  "demo-a-sustitucion": 0.1268,
  "demo-c-mejora": 0.1279,
  "demo-b-cambia": 0.1281,
  "demo-a-liquidez": 0.1866,
  "demo-b-liquidez": 0.1908,
  "demo-e-liquidez": 0.1850,
  "demo-b-terreno": 0.1605,
  "demo-a-terreno": 0.1629,
  "demo-e-terreno": 0.1644,
  "demo-b-impulso-pyme": 0.1862,
  "demo-g-capital-trabajo": 0.1900,
  "demo-a-pyme-simple": 0.2089,
};

// Cifras ya producidas por el motor para cada escenario semilla. Se aplican
// sobre el resultado calculado para que el prototipo muestre los números de
// origen. SUSTITUIR: al conectar la API, borrar este bloque y el merge.
export const semillaResultados = {
  "demo-a-fija": { pagoPrimerMes: 20249.91, pagoUltimoMes: 18618.10, costoTotal: 4959170.77, totalIntereses: 2687680.20, totalSeguros: 256265.57, costoFinanciero: 3109170.77, comisionApertura: 15725, desembolsoInicial: 815225, sumaMensualidades: 4694445.77 },
  "demo-b-casa-fija": { pagoPrimerMes: 20429.93, pagoUltimoMes: 18540.00, costoTotal: 4980232.65 },
  "demo-c-preferente": { pagoPrimerMes: 20488.43, pagoUltimoMes: 19020.00, costoTotal: 5010236.30 },
  "demo-a-fija-convenio-gid": { pagoPrimerMes: 19441.65, costoTotal: 4756965.99 },
  // Demo H e I: motor sin redondeo intermedio (las de arriba son del motor
  // anterior, que redondeaba cada renglón; difieren ~$3 en costo total).
  "demo-h-base360": { pagoPrimerMes: 20439.28, pagoUltimoMes: 19589.00, costoTotal: 5004987.21 },
  "demo-i-base304": { pagoPrimerMes: 20431.69, pagoUltimoMes: 19607.70, costoTotal: 5003177.30 },

  "demo-a-liquidez": { pagoPrimerMes: 24028.63, pagoUltimoMes: 23269.87, costoTotal: 2983659.23 },
  "demo-b-liquidez": { pagoPrimerMes: 24110.97, pagoUltimoMes: 23145.98, costoTotal: 2999400.83 },
  "demo-e-liquidez": { pagoPrimerMes: 24388.55, pagoUltimoMes: 23726.70, costoTotal: 3002661.62 },

  "demo-b-terreno": { pagoPrimerMes: 11260.88, pagoUltimoMes: 10800.46, costoTotal: 1436891.59, desembolsoInicial: 587500 },
  "demo-a-terreno": { pagoPrimerMes: 11474.34, pagoUltimoMes: 11119.36, costoTotal: 1458107.49, desembolsoInicial: 577800 },
  "demo-e-terreno": { pagoPrimerMes: 11699.05, pagoUltimoMes: 11401.07, costoTotal: 1476607.32, desembolsoInicial: 566500 },

  "demo-a-sustitucion": { pagoPrimerMes: 17639.38, costoDeCambiarse: 106570, comisionApertura: 12070, avaluo: 9500 },
  "demo-c-mejora": { pagoPrimerMes: 17770.61, costoDeCambiarse: 93000, comisionApertura: 0, avaluo: 8000 },
  "demo-b-cambia": { pagoPrimerMes: 17912.98, costoDeCambiarse: 110200, comisionApertura: 14200, avaluo: 11000 },

  "demo-a-pyme-simple": { pagoPrimerMes: 59028.75, pagoUltimoMes: 58251.54, costoTotal: 2856784.98 },
};

// Productos de tasa variable: el motor entrega una cifra por escenario de
// referencia. SUSTITUIR: el motor real recalcula con la tasa resuelta.
// El CAT solo se calculó para el escenario base.
export const semillaPorEscenarioRef = {
  "demo-b-impulso-pyme": {
    conservador: { costoTotal: 2661305.30, catEstimado: null },
    base: { costoTotal: 2758151.34, pagoPrimerMes: 56815.28, pagoUltimoMes: 55940.07, catEstimado: 0.1862 },
    estres: { costoTotal: 2857012.62, catEstimado: null },
  },
  "demo-g-capital-trabajo": {
    conservador: { costoTotal: 2687845.59, catEstimado: null },
    base: { costoTotal: 2785910.73, pagoPrimerMes: 57954.02, pagoUltimoMes: 57215.45, catEstimado: 0.1900 },
    estres: { costoTotal: 2885975.64, catEstimado: null },
  },
};

// Resultados de sustitución ya producidos por el motor.
// SUSTITUIR: el motor real devuelve punto de equilibrio y ahorro neto.
export const semillaSustitucion = {
  "demo-a-sustitucion": { ahorroMensual: 1703.09, puntoEquilibrioMes: 63, ahorroNeto: 175481.19 },
  "demo-c-mejora": { ahorroMensual: 1571.86, puntoEquilibrioMes: 60, ahorroNeto: 160405.81 },
  "demo-b-cambia": { ahorroMensual: 1429.49, puntoEquilibrioMes: 76, ahorroNeto: 141732.76 },
};

// Línea base del escenario de sustitución: qué pasa si el cliente no hace nada.
export const semillaLineaBase = {
  pagoMensualActual: 19342.47,
  pagoUltimoActual: 18613.29,
  sumaPagosRestantes: 3205150.69,
};

// Un escenario coincide con el semilla cuando los campos financieros son
// idénticos; solo entonces se aplican las cifras del motor.
function coincideConSemilla(escenario) {
  const b = escenariosBase[escenario.subtipo];
  if (!b) return false;
  const campos = ["montoCredito", "plazoMeses", "valorVivienda", "valorInmuebleGarantia", "valorTerreno", "valorInmueble", "saldoInsoluto", "gastosNotariales", "enganche", "ventasAnuales", "antiguedadEmpresaAnios"];
  return campos.every((k) => {
    if (b[k] === undefined) return true;
    return Number(escenario[k] || 0) === Number(b[k] || 0);
  });
}

export function evaluarEscenario(escenario, escenarioRefId, ids) {
  const lista = ids
    ? productos.filter((p) => ids.includes(p.id))
    : productos.filter((p) => p.subtipo === escenario.subtipo && p.id !== "demo-c-preferente-2025");
  const usaSemilla = coincideConSemilla(escenario);
  const ref = escenarioRefId || "base";

  return lista.map((producto) => {
    const res = evaluar(producto, escenario, ref);
    if (!usaSemilla || !res.elegible) return res;
    const semilla = semillaResultados[producto.id];
    if (semilla) Object.assign(res, semilla);
    const porRef = semillaPorEscenarioRef[producto.id];
    if (porRef && porRef[ref]) Object.assign(res, porRef[ref]);
    if (res.costoTotal !== null) res.costoFinanciero = res.costoTotal - res.montoCredito;
    return res;
  });
}

// --- Sustitución: cada opción contra quedarse donde está -------------------
// La línea base es el crédito que el cliente ya tiene.
export function lineaBaseSustitucion(escenario) {
  const productoActual = {
    tasa: { tipo: "fija", valor: escenario.tasaActual },
    seguroVidaMensual: 0.00045,
    seguroDanosAnual: 0.0035,
    baseSeguroDanos: "valor_construccion",
    factorConstruccion: 0.70,
    comisionMensual: 0,
    comisionApertura: 0,
    avaluo: 0,
  };
  const escActual = Object.assign({}, escenario, {
    montoCredito: escenario.saldoInsoluto,
    plazoMeses: escenario.plazoRemanenteMeses,
  });
  const tabla = generarTabla(productoActual, escActual, escenario.plazoRemanenteMeses);
  const suma = tabla.reduce((a, r) => a + r.pagoTotal, 0);
  const usaSemilla = coincideConSemilla(escenario);
  return {
    institucionActual: escenario.institucionActual,
    saldoInsoluto: escenario.saldoInsoluto,
    tasaActual: escenario.tasaActual,
    plazoRemanenteMeses: escenario.plazoRemanenteMeses,
    pagoMensualActual: usaSemilla ? semillaLineaBase.pagoMensualActual : tabla[0].pagoTotal,
    pagoUltimoActual: usaSemilla ? semillaLineaBase.pagoUltimoActual : tabla[tabla.length - 1].pagoTotal,
    sumaPagosRestantes: usaSemilla ? semillaLineaBase.sumaPagosRestantes : suma,
    tabla,
  };
}

// Ahorro acumulado mes a mes, contra la línea base. El cruce con cero es el
// punto de equilibrio. SUSTITUIR: el motor real devuelve esta serie.
export function evaluarSustitucion(escenario, escenarioRefId) {
  const base = lineaBaseSustitucion(escenario);
  const usaSemilla = coincideConSemilla(escenario);
  const opciones = evaluarEscenario(escenario, escenarioRefId).map((res) => {
    if (!res.elegible) return Object.assign({}, res, { serie: [], lineaBase: base });
    const semilla = usaSemilla ? semillaSustitucion[res.producto.id] : null;
    const costo = res.costoDeCambiarse || 0;
    const serie = [];
    let acumulado = -costo;
    const n = Math.min(base.tabla.length, res.tabla.length);
    for (let k = 0; k < n; k++) {
      acumulado += base.tabla[k].pagoTotal - res.tabla[k].pagoTotal;
      serie.push({ mes: k + 1, acumulado });
    }
    const cruce = serie.find((p) => p.acumulado >= 0);
    const ahorroMensualCalc = base.tabla[0].pagoTotal - res.tabla[0].pagoTotal;
    const ahorroNetoCalc = serie.length ? serie[serie.length - 1].acumulado : 0;
    return Object.assign({}, res, {
      lineaBase: base,
      serie,
      ahorroMensual: semilla ? semilla.ahorroMensual : ahorroMensualCalc,
      puntoEquilibrioMes: semilla ? semilla.puntoEquilibrioMes : (cruce ? cruce.mes : null),
      ahorroNeto: semilla ? semilla.ahorroNeto : ahorroNetoCalc,
      costoDeCambiarse: costo,
    });
  });
  opciones.sort((a, b) => (b.ahorroNeto || -Infinity) - (a.ahorroNeto || -Infinity));
  return { lineaBase: base, opciones };
}

// Rango de costo total entre el escenario conservador y el de estrés.
// Solo tiene sentido para productos de tasa variable.
export function sensibilidad(producto, escenario) {
  if (!producto.tasa || producto.tasa.tipo !== "variable") return null;
  const valores = ESCENARIOS_REFERENCIA.map((ref) => {
    const r = evaluarEscenario(escenario, ref.id, [producto.id])[0];
    return r && r.elegible ? r.costoTotal : null;
  }).filter((x) => x !== null);
  if (valores.length < 2) return null;
  return { min: Math.min.apply(null, valores), max: Math.max.apply(null, valores) };
}

export const avisoLegal = [
  "Esta comparación es informativa y no constituye una oferta de crédito, una preaprobación ni un compromiso de otorgamiento por parte de ninguna institución.",
  "El CAT mostrado es un cálculo propio conforme a la metodología publicada por el Banco de México y está pendiente de validación contra el CAT publicado por cada institución.",
  "En los productos de tasa variable el costo total depende del comportamiento futuro de la TIIE. Las cifras corresponden al escenario de tasa señalado y no son una previsión.",
  "La tasa final depende del análisis de riesgo que cada institución realice sobre el expediente del solicitante y puede diferir de la tasa publicada que aquí se compara.",
  "Las tasas, comisiones, seguros y requisitos pueden cambiar sin previo aviso. Las cifras corresponden a las condiciones vigentes en la fecha de consulta indicada en esta página.",
  "Los gastos notariales, impuestos y derechos de registro son estimados y varían por notaría y municipio. El avalúo puede modificar el monto autorizado.",
];
