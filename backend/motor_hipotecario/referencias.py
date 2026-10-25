"""
Tasas de referencia para productos de tasa variable.

Los escenarios de TIIE son SUPUESTOS para comparar, no pronósticos.

Fuentes (consultadas 2026-10-24):
  - TIIE a 28 días 6.7760 %, determinada el 22/10/2026, DOF 23/10/2026
    (https://dof.gob.mx/nota_detalle.php?codigo=5802010&fecha=23/10/2026).
  - TIIE de Fondeo 6.52 % (DOF 23/10/2026); tasa objetivo 6.50 % desde el
    7/05/2026, mantenida el 24/09/2026.
  - Encuesta Banxico de expectativas, septiembre 2026 (publicada 1/10/2026):
    tasa de fondeo esperada 6.50 % (mediana) hasta 2028-III, rango 5.75 % a
    7.25 %.

Escenarios: base = TIIE 28 vigente; conservador y estrés = mínimo y máximo de
la encuesta más el diferencial observado TIIE 28 − TIIE de Fondeo (~0.25).
El estrés es el rango de los analistas, NO un extremo histórico (en 2023 la
TIIE superó 11 %); el techo de 15 % del 7x5 solo opera con TIIE > 10.5 %.

OJO: desde el 1/01/2025 los contratos nuevos no pueden referenciar la TIIE a
28 días (Banxico, Circular 3/2023, DOF 13/04/2023); usan TIIE de Fondeo u otra
tasa permitida. La TIIE 28 sigue publicándose para contratos anteriores.
"""

from __future__ import annotations

from decimal import Decimal

TIIE_BASE = Decimal("0.067760")
ESCENARIOS_TIIE = {
    "conservador": Decimal("0.0600"),
    "base": TIIE_BASE,
    "estres": Decimal("0.0750"),
}
FUENTE_TIIE = (
    "TIIE 28 días 6.7760 % (DOF 23/10/2026). Conservador y estrés: rango 5.75 %–7.25 % "
    "de la Encuesta Banxico de septiembre 2026 más el diferencial TIIE 28 − Fondeo. "
    "Es el rango de los analistas, no un extremo histórico."
)
