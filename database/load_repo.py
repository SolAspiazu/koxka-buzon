import sqlite3
import json
import pandas as pd
from config.settings import DB_PATH


def from_db_date(value):
    if not value:
        return None
    return pd.to_datetime(value, errors="coerce")


def deserialize_pedido(p):

    # =========================
    # FECHAS NIVEL TOP (Cabecera)
    # =========================
    for k in [
        "fecha_entrada",      # <-- Agregada aquí que faltaba
        "fecha_cliente",
        "fecha_compromiso",
        "fecha_calculada",
        "fecha_carga",
        "ultima_actualizacion",
        "fecha_salida_real"
    ]:
        if k in p:
            p[k] = from_db_date(p[k])

    # =========================
    # LINEAS (Detalle)
    # =========================
    if "lineas" in p and isinstance(p["lineas"], list):
        for l in p["lineas"]:
            for k in [
                "fecha_entrada",      
                "fecha_calculada",    
                "fecha_compromiso",
                "fecha_carga"
            ]:
                if k in l:
                    l[k] = from_db_date(l[k])
                else:
                    # 🔥 Si la línea no tiene la fecha, la hereda de la cabecera del ERP
                    l[k] = p.get(k)

    return p


def cargar_pedidos_db():

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT data FROM pedidos")

    rows = c.fetchall()
    conn.close()

    pedidos = []

    for r in rows:

        pedido = json.loads(r[0])

        pedidos.append(deserialize_pedido(pedido))

    return pedidos