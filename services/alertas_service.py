import pandas as pd
import streamlit as st
import sqlite3
from datetime import datetime
from database.connection import get_conn  # Conexión nativa de KOXKA
from core.audit import registrar_cambio
from core.app_context import notificar_alerta_global

# =========================================================
# 1. GESTIÓN UNIFICADA DE ALERTAS EN BASE DE DATOS (SQLITE)
# =========================================================

def crear_alerta_manual(pedido, mensaje, tipo):
    """
    Guarda una alerta manual físicamente en la Base de Datos SQLite.
    """
    alert_id = f"manual_{tipo}_{pedido}_{datetime.now().timestamp()}".replace(".", "")
    notificar_alerta_global()
    _insertar_alerta_en_db(alert_id, pedido, mensaje, tipo)


def _insertar_alerta_en_db(alert_id, pedido, mensaje, tipo):
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alertas_db (
                id TEXT PRIMARY KEY,
                pedido TEXT,
                mensaje TEXT,
                tipo TEXT,
                estado TEXT,
                fecha TEXT
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alertas_estado ON alertas_db (estado);")
        
        cursor.execute("""
            INSERT OR IGNORE INTO alertas_db (id, pedido, mensaje, tipo, estado, fecha)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (alert_id, str(pedido), mensaje, tipo, "activa", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except Exception as e:
        print(f"Error al guardar alerta en alertas_db: {e}")
    finally:
        conn.close()

def contar_alertas():
    total_activas = 0
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM alertas_db WHERE estado = 'activa'")
        total_activas = cursor.fetchone()[0]
    except Exception as e:
        total_activas = 0
    finally:
        conn.close()
        
    return total_activas


def alertas_activas():
    alertas_db = []
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, pedido, mensaje, tipo, estado, fecha FROM alertas_db WHERE estado = 'activa'")
        filas = cursor.fetchall()
        for f in filas:
            alertas_db.append({
                "id": f[0],
                "pedido": f[1],
                "mensaje": f[2],
                "tipo": f[3],
                "estado": f[4],
                "fecha": f[5]
            })
    except Exception as e:
        pass
    finally:
        conn.close()
        
    return alertas_db


def marcar_alerta_leida(alerta_id):
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE alertas_db SET estado = 'leida' WHERE id = ?", (alerta_id,))
        conn.commit()
    except Exception as e:
        print(f"Error al marcar alerta como leída en la BD: {e}")
    finally:
        conn.close()

    if "alertas_leidas" not in st.session_state:
        st.session_state["alertas_leidas"] = []
    if alerta_id not in st.session_state["alertas_leidas"]:
        st.session_state["alertas_leidas"].append(alerta_id)
        
    st.session_state["last_alert_update"] = datetime.now()
    notificar_alerta_global()


# =========================================================
# 2. DETECCIÓN Y LÓGICA DEL ERP BAAN (PERSISTENCIA INYECTADA)
# =========================================================

def hay_cambios_erp(viejos, nuevos_pedidos):
    mapa_viejos = {p["id"]: p for p in viejos}
    
    for nuevo in nuevos_pedidos:
        viejo = mapa_viejos.get(nuevo["id"])
        if viejo:
            if str(viejo.get("fecha_compromiso")) != str(nuevo.get("fecha_compromiso")):
                return True
            if str(viejo.get("fecha_entrada")) != str(nuevo.get("fecha_entrada")):
                return True
            if str(viejo.get("fecha_calculada")) != str(nuevo.get("fecha_calculada")):
                return True
            if str(viejo.get("carga")).strip().upper() != str(nuevo.get("carga")).strip().upper():
                return True
    return False


def detectar_cambios_erp(viejos, nuevos_pedidos):
    """
    Analiza el .txt del ERP, clasifica los cambios de KOXKA.
    Nota: Hemos quitado el disparador del historial de aquí para evitar que re-lea
    cambios antiguos del TXT en cada pasada.
    """
    mapa_viejos = {p["id"]: p for p in viejos}
    viejos_ids = {p["id"] for p in viejos}
    
    nuevos_detectados = []
    actualizados_detectados = []

    for nuevo in nuevos_pedidos:
        pedido_id = nuevo["id"]
        
        if pedido_id not in viejos_ids:
            nuevos_detectados.append({
                "pedido": pedido_id,
                "cliente": nuevo.get("cliente", "Desconocido"),
                "tipo_alerta": "Comercial (Nuevo Pedido)"
            })
            continue
            
        viejo = mapa_viejos.get(pedido_id)
        if viejo:
            cambios = []
            campos_criticos = ["fecha_compromiso", "fecha_cliente"]
            
            for campo_critico in campos_criticos:
                v_val = str(viejo.get(campo_critico)).strip().upper()
                n_val = str(nuevo.get(campo_critico)).strip().upper()
                
                if v_val != n_val:
                    destino = "Planeación" if campo_critico == "fecha_compromiso" else "Comercial"
                    
                    antes_str = str(viejo.get(campo_critico)).split(" ")[0] if viejo.get(campo_critico) else "Ninguna"
                    despues_str = str(nuevo.get(campo_critico)).split(" ")[0] if nuevo.get(campo_critico) else "Ninguna"

                    cambios.append({
                        "campo": campo_critico,
                        "antes": antes_str,
                        "despues": despues_str,
                        "destino": destino
                    })
            
            if cambios:
                actualizados_detectados.append({
                    "pedido": pedido_id,
                    "cambios": cambios
                })
                
    return {"nuevos": nuevos_detectados, "actualizados": actualizados_detectados}


def construir_alertas_erp(resumen_erp):
    """
    Procesa las alertas y registra en el historial ÚNICAMENTE si la alerta es NUEVA.
    Usamos el ID único de la alerta para saber si ya se procesó en el pasado y evitar duplicados fatales.
    """
    conn = get_conn()
    cursor = conn.cursor()
    
    # Aseguramos que existe la tabla de alertas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alertas_db (
            id TEXT PRIMARY KEY, pedido TEXT, mensaje TEXT, tipo TEXT, estado TEXT, fecha TEXT
        )
    """)
    conn.commit()

    for p_nuevo in resumen_erp.get("nuevos", []):
        pedido_id = p_nuevo["pedido"]
        id_alerta_nuevo = f"alerta_nuevo_{pedido_id}"
        
        # Verificar si ya existía esta alerta exacta en la base de datos
        cursor.execute("SELECT 1 FROM alertas_db WHERE id = ?", (id_alerta_nuevo,))
        existe = cursor.fetchone()
        
        if not existe:
            mensaje = f"📦 ¡Nuevo pedido detectado en ERP! Cliente: {p_nuevo['cliente']}"
            _insertar_alerta_en_db(id_alerta_nuevo, pedido_id, mensaje, "Comercial")
            registrar_cambio(pedido_id, "pedido", "Inexistente", "Nuevo Pedido (ERP)", "erp_update")

    for p_act in resumen_erp.get("actualizados", []):
        pedido_id = p_act["pedido"]
        for c in p_act["cambios"]:
            campo = c["campo"]
            antes_limpio = c["antes"]
            despues_limpio = c["despues"]
            destino = c["destino"]
            
            id_alerta_unico = f"alerta_{pedido_id}_{campo}_{despues_limpio}".replace(" ", "_")
            
            # 🔥 LA SOLUCIÓN QUIRÚRGICA: Solo si la alerta NO existe en la BD, significa que es un cambio REAL de ahora
            cursor.execute("SELECT 1 FROM alertas_db WHERE id = ?", (id_alerta_unico,))
            existe_alerta = cursor.fetchone()
            
            if not existe_alerta:
                campo_pantalla = campo.replace("_", " ").capitalize()
                mensaje = f"⚠️ Cambio en {campo_pantalla}: {antes_limpio} → {despues_limpio}"
                
                # 1. Guardamos la alerta de manera persistente
                _insertar_alerta_en_db(id_alerta_unico, pedido_id, mensaje, destino)
                
                # 2. Guardamos en el historial una ÚNICA VEZ con el pedido e ID correcto
                registrar_cambio(
                    pedido_id=pedido_id,
                    campo=campo,
                    valor_anterior=antes_limpio,
                    valor_nuevo=despues_limpio,
                    origen="manual"
                )
            
    conn.close()
    
    if resumen_erp.get("nuevos") or resumen_erp.get("actualizados"):
        notificar_alerta_global()
    
    return alertas_activas()

def marcar_todas_las_alertas_como_leidas(tipo_departamento=None):
    conn = get_conn()
    cursor = conn.cursor()
    try:
        if tipo_departamento:
            cursor.execute(
                "UPDATE alertas_db SET estado = 'leido' WHERE tipo = ? AND (estado != 'leido' OR estado IS NULL)",
                (tipo_departamento,)
            )
        else:
            cursor.execute(
                "UPDATE alertas_db SET estado = 'leido' WHERE estado != 'leido' OR estado IS NULL"
            )
        conn.commit()
        notificar_alerta_global()
    except Exception as e:
        print(f"Error al marcar todas las alertas como leídas: {e}")
    finally:
        conn.close()
