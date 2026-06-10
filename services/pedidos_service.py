import pandas as pd

from datetime import datetime, timedelta

from config.settings import MAP
from utils.helpers import safe_first

from database.connection import get_conn

from core.audit import registrar_cambio

from utils.calendario import calcular_fecha_carga

from utils.helpers import normalize_fecha

def filtrar_por_anio(df, col_fecha, anio=2026):
    # CORREGIDO: Añadido dayfirst=True para evitar la conversión americana al arrancar
    df[col_fecha] = pd.to_datetime(df[col_fecha], dayfirst=True, errors="coerce")
    return df[df[col_fecha].dt.year == anio]

def generar_pedidos(df):
    if df is None or df.empty:
        return []

    pedidos = []

    pedido_col = f"col_{MAP['pedido']}"
    df[pedido_col] = df[pedido_col].astype(str).str.strip()

    # 🔥 filtrar basura una sola vez
    df = df[
        (df[pedido_col] != "")
        & (df[pedido_col].str.lower() != "pedido")
        & (df[pedido_col] != "nan")
    ]

    # 🔥 preparseo de fechas UNA SOLA VEZ (gran mejora de velocidad)
    def fast_parse(col):
        return df[col].apply(normalize_fecha)

    df["_fecha_entrada"] = fast_parse(f"col_{MAP['fecha_entrada']}")
    df["_fecha_calculada"] = fast_parse(f"col_{MAP['fecha_calculada']}")
    df["_fecha_compromiso"] = fast_parse(f"col_{MAP['fecha_compromiso']}")
    df["_fecha_requerida"] = fast_parse(f"col_{MAP['fecha_requerida']}")


    # =====================================================
    # FILTRO: SOLO 2026 EN ADELANTE
    # =====================================================
    df = df[
        df["_fecha_requerida"].notna()
        & (df["_fecha_requerida"] >= pd.Timestamp("2026-01-01"))
    ]

    for pedido_id, grupo in df.groupby(pedido_col, sort=False):

        pedido_id = str(pedido_id).strip()

        if not pedido_id or pedido_id.lower() == "nan":
            continue

        lineas = []

        records = grupo.to_dict("records")

        for row in records:

            fecha_compromiso_linea = row["_fecha_compromiso"]

            fecha_carga_linea = calcular_fecha_carga(
                fecha_compromiso_linea
            )

            lineas.append({
                "linea": row[f"col_{MAP['linea']}"],
                "posicion": row[f"col_{MAP['posicion']}"],
                "cantidad": row[f"col_{MAP['cantidad']}"],
                "maquina": row[f"col_{MAP['maquina']}"],
                "carga": str(row.get(f"col_{MAP['carga']}", "")).strip().upper(),
                "fecha_entrada": normalize_fecha(row["_fecha_entrada"]),
                "fecha_calculada": normalize_fecha(row["_fecha_calculada"]),
                "fecha_compromiso": normalize_fecha(fecha_compromiso_linea),
                "fecha_carga": normalize_fecha(fecha_carga_linea)
            })

        fecha_cliente = grupo["_fecha_requerida"].dropna()
        fecha_cliente = fecha_cliente.max() if not fecha_cliente.empty else None

        fechas_compromiso = grupo["_fecha_compromiso"].dropna()
        fecha_compromiso = fechas_compromiso.max() if not fechas_compromiso.empty else None

        fechas_calculadas = grupo["_fecha_calculada"].dropna()
        fecha_calculada = fechas_calculadas.max() if not fechas_calculadas.empty else None

        fecha_carga = calcular_fecha_carga(
            fecha_compromiso
        )

        pedidos.append({
            "id": pedido_id,
            "cliente": safe_first(grupo, f"col_{MAP['cliente']}"),
            "referencia": safe_first(grupo, f"col_{MAP['referencia']}"),
            "representante": safe_first(grupo, f"col_{MAP['representante']}"),
            "carga": safe_first(grupo, f"col_{MAP['carga']}"),
            "fecha_cliente": normalize_fecha(fecha_cliente),
            "fecha_compromiso": normalize_fecha(fecha_compromiso),
            "fecha_calculada": normalize_fecha(fecha_calculada),
            "fecha_carga": normalize_fecha(fecha_carga),
            "estado": "comercial",
            "lineas": lineas,
            "estado_expedicion": "sin_definir",
            "ultima_actualizacion": datetime.now().replace(microsecond=0)
        })

    return pedidos



