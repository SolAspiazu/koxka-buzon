import streamlit as st
import pandas as pd

from database.pedidos_repo import guardar_pedidos

from services.alertas_service import crear_alerta_manual
from core.audit import registrar_cambio
from datetime import datetime
from config.settings import MAP
from utils.formatters import (
    safe_date,
    mostrar_fecha_compromiso,
    mostrar_fecha_carga
)

from services.export_baan import generar_txt_baan

from utils.helpers import to_datetime_safe

from core.app_context import (
    update_pedido,
    save_if_needed
)
from core.app_context import (
    get_pedidos,
    get_pedidos_map
)
def safe_date_input_value(value):
    value = pd.to_datetime(value, errors="coerce")
    if pd.isna(value):
        return datetime.today().date()
    return value.date()

def render_comercial():

    st.header("🟦 Comercial")

    from core.app_context import get_pedidos

    pedidos = get_pedidos()

    pedidos = get_pedidos()
    pedidos_map = get_pedidos_map()

    # =======================
    # BÚSQUEDA
    # =======================
    st.subheader("🔎 Selección de pedido")

    col_mode, col_search = st.columns([1, 2])

    modo = col_mode.selectbox(
        "Buscar por",
        ["Pedido", "Referencia", "Cliente", "Representante"]
    )

    busqueda = col_search.text_input("Buscar...")

    resultado = pedidos

    if busqueda:
        b = busqueda.lower()

        if modo == "Pedido":
            resultado = [p for p in pedidos if b in str(p.get("id", "")).lower()]
        elif modo == "Cliente":
            resultado = [p for p in pedidos if b in str(p.get("cliente", "")).lower()]
        elif modo == "Representante":
            resultado = [p for p in pedidos if b in str(p.get("representante", "")).lower()]
        elif modo == "Referencia":
            resultado = [ p for p in pedidos if b in str(p.get("referencia", "")).lower()]
        
    # =======================
    # ALERTAS VISUALES (CON BOTÓN PARA CERRAR "X")
    # =======================
    # Filtramos los pedidos que tienen la alerta activa directamente para poder interactuar con ellos
    pedidos_con_alerta = [p for p in pedidos if p.get("compromiso_otc_actualizado")]

    if pedidos_con_alerta:
        st.subheader("📌 Actualizaciones OTC")
        
        for p_alerta in pedidos_con_alerta:
            # Creamos una fila con dos columnas: una para el texto y otra pequeña para la 'X'
            col_txt, col_btn = st.columns([8, 1])
            
            with col_txt:
                st.info(f"📌 Pedido {p_alerta.get('id')} - Fecha compromiso actualizado")
            
            with col_btn:
                # El botón actúa como la 'X' para descartar la alerta
                if st.button("❌", key=f"cerrar_alerta_{p_alerta.get('id')}", help="Marcar como leída y quitar"):
                    
                    # 1. Actualizamos el flag a False en el estado del pedido
                    update_pedido(p_alerta["id"], {
                        "compromiso_otc_actualizado": False,
                        "ultima_actualizacion": datetime.now().replace(microsecond=0)
                    })
                    
                    # 2. Forzamos el guardado en la base de datos de KOXKA
                    st.session_state["dirty"] = True
                    save_if_needed()
                    
                    # 3. Recargamos la interfaz para que desaparezca inmediatamente
                    st.success(f"Alerta del pedido {p_alerta.get('id')} marcada como leída.")
                    st.rerun()

    # =======================
    # SELECCIÓN
    # =======================
    pedido_sel = st.session_state.get("pedido_activo")

    if not pedido_sel and pedidos:
        pedido_sel = pedidos[0]["id"]

    st.session_state["pedido_activo"] = pedido_sel

    pedido = pedidos_map.get(pedido_sel)

    if not pedido:
        st.warning("Pedido no encontrado")
        st.stop()

    lineas = pedido.get("lineas", [])

    # =======================
    # RESULTADOS
    # =======================
    st.write("### 📋 Resultados")

    container = st.container(height=280)

    with container:

        if resultado:

            for p in resultado:

                col1, col2, col3 = st.columns([4, 3, 2])

                with col1:
                    st.write(f"📦 {p.get('id','-')} | Ref: {p.get('referencia','-')} - {p.get('cliente','-')}")

                with col2:
                    st.write(f"👨‍💼 {p.get('representante','-')}")

                with col3:
                    st.write(f"📅 {safe_date(p.get('fecha_cliente'))}")

                if st.button("Abrir", key=f"sel_{str(p.get('id'))}_{hash(str(p))}"):
                    st.session_state["pedido_activo"] = p.get("id")
                    st.rerun()

        else:
            st.info("Sin resultados")

    st.divider()

    # =======================
    # =======================
    # DETALLE PEDIDO
    # =======================
    if not lineas:
        st.warning("Sin líneas en este pedido")
        st.stop()

    df_lineas = pd.DataFrame(lineas)

    col_izq, col_der = st.columns([2, 1])

    with col_izq:
        st.subheader(f"📦 Pedido {pedido.get('id')}")

        st.write(f"👤 Cliente: {pedido.get('cliente','-')}")
        st.write(f"👤 Referencia: {pedido.get('referencia','-')}")
        st.write(f"👨‍💼 Representante: {pedido.get('representante','-')}")
        st.write(f"📅 Fecha cliente: {safe_date(pedido.get('fecha_cliente'))}")
        st.write(f"📌 Estado: {pedido.get('estado')}")

        st.divider()


        # Visualización de días de retraso
        dias = pedido.get("dias_retraso")
        if dias is not None:
            if dias > 5:
                st.error(f"🔴 Retraso grave: {dias} días")
            elif dias > 0:
                st.warning(f"🟠 Retraso: {dias} días")
            elif dias >= -2:
                st.info(f"🟡 Justo: {dias} días")
            else:
                st.success(f"🟢 Adelantado: {dias} días")
    
    # =====================================================
    # DETALLE DE PEDIDO UNIFICADO
    # =====================================================
    st.divider()
    st.write("### 📊 Detalle del Pedido")
        
    if not df_lineas.empty:
        filas_procesadas = []
            
        for _, row in df_lineas.iterrows():
            # Leemos la carga (C) que añadimos en el servicio
            val_carga = str(row.get("carga", "")).strip().upper()
                
            # Definimos el texto del Estado según la condición de la "C"
            estado_texto = "🟢 Confirmada" if val_carga == "C" else "🟡 Pendiente"
                
            filas_procesadas.append({
                "Posición": row.get("posicion", "-"),
                "Máquina": row.get("maquina", "-"),
                "Cantidad": row.get("cantidad", "-"),
                "Fecha Compromiso": safe_date(row.get("fecha_compromiso")),
                "Fecha Carga": safe_date(row.get("fecha_carga")), # Usamos fecha_carga como entrega
                "Estado": estado_texto
            })
            
        df_detalle = pd.DataFrame(filas_procesadas)
        st.dataframe(df_detalle, use_container_width=True, hide_index=True)
        

    with col_der:
        st.subheader("⚙️ Control")

        fecha_actual = pedido.get("fecha_cliente")
        value = safe_date_input_value(pedido.get("fecha_cliente"))

        nueva_fecha = st.date_input(
            "Nueva fecha cliente",
            value=value,
            key=f"fecha_{pedido.get('id')}"
        )

        confirmar = True
        if pedido.get("compromiso_otc_actualizado"):
            st.warning("⚠ Este pedido ya fue comunicado a OTC")
            confirmar = st.checkbox(
                "Confirmo que quiero actualizar fecha cliente",
                key=f"confirm_{pedido['id']}"
            )

        guardar_click = st.button(
            "💾 Guardar cambio",
            key=f"guardar_{pedido['id']}"
        )

        if guardar_click and confirmar:
            valor_anterior = pedido.get("fecha_cliente")

            if pd.isna(nueva_fecha):
                st.error("Fecha inválida")
                st.stop()

            nuevo_valor = datetime.combine(nueva_fecha, datetime.min.time())

            update_pedido(pedido["id"], {
                "fecha_cliente": nuevo_valor,
                "ultima_actualizacion": datetime.now().replace(microsecond=0),
                "dias_retraso": (
                    to_datetime_safe(pedido.get("fecha_compromiso")) - to_datetime_safe(nuevo_valor)
                ).days,
                "cambio_comercial": True,
                "fecha_cliente_modificada": datetime.now().replace(microsecond=0)
            })

            registrar_cambio(
                pedido["id"],
                "fecha_cliente",
                valor_anterior,
                nuevo_valor,
                "comercial_otc_update"
            )

            # Llamada adaptada a tu alertas_service global de base de datos
            crear_alerta_manual(
                pedido=pedido["id"],
                mensaje="Fecha cliente modificada manualmente",
                tipo="COMERCIAL"
            )

            generar_txt_baan(
                pedido=pedido,
                accion="UPDATE_FECHA_CLIENTE",
                fecha_anterior=valor_anterior,
                fecha_nueva=nuevo_valor
            )

            st.session_state["dirty"] = True
            save_if_needed()

            st.success("Cambio guardado")
            st.rerun()