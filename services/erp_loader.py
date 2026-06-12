import os
import pandas as pd
import streamlit as st
from utils.helpers import normalize_fecha

from config.settings import MAP


@st.cache_data(ttl=10)
def cargar_datos(file_path, mtime):

    if not os.path.exists(file_path):
        return pd.DataFrame()

    rows = []

    with open(file_path, encoding="cp1252", errors="ignore") as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            if line.startswith("-") or "Fecha" in line:
                continue

            parts = line.split("|")

            if len(parts) < 30:
                parts += [""] * (30 - len(parts))

            rows.append(parts)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    df.columns = [
        f"col_{i}"
        for i in range(df.shape[1])
    ]


    col_pedido = f"col_{MAP['pedido']}"

    mask = (
        df[col_pedido].notna()
        & (df[col_pedido].astype(str).str.strip() != "")
        & (df[col_pedido].astype(str).str.lower() != "pedido")
    )

    return df.loc[mask].copy()
