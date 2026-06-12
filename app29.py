import streamlit as st
import pandas as pd
import os
import sqlite3
import json
import time

from datetime import datetime, timedelta
from collections import Counter
from config.settings import MAP, FILE_PATH, DB_PATH

from database.connection import get_conn
from database.init_db import init_db
from database.history import cargar_historial
from services.erp_loader import cargar_datos
from database.load_repo import cargar_pedidos_db

from services.pedidos_service import (
    generar_pedidos,
    merge_pedidos
)

from utils.helpers import (
    safe_date,
    parse_fecha,
    safe_first
)

from services.alertas_service import (
    marcar_alerta_leida,
    crear_alerta_manual,
    hay_cambios_erp,
    contar_alertas,
    alertas_activas,
    detectar_cambios_erp,
    construir_alertas_erp
)

from core.audit import registrar_cambio

from services.expedicion_service import (
    compromiso_confirmado,
    tiene_c,
    mostrar_fecha_compromiso,
    mostrar_fecha_carga,
    calcular_estado_expedicion
)

from views.dashboard_view import render_dashboard
from views.comercial import render_comercial
from views.planificacion import render_planificacion
from views.otc import render_otc
from views.expedicion import render_expedicion

from database.pedidos_repo import guardar_pedidos
from core.app_context import get_pedidos
from core.app_context import obtener_timestamp_alertas, notificar_alerta_global

# =========================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTADOS INICIALES
# =========================================================
st.set_page_config(layout="wide", page_title="KOXKA")

if "mi_timestamp_alertas" not in st.session_state:
    st.session_state["mi_timestamp_alertas"] = obtener_timestamp_alertas()
    st.session_state["last_known_alert_count"] = contar_alertas()

timestamp_servidor = obtener_timestamp_alertas()

if timestamp_servidor != st.session_state["mi_timestamp_alertas"]:
    st.session_state["mi_timestamp_alertas"] = timestamp_servidor
    st.session_state["last_known_alert_count"] = contar_alertas()
    
    st.cache_data.clear() 
    st.session_state["pedidos"] = None
    if "cache" in st.session_state:
        st.session_state["cache"].clear()
    st.rerun()

conteo_alertas_actual = int(st.session_state["last_known_alert_count"])
    
if "cache" not in st.session_state or "pedidos" not in st.session_state["cache"]:
    if "cache" not in st.session_state:
        st.session_state["cache"] = {}
    st.session_state["cache"]["pedidos"] = cargar_pedidos_db()

if "historial_cambios" not in st.session_state:
    st.session_state.historial_cambios = []

if "alertas_manual" not in st.session_state:
    st.session_state.alertas_manual = []

if "pedido_activo" not in st.session_state:
    st.session_state.pedido_activo = None

if "eventos" not in st.session_state:
    st.session_state.eventos = []

if "abrir_buzon" not in st.session_state:
    st.session_state.abrir_buzon = False

# =========================================================
# 2. INICIALIZAR EN DISCO
# =========================================================
init_db()
cargar_historial()

st.title("🏭 KOXKA")

# =========================================================
# 3. 🔥 BOTÓN MANUAL ACTUALIZAR ERP
# =========================================================
if st.button("🔄 Actualizar ERP", key="btn_update_erp_manual"):
    st.cache_data.clear()
    nuevo_mtime = os.path.getmtime(FILE_PATH) if os.path.exists(FILE_PATH) else 0

    df_fresco = cargar_datos(FILE_PATH, nuevo_mtime)
    nuevos_pedidos = generar_pedidos(df_fresco)
    viejos = get_pedidos()

    viejos_ids = {p["id"] for p in viejos}
    nuevos_ids = {p["id"] for p in nuevos_pedidos}
    pedidos_nuevos = nuevos_ids - viejos_ids

    if pedidos_nuevos or hay_cambios_erp(viejos, nuevos_pedidos):
        resumen_erp = detectar_cambios_erp(viejos, nuevos_pedidos)
        st.session_state["ultimo_resumen_erp"] = resumen_erp
        
        construir_alertas_erp(resumen_erp)

        # 🚀 REGISTRO EN HISTORIAL: Procesamos las modificaciones reales del botón manual
        for p_act in resumen_erp.get("actualizados", []):
            for cambio in p_act.get("cambios", []):
                registrar_cambio(
                    pedido_id=p_act["pedido"],
                    campo=cambio["campo"],
                    valor_anterior=str(cambio["antes"]).split(" ")[0],
                    valor_nuevo=str(cambio["despues"]).split(" ")[0],
                    origen="manual"
                )

        pedidos_mergeados = merge_pedidos(viejos, nuevos_pedidos)
        guardar_pedidos(pedidos_mergeados)

        st.session_state.last_mtime = nuevo_mtime
        st.session_state.df_cache = df_fresco

        if "cache" in st.session_state:
            st.session_state["cache"].pop("pedidos", None)
            st.session_state["cache"].pop("pedidos_map", None)
        else:
            st.session_state["cache"] = {}
        
        st.session_state["cache"]["pedidos"] = cargar_pedidos_db()
        st.session_state["dirty"] = False
        st.session_state["last_known_alert_count"] = contar_alertas()

        st.success("🔁 ERP actualizado con cambios en el sistema")
    else:
        st.info("ℹ️ Sin cambios en ERP, no se generaron alertas")
        
    st.rerun()

