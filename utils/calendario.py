import pandas as pd
import holidays
from datetime import timedelta

# Festivos España
es_holidays = holidays.Spain()


def es_dia_habil(fecha):
    fecha = pd.to_datetime(fecha).date()

    # fin de semana
    if fecha.weekday() >= 5:
        return False

    # festivo
    if fecha in es_holidays:
        return False

    return True


def sumar_dias_habiles(fecha, dias=1):
    fecha = pd.to_datetime(fecha)

    while dias > 0:
        fecha += timedelta(days=1)

        if es_dia_habil(fecha):
            dias -= 1

    return fecha


def calcular_fecha_carga(fecha_compromiso):
    if fecha_compromiso is None or pd.isna(fecha_compromiso):
        return None

    fecha_compromiso = pd.to_datetime(fecha_compromiso)

    return sumar_dias_habiles(fecha_compromiso, 1)