def merge_pedidos(viejos, nuevos_pedidos):
    """
    Regla KOXKA Corregida: 
    Forzar la actualización independiente de 'fecha_entrada', 'fecha_calculada' 
    y 'fecha_cliente' cuando cambien en el archivo .txt. 
    El resto de campos se mantienen según su lógica actual.
    """
    mapa_viejos = {p["id"]: p for p in viejos}
    resultado = []

    for nuevo in nuevos_pedidos:
        pedido_id = nuevo["id"]
        viejo = mapa_viejos.get(pedido_id)

        if viejo:
            # =============================================================
            # 1. RETENER LÓGICA EXISTENTE PARA LAS DEMÁS FECHAS DE FABRICACIÓN
            # =============================================================
            # 🔥 QUITAMOS EL TAPÓN DE FECHA_CLIENTE: El .txt ahora tiene prioridad absoluta.
            nuevo["cambio_comercial"] = viejo.get("cambio_comercial", False)
            nuevo["fecha_compromiso"] = viejo.get("fecha_compromiso", nuevo.get("fecha_compromiso"))
            nuevo["fecha_carga"] = viejo.get("fecha_carga", nuevo.get("fecha_carga"))
            
            # Conservar estados y alertas internas de la app
            if "alertas_manuales" in viejo:
                nuevo["alertas_manuales"] = viejo["alertas_manuales"]

            # =============================================================
            # 2. INDEPENDENCIA Y PRIORIDAD ABSOLUTA PARA LAS FECHAS DEL ERP
            # =============================================================
            
            # A) Corregir y auditar FECHA CLIENTE si el .txt trae un cambio fresco
            if str(viejo.get("fecha_cliente")) != str(nuevo.get("fecha_cliente")):
                registrar_cambio(
                    pedido_id, 
                    "fecha_cliente", 
                    viejo.get("fecha_cliente"), 
                    nuevo.get("fecha_cliente"), 
                    "erp_update"
                )
                # El objeto 'nuevo' ya conserva por defecto el valor fresco del .txt

            # B) Corregir y auditar FECHA DE ENTRADA si el .txt trae un cambio
            if str(viejo.get("fecha_entrada")) != str(nuevo.get("fecha_entrada")):
                registrar_cambio(
                    pedido_id, 
                    "fecha_entrada", 
                    viejo.get("fecha_entrada"), 
                    nuevo.get("fecha_entrada"), 
                    "erp_update"
                )

            # C) Corregir y auditar FECHA CALCULADA si el .txt trae un cambio
            if str(viejo.get("fecha_calculada")) != str(nuevo.get("fecha_calculada")):
                registrar_cambio(
                    pedido_id, 
                    "fecha_calculada", 
                    viejo.get("fecha_calculada"), 
                    nuevo.get("fecha_calculada"), 
                    "erp_update"
                )

            # =============================================================
            # 3. MANTENER ACTUALIZACIÓN DE OTROS CAMPOS ESTÁNDAR
            # =============================================================
            if str(viejo.get("carga")).strip().upper() != str(nuevo.get("carga")).strip().upper():
                registrar_cambio(pedido_id, "carga", viejo.get("carga"), nuevo.get("carga"), "erp_update")

            # Recalcular el KPI de días de retraso de forma segura (normalizando con pd.to_datetime)
            fc = pd.to_datetime(nuevo.get("fecha_cliente"), errors="coerce")
            fcomp = pd.to_datetime(nuevo.get("fecha_compromiso"), errors="coerce")
            if pd.notnull(fc) and pd.notnull(fcomp):
                nuevo["dias_retraso"] = (fcomp - fc).days
            else:
                nuevo["dias_retraso"] = viejo.get("dias_retraso", 0)

        resultado.append(nuevo)

    return resultado