# =========================================================
# 4. CARGA AUTOMÁTICA POR CAMBIO EN DISCO
# =========================================================
mtime = os.path.getmtime(FILE_PATH) if os.path.exists(FILE_PATH) else 0

if "last_mtime" not in st.session_state:
    st.session_state["last_mtime"] = mtime
    df = cargar_datos(FILE_PATH, mtime)
    st.session_state.df_cache = df
else:
    df = st.session_state.df_cache

if mtime != st.session_state["last_mtime"]:
    st.cache_data.clear()
    st.session_state["last_mtime"] = mtime

    df = cargar_datos(FILE_PATH, mtime)
    st.session_state.df_cache = df
    
    nuevos_pedidos = generar_pedidos(df)
    viejos_auto = get_pedidos()
    resumen_erp = detectar_cambios_erp(viejos_auto, nuevos_pedidos)
    st.session_state["ultimo_resumen_erp"] = resumen_erp

    # 🚀 REGISTRO EN HISTORIAL: Procesamos las modificaciones reales del cambio automático en disco
    for p_act in resumen_erp.get("actualizados", []):
        for cambio in p_act.get("cambios", []):
            registrar_cambio(
                pedido_id=p_act["pedido"],
                campo=cambio["campo"],
                valor_anterior=str(cambio["antes"]).split(" ")[0],
                valor_nuevo=str(cambio["despues"]).split(" ")[0],
                origen="manual"
            )

    pedidos_mergeados = merge_pedidos(viejos_auto, nuevos_pedidos)
    guardar_pedidos(pedidos_mergeados)

    if "cache" in st.session_state:
        st.session_state["cache"].pop("pedidos", None)
        st.session_state["cache"].pop("pedidos_map", None)
    else:
        st.session_state["cache"] = {}
        
    st.session_state["cache"]["pedidos"] = cargar_pedidos_db()
    st.session_state["dirty"] = False
    
    construir_alertas_erp(resumen_erp)
    st.session_state["last_known_alert_count"] = int(contar_alertas())
    
    st.toast("🔁 El archivo ERP ha cambiado en el disco. Datos actualizados.", icon="🔄")
    st.rerun()

# =========================================================
# 5. MENÚ Y NAVEGACIÓN LATERAL
# =========================================================
menu_opciones = ["Dashboard", "Comercial", "Planificacion", "OTC", "Expedición", "Historial", "Buzón"]

if "menu" not in st.session_state:
    st.session_state["menu"] = "Dashboard"

if st.sidebar.button(f"📩 Buzón ({conteo_alertas_actual})", key="btn_buzon_sidebar"):
    st.session_state["menu"] = "Buzón"
    st.session_state["abrir_buzon"] = True
    st.rerun()

menu = st.sidebar.selectbox(
    "📌 Menú",
    menu_opciones,
    index=menu_opciones.index(st.session_state["menu"]),
    key="menu_select"
)
st.session_state["menu"] = menu
st.sidebar.divider()

