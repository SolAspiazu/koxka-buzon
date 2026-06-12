import pandas as pd
from datetime import datetime

# 1. NORMALIZACIÓN (TODO entra aquí)
def to_datetime(value):
    if value is None or pd.isna(value):
        return None

    if isinstance(value, datetime):
        return value

    dt = pd.to_datetime(value, errors="coerce")

    return None if pd.isna(dt) else dt.to_pydatetime()


# 2. FORMATO UI (solo presentación)
def to_ui(value):
    dt = to_datetime(value)

    if not dt:
        return "-"

    return dt.strftime("%d/%m/%Y %H:%M")


# 3. FORMATO BASE PARA BD/API
def to_iso(value):
    dt = to_datetime(value)

    if not dt:
        return None

    return dt.isoformat()