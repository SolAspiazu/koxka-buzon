import pandas as pd
import streamlit as st

from database.connection import get_conn


def cargar_historial():

    conn = get_conn()

    try:

        df_historial = pd.read_sql_query(
            """
            SELECT
                pedido,
                campo,
                antes,
                despues,
                origen,
                fecha
            FROM historial
            ORDER BY fecha ASC
            """,
            conn
        )

        if not df_historial.empty:

            df_historial["fecha"] = pd.to_datetime(
                df_historial["fecha"],
                errors="coerce"
            )

            st.session_state.historial_cambios = (
                df_historial.to_dict("records")
            )

    finally:
        conn.close()