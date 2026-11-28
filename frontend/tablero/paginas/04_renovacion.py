# -*- coding: utf-8 -*-
"""04 · Renovación y retención: calendario de vencimientos, cartera por ejecutiva y factores de retención."""
import pandas as pd
import plotly.express as px
import plotly.colors as pcolors
import plotly.graph_objects as go
import streamlit as st

import comun as c
import extracto
import ia


@st.cache_data(ttl=300, show_spinner="Generando los extractos de valor…")
def _zip_extractos(ids: tuple, corte: str) -> bytes:
    todas_ = c.empresas()
    sel = todas_[todas_["empresa_id"].isin(ids)]
    u = c.uso_beneficios()
    a = c.asistencia()
    r = c.encuestas()
    return extracto.zip_extractos(sel, u[u["empresa_id"].isin(ids)], a[a["empresa_id"].isin(ids)],
                                  r[r["empresa_id"].isin(ids)], c.catalogo(), corte, ia.t("recomendacion"))

c.encabezado("Renovación y retención", "Quién vence, quién está en riesgo y en qué cartera, a tiempo para actuar")

p = c.parametros()
corte = pd.Timestamp(p["fecha_corte"])
todas = c.filtrar_empresas(c.empresas())
vig = ia.con_ia(todas[todas["es_vigente"] == 1])
if "p_renovar" not in vig:
    vig["p_renovar"] = None
acc = ia.t("accion")
vig = vig.merge(acc, on="empresa_id", how="left") if len(acc) else vig.assign(accion=None)

ventana = st.segmented_control("Ventana de vencimiento", [30, 60, 90], default=90, key="ren_ventana",
                               format_func=lambda d: f"Próximos {d} días") if hasattr(st, "segmented_control") else \
    st.radio("Ventana de vencimiento", [30, 60, 90], index=2, horizontal=True, key="ren_ventana")
ventana = ventana or 90
prox = vig[(vig["dias_a_vencer"].between(0, ventana)) | (vig["rango_vencimiento"] == "Vencida")]

renov = c.tasa_renovacion(todas)
k = c.fila(5)
c.kpi(k[0], f"Vencen en {ventana} días", c.fmt(vig["dias_a_vencer"].between(0, ventana).sum()),
      "Membresías vigentes por renovar", oscuro=True,
      chip_=("Morado", f"{c.fmt((vig['rango_vencimiento'] == 'Vencida').sum())} vencidas en gracia"))
c.kpi(k[1], "Prioridad alta", c.fmt((prox["semaforo"] == "Rojo").sum()), "Con riesgo alto dentro de la ventana",
      chip_=("Riesgo", "Contactar primero"))
c.kpi(k[2], "Sin participación", c.fmt((~prox["participa_en_ventana"].astype(bool)).sum()),
      "Sin asistencias en 90 días", chip_=("Alerta", "Reactivar antes de renovar"))
c.kpi(k[3], "Tasa de renovación", c.fmt(renov["tasa"], 1, " %"), f"{renov['tipo'].capitalize()} · últimos 12 meses · con los filtros",
      chip_=("Alerta" if (renov["tasa"] or 0) < 90 else "OK", "Meta 2027: 90 %"),
      ayuda_=c.ayuda("Tasa de renovación (medida)" if renov["tipo"] == "medida" else "Tasa de renovación (aproximada)"))
c.kpi(k[4], "Retiros", c.fmt(renov["no_renovo"]), "No renovaron en 12 meses",
      chip_=("Riesgo", "Motivo no registrado"), ayuda_=c.ayuda("Retiros"))

