# -*- coding: utf-8 -*-
"""
Utilidades compartidas del tablero ACTHO (Streamlit + Plotly).

* Lectura de las vistas del esquema 'actho' en PostgreSQL (con caché).
* Estilo con la línea gráfica de ACTHO (morado, naranja, cian, menta, Poppins).
* Filtros globales del reto: periodo, nivel, tipo, sector, ciudad y ejecutiva.
* Componentes visuales: encabezado con píldoras de estado, tarjetas KPI,
  panel lateral "Pulso" y gráficos con la paleta de la marca.
"""
from __future__ import annotations

import html
import sys
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
# Marca
# ──────────────────────────────────────────────────────────────────────────────
C = {
    "morado": "#5B00D9", "morado_osc": "#2E0670", "lavanda": "#EDE5FF", "lavanda_2": "#C9B5FF",
    "naranja": "#FF5A0F", "naranja_suave": "#FFE6DA", "cian": "#18C5E0", "cian_suave": "#DDF7FB",
    "menta": "#EEF6F5", "tinta": "#1E1038", "gris": "#6B6880", "linea": "#E3E0EC",
    "rojo": "#E5484D", "amarillo": "#F5A524", "verde": "#12A57A",
}
SEMAFORO = {"Rojo": C["rojo"], "Amarillo": C["amarillo"], "Verde": C["verde"]}
SECUENCIA = [C["morado"], C["naranja"], C["cian"], C["lavanda_2"], C["morado_osc"], "#FF9C6B", "#7FDDEB"]
METAS_2027 = {"renovacion": 90.0, "nps": 55.0}

