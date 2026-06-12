import pandas as pd

from utils.helpers import to_datetime_safe


def compromiso_confirmado(pedido):
    return str(pedido.get("carga", "")).strip().upper() == "C"


def tiene_c(pedido):
    return str(pedido.get("carga", "")).strip().upper() == "C"

def mostrar_fecha_compromiso(pedido):
    if not tiene_c(pedido):
        return "🟡 PENDIENTE"

    fecha = pd.to_datetime(
        pedido.get("fecha_compromiso"),
        errors="coerce"
    )

    return fecha.date() if pd.notnull(fecha) else "🟡 PENDIENTE"

def mostrar_fecha_carga(pedido):
    if not tiene_c(pedido):
        return "🟡 PENDIENTE"

    fecha = pd.to_datetime(
        pedido.get("fecha_carga"),
        errors="coerce"
    )

    return fecha.date() if pd.notnull(fecha) else "🟡 PENDIENTE"

def safe_to_date(value):
    value = pd.to_datetime(value, errors="coerce")
    if pd.isna(value):
        return None
    return value.date()


def calcular_estado_expedicion(p, hoy):

    fecha_carga = p.get("fecha_carga")

    carga_ok = str(p.get("carga", "")).strip().upper() == "C"

    # 1. NO CONFIRMADO
    if not carga_ok:
        return "no_confirmado"

    # 2. SIN FECHA
    if pd.isna(fecha_carga):
        return "incidencia"

    # 3. YA DESPACHADO
    if p.get("estado_expedicion") == "despachado_confirmado":
        return "despachado_confirmado"
    
    fc = safe_to_date(fecha_carga)
    fh = safe_to_date(hoy)

    # 4. FUTURO
    if fc and fc > fh:
        return "programado"

    # 5. HOY

    fc = to_datetime_safe(fecha_carga)
    h = to_datetime_safe(hoy)
    if fc and h and fc.date() == h.date(): 
        return "en_preparacion"

    # 6. ATRASADO
    if safe_to_date(fecha_carga) and safe_to_date(hoy):

        if safe_to_date(fecha_carga) < safe_to_date(hoy):
            return "retrasado"

    return "incidencia"

from datetime import datetime

from core.audit import registrar_cambio
from services.alertas_service import crear_alerta_manual


def confirmar_salida(pedido):

    viejo_estado = pedido.get("estado_expedicion")

    pedido["estado_expedicion"] = "despachado_confirmado"

    pedido["fecha_salida_real"] = datetime.now()

    registrar_cambio(
        pedido["id"],
        "estado_expedicion",
        viejo_estado,
        "despachado_confirmado",
        "expedicion"
    )

    crear_alerta_manual(
        "expedicion",
        pedido["id"],
        "🚚 Pedido despachado y confirmado en logística"
    )

    return pedido


def obtener_pedidos_expedicion(pedidos):

    return [
        p for p in pedidos
        if p.get("estado_expedicion") in [
            "programado",
            "en_preparacion",
            "retrasado"
        ]
    ]


def obtener_despachados(pedidos):

    return [
        p for p in pedidos
        if p.get("estado_expedicion") == "despachado_confirmado"
    ]