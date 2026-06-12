from datetime import datetime
import streamlit as st


def crear_alerta_manual(tipo, pedido, mensaje):

    alert_id = f"manual_{tipo}_{pedido}_{datetime.now().timestamp()}"

    if "alertas_manual" not in st.session_state:
        st.session_state.alertas_manual = []

    st.session_state.alertas_manual.append({
        "id": alert_id,
        "tipo": tipo,
        "pedido": pedido,
        "mensaje": mensaje,
        "estado": "activa",
        "timestamp": datetime.now().replace(microsecond=0)
    })