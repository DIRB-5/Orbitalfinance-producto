"""
API del comparador. Capa delgada sobre el motor: traduce, redondea al
presentar y no hace aritmética financiera propia.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, HTTPException

from motor_hipotecario.amortizacion import redondear, tasa_normalizada
from motor_hipotecario.catalogo import CATALOGO
from motor_hipotecario.instituto import COFINAVIT
from motor_hipotecario.referencias import ESCENARIOS_TIIE, FUENTE_TIIE
from motor_hipotecario.comparador import (
    VERSION_MOTOR,
    ResultadoOpcion,
    comparar,
    primer_pago_por_defecto,
)
from motor_hipotecario.modelos import (
    Cofinanciamiento,
    CreditoActual,
    CreditoInstitutoActual,
    Escenario,
    ProductoHipotecario,
)

from .esquemas import (
    CatalogoSalida,
    ComparacionSalida,
    CreditoInstitutoSalida,
    EscalonSalida,
    EscenarioTasaSalida,
    FaseCrecimientoSalida,
    FinanciamientoGastosSalida,
    LineaGastosSalida,
    LineaInstitutoSalida,
    EscenarioEntrada,
    OpcionSalida,
    ProductoSalida,
    ReglaAportacionesSalida,
    RenglonSalida,
    TasaVariableSalida,
    TramoTasaSalida,
)

NOMBRES_ESCENARIO = {"conservador": "Conservador", "base": "Base", "estres": "Estrés"}

app = FastAPI(title="Comparador hipotecario", version=VERSION_MOTOR)

PRECISION_TASA = Decimal("1E-10")


def _dinero(valor: Decimal) -> str:
    return str(redondear(valor))


def _dinero_opcional(valor: Optional[Decimal]) -> Optional[str]:
    return None if valor is None else _dinero(valor)


def _tasa(valor: Decimal) -> str:
    return str(valor.quantize(PRECISION_TASA).normalize())


def _regla(p: ProductoHipotecario) -> Optional[ReglaAportacionesSalida]:
    r = p.regla_aportaciones
    if r is None:
        return None
    return ReglaAportacionesSalida(
        instituto=r.instituto.value,
        porcentaje_salario=_tasa(r.porcentaje_salario),
        tope=_dinero_opcional(r.tope),
        incremento_anual=_tasa(r.incremento_anual),
        mes_inicio=r.mes_inicio,
        cada_meses=r.cada_meses,
        excedente=r.excedente.value,
    )


def _producto(p: ProductoHipotecario) -> ProductoSalida:
    return ProductoSalida(
        id=p.id,
        institucion=p.institucion,
        nombre=p.nombre,
        tipo=p.tipo.value,
        destino=p.destino.value,
        tasa_anual=_tasa(p.tasa_anual),
        tasa_normalizada=_tasa(tasa_normalizada(p)),
        convencion_interes=p.convencion_interes.value,
        convencion_pago=(p.convencion_pago or p.convencion_interes).value,
        convencion_amortizacion=(p.convencion_amortizacion or p.convencion_interes).value,
        seguros_en_pago_fijo=p.seguros_en_pago_fijo,
        crecimiento_pago_mensual=[
            FaseCrecimientoSalida(desde_mes=desde, crecimiento_mensual=_tasa(g))
            for desde, g in p.crecimiento_pago_mensual
        ],
        factores_al_millar_anuales=[str(f) for f in p.factores_al_millar_anuales],
        crecimiento_pago_anual=(
            _tasa(p.crecimiento_pago_anual) if p.crecimiento_pago_anual else None
        ),
        tasas_escalonadas=[
            EscalonSalida(desde_mes=desde, tasa_anual=_tasa(tasa))
            for desde, tasa in p.tasas_escalonadas
        ],
        recalcular_pago_al_cambiar_tasa=p.recalcular_pago_al_cambiar_tasa,
        regla_aportaciones=_regla(p),
        financiamiento_gastos=(
            FinanciamientoGastosSalida(
                tope=_tasa(p.financiamiento_gastos.tope) if p.financiamiento_gastos.tope else None,
                base_tope=p.financiamiento_gastos.base_tope.value,
                apertura_y_aforo_sobre_total=p.financiamiento_gastos.apertura_y_aforo_sobre_total,
                incluye_apertura_y_avaluo=p.financiamiento_gastos.incluye_apertura_y_avaluo,
                linea_separada=p.financiamiento_gastos.linea_separada,
            )
            if p.financiamiento_gastos
            else None
        ),
        acepta_garantia_adicional=p.acepta_garantia_adicional,
        dictamen_tecnico_pct=_tasa(p.dictamen_tecnico_pct),
        dictamen_tecnico_minimo=_dinero(p.dictamen_tecnico_minimo),
        dictamen_tecnico_maximo=_dinero_opcional(p.dictamen_tecnico_maximo),
        requiere_cofinanciamiento=p.requiere_cofinanciamiento,
        dia_de_pago=p.dia_de_pago,
        primer_periodo_dias_reales=p.primer_periodo_dias_reales,
        tasa_variable=(
            TasaVariableSalida(
                desde_mes=p.tasa_variable.desde_mes,
                referencia=p.tasa_variable.referencia,
                sobretasa=_tasa(p.tasa_variable.sobretasa),
                techo=_tasa(p.tasa_variable.techo) if p.tasa_variable.techo is not None else None,
            )
            if p.tasa_variable is not None
            else None
        ),
        tabla_tasas=[
            TramoTasaSalida(plazo_max_meses=pl, aforo_max=_tasa(af), tasa_anual=_tasa(t))
            for pl, af, t in p.tabla_tasas
        ],
        tiene_tarifa_avaluo=bool(p.tarifa_avaluo),
        valor_minimo_inmueble=_dinero_opcional(p.valor_minimo_inmueble),
        plazos_meses=list(p.plazos_meses),
        aforo_max=_tasa(p.aforo_max),
        comision_apertura=_tasa(p.comision_apertura),
        comision_apertura_monto=_dinero_opcional(p.comision_apertura_monto),
        comision_mensual=_dinero(p.comision_mensual),
        seguro_vida_mensual=_tasa(p.seguro_vida_mensual),
        seguro_danos_anual=_tasa(p.seguro_danos_anual),
        seguro_danos_monto_mensual=_dinero_opcional(p.seguro_danos_monto_mensual),
        base_seguro_danos=p.base_seguro_danos.value,
        factor_construccion=_tasa(p.factor_construccion),
        avaluo=_dinero(p.avaluo),
        cat_netos_de_iva=sorted(c.value for c in p.cat_netos_de_iva),
        monto_minimo=_dinero_opcional(p.monto_minimo),
        monto_maximo=_dinero_opcional(p.monto_maximo),
        vigente_desde=p.vigente_desde.isoformat(),
        vigente_hasta=p.vigente_hasta.isoformat() if p.vigente_hasta else None,
        fuente=p.fuente,
        notas=p.notas,
        negociado_por=p.negociado_por,
    )


def _credito_actual(c) -> CreditoActual:
    datos = c.model_dump(exclude={"credito_instituto"})
    instituto = None
    if c.credito_instituto is not None:
        instituto = CreditoInstitutoActual(**c.credito_instituto.model_dump())
    return CreditoActual(**datos, credito_instituto=instituto)


def _linea_instituto(o: ResultadoOpcion) -> Optional[LineaInstitutoSalida]:
    t = o.tabla_instituto_refinanciado
    if t is None:
        return None
    return LineaInstitutoSalida(
        instituto=o.credito_actual.credito_instituto.instituto.value,
        monto=_dinero(t.monto),
        tasa_anual=_tasa(t.tasa_anual),
        pago_mensual=_dinero(t.pago_regular_inicial),
        total_pagado=_dinero(t.total_pagado),
        total_intereses=_dinero(t.total_intereses),
        cat_estimado=_tasa(o.cat_instituto_refinanciado_estimado),
    )


def _linea_gastos(o: ResultadoOpcion) -> Optional[LineaGastosSalida]:
    t = o.tabla_gastos
    if t is None:
        return None
    return LineaGastosSalida(
        monto=_dinero(t.monto),
        tasa_anual=_tasa(t.tasa_anual),
        pago_mensual=_dinero(t.pago_regular_inicial),
        total_pagado=_dinero(t.total_pagado),
        total_intereses=_dinero(t.total_intereses),
        total_iva_intereses=_dinero(sum((r.iva_intereses for r in t.renglones), Decimal("0"))),
        cat_estimado=_tasa(o.cat_gastos_estimado),
    )


def _credito_instituto(o: ResultadoOpcion) -> Optional[CreditoInstitutoSalida]:
    t = o.tabla_instituto
    if t is None:
        return None
    return CreditoInstitutoSalida(
        instituto=COFINAVIT.instituto.value,
        producto=COFINAVIT.producto,
        monto=_dinero(t.monto),
        tasa_anual=_tasa(t.tasa_anual),
        pago_mensual=_dinero(t.primer_pago),
        plazo_efectivo_meses=t.plazo_efectivo_meses,
        total_pagado=_dinero(t.total_pagado),
        total_aportaciones=_dinero(t.total_aportaciones),
        fuente=COFINAVIT.fuente,
    )


def _opcion(o: ResultadoOpcion, escenario: Escenario) -> OpcionSalida:
    t = o.tabla
    return OpcionSalida(
        producto_id=o.producto.id,
        tasa_variable=o.producto.tasa_variable is not None,
        alternativa_sin_cofinanciamiento=o.alternativa_sin_cofinanciamiento,
        tasa_anual=_tasa(o.producto.tasa_anual),
        tasa_normalizada=_tasa(tasa_normalizada(o.producto)),
        elegible=o.elegible,
        motivos_rechazo=list(o.motivos_rechazo),
        advertencias=list(o.advertencias),
        monto_credito=_dinero(o.monto_credito),
        aforo=_tasa(escenario.aforo),
        plazo_calculado_meses=t.plazo_meses,
        plazo_efectivo_meses=t.plazo_efectivo_meses,
        comision_apertura=_dinero(o.comision_apertura),
        comision_investigacion=_dinero(o.comision_investigacion),
        dictamen_tecnico=_dinero(o.dictamen_tecnico),
        avaluo=_dinero(o.avaluo),
        gastos_notariales=_dinero(o.gastos_notariales),
        gastos_financiados=_dinero(o.gastos_financiados),
        gastos_de_contado=_dinero(o.gastos_de_contado),
        linea_gastos=_linea_gastos(o),
        linea_instituto=_linea_instituto(o),
        cat_estimado=_tasa(o.cat_estimado),
        pago_primer_mes=_dinero(o.pago_primer_mes),
        pago_ultimo_mes=_dinero(o.pago_ultimo_mes),
        pago_regular_inicial=_dinero(o.pago_regular_inicial),
        pago_regular_final=_dinero(o.pago_regular_final),
        primer_pago_irregular=t.primer_renglon_irregular,
        dias_primer_periodo=t.dias_primer_periodo,
        total_intereses=_dinero(o.total_intereses),
        total_seguros=_dinero(o.total_seguros),
        total_comision_mensual=_dinero(t.total_comision_mensual),
        total_aportaciones=_dinero(o.total_aportaciones),
        credito_instituto=_credito_instituto(o),
        costo_de_cambiarse=_dinero_opcional(o.costo_de_cambiarse),
        ahorro_mensual=_dinero_opcional(o.ahorro_mensual),
        punto_equilibrio_mes=o.punto_equilibrio_mes,
        ahorro_neto=_dinero_opcional(o.ahorro_neto),
        serie_ahorro=[_dinero(a) for a in o.serie_ahorro],
        suma_mensualidades=_dinero(t.total_pagado),
        costo_total=_dinero(o.costo_total),
        costo_financiero=_dinero(o.costo_financiero),
        desembolso_inicial=_dinero(o.desembolso_inicial),
        tabla=[
            RenglonSalida(
                mes=r.mes,
                fecha_pago=r.fecha_pago.isoformat() if r.fecha_pago else None,
                saldo_inicial=_dinero(r.saldo_inicial),
                interes=_dinero(r.interes),
                capital=_dinero(r.capital),
                seguro_vida=_dinero(r.seguro_vida),
                seguro_danos=_dinero(r.seguro_danos),
                comision_mensual=_dinero(r.comision_mensual),
                aportacion=_dinero(r.aportacion),
                seguro_desempleo=_dinero(r.seguro_desempleo),
                iva_intereses=_dinero(r.iva_intereses),
                pago_total=_dinero(r.pago_total),
                saldo_final=_dinero(r.saldo_final),
            )
            for r in t.renglones
        ],
    )


@app.get("/api/salud")
def salud() -> dict:
    return {"estado": "ok", "versionMotor": VERSION_MOTOR}


@app.get("/api/catalogo", response_model=CatalogoSalida)
def catalogo() -> CatalogoSalida:
    hoy = date.today()
    return CatalogoSalida(
        productos=[_producto(p) for p in CATALOGO if p.vigente_en(hoy)],
        escenarios_tiie=[
            EscenarioTasaSalida(id=k, nombre=NOMBRES_ESCENARIO[k], tiie=_tasa(v))
            for k, v in ESCENARIOS_TIIE.items()
        ],
        fuente_tiie=FUENTE_TIIE,
    )


@app.post("/api/comparar", response_model=ComparacionSalida)
def comparar_escenario(entrada: EscenarioEntrada) -> ComparacionSalida:
    escenario = Escenario(
        valor_vivienda=entrada.valor_vivienda,
        enganche=entrada.enganche,
        plazo_meses=entrada.plazo_meses,
        gastos_notariales=entrada.gastos_notariales,
        financiar_gastos_notariales=entrada.financiar_gastos_notariales,
        valor_garantia_adicional=entrada.valor_garantia_adicional,
        ingreso_mensual=entrada.ingreso_mensual,
        factor_pago_ingreso=entrada.factor_pago_ingreso,
        fecha_primer_pago=entrada.fecha_primer_pago,
        fecha_disposicion=entrada.fecha_disposicion,
        tiie=ESCENARIOS_TIIE[entrada.escenario_tasa],
        destino=entrada.destino,
        credito_actual=(
            _credito_actual(entrada.credito_actual) if entrada.credito_actual else None
        ),
        cofinanciamiento=(
            Cofinanciamiento(**entrada.cofinanciamiento.model_dump())
            if entrada.cofinanciamiento
            else None
        ),
    )
    try:
        resultado = comparar(escenario, CATALOGO)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    # Orden por defecto: costo total; las no elegibles al final, con su motivo.
    opciones = sorted(resultado.opciones, key=lambda o: (not o.elegible, o.costo_total))
    return ComparacionSalida(
        version_motor=resultado.snapshot.version_motor,
        escenario_tasa=entrada.escenario_tasa,
        tiie=_tasa(escenario.tiie),
        generado_en=resultado.snapshot.generado_en.isoformat(),
        fecha_primer_pago=(
            escenario.fecha_primer_pago or primer_pago_por_defecto(resultado.snapshot.generado_en)
        ).isoformat(),
        opciones=[_opcion(o, escenario) for o in opciones],
    )
