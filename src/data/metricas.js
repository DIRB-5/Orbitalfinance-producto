// Motor de métricas del pipeline. Todo se deriva de PIPELINE; nada se escribe
// a mano. Las tendencias centrales son MEDIANAS, nunca promedios.
import { PIPELINE, ASESORES, ETAPAS, MOTIVOS_PERDIDA } from "./pipeline.js";

export { PIPELINE, ASESORES, ETAPAS, MOTIVOS_PERDIDA };

export const HOY = new Date().toISOString().slice(0, 10);

const MS_DIA = 86400000;
const t = (iso) => new Date(iso + "T12:00:00").getTime();
export const dias = (a, b) => Math.round((t(b) - t(a)) / MS_DIA);

export function mediana(xs) {
  const v = xs.filter((x) => x !== null && x !== undefined && !isNaN(x)).slice().sort((a, b) => a - b);
  if (!v.length) return null;
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

export const alcanzo = (p, etapa) => !!p.fechas[etapa];
export const esGanado = (p) => p.etapa === "escriturado";
export const esPerdido = (p) => p.etapa === "perdido";
export const esActivo = (p) => p.etapa !== "escriturado" && p.etapa !== "perdido";

// Última fecha registrada del prospecto.
export function ultimaFecha(p) {
  return Object.values(p.fechas).sort().slice(-1)[0];
}
export function diasEnEtapa(p, hoy = HOY) {
  return dias(p.fechas[p.etapa] || ultimaFecha(p), hoy);
}
export const estancado = (p, hoy = HOY) => esActivo(p) && diasEnEtapa(p, hoy) > 30;

export function cicloDe(p) {
  if (!esGanado(p)) return null;
  return dias(p.fechas.prospecto, p.fechas.escriturado);
}

export function metricas(lista) {
  const escenarios = lista.filter((p) => alcanzo(p, "escenario"));
  const propuestas = lista.filter((p) => alcanzo(p, "propuesta"));
  const ganados = lista.filter(esGanado);
  const perdidos = lista.filter(esPerdido);
  const conDiv = propuestas.filter((p) => p.divergencia);
  return {
    total: lista.length,
    escenarios: escenarios.length,
    propuestas: propuestas.length,
    ganados: ganados.length,
    perdidos: perdidos.length,
    activos: lista.filter(esActivo).length,
    convPropuesta: escenarios.length ? propuestas.length / escenarios.length : null,
    convCierre: propuestas.length ? ganados.length / propuestas.length : null,
    ciclo: mediana(ganados.map(cicloDe)),
    divergencias: conDiv.length,
    divergenciaPct: propuestas.length ? conDiv.length / propuestas.length : null,
    divergenciaPesos: conDiv.reduce((a, p) => a + p.divergencia.diferencia, 0),
    colocado: ganados.reduce((a, p) => a + (p.montoFinal || 0), 0),
    montoPipeline: lista.filter(esActivo).reduce((a, p) => a + p.monto, 0),
    estancados: lista.filter((p) => estancado(p)).length,
  };
}

export function porAsesor(pipeline = PIPELINE) {
  return ASESORES.filter((a) => a.rol === "asesor").map((a) => {
    const lista = pipeline.filter((p) => p.asesorId === a.id);
    return Object.assign({ asesor: a, lista }, metricas(lista));
  });
}

// Embudo: cuántos prospectos ALCANZARON cada etapa, con su monto.
export function embudo(lista) {
  return ETAPAS.map((etapa, i) => {
    const en = lista.filter((p) => alcanzo(p, etapa));
    const prev = i === 0 ? null : lista.filter((p) => alcanzo(p, ETAPAS[i - 1])).length;
    return {
      etapa,
      cantidad: en.length,
      // En escrituración vale el monto realmente colocado, no el solicitado.
      monto: en.reduce((a, p) => a + (etapa === "escriturado" ? (p.montoFinal || p.monto) : p.monto), 0),
      caida: prev ? 1 - en.length / prev : null,
    };
  });
}

// Mediana de días que un prospecto permanece en cada etapa (transiciones
// completadas + los que siguen ahí hoy).
export function permanenciaPorEtapa(lista, hoy = HOY) {
  return ETAPAS.map((etapa, i) => {
    const ds = [];
    lista.forEach((p) => {
      const desde = p.fechas[etapa];
      if (!desde) return;
      let hasta = null;
      for (let j = i + 1; j < ETAPAS.length; j++) if (p.fechas[ETAPAS[j]]) { hasta = p.fechas[ETAPAS[j]]; break; }
      if (!hasta && p.fechas.perdido) hasta = p.fechas.perdido;
      if (!hasta) hasta = p.etapa === etapa ? hoy : null;
      if (hasta) ds.push(dias(desde, hasta));
    });
    return { etapa, mediana: mediana(ds), n: ds.length };
  });
}

export function cuelloDeBotella(lista) {
  const ps = permanenciaPorEtapa(lista).filter((x) => x.mediana !== null && x.etapa !== "escriturado");
  return ps.sort((a, b) => b.mediana - a.mediana)[0] || null;
}

export function motivos(lista) {
  const perdidos = lista.filter(esPerdido);
  return MOTIVOS_PERDIDA.map((mo) => {
    const n = perdidos.filter((p) => p.motivoPerdida === mo).length;
    return { motivo: mo, cantidad: n, parte: perdidos.length ? n / perdidos.length : 0 };
  }).filter((x) => x.cantidad > 0).sort((a, b) => b.cantidad - a.cantidad);
}

// Desviación mediana entre tasa cotizada y tasa final aprobada, en pp.
export function precisionCatalogo(pipeline = PIPELINE) {
  const cierres = pipeline.filter((p) => esGanado(p) && p.institucionFinal && p.tasaCotizada != null && p.tasaFinal != null);
  const inst = Array.from(new Set(cierres.map((p) => p.institucionFinal))).sort();
  return inst.map((nombre) => {
    const ls = cierres.filter((p) => p.institucionFinal === nombre);
    return {
      institucion: nombre,
      cierres: ls.length,
      desviacionPP: mediana(ls.map((p) => (p.tasaFinal - p.tasaCotizada) * 100)),
    };
  }).sort((a, b) => a.desviacionPP - b.desviacionPP);
}

export function estancados(pipeline = PIPELINE, hoy = HOY) {
  return pipeline.filter((p) => estancado(p, hoy)).sort((a, b) => diasEnEtapa(b, hoy) - diasEnEtapa(a, hoy));
}

// Periodo: últimos 90 días contra los 90 anteriores.
export function comparativoPeriodo(pipeline = PIPELINE, hoy = HOY, ventana = 90) {
  const fin = t(hoy), corte = fin - ventana * MS_DIA, inicio = fin - 2 * ventana * MS_DIA;
  const en = (iso, a, b) => iso && t(iso) > a && t(iso) <= b;
  const bloque = (a, b) => ({
    nuevos: pipeline.filter((p) => en(p.fechas.prospecto, a, b)).length,
    propuestas: pipeline.filter((p) => en(p.fechas.propuesta, a, b)).length,
    cierres: pipeline.filter((p) => en(p.fechas.escriturado, a, b)).length,
    colocado: pipeline.filter((p) => en(p.fechas.escriturado, a, b)).reduce((s, p) => s + (p.montoFinal || 0), 0),
  });
  return { actual: bloque(corte, fin), previo: bloque(inicio, corte) };
}

export const ETIQUETA_ETAPA = {
  prospecto: "Prospecto", escenario: "Escenario", propuesta: "Propuesta",
  documentacion: "Documentación", aprobado: "Aprobado", escriturado: "Escriturado", perdido: "Perdido",
};

export const ETIQUETA_SUBTIPO = {
  adquisicion: "Adquisición", sustitucion: "Sustitución", liquidez: "Liquidez",
  terreno: "Terreno", construccion: "Construcción", "terreno-construccion": "Terreno y construcción",
};

export function etiquetaTipo(p) {
  if (p.familia === "pyme") return "PyME";
  return "Hipotecario · " + (ETIQUETA_SUBTIPO[p.subtipo] || p.subtipo);
}
