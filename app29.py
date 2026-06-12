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
from core.app_context import get_pedidos, obtener_timestamp_alertas, notificar_alerta_global

# =========================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTADOS INICIALES
# =========================================================
st.set_page_config(layout="wide", page_title="KOXKA")

# Inicializar Base de Datos e Historial de manera segura
init_db()
cargar_historial()

# Inicializamos el rastro del timbre en esta pestaña del navegador
if "mi_timestamp_alertas" not in st.session_state:
    st.session_state["mi_timestamp_alertas"] = obtener_timestamp_alertas()
    st.session_state["last_known_alert_count"] = contar_alertas()

# ⚡ COMPROBACIÓN REACIVA MULTIPANTALLA
timestamp_servidor = obtener_timestamp_alertas()

if timestamp_servidor != st.session_state["mi_timestamp_alertas"]:
    st.session_state["mi_timestamp_alertas"] = timestamp_servidor
    st.session_state["last_known_alert_count"] = contar_alertas()
    
    st.cache_data.clear() 
    st.session_state["pedidos"] = None
    if "cache" in st.session_state:
        st.session_state["cache"].clear()
    st.rerun()

# Conteo limpio para la interfaz
conteo_alertas_actual = int(st.session_state["last_known_alert_count"])
    
# 🚨 UNIFICACIÓN DE CACHÉ: Forzar que todo use el repositorio central de app_context
if "pedidos" not in st.session_state or st.session_state["pedidos"] is None:
    st.session_state["pedidos"] = cargar_pedidos_db()

if "cache" not in st.session_state:
    st.session_state["cache"] = {}
st.session_state["cache"]["pedidos"] = st.session_state["pedidos"]

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
# 5. LOGICA DE CARGA Y ACTUALIZACIÓN ERP
# =========================================================
st.title("🏭 KOXKA")

# Mostrar resumen si existe en la sesión
resumen = st.session_state.get("ultimo_resumen_erp")
if resumen:
    nuevos = resumen.get("nuevos", [])
    actualizados = resumen.get("actualizados", [])

    if nuevos or actualizados:
        st.subheader("📡 Cambios detectados en ERP")

    if nuevos:
        st.success(f"🆕 Pedidos nuevos: {len(nuevos)}")
        for n in nuevos:
            st.write(f"📦 {n['pedido']} | 👤 {n['cliente']}")

    if actualizados:
        st.warning(f"🔄 Pedidos actualizados: {len(actualizados)}")
        for p in actualizados:
            st.markdown(f"### 📦 Pedido {p['pedido']}")
            for c in p["cambios"]:
                st.write(f"• {c['campo']}: {safe_date(c['antes'])} → {safe_date(c['despues'])}")

# =========================================================
# 🔥 BOTÓN MANUAL CORREGIDO Y BLINDADO
# =========================================================
if st.button("🔄 Actualizar ERP", key="btn_update_erp_manual"):
    st.cache_data.clear()
    nuevo_mtime = os.path.getmtime(FILE_PATH) if os.path.exists(FILE_PATH) else 0

    df_fresco = cargar_datos(FILE_PATH, nuevo_mtime)
    nuevos_pedidos = generar_pedidos(df_fresco)
    viejos = cargar_pedidos_db()  # Forzamos lectura directa para comparar limpio

    viejos_ids = {p["id"] for p in viejos}
    nuevos_ids = {p["id"] for p in nuevos_pedidos}
    pedidos_nuevos = nuevos_ids - viejos_ids

    if pedidos_nuevos or hay_cambios_erp(viejos, nuevos_pedidos):
        resumen_erp = detectar_cambios_erp(viejos, nuevos_pedidos)
        st.session_state["ultimo_resumen_erp"] = resumen_erp
        
        construir_alertas_erp(resumen_erp)

        pedidos_mergeados = merge_pedidos(viejos, nuevos_pedidos)
        guardar_pedidos(pedidos_mergeados)  # Guardado físico real sin asignaciones erróneas

        st.session_state.last_mtime = nuevo_mtime
        st.session_state.df_cache = df_fresco

        # Purgamos las cachés cruzadas por completo para forzar recarga remota
        st.session_state["pedidos"] = None
        if "cache" in st.session_state:
            st.session_state["cache"].clear()
        
        st.session_state["cache"]["pedidos"] = cargar_pedidos_db()
        st.session_state["pedidos"] = st.session_state["cache"]["pedidos"]
        st.session_state["dirty"] = False
        
        notificar_alerta_global()  # Tocamos el timbre eléctrico de la fábrica
        st.session_state["last_known_alert_count"] = contar_alertas()

        st.success("🔁 ERP actualizado con cambios en el sistema")
    else:
        st.info("ℹ️ Sin cambios en ERP, no se generaron alertas")
        
    st.rerun()


