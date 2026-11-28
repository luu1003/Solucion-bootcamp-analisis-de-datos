# -*- coding: utf-8 -*-
"""
Utilidades compartidas del tablero ACTHO (Streamlit + Plotly).

Replica el sistema de diseño de los wireframes de Figma y de actho.org:
  * Pantalla en menta, barra lateral morada con la cinta naranja y el lema en cian.
  * Tarjetas blancas (radio 20) con título morado y subtítulo naranja.
  * Tarjetas KPI: etiqueta en mayúsculas, valor, chip de tono y nota (variante oscura morada).
  * Encabezado de página con tres píldoras de estado en mayúsculas.
  * Panel derecho morado (Pulso) con tarjetas blancas y botón naranja tipo píldora.
  * Tablas con encabezado en mayúsculas y filas título + detalle + chip.
  * Gráficos con barras redondeadas en morado, lavanda y naranja, en Poppins.
"""
from __future__ import annotations

import base64
import html
import sys
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

# ──────────────────────────────────────────────────────────────────────────────
# Tokens de diseño (variables "ACTHO · Color" del archivo de Figma)
# ──────────────────────────────────────────────────────────────────────────────
C = {
    # Marca ACTHO
    "morado": "#5B00D9", "morado_700": "#5B00D9", "morado_500": "#7C3AED", "morado_900": "#2B0A6B",
    "morado_100": "#EFE6FF", "lavanda": "#EFE6FF", "lavanda_2": "#C9B2FF",
    "naranja": "#FF5A0F", "naranja_300": "#FF9A66", "naranja_suave": "#FFF0E8",
    "cian": "#22C7E8", "menta": "#EEF6F5", "blanco": "#FFFFFF",
    "tinta": "#1B1235", "gris": "#6E6787", "linea": "#E4E1EC",
    # Variantes de la marca que cumplen contraste WCAG 2.1 AA
    "naranja_texto": "#C2410C",   # texto naranja sobre blanco (5,2:1)
    "naranja_accion": "#D14800",  # fondo de botones con texto blanco (4,5:1)
    "cian_claro": "#8AE6F7",      # texto cian sobre morado (6,0:1)
    "cian_graf": "#0B8199",       # cian para gráficos sobre blanco (4,6:1)
    "lavanda_graf": "#9D75FF",    # lavanda para gráficos sobre blanco (3,3:1)
    # Estados (chips): texto ≥ 4,5:1 sobre su fondo
    "ok": "#0B6E4C", "ok_suave": "#DDF4EA", "alerta": "#8A4700", "alerta_suave": "#FFF0D6",
    "riesgo": "#A8360A", "riesgo_suave": "#FFF0E8",
    "morado_osc": "#2B0A6B",
}
# Una sola regla de color en todo el tablero: naranja = atender, lavanda = intermedio, morado = bien.
SEMAFORO = {"Rojo": C["naranja"], "Amarillo": C["lavanda_graf"], "Verde": C["morado"]}
SEM_TXT = {"Rojo": "Alto", "Amarillo": "Medio", "Verde": "Bajo"}
RIESGO = {SEM_TXT[k]: v for k, v in SEMAFORO.items()}          # mismos colores con la etiqueta visible
ORDEN_RIESGO = ["Alto", "Medio", "Bajo"]
NPS_COLOR = {"Detractor": C["naranja"], "Pasivo": C["lavanda_graf"], "Promotor": C["morado"]}
CONDICION = {"Afiliada": C["morado"], "No afiliada": C["cian_graf"]}
MODALIDAD = {"Presencial": C["morado"], "Virtual": C["naranja"], "Híbrido": C["cian_graf"], "Hibrido": C["cian_graf"]}
LINEA = {"Anticipar": C["morado"], "Evento grande": C["naranja"], "Foro": C["cian_graf"], "Pares": C["lavanda_graf"],
         "Proyectar": C["morado_900"], "Sin línea": C["gris"]}
SECUENCIA = [C["morado"], C["naranja"], C["cian_graf"], C["lavanda_graf"], C["morado_900"], C["naranja_300"]]
TONOS = {"OK": "ok", "Alerta": "alerta", "Riesgo": "riesgo", "Morado": "morado", "Neutro": "neutro", "IA": "ia"}


def riesgo_txt(s) -> str:
    """'Rojo' -> 'Alto'. El semáforo se guarda con colores y se muestra como nivel de riesgo."""
    return SEM_TXT.get(s, s if isinstance(s, str) else "Sin evaluar")
METAS_2027 = {"renovacion": 90.0, "nps": 55.0}
PAGINAS_ACTIVAS: set = set()   # la llena Inicio.py con las páginas visibles en el menú


def pagina_activa(archivo: str) -> bool:
    return archivo in PAGINAS_ACTIVAS

pio.templates["actho"] = go.layout.Template(layout=dict(
    font=dict(family="Poppins, sans-serif", color=C["tinta"], size=12),
    colorway=SECUENCIA, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor=C["linea"], zeroline=False, tickfont=dict(color=C["gris"], size=11)),
    yaxis=dict(gridcolor=C["linea"], griddash="dot", linecolor="rgba(0,0,0,0)", zeroline=False,
               tickfont=dict(color=C["gris"], size=11)),
    hoverlabel=dict(font_family="Poppins, sans-serif", bgcolor=C["morado_900"], font_color="#fff", bordercolor=C["morado_900"]),
    bargap=0.35,
))
pio.templates.default = "actho"

# Cinta naranja de actho.org (decoración de la barra lateral y del héroe)
_CINTA = ('<svg xmlns="http://www.w3.org/2000/svg" width="170" height="300" viewBox="0 0 170 300" fill="none">'
          '<path d="M160 -10C60 50 30 140 95 172C160 204 172 118 118 118C64 118 48 230 150 320" '
          'stroke="#FF5A0F" stroke-width="18" stroke-linecap="round"/></svg>')
CINTA_URI = "data:image/svg+xml;base64," + base64.b64encode(_CINTA.encode()).decode()

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
html, body, .stApp, [class*="css"], .stMarkdown, p, span, label, button, input, textarea, select, li, div {{
  font-family: 'Poppins', sans-serif; }}
code {{ font-family: ui-monospace, monospace !important; }}
.stApp {{ background: {C['menta']}; }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding: 1rem 1rem 2rem 1rem !important; max-width: 1480px; }}
[data-testid="stVerticalBlock"] {{ gap: .85rem; }}

