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

st.set_page_config(page_title="ACTHO · Tablero de afiliados", page_icon=str(AQUI / "recursos" / "icono_actho.png"),
                   layout="wide",
                   initial_sidebar_state="expanded")

import comun  # noqa: E402

comun.reiniciar_contadores()
comun.estilo()

import login  # noqa: E402

login.requerir_sesion()          # muestra el inicio de sesión si no hay sesión activa
comun.verificar_conexion()

# Menú agrupado por para quién es cada página (todas visibles).
SECCIONES = {
    "Resumen": [
        ("01_panel_general.py", "Dashboard", ":material/dashboard:"),
        ("06_pulso.py", "Pulso", ":material/monitor_heart:"),
    ],
    "Cartera": [
        ("09_base_afiliados.py", "Base de afiliados", ":material/monitoring:"),
        ("02_afiliados.py", "Afiliados", ":material/groups:"),
        ("03_ficha_360.py", "Ficha 360°", ":material/badge:"),
        ("04_renovacion.py", "Renovación y retención", ":material/autorenew:"),
    ],
    "Experiencias": [
        ("05_experiencias_nps.py", "Experiencias y NPS", ":material/event:"),
        ("10_planeacion_eventos.py", "Planeación de eventos", ":material/event_upcoming:"),
        ("07_segmentos.py", "Segmentos", ":material/campaign:"),
    ],
    "Datos": [
        ("08_datos_calidad.py", "Datos y calidad", ":material/fact_check:"),
        ("11_importar_datos.py", "Importar datos", ":material/upload_file:"),
    ],
}
comun.PAGINAS_ACTIVAS.clear()
comun.PAGINAS_ACTIVAS.update(archivo for paginas in SECCIONES.values() for archivo, _, _ in paginas)

pagina = st.navigation({seccion: [st.Page(AQUI / "paginas" / archivo, title=titulo, icon=icono,
                                          default=(archivo == "01_panel_general.py"))
                                  for archivo, titulo, icono in paginas]
                        for seccion, paginas in SECCIONES.items()})
comun.lateral_usuario()
pagina.run()
