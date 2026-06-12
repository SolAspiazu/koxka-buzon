import streamlit as st
import pandas as pd

from utils.helpers import safe_date
from services.alertas_service import alertas_activas

from core.app_context import get_pedidos


def render_dashboard():

    st.subheader("📊 Resumen general del sistema")

    pedidos = get_pedidos()

    if not pedidos:
        st.info("No hay pedidos cargados aún")
        st.stop()

    # =========================
    # KPI
    # =========================
    sin_c = [p for p in pedidos if str(p.get("carga", "")).strip().upper() != "C"]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("🟦 Comercial", len([p for p in pedidos if p.get("estado") == "comercial"]))
    col2.metric("🟧 Planificacion", len([p for p in pedidos if p.get("estado") == "planificacion"]), f"{len(sin_c)} sin C")
    col3.metric("🟨 OTC", len([p for p in pedidos if p.get("estado") == "otc"]))
    col4.metric("🟩 Expedición", len([p for p in pedidos if p.get("estado") in ["carga", "enviado"]]))

    st.divider()

    # =========================
    # ALERTAS DEL SISTEMA (CORREGIDO)
    # =========================
    st.subheader("📢 Alertas del sistema")

    alertas = alertas_activas()

    alert_comercial = []
    alert_planificacion = []
    alert_otc = []
    alert_expedicion = []

    # =========================================================
    # CLASIFICACIÓN ÚNICA (DETECTA "OTC" Y "VALIDÓ COMPROMISO")
    # =========================================================
    for a in alertas:
        id_pedido = a.get('pedido', '-')
        txt_mensaje = str(a.get('mensaje', '')).strip()
        
        mensaje = f"📦 Pedido {id_pedido} → {txt_mensaje}"
        
        tipo_alerta = str(a.get("tipo", "")).strip().lower()
        mensaje_lower = txt_mensaje.lower()

        if tipo_alerta == "otc" or "otc" in mensaje_lower or "validó compromiso" in mensaje_lower:
            alert_otc.append(mensaje)

        elif tipo_alerta == "comercial":
            alert_comercial.append(mensaje)

        elif tipo_alerta in ["planeación", "planeacion", "planificacion"]:
            alert_planificacion.append(mensaje)

        elif tipo_alerta in ["expedicion", "expedición"]:
            alert_expedicion.append(mensaje)

    # =========================
    # UI FINAL
    # =========================
    colA, colB, colC, colD = st.columns(4)

    with colA:
        st.markdown("### 🟦 Comercial")
        if alert_comercial:
            for a in alert_comercial:
                st.warning(a)
        else:
            st.info("Sin alertas")

    with colB:
        st.markdown("### 🟧 Planificación")
        if alert_planificacion:
            for a in alert_planificacion:
                st.warning(a)
        else:
            st.info("Sin alertas")

    with colC:
        st.markdown("### 🟨 OTC")
        if alert_otc:
            for a in alert_otc:
                st.warning(a)
        else:
            st.info("Sin alertas")

    with colD:
        st.markdown("### 🟩 Expedición")
        if alert_expedicion:
            for a in alert_expedicion:
                st.success(a)
        else:
            st.info("Sin alertas")

    st.divider()

    # =========================
    # TABLA GENERAL
    # =========================
    st.subheader("📋 Vista general de pedidos")

    filas = []
    for p in pedidos:
        filas.append({
            "Pedido": p.get("id", "-"),
            "Referencia": p.get("referencia", "-"),
            "Cliente": p.get("cliente", "-"),
            "Representante": p.get("representante", "-"),
            "Fecha cliente": safe_date(p.get("fecha_cliente")),
            "Estado": p.get("estado", "-")
        })

    if filas:
        st.dataframe(pd.DataFrame(filas), use_container_width=True)
