import streamlit as st
from datetime import datetime
from database.connection import get_conn
from utils.date_utils import to_db_date

def registrar_cambio(pedido_id, campo, valor_anterior, valor_nuevo, origen):
    # Si no hay cambio real, no hacemos nada
    if str(valor_anterior) == str(valor_nuevo):
        return

    # =====================================================
    # 🔥 DETECCIÓN DINÁMICA DEL DEPARTAMENTO (KOXKA)
    # =====================================================
    # Si el origen viene con el texto genérico, lo cambiamos según el campo
    if origen in ["comercial_otc_update", "manual", "update"]:
        campo_lower = str(campo).lower()
        
        if "cliente" in campo_lower:
            origen = "Comercial"
        elif "compromiso" in campo_lower:
            origen = "Planificación"
        elif "carga" in campo_lower or "entrega" in campo_lower:
            origen = "Planificación"  # O el departamento que gestione las cargas
        else:
            origen = "Sistema" # Por si es otro campo genérico
    
    # Aseguramos un formato estético si ya venía bien de los botones manuales
    elif str(origen).lower() == "comercial":
        origen = "Comercial"
    elif str(origen).lower() == "otc":
        origen = "OTC"
    elif str(origen).lower() in ["planificacion", "planeacion", "planificaciòn"]:
        origen = "Planificación"

    # =====================================================
    # CONTINÚA TU LOGÍSICA NORMAL DE GUARDADO
    # =====================================================
    fecha = datetime.now().replace(microsecond=0)
    fecha_iso_perfecta = fecha.strftime("%Y-%m-%d %H:%M:%S")

    cambio = {
        "pedido": pedido_id,
        "campo": campo,
        "antes": valor_anterior,
        "despues": valor_nuevo,
        "origen": origen, # Guardará "Comercial", "Planificación" o "OTC"
        "fecha": fecha_iso_perfecta
    }

    if "historial_cambios" not in st.session_state:
        st.session_state.historial_cambios = []
    st.session_state.historial_cambios.append(cambio)

    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO historial
            (pedido, campo, antes, despues, origen, fecha)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            pedido_id,
            campo,
            str(valor_anterior),
            str(valor_nuevo),
            origen,  # Se guarda el departamento limpio
            fecha_iso_perfecta
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error al registrar en historial: {e}")