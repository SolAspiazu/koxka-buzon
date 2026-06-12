from datetime import datetime, timedelta
import pandas as pd

from core.audit import registrar_cambio
# 🔄 Cambiamos crear_alerta_manual por crear_alerta
from services.alertas_service import crear_alerta 

from utils.calendario import calcular_fecha_carga


def validar_pedido_otc(p):

    base = p.get("fecha_compromiso") or p.get("fecha_cliente")
    base_dt = pd.to_datetime(base, errors="coerce")

    if pd.notnull(base_dt):
        nueva_carga = calcular_fecha_carga(base_dt)
              
    else:
        nueva_carga = None

    # AUDITORÍA
    registrar_cambio(
        p.get("id"),
        "fecha_carga",
        p.get("fecha_carga"),
        nueva_carga,
        "otc"
    )

    registrar_cambio(
        p.get("id"),
        "estado",
        "otc",
        "carga",
        "otc"
    )

    # ACTUALIZACIÓN
    p["fecha_carga"] = nueva_carga
    p["estado"] = "carga"

    # 🔥 ALERTA ÚNICA CORREGIDA: Guarda en BD con tipo "otc" para el Dashboard y el Buzón
    crear_alerta(
        pedido=p["id"],
        mensaje="OTC validó compromiso",
        tipo="otc"
    )

    # FLAGS
    p["cambio_comercial"] = False
    p["pendiente_otc"] = False
    p["compromiso_otc_actualizado"] = True

    p["fecha_compromiso_anterior"] = p.get("fecha_compromiso")
    p["fecha_compromiso"] = base_dt

    p["fecha_comunicacion_otc"] = datetime.now().replace(microsecond=0)

    p["ultima_actualizacion"] = datetime.now().replace(microsecond=0)

    return p


def devolver_a_comercial(p):

    registrar_cambio(
        p.get("id"),
        "estado",
        "otc",
        "comercial",
        "otc"
    )

    p["estado"] = "comercial"

    p["cambio_comercial"] = False
    p["pendiente_otc"] = False

    p["ultima_actualizacion"] = datetime.now().replace(microsecond=0)

    return p
