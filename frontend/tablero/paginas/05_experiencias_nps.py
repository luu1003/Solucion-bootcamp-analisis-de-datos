# -*- coding: utf-8 -*-
"""05 · Experiencias y NPS: participación por línea y formato, satisfacción y lo que piden los afiliados."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import comun as c
import ia

c.encabezado("Experiencias y NPS", "Qué eventos, líneas y formatos convocan más, a quién y con qué satisfacción")

a = c.filtrar_detalle(c.asistencia(), "fecha_evento")
r = c.filtrar_detalle(c.encuestas(), "fecha_respuesta")
ev = c.tabla("v_evento_resumen")
ev = ev[ev["evento_id"].isin(a["evento_id"].unique()) | (not c.hay_filtros_empresa())]

r_sat = r["satisfaccion_general"].fillna(r["satisfaccion_prom"])
nps_n = r["nps_puntaje"].notna().sum()
prom, det = (r["nps_categoria"] == "Promotor").sum(), (r["nps_categoria"] == "Detractor").sum()

k = c.fila(5)
nps_v = 100 * (prom - det) / nps_n if nps_n else None
c.kpi(k[0], "Experiencias 2026", c.fmt(a["evento_id"].nunique()), f"{c.fmt(len(a))} inscripciones en el periodo", oscuro=True,
      chip_=("Morado", f"{c.fmt(a['linea_2027'].nunique())} líneas 2027"))
c.kpi(k[1], "Personas que participan", c.fmt(a["persona_id"].nunique()), f"De {c.fmt(a['empresa_id'].nunique())} empresas",
      chip_=("OK", f"{c.fmt(a.loc[a['condicion_empresa'] == 'Afiliada', 'empresa_id'].nunique())} afiliadas"))
c.kpi(k[2], "Asistentes no afiliados", c.fmt(100 * (a["condicion_empresa"] == "No afiliada").mean() if len(a) else None, 1, " %"),
      "De las inscripciones del periodo", chip_=("Alerta", "Potencial de afiliación"))
alta = (r_sat.mean() or 0) >= 4.5
c.kpi(k[3], "Satisfacción", c.fmt(r_sat.mean(), 2), f"Promedio 1-5 de {c.fmt(len(r))} respuestas",
      chip_=("OK" if alta else "Alerta", "Alta" if alta else "Por mejorar"))
c.kpi(k[4], "NPS de eventos", ("+" if (nps_v or 0) > 0 else "") + c.fmt(nps_v, 0), f"{c.fmt(nps_n)} respuestas con NPS",
      chip_=("OK" if (nps_v or 0) >= 55 else "Alerta", "Meta 2027: +55"))

izq, der = c.columnas([2.3, 1], "lateral", gap="medium")
with izq:
    g1, g2 = c.columnas(2, "pareja")
    with g1:
        with c.tarjeta():
            dims = ["linea_2027", "condicion_empresa"]
            _, a1, _ = c.datos(excluir=dims)
            lin = a1.groupby(["linea_2027", "condicion_empresa"]).size().reset_index(name="inscripciones")
            lin["Empresa"] = lin["condicion_empresa"]
            fig = px.bar(lin, x="inscripciones", y="linea_2027", color="Empresa", orientation="h", custom_data=dims,
                         color_discrete_map=c.CONDICION, title="Participación por línea")
            fig.update_traces(hovertemplate="%{y} · %{fullData.name}: <b>%{x}</b> inscripciones<extra></extra>")
            fig.update_yaxes(title="", categoryorder="total ascending")
            fig.update_xaxes(title="Inscripciones")
            c.grafico(fig, 270, "Inscripciones por línea de la oferta 2027 · clic para filtrar", dims=dims, clave="linea")
    with g2:
        with c.tarjeta():
            dims = ["nivel_cargo", "modalidad"]
            _, a2, _ = c.datos(excluir=dims)
            niv = a2[a2["nivel_cargo"] != "Sin dato"].groupby(["nivel_cargo", "modalidad"]).size().reset_index(name="inscripciones")
            niv["Modalidad"] = niv["modalidad"]
            fig = px.bar(niv, x="inscripciones", y="nivel_cargo", color="Modalidad", orientation="h", custom_data=dims,
                         title="Quién participa", color_discrete_map=c.MODALIDAD)
            fig.update_traces(hovertemplate="%{y} · %{fullData.name}: <b>%{x}</b> inscripciones<extra></extra>")
            fig.update_yaxes(title="", categoryorder="total ascending")
            fig.update_xaxes(title="Inscripciones")
            c.grafico(fig, 270, "Inscripciones por nivel de cargo y modalidad · clic para filtrar", dims=dims, clave="cargo")

    with c.tarjeta():
        c.cabeza("Experiencias recientes", "Convocatoria, satisfacción y NPS por evento")
        c.tabla_df(ev[["fecha", "evento", "linea_2027", "inscripciones",
                       "pct_inscripciones_afiliadas", "respuestas_encuesta", "satisfaccion_promedio", "nps"]]
                   .sort_values("fecha", ascending=False), height=330, column_config={
                       "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                       "evento": st.column_config.TextColumn("Evento", width="medium"),
                       "linea_2027": st.column_config.TextColumn("Línea", width="small"),
                       "modalidad": st.column_config.TextColumn("Modalidad", width="small"),
                       "inscripciones": st.column_config.NumberColumn("Inscritos", width="small"),
                       "empresas": st.column_config.NumberColumn("Empresas", width="small"),
                       "pct_inscripciones_afiliadas": st.column_config.ProgressColumn(
                           "% afiliados", min_value=0, max_value=100, format="%.0f %%"),
                       "respuestas_encuesta": st.column_config.NumberColumn("Respuestas", width="small"),
                       "satisfaccion_promedio": st.column_config.NumberColumn("Satisf.", format="%.2f"),
                       "nps": st.column_config.NumberColumn("NPS", format="%.0f")})
        st.caption("Las encuestas no registran el evento: se asigna por fecha y modalidad. "
                   "Las respuestas de 2025 no corresponden a eventos de 2026.")

    g3, g4 = c.columnas(2, "pareja")
    with g3:
        with c.tarjeta():
            asp = pd.DataFrame({
                "Aspecto": ["Expositores", "Contenido", "Espacio o plataforma", "Convocatoria", "Recepción", "Manejo del tiempo"],
                "Promedio": [r["calif_expositor"].mean(), r["calif_contenido"].mean(), r["calif_espacio"].mean(),
                             r["calif_convocatoria"].mean(), r["calif_recepcion"].mean(), r["calif_manejo_tiempo"].mean()],
            }).dropna()
            fig = px.bar(asp.sort_values("Promedio"), x="Promedio", y="Aspecto", orientation="h", text_auto=".2f",
                         title="Satisfacción por aspecto", color_discrete_sequence=[c.C["morado"]])
            fig.update_traces(textfont=dict(color="#FFFFFF"), insidetextanchor="end",
                              hovertemplate="%{y}: <b>%{x:.2f}</b> de 5<extra></extra>")
            fig.update_xaxes(range=[1, 5.2], title="")
            fig.update_yaxes(title="")
            c.grafico(fig, 270, "Promedio 1 a 5 de cada aspecto evaluado")
    with g4:
        with c.tarjeta():
            _, _, r4 = c.datos(excluir=("nps_categoria",))
            dist = r4["nps_puntaje"].dropna().astype(int).value_counts().reindex(range(11), fill_value=0).reset_index()
            dist.columns = ["puntaje", "respuestas"]
            dist["nps_categoria"] = pd.cut(dist["puntaje"], [-1, 6, 8, 10], labels=["Detractor", "Pasivo", "Promotor"]).astype(str)
            dist["Categoría"] = dist["nps_categoria"]
            fig = px.bar(dist, x="puntaje", y="respuestas", color="Categoría", title="Distribución del NPS",
                         custom_data=["nps_categoria"], color_discrete_map=c.NPS_COLOR,
                         category_orders={"Categoría": ["Detractor", "Pasivo", "Promotor"]})
            fig.update_traces(hovertemplate="Puntaje %{x} · %{fullData.name}: <b>%{y}</b> respuestas<extra></extra>")
            fig.update_xaxes(dtick=1, title="Puntaje (0 a 10)")
            fig.update_yaxes(title="Respuestas")
            c.grafico(fig, 270, f"{c.fmt(r4['nps_puntaje'].notna().sum())} respuestas · promotores 9-10, pasivos 7-8, "
                      "detractores 0-6 · clic para filtrar", dims=["nps_categoria"], clave="nps")

    # NPS de ACTHO: encuesta de relación a 90 días (meta central 2027)
    with c.tarjeta():
        c.cabeza("NPS de ACTHO · encuesta de relación a 90 días",
                 "Mide la relación con la asociación y la intención de renovar, no un evento")
        rel = c.relacion()
        if len(rel):
            rel = rel[c.dentro_del_periodo(rel["fecha"])]
            if c.hay_filtros_empresa():
                rel = rel[rel["empresa_id"].isin(set(c.filtrar_empresas(c.empresas())["empresa_id"]))]
        pe = c.tabla("v_encuesta_90d_por_enviar") if c.existe("actho.v_encuesta_90d_por_enviar") else pd.DataFrame()
        n = rel["nps_actho"].notna().sum() if len(rel) else 0
        nps_a = 100 * ((rel["nps_categoria"] == "Promotor").sum() - (rel["nps_categoria"] == "Detractor").sum()) / n if n else None
        kk = c.fila(4)
        c.kpi(kk[0], "NPS de ACTHO", (("+" if (nps_a or 0) > 0 else "") + c.fmt(nps_a, 0)) if n else "—",
              f"{c.fmt(n)} respuestas" if n else "Aún sin respuestas", oscuro=True,
              chip_=("Morado", "Meta 2027: +55"), ayuda_=c.ayuda("NPS de ACTHO"))
        c.kpi(kk[1], "Intención de renovar", c.fmt(100 * (rel["intencion_renovar"] >= 4).mean(), 0, " %") if n else "—",
              "Responden 4 o 5 de 5", ayuda_=c.ayuda("Intención de renovar"))
        c.kpi(kk[2], "Bienvenida y ejecutiva", f"{c.fmt(rel['calif_bienvenida'].mean(), 1)} · {c.fmt(rel['calif_ejecutiva'].mean(), 1)}" if n else "—",
              "Promedio 1-5 de cada una")
        c.kpi(kk[3], "Por encuestar", c.fmt(len(pe)), "Cumplen 90 días o renuevan en ~60 días",
              chip_=("Alerta" if len(pe) else "OK", "Enviar desde Segmentos" if len(pe) else "Al día"))
        if n:
            g1_, g2_ = c.columnas(2, "pareja")
            with g1_:
                cat_ = rel["nps_categoria"].value_counts().reindex(["Detractor", "Pasivo", "Promotor"]).fillna(0).reset_index()
                cat_.columns = ["Categoría", "Respuestas"]
                fig = px.bar(cat_, x="Categoría", y="Respuestas", color="Categoría", color_discrete_map=c.NPS_COLOR,
                             title="Promotores, pasivos y detractores", text="Respuestas")
                fig.update_traces(textposition="outside", cliponaxis=False)
                fig.update_layout(showlegend=False)
                fig.update_xaxes(title="")
                fig.update_yaxes(title="", tickformat="d", rangemode="tozero", dtick=max(1, int(cat_["Respuestas"].max() // 5)))
                c.grafico(fig, 240)
            with g2_:
                ben = rel["beneficios_usados"].dropna().str.split("; ").explode().value_counts().reset_index()
                ben.columns = ["Beneficio", "Respuestas"]
                fig = px.bar(ben.sort_values("Respuestas"), x="Respuestas", y="Beneficio", orientation="h", text="Respuestas",
                             title="Beneficios que dicen haber usado", color_discrete_sequence=[c.C["morado"]])
                fig.update_traces(textposition="outside", cliponaxis=False, textfont=dict(color=c.C["tinta"]))
                fig.update_xaxes(title="", showticklabels=False, showgrid=False, range=[0, ben["Respuestas"].max() * 1.25])
                fig.update_yaxes(title="")
                c.grafico(fig, 240)
            razones = rel["razon_nps"].dropna().drop_duplicates()
            for t in razones.head(3):
                c.hallazgo(f"«{c._e(t[:160])}»")
        else:
            st.markdown("El tablero ya está **listo para recibirla**: cuando ACTHO active la encuesta y deje la exportación en "
                        "`Datos/3. Encuestas y NPS/`, este bloque mostrará el NPS de la asociación, la intención de renovar, "
                        "la calificación de la bienvenida y de la ejecutiva, y los beneficios que cada afiliado dice usar "
                        "(que también alimentan el indicador de uso de beneficios).")
        if len(pe):
            with st.expander(f"Empresas por encuestar ({c.fmt(len(pe))})", icon=":material/outgoing_mail:"):
                c.tabla_df(pe[["empresa_id", "ejecutiva", "nivel_2027", "motivo", "fecha_afiliacion", "dias_a_vencer"]], height=260,
                           column_config={"empresa_id": "Empresa", "ejecutiva": "Ejecutiva", "nivel_2027": "Nivel",
                                          "motivo": "Por qué ahora",
                                          "fecha_afiliacion": st.column_config.DateColumn("Afiliada", format="DD/MM/YYYY"),
                                          "dias_a_vencer": st.column_config.NumberColumn("Días a vencer", format="%d")})
                c.descargar(pe, "encuesta_90_dias_por_enviar.csv", "Exportar lista")

    ctrl = ia.t("control")
    if len(ctrl):
        with c.tarjeta("¿Algo se salió de lo normal?", "✦ Gráficos de control: puntos fuera de los límites merecen revisión"):
            t1, t2 = st.tabs(["Satisfacción por evento", "NPS por mes"])
            for tab_, serie, eje, fmt_ in ((t1, "satisfaccion_evento", "Satisfacción (1 a 5)", ".2f"),
                                           (t2, "nps_mensual", "NPS", ".0f")):
                d = ctrl[ctrl["serie"] == serie].copy()
                d["periodo"] = pd.to_datetime(d["periodo"])
                d = d.sort_values("periodo")
                with tab_:
                    if d.empty:
                        st.caption("Sin suficientes respuestas.")
                        continue
                    fig = go.Figure()
                    fig.add_scatter(x=d["periodo"], y=d["lcs"], mode="lines", line=dict(color=c.C["lavanda_graf"], dash="dot", shape="hv"),
                                    name="Límite superior", hoverinfo="skip")
                    fig.add_scatter(x=d["periodo"], y=d["lci"], mode="lines", line=dict(color=c.C["lavanda_graf"], dash="dot", shape="hv"),
                                    name="Límite inferior", fill="tonexty", fillcolor="rgba(239,230,255,.45)", hoverinfo="skip")
                    fig.add_hline(y=d["centro"].iloc[0], line=dict(color=c.C["gris"], width=1),
                                  annotation_text=f"Promedio {d['centro'].iloc[0]:{fmt_}}", annotation_position="top left")
                    fuera = d["fuera"].fillna("") != ""
                    fig.add_scatter(x=d["periodo"], y=d["valor"], mode="lines+markers", name="Valor",
                                    line=dict(color=c.C["morado"], width=2),
                                    marker=dict(size=[12 if f_ else 8 for f_ in fuera],
                                                color=[c.C["naranja"] if f_ else c.C["morado"] for f_ in fuera]),
                                    customdata=np.c_[d["etiqueta"].astype(str).str[:70], d["n"]],
                                    hovertemplate="%{customdata[0]}<br><b>%{y:" + fmt_ + "}</b> · %{customdata[1]} respuestas<extra></extra>")
                    fig.update_yaxes(title=eje)
                    fig.update_xaxes(title="")
                    c.grafico(fig, 280, f"{c.fmt(fuera.sum())} fuera de control · el ancho de la banda depende de cuántas respuestas tuvo cada punto")
            ia.nota("control")

with der, c.panel():
    temas = c.tabla("v_temas_solicitados")
    dem = ia.t("tema_demanda")
    if len(dem):   # con IA: los 12 temas leídos de todos los comentarios, no solo de la encuesta estructurada
        temas = dem[dem["solicitudes"] > 0].rename(columns={"solicitudes": "menciones"})[["tema", "menciones"]]
        temas = temas.sort_values("menciones", ascending=False)
    temas["tema_completo"] = temas["tema"]
    temas["tema"] = temas["tema"].map(lambda t: c.partir(t, 22))
    with c.tarjeta():
        fig = px.bar(temas.head(8).sort_values("menciones"), x="menciones", y="tema", orientation="h",
                     title="Lo que piden los afiliados", color_discrete_sequence=[c.C["morado"]],
                     custom_data=["tema_completo"])
        fig.update_traces(hovertemplate="%{customdata[0]}: <b>%{x}</b> menciones<extra></extra>")
        fig.update_yaxes(title="")
        fig.update_xaxes(title="")
        fig.update_layout(bargap=0.3)
        c.grafico(fig, 380, "Temas para próximos espacios" + (" · ✦ leídos con IA de todos los comentarios" if len(dem) else ""))
    gusto = r["lo_que_gusto"].dropna()
    gusto = gusto[gusto.str.len() > 15]
    mejora = r["a_mejorar"].dropna()
    mejora = mejora[mejora.str.len() > 10]
    items = [f"<b>Lo que más gustó</b><br><span>«{t[:140]}»</span>" for t in gusto.head(2)]
    items += [f"<b>Qué mejorar</b><br><span>«{t[:140]}»</span>" for t in mejora.head(2)]
    if not items:
        items = ["<b>Sin comentarios abiertos</b><br><span>No hay comentarios en la selección actual.</span>"]
    c.pulso(items, titulo="Voz de los asistentes", lema="Comentarios recientes de la encuesta post-evento")