# =========================================================
# 6. ESCUCHADOR PASIVO MULTIPANTALLA
# =========================================================
@st.fragment(run_every=1)
def ejecutar_escuchador_pasivo(timestamp_local):
    if st.session_state.get("dirty", False):
        return
        
    if obtener_timestamp_alertas() != timestamp_local:
        st.cache_data.clear()
        st.rerun()

if menu in ["Dashboard", "Buzón", "Planificacion", "Comercial", "OTC", "Expedición"]:
    if timestamp_servidor == st.session_state["mi_timestamp_alertas"]:
        ejecutajax = ejecutar_escuchador_pasivo(st.session_state["mi_timestamp_alertas"])

# =========================================================
# 7. INTERFAZ: BUZÓN DE NOTIFICACIONES
# =========================================================
if menu == "Buzón":
    st.header("📩 Buzón de notificaciones")
    alertas = alertas_activas()

    if not alertas:
        st.info("Sin notificaciones")
    else:
        if st.button("🧹 Marcar todas como leídas", use_container_width=True):
            conn = get_conn()
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE alertas_db SET estado = 'leido' WHERE estado != 'leido' OR estado IS NULL")
                conn.commit()
                notificar_alerta_global()
                st.session_state["pedidos"] = None
                st.session_state["mi_timestamp_alertas"] = obtener_timestamp_alertas()
                st.session_state["last_known_alert_count"] = 0
                st.success("¡Buzón vaciado correctamente!")
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"Error al vaciar el buzón: {e}")
            finally:
                conn.close()

        st.divider()

        for a in reversed(alertas):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"📦 {a.get('pedido')} | {a.get('mensaje')} | {a.get('tipo')}")
            with col2:
                alerta_id = a.get("id")
                if st.button("✔ Leído", key=f"read_{alerta_id}"):
                    marcar_alerta_leida(alerta_id)
                    st.session_state["pedidos"] = None
                    st.session_state["mi_timestamp_alertas"] = obtener_timestamp_alertas()
                    st.session_state["last_known_alert_count"] = contar_alertas() 
                    st.rerun()

# =========================================================
# 8. 📡 RECUADRO SIMULACIÓN BAAN (UPLOADER SIDEBAR)
# =========================================================
st.sidebar.subheader("📡 Simular Carga BAAN IV")

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

archivo_arrastrado = st.sidebar.file_uploader(
    "Arrastra aquí el reporte modificado (.txt)", 
    type=["txt"],
    key=f"txt_simulador_{st.session_state['uploader_key']}"
)

if archivo_arrastrado is not None:
    st.cache_data.clear()
    ruta_temporal = "simulacion_baan.txt"
    try:
        bytes_data = archivo_arrastrado.read()
        with open(ruta_temporal, "w", encoding="cp1252", errors="ignore") as f_temp:
            f_temp.write(bytes_data.decode("cp1252", errors="ignore"))
            
        df_fresco = cargar_datos.__wrapped__(ruta_temporal, time.time())
        nuevos_pedidos = generar_pedidos(df_fresco)
        
        # 🚨 SOLUCIÓN AL ESTANCAMIENTO: Traemos la foto más fresca de la BD justo en este milisegundo
        viejos = cargar_pedidos_db()

        viejos_ids = {p["id"] for p in viejos}
        nuevos_ids = {p["id"] for p in nuevos_pedidos}
        pedidos_nuevos = nuevos_ids - viejos_ids

        if pedidos_nuevos or hay_cambios_erp(viejos, nuevos_pedidos):
            resumen_erp = detectar_cambios_erp(viejos, nuevos_pedidos)
            st.session_state["ultimo_resumen_erp"] = resumen_erp
            
            construir_alertas_erp(resumen_erp)

            # =========================================================
            # 📜 INYECCIÓN DEL HISTORIAL PARA ARCHIVOS ARRASTRADOS
            # =========================================================
            # Aquí extraemos los cambios limpios del resumen real de KOXKA
            for p_act in resumen_erp.get("actualizados", []):
                pedido_id_cambio = p_act["pedido"]
                for cambio in p_act.get("cambios", []):
                    registrar_cambio(
                        pedido_id=pedido_id_cambio,
                        campo=cambio["campo"],
                        valor_anterior=str(cambio["antes"]).split(" ")[0],
                        valor_nuevo=str(cambio["despues"]).split(" ")[0],
                        origen="manual" # Vincula automáticamente Planificación u OTC según el campo
                    )

            pedidos_mergeados = merge_pedidos(viejos, nuevos_pedidos)
            guardar_pedidos(pedidos_mergeados)

            st.session_state.df_cache = df_fresco
            
            if "cache" in st.session_state:
                st.session_state["cache"].pop("pedidos", None)
                st.session_state["cache"].pop("pedidos_map", None)
            else:
                st.session_state["cache"] = {}
                
            st.session_state["cache"]["pedidos"] = cargar_pedidos_db()
            st.session_state["pedidos"] = st.session_state["cache"]["pedidos"]
            st.session_state["dirty"] = False
            st.session_state["last_known_alert_count"] = contar_alertas()
            
            notificar_alerta_global()
            st.sidebar.success("🔁 ¡Archivo procesado y grabado en Base de Datos!")
        else:
            st.sidebar.info("ℹ️ El archivo arrastrado no contiene cambios respecto a la BD")
            
    except Exception as e:
        st.sidebar.error(f"Error procesando la simulación: {e}")
    finally:
        if os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)
    
    st.session_state["uploader_key"] += 1
    time.sleep(0.5)
    st.rerun()

