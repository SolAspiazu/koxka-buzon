from database.connection import get_conn


def init_db():

    conn = get_conn()
    cur = conn.cursor()

    # =========================
    # PEDIDOS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS pedidos (
        id TEXT PRIMARY KEY,
        data TEXT
    )
    """)

    # =========================
    # HISTORIAL
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS historial (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido TEXT,
        campo TEXT,
        antes TEXT,
        despues TEXT,
        origen TEXT,
        fecha TEXT
    )
    """)

    # =========================
    # ALERTAS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alertas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT,
        pedido TEXT,
        mensaje TEXT,
        fecha TEXT
    )
    """)

    conn.commit()
    conn.close()