pio.templates["actho"] = go.layout.Template(layout=dict(
    font=dict(family="Poppins, sans-serif", color=C["tinta"], size=12),
    colorway=SECUENCIA, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=8, r=8, t=36, b=8), title=dict(font=dict(size=14, color=C["tinta"]), x=0, xanchor="left"),
    xaxis=dict(gridcolor=C["linea"], linecolor=C["linea"], zeroline=False),
    yaxis=dict(gridcolor=C["linea"], linecolor=C["linea"], zeroline=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, title_text=""),
    hoverlabel=dict(font_family="Poppins, sans-serif"),
))
pio.templates.default = "actho"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select {{ font-family: 'Poppins', sans-serif; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1500px; }}
h1, h2, h3 {{ font-family: 'Poppins', sans-serif; color: {C['tinta']}; letter-spacing: -0.01em; }}
[data-testid="stSidebar"] {{ background: {C['morado']}; }}
[data-testid="stSidebar"] * {{ color: #FFFFFF; }}
[data-testid="stSidebar"] [data-baseweb="select"] *, [data-testid="stSidebar"] input,
[data-testid="stSidebar"] [data-baseweb="tag"] * {{ color: {C['tinta']} !important; }}
[data-testid="stSidebar"] [data-baseweb="tag"] {{ background: {C['lavanda']} !important; }}
[data-testid="stSidebarNav"] a {{ border-radius: 999px; }}
[data-testid="stSidebarHeader"] img, [data-testid="stLogo"] {{ height: 3.2rem !important; max-width: 14rem; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: rgba(255,255,255,0.18); }}
[data-testid="stSidebarNavSeparator"] {{ border-color: rgba(255,255,255,0.25); }}
.marca {{ font-weight: 700; font-size: 1.6rem; line-height: 1; color: #fff; }}
.marca small {{ display:block; font-weight:500; font-size: .78rem; color: {C['cian']}; margin-top: .35rem; }}
.cinta {{ height: 6px; border-radius: 999px; background: {C['naranja']}; width: 64px; margin: .7rem 0 1rem; }}
.titulo {{ font-size: 1.75rem !important; font-weight: 700 !important; color: {C['tinta']}; margin: 0 !important; line-height: 1.2 !important; }}
.subtitulo {{ color: {C['gris']}; margin: .15rem 0 .4rem !important; font-size: .92rem !important; }}
.pildoras {{ display:flex; gap:.5rem; flex-wrap:wrap; justify-content:flex-end; }}
.pildora {{ border-radius: 999px; padding: .32rem .8rem; font-size: .78rem; font-weight: 500;
           background: #fff; border: 1px solid {C['linea']}; color: {C['tinta']}; white-space: nowrap; }}
.pildora b {{ font-weight: 600; }}
.pildora.ok {{ background: #E3F6EF; border-color: #BDE8D8; color: #0B6B4F; }}
.pildora.alerta {{ background: {C['naranja_suave']}; border-color: #FFC9AE; color: #9A3200; }}
.pildora.info {{ background: {C['lavanda']}; border-color: {C['lavanda_2']}; color: {C['morado_osc']}; }}
.kpi {{ background:#fff; border-radius: 18px; padding: 1rem 1.1rem; border: 1px solid {C['linea']}; height: 100%; }}
.kpi.oscuro {{ background: {C['morado']}; border-color: {C['morado']}; }}
.kpi .et {{ font-size: .78rem; color: {C['gris']}; font-weight: 500; }}
.kpi .va {{ font-size: 1.75rem; font-weight: 700; color: {C['tinta']}; line-height: 1.2; margin-top: .2rem; }}
.kpi .no {{ font-size: .75rem; color: {C['gris']}; margin-top: .25rem; }}
.kpi.oscuro .et, .kpi.oscuro .no {{ color: {C['lavanda_2']}; }}
.kpi.oscuro .va {{ color: #fff; }}
.chip {{ display:inline-block; border-radius:999px; padding:.12rem .55rem; font-size:.72rem; font-weight:600; }}
.chip.rojo {{ background:#FDE7E8; color:#A3191E; }} .chip.amarillo {{ background:#FEF1D9; color:#8A5600; }}
.chip.verde {{ background:#DDF4EC; color:#0B6B4F; }} .chip.gris {{ background:#EFEDF4; color:{C['gris']}; }}
.chip.morado {{ background:{C['lavanda']}; color:{C['morado_osc']}; }}
.meta {{ background:#fff; border-radius:18px; padding:1rem 1.1rem; border:1px solid {C['linea']}; }}
.meta .barra {{ height:10px; background:{C['menta']}; border-radius:999px; margin:.55rem 0 .35rem; overflow:hidden; }}
.meta .barra div {{ height:100%; border-radius:999px; background:{C['naranja']}; }}
.pulso {{ background: {C['morado']}; color:#fff; border-radius: 22px; padding: 1.1rem 1.2rem; }}
.pulso h4 {{ color:#fff; margin:0 0 .2rem; font-size:1.05rem; }}
.pulso .lema {{ color:{C['cian']}; font-size:.8rem; margin-bottom:.8rem; }}
.pulso .item {{ background: rgba(255,255,255,.10); border-radius: 14px; padding:.7rem .8rem; margin-bottom:.6rem; font-size:.84rem; line-height:1.35; }}
.pulso .item b {{ color:#fff; }} .pulso .item span {{ color:{C['lavanda_2']}; }}
.tarjeta {{ background:#fff; border-radius:18px; padding:1rem 1.1rem; border:1px solid {C['linea']}; }}
.accion {{ border-left: 4px solid {C['naranja']}; background:#fff; border-radius: 0 14px 14px 0; padding:.6rem .8rem; margin-bottom:.5rem; font-size:.86rem; }}
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > div > .marco) {{ background:#fff; border-radius:18px; }}
.stDownloadButton button, .stButton button {{ border-radius: 999px; font-weight: 600; }}
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
        with st.expander("Filtros", expanded=False):
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


def grafico(fig, altura=320):
    fig.update_layout(height=altura, legend_title_text="",
                      legend=dict(orientation="h", yanchor="top", y=-0.16, xanchor="left", x=0),
                      margin=dict(l=12, r=12, t=44, b=12))
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
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
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    f = pd.Timestamp(f)
    return f"{f.day} {meses[f.month - 1]} {f.year}"


def encabezado(titulo: str, subtitulo: str):
    p = parametros()
    carga = ultima_carga()
    calidad = consulta("SELECT count(*) AS n FROM actho.reporte_calidad WHERE accion = 'Revisar con ACTHO'")["n"].iloc[0]
    izq, der = st.columns([2.5, 2.5])
    izq.markdown(f'<p class="titulo">{html.escape(titulo)}</p><p class="subtitulo">{html.escape(subtitulo)}</p>',
                 unsafe_allow_html=True)
    pild = [f'<span class="pildora info">Corte <b>{fecha_txt(p["fecha_corte"])}</b></span>',
            f'<span class="pildora ok">Última carga <b>{fecha_txt(carga) if carga is not None else "manual"}</b></span>',
            f'<span class="pildora {"alerta" if calidad else "ok"}">Calidad <b>{calidad} por revisar</b></span>']
    der.markdown(f'<div class="pildoras">{"".join(pild)}</div>', unsafe_allow_html=True)


def kpi(col, etiqueta, valor, nota="", oscuro=False):
    col.markdown(f'<div class="kpi{" oscuro" if oscuro else ""}"><div class="et">{html.escape(etiqueta)}</div>'
                 f'<div class="va">{valor}</div><div class="no">{nota}</div></div>', unsafe_allow_html=True)


def meta(col, etiqueta, actual, objetivo, nota="", sufijo="%"):
    pct = 0 if actual is None or pd.isna(actual) else max(0, min(100, 100 * actual / objetivo))
    col.markdown(f'<div class="meta"><div class="kpi" style="border:none;padding:0">'
                 f'<div class="et">{etiqueta}</div><div class="va">{fmt(actual, 1, sufijo)} '
                 f'<span style="font-size:.85rem;color:{C["gris"]};font-weight:500">meta {fmt(objetivo, 0, sufijo)}</span></div></div>'
                 f'<div class="barra"><div style="width:{pct:.0f}%"></div></div>'
                 f'<div class="no" style="font-size:.75rem;color:{C["gris"]}">{nota}</div></div>', unsafe_allow_html=True)


def chip(texto, tono="gris"):
    return f'<span class="chip {tono}">{html.escape(str(texto))}</span>'


def chip_semaforo(s):
    return chip(s, {"Rojo": "rojo", "Amarillo": "amarillo", "Verde": "verde"}.get(s, "gris"))


def pulso(items: list, titulo="Pulso", lema="Lo que dicen los datos hoy"):
    cuerpo = "".join(f'<div class="item">{i}</div>' for i in items)
    st.markdown(f'<div class="pulso"><h4>{titulo}</h4><div class="lema">{lema}</div>{cuerpo}</div>',
                unsafe_allow_html=True)


def tarjeta(titulo: str):
    """Contenedor blanco con borde para agrupar un bloque."""
    cont = st.container(border=True)
    cont.markdown(f"**{titulo}**")
    return cont


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
