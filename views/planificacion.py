import streamlit as st
import pandas as pd
from utils.helpers import safe_date
from core.app_context import (
    get_pedidos,
    get_pedidos_map
)
from utils.date_utils import safe_format

def render_planificacion():

    st.header("🟧 Planificación")

    pedidos = get_pedidos()
    pedidos_map = {p["id"]: p for p in pedidos}
    # =======================
    # CONTROL OPERATIVO (SIN C)
    # =======================
    sin_c = [
        p for p in pedidos
        if str(p.get("carga", "")).strip().upper() != "C"
        and p.get("estado") in ["comercial", "planificacion"]
    ]

    
    st.metric("📌 Pendientes sin confirmación (sin C)", len(sin_c))

    with st.expander("📋 Ver pedidos pendientes"):
        if sin_c:
            for p in sin_c:
                st.write(
                    f"📦 {p.get('id')} | "
                    f"👤 {p.get('cliente')} | "
                    f"👨‍💼 {p.get('representante')} | "
                    f"📅 {safe_date(p.get('fecha_cliente'))}"
                )
        else:
            st.write("No hay pedidos pendientes sin confirmación de carga.")

    st.divider()

    # =======================
    # SELECCIÓN PEDIDO (PERSISTENTE)
    # =======================
    col1, col2 = st.columns(2)

    ids = [p["id"] for p in pedidos]

    # Sincronizar selección global
    pedido_default = st.session_state.get("pedido_activo")

    if pedido_default in ids:
        index_default = ids.index(pedido_default)
    else:
        index_default = 0

    pedido_sel = col1.selectbox(
        "Selecciona pedido",
        ids,
        index=index_default
    )

    st.session_state["pedido_activo"] = pedido_sel

    # Búsqueda rápida
    busqueda = col2.text_input("Buscar pedido")

    if busqueda:
        coincidencias = [
            p for p in pedidos
            if busqueda.lower() in str(p.get("id", "")).lower()
        ]
        if coincidencias:
            pedido_sel = coincidencias[0]["id"]
            st.session_state["pedido_activo"] = pedido_sel
            
    # =======================
    # OBTENER PEDIDO ACTIVO
    # =======================
    pedido = pedidos_map.get(pedido_sel)

    if not pedido:
        st.warning("Pedido no encontrado")
        st.stop()

    lineas = pedido.get("lineas", [])

    if not lineas:
        st.warning("Este pedido no tiene líneas")
        st.stop()

   
    # =======================
    # VISTA Y EDITOR (SIN COLUMNA CARGA)
    # =======================
    st.subheader("📊 Tabla de planificación")

    df_lineas = pd.DataFrame(lineas)
    df_view = df_lineas.copy()

    # 🔥 Forzamos que las columnas existan en la tabla con el dato del ERP antes de formatear
    if "fecha_entrada" not in df_view.columns:
        df_view["fecha_entrada"] = pedido.get("fecha_entrada")
    if "fecha_calculada" not in df_view.columns:
        df_view["fecha_calculada"] = pedido.get("fecha_calculada")

    # Asegurar que las columnas de fecha sean datetime para el editor
    for col in [
        "fecha_entrada",
        "fecha_calculada",
        "fecha_compromiso",
        "fecha_carga"
    ]:
        if col in df_view.columns:
            df_view[col] = pd.to_datetime(
                df_view[col],
                dayfirst=True,
                errors="coerce"
            ).dt.date
    
    df_view["fecha_cliente"] = pd.to_datetime(
        pedido.get("fecha_cliente"),
        errors="coerce"
    ).date()

    # Eliminamos la columna "carga" solo de la vista visual del DataFrame
    if "carga" in df_view.columns:
        df_view = df_view.drop(columns=["carga"], errors="ignore")

    # Renderizamos la tabla ya limpia
    st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # =======================
    # DETALLE INFORMATIVO
    # =======================
    st.divider()
    st.subheader("📋 Detalle del pedido")
    colD1, colD2, colD3 = st.columns(3)

    with colD1:
        st.write(f"👤 Cliente: {pedido.get('cliente','-')}")
        st.write(f"👨‍💼 Representante: {pedido.get('representante','-')}")
        st.write(f"👨‍💼 Referencia: {pedido.get('referencia','-')}")

    with colD2:
        st.write(f"📅 Fecha cliente: {safe_date(pedido.get('fecha_cliente'))}")

    with colD3:
        ultima = pedido.get("ultima_actualizacion_planificacion")
        origen_cambio = pedido.get("origen_ultimo_cambio", "Importación TXT") # Por si manejas el origen

        st.markdown("##### ⏱️ Estado del Registro")
        if ultima is None:
            st.caption("🕒 Sin modificaciones manuales recientes.")
        else:
            try:
                fecha_formateada = pd.to_datetime(ultima).strftime('%d/%m/%Y %H:%M')
                st.write(f"**🕒 Último cambio:** {fecha_formateada}")
                
                # Un aviso visual según quién cambió el dato por última vez
                if "comercial" in str(origen_cambio).lower():
                    st.warning("⚠️ Modificado por Comercial")
                else:
                    st.info("💾 Actualizado por el sistema / Planificación")
            except:
                st.write("🕒 Última act: -")