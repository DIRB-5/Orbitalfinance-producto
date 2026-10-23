// Pipeline de prospectos.
//
// Esquema de cada tupla:
// [id, asesorId, cliente, familia, subtipo, monto, etapa, fechas,
//  motivoPerdida, perdidoEn, institucionFinal, tasaCotizada, tasaFinal,
//  montoFinal, divergenciaPesos]
//
// "fechas" es "etapa:AAAA-MM-DD|etapa:AAAA-MM-DD|..." en orden de avance.

export const ASESORES = [
  { id: "ase-1", nombre: "Asesor",        rol: "asesor",        activo: true },
  { id: "adm-1", nombre: "Administrador", rol: "administrador", activo: true },
];

export const ETAPAS = [
  "prospecto", "escenario", "propuesta", "documentacion", "aprobado", "escriturado",
];

export const MOTIVOS_PERDIDA = [
  "No calificó (ingresos o historial)",
  "Eligió otro broker",
  "Desistió de la compra",
  "Condiciones no competitivas",
  "Documentación incompleta",
  "Sin respuesta del cliente",
  "Otro",
];

// Vacío: los prospectos se capturan en la plataforma.
const CRUDO = [];

export const PIPELINE = CRUDO.map(([
  id, asesorId, cliente, familia, subtipo, monto, etapa, fechas,
  motivoPerdida, perdidoEn, institucionFinal, tasaCotizada, tasaFinal,
  montoFinal, divergenciaPesos,
]) => ({
  id, asesorId, cliente, familia, subtipo, monto, etapa,
  fechas: Object.fromEntries(
    fechas.split("|").map((p) => p.split(":"))
  ),
  motivoPerdida, perdidoEn, institucionFinal,
  tasaCotizada, tasaFinal, montoFinal,
  divergencia: divergenciaPesos ? { diferencia: divergenciaPesos } : null,
}));
