import sqlite3
from config.settings import DB_PATH


def get_conn():
    # El timeout de 30.0 evita que la app falle si otra pantalla está escribiendo un pedido en ese instante
    conn = sqlite3.connect(DB_PATH, timeout=30.0) 
    # Esto activa el modo Write-Ahead Logging para que convivan lecturas y escrituras sin colisionar
    conn.execute("PRAGMA journal_mode=WAL;")      
    return conn