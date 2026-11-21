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
    "morado": "#5B00D9", "morado_700": "#5B00D9", "morado_500": "#7C3AED", "morado_900": "#2B0A6B",
    "morado_100": "#EFE6FF", "lavanda": "#EFE6FF", "lavanda_2": "#C9B2FF",
    "naranja": "#FF5A0F", "naranja_300": "#FF9A66", "naranja_suave": "#FFF0E8",
    "cian": "#22C7E8", "menta": "#EEF6F5", "blanco": "#FFFFFF",
    "tinta": "#1B1235", "gris": "#6E6787", "linea": "#E4E1EC",
    "ok": "#0F8A5F", "ok_suave": "#DDF4EA", "alerta": "#B25E00", "alerta_suave": "#FFF0D6",
    "riesgo": "#C93A22", "riesgo_suave": "#FFE5E0",
    "rojo": "#E5484D", "amarillo": "#F5A524", "verde": "#12A57A",
    "morado_osc": "#2B0A6B",
}
SEMAFORO = {"Rojo": C["rojo"], "Amarillo": C["amarillo"], "Verde": C["verde"]}
SECUENCIA = [C["morado"], C["naranja"], C["lavanda_2"], C["cian"], C["morado_500"], C["naranja_300"]]
TONOS = {"OK": "ok", "Alerta": "alerta", "Riesgo": "riesgo", "Morado": "morado", "Neutro": "neutro"}
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
[data-testid="stNavSectionHeader"] {{ color: {C['cian']} !important; font-size: .68rem !important; font-weight: 600 !important;
  letter-spacing: .08em; text-transform: uppercase; margin-top: .8rem !important; }}
[data-testid="stNavSectionHeader"] * {{ color: {C['cian']} !important; }}
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
.lema-lateral {{ color: {C['cian']}; font-size: .8rem; font-weight: 500; margin: -.2rem 0 .2rem; }}
.usuario {{ display:flex; align-items:center; gap:.65rem; border-top: 1px solid rgba(255,255,255,.2); padding-top: .9rem; margin-top: .6rem; }}
.usuario .avatar {{ width: 36px; height: 36px; border-radius: 50%; background: #fff; color: {C['morado']} !important;
  display:flex; align-items:center; justify-content:center; font-weight: 700; font-size: .8rem; }}
.usuario b {{ display:block; font-size: .85rem; font-weight: 600; }} .usuario small {{ font-size: .72rem; color: {C['lavanda_2']} !important; }}

/* ── Encabezado de página ── */
.titulo {{ font-size: 1.75rem !important; font-weight: 700 !important; color: {C['tinta']} !important; margin: 0 !important; line-height: 1.15 !important; letter-spacing: -.01em; }}
.subtitulo {{ color: {C['gris']} !important; margin: .2rem 0 0 !important; font-size: .9rem !important; }}
.pildoras {{ display:flex; gap:.5rem; flex-wrap:wrap; justify-content:flex-end; padding-top: .3rem; }}
.pildora {{ display:inline-flex; align-items:center; gap:.45rem; border-radius: 999px; padding: .42rem .9rem .42rem .7rem;
  font-size: .72rem; font-weight: 500; letter-spacing: .02em; text-transform: uppercase; background: #fff;
  border: 1px solid {C['linea']}; color: {C['tinta']}; white-space: nowrap; }}
