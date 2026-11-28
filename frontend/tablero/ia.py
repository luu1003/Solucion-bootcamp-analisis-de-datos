# -*- coding: utf-8 -*-
"""Apoyo de IA en el tablero: lee las tablas del esquema `ia` (las escribe src/modelos_ia.py después de cada
carga) y ofrece piezas comunes: el chip ✦ IA, la nota con la métrica de cada modelo y cargadores en caché.

Si los modelos aún no se han entrenado, todo devuelve tablas vacías y las páginas siguen funcionando."""
import json
import sys

import pandas as pd
import streamlit as st

import comun as c

sys.path.insert(0, str(c.RAIZ / "src"))


@st.cache_data(ttl=60, show_spinner=False)
def t(nombre: str) -> pd.DataFrame:
    """Tabla ia.<nombre>, o vacía si no existe."""
    try:
        if not c.existe(f"ia.{nombre}"):
            return pd.DataFrame()
        return c.tabla(nombre, "ia")
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


def hay() -> bool:
    return not t("modelo").empty


def ficha(modelo: str) -> dict:
    f = t("modelo")
    if f.empty or modelo not in set(f["modelo"]):
        return {}
    r = f[f["modelo"] == modelo].iloc[0].to_dict()
    try:
        r["detalle"] = json.loads(r.get("detalle") or "{}")
    except ValueError:
        r["detalle"] = {}
    return r


# Cómo funciona cada modelo, en dos frases, para el ícono ⓘ (al pasar el cursor)
DESCRIPCION = {
    "renovacion": "Regresión logística entrenada con 503 empresas cuyo desenlace ya se conoce (renovó o no). Combina "
                  "antigüedad, tamaño, nivel, región y comunidades con su participación en los 6 meses previos y da una "
                  "probabilidad de 0 a 100 %.",
    "perfiles": "k-means agrupa a las afiliadas vigentes según cómo usaron la membresía en 12 meses (asistencias, "
                "personas, líneas, beneficios y comunidades). Las empresas de un mismo perfil se comportan parecido.",
    "propension": "Un bosque aleatorio aprende cómo participan las afiliadas y mide de 0 a 100 qué tanto se parece cada "
                  "no afiliada. No es probabilidad de compra: no hay historia de conversiones.",
    "temas": "Compara cada comentario con la descripción de los 12 temas de la encuesta (TF-IDF: parecido de palabras) y "
             "le asigna el más cercano; si ninguno se parece lo suficiente, queda sin tema.",
    "identidad": "Para encuestas sin empresa o con una dudosa, sugiere la empresa con la que esa misma persona se "
                 "inscribió a eventos. Se revisa antes de corregir.",
    "recomendador": "Sugiere beneficios del nivel que la empresa no ha usado en 12 meses y temas que las empresas de su "
                    "mismo perfil aprovechan y ella aún no.",
    "accion": "Regla que cruza días al vencimiento, participación reciente y probabilidad de renovar para sugerir el "
              "siguiente paso de la ejecutiva.",
    "eventos": "Busca los 5 eventos pasados más parecidos (modalidad, línea, tema, costo, mes y día) y promedia sus "
               "resultados. El rango sale de cuánto se equivocó al estimar cada evento pasado sin mirarlo.",
    "altas": "SARIMA: aprende la tendencia y la estacionalidad de las afiliaciones mensuales desde 2019 y las proyecta "
             "con rangos de 80 % y 95 %.",
    "vigentes": "Simula 2.000 escenarios: cada vigente renueva o no en su mes de vencimiento según su probabilidad de "
                "renovar, y se suman las altas esperadas del SARIMA.",
    "control": "Dibuja límites a 3 errores estándar del promedio histórico; un punto fuera indica algo distinto a la "
               "variación normal. La banda es más ancha cuando hubo pocas respuestas.",
    "general": "Modelos entrenados con los datos de cada carga. Ordenan y explican para apoyar la decisión; no deciden "
               "por el equipo. Fichas completas en Datos y calidad → Modelos de IA.",
}


def desc(modelo: str) -> str:
    return DESCRIPCION.get(modelo, DESCRIPCION["general"])


def info(modelo: str) -> str:
    """Ícono ⓘ con la explicación corta del modelo (HTML para poner junto a un título o texto)."""
    return c._icono_ayuda(desc(modelo), "i", "info")


def chip(texto: str = "IA") -> str:
    return c.chip(texto, "IA")


def _num(v, dec=2):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def nota(modelo: str, extra: str = ""):
    """Línea pequeña bajo un resultado de IA: qué modelo es y qué tan bien funciona."""
    f = ficha(modelo)
    if not f:
        return
    v = f["valor"]
    dec = 0 if v is not None and (abs(v) >= 10 or float(v).is_integer()) else 2
    st.markdown(f'<div class="nota-ia">{chip()} &nbsp;<b>{c._e(f["nombre"])}</b>{info(modelo)} · {c._e(f["metrica"])}: '
                f'<b>{_num(f["valor"], dec)}</b>{" · " + extra if extra else ""} · '
                'detalles en <i>Datos y calidad → Modelos de IA</i></div>', unsafe_allow_html=True)


def sin_modelos():
    st.info("Los modelos de IA todavía no están listos. Si acabas de correr `python3 setup.py`, se están entrenando en "
            "segundo plano: esta sección aparece sola al terminar (recarga la página en un par de minutos).",
            icon=":material/auto_awesome:")


# ── Cargadores ya preparados ─────────────────────────────────────────────────
def renovacion() -> pd.DataFrame:
    return t("renovacion")


def perfiles() -> pd.DataFrame:
    return t("perfil")


def propension() -> pd.DataFrame:
    return t("propension")


def pronostico(serie: str) -> pd.DataFrame:
    p = t("pronostico")
    if p.empty:
        return p
    p = p[p["serie"] == serie].copy()
    p["mes"] = pd.to_datetime(p["mes"])
    return p.sort_values("mes")


def con_ia(e: pd.DataFrame) -> pd.DataFrame:
    """Agrega a una tabla de empresas la probabilidad de renovar, el perfil y la propensión."""
    out = e.copy()
    r, p, pr = renovacion(), perfiles(), propension()
    if not r.empty:
        out = out.merge(r[["empresa_id", "p_renovar", "banda", "a_favor", "en_contra"]], on="empresa_id", how="left")
    if not p.empty:
        out = out.merge(p[["empresa_id", "perfil"]], on="empresa_id", how="left")
    if not pr.empty:
        out = out.merge(pr[["empresa_id", "puntaje"]].rename(columns={"puntaje": "propension"}), on="empresa_id",
                        how="left")
    return out


BANDA_COLOR = {"En riesgo": c.C["naranja"], "Incierta": c.C["lavanda_graf"], "Probable": c.C["morado"]}
ORDEN_BANDA = ["En riesgo", "Incierta", "Probable"]
