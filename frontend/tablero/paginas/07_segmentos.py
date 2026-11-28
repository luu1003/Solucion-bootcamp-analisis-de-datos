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


# ──────────────────────────────────────────────────────────────────────────────
# Segmentos con apoyo de IA
# ──────────────────────────────────────────────────────────────────────────────
import ia  # noqa: E402

with c.tarjeta("Segmentos con apoyo de IA", "✦ Listas armadas con los modelos: perfil de uso, interés por tema y parecido con afiliadas",
               ayuda="Perfil de uso: " + ia.desc("perfiles") + " Interés por tema: asistencias a eventos del tema + "
                     "lo pedido en encuestas. Parecido con afiliadas: " + ia.desc("propension")):
    if not ia.hay():
        ia.sin_modelos()
    else:
        personas = c.consulta("SELECT persona_id, empresa_id, nivel_cargo, autoriza_datos FROM actho.dim_persona")
        aut = personas[personas["autoriza_datos"] == "Sí"]
        t1, t2, t3 = st.tabs(["Por perfil de uso", "Por interés en un tema", "No afiliadas parecidas a las afiliadas"])
        with t1:
            per, res_p, ren = ia.perfiles(), ia.t("perfil_resumen"), ia.renovacion()
            m = per.merge(ren[["empresa_id", "p_renovar"]], on="empresa_id", how="left")
            if c.hay_filtros_empresa():
                m = m[m["empresa_id"].isin(set(c.filtrar_empresas(c.empresas())["empresa_id"]))]
            r_ = m.groupby("perfil").agg(empresas=("empresa_id", "count"), p=("p_renovar", "mean")).reset_index()
            r_ = r_.merge(res_p[["perfil", "descripcion", "inscripciones", "personas", "servicios"]], on="perfil", how="left")
            filas = [{"p": x.perfil, "d": x.descripcion, "e": c.fmt(x.empresas), "i": c.fmt(x.inscripciones, 1),
                      "r": ia.chip(f"{100 * x.p:.0f} %")} for x in r_.sort_values("p").itertuples()]
            c.tabla_html(filas, [("Perfil", ("p", "d"), "texto"), ("Empresas", "e", "num"),
                                 ("Asist. 12m (prom.)", "i", "num"), ("Prob. renovar", "r", "html")])
            elegido_p = st.selectbox("Perfil para exportar", r_.sort_values("p")["perfil"].tolist(), key="seg_perfil")
            ids_p = set(m[m["perfil"] == elegido_p]["empresa_id"])
            lista = aut[aut["empresa_id"].isin(ids_p)]
            if len(lista):
                st.caption(f"{c.fmt(len(lista))} personas que autorizaron datos en {c.fmt(lista['empresa_id'].nunique())} "
                           f"empresas del perfil «{elegido_p}».")
                c.descargar(lista, f"perfil_{elegido_p.lower().replace(' ', '_')}.csv", "Exportar personas del perfil")
            else:
                emp_p = c.empresas()
                emp_p = emp_p[emp_p["empresa_id"].isin(ids_p)][["empresa_id", "ejecutiva", "nivel_2027", "fecha_expiracion"]]
                st.caption(f"Las {c.fmt(len(emp_p))} empresas de «{elegido_p}» no tienen personas registradas en eventos: "
                           "el contacto va por su ejecutiva. Exporta la lista de empresas.")
                c.descargar(emp_p, f"perfil_{elegido_p.lower().replace(' ', '_')}_empresas.csv", "Exportar empresas del perfil")
            ia.nota("perfiles")
        with t2:
            inter = ia.t("interes_persona")
            temas = sorted(inter["tema"].unique())
            tema = st.selectbox("Tema", temas, key="seg_tema")
            x = inter[(inter["tema"] == tema) & (inter["autoriza_datos"] == "Sí")].sort_values("puntaje", ascending=False)
            c.tabla_df(x[["persona_id", "empresa_id", "nivel_cargo", "asistencias", "pedidos", "es_afiliada"]], height=260,
                       column_config={"persona_id": "Persona", "empresa_id": "Empresa", "nivel_cargo": "Cargo",
                                      "asistencias": "Eventos del tema", "pedidos": "Lo pidió",
                                      "es_afiliada": st.column_config.CheckboxColumn("Afiliada")})
            c.descargar(x, f"interes_{tema[:30].lower().replace(' ', '_')}.csv", "Exportar interesados en el tema")
            ia.nota("temas")
        with t3:
            pr = ia.propension()
            banda_sel = st.segmented_control("Parecido", ["Alta", "Media", "Baja"], default="Alta", key="seg_prop") \
                if hasattr(st, "segmented_control") else st.radio("Parecido", ["Alta", "Media", "Baja"], horizontal=True)
            emp_sel = pr[pr["banda"] == (banda_sel or "Alta")]
            lista = aut[aut["empresa_id"].isin(set(emp_sel["empresa_id"]))].merge(
                emp_sel[["empresa_id", "puntaje"]], on="empresa_id").sort_values("puntaje", ascending=False)
            k = c.fila(3)
            c.kpi(k[0], "Empresas no afiliadas", c.fmt(len(emp_sel)), f"Con parecido {(banda_sel or 'Alta').lower()}")
            c.kpi(k[1], "Personas contactables", c.fmt(len(lista)), "Autorizaron el tratamiento de datos")
            c.kpi(k[2], "Asistencias en 2026", c.fmt(emp_sel["inscripciones"].sum()), "Ya conocen la oferta de ACTHO")
            c.tabla_df(lista.rename(columns={"persona_id": "Persona", "empresa_id": "Empresa", "nivel_cargo": "Cargo",
                                             "puntaje": "Parecido (0-100)"}).drop(columns=["autoriza_datos"]), height=240)
            c.descargar(lista, "no_afiliadas_parecidas.csv", "Exportar para campaña de afiliación")
            ia.nota("propension")