izq, der = c.columnas([2.3, 1], "lateral", gap="medium")
with izq:
    with c.tarjeta():
        c.cabeza("Calendario de renovaciones", f"{c.fmt(len(prox))} empresas por contactar · primero las de mayor prioridad")
        orden_ia = prox["p_renovar"].notna().any() and st.toggle(
            "Ordenar por probabilidad de renovar (✦ IA), de menor a mayor", value=True, key="ren_orden_ia",
            help="Apagado, se ordena por el semáforo de riesgo y la cercanía del vencimiento. " + ia.desc("renovacion"))
        prox_o = (prox.sort_values(["p_renovar", "dias_a_vencer"]) if orden_ia
                  else prox.sort_values(["puntaje_riesgo", "dias_a_vencer"], ascending=[False, True]))
        lista = prox_o[["empresa_id", "semaforo", "p_renovar", "ejecutiva", "nivel_2027", "fecha_expiracion", "dias_a_vencer",
                        "inscripciones_12m", "satisfaccion_promedio", "accion", "motivos_riesgo"]].copy()
        lista["satisfaccion_promedio"] = lista["satisfaccion_promedio"].map(lambda v: c.fmt(v, 2))
        lista["semaforo"] = lista["semaforo"].map(c.SEM_TXT).fillna("Sin evaluar")
        sel = c.tabla_df(lista, height=min(330, 36 * (len(lista) + 1) + 4), on_select="rerun", selection_mode="single-row",
                         key="ren_tabla",
                         column_config={
                             "empresa_id": "Empresa", "semaforo": "Riesgo", "ejecutiva": "Ejecutiva",
                             "p_renovar": st.column_config.ProgressColumn("✦ Prob. renovar", min_value=0, max_value=1,
                                                                          format="percent", width="small",
                                                                          help=ia.desc("renovacion")),
                             "accion": st.column_config.TextColumn("✦ Siguiente paso", width="medium", help=ia.desc("accion")),
                             "nivel_2027": st.column_config.TextColumn("Nivel", width="small"),
                             "fecha_expiracion": st.column_config.DateColumn("Vence", format="DD/MM/YYYY"),
                             "dias_a_vencer": st.column_config.NumberColumn("Días", format="%d"),
                             "inscripciones_12m": "Asist. 12m",
                             "satisfaccion_promedio": "Satisf.",
                             "motivos_riesgo": st.column_config.TextColumn("Motivos", width="large")})
        b1, b2, b3 = c.columnas([1.25, 1.25, 1], "controles")
        with b1:
            c.descargar(lista, f"vencimientos_{ventana}_dias.csv", "Exportar para campaña de renovación")
        if len(lista):
            b2.download_button(f"Extractos de valor ({c.fmt(len(lista))}, ZIP)",
                               _zip_extractos(tuple(sorted(lista["empresa_id"])), str(p["fecha_corte"])),
                               file_name=f"extractos_valor_{ventana}_dias.zip", mime="application/zip",
                               icon=":material/folder_zip:", key="ren_zip",
                               help="Un extracto por empresa de la lista, para llevar a la conversación de renovación")
        if prox["p_renovar"].notna().any():
            ia.nota("renovacion", f"se esperan ≈{c.fmt(prox['p_renovar'].sum())} renovaciones de las "
                                  f"{c.fmt(prox['p_renovar'].notna().sum())} de la lista")
        filas = sel.selection.rows if sel is not None and hasattr(sel, "selection") else []
        if filas and b3.button("Abrir ficha 360°", **c.ancho(st.button)):
            c.ir("03_ficha_360.py", lista.iloc[filas[0]]["empresa_id"])

    with c.tarjeta():
        dims = ["ejecutiva", "mes_venc"]
        e_c, _, _ = c.datos(excluir=dims)
        mes = e_c[(e_c["es_vigente"] == 1) & e_c["fecha_expiracion"].notna()
                  & (e_c["fecha_expiracion"] <= corte + pd.DateOffset(months=12))]
        calor = mes.pivot_table(index="ejecutiva", columns="mes_venc", values="empresa_id", aggfunc="count", fill_value=0)
        if calor.empty:
            c.cabeza("Vencimientos por ejecutiva", "Membresías vigentes por mes de expiración")
            st.info("No hay vencimientos en los próximos 12 meses con los filtros actuales.")
        else:
            # Mapa de calor dibujado con marcadores cuadrados: se ve igual y, a diferencia de go.Heatmap,
            # admite el clic para filtrar.
            celdas = calor.stack().reset_index(name="n")
            celdas.columns = ["ejecutiva", "mes_venc", "n"]
            celdas["x"] = celdas["mes_venc"].map(lambda m: c.anio_mes_txt(m).replace(" ", "<br>"))
            celdas["y"] = celdas["ejecutiva"].str.replace(" (cuenta ACTHO)", "", regex=False)
            maximo = max(celdas["n"].max(), 1)
            escala = [[0, c.C["lavanda"]], [0.5, c.C["lavanda_graf"]], [1, c.C["morado"]]]
            colores = ["#F6F2FF" if v == 0 else pcolors.sample_colorscale(escala, v / maximo, colortype="rgb")[0]
                       for v in celdas["n"]]
            sel_ = c.xf()
            elegida = [(sel_.get("ejecutiva", ej) == ej) and (sel_.get("mes_venc", m) == m)
                       for ej, m in zip(celdas["ejecutiva"], celdas["mes_venc"])]
            hay_sel = any(d in sel_ for d in dims)
            if hay_sel:   # como en Power BI: se atenúa lo que no está elegido
                colores = [col if ok else col.replace("rgb(", "rgba(").replace(")", ",0.25)") if col.startswith("rgb(")
                           else "rgba(246,242,255,0.4)" for col, ok in zip(colores, elegida)]
            fig = go.Figure(go.Scatter(
                x=celdas["x"], y=celdas["y"], mode="markers+text", text=celdas["n"],
                textfont=dict(color=[c.C["gris"] if (v == 0 or (hay_sel and not ok)) else
                                     (c.C["tinta"] if v < maximo * .5 else "#FFFFFF")
                                     for v, ok in zip(celdas["n"], elegida)], size=12),
                marker=dict(symbol="square", size=30, color=colores,
                            line=dict(width=[3 if (hay_sel and ok) else 0 for ok in elegida], color=c.C["naranja"])),
                customdata=celdas[["ejecutiva", "mes_venc"]].to_numpy(),
                hovertemplate="%{y} · %{x}: <b>%{text}</b> vencimientos<extra></extra>", showlegend=False))
            fig.update_layout(title="Vencimientos por ejecutiva")
            fig.update_xaxes(title="", showgrid=False, ticks="", showline=False, categoryorder="array",
                             categoryarray=list(dict.fromkeys(celdas["x"])))
            fig.update_yaxes(title="", showgrid=False, ticks="", showline=False, autorange="reversed", categoryorder="array",
                             categoryarray=list(dict.fromkeys(celdas["y"])))
            c.grafico(fig, 60 + 38 * celdas["y"].nunique(),
                      "Membresías vigentes por mes de expiración · clic en una celda para filtrar", dims=dims, clave="calor")
    with c.tarjeta():
        c.cabeza("Seguimiento por ejecutiva de cuenta", "Cartera vigente, participación, satisfacción y empresas por nivel de riesgo")
        cart = vig.groupby("ejecutiva").agg(
            vigentes=("empresa_id", "count"),
            vencen_90=("dias_a_vencer", lambda s: s.between(0, 90).sum()),
            vencidas=("rango_vencimiento", lambda s: (s == "Vencida").sum()),
            participan=("participa_en_ventana", "mean"),
            satisfaccion=("satisfaccion_promedio", "mean"),
            rojo=("semaforo", lambda s: (s == "Rojo").sum()),
            amarillo=("semaforo", lambda s: (s == "Amarillo").sum()),
            verde=("semaforo", lambda s: (s == "Verde").sum()),
        ).reset_index().sort_values("rojo", ascending=False)
        cart["participan"] = (100 * pd.to_numeric(cart["participan"], errors="coerce")).round(1)
        cart["satisfaccion"] = pd.to_numeric(cart["satisfaccion"], errors="coerce").map(lambda v: c.fmt(v, 2))
        c.tabla_df(cart, column_config={
            "ejecutiva": st.column_config.TextColumn("Ejecutiva", width="small"),
            "vigentes": st.column_config.NumberColumn("Vigentes", width="small"),
            "vencen_90": st.column_config.NumberColumn("Vencen 90 d", width="small"),
            "vencidas": st.column_config.NumberColumn("Vencidas", width="small"),
            "participan": st.column_config.ProgressColumn("% participa", min_value=0, max_value=100, format="%.0f %%", width="small"),
            "satisfaccion": st.column_config.TextColumn("Satisf.", width="small"),
            "rojo": st.column_config.NumberColumn("Alto", width="small", help="Empresas con riesgo alto"),
            "amarillo": st.column_config.NumberColumn("Medio", width="small", help="Empresas con riesgo medio"),
            "verde": st.column_config.NumberColumn("Bajo", width="small", help="Empresas con riesgo bajo")})

