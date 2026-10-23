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
from motor_hipotecario.comparador import (
    VERSION_MOTOR,
    ResultadoOpcion,
    comparar,
    primer_pago_por_defecto,
)
from motor_hipotecario.modelos import Cofinanciamiento, Escenario, ProductoHipotecario

from .esquemas import (
    CatalogoSalida,
    EscalonSalida,
    ComparacionSalida,
    EscenarioEntrada,
    OpcionSalida,
    ProductoSalida,
    ReglaAportacionesSalida,
    RenglonSalida,
)

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
        tasa_anual=_tasa(p.tasa_anual),
        tasa_normalizada=_tasa(tasa_normalizada(p)),
        convencion_interes=p.convencion_interes.value,
        convencion_pago=(p.convencion_pago or p.convencion_interes).value,
        convencion_amortizacion=(p.convencion_amortizacion or p.convencion_interes).value,
        seguros_en_pago_fijo=p.seguros_en_pago_fijo,
        crecimiento_pago_anual=_tasa(p.crecimiento_pago_anual),
        tasas_escalonadas=[
            EscalonSalida(desde_mes=desde, tasa_anual=_tasa(tasa))
            for desde, tasa in p.tasas_escalonadas
        ],
        recalcular_pago_al_cambiar_tasa=p.recalcular_pago_al_cambiar_tasa,
        regla_aportaciones=_regla(p),
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


def _opcion(o: ResultadoOpcion, escenario: Escenario) -> OpcionSalida:
    t = o.tabla
    return OpcionSalida(
        producto_id=o.producto.id,
        elegible=o.elegible,
        motivos_rechazo=list(o.motivos_rechazo),
        advertencias=list(o.advertencias),
        monto_credito=_dinero(o.monto_credito),
        aforo=_tasa(escenario.aforo),
        plazo_calculado_meses=t.plazo_meses,
        plazo_efectivo_meses=t.plazo_efectivo_meses,
        comision_apertura=_dinero(o.comision_apertura),
        avaluo=_dinero(o.avaluo),
        gastos_notariales=_dinero(o.gastos_notariales),
        cat_estimado=_tasa(o.cat_estimado),
        pago_primer_mes=_dinero(o.pago_primer_mes),
        pago_ultimo_mes=_dinero(o.pago_ultimo_mes),
        total_intereses=_dinero(o.total_intereses),
        total_seguros=_dinero(o.total_seguros),
        total_comision_mensual=_dinero(t.total_comision_mensual),
        total_aportaciones=_dinero(t.total_aportaciones),
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
    return CatalogoSalida(productos=[_producto(p) for p in CATALOGO if p.vigente_en(hoy)])


@app.post("/api/comparar", response_model=ComparacionSalida)
def comparar_escenario(entrada: EscenarioEntrada) -> ComparacionSalida:
    escenario = Escenario(
        valor_vivienda=entrada.valor_vivienda,
        enganche=entrada.enganche,
        plazo_meses=entrada.plazo_meses,
        gastos_notariales=entrada.gastos_notariales,
        ingreso_mensual=entrada.ingreso_mensual,
        factor_pago_ingreso=entrada.factor_pago_ingreso,
        fecha_primer_pago=entrada.fecha_primer_pago,
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
        generado_en=resultado.snapshot.generado_en.isoformat(),
        fecha_primer_pago=(
            escenario.fecha_primer_pago or primer_pago_por_defecto(resultado.snapshot.generado_en)
        ).isoformat(),
        opciones=[_opcion(o, escenario) for o in opciones],
    )