# =========================================================
# CARGA AUTOMÁTICA / DETECCIÓN DE CAMBIOS EN DISCO
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
    viejos_db = cargar_pedidos_db()
    
    resumen_erp = detectar_cambios_erp(viejos_db, nuevos_pedidos)
    st.session_state["ultimo_resumen_erp"] = resumen_erp

    pedidos_mergeados = merge_pedidos(viejos_db, nuevos_pedidos)
    guardar_pedidos(pedidos_mergeados)

    st.session_state["pedidos"] = None
    if "cache" in st.session_state:
        st.session_state["cache"].clear()
        
    st.session_state["cache"]["pedidos"] = cargar_pedidos_db()
    st.session_state["pedidos"] = st.session_state["cache"]["pedidos"]
    st.session_state["dirty"] = False
    
    construir_alertas_erp(resumen_erp)
    notificar_alerta_global()
    st.session_state["last_known_alert_count"] = int(contar_alertas())
    
    st.toast("🔁 El archivo ERP ha cambiado en el disco. Datos actualizados.", icon="🔄")
    st.rerun()

# =========================================================
# 6. MENÚ Y NAVEGACIÓN
# =========================================================
menu_opciones = ["Dashboard", "Comercial", "Planificacion", "OTC", "Expedición", "Historial", "Buzón"]

if "menu" not in st.session_state:
    st.session_state["menu"] = "Dashboard"

if st.sidebar.button(f"📩 Buzón ({conteo_alertas_actual})", key="btn_buzon_sidebar"):
    st.session_state["menu"] = "Buzón"
    st.session_state["abrir_buzon"] = True
    st.rerun()

menu = st.sidebar.selectbox("📌 Menú", menu_opciones, index=menu_opciones.index(st.session_state["menu"]), key="menu_select")
st.session_state["menu"] = menu
st.sidebar.divider()

# Escuchador pasivo en segundo plano
@st.fragment(run_every=1)
def ejecutar_escuchador_pasivo(timestamp_local):
    if st.session_state.get("dirty", False):
        return
    if obtener_timestamp_alertas() != timestamp_local:
        st.cache_data.clear()
        st.rerun()

if menu in ["Dashboard", "Buzón", "Planificacion", "Comercial", "OTC", "Expedición"]:
    if timestamp_servidor == st.session_state["mi_timestamp_alertas"]:
        ejecutar_escuchador_pasivo(st.session_state["mi_timestamp_alertas"])

# =========================================================
# VISTA: BUZÓN
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

        for i, a in enumerate(reversed(alertas)):
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

# Renderizado de vistas estándar
if menu == "Dashboard": render_dashboard()
if menu == "Comercial": render_comercial()
if menu == "Planificacion": render_planificacion()
if menu == "OTC": render_otc()
if menu == "Expedición": render_expedicion()
    
# =========================================================
# VISTA: HISTORIAL (CON BLINDAJE DE PARSEO DE FECHAS)
# =========================================================
if menu == "Historial":
    st.header("📜 Historial de Auditoría")
    st.info("Registro de movimientos y cambios de fechas realizados por los distintos departamentos.")

    conn = get_conn()
    query = "SELECT pedido, campo, antes, despues, origen, fecha FROM historial ORDER BY fecha DESC"
    try:
        df_hist = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    if df_hist.empty:
        st.info("Aún no se han registrado cambios ni movimientos en el historial del sistema.")
    else:
        # 🚨 PARSEO BLINDADO DEL TIMESTAMPS MODIFICADO: Evitamos desajustes por formato europeo/ISO
        df_hist["fecha_dt"] = pd.to_datetime(df_hist["fecha"], dayfirst=True, errors='coerce')

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

        # Asegurar formato de visualización limpio sin romper si falla el parseo de horas
        df_display = pd.DataFrame({
            "ID Pedido": df_hist["pedido"],
            "Campo Modificado": df_hist["campo"],
            "Valor Anterior": df_hist["antes"],
            "Valor Nuevo": df_hist["despues"],
            "Sección Origen": df_hist["origen"],
            "Fecha y Hora": df_hist["fecha_dt"].dt.strftime('%d/%m/%Y %H:%M:%S').fillna(df_hist["fecha"])
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
