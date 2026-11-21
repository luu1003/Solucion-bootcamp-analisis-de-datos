# -*- coding: utf-8 -*-
"""
Tablero Integral de Afiliados · ACTHO

Forma recomendada de abrirlo (instala, carga datos y abre el navegador):
    python3 setup.py
Directamente, con el entorno ya listo:
    streamlit run frontend/tablero/Inicio.py

Lee las vistas del esquema 'actho' en PostgreSQL (ver README, sección 7).
"""
from pathlib import Path

import streamlit as st

AQUI = Path(__file__).resolve().parent

st.set_page_config(page_title="ACTHO · Tablero de afiliados", page_icon="🟣", layout="wide",
                   initial_sidebar_state="expanded")

import comun  # noqa: E402

comun.reiniciar_contadores()
comun.estilo()

import login  # noqa: E402

login.requerir_sesion()          # muestra el inicio de sesión si no hay sesión activa
comun.verificar_conexion()

# Páginas visibles por ahora. Las demás siguen en paginas/ y se activan agregándolas a esta lista:
#   03_ficha_360.py (Ficha 360°) · 04_renovacion.py (Renovación y retención) · 06_pulso.py (Pulso)
#   07_segmentos.py (Segmentos) · 08_datos_calidad.py (Datos y calidad)
VISIBLES = [
    ("01_panel_general.py", "Dashboard", ":material/dashboard:"),
    ("02_afiliados.py", "Afiliados", ":material/groups:"),
    ("05_experiencias_nps.py", "Experiencias", ":material/event:"),
]
comun.PAGINAS_ACTIVAS.clear()
comun.PAGINAS_ACTIVAS.update(archivo for archivo, _, _ in VISIBLES)

pagina = st.navigation([st.Page(AQUI / "paginas" / archivo, title=titulo, icon=icono, default=(i == 0))
                        for i, (archivo, titulo, icono) in enumerate(VISIBLES)])
comun.filtros_barra_lateral()
pagina.run()
