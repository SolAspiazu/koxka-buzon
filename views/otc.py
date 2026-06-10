import streamlit as st
import pandas as pd

from utils.helpers import (
    safe_date,
    mostrar_fecha_compromiso,
    mostrar_fecha_carga
)

from services.otc_service import (
    validar_pedido_otc,
    devolver_a_comercial
)

from core.app_context import (
    get_pedidos,
    update_pedido,
    save_if_needed
)
from datetime import datetime
# =========================================================
# RENDER DE UN PEDIDO (BLOQUE CENTRAL REUTILIZABLE)
# =========================================================
def render_pedido_otc(p):

    confirmado = str(p.get("carga", "")).strip().upper() == "C"

    with st.expander(
        f"📦 Pedido {p.get('id')} - {p.get('cliente','-')}",
        expanded=(st.session_state.get("pedido_activo") == p.get("id"))
    ):

        # =====================================================
        # INFO GENERAL
        # =====================================================
        col_info1, col_info2 = st.columns(2)

        with col_info1:
            st.write(f"**👤 Cliente:** {p.get('cliente','-')}")
            st.write(f"**👨‍💼 Representante:** {p.get('representante','-')}")

        with col_info2:
            st.write(f"**📅 Fecha cliente:** {safe_date(p.get('fecha_cliente'))}")
            st.write(f"**🕒 Origen:** {p.get('origen_otc', 'Manual')}")

        # =====================================================
        # ESTADO
        # =====================================================
        if not confirmado:
            st.warning("⚠ Pedido pendiente por confirmar fecha compromiso")
        else:
            st.success("✅ Pedido confirmado")

        st.divider()

        # =====================================================
        # DETALLE DE LÍNEAS (IMPORTANTE: SIEMPRE VISIBLE)
        # =====================================================
        st.markdown("### 📊 Detalle de líneas")

        filas = []
        for l in p.get("lineas", []):

            filas.append({
                "Máquina": l.get("maquina", "-"),
                "Posición": l.get("posicion", "-"),
                "Cantidad": l.get("cantidad", "-"),
                "F. Cliente": safe_date(p.get("fecha_cliente")),
                "F. Compromiso": safe_date(l.get("fecha_compromiso")),
                "F. Carga": safe_date(l.get("fecha_carga"))
            })

        st.dataframe(
            pd.DataFrame(filas),
            use_container_width=True,
            height=180
        )

        # =====================================================
        # ALERTAS / RIESGO (MISMO BLOQUE VISUAL)
        # =====================================================
        dias = p.get("dias_retraso")

        if dias is not None:

            st.markdown("### ⚠️ Análisis de riesgo")

            if dias > 5:
                st.error(f"🔴 Riesgo alto: {dias} días de retraso")

            elif dias > 0:
                st.warning(f"🟠 Riesgo: {dias} días de retraso")

            elif dias >= -2:
                st.info(f"🟡 Plazo ajustado ({dias} días)")

            else:
                st.success(f"🟢 Plazo OK ({abs(dias)} días adelanto)")

        st.divider()

        # =====================================================
        # ACCIONES
        # =====================================================
        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            if st.button(
                f"📢 Validar y Comunicar {p.get('id')}",
                key=f"otc_val_{p.get('id')}",
                use_container_width=True
            ):
                validar_pedido_otc(p)

                st.session_state["dirty"] = True
                save_if_needed()

                st.success(f"✅ Pedido {p.get('id')} validado")
                st.rerun()

        with col_btn2:
            if st.button(
                f"🔁 Devolver a Comercial",
                key=f"otc_rev_{p.get('id')}",
                use_container_width=True
            ):
                # 1. Ejecuta tu lógica actual del servicio
                devolver_a_comercial(p)

                # 2. 🔥 ACTIVA LA ALERTA EN COMERCIAL pasando el flag a True
                update_pedido(p["id"], {
                    "devuelto_por_otc": True,
                    "ultima_actualizacion": datetime.now().replace(microsecond=0)
                })

                # 3. Guarda los cambios en el estado de la app
                st.session_state["dirty"] = True
                save_if_needed()

                st.warning(f"↩️ Pedido {p.get('id')} devuelto a Comercial")
                st.rerun()


# =========================================================
# PANTALLA PRINCIPAL OTC
# =========================================================
def render_otc():

    st.header("🟨 OTC")

    pedidos = get_pedidos()

    # ===============================
    # BUSCADOR
    # ===============================
    st.subheader("🔎 Buscar pedido")

    busqueda_otc = st.text_input("Buscar pedido, cliente o referencia")

    resultado_busqueda = []

    if busqueda_otc:
        b = busqueda_otc.lower()

        resultado_busqueda = [
            p for p in pedidos
            if (
                b in str(p.get("id", "")).lower()
                or b in str(p.get("cliente", "")).lower()
                or b in str(p.get("referencia", "")).lower()
            )
        ]

    # ===============================
    # RESULTADOS BUSQUEDA
    # ===============================
    if resultado_busqueda:

        st.subheader("📋 Resultado búsqueda")

        for p in resultado_busqueda:
            render_pedido_otc(p)

    # ===============================
    # LISTADO OTC
    # ===============================
    pedidos_otc = [
        p for p in pedidos
        if str(p.get("carga", "")).strip().upper() == "C"
    ]

    if st.session_state.get("pedido_activo"):

        pedidos_otc = sorted(
            pedidos_otc,
            key=lambda p: p["id"] != st.session_state["pedido_activo"]
        )

    if not pedidos_otc:
        st.info("No hay pedidos pendientes en OTC")
        return

    st.subheader(f"📋 Pedidos por validar: {len(pedidos_otc)}")

    PAGE_SIZE = 15

    total_pages = max(1, (len(pedidos_otc) - 1) // PAGE_SIZE + 1)

    page = st.number_input(
        "Página OTC",
        min_value=1,
        max_value=total_pages,
        value=1
    )

    inicio = (page - 1) * PAGE_SIZE
    fin = inicio + PAGE_SIZE

    for p in pedidos_otc[inicio:fin]:
        render_pedido_otc(p)