with der, c.panel("Retención", "Qué se asocia con quedarse"):
    rel = c.tabla("v_relacion_participacion_renovacion")
    with c.tarjeta():
        fig = px.bar(rel, y="nivel_participacion_12m", x="pct_vigentes", text="pct_vigentes", orientation="h",
                     title="Vigencia según participación", color_discrete_sequence=[c.C["morado"]])
        fig.update_traces(texttemplate="%{x:.0f} %", textposition="outside", cliponaxis=False,
                          textfont=dict(color=c.C["tinta"]), hovertemplate="%{y}: <b>%{x:.1f} %</b> sigue vigente<extra></extra>")
        fig.update_xaxes(range=[0, 125], title="", showticklabels=False, showgrid=False)
        fig.update_yaxes(title="", autorange="reversed")
        c.grafico(fig, 250, "% que sigue vigente · asistencias en 12 meses · toda la base")
    hist = c.tabla("v_movimientos_mensuales", "historial") if c.existe("historial.v_movimientos_mensuales") else pd.DataFrame()
    items = []
    coef = ia.t("renovacion_coef")
    if len(coef):
        top = coef.head(4)
        items.append(f"<b>✦ Lo que más pesa en el modelo</b>{ia.info('renovacion')}<br><span>" + " · ".join(
            f"{r.etiqueta} ({'+' if r.coeficiente > 0 else '−'})" for r in top.itertuples()) + "</span>")
    items += [
        "<b>Motivos de no renovación</b><br><span>El CRM no registra el motivo del retiro. Se propone capturarlo "
        "con una lista cerrada al cancelar (ver Datos y calidad).</span>",
        ("<b>Renovaciones medidas</b><br><span>" +
         (f"{c.fmt(hist['renovaciones'].sum())} renovaciones y {c.fmt(hist['retiros'].sum())} retiros en "
          f"{len(hist)} mes(es) con foto mensual.</span>" if len(hist) else
          "La tasa es aproximada hasta tener dos fotos mensuales (DAG diario de Airflow).</span>")),
    ]
    with c.tarjeta():
        crm = todas[(todas["en_crm"] == 1) & (todas["estado_membresia"] != "Sin estado") & todas["fecha_afiliacion"].notna()].copy()
        anios = (corte - crm["fecha_afiliacion"]).dt.days / 365.25
        crm["antiguedad"] = pd.cut(anios, [-1, 1, 2, 4, 8, 100],
                                   labels=["Menos de 1 año", "1-2 años", "2-4 años", "4-8 años", "Más de 8 años"])
        ret = crm.groupby("antiguedad", observed=False).agg(empresas=("empresa_id", "count"),
                                                            vigentes=("es_vigente", "sum")).reset_index()
        ret["% vigente"] = (100 * ret["vigentes"] / ret["empresas"]).round(1)
        fig = px.bar(ret, y="antiguedad", x="% vigente", text="% vigente", custom_data=["empresas"], orientation="h",
                     title="Retención por antigüedad", color_discrete_sequence=[c.C["naranja"]])
        fig.update_traces(texttemplate="%{x:.0f} %", textposition="outside", cliponaxis=False,
                          textfont=dict(color=c.C["tinta"]),
                          hovertemplate="%{y}: <b>%{x:.1f} %</b> vigente · %{customdata[0]} empresas<extra></extra>")
        fig.update_xaxes(range=[0, 125], title="", showticklabels=False, showgrid=False)
        fig.update_yaxes(title="", autorange="reversed")
        c.grafico(fig, 260, "% que sigue vigente según años de afiliación")
    for i in items:
        partes = i.split("<br>", 1)
        c.actividad(partes[0].replace("<b>", "").replace("</b>", ""), partes[1].replace("<span>", "").replace("</span>", ""), acento=True)