st.sidebar.divider()

# =========================================================
# 9. RENDERIZADO DE VISTAS OPERATIVAS
# =========================================================
if menu == "Dashboard":
    render_dashboard()

if menu == "Comercial":
    render_comercial()
            
if menu == "Planificacion":
    render_planificacion()

if menu == "OTC":
    render_otc()

if menu == "Expedición":
    render_expedicion()
    
# =========================================================
# 10. HISTORIAL DE AUDITORÍA
# =========================================================
if menu == "Historial":
    st.header("📜 Historial de Auditoría")
    st.info("Registro de movimientos y cambios de fechas realizados por los distintos departamentos.")

    conn = get_conn()
    query = "SELECT pedido, campo, antes, despues, origen, fecha FROM historial ORDER BY fecha DESC"
    try:
        df_hist = pd.read_sql_query(query, conn, parse_dates=None)
    finally:
        conn.close()

    if df_hist.empty:
        st.info("Aún no se han registrado cambios ni movimientos en el historial del sistema.")
    else:
        df_hist["fecha_dt"] = pd.to_datetime(df_hist["fecha"], errors='coerce')
        mask_nat = df_hist["fecha_dt"].isna()
        if mask_nat.any():
            df_hist.loc[mask_nat, "fecha_dt"] = pd.to_datetime(df_hist.loc[mask_nat, "fecha"], dayfirst=True, errors='coerce')

        df_hist = df_hist.sort_values("fecha_dt", ascending=False)

        with st.expander("🔍 Filtros de búsqueda", expanded=True):
            f1, f2, f3 = st.columns(3)
            filto_pedido = f1.text_input("📦 ID Pedido")
            orig_list = ["Todos"] + sorted(list(df_hist["origen"].unique().astype(str)))
            filtro_origen = f2.selectbox("📍 Origen del cambio", orig_list)
            filtro_campo = f3.text_input("📝 Campo modificado")

        if filto_pedido:
            df_hist = df_hist[df_hist["pedido"].astype(str).str.contains(filto_pedido, case=False)]
        if filtro_origen != "Todos":
            df_hist = df_hist[df_hist["origen"] == filtro_origen]
        if filtro_campo:
            df_hist = df_hist[df_hist["campo"].astype(str).str.contains(filtro_campo, case=False)]

        df_display = pd.DataFrame({
            "ID Pedido": df_hist["pedido"],
            "Campo Modificado": df_hist["campo"],
            "Valor Anterior": df_hist["antes"],
            "Valor Nuevo": df_hist["despues"],
            "Sección Origen": df_hist["origen"],
            "Fecha y Hora": df_hist["fecha_dt"].dt.strftime('%d/%m/%Y %H:%M:%S')
        })

        st.dataframe(df_display, use_container_width=True, hide_index=True)
        st.divider()
        st.subheader("📊 Actividad por departamento")
        st.bar_chart(df_display["Sección Origen"].value_counts())

        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar historial (CSV)",
            data=csv,
            file_name=f"historial_koxka_{datetime.now().strftime('%Y%m%d')}.csv",
            mime='text/csv',
        )
