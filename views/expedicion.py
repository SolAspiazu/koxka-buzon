import streamlit as st
import pandas as pd

from utils.helpers import safe_date

from services.expedicion_service import (
    calcular_estado_expedicion,
    confirmar_salida,
    obtener_pedidos_expedicion,
    obtener_despachados,
    mostrar_fecha_compromiso,
    mostrar_fecha_carga
)

from utils.helpers import safe_date

from core.app_context import (
    get_pedidos,
    save_if_needed
)

def render_expedicion():

    st.header("🟩 Expedición")

    pedidos = get_pedidos()

    # =========================
    # BUSCADOR
    # =========================

    busqueda_exp = st.text_input(
        "🔎 Buscar pedido, cliente o referencia"
    )

    # =========================
    # CALCULAR ESTADOS
    # =========================

    hoy = pd.Timestamp.now().normalize()

    for p in pedidos:

        p["estado_expedicion"] = calcular_estado_expedicion(
            p,
            hoy
        )

    # =========================
    # LISTAS
    # =========================

    pedidos_confirmados = [
        p for p in pedidos
        if str(p.get("carga", "")).strip().upper() == "C"
    ]

    pendientes_entrega = obtener_pedidos_expedicion(
        pedidos
    )

    posible_despacho = [
        p for p in pedidos
        if p.get("estado_expedicion")
        == "posible_despachado"
    ]

    despachados = obtener_despachados(
        pedidos
    )

    # =========================
    # FILTRO BÚSQUEDA
    # =========================

    if busqueda_exp:

        b = busqueda_exp.lower()

        pendientes_entrega = [

            p for p in pendientes_entrega

            if (
                b in str(p.get("id", "")).lower()
                or b in str(p.get("cliente", "")).lower()
                or b in str(p.get("referencia", "")).lower()
            )
        ]

    # =========================
    # KPI LOGÍSTICOS
    # =========================

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "🚛 En proceso",
        len([
            p for p in pedidos
            if p.get("estado_expedicion") in [
                "programado",
                "en_preparacion"
            ]
        ])
    )

    col2.metric(
        "⚠️ Posible despachado",
        len([
            p for p in pedidos
            if p.get("estado_expedicion")
            == "posible_despachado"
        ])
    )

    col3.metric(
        "✅ Confirmados",
        len([
            p for p in pedidos
            if p.get("estado_expedicion")
            == "despachado_confirmado"
        ])
    )

    st.divider()

    # =========================
    # BANDEJA DE SALIDA
    # =========================

    st.subheader("🚛 Pendientes de entrega")

    if not pendientes_entrega:

        st.info(
            "No hay pedidos pendientes de salida en el muelle."
        )

        return

    # =========================
    # ORDENAR
    # =========================

    pendientes_entrega = sorted(

        pendientes_entrega,

        key=lambda x:
        str(x.get("fecha_carga"))
        if x.get("fecha_carga")
        else "9999"
    )

    # =========================
    # PAGINACIÓN
    # =========================

    PAGE_SIZE = 15

    total_pages = max(
        1,
        (len(pendientes_entrega) - 1)
        // PAGE_SIZE + 1
    )

    page = st.number_input(
        "Página entrega",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1
    )

    inicio = (page - 1) * PAGE_SIZE
    fin = inicio + PAGE_SIZE

    pendientes_entrega = pendientes_entrega[
        inicio:fin
    ]

    # =========================
    # LISTADO PRINCIPAL
    # =========================

    for p in pendientes_entrega:

        retrasos_logisticos = [

            x for x in pendientes_entrega

            if (
                x.get("estado_expedicion")
                == "en_preparacion"

                and pd.notnull(
                    x.get("fecha_carga")
                )

                and pd.to_datetime(
                    x.get("fecha_carga"),
                    errors="coerce"
                ) < pd.Timestamp.now().normalize()
            )
        ]

        es_urgente = p in retrasos_logisticos

        label_urgencia = (
            "🚨 RETRASADO"
            if es_urgente
            else "🕙 A TIEMPO"
        )

        with st.expander(
            f"{label_urgencia} | "
            f"Pedido {p['id']} - "
            f"{p.get('cliente','-')}"
        ):

            # =====================
            # TABLA LÍNEAS
            # =====================

            st.markdown(
                "### 🏭 Líneas de expedición"
            )

            filas_lineas = []

            for l in p.get("lineas", []):

                filas_lineas.append({

                    "Máquina":
                    l.get("maquina", "-"),

                    "Posición":
                    l.get("posicion", "-"),

                    "Cantidad":
                    l.get("cantidad", "-"),

                    "F. Compromiso":
                    safe_date(
                        l.get("fecha_compromiso")
                    ),

                    "F. Carga":
                    safe_date(
                        l.get("fecha_carga")
                    )
                })

            st.dataframe(
                pd.DataFrame(filas_lineas),
                use_container_width=True,
                hide_index=True
            )

            # =====================
            # INFO GENERAL
            # =====================

            c1, c2 = st.columns(2)

            with c1:

                st.write(
                    f"**👤 Cliente:** "
                    f"{p.get('cliente','-')}"
                )

                st.write(
                    f"**👨‍💼 Rep:** "
                    f"{p.get('representante','-')}"
                )

            with c2:

                st.write(
                    f"**📅 F. Cliente:** "
                    f"{safe_date(p.get('fecha_cliente'))}"
                )

                

            

            # =====================
            # ESTADO VISUAL
            # =====================

            estado = p.get("estado_expedicion")

            if estado == "programado":

                st.info("🟦 Programado")

            elif estado == "en_preparacion":

                st.warning("🟧 En preparación")

            elif estado == "retrasado":

                st.error("🚨 Pedido retrasado")

            elif estado == "posible_despachado":

                st.error(
                    "🟨 Posible despachado "
                    "(no aparece en ERP)"
                )

            elif estado == "despachado_confirmado":

                st.success(
                    "🟩 Despachado confirmado"
                )

            elif estado == "no_confirmado":

                st.info(
                    "⚪ No confirmado (sin carga)"
                )

            # =====================
            # BOTÓN CONFIRMAR
            # =====================

            if estado != "despachado_confirmado":

                if st.button(
                    f"✅ Confirmar salida {p['id']}",
                    key=f"desp_{p['id']}"
                ):

                    confirmar_salida(p)

                    # marcar cambios
                    st.session_state["dirty"] = True

                    # guardar sqlite
                    save_if_needed()

                    st.success(
                        "Pedido despachado correctamente"
                    )

                    st.rerun()

    # =========================
    # HISTORIAL RECIENTE
    # =========================

    if despachados:

        st.divider()

        with st.expander(
            "🕒 Ver últimos envíos realizados"
        ):

            historial = []

            for h in reversed(despachados[-5:]):

                historial.append({

                    "ID":
                    h.get("id"),

                    "Cliente":
                    h.get("cliente"),

                    "F. Compromiso":
                    safe_date(
                        h.get("fecha_compromiso")
                    ),

                    "F. Carga":
                    safe_date(
                        h.get("fecha_carga")
                    ),

                    "Estado":
                    "✅ ENVIADO"
                })

            st.table(
                pd.DataFrame(historial)
            )