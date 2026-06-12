from utils.date_utils import (
    format_date,
    to_date_safe
)


def safe_date(x):

    return format_date(x)


def tiene_c(pedido):

    return str(
        pedido.get("carga", "")
    ).strip().upper() == "C"


def mostrar_fecha_compromiso(pedido):

    if not tiene_c(pedido):
        return "🟡 PENDIENTE"

    fecha = pedido.get("fecha_compromiso")

    fecha_ok = to_date_safe(fecha)

    return fecha_ok if fecha_ok else "🟡 PENDIENTE"


def mostrar_fecha_carga(pedido):

    if not tiene_c(pedido):
        return "🟡 PENDIENTE"

    fecha = pedido.get("fecha_carga")

    fecha_ok = to_date_safe(fecha)

    return fecha_ok if fecha_ok else "🟡 PENDIENTE"