/* ── Barra lateral (componente Sidebar) ── */
[data-testid="stSidebar"] {{ background: {C['morado']}; border-right: none; }}
[data-testid="stSidebar"] > div:first-child {{ background: url("{CINTA_URI}") no-repeat right -34px bottom 64px / 118px auto; }}
[data-testid="stSidebar"] * {{ color: #FFFFFF; }}
[data-testid="stSidebarNav"] {{ padding-top: .2rem; }}
[data-testid="stSidebarNav"] a {{ border-radius: 999px; padding: .3rem .85rem !important; margin: 1px 0 !important; min-height: 0 !important; line-height: 1.6; }}
[data-testid="stSidebarNav"] li {{ margin: 0 !important; }}
[data-testid="stSidebarNav"] a span {{ font-size: .9rem; font-weight: 500; color: #FFFFFF !important; }}
[data-testid="stSidebarNav"] a:hover {{ background: rgba(255,255,255,.12); }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: #FFFFFF; }}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"],
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] * {{ color: {C['morado']} !important; }}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] span {{ font-weight: 600 !important; }}
[data-testid="stNavSectionHeader"], [data-testid="stSidebarNav"] header, [data-testid="stSidebarNavSeparator"] + * {{ }}
[data-testid="stNavSectionHeader"] {{ color: {C['cian_claro']} !important; font-size: .72rem !important; font-weight: 600 !important;
  letter-spacing: .08em; text-transform: uppercase; margin-top: .8rem !important; }}
[data-testid="stNavSectionHeader"] * {{ color: {C['cian_claro']} !important; }}
[data-testid="stSidebarNavSeparator"] {{ border-color: rgba(255,255,255,.2); }}
[data-testid="stSidebarHeader"] {{ padding-top: 1.4rem; padding-bottom: .4rem; }}
[data-testid="stSidebarHeader"] img, [data-testid="stLogo"] {{ height: 2.9rem !important; max-width: 9rem; }}
[data-testid="stSidebar"] [data-testid="stExpander"] details {{ background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.18); border-radius: 16px; }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{ color: #fff; }}
[data-testid="stSidebar"] [data-baseweb="select"] > div, [data-testid="stSidebar"] [data-baseweb="input"] {{ background: #fff; border-radius: 12px; }}
[data-testid="stSidebar"] [data-baseweb="select"] *, [data-testid="stSidebar"] input,
[data-testid="stSidebar"] [data-baseweb="tag"] * {{ color: {C['tinta']} !important; }}
[data-testid="stSidebar"] [data-baseweb="tag"] {{ background: {C['lavanda']} !important; }}
[data-testid="stSidebar"] .stButton button {{ background: transparent; border: 1px solid rgba(255,255,255,.6); }}
.lema-lateral {{ color: {C['cian_claro']}; font-size: .8rem; font-weight: 500; margin: -.2rem 0 .2rem; }}
.usuario {{ display:flex; align-items:center; gap:.65rem; border-top: 1px solid rgba(255,255,255,.2); padding-top: .9rem; margin-top: .6rem; }}
.usuario .avatar {{ width: 36px; height: 36px; border-radius: 50%; background: #fff; color: {C['morado']} !important;
  display:flex; align-items:center; justify-content:center; font-weight: 700; font-size: .8rem; }}
.usuario b {{ display:block; font-size: .85rem; font-weight: 600; }} .usuario small {{ font-size: .72rem; color: {C['lavanda_2']} !important; }}

/* ── Encabezado de página ── */
.titulo {{ font-size: 1.75rem !important; font-weight: 700 !important; color: {C['tinta']} !important; margin: 0 !important; line-height: 1.15 !important; letter-spacing: -.01em; }}
.subtitulo {{ color: {C['gris']} !important; margin: .2rem 0 0 !important; font-size: .9rem !important; }}
.pildoras {{ display:flex; gap:.4rem; flex-wrap:nowrap; justify-content:flex-end; padding-top: .35rem; }}
.pildora {{ position: relative; display:inline-flex; align-items:center; gap:.38rem; border-radius: 999px;
  padding: .3rem .7rem .3rem .55rem; font-size: .7rem; font-weight: 500; background: #fff; cursor: default;
  border: 1px solid {C['linea']}; color: {C['tinta']}; white-space: nowrap; }}
.pildora[data-tip]:hover::after, .pildora[data-tip]:focus::after {{ content: attr(data-tip); position:absolute; right:0;
  top: calc(100% + 6px); width: 240px; white-space: normal; background:{C['tinta']}; color:#fff; font-size:.72rem;
  font-weight:400; line-height:1.4; padding:.5rem .65rem; border-radius:8px; z-index:1000; box-shadow:0 6px 18px rgba(0,0,0,.18); }}
.frescura {{ color: {C['gris']} !important; font-size: .74rem !important; margin: .35rem 0 0 !important; }}
.frescura b {{ color: {C['tinta']}; font-weight: 600; }}
.frescura .revisar {{ color: {C['naranja_texto']}; font-weight: 600; }}
.pildora b {{ font-weight: 700; }}
.pildora i {{ width: 9px; height: 9px; border-radius: 50%; display:inline-block; background: {C['gris']}; }}
.pildora.ok i {{ background: {C['cian_graf']}; }} .pildora.alerta i {{ background: {C['naranja']}; }}
.pildora.riesgo i {{ background: {C['naranja']}; }} .pildora.morado i {{ background: {C['morado']}; }}

/* ── Tarjetas (contenedores con borde) ── */
div[class*="st-key-tarjeta"] {{ background:#FFFFFF !important; border:none !important; border-radius:20px !important;
  padding: 1.05rem 1.2rem 1rem !important; box-shadow: none !important; }}
div[class*="st-key-tarjeta"] div[class*="st-key-tarjeta"] {{ padding: .4rem 0 0 !important; }}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{ }}
div[data-testid="stVerticalBlockBorderWrapper"][data-test-scroll-behavior], div[class*="st-key-tarjeta"],
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 20px !important; }}
[data-testid="stVerticalBlockBorderWrapper"]:not(:has([data-testid="stVerticalBlockBorderWrapper"])) {{ }}
.stVerticalBlock.st-key-x {{ }}
div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"][class*="border"] {{ }}
.cabeza {{ margin: 0 0 .35rem; }}
.cabeza h3 {{ font-size: 1.02rem !important; font-weight: 600 !important; color: {C['morado']} !important; margin: 0 !important; padding: 0 !important; line-height: 1.3 !important; }}
.cabeza p {{ font-size: .76rem !important; font-weight: 500 !important; color: {C['naranja_texto']} !important; margin: .1rem 0 0 !important; }}
.cabeza.oscura h3 {{ color: #fff !important; }} .cabeza.oscura p {{ color: {C['cian_claro']} !important; }}

/* ── KPI ── */
.kpi {{ background:#fff; border-radius: 20px; padding: 1rem 1.15rem; height: 100%; display:flex; flex-direction:column; gap:.3rem; }}
.kpi .et {{ font-size: .7rem; color: {C['gris']}; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; }}
.kpi .va {{ font-size: clamp(1.45rem, 2.1vw, 2rem); font-weight: 700; color: {C['tinta']}; line-height: 1.05; letter-spacing: -.02em; white-space: nowrap; }}
.kpi .et, .meta .et-meta {{ word-break: normal; overflow-wrap: normal; hyphens: manual; }}
.kpi .no {{ font-size: .74rem; color: {C['gris']}; line-height: 1.35; }}
.kpi.oscuro {{ background: {C['morado']}; }}
.kpi.oscuro .et {{ color: {C['lavanda_2']}; }} .kpi.oscuro .va {{ color: #fff; }} .kpi.oscuro .no {{ color: {C['lavanda_2']}; }}

/* ── Chips ── */
.chip {{ display:inline-block; border-radius:999px; padding:.18rem .6rem; font-size:.7rem; font-weight:600; letter-spacing:.02em;
  width: fit-content; max-width: 100%; white-space: normal; line-height: 1.35; overflow-wrap: anywhere; }}
.tabla .chip {{ white-space: nowrap; }}
.chip.ok, .chip.verde {{ background:{C['ok_suave']}; color:{C['ok']}; }}
.chip.alerta, .chip.amarillo {{ background:{C['alerta_suave']}; color:{C['alerta']}; }}
.chip.riesgo, .chip.rojo {{ background:{C['riesgo_suave']}; color:{C['riesgo']}; }}
.chip.morado {{ background:{C['lavanda']}; color:{C['morado']}; }}
.chip.neutro, .chip.gris {{ background:#F1EFF5; color:{C['gris']}; }}
.chip.ia {{ background:#E3F6FA; color:#075E70; }}
.chip.ia::before {{ content:'✦ '; }}
.kpi.oscuro .chip.ia {{ background: rgba(138,230,247,.18); color:{C['cian_claro']}; }}
.nota-ia {{ font-size:.74rem; color:{C['gris']}; margin:.15rem 0 .4rem; }}
.nota-ia b {{ color:#075E70; }}
.kpi.oscuro .chip.morado {{ background: rgba(255,255,255,.16); color:#fff; }}

/* ── Distribución: sin superposiciones ni alturas distintas ── */
/* Streamlit compensa el margen del último párrafo con margin-bottom:-16px; los componentes propios no lo tienen,
   así que se anula para que el bloque siguiente no se monte encima. */
[data-testid="stMarkdownContainer"]:has(.fila-tarjetas, .titulo, .subtitulo, .pildoras, .cabeza, .tabla, .heroe, .act,
  .hallazgo, .panel-titulo, .usuario, .lema-lateral, .login-hero, .login-titulo, .login-fila, .filtros-ayuda) {{ margin-bottom: 0 !important; }}
/* Tarjetas que comparten fila: todas con la altura de la más alta. */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:only-child > div[class*="st-key-tarjeta"]) {{
  align-items: stretch !important; }}
[data-testid="stColumn"] > [data-testid="stVerticalBlock"]:has(> [data-testid="stLayoutWrapper"]:only-child > div[class*="st-key-tarjeta"]),
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:only-child:has(> div[class*="st-key-tarjeta"]),
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:only-child > div[class*="st-key-tarjeta"] {{
  height: 100% !important; }}

/* ── Filas de tarjetas del mismo tipo (altura uniforme) ── */
.fila-tarjetas {{ display:grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); gap: .85rem; align-items: stretch; }}
@media (max-width: 1320px) {{ .kpi {{ padding: .9rem .9rem; }} .kpi .et {{ font-size: .66rem; letter-spacing: .03em; }} }}
.fila-tarjetas > div {{ height: 100%; min-width: 0; }}
@media (max-width: 1000px) {{ .fila-tarjetas {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
.et-meta {{ font-size: .7rem; color: {C['gris']}; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; }}

/* ── Metas 2027 ── */
.meta {{ background:#fff; border-radius:20px; padding:1rem 1.15rem; height:100%; }}
.meta .fila {{ display:flex; align-items:baseline; gap:.5rem; flex-wrap: wrap; margin-top:.3rem; }}
.meta .va {{ font-size: clamp(1.5rem, 2vw, 1.9rem); font-weight:700; color:{C['tinta']}; letter-spacing:-.02em; }}
.meta .obj {{ font-size:.78rem; color:{C['gris']}; }}
.meta .barra {{ height:10px; background:{C['menta']}; border-radius:999px; margin:.55rem 0 .45rem; overflow:hidden; }}
.meta .barra div {{ height:100%; border-radius:999px; background:{C['naranja']}; }}
.meta .no {{ font-size:.74rem; color:{C['gris']}; }}

/* ── Panel derecho morado ── */
div[class*="st-key-panel"] {{ background: {C['morado']}; border-radius: 20px; padding: 1.1rem 1rem 1rem; position: relative; overflow: hidden; }}
div[class*="st-key-panel"] div[class*="st-key-tarjeta"] {{ border-radius: 16px !important; padding: .9rem 1rem .8rem !important; }}
div[class*="st-key-panel"] .stMarkdown p, div[class*="st-key-panel"] label {{ color: #fff; }}
div[class*="st-key-panel"] div[class*="st-key-tarjeta"] .stMarkdown p {{ color: {C['tinta']}; }}
.panel-titulo {{ color:#fff !important; font-size:1.08rem !important; font-weight:600 !important; margin:0 !important; }}
.panel-lema {{ color:{C['cian_claro']} !important; font-size:.76rem !important; font-weight:500 !important; margin:.1rem 0 .3rem !important; }}
.act {{ background:#fff; border-radius:14px; padding:.7rem .85rem; margin-bottom:.55rem; }}
.act b {{ display:block; color:{C['tinta']}; font-size:.84rem; font-weight:600; line-height:1.3; }}
.act span {{ display:block; color:{C['gris']}; font-size:.75rem; line-height:1.35; margin-top:.15rem; }}
.act.acento {{ border-left: 4px solid {C['naranja']}; }}
.hallazgo {{ display:flex; gap:.6rem; align-items:stretch; background:{C['lavanda']}; border-radius:12px; padding:.65rem .8rem; margin-bottom:.5rem; }}
.hallazgo::before {{ content:''; width:4px; border-radius:2px; background:{C['morado']}; flex:none; }}
.hallazgo div {{ font-size:.82rem; color:{C['tinta']}; line-height:1.4; }}

/* ── Tabla HTML (componentes Tabla/Encabezado y Tabla/Fila) ── */
.tabla {{ width:100%; border-collapse:collapse; }}
.tabla th {{ white-space: nowrap; font-size:.7rem; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:{C['gris']};
  text-align:left; padding:.5rem .6rem; border-bottom:1px solid {C['linea']}; background:transparent; }}
.tabla td {{ font-size:.82rem; color:{C['tinta']}; padding:.55rem .6rem; border-bottom:1px solid {C['linea']}; vertical-align:middle; }}
.tabla td .t {{ font-weight:600; display:block; }} .tabla td .d {{ color:{C['gris']}; font-size:.74rem; display:block; }}
.tabla td.nw, .tabla td.nw .t, .tabla td.nw .d {{ white-space: nowrap; }}
.tabla tr:last-child td {{ border-bottom:none; }} .tabla td.num {{ text-align:right; font-variant-numeric: tabular-nums; }}

/* ── Héroe (tarjeta morada "Pregúntale a Pulso") ── */
.heroe {{ background:{C['morado']} url("{CINTA_URI}") no-repeat right 30px top -60px / 150px auto; border-radius:20px; padding:1.3rem 1.5rem; }}
.heroe .lema {{ color:{C['cian_claro']}; font-size:.8rem; font-weight:500; }}
.heroe h2 {{ color:#fff !important; font-size:1.35rem !important; font-weight:700 !important; margin:.2rem 0 .2rem !important; padding:0 !important; }}
.heroe p {{ color:{C['lavanda_2']} !important; font-size:.85rem !important; max-width: 70%; margin:0 !important; }}

/* ── Controles ── */
.stButton button, .stDownloadButton button {{ border-radius: 999px !important; font-weight: 600 !important; padding: .45rem 1.2rem !important; }}
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"], button[data-testid="stBaseButton-primary"] {{
  background: {C['naranja_accion']} !important; border-color: {C['naranja_accion']} !important; color: #fff !important; }}
.stButton button[kind="primary"]:hover, .stDownloadButton button[kind="primary"]:hover {{ background: {C['riesgo']} !important; border-color: {C['riesgo']} !important; }}
button[data-testid="stBaseButton-secondary"] {{ background: #fff; color: {C['morado']}; border-color: {C['lavanda_2']}; }}
[data-baseweb="select"] > div, [data-baseweb="input"], .stTextInput input, .stDateInput input {{ border-radius: 12px !important; }}
[data-testid="stMain"] [data-baseweb="select"] > div, [data-testid="stMain"] [data-baseweb="input"] {{ background:#fff; border-color:{C['linea']}; }}
[data-testid="stWidgetLabel"] p {{ font-size: .74rem !important; font-weight: 600 !important; color: {C['gris']} !important; text-transform: uppercase; letter-spacing: .05em; }}
div[class*="st-key-panel"] [data-testid="stWidgetLabel"] p {{ color: {C['lavanda_2']} !important; }}
.stTabs [data-baseweb="tab-list"] {{ gap: .4rem; border-bottom: none; }}
.stTabs [data-baseweb="tab"] {{ background:#fff; border-radius:999px; padding:.4rem 1rem; height:auto; }}
.stTabs [data-baseweb="tab"] p {{ font-weight:600; font-size:.85rem; color:{C['morado']}; }}
.stTabs [aria-selected="true"] {{ background:{C['morado']}; }} .stTabs [aria-selected="true"] p {{ color:#fff !important; }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display:none; }}
/* Pestañas (Streamlit ≥ 1.6x: data-testid="stTab") como píldoras */
[data-testid="stTabs"] [role="tablist"] {{ gap: .45rem; border: none !important; box-shadow: none !important; flex-wrap: wrap; }}
[data-testid="stTabs"] [role="tablist"]::after, [data-testid="stTabs"] [role="tablist"]::before {{ display: none !important; }}
[data-testid="stTab"] {{ background:#fff; border-radius:999px; padding:.5rem 1.15rem !important; height:auto !important;
  border: 1px solid {C['linea']}; cursor: pointer; }}
[data-testid="stTab"] p {{ font-weight:600 !important; font-size:.88rem !important; color:{C['morado']} !important; margin:0 !important; }}
[data-testid="stTab"]:hover {{ border-color: {C['lavanda_graf']}; }}
[data-testid="stTab"][aria-selected="true"] {{ background:{C['morado']}; border-color:{C['morado']}; }}
[data-testid="stTab"][aria-selected="true"] p {{ color:#fff !important; }}
[data-testid="stTab"] > div:not([data-testid]) {{ display:none !important; }}
[data-testid="stSegmentedControl"] button, [data-testid="stButtonGroup"] button {{ border-radius: 999px !important; background:#fff; }}
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[kind*="Active"] {{
  background:{C['morado']} !important; color:#fff !important; border-color:{C['morado']} !important; }}
[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
[data-testid="stMain"] [data-testid="stExpander"] details {{ background:#fff; border:none; border-radius:20px; }}
[data-testid="stMain"] [data-testid="stExpander"] summary p {{ color:{C['morado']}; font-weight:600; }}
[data-testid="stAlert"] {{ border-radius: 14px; }}
[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) > div {{ background: {C['lavanda']} !important; color: {C['tinta']} !important; }}
[data-testid="stAlertContentInfo"] p, [data-testid="stAlertContentInfo"] svg {{ color: {C['morado_900']} !important; fill: {C['morado']} !important; font-size: .9rem; }}
[data-testid="stCaptionContainer"] {{ color: {C['gris']}; }}

/* ── Chips del nivel de riesgo: punto del mismo color del gráfico + texto (no depende solo del color) ── */
.chip.sem {{ background:#F1EFF5; color:{C['tinta']}; display:inline-flex; align-items:center; gap:.35rem; }}
.chip.sem::before {{ content:''; width:8px; height:8px; border-radius:50%; background: var(--c); flex:none; }}
.chip.sem.alto {{ background:{C['naranja_suave']}; color:{C['riesgo']}; }}
.kpi.oscuro .chip.sem {{ background: rgba(255,255,255,.16); color:#fff; }}

/* ── Barra de filtros sobre el panel ── */
div[class*="st-key-barra_filtros"] {{ background:#FFFFFF; border-radius:20px; padding: .75rem 1rem .55rem !important; gap: .35rem !important; }}
div[class*="st-key-barra_filtros"] [data-testid="stHorizontalBlock"] {{ gap: .6rem !important; align-items: flex-end; }}
div[class*="st-key-barra_filtros"] [data-baseweb="select"] > div, div[class*="st-key-barra_filtros"] [data-baseweb="input"] {{
  background: {C['menta']} !important; border-color: transparent !important; min-height: 40px; }}
div[class*="st-key-barra_filtros"] [data-baseweb="tag"] {{ background: {C['lavanda']} !important; }}
div[class*="st-key-barra_filtros"] [data-baseweb="tag"] span {{ color: {C['morado']} !important; font-weight: 600; }}
div[class*="st-key-barra_filtros"] .stButton button {{ min-height: 40px; white-space: nowrap; }}
.filtros-ayuda {{ font-size: .76rem; color: {C['gris']}; margin: 0; display:flex; align-items:center; gap:.4rem; }}
.filtros-ayuda b {{ color: {C['morado']}; font-weight: 600; }}
div[class*="st-key-xf_activos"] [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap; gap: .4rem !important; align-items: center; }}
div[class*="st-key-xf_activos"] [data-testid="stColumn"] {{ width: auto !important; flex: 0 0 auto !important; min-width: 0 !important; }}
div[class*="st-key-xf_quitar"] button {{ background: {C['morado']} !important; color:#fff !important; border-color: {C['morado']} !important;
  padding: .2rem .8rem !important; min-height: 0 !important; font-size: .76rem !important; }}
div[class*="st-key-xf_quitar"] button p {{ font-size: .76rem !important; }}
div[class*="st-key-limpiar_filtros"] button {{ padding: .2rem .8rem !important; min-height: 0 !important; }}
div[class*="st-key-limpiar_filtros"] button p {{ font-size: .76rem !important; }}

/* ── Gráficos interactivos: cursor de clic, como en Power BI ── */
div[class*="st-key-gi_"] .nsewdrag, div[class*="st-key-gi_"] .pielayer path, div[class*="st-key-gi_"] .hm {{ cursor: pointer !important; }}

/* ── Ícono de ayuda con la definición del indicador (hover o foco con teclado) ── */
.kpi, .meta {{ position: relative; }}
.ayuda {{ display:inline-flex; align-items:center; justify-content:center; width:16px; height:16px; margin-left:.35rem;
  border-radius:50%; background:{C['lavanda']}; color:{C['morado']}; font-size:.62rem; font-weight:700; cursor:help;
  vertical-align: middle; position: relative; text-transform:none; letter-spacing:0; }}
.kpi.oscuro .ayuda {{ background: rgba(255,255,255,.2); color:#fff; }}
.ayuda.info {{ background:#E3F6FA; color:#075E70; font-style:italic; font-family: Georgia, serif; font-weight:700;
  text-transform:none; letter-spacing:0; vertical-align: middle; }}
.cabeza h3 .ayuda {{ font-size:.72rem; }}
.ayuda.info:hover::after, .ayuda.info:focus::after {{ font-style:normal; font-family: inherit; font-weight:400;
  text-transform:none; letter-spacing:0; width: 260px; white-space: normal; text-align:left; font-family: 'Poppins', sans-serif; }}
.ayuda:hover::after, .ayuda:focus::after {{ content: attr(data-tip); position:absolute; left:50%; top:22px; transform:translateX(-50%);
  width: 260px; background:{C['morado_900']}; color:#fff; font-size:.74rem; font-weight:400; line-height:1.4;
  padding:.6rem .7rem; border-radius:10px; z-index:1000; text-align:left; white-space:normal; box-shadow:0 8px 24px rgba(43,10,107,.25); }}
div[class*="st-key-acciones_encabezado"] {{ display:flex; justify-content:flex-start; margin-top:.55rem; }}
div[class*="st-key-acciones_encabezado"] [data-testid="stHorizontalBlock"] {{ justify-content:flex-start; }}
div[class*="st-key-acciones_encabezado"] [data-testid="stElementContainer"] {{ width:auto !important; }}

/* ── Accesibilidad: foco visible al navegar con teclado (WCAG 2.4.7) ── */
a:focus-visible, button:focus-visible, [role="tab"]:focus-visible, input:focus-visible, [tabindex]:focus-visible {{
  outline: 3px solid {C['naranja']} !important; outline-offset: 2px !important; }}
[data-testid="stSidebar"] a:focus-visible, [data-testid="stSidebar"] button:focus-visible {{ outline-color: {C['cian_claro']} !important; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; animation: none !important; }} }}
</style>
"""


# ──────────────────────────────────────────────────────────────────────────────
# Datos
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _url():
    from cargar_postgres import cadena_conexion
    return cadena_conexion()


def _a_df(cur) -> pd.DataFrame:
    filas = cur.fetchall()
    df = pd.DataFrame(filas, columns=[d.name for d in cur.description])
    for c in df.columns:
        muestra = df[c].dropna()
        if not muestra.empty:
            v = muestra.iloc[0]
            if isinstance(v, Decimal):
                df[c] = pd.to_numeric(df[c], errors="coerce")
            elif isinstance(v, date):
                df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


@st.cache_data(ttl=300, show_spinner=False)
def consulta(sql: str, params: tuple = ()) -> pd.DataFrame:
    import psycopg
    with psycopg.connect(_url(), connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return _a_df(cur)


def tabla(nombre: str, esquema: str = "actho") -> pd.DataFrame:
    return consulta(f"SELECT * FROM {esquema}.{nombre}")


def existe(objeto: str) -> bool:
    try:
        return bool(consulta("SELECT to_regclass(%s) IS NOT NULL AS ok", (objeto,))["ok"].iloc[0])
    except Exception:  # noqa: BLE001
        return False


def verificar_conexion():
    """Detiene la página con instrucciones claras si la base no está lista."""
    try:
        url = _url()
    except Exception as e:  # noqa: BLE001
        url, err = None, e
    if not url:
        st.error("No hay conexión configurada a PostgreSQL.")
        st.markdown("Copia `.env.ejemplo` como `.env`, enciende la base (`docker compose up -d postgres`) "
                    "y corre `python3 setup.py`.")
        st.stop()
    try:
        ok = existe("actho.v_empresa_360")
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudo conectar a PostgreSQL: {e}")
        st.stop()
    if not ok:
        st.warning("La base está conectada pero aún no tiene datos. Corre `python3 setup.py` "
                   "o lanza el DAG `actho_ingesta_datos` en Airflow.")
        st.stop()


@st.cache_data(ttl=300, show_spinner=False)
def empresas() -> pd.DataFrame:
    df = tabla("v_empresa_360")
    # Mes de vencimiento (las ya vencidas cuentan en el mes de corte): dimensión del filtro cruzado
    corte = pd.Timestamp(df["fecha_corte"].dropna().iloc[0]) if df["fecha_corte"].notna().any() else pd.Timestamp.today()
    fx = pd.to_datetime(df["fecha_expiracion"])
    df["mes_venc"] = fx.where(fx >= corte, corte).dt.strftime("%Y-%m").where(fx.notna())
    df["riesgo"] = df["semaforo"].map(SEM_TXT)
    df["mes_alta"] = pd.to_datetime(df["fecha_afiliacion"]).dt.strftime("%Y-%m")
    return df


@st.cache_data(ttl=300, show_spinner=False)
def asistencia() -> pd.DataFrame:
    return tabla("v_asistencia_detalle")


@st.cache_data(ttl=300, show_spinner=False)
def encuestas() -> pd.DataFrame:
    df = tabla("v_encuesta_detalle")
    extra = consulta("SELECT encuesta_id, lo_que_gusto, a_mejorar, temas_solicitados, calif_recepcion, "
                     "calif_manejo_tiempo FROM actho.fact_encuesta_evento")
    return df.merge(extra, on="encuesta_id", how="left")


@st.cache_data(ttl=300, show_spinner=False)
def uso_beneficios() -> pd.DataFrame:
    """Una fila por uso de un beneficio (asistencia, comunidades, encuesta de 90 días, plantilla mensual)."""
    if not existe("actho.v_uso_beneficio_detalle"):
        return pd.DataFrame(columns=["empresa_id", "servicio", "linea_servicio", "fecha", "fuente", "es_fechado", "anio_mes"])
    return tabla("v_uso_beneficio_detalle")


@st.cache_data(ttl=300, show_spinner=False)
def catalogo() -> pd.DataFrame:
    return tabla("dim_servicio") if existe("actho.dim_servicio") else pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def relacion() -> pd.DataFrame:
    """Respuestas de la encuesta de relación a 90 días (sin pruebas)."""
    if not existe("actho.v_encuesta_relacion_detalle"):
        return pd.DataFrame(columns=["empresa_id", "fecha", "nps_actho", "nps_categoria", "intencion_renovar"])
    return tabla("v_encuesta_relacion_detalle")


@st.cache_data(ttl=300, show_spinner=False)
def definiciones() -> pd.DataFrame:
    if not existe("actho.definicion_indicador"):
        return pd.DataFrame(columns=["orden", "indicador", "definicion", "calculo", "fuente", "estado"])
    return consulta("SELECT * FROM actho.definicion_indicador ORDER BY orden")


def ayuda(indicador: str) -> str:
    """Definición acordable del indicador (tabla actho.definicion_indicador) para el ícono de ayuda."""
    d = definiciones()
    fila = d[d["indicador"] == indicador]
    if fila.empty:
        return ""
    f = fila.iloc[0]
    extra = f" Cálculo: {f['calculo']}" if isinstance(f["calculo"], str) and f["calculo"] else ""
    return f"{f['definicion']}{extra} ({'definición acordada' if f['estado'] == 'Acordada' else 'propuesta por validar con ACTHO'})"


@st.cache_data(ttl=300, show_spinner=False)
def renovacion_medida() -> pd.DataFrame:
    if not existe("historial.v_renovacion_medida"):
        return pd.DataFrame()
    return consulta("SELECT * FROM historial.v_renovacion_medida")


def tasa_renovacion(e: pd.DataFrame) -> dict:
    """Tasa de renovación sobre las empresas filtradas. Usa la medida (fotos mensuales) cuando ya hay
    renovaciones registradas en los últimos 12 meses; si no, la aproximada."""
    ids = set(e["empresa_id"])
    rm = renovacion_medida()
    if len(rm):
        corte = pd.Timestamp(parametros()["fecha_corte"])
        rm = rm[pd.to_datetime(rm["periodo"]) > corte - pd.DateOffset(months=12)]
        rm = rm.sort_values("periodo").drop_duplicates(["empresa_id", "expiracion_anterior"], keep="last")
        rm = rm[rm["empresa_id"].isin(ids) & rm["resultado"].isin(["Renovó", "No renovó"])]
        if len(rm):
            si, no = (rm["resultado"] == "Renovó").sum(), (rm["resultado"] == "No renovó").sum()
            return dict(tasa=100 * si / (si + no), renovo=int(si), no_renovo=int(no), tipo="medida",
                        nota=f"Medida con fotos mensuales: {fmt(si)} renovaron y {fmt(no)} no, de las que vencían")
    sub = e[e["en_crm"] == 1] if "en_crm" in e else e
    si, no = (sub["renovacion_aprox"] == "Renovó").sum(), (sub["renovacion_aprox"] == "No renovó").sum()
    tasa = 100 * si / (si + no) if (si + no) else None
    return dict(tasa=tasa, renovo=int(si), no_renovo=int(no), tipo="aproximada",
                nota=f"Aproximada: {fmt(si)} renovados y {fmt(no)} no renovados en 12 meses")


@st.cache_data(ttl=300, show_spinner=False)
def parametros() -> dict:
    return tabla("v_parametros").iloc[0].to_dict()


@st.cache_data(ttl=300, show_spinner=False)
def ultima_carga():
    if not existe("ingesta.ejecucion"):
        return None
    df = consulta("SELECT fin, estado FROM ingesta.ejecucion WHERE estado = 'procesado' ORDER BY fin DESC LIMIT 1")
    return None if df.empty else df.iloc[0]["fin"]


# ──────────────────────────────────────────────────────────────────────────────
# Filtros globales (barra sobre el panel) y filtro cruzado (clic en los gráficos)
# ──────────────────────────────────────────────────────────────────────────────
FILTROS = [("nivel_2027", "Nivel 2027"), ("tipo_membresia", "Tipo de afiliado"), ("sector", "Sector"),
           ("ciudad", "Ciudad"), ("ejecutiva", "Ejecutiva")]

# Dimensiones del filtro cruzado: columna -> (etiqueta, alcance). 'emp' filtra empresas; 'det' filtra
# asistencias o encuestas (y, por la empresa, todo lo demás), como una relación de Power BI.
XF_DIMS = {
    "semaforo": ("Riesgo", "emp"), "nivel_2027": ("Nivel", "emp"), "mes_venc": ("Vence en", "emp"),
    "ejecutiva": ("Ejecutiva", "emp"), "tipo_membresia": ("Tipo", "emp"), "sector": ("Sector", "emp"),
    "tamano_empresa": ("Tamaño", "emp"), "ciudad": ("Ciudad", "emp"), "mes_alta": ("Afiliada en", "emp"),
    "anio_mes": ("Mes", "det"), "servicio": ("Beneficio", "det"), "fuente": ("Fuente", "det"), "condicion_empresa": ("Empresa", "det"), "linea_2027": ("Línea", "det"),
    "modalidad": ("Modalidad", "det"), "nivel_cargo": ("Cargo", "det"), "nps_categoria": ("NPS", "det"),
}


def _g(col):
    """Valor vigente de un filtro global (se guarda aparte del widget para que se conserve entre páginas)."""
    return st.session_state.get(f"g_{col}")


def _sincronizar(col):
    st.session_state[f"g_{col}"] = st.session_state.get(f"w_{col}")


def xf() -> dict:
    return st.session_state.setdefault("xf", {})


def valor_txt(dim, v) -> str:
    if dim == "semaforo":
        return riesgo_txt(v)
    if dim in ("mes_venc", "anio_mes", "mes_alta"):
        return anio_mes_txt(v)
    return str(v)


def _limpiar_todo(fmin, fmax):
    for col, _ in FILTROS:
        st.session_state[f"g_{col}"] = []
        st.session_state[f"w_{col}"] = []
    st.session_state["g_periodo"] = (fmin, fmax)
    st.session_state["w_periodo"] = (fmin, fmax)
    xf().clear()
    st.session_state["xf_ver"] = st.session_state.get("xf_ver", 0) + 1


def _quitar_xf(dim):
    xf().pop(dim, None)
    st.session_state["xf_ver"] = st.session_state.get("xf_ver", 0) + 1


def barra_filtros():
    """Filtros globales sobre el contenido (periodo, nivel, tipo, sector, ciudad y ejecutiva) y, debajo,
    los filtros activos por clic en los gráficos. Se conservan al cambiar de página."""
    e = empresas()
    vig = e[e["es_vigente"] == 1]
    a = asistencia()
    corte = pd.Timestamp(parametros()["fecha_corte"])
    fmin, fmax = a["fecha_evento"].min().date(), max(a["fecha_evento"].max(), corte).date()
    st.session_state.setdefault("g_periodo", (fmin, fmax))
    with st.container(key="barra_filtros"):
        cols = st.columns([1.95, 1, 1, 1.1, 1, 1])
        st.session_state["w_periodo"] = _g("periodo")
        cols[0].date_input("Periodo", key="w_periodo", min_value=date(2025, 1, 1), max_value=date(2027, 12, 31),
                           format="DD/MM/YYYY", on_change=lambda: (
                               st.session_state.__setitem__("g_periodo", st.session_state["w_periodo"])
                               if len(st.session_state.get("w_periodo") or ()) == 2 else None))
        for i, (col, et) in enumerate(FILTROS, start=1):
            opciones = sorted(vig[col].dropna().unique().tolist())
            st.session_state[f"w_{col}"] = [v for v in (_g(col) or []) if v in opciones]
            cols[i].multiselect(et, opciones, key=f"w_{col}", placeholder="Todos", on_change=_sincronizar, args=(col,))
        hay = hay_filtros_empresa() or bool(xf()) or tuple(_g("periodo") or ()) != (fmin, fmax)
        izq, der = st.columns([6, 1], vertical_alignment="center")
        activos = xf()
        with izq:
            if activos:
                with st.container(key="xf_activos"):
                    chips = st.columns(len(activos) + 1)
                    chips[0].markdown('<p class="filtros-ayuda"><b>Filtrado por clic:</b></p>', unsafe_allow_html=True)
                    for j, (dim, v) in enumerate(list(activos.items()), start=1):
                        chips[j].button(f"{XF_DIMS[dim][0]}: {valor_txt(dim, v)}", key=f"xf_quitar_{dim}",
                                        icon=":material/close:", on_click=_quitar_xf, args=(dim,),
                                        help=f"Quitar el filtro de {XF_DIMS[dim][0].lower()}")
            else:
                st.markdown('<p class="filtros-ayuda">Clic en una barra, segmento o punto de un gráfico para filtrar '
                            'todo el tablero; otro clic lo quita.</p>', unsafe_allow_html=True)
        der.button("Limpiar", key="limpiar_filtros", icon=":material/filter_alt_off:", disabled=not hay,
                   on_click=_limpiar_todo, args=(fmin, fmax), help="Quita todos los filtros", **ancho(st.button))


def lateral_usuario():
    """Barra lateral: lema, usuario y cierre de sesión (la navegación la pone st.navigation)."""
    with st.sidebar:
        st.markdown('<p class="lema-lateral">Sentimos el pulso.</p>', unsafe_allow_html=True)
        sesion = st.session_state.get("sesion") or {"nombre": "Equipo ACTHO", "rol": "Dirección Ejecutiva"}
        iniciales = "".join(p[0] for p in sesion["nombre"].split()[:2]).upper() or "A"
        st.markdown(f'<div class="usuario"><span class="avatar" aria-hidden="true">{_e(iniciales)}</span><div><b>{_e(sesion["nombre"])}</b>'
                    f'<small>{_e(sesion.get("rol", ""))}</small></div></div>', unsafe_allow_html=True)
        if st.session_state.get("sesion") and st.button("Cerrar sesión", key="cerrar_sesion", icon=":material/logout:",
                                                        **ancho(st.button)):
            import login
            login.cerrar_sesion()


def ancho(funcion=None):
    """Argumentos de ancho completo según lo que acepte cada función de Streamlit (1.50 a 1.6x)."""
    import inspect
    params = inspect.signature(funcion or st.button).parameters
    if "width" in params:
        return {"width": "stretch"}
    if "use_container_width" in params:
        return {"use_container_width": True}
    return {}


MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def partir(texto: str, ancho: int = 24, max_lineas: int = 2) -> str:
    """Parte una etiqueta larga en líneas (<br>) para que no se corte en los ejes."""
    palabras, lineas, actual = str(texto).split(), [], ""
    for p_ in palabras:
        if len(actual) + len(p_) + 1 > ancho and actual:
            lineas.append(actual)
            actual = p_
        else:
            actual = f"{actual} {p_}".strip()
    lineas.append(actual)
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        lineas[-1] = lineas[-1][:ancho - 1].rstrip() + "…"
    return "<br>".join(lineas)


def mes_txt(f) -> str:
    """Timestamp -> 'nov 26' (etiqueta de mes en español para los ejes)."""
    f = pd.Timestamp(f)
    return f"{MESES[f.month - 1]} {str(f.year)[2:]}"


def anio_mes_txt(v: str) -> str:
    """'2026-03' -> 'mar 26'."""
    try:
        return mes_txt(pd.Timestamp(str(v) + "-01"))
    except Exception:  # noqa: BLE001
        return str(v)


def _desvanecer(color: str, alfa=0.28) -> str:
    color = str(color)
    if color.startswith("#") and len(color) == 7:
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
        return f"rgba({r},{g},{b},{alfa})"
    return color


def _resaltar(fig, dims):
    """Como en Power BI: el gráfico que origina el filtro no se filtra a sí mismo; resalta lo elegido y
    atenúa el resto."""
    act = {d: xf()[d] for d in dims if d in xf()}
    if not act:
        return
    for tr in fig.data:
        cd = getattr(tr, "customdata", None)
        if cd is None or tr.type == "heatmap":
            continue
        sel = [all(str(fila[i]) == str(act[d]) for i, d in enumerate(dims) if d in act) for fila in cd]
        if tr.type == "bar":
            tr.marker.opacity = [1 if s_ else 0.28 for s_ in sel]
        elif tr.type == "pie":
            base = list(tr.marker.colors) if tr.marker.colors is not None else SECUENCIA
            tr.marker.colors = [c_ if s_ else _desvanecer(c_) for c_, s_ in zip(base, sel)]
            tr.pull = [0.06 if s_ else 0 for s_ in sel]
        elif tr.type == "scatter" and tr.marker.symbol == "square":      # mapa de calor: lo resalta su página
            continue
        elif tr.type == "scatter":
            tr.marker.size = [13 if s_ else 7 for s_ in sel]
            tr.marker.line = dict(width=[3 if s_ else 0 for s_ in sel], color="#FFFFFF")


def _al_clic(clave, dims):
    """Callback del clic: fija (o quita, si se repite) los valores del punto en el filtro cruzado."""
    ev = st.session_state.get(clave)
    try:
        puntos = ev["selection"]["points"]
    except Exception:  # noqa: BLE001
        puntos = []
    if not puntos:
        return
    pt = puntos[0]
    cd = pt.get("customdata")
    if cd is None:
        cd = [pt.get("label")]
    if not isinstance(cd, (list, tuple)):
        cd = [cd]
    valores = {d: v for d, v in zip(dims, cd) if v is not None and str(v) not in ("", "nan", "None")}
    if not valores:
        return
    f = xf()
    if all(f.get(d) == v for d, v in valores.items()):
        for d in valores:
            f.pop(d, None)
    else:
        f.update(valores)
    st.session_state["xf_ver"] = st.session_state.get("xf_ver", 0) + 1


def grafico(fig, altura=320, sub=None, oscuro=False, dims=None, clave=None):
    """Dibuja un gráfico con el estilo de los wireframes: el título de la figura se muestra como
    encabezado de tarjeta (morado + subtítulo naranja), barras redondeadas y leyenda abajo.
    Con dims (y customdata en el mismo orden), un clic filtra todo el tablero por esos valores."""
    titulo = fig.layout.title.text if fig.layout.title and fig.layout.title.text else None
    if titulo:
        cabeza(titulo, sub, oscuro)
    # Leyenda arriba a la izquierda (como en Power BI): no choca con los títulos de los ejes
    con_leyenda = any(t.type == "pie" for t in fig.data) or \
        len([t for t in fig.data if t.showlegend is not False and t.name]) > 1
    if fig.layout.showlegend is False:
        con_leyenda = False
    fig.update_layout(title=None, height=altura, legend_title_text="", paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                      showlegend=con_leyenda,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                                  font=dict(size=12, color=C["tinta"]), itemclick=False, itemdoubleclick=False),
                      margin=dict(l=6, r=6, t=34 if con_leyenda else 8, b=6), separators=",.")
    try:
        fig.update_layout(barcornerradius=6)
    except Exception:  # noqa: BLE001  (Plotly < 5.19)
        pass
    if any(getattr(t, "orientation", None) == "h" for t in fig.data):
        fig.update_yaxes(ticksuffix="  ")      # aire entre la etiqueta y la barra
    fig.update_xaxes(automargin=True, title_font=dict(size=12, color=C["gris"]), tickfont=dict(size=12, color=C["gris"]))
    fig.update_yaxes(automargin=True, title_font=dict(size=12, color=C["gris"]), tickfont=dict(size=12, color=C["gris"]))
    config = {"displayModeBar": False, "locale": "es"}
    if dims:
        _resaltar(fig, dims)
        fig.update_layout(dragmode=False, clickmode="event+select", hovermode="closest")
        k = f"gi_{clave or '_'.join(dims)}_{st.session_state.get('xf_ver', 0)}"
        st.plotly_chart(fig, config=config, theme=None, key=k, on_select=lambda: _al_clic(k, dims),
                        selection_mode="points", **ancho(st.plotly_chart))
    else:
        fig.update_layout(dragmode=False)
        st.plotly_chart(fig, config=config, theme=None, **ancho(st.plotly_chart))


def periodo():
    p = _g("periodo")
    if isinstance(p, (list, tuple)) and len(p) == 2:
        return pd.Timestamp(p[0]), pd.Timestamp(p[1])
    return None, None


def _activos(alcance, excluir=()):
    return {d: v for d, v in xf().items() if XF_DIMS[d][1] == alcance and d not in excluir}


def _por_fecha(df, col_fecha):
    ini, fin = periodo()
    if ini is not None:
        f = pd.to_datetime(df[col_fecha])
        dentro = (f >= ini) & (f <= fin)
        if "es_fechado" in df.columns:      # vinculaciones vigentes (comunidades) no dependen del periodo
            dentro = dentro | (df["es_fechado"] == 0)
        df = df[dentro]
    return df


def _aplicar(df, filtros):
    for d, v in filtros.items():
        if d in df.columns:
            df = df[df[d].astype(str) == str(v)]
    return df


def _ids_detalle(excluir=()):
    """Empresas con actividad que cumple los filtros cruzados de asistencia o encuestas (None si no hay)."""
    det = _activos("det", excluir)
    if not det:
        return None
    ids = set()
    for df, col in ((asistencia(), "fecha_evento"), (encuestas(), "fecha_respuesta"), (uso_beneficios(), "fecha")):
        if any(d in df.columns for d in det):
            ids |= set(_aplicar(_por_fecha(df, col), det)["empresa_id"].dropna())
    return ids


def filtrar_empresas(df: pd.DataFrame, excluir=()) -> pd.DataFrame:
    """Filtros globales + filtro cruzado. 'excluir' deja fuera las dimensiones del gráfico que se dibuja."""
    for col, _ in FILTROS:
        sel = _g(col)
        if sel:
            df = df[df[col].isin(sel)]
    df = _aplicar(df, _activos("emp", excluir))
    ids = _ids_detalle(excluir)
    if ids is not None:
        df = df[df["empresa_id"].isin(ids)]
    return df


def hay_filtros_empresa(excluir=()) -> bool:
    return any(_g(c) for c, _ in FILTROS) or bool(_activos("emp", excluir)) or bool(_activos("det", excluir))


def filtrar_detalle(df: pd.DataFrame, col_fecha: str, excluir=()) -> pd.DataFrame:
    df = _por_fecha(df, col_fecha)
    det = _activos("det", excluir)
    df = _aplicar(df, det)
    if any(_g(c) for c, _ in FILTROS) or _activos("emp", excluir) or any(d not in df.columns for d in det):
        ids = set(filtrar_empresas(empresas(), excluir)["empresa_id"])
        df = df[df["empresa_id"].isin(ids)]
    return df


def datos_uso(excluir=()) -> pd.DataFrame:
    """Uso de beneficios con todos los filtros (las comunidades vigentes no dependen del periodo)."""
    return filtrar_detalle(uso_beneficios(), "fecha", excluir)


def datos(excluir=()):
    """(empresas, asistencia, encuestas) con todos los filtros, menos las dimensiones de 'excluir'."""
    return (filtrar_empresas(empresas(), excluir), filtrar_detalle(asistencia(), "fecha_evento", excluir),
            filtrar_detalle(encuestas(), "fecha_respuesta", excluir))


# ──────────────────────────────────────────────────────────────────────────────
# Componentes
# ──────────────────────────────────────────────────────────────────────────────
def estilo():
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        st.logo(str(Path(__file__).parent / "recursos" / "logo.svg"), size="large")
    except Exception:  # noqa: BLE001
        pass


def fmt(n, dec=0, sufijo=""):
    if n is None or (isinstance(n, float) and pd.isna(n)):
        return "—"
    txt = f"{n:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return txt + sufijo


def fecha_txt(f) -> str:
    if f is None or pd.isna(f):
        return "—"
    f = pd.Timestamp(f)
    return f"{f.day} {MESES[f.month - 1]} {f.year}"


def _e(t) -> str:
    return html.escape(str(t))


def pildoras_negocio() -> list:
    """Tres señales del negocio para el encabezado (toda la base, sin filtros): cartera vigente, renovación
    frente a la meta y renovaciones de los próximos 60 días. Cada una trae su explicación al pasar el cursor."""
    e = empresas()
    corte = pd.Timestamp(parametros()["fecha_corte"])
    vig = e[e["es_vigente"] == 1]
    nuevas = int((pd.to_datetime(vig["fecha_afiliacion"]) >= corte - pd.Timedelta(days=30)).sum())
    ren = tasa_renovacion(e)
    tasa, meta = ren.get("tasa"), METAS_2027["renovacion"]
    dias = pd.to_numeric(vig["dias_a_vencer"], errors="coerce")
    vencen = int(((dias >= 0) & (dias <= 60)).sum())
    return [
        ("Morado", f"<b>{fmt(len(vig))}</b> afiliadas vigentes",
         f"Empresas con membresía vigente al corte (incluye las que están en periodo de gracia). "
         f"{fmt(nuevas)} se afiliaron en los últimos 30 días."),
        ("OK" if tasa is not None and tasa >= meta else "Alerta",
         f"Renovación <b>{fmt(tasa, 1, ' %')}</b> · meta {fmt(meta, 0, ' %')}",
         f"De las membresías que vencieron en los últimos 12 meses, cuántas renovaron ({ren.get('tipo', '')}). "
         f"La meta 2027 es {fmt(meta, 0, ' %')}."),
        ("Alerta" if vencen else "OK", f"<b>{fmt(vencen)}</b> vencen en 60 días",
         "Membresías vigentes que vencen en los próximos 60 días: es el próximo frente de renovación. "
         "Detalle y contactos en Renovación y retención."),
    ]


def encabezado(titulo: str, subtitulo: str, pildoras: list | None = None, filtros: bool = True, acciones=None):
    """Componente 'Encabezado de página': título, subtítulo, frescura de los datos, tres píldoras de negocio
    (tono, texto[, explicación]) y, debajo, la barra de filtros (filtros=False en páginas de una sola empresa o de datos).
    acciones: función que dibuja botones (p. ej. Ver en Power BI); van alineados a la izquierda, bajo el título."""
    if pildoras is None:
        pildoras = pildoras_negocio()
    p = parametros()
    carga = ultima_carga()
    calidad = consulta("SELECT count(*) AS n FROM actho.reporte_calidad WHERE accion = 'Revisar con ACTHO'")["n"].iloc[0]
    frescura = (f'Datos al <b>{fecha_txt(carga) if carga is not None else "corte manual"}</b> · '
                f'evaluados al {fecha_txt(p["fecha_corte"])}'
                + (f' · <span class="revisar">{calidad} registros por revisar</span> en Datos y calidad' if calidad else ""))
    izq, der = st.columns([2.5, 2.5])
    with izq:
        st.markdown(f'<p class="titulo" role="heading" aria-level="1">{_e(titulo)}</p><p class="subtitulo">{_e(subtitulo)}</p>'
                    f'<p class="frescura">{frescura}</p>', unsafe_allow_html=True)
        if acciones is not None:
            with st.container(key="acciones_encabezado"):
                acciones()
    cuerpo = ""
    for pil in pildoras:
        t, txt = pil[0], pil[1]
        tip = f' tabindex="0" data-tip="{_e(pil[2])}" aria-label="{_e(pil[2])}"' if len(pil) > 2 and pil[2] else ""
        cuerpo += f'<span class="pildora {TONOS.get(t, "neutro")}"{tip}><i aria-hidden="true"></i>{txt}</span>'
    der.markdown(f'<div class="pildoras" role="status">{cuerpo}</div>', unsafe_allow_html=True)
    if filtros:
        barra_filtros()


def chip(texto, tono="Neutro"):
    clase = TONOS.get(tono, tono)
    return f'<span class="chip {clase}">{_e(texto)}</span>'


def chip_semaforo(s):
    """Chip del nivel de riesgo: punto del color del gráfico + texto (Alto, Medio, Bajo)."""
    if s not in SEMAFORO:
        return chip("Sin evaluar")
    return (f'<span class="chip sem{" alto" if s == "Rojo" else ""}" style="--c:{SEMAFORO[s]}">'
            f'Riesgo {_e(SEM_TXT[s].lower())}</span>')


class _Fila:
    """Fila de tarjetas del mismo tipo dibujada como una sola cuadrícula CSS: todas miden lo mismo."""

    def __init__(self, n: int):
        self.n, self.ph, self.html = n, st.empty(), [None] * n

    def poner(self, i: int, contenido: str):
        self.html[i] = contenido
        celdas = "".join(h or "<div></div>" for h in self.html)
        self.ph.markdown(f'<div class="fila-tarjetas" style="--n:{self.n}">{celdas}</div>', unsafe_allow_html=True)


class _Ranura:
    def __init__(self, fila_: _Fila, i: int):
        self.fila, self.i = fila_, i


def fila(n: int) -> list:
    """Reemplaza a st.columns(n) para filas de KPI o metas: devuelve n ranuras de igual ancho y alto."""
    f = _Fila(n)
    return [_Ranura(f, i) for i in range(n)]


def _poner(col, contenido: str):
    if isinstance(col, _Ranura):
        col.fila.poner(col.i, contenido)
    else:
        col.markdown(contenido, unsafe_allow_html=True)


def _icono_ayuda(texto: str, simbolo: str = "?", clase: str = "") -> str:
    """Ícono con explicación al pasar el cursor (o al enfocarlo con el teclado)."""
    if not texto:
        return ""
    t = _e(texto)
    return (f'<span class="ayuda{" " + clase if clase else ""}" tabindex="0" role="note" aria-label="{t}" '
            f'data-tip="{t}">{simbolo}</span>')


def kpi(col, etiqueta, valor, nota="", oscuro=False, chip_=None, ayuda_=""):
    """Componente 'KPI/Tarjeta': ETIQUETA, valor, chip (tono, texto) y nota. ayuda_ = definición del indicador."""
    ch = chip(chip_[1], chip_[0]) if chip_ else ""
    _poner(col, f'<div class="kpi{" oscuro" if oscuro else ""}"><div class="et">{_e(etiqueta)}{_icono_ayuda(ayuda_)}</div>'
                f'<div class="va">{valor}</div>{ch}<div class="no">{nota}</div></div>')


def meta(col, etiqueta, actual, objetivo, nota="", sufijo="%", chip_=None, ayuda_="", proyeccion=None, ayuda_proy=""):
    """proyeccion: valor proyectado por un modelo de IA; se marca sobre la barra con una línea cian."""
    pct = 0 if actual is None or pd.isna(actual) else max(0, min(100, 100 * actual / objetivo))
    ch = chip(chip_[1], chip_[0]) if chip_ else ""
    marca, txt_p = "", ""
    if proyeccion is not None and not pd.isna(proyeccion):
        pp = max(0, min(100, 100 * proyeccion / objetivo))
        marca = (f'<span title="Proyección IA: {fmt(proyeccion, 1, sufijo)}" style="position:absolute;left:calc({pp:.0f}% - 2px);'
                 f'top:-4px;bottom:-4px;width:4px;border-radius:2px;background:{C["cian_graf"]}"></span>')
        txt_p = (f'<div class="no" style="color:#075E70">✦ Proyección IA: <b>{fmt(proyeccion, 1, sufijo)}</b>'
                 f'{_icono_ayuda(ayuda_proy, "i", "info")}</div>')
    _poner(col, f'<div class="meta"><div class="et-meta">{_e(etiqueta)}{_icono_ayuda(ayuda_)}</div>'
                f'<div class="fila"><span class="va">{fmt(actual, 1, sufijo)}</span>'
                f'<span class="obj">meta 2027: {fmt(objetivo, 0, sufijo)}</span> {ch}</div>'
                f'<div class="barra" style="position:relative;overflow:visible"><div style="width:{pct:.0f}%"></div>{marca}</div>'
                f'<div class="no">{nota}</div>{txt_p}</div>')


def cabeza(titulo: str, sub: str | None = None, oscuro=False, ayuda: str = ""):
    """Encabezado de tarjeta: título morado y subtítulo naranja (en panel morado: blanco y cian).
    ayuda: si viene, se agrega un ícono ⓘ con esa explicación junto al título."""
    st.markdown(f'<div class="cabeza{" oscura" if oscuro else ""}"><h3>{_e(titulo)}{_icono_ayuda(ayuda, "i", "info")}</h3>'
                + (f"<p>{_e(sub)}</p>" if sub else "") + "</div>", unsafe_allow_html=True)


_contador_tarjeta = {"n": 0}
_contador_panel = {"n": 0}


def reiniciar_contadores():
    _contador_tarjeta["n"] = 0
    _contador_panel["n"] = 0


def tarjeta(titulo: str | None = None, sub: str | None = None, ayuda: str = ""):
    """Tarjeta blanca (radio 20, sin borde) con su encabezado. Lleva una clave para poder estilizarla."""
    _contador_tarjeta["n"] += 1
    cont = st.container(border=True, key=f"tarjeta_{_contador_tarjeta['n']}")
    if titulo:
        with cont:
            cabeza(titulo, sub, ayuda=ayuda)
    return cont


@contextmanager
def panel(titulo: str | None = None, lema: str | None = None):
    """Panel derecho morado de los wireframes (Pulso). Acepta contenido nativo de Streamlit."""
    _contador_panel["n"] += 1
    with st.container(key=f"panel_{_contador_panel['n']}"):
        if titulo:
            st.markdown(f'<p class="panel-titulo">{_e(titulo)}</p>' + (f'<p class="panel-lema">{_e(lema)}</p>' if lema else ""),
                        unsafe_allow_html=True)
        yield


def actividad(titulo: str, meta_: str = "", acento=False):
    """Componente 'Actividad/Tarjeta': tarjeta blanca con título y detalle dentro del panel morado."""
    st.markdown(f'<div class="act{" acento" if acento else ""}"><b>{titulo}</b>' + (f"<span>{meta_}</span>" if meta_ else "")
                + "</div>", unsafe_allow_html=True)


def pulso(items: list, titulo="Pulso", lema="Lo que dicen los datos hoy"):
    """Lecturas de Pulso como tarjetas blancas. Cada ítem: texto HTML '<b>título</b><br><span>detalle</span>'."""
    st.markdown(f'<p class="panel-titulo">{_e(titulo)}</p><p class="panel-lema">{_e(lema)}</p>', unsafe_allow_html=True)
    for i in items:
        partes = i.split("<br>", 1)
        tit = partes[0].replace("<b>", "").replace("</b>", "") if partes[0].startswith("<b>") and partes[0].endswith("</b>") else partes[0]
        det = partes[1].replace("<span>", "").replace("</span>", "") if len(partes) > 1 else ""
        actividad(tit, det)


def hallazgo(texto: str):
    st.markdown(f'<div class="hallazgo"><div>{texto}</div></div>', unsafe_allow_html=True)


def tabla_html(filas: list, columnas: list):
    """Tabla con el estilo de los componentes Tabla/Encabezado y Tabla/Fila.
    columnas: [(titulo, clave, tipo)] con tipo 'texto' | 'num' | 'html'. Una clave puede ser (titulo, detalle)."""
    enc = "".join(f'<th scope="col" style="text-align:{"right" if t == "num" else "left"}">{_e(n)}</th>' for n, _, t in columnas)
    cuerpo = ""
    for f in filas:
        celdas = ""
        for _, k, t in columnas:
            clase = {"num": "num", "nw": "nw"}.get(t, "")
            if isinstance(k, tuple):
                celdas += f'<td class="{clase}"><span class="t">{_e(f[k[0]])}</span><span class="d">{_e(f[k[1]])}</span></td>'
            elif t == "html":
                celdas += f"<td>{f[k]}</td>"
            else:
                celdas += f'<td class="{clase}">{_e(f[k])}</td>'
        cuerpo += f"<tr>{celdas}</tr>"
    st.markdown(f'<table class="tabla"><thead><tr>{enc}</tr></thead><tbody>{cuerpo}</tbody></table>', unsafe_allow_html=True)


def heroe(lema: str, titulo: str, texto: str = ""):
    st.markdown(f'<div class="heroe"><div class="lema">{_e(lema)}</div><h2>{_e(titulo)}</h2>'
                + (f"<p>{_e(texto)}</p>" if texto else "") + "</div>", unsafe_allow_html=True)


def descargar(df: pd.DataFrame, nombre: str, etiqueta="Descargar CSV"):
    st.download_button(etiqueta, df.to_csv(index=False).encode("utf-8-sig"), file_name=nombre,
                       mime="text/csv", type="primary")


def ir(pagina: str, empresa: str | None = None):
    """Navega a otra página del tablero (opcionalmente con una empresa seleccionada)."""
    if empresa:
        st.session_state["empresa_sel"] = empresa
    st.switch_page(f"paginas/{pagina}")


def tabla_df(df: pd.DataFrame, **kw):
    """st.dataframe con ancho completo y sin índice."""
    return st.dataframe(df, hide_index=True, **ancho(st.dataframe), **kw)
