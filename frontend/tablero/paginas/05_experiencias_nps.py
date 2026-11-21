# -*- coding: utf-8 -*-
"""05 · Experiencias y NPS: participación por línea y formato, satisfacción y lo que piden los afiliados."""
import pandas as pd
import plotly.express as px
import streamlit as st

import comun as c

c.encabezado("Experiencias y NPS", "Qué eventos, líneas y formatos convocan más, a quién y con qué satisfacción")

a = c.filtrar_detalle(c.asistencia(), "fecha_evento")
r = c.filtrar_detalle(c.encuestas(), "fecha_respuesta")
ev = c.tabla("v_evento_resumen")
ev = ev[ev["evento_id"].isin(a["evento_id"].unique()) | (not c.hay_filtros_empresa())]

r_sat = r["satisfaccion_general"].fillna(r["satisfaccion_prom"])
nps_n = r["nps_puntaje"].notna().sum()
prom, det = (r["nps_categoria"] == "Promotor").sum(), (r["nps_categoria"] == "Detractor").sum()

k = st.columns(5)
c.kpi(k[0], "Eventos con asistencia", c.fmt(a["evento_id"].nunique()), f"{c.fmt(len(a))} inscripciones", oscuro=True)
c.kpi(k[1], "Personas distintas", c.fmt(a["persona_id"].nunique()), f"{c.fmt(a['empresa_id'].nunique())} empresas")
c.kpi(k[2], "Inscripciones de no afiliados", c.fmt(100 * (a["condicion_empresa"] == "No afiliada").mean() if len(a) else None, 1, " %"),
      "Potencial de afiliación")
c.kpi(k[3], "Satisfacción", c.fmt(r_sat.mean(), 2), f"{c.fmt(len(r))} respuestas · escala 1-5")
c.kpi(k[4], "NPS de eventos", c.fmt(100 * (prom - det) / nps_n if nps_n else None, 0),
      f"{c.fmt(nps_n)} respuestas · meta +55")
st.write("")

izq, der = st.columns([2.3, 1], gap="medium")
with izq:
    g1, g2 = st.columns(2)
    with g1:
        with st.container(border=True):
            lin = a.groupby(["linea_2027", "condicion_empresa"]).size().reset_index(name="inscripciones")
            fig = px.bar(lin, x="inscripciones", y="linea_2027", color="condicion_empresa", orientation="h",
                         color_discrete_map={"Afiliada": c.C["morado"], "No afiliada": c.C["cian"]},
                         title="Participación por línea 2027")
            fig.update_yaxes(title="", categoryorder="total ascending")
            fig.update_xaxes(title="")
            c.grafico(fig, 290)
    with g2:
        with st.container(border=True):
            niv = a[a["nivel_cargo"] != "Sin dato"].groupby(["nivel_cargo", "modalidad"]).size().reset_index(name="inscripciones")
            fig = px.bar(niv, x="inscripciones", y="nivel_cargo", color="modalidad", orientation="h",
                         title="Nivel de cargo por modalidad")
            fig.update_yaxes(title="", categoryorder="total ascending")
            fig.update_xaxes(title="")
            c.grafico(fig, 290)

    with st.container(border=True):
        st.markdown("**Eventos: convocatoria, satisfacción y NPS**")
        c.tabla_df(ev[["fecha", "evento", "linea_2027", "modalidad", "inscripciones", "empresas",
                       "pct_inscripciones_afiliadas", "respuestas_encuesta", "satisfaccion_promedio", "nps"]]
                   .sort_values("fecha", ascending=False), height=330, column_config={
                       "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                       "evento": st.column_config.TextColumn("Evento", width="large"), "linea_2027": "Línea",
                       "modalidad": "Modalidad", "inscripciones": "Inscritos", "empresas": "Empresas",
                       "pct_inscripciones_afiliadas": st.column_config.ProgressColumn(
                           "% afiliados", min_value=0, max_value=100, format="%.0f %%"),
                       "respuestas_encuesta": "Respuestas",
                       "satisfaccion_promedio": st.column_config.NumberColumn("Satisf.", format="%.2f"),
                       "nps": st.column_config.NumberColumn("NPS", format="%.0f")})
        st.caption("Las encuestas no registran el evento: se asigna por fecha y modalidad. "
                   "Las respuestas de 2025 no corresponden a eventos de 2026.")

    g3, g4 = st.columns(2)
    with g3:
        with st.container(border=True):
            asp = pd.DataFrame({
                "Aspecto": ["Expositores", "Contenido", "Espacio o plataforma", "Convocatoria", "Recepción", "Manejo del tiempo"],
                "Promedio": [r["calif_expositor"].mean(), r["calif_contenido"].mean(), r["calif_espacio"].mean(),
                             r["calif_convocatoria"].mean(), r["calif_recepcion"].mean(), r["calif_manejo_tiempo"].mean()],
            }).dropna()
            fig = px.bar(asp.sort_values("Promedio"), x="Promedio", y="Aspecto", orientation="h", text_auto=".2f",
                         title="Satisfacción por aspecto (1-5)", color_discrete_sequence=[c.C["naranja"]])
            fig.update_xaxes(range=[1, 5.2], title="")
            fig.update_yaxes(title="")
            c.grafico(fig, 290)
    with g4:
        with st.container(border=True):
            dist = r["nps_puntaje"].dropna().astype(int).value_counts().reindex(range(11), fill_value=0).reset_index()
            dist.columns = ["puntaje", "respuestas"]
            dist["categoria"] = pd.cut(dist["puntaje"], [-1, 6, 8, 10], labels=["Detractor", "Pasivo", "Promotor"]).astype(str)
            fig = px.bar(dist, x="puntaje", y="respuestas", color="categoria", title="Distribución del NPS (0-10)",
                         color_discrete_map={"Detractor": c.C["rojo"], "Pasivo": c.C["amarillo"], "Promotor": c.C["verde"]})
            fig.update_xaxes(dtick=1, title="")
            fig.update_yaxes(title="")
            c.grafico(fig, 290)

with der:
    temas = c.tabla("v_temas_solicitados")
    temas["tema"] = temas["tema"].map(lambda t: t if len(t) <= 30 else t[:29] + "…")
    with st.container(border=True):
        fig = px.bar(temas.head(8).sort_values("menciones"), x="menciones", y="tema", orientation="h",
                     title="Temas que piden", color_discrete_sequence=[c.C["morado"]])
        fig.update_yaxes(title="")
        fig.update_xaxes(title="")
        c.grafico(fig, 330)
    gusto = r["lo_que_gusto"].dropna()
    gusto = gusto[gusto.str.len() > 15]
    mejora = r["a_mejorar"].dropna()
    mejora = mejora[mejora.str.len() > 10]
    items = [f"<b>Lo que más gustó</b><br><span>«{t[:140]}»</span>" for t in gusto.head(2)]
    items += [f"<b>Qué mejorar</b><br><span>«{t[:140]}»</span>" for t in mejora.head(2)]
    if not items:
        items = ["<b>Sin comentarios abiertos</b><br><span>No hay comentarios en la selección actual.</span>"]
    c.pulso(items, titulo="Voz de los asistentes", lema="Comentarios recientes de la encuesta post-evento")
