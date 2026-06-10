import sqlite3
import json
import pandas as pd
from config.settings import DB_PATH


def serialize_json(obj):
    """
    Convierte datetime/Timestamp a string ISO antes de JSON
    """

    if isinstance(obj, dict):
        return {k: serialize_json(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [serialize_json(v) for v in obj]

    if isinstance(obj, (pd.Timestamp, )):
        return obj.strftime("%Y-%m-%d")

    if hasattr(obj, "isoformat"):
        return obj.isoformat()

    return obj


def guardar_pedidos(pedidos):

    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        c = conn.cursor()

        for p in pedidos:

            p_clean = serialize_json(p)

            c.execute("""
            INSERT OR REPLACE INTO pedidos (id, data)
            VALUES (?, ?)
            """, (
                p_clean.get("id"),
                json.dumps(p_clean, ensure_ascii=False)
            ))

        conn.commit()