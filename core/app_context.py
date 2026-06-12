import streamlit as st
import time
from database.pedidos_repo import guardar_pedidos
from database.load_repo import cargar_pedidos_db
import threading

def save_pedidos(pedidos):
    guardar_pedidos(pedidos)
    st.session_state["pedidos"] = pedidos

# =========================================================
# INIT
# =========================================================
def init_app():
    # 🚨 UNIFICADO: Guardamos los pedidos siempre en st.session_state["pedidos"]
    if "pedidos" not in st.session_state:
        st.session_state["pedidos"] = cargar_pedidos_db()

    if "dirty" not in st.session_state:
        st.session_state["dirty"] = False


# =========================================================
# GET PEDIDOS
# =========================================================
def get_pedidos():
    """
    Devuelve los pedidos. Si la sesión ha sido limpiada por app29.py 
    al detectar una nueva alerta, se ve obligada a leer los datos frescos de SQLite.
    """
    # 🚨 Si la pantalla pasiva detectó un cambio y borró "pedidos", los recargamos limpios de SQLite
    if "pedidos" not in st.session_state or st.session_state["pedidos"] is None:
        st.session_state["pedidos"] = cargar_pedidos_db()
    return st.session_state["pedidos"]


# =========================================================
# GET PEDIDO BY ID
# =========================================================
def get_pedido_by_id(pedido_id):
    for p in get_pedidos():
        if str(p["id"]) == str(pedido_id):
            return p
    return None


# =========================================================
# UPDATE PEDIDO
# =========================================================
def update_pedido(pedido_id, nuevos_datos):
    """
    Actualiza el pedido tanto en la memoria de la pantalla actual 
    como en la estructura interna para evitar desfases.
    """
    pedidos_map = get_pedidos_map()
    if pedido_id in pedidos_map:
        # Actualizamos los campos en memoria
        pedidos_map[pedido_id].update(nuevos_datos)
        st.session_state["pedidos"] = list(pedidos_map.values())


# =========================================================
# GET MAP
# =========================================================
def get_pedidos_map():
    """Genera un mapa rápido id -> pedido basado en los pedidos actuales."""
    pedidos = get_pedidos()
    return {p["id"]: p for p in pedidos}


# =========================================================
# SAVE
# =========================================================
def save_if_needed():
    """
    Si hay cambios pendientes (dirty), guarda de manera física 
    en la base de datos SQLite compartida.
    """
    if st.session_state.get("dirty", False):
        pedidos = get_pedidos()
        guardar_pedidos(pedidos)
        st.session_state["dirty"] = False

# 🚨 SISTEMA MULTIPANTALLA PRO: Canal de eventos en memoria RAM compartido por toda la fábrica
_global_lock = threading.Lock()
_global_state = {
    "ultimo_cambio_alertas": 0.0
}

def notificar_alerta_global():
    """Toca el timbre eléctrico. Avisa a todas las pantallas que hay cambios."""
    import time
    with _global_lock:
        _global_state["ultimo_cambio_alertas"] = time.time()

def obtener_timestamp_alertas():
    """Devuelve el microsegundo exacto del último movimiento en KOXKA."""
    return _global_state["ultimo_cambio_alertas"]