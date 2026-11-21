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
}

res = seg.groupby("segmento").agg(personas=("persona_id", "count"), empresas=("empresa_id", "nunique"),
                                   contactables=("autoriza_datos", lambda s: (s == "Sí").sum())).reindex(USO.keys()).fillna(0)
cols = st.columns(4)
for i, (nombre, fila) in enumerate(res.iterrows()):
    c.kpi(cols[i % 4], nombre, c.fmt(fila["contactables"]),
          f"contactables de {c.fmt(fila['personas'])} personas · {c.fmt(fila['empresas'])} empresas", oscuro=(i == 0))
    if i % 4 == 3:
        st.write("")
        cols = st.columns(4)
st.write("")

izq, der = st.columns([2.2, 1], gap="medium")
with izq:
    with st.container(border=True):
        elegido = st.selectbox("Segmento", list(USO.keys()), key="seg_elegido")
        solo_aut = st.toggle("Solo personas que autorizaron el tratamiento de datos (Ley 1581)", value=True, key="seg_aut")
        lista = seg[seg["segmento"] == elegido]
        if solo_aut:
            lista = lista[lista["autoriza_datos"] == "Sí"]
        st.caption(USO[elegido])
        c.tabla_df(lista[["persona_id", "empresa_id", "ejecutiva", "nivel_2027", "nivel_cargo", "autoriza_datos"]],
                   height=360, column_config={"persona_id": "Persona", "empresa_id": "Empresa", "ejecutiva": "Ejecutiva",
                                              "nivel_2027": "Nivel", "nivel_cargo": "Cargo", "autoriza_datos": "Autoriza"})
        if len(lista):
            c.descargar(lista, f"segmento_{elegido.lower().replace(' ', '_')}.csv", "Exportar lista para campaña")
        else:
            st.info("Este segmento no tiene personas con la selección actual.")
with der:
    with st.container(border=True):
        g = res.reset_index().rename(columns={"index": "segmento"})
        fig = px.bar(g.sort_values("contactables"), x="contactables", y="segmento", orientation="h",
                     title="Personas contactables por segmento", color_discrete_sequence=[c.C["naranja"]])
        fig.update_yaxes(title="")
        fig.update_xaxes(title="")
        c.grafico(fig, 330)
    c.pulso(["<b>Protección de datos</b><br><span>Las listas se exportan sin correo ni teléfono (no están en la "
             "base del reto) y, por defecto, solo con personas que autorizaron.</span>"],
            titulo="Antes de enviar", lema="Uso responsable de las listas")
