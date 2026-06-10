import pandas as pd
from datetime import datetime


def to_datetime_safe(value):
    if value is None or pd.isna(value):
        return None

    # Si ya es un objeto datetime o Timestamp, lo convertimos directamente sin formatear texto
    if isinstance(value, (datetime, pd.Timestamp)):
        return pd.to_datetime(value).to_pydatetime()

    value = str(value).strip()
    if value in ["", "-", "nan", "None"]:
        return None

    try:
        # Usamos dayfirst=True para que Pandas sepa que el primer número es el DÍA ante la ambigüedad
        dt = pd.to_datetime(value, dayfirst=True, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.to_pydatetime()
    except:
        return None
def to_date_safe(value):
    """
    Convierte a date() seguro
    """

    dt = to_datetime_safe(value)

    if dt is None:
        return None

    return dt.date()


def format_date(value):

    dt = pd.to_datetime(value, errors="coerce")

    if pd.isna(dt):
        return "-"

    return dt.strftime("%d/%m/%Y")


def format_datetime(value):
    """
    Fecha + hora visual
    """

    dt = to_datetime_safe(value)

    if dt is None:
        return "-"

    return dt.strftime("%d/%m/%Y %H:%M")


def to_iso(value):
    """
    Formato para guardar en DB
    """

    dt = to_datetime_safe(value)

    if dt is None:
        return None

    return dt.isoformat()

def to_db_date(value):
    """
    Convierte cualquier fecha a formato SQLite:
    YYYY-MM-DD
    """

    import pandas as pd

    dt = pd.to_datetime(value, errors="coerce")

    if pd.isna(dt):
        return None

    return dt.strftime("%Y-%m-%d")



def safe_format(value, fmt="%d/%m/%Y %H:%M"):

    if value is None or pd.isna(value):
        return "-"

    try:
        dt = pd.to_datetime(value, errors="coerce")

        if pd.isna(dt):
            return "-"

        return dt.strftime(fmt)

    except:
        return "-"