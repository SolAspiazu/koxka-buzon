import pandas as pd
from datetime import datetime, timedelta

from config.settings import MAP
from utils.helpers import safe_first

from database.connection import get_conn
from core.audit import registrar_cambio
from utils.calendario import calcular_fecha_carga
from utils.helpers import normalize_fecha

def filtrar_por_anio(df, col_fecha, anio=2026):
    df[col_fecha] = pd.to_datetime(df[col_fecha], dayfirst=True, errors="coerce")
    return df[df[col_fecha].dt.year == anio]

def generar_pedidos(df):
    if df is None or df.empty:
        return []

    pedidos = []

    pedido_col = f"col_{MAP['pedido']}"
    df[pedido_col] = df[pedido_col].astype(str).str.strip()

    # Filtrar basura una sola vez
    df = df[
        (df[pedido_col] != "")
        & (df[pedido_col].str.lower() != "pedido")
        & (df[pedido_col] != "nan")
    ]

    # Preparseo de fechas seguro
    def fast_parse(col):
        if col in df.columns:
            return df[col].apply(normalize_fecha)
        return pd.Series(None, index=df.index)

    df["_fecha_entrada"] = fast_parse(f"col_{MAP['fecha_entrada']}")
    df["_fecha_calculada"] = fast_parse(f"col_{MAP['fecha_calculada']}")
    df["_fecha_compromiso"] = fast_parse(f"col_{MAP['fecha_compromiso']}")
    df["_fecha_requerida"] = fast_parse(f"col_{MAP['fecha_requerida']}")

    # =====================================================
    # FILTRO FLEXIBLE: Evitamos tirar filas si falla el parseo inicial
    # =====================================================
    col_req_original = f"col_{MAP['fecha_requerida']}"
    if col_req_original in df.columns:
        df = df[df[col_req_original].astype(str).str.strip() != ""]

    for pedido_id, grupo in df.groupby(pedido_col, sort=False):
        pedido_id = str(pedido_id).strip()

        if not pedido_id or pedido_id.lower() == "nan":
            continue

        lineas = []
        records = grupo.to_dict("records")

        for row in records:
            fecha_compromiso_linea = row["_fecha_compromiso"]
            fecha_carga_linea = calcular_fecha_carga(fecha_compromiso_linea)

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

        # =====================================================
        # 🚨 EXTRACCIÓN ULTRA-SEGURA DE FECHAS (Doble comprobación)
        # =====================================================
        
        # 1. FECHA CLIENTE (Si falla la columna parseada, extraemos de la columna original del MAP)
        fechas_cliente_grupo = grupo["_fecha_requerida"].dropna()
        if not fechas_cliente_grupo.empty:
            fecha_cliente_final = fechas_cliente_grupo.max()
        else:
            # Plan B: Leer directo de la columna original del excel/txt
            col_raw = f"col_{MAP['fecha_requerida']}"
            raw_vals = grupo[col_raw].dropna() if col_raw in grupo.columns else pd.Series()
            fecha_cliente_final = raw_vals.max() if not raw_vals.empty else None

        # 2. FECHA COMPROMISO
        fechas_compromiso = grupo["_fecha_compromiso"].dropna()
        if not fechas_compromiso.empty:
            fecha_compromiso = fechas_compromiso.max()
        else:
            col_raw = f"col_{MAP['fecha_compromiso']}"
            raw_vals = grupo[col_raw].dropna() if col_raw in grupo.columns else pd.Series()
            fecha_compromiso = raw_vals.max() if not raw_vals.empty else None

        # 3. FECHA CALCULADA
        fechas_calculadas = grupo["_fecha_calculada"].dropna()
        if not fechas_calculadas.empty:
            fecha_calculada = fechas_calculadas.max()
        else:
            col_raw = f"col_{MAP['fecha_calculada']}"
            raw_vals = grupo[col_raw].dropna() if col_raw in grupo.columns else pd.Series()
            fecha_calculada = raw_vals.max() if not raw_vals.empty else None

        # 4. FECHA ENTRADA GENERAL
        fechas_entrada = grupo["_fecha_entrada"].dropna()
        if not fechas_entrada.empty:
            fecha_entrada_general = fechas_entrada.max()
        else:
            col_raw = f"col_{MAP['fecha_entrada']}"
            raw_vals = grupo[col_raw].dropna() if col_raw in grupo.columns else pd.Series()
            fecha_entrada_general = raw_vals.max() if not raw_vals.empty else None

        # Calcular fecha de carga final basada en el compromiso obtenido
        fecha_carga = calcular_fecha_carga(fecha_compromiso)

        # =====================================================
        # CONSTRUCCIÓN DEL DICCIONARIO FINAL
        # =====================================================
        pedidos.append({
            "id": pedido_id,
            "cliente": safe_first(grupo, f"col_{MAP['cliente']}"),
            "referencia": safe_first(grupo, f"col_{MAP['referencia']}"),
            "representante": safe_first(grupo, f"col_{MAP['representante']}"),
            "carga": safe_first(grupo, f"col_{MAP['carga']}"),
            
            "fecha_entrada": normalize_fecha(fecha_entrada_general),  
            "fecha_cliente": normalize_fecha(fecha_cliente_final),  
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
    Regla KOXKA Corregida de manera Quirúrgica: 
    Se rompe el bloqueo de 'fecha_compromiso' para que las actualizaciones sucesivas 
    de fechas (ej. de 14 a 15) se pisen correctamente y salten de forma secuencial.
    """
    mapa_viejos = {p["id"]: p for p in viejos}
    resultado = []

    for nuevo in nuevos_pedidos:
        pedido_id = nuevo["id"]
        viejo = mapa_viejos.get(pedido_id)

        if viejo:
            # =============================================================
            # 1. RETENER PARAMETRIZACIONES PROPIAS DE LA SESIÓN DE LA APP
            # =============================================================
            nuevo["cambio_comercial"] = viejo.get("cambio_comercial", False)
            
            # Conservar estados y alertas internas de la app
            if "alertas_manuales" in viejo:
                nuevo["alertas_manuales"] = viejo["alertas_manuales"]

            # =============================================================
            # 2. INDEPENDENCIA Y PRIORIDAD ABSOLUTA PARA LAS FECHAS DEL ERP
            # =============================================================
            
            # 🔥 CORRECCIÓN CRÍTICA: Liberamos fecha_compromiso para romper el bucle histórico
            if str(viejo.get("fecha_compromiso")) != str(nuevo.get("fecha_compromiso")):
                registrar_cambio(
                    pedido_id, 
                    "fecha_compromiso", 
                    viejo.get("fecha_compromiso"), 
                    nuevo.get("fecha_compromiso"), 
                    "erp_update"
                )
                # Forzamos que se recalcule de forma exacta la fecha de carga según el valor fresco
                nuevo["fecha_carga"] = calcular_fecha_carga(nuevo.get("fecha_compromiso"))
            else:
                # Si no varió en el txt, retenemos el valor que ya teníamos guardado
                nuevo["fecha_compromiso"] = viejo.get("fecha_compromiso")
                nuevo["fecha_carga"] = viejo.get("fecha_carga")

            # A) Corregir y auditar FECHA CLIENTE
            if str(viejo.get("fecha_cliente")) != str(nuevo.get("fecha_cliente")):
                registrar_cambio(
                    pedido_id, 
                    "fecha_cliente", 
                    viejo.get("fecha_cliente"), 
                    nuevo.get("fecha_cliente"), 
                    "erp_update"
                )

            # B) Corregir y auditar FECHA DE ENTRADA
            if str(viejo.get("fecha_entrada")) != str(nuevo.get("fecha_entrada")):
                registrar_cambio(
                    pedido_id, 
                    "fecha_entrada", 
                    viejo.get("fecha_entrada"), 
                    nuevo.get("fecha_entrada"), 
                    "erp_update"
                )

            # C) Corregir y auditar FECHA CALCULADA
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

            # Recalcular el KPI de días de retraso de forma segura
            fc = pd.to_datetime(nuevo.get("fecha_cliente"), errors="coerce")
            fcomp = pd.to_datetime(nuevo.get("fecha_compromiso"), errors="coerce")
            if pd.notnull(fc) and pd.notnull(fcomp):
                nuevo["dias_retraso"] = (fcomp - fc).days
            else:
                nuevo["dias_retraso"] = viejo.get("dias_retraso", 0)

        resultado.append(nuevo)

    return resultado
