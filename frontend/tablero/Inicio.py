# -*- coding: utf-8 -*-
"""
Tablero Integral de Afiliados · ACTHO

Ejecutar desde la raíz del proyecto:
    streamlit run frontend/tablero/Inicio.py

Lee las vistas del esquema 'actho' en PostgreSQL (ver README, sección 7).
"""
from pathlib import Path

import streamlit as st

AQUI = Path(__file__).resolve().parent

st.set_page_config(page_title="ACTHO · Tablero de afiliados", page_icon="🟣", layout="wide",
                   initial_sidebar_state="expanded")

import comun  # noqa: E402

comun.estilo()
comun.verificar_conexion()

paginas = {
    "Dirección": [
        st.Page(AQUI / "paginas/01_panel_general.py", title="Panel general", icon=":material/dashboard:", default=True),
    ],
    "Comercial": [
        st.Page(AQUI / "paginas/02_afiliados.py", title="Afiliados", icon=":material/groups:"),
        st.Page(AQUI / "paginas/03_ficha_360.py", title="Ficha 360°", icon=":material/badge:"),
        st.Page(AQUI / "paginas/04_renovacion.py", title="Renovación y retención", icon=":material/autorenew:"),
    ],
    "Experiencias": [
        st.Page(AQUI / "paginas/05_experiencias_nps.py", title="Experiencias y NPS", icon=":material/event:"),
        st.Page(AQUI / "paginas/07_segmentos.py", title="Segmentos", icon=":material/campaign:"),
    ],
    "Inteligencia y datos": [
        st.Page(AQUI / "paginas/06_pulso.py", title="Pulso", icon=":material/monitor_heart:"),
        st.Page(AQUI / "paginas/08_datos_calidad.py", title="Datos y calidad", icon=":material/database:"),
    ],
}
pagina = st.navigation(paginas)
comun.filtros_barra_lateral()
pagina.run()