.pildora b {{ font-weight: 700; }}
.pildora i {{ width: 9px; height: 9px; border-radius: 50%; display:inline-block; background: {C['gris']}; }}
.pildora.ok i {{ background: {C['verde']}; }} .pildora.alerta i {{ background: {C['amarillo']}; }}
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
.cabeza p {{ font-size: .74rem !important; font-weight: 500 !important; color: {C['naranja']} !important; margin: .1rem 0 0 !important; }}
.cabeza.oscura h3 {{ color: #fff !important; }} .cabeza.oscura p {{ color: {C['cian']} !important; }}

/* ── KPI ── */
.kpi {{ background:#fff; border-radius: 20px; padding: 1rem 1.15rem; height: 100%; display:flex; flex-direction:column; gap:.3rem; }}
.kpi .et {{ font-size: .68rem; color: {C['gris']}; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; }}
.kpi .va {{ font-size: 2rem; font-weight: 700; color: {C['tinta']}; line-height: 1.05; letter-spacing: -.02em; }}
.kpi .no {{ font-size: .74rem; color: {C['gris']}; line-height: 1.35; }}
.kpi.oscuro {{ background: {C['morado']}; }}
.kpi.oscuro .et {{ color: {C['lavanda_2']}; }} .kpi.oscuro .va {{ color: #fff; }} .kpi.oscuro .no {{ color: {C['lavanda_2']}; }}

/* ── Chips ── */
.chip {{ display:inline-block; border-radius:999px; padding:.18rem .6rem; font-size:.68rem; font-weight:600; letter-spacing:.02em;
  width: fit-content; max-width: 100%; white-space: normal; line-height: 1.35; overflow-wrap: anywhere; }}
.tabla .chip {{ white-space: nowrap; }}
.chip.ok, .chip.verde {{ background:{C['ok_suave']}; color:{C['ok']}; }}
.chip.alerta, .chip.amarillo {{ background:{C['alerta_suave']}; color:{C['alerta']}; }}
.chip.riesgo, .chip.rojo {{ background:{C['riesgo_suave']}; color:{C['riesgo']}; }}
.chip.morado {{ background:{C['lavanda']}; color:{C['morado']}; }}
.chip.neutro, .chip.gris {{ background:#F1EFF5; color:{C['gris']}; }}
.kpi.oscuro .chip.morado {{ background: rgba(255,255,255,.16); color:#fff; }}

/* ── Distribución: sin superposiciones ni alturas distintas ── */
/* Streamlit compensa el margen del último párrafo con margin-bottom:-16px; los componentes propios no lo tienen,
   así que se anula para que el bloque siguiente no se monte encima. */
[data-testid="stMarkdownContainer"]:has(.fila-tarjetas, .titulo, .subtitulo, .pildoras, .cabeza, .tabla, .heroe, .act,
  .hallazgo, .panel-titulo, .usuario, .lema-lateral, .login-hero, .login-titulo, .login-fila) {{ margin-bottom: 0 !important; }}
/* Tarjetas que comparten fila: todas con la altura de la más alta. */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:only-child > div[class*="st-key-tarjeta"]) {{
  align-items: stretch !important; }}
[data-testid="stColumn"] > [data-testid="stVerticalBlock"]:has(> [data-testid="stLayoutWrapper"]:only-child > div[class*="st-key-tarjeta"]),
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:only-child:has(> div[class*="st-key-tarjeta"]),
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:only-child > div[class*="st-key-tarjeta"] {{
  height: 100% !important; }}

/* ── Filas de tarjetas del mismo tipo (altura uniforme) ── */
.fila-tarjetas {{ display:grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); gap: .85rem; align-items: stretch; }}
.fila-tarjetas > div {{ height: 100%; min-width: 0; }}
@media (max-width: 1000px) {{ .fila-tarjetas {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
.et-meta {{ font-size: .68rem; color: {C['gris']}; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; }}

/* ── Metas 2027 ── */
.meta {{ background:#fff; border-radius:20px; padding:1rem 1.15rem; height:100%; }}
.meta .fila {{ display:flex; align-items:baseline; gap:.5rem; flex-wrap: wrap; margin-top:.3rem; }}
.meta .va {{ font-size: 1.9rem; font-weight:700; color:{C['tinta']}; letter-spacing:-.02em; }}
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
.panel-lema {{ color:{C['cian']} !important; font-size:.76rem !important; font-weight:500 !important; margin:.1rem 0 .3rem !important; }}
.act {{ background:#fff; border-radius:14px; padding:.7rem .85rem; margin-bottom:.55rem; }}
.act b {{ display:block; color:{C['tinta']}; font-size:.84rem; font-weight:600; line-height:1.3; }}
.act span {{ display:block; color:{C['gris']}; font-size:.75rem; line-height:1.35; margin-top:.15rem; }}
.act.acento {{ border-left: 4px solid {C['naranja']}; }}
.hallazgo {{ display:flex; gap:.6rem; align-items:stretch; background:{C['lavanda']}; border-radius:12px; padding:.65rem .8rem; margin-bottom:.5rem; }}
.hallazgo::before {{ content:''; width:4px; border-radius:2px; background:{C['morado']}; flex:none; }}
.hallazgo div {{ font-size:.82rem; color:{C['tinta']}; line-height:1.4; }}

/* ── Tabla HTML (componentes Tabla/Encabezado y Tabla/Fila) ── */
.tabla {{ width:100%; border-collapse:collapse; }}
.tabla th {{ font-size:.66rem; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:{C['gris']};
  text-align:left; padding:.5rem .6rem; border-bottom:1px solid {C['linea']}; background:transparent; }}
.tabla td {{ font-size:.82rem; color:{C['tinta']}; padding:.55rem .6rem; border-bottom:1px solid {C['linea']}; vertical-align:middle; }}
.tabla td .t {{ font-weight:600; display:block; }} .tabla td .d {{ color:{C['gris']}; font-size:.72rem; display:block; }}
.tabla tr:last-child td {{ border-bottom:none; }} .tabla td.num {{ text-align:right; font-variant-numeric: tabular-nums; }}

/* ── Héroe (tarjeta morada "Pregúntale a Pulso") ── */
.heroe {{ background:{C['morado']} url("{CINTA_URI}") no-repeat right 30px top -60px / 150px auto; border-radius:20px; padding:1.3rem 1.5rem; }}
.heroe .lema {{ color:{C['cian']}; font-size:.8rem; font-weight:500; }}
.heroe h2 {{ color:#fff !important; font-size:1.35rem !important; font-weight:700 !important; margin:.2rem 0 .2rem !important; padding:0 !important; }}
.heroe p {{ color:{C['lavanda_2']} !important; font-size:.85rem !important; max-width: 70%; margin:0 !important; }}

/* ── Controles ── */
.stButton button, .stDownloadButton button {{ border-radius: 999px !important; font-weight: 600 !important; padding: .45rem 1.2rem !important; }}
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"], button[data-testid="stBaseButton-primary"] {{
  background: {C['naranja']} !important; border-color: {C['naranja']} !important; color: #fff !important; }}
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
[data-testid="stSegmentedControl"] button, [data-testid="stButtonGroup"] button {{ border-radius: 999px !important; background:#fff; }}
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[kind*="Active"] {{
  background:{C['morado']} !important; color:#fff !important; border-color:{C['morado']} !important; }}
[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
[data-testid="stAlert"] {{ border-radius: 14px; }}
[data-testid="stCaptionContainer"] {{ color: {C['gris']}; }}
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
    return tabla("v_empresa_360")


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
def parametros() -> dict:
    return tabla("v_parametros").iloc[0].to_dict()


@st.cache_data(ttl=300, show_spinner=False)
def ultima_carga():
    if not existe("ingesta.ejecucion"):
        return None
    df = consulta("SELECT fin, estado FROM ingesta.ejecucion WHERE estado = 'procesado' ORDER BY fin DESC LIMIT 1")
    return None if df.empty else df.iloc[0]["fin"]


# ──────────────────────────────────────────────────────────────────────────────
# Filtros globales (barra lateral)
# ──────────────────────────────────────────────────────────────────────────────
FILTROS = [("nivel_2027", "Nivel 2027"), ("tipo_membresia", "Tipo de afiliado"), ("sector", "Sector"),
           ("ciudad", "Ciudad"), ("ejecutiva", "Ejecutiva de cuenta")]


def filtros_barra_lateral():
    e = empresas()
    vig = e[e["es_vigente"] == 1]
    with st.sidebar:
        st.markdown('<p class="lema-lateral">Sentimos el pulso.</p>', unsafe_allow_html=True)
        with st.expander("Filtros", expanded=False, icon=":material/tune:"):
            a = asistencia()
            fmin, fmax = a["fecha_evento"].min().date(), a["fecha_evento"].max().date()
            st.date_input("Periodo de eventos y encuestas", value=(fmin, fmax), key="f_periodo",
                          min_value=date(2025, 1, 1), max_value=date(2027, 12, 31), format="DD/MM/YYYY")
            for col, et in FILTROS:
                opciones = sorted(vig[col].dropna().unique().tolist())
                st.multiselect(et, opciones, key=f"f_{col}", placeholder="Todos")
            if st.button("Limpiar filtros", **ancho(st.button)):
                for col, _ in FILTROS:
                    st.session_state[f"f_{col}"] = []
                st.session_state["f_periodo"] = (fmin, fmax)
                st.rerun()
        activos = sum(1 for c, _ in FILTROS if st.session_state.get(f"f_{c}"))
        st.caption(f"{activos} filtro(s) activo(s)" if activos else "Sin filtros: toda la base")
        sesion = st.session_state.get("sesion") or {"nombre": "Equipo ACTHO", "rol": "Dirección Ejecutiva"}
        iniciales = "".join(p[0] for p in sesion["nombre"].split()[:2]).upper() or "A"
        st.markdown(f'<div class="usuario"><span class="avatar">{_e(iniciales)}</span><div><b>{_e(sesion["nombre"])}</b>'
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


def grafico(fig, altura=320, sub=None, oscuro=False):
    """Dibuja un gráfico con el estilo de los wireframes: el título de la figura se muestra como
    encabezado de tarjeta (morado + subtítulo naranja), barras redondeadas y leyenda abajo."""
    titulo = fig.layout.title.text if fig.layout.title and fig.layout.title.text else None
    if titulo:
        cabeza(titulo, sub, oscuro)
    fig.update_layout(title=None, height=altura, legend_title_text="", paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                      legend=dict(orientation="h", yanchor="top", y=-0.14, xanchor="left", x=0,
                                  font=dict(size=11, color=C["gris"])),
                      margin=dict(l=6, r=6, t=8, b=6))
    try:
        fig.update_layout(barcornerradius=6)
    except Exception:  # noqa: BLE001  (Plotly < 5.19)
        pass
    fig.update_xaxes(automargin=True, title_font=dict(size=11, color=C["gris"]))
    fig.update_yaxes(automargin=True, title_font=dict(size=11, color=C["gris"]))
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None, **ancho(st.plotly_chart))


def periodo():
    p = st.session_state.get("f_periodo")
    if isinstance(p, (list, tuple)) and len(p) == 2:
        return pd.Timestamp(p[0]), pd.Timestamp(p[1])
    return None, None


def filtrar_empresas(df: pd.DataFrame) -> pd.DataFrame:
    for col, _ in FILTROS:
        sel = st.session_state.get(f"f_{col}")
        if sel:
            df = df[df[col].isin(sel)]
    return df


def hay_filtros_empresa() -> bool:
    return any(st.session_state.get(f"f_{c}") for c, _ in FILTROS)


def filtrar_detalle(df: pd.DataFrame, col_fecha: str) -> pd.DataFrame:
    ini, fin = periodo()
    if ini is not None:
        f = pd.to_datetime(df[col_fecha])
        df = df[(f >= ini) & (f <= fin)]
    if hay_filtros_empresa():
        ids = set(filtrar_empresas(empresas())["empresa_id"])
        df = df[df["empresa_id"].isin(ids)]
    return df


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


def encabezado(titulo: str, subtitulo: str, pildoras: list | None = None):
    """Componente 'Encabezado de página': título, subtítulo y tres píldoras de estado (tono, texto)."""
    if pildoras is None:
        p = parametros()
        carga = ultima_carga()
        calidad = consulta("SELECT count(*) AS n FROM actho.reporte_calidad WHERE accion = 'Revisar con ACTHO'")["n"].iloc[0]
        pildoras = [("Morado", f"Corte <b>{fecha_txt(p['fecha_corte'])}</b>"),
                    ("OK" if carga is not None else "Neutro",
                     f"Última carga <b>{fecha_txt(carga) if carga is not None else 'manual'}</b>"),
                    ("Alerta" if calidad else "OK", f"<b>{calidad}</b> datos por revisar")]
    izq, der = st.columns([2.4, 2.6])
    izq.markdown(f'<p class="titulo">{_e(titulo)}</p><p class="subtitulo">{_e(subtitulo)}</p>', unsafe_allow_html=True)
    cuerpo = "".join(f'<span class="pildora {TONOS.get(t, "neutro")}"><i></i>{txt}</span>' for t, txt in pildoras)
    der.markdown(f'<div class="pildoras">{cuerpo}</div>', unsafe_allow_html=True)


def chip(texto, tono="Neutro"):
    clase = TONOS.get(tono, tono)
    return f'<span class="chip {clase}">{_e(texto)}</span>'


def chip_semaforo(s):
    return chip(s, {"Rojo": "Riesgo", "Amarillo": "Alerta", "Verde": "OK"}.get(s, "Neutro"))


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


def kpi(col, etiqueta, valor, nota="", oscuro=False, chip_=None):
    """Componente 'KPI/Tarjeta': ETIQUETA, valor, chip (tono, texto) y nota."""
    ch = chip(chip_[1], chip_[0]) if chip_ else ""
    _poner(col, f'<div class="kpi{" oscuro" if oscuro else ""}"><div class="et">{_e(etiqueta)}</div>'
                f'<div class="va">{valor}</div>{ch}<div class="no">{nota}</div></div>')


def meta(col, etiqueta, actual, objetivo, nota="", sufijo="%", chip_=None):
    pct = 0 if actual is None or pd.isna(actual) else max(0, min(100, 100 * actual / objetivo))
    ch = chip(chip_[1], chip_[0]) if chip_ else ""
    _poner(col, f'<div class="meta"><div class="et-meta">{_e(etiqueta)}</div>'
                f'<div class="fila"><span class="va">{fmt(actual, 1, sufijo)}</span>'
                f'<span class="obj">meta 2027: {fmt(objetivo, 0, sufijo)}</span> {ch}</div>'
                f'<div class="barra"><div style="width:{pct:.0f}%"></div></div><div class="no">{nota}</div></div>')


def cabeza(titulo: str, sub: str | None = None, oscuro=False):
    """Encabezado de tarjeta: título morado y subtítulo naranja (en panel morado: blanco y cian)."""
    st.markdown(f'<div class="cabeza{" oscura" if oscuro else ""}"><h3>{_e(titulo)}</h3>'
                + (f"<p>{_e(sub)}</p>" if sub else "") + "</div>", unsafe_allow_html=True)


_contador_tarjeta = {"n": 0}
_contador_panel = {"n": 0}


def reiniciar_contadores():
    _contador_tarjeta["n"] = 0
    _contador_panel["n"] = 0


def tarjeta(titulo: str | None = None, sub: str | None = None):
    """Tarjeta blanca (radio 20, sin borde) con su encabezado. Lleva una clave para poder estilizarla."""
    _contador_tarjeta["n"] += 1
    cont = st.container(border=True, key=f"tarjeta_{_contador_tarjeta['n']}")
    if titulo:
        with cont:
            cabeza(titulo, sub)
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
    enc = "".join(f'<th style="text-align:{"right" if t == "num" else "left"}">{_e(n)}</th>' for n, _, t in columnas)
    cuerpo = ""
    for f in filas:
        celdas = ""
        for _, k, t in columnas:
            if isinstance(k, tuple):
                celdas += f'<td><span class="t">{_e(f[k[0]])}</span><span class="d">{_e(f[k[1]])}</span></td>'
            elif t == "html":
                celdas += f"<td>{f[k]}</td>"
            else:
                celdas += f'<td class="{"num" if t == "num" else ""}">{_e(f[k])}</td>'
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
