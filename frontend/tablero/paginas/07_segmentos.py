# -*- coding: utf-8 -*-
"""07 · Segmentos para comunicaciones: listas exportables respetando la autorización de datos."""
import plotly.express as px
import streamlit as st

import comun as c

c.encabezado("Segmentos", "A quién dirigir cada mensaje, en vez de enviarle lo mismo a toda la base")

seg = c.tabla("v_segmentos_comunicacion")
if c.hay_filtros_empresa():
    seg = seg[seg["empresa_id"].isin(set(c.filtrar_empresas(c.empresas())["empresa_id"]))]

USO = {
    "Afiliados que no participan": "Recordarles qué incluye su nivel y proponer la próxima experiencia de su interés",
    "Vencimientos próximos": "Campaña de renovación con el valor recibido durante el año",
    "Detractores recientes": "Seguimiento personal de la ejecutiva antes de cualquier envío masivo",
    "Promotores": "Invitarlos a tomar la palabra: testimonio, columna, podcast o referidos",
    "Asistentes no afiliados": "Comunicación de afiliación desde canales propios",
    "Afiliados de un solo contacto": "Abrir la relación a más personas del área y a otros niveles",
    "Nuevos afiliados": "Secuencia de bienvenida y encuesta de 90 días",
    "Encuesta de 90 días por enviar": "Cumplen 90 días o les faltan unos 60 para renovar: medir NPS e intención de renovar",
}

res = seg.groupby("segmento").agg(personas=("persona_id", "count"), empresas=("empresa_id", "nunique"),
                                   contactables=("autoriza_datos", lambda s: (s == "Sí").sum())).reindex(USO.keys()).fillna(0)
cols = c.fila(4)
for i, (nombre, fila) in enumerate(res.iterrows()):
    c.kpi(cols[i % 4], nombre, c.fmt(fila["contactables"]), USO[nombre], oscuro=(i == 0),
          chip_=("Morado" if i == 0 else "Neutro", f"de {c.fmt(fila['personas'])} personas · {c.fmt(fila['empresas'])} empresas"))
    if i % 4 == 3:
        cols = c.fila(4)

izq, der = st.columns([2.2, 1], gap="medium")
with izq:
    with c.tarjeta():
        c.cabeza("Lista para campaña", "Elige el segmento y exporta solo a quienes autorizaron")
        st.session_state.setdefault("seg_elegido", list(USO.keys())[0])
        elegido = st.selectbox("Segmento", list(USO.keys()), key="seg_elegido",
                               help="También puedes elegirlo con un clic en el gráfico de la derecha")
        solo_aut = st.toggle("Solo personas que autorizaron el tratamiento de datos (Ley 1581)", value=True, key="seg_aut")
        lista = seg[seg["segmento"] == elegido]
        if solo_aut:
            lista = lista[lista["autoriza_datos"] == "Sí"]
        c.tabla_df(lista[["persona_id", "empresa_id", "ejecutiva", "nivel_2027", "nivel_cargo", "autoriza_datos"]],
                   height=360, column_config={"persona_id": "Persona", "empresa_id": "Empresa", "ejecutiva": "Ejecutiva",
                                              "nivel_2027": "Nivel", "nivel_cargo": "Cargo", "autoriza_datos": "Autoriza"})
        if len(lista):
            c.descargar(lista, f"segmento_{elegido.lower().replace(' ', '_')}.csv", "Exportar lista para campaña")
        else:
            st.info("Este segmento no tiene personas con la selección actual.")
with der, c.panel("Segmentos", "A quién dirigir cada mensaje"):
    with c.tarjeta():
        g = res.reset_index().rename(columns={"index": "segmento"})
        g["color"] = [c.C["naranja"] if s_ == st.session_state.get("seg_elegido") else c.C["morado"] for s_ in g["segmento"]]
        g = g.sort_values("contactables")
        fig = px.bar(g, x="contactables", y="segmento", orientation="h", text="contactables", custom_data=["segmento"],
                     title="Personas contactables")
        fig.update_traces(marker_color=g["color"].tolist(), textposition="outside", cliponaxis=False,
                          textfont=dict(color=c.C["tinta"]), hovertemplate="%{y}: <b>%{x}</b> contactables<extra></extra>")
        fig.update_yaxes(title="")
        fig.update_xaxes(title="", range=[0, max(g["contactables"].max(), 1) * 1.38], showticklabels=False, showgrid=False)

        def _elegir(k):
            pts = (st.session_state.get(k) or {}).get("selection", {}).get("points", [])
            if pts and pts[0].get("customdata"):
                st.session_state["seg_elegido"] = pts[0]["customdata"][0]
                st.session_state["seg_ver"] = st.session_state.get("seg_ver", 0) + 1

        c.cabeza("Personas contactables", "Con autorización de datos · clic en un segmento para ver su lista")
        fig.update_layout(title=None, height=300, dragmode=False, clickmode="event+select", showlegend=False,
                          paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF", margin=dict(l=6, r=6, t=8, b=6))
        fig.update_yaxes(ticksuffix="  ", automargin=True, tickfont=dict(size=12, color=c.C["gris"]))
        clave = f"gi_seg_{st.session_state.get('seg_ver', 0)}"
        st.plotly_chart(fig, config={"displayModeBar": False}, theme=None, key=clave, on_select=lambda: _elegir(clave),
                        selection_mode="points", **c.ancho(st.plotly_chart))
    c.actividad("Protección de datos (Ley 1581)", "Las listas se exportan sin correo ni teléfono (no están en la base "
                "del reto) y, por defecto, solo con personas que autorizaron.", acento=True)
