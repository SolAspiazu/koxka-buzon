import os
import pandas as pd
import streamlit as st
from utils.helpers import normalize_fecha
from config.settings import MAP

def cargar_datos(file_path, mtime):
    lineas = []
    
    # -------------------------------------------------------------
    # DETECCIÓN DE ORIGEN: ¿Es una ruta de disco o un archivo web?
    # -------------------------------------------------------------
    if isinstance(file_path, str):
        # CASO DE DISCO (Planta Real de KOXKA)
        if not os.path.exists(file_path):
            return pd.DataFrame()
        with open(file_path, "r", encoding="cp1252", errors="ignore") as f:
            lineas = f.readlines()
    else:
        # CASO DE SIMULACIÓN/WEB (Presentación del TFM)
        try:
            bytes_data = file_path.read()
            # Devolvemos el puntero al principio por si acaso se vuelve a leer
            file_path.seek(0)
            contenido_texto = bytes_data.decode("cp1252", errors="ignore")
            lineas = contenido_texto.splitlines()
        except Exception as e:
            return pd.DataFrame()

    # -------------------------------------------------------------
    # TU LÓGICA DE PROCESAMIENTO ORIGINAL (INTACTA)
    # -------------------------------------------------------------
    rows = []
    for line in lineas:
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
