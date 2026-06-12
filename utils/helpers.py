import pandas as pd
from datetime import datetime

from utils.date_utils import (
    to_datetime_safe,
    to_date_safe,
    format_date
)


def safe_date(x):
    """
    Formato seguro visual
    """
    return format_date(x)


def mostrar_fecha_compromiso(p):

    fecha = (
        p.get("fecha_compromiso")
        or p.get("fecha_cliente")
    )

    return format_date(fecha)


def mostrar_fecha_carga(p):

    fecha = p.get("fecha_carga")

    return format_date(fecha)


def parse_fecha(x):

    return to_datetime_safe(x)


def safe_first(grupo, col):

    if col in grupo.columns and not grupo[col].dropna().empty:
        return grupo[col].dropna().iloc[0]

    return "-"


def solo_fecha(valor):

    return to_date_safe(valor)


def normalize_fecha(value):

    return to_datetime_safe(value)