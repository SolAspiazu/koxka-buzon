import os
from datetime import datetime
import pandas as pd

CARPETA_SALIDA = "salida_baan"

os.makedirs(CARPETA_SALIDA, exist_ok=True)


def generar_txt_baan(
    pedido,
    accion,
    fecha_anterior,
    fecha_nueva
):

    pedido_id = pedido.get("id")

    ruta = os.path.join(
        CARPETA_SALIDA,
        "OUTBOX_BAAN.txt"
    )

    lineas = []

    # =========================================
    # FORMATEAR FECHAS
    # =========================================

    fecha_old = (
        pd.to_datetime(fecha_anterior)
        .strftime("%d/%m/%Y")
        if pd.notnull(fecha_anterior)
        else ""
    )

    fecha_new = (
        pd.to_datetime(fecha_nueva)
        .strftime("%d/%m/%Y")
        if pd.notnull(fecha_nueva)
        else ""
    )

    # =========================================
    # GENERAR UNA LINEA POR POSICIÓN
    # =========================================

    for l in pedido.get("lineas", []):

        posicion = l.get("posicion", "")

        linea = (
            f"{pedido_id}|"
            f"{posicion}|"
            f"{accion}|"
            f"{fecha_old}|"
            f"{fecha_new}"
        )

        lineas.append(linea)

    # =========================================
    # ESCRIBIR TXT
    # =========================================

    with open(ruta, "a", encoding="utf-8") as f:

        for linea in lineas:

            f.write(linea + "\n")

    return ruta