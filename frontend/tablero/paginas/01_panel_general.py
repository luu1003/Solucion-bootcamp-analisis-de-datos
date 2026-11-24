# -*- coding: utf-8 -*-
"""01 · Panel general: metas 2027, salud de la base, vencimientos, participación y satisfacción.

Los gráficos funcionan como en Power BI: un clic en una barra, un segmento o un punto filtra todo el
panel; el gráfico de origen no se filtra a sí mismo, sino que resalta lo elegido."""
import pandas as pd
import plotly.express as px
import streamlit as st

import comun as c

c.encabezado("Dashboard", "Cómo va la asociación: afiliados, retención, participación y satisfacción")

p = c.parametros()
corte = pd.Timestamp(p["fecha_corte"])
e, a, r = c.datos()
vig = e[e["es_vigente"] == 1]
filtrado = c.hay_filtros_empresa() or bool(c.xf())

# Indicadores sobre la selección actual
renov = c.tabla("v_tasa_renovacion").iloc[0]
part = 100 * vig["participa_en_ventana"].mean() if len(vig) else None
sat = r["satisfaccion_general"].fillna(r["satisfaccion_prom"]).mean()
nps_n = r["nps_puntaje"].notna().sum()
nps = (100 * ((r["nps_categoria"] == "Promotor").sum() - (r["nps_categoria"] == "Detractor").sum()) / nps_n) if nps_n else None
v90 = vig[vig["dias_a_vencer"].between(0, 90)]
rojos = (vig["semaforo"] == "Rojo").sum()

principal, lateral = st.columns([3.2, 1], gap="medium")
with principal:
    m1, m2 = c.fila(2)
    brecha = c.METAS_2027["renovacion"] - renov["tasa_renovacion_aprox"]
    c.meta(m1, "Tasa de renovación", renov["tasa_renovacion_aprox"], c.METAS_2027["renovacion"],
           f"Aproximada{' · toda la base' if filtrado else ''}: {c.fmt(renov['renovados'])} renovados y "
           f"{c.fmt(renov['no_renovados'])} no renovados en 12 meses",
           chip_=("Alerta" if brecha > 0 else "OK", f"{c.fmt(brecha, 1)} pts por debajo" if brecha > 0 else "Sobre la meta"))
    sobre = (nps or 0) >= c.METAS_2027["nps"]
    c.meta(m2, "NPS de eventos", nps, c.METAS_2027["nps"],
           f"{c.fmt(nps_n)} respuestas con NPS · el NPS de ACTHO (encuesta de 90 días) aún no tiene respuestas", sufijo="",
           chip_=("Neutro", "Sin respuestas") if nps is None else ("OK" if sobre else "Alerta", "Sobre la meta" if sobre else "Bajo la meta"))
    k = c.fila(5)
    nuevos = int(vig["es_nuevo_afiliado"].fillna(False).sum())
    c.kpi(k[0], "Afiliados activos", c.fmt((vig["es_activo"] == 1).sum()), f"{c.fmt(len(vig))} vigentes con gracia y por expirar",
          oscuro=True, chip_=("Morado", f"+{nuevos} nuevos en 90 días"))
    c.kpi(k[1], "Vencen en 90 días", c.fmt(len(v90)), "Membresías vigentes por renovar",
          chip_=("Riesgo", f"{c.fmt((vig['rango_vencimiento'] == 'Vencida').sum())} ya vencidas"))
    c.kpi(k[2], "Participación activa", c.fmt(part, 1, " %"), "Vigentes con al menos una asistencia en 90 días",
          chip_=("Alerta", f"{c.fmt((~vig['participa_en_ventana'].astype(bool)).sum())} sin asistir"))
    c.kpi(k[3], "Satisfacción", c.fmt(sat, 2), f"Promedio 1-5 de {c.fmt(len(r))} respuestas",
          chip_=("OK" if (sat or 0) >= 4.5 else "Alerta", "Alta" if (sat or 0) >= 4.5 else "Por mejorar"))
    c.kpi(k[4], "Riesgo alto de no renovar", c.fmt(rojos), "Empresas vigentes con riesgo alto",
          chip_=("Alerta", f"{c.fmt((vig['semaforo'] == 'Amarillo').sum())} con riesgo medio"))

    g1, g2 = st.columns([1.35, 1])
    with g1:
        with c.tarjeta():
            dims = ["mes_venc", "semaforo"]
            e1, _, _ = c.datos(excluir=dims)
            v1 = e1[(e1["es_vigente"] == 1) & e1["fecha_expiracion"].notna()
                    & (e1["fecha_expiracion"] <= corte + pd.DateOffset(months=12))]
            serie = v1.groupby(["mes_venc", "semaforo"]).size().reset_index(name="empresas").sort_values("mes_venc")
            serie["Riesgo"] = serie["semaforo"].map(c.SEM_TXT)
            serie["Mes"] = serie["mes_venc"].map(lambda m: c.anio_mes_txt(m).replace(" ", "<br>"))
            fig = px.bar(serie, x="Mes", y="empresas", color="Riesgo", color_discrete_map=c.RIESGO,
                         custom_data=dims, title="Vencimientos de los próximos 12 meses",
                         category_orders={"Riesgo": c.ORDEN_RIESGO},
                         labels={"empresas": "Empresas", "Mes": "Mes de expiración"})
            fig.update_xaxes(title="", tickangle=0, categoryorder="array", categoryarray=list(dict.fromkeys(serie["Mes"])))
            fig.update_yaxes(title="Empresas")
            fig.update_traces(hovertemplate="%{x}<br>Riesgo %{fullData.name}: <b>%{y}</b> empresas<extra></extra>")
            c.grafico(fig, 300, "Membresías vigentes por mes de expiración y nivel de riesgo · clic para filtrar",
                      dims=dims, clave="venc")
    with g2:
        with c.tarjeta():
            e2, _, _ = c.datos(excluir=("semaforo",))
            v2 = e2[e2["es_vigente"] == 1]
            sem = v2["semaforo"].value_counts().reindex(["Rojo", "Amarillo", "Verde"]).fillna(0).reset_index()
            sem.columns = ["semaforo", "empresas"]
            sem["Riesgo"] = sem["semaforo"].map(c.SEM_TXT)
            total = max(sem["empresas"].sum(), 1)
            sem["etiqueta"] = [f"<b>{c.fmt(n)}</b>  ·  {c.fmt(100 * n / total, 0)} %" for n in sem["empresas"]]
            fig = px.bar(sem, x="empresas", y="Riesgo", orientation="h", color="Riesgo", text="etiqueta",
                         color_discrete_map=c.RIESGO, custom_data=["semaforo"], title="Semáforo de riesgo",
                         category_orders={"Riesgo": c.ORDEN_RIESGO})
            fig.update_traces(textposition="outside", cliponaxis=False, textfont=dict(color=c.C["tinta"], size=13),
                              width=0.62, hovertemplate="Riesgo %{y}: <b>%{x}</b> empresas<extra></extra>")
            fig.update_layout(showlegend=False, bargap=0.25)
            fig.update_xaxes(title="", showticklabels=False, showgrid=False, range=[0, sem["empresas"].max() * 1.55 + 1])
            fig.update_yaxes(title="", ticksuffix="  ", tickfont=dict(size=13))
            c.grafico(fig, 262, f"{c.fmt(len(v2))} vigentes · vencimiento + participación + satisfacción · clic para filtrar",
                      dims=["semaforo"], clave="sem")

    with c.tarjeta():
        c.cabeza("Renovaciones prioritarias", "Próximos 90 días y vencidas sin renovar · ordenadas por riesgo")
        top = vig[vig["dias_a_vencer"].between(-365, 90)].sort_values(["puntaje_riesgo", "dias_a_vencer"],
                                                                       ascending=[False, True]).head(6)
        if len(top):
            filas = [{"emp": r_.empresa_id, "det": f"{r_.nivel_2027} · {r_.sector}", "ej": r_.ejecutiva,
                      "vence": c.fecha_txt(r_.fecha_expiracion),
                      "dias": (f"hace {c.fmt(-r_.dias_a_vencer)} días" if r_.dias_a_vencer < 0 else f"en {c.fmt(r_.dias_a_vencer)} días"),
                      "asis": c.fmt(r_.inscripciones_12m), "sem": c.chip_semaforo(r_.semaforo),
                      "mot": r_.motivos_riesgo or ""} for r_ in top.itertuples()]
            c.tabla_html(filas, [("Afiliado", ("emp", "det"), "texto"), ("Ejecutiva", "ej", "nw"),
                                 ("Vence", ("vence", "dias"), "nw"), ("Asist. 12 m", "asis", "num"),
                                 ("Riesgo", "sem", "html"), ("Por qué", "mot", "texto")])
            if st.button("Ver todo el calendario de renovaciones", icon=":material/arrow_forward:", key="ir_renov"):
                c.ir("04_renovacion.py")
        else:
            st.info("No hay renovaciones en los próximos 90 días con los filtros actuales.")

    g3, g4 = st.columns(2)
    with g3:
        with c.tarjeta():
            dims = ["anio_mes", "condicion_empresa"]
            _, a3, _ = c.datos(excluir=dims)
            pm = a3.groupby(["anio_mes", "condicion_empresa"]).size().reset_index(name="inscripciones").sort_values("anio_mes")
            pm["Mes"] = pm["anio_mes"].map(lambda m: c.anio_mes_txt(m).replace(" ", "<br>"))
            pm["Empresa"] = pm["condicion_empresa"]
            fig = px.bar(pm, x="Mes", y="inscripciones", color="Empresa", color_discrete_map=c.CONDICION,
                         custom_data=dims, title="Participación en experiencias")
            fig.update_xaxes(title="", tickangle=0)
            fig.update_yaxes(title="Inscripciones")
            fig.update_traces(hovertemplate="%{x} · %{fullData.name}: <b>%{y}</b> inscripciones<extra></extra>")
            c.grafico(fig, 280, "Inscripciones por mes · afiliadas y no afiliadas · clic para filtrar",
                      dims=dims, clave="part")
    with g4:
        with c.tarjeta():
            e4, _, _ = c.datos(excluir=("nivel_2027",))
            v4 = e4[e4["es_vigente"] == 1]
            niv = v4.groupby("nivel_2027").agg(vigentes=("empresa_id", "count"),
                                               participan=("participa_en_ventana", "sum")).reset_index()
            niv["pct"] = (100 * niv["participan"] / niv["vigentes"]).round(1)
            fig = px.bar(niv.sort_values("vigentes"), x="vigentes", y="nivel_2027", orientation="h", text="vigentes",
                         custom_data=["nivel_2027", "pct"], title="Afiliados por nivel 2027",
                         color_discrete_sequence=[c.C["morado"]])
            fig.update_traces(textposition="outside", cliponaxis=False, textfont=dict(color=c.C["tinta"]),
                              hovertemplate="%{y}: <b>%{x}</b> vigentes · %{customdata[1]} % participa<extra></extra>")
            fig.update_yaxes(title="")
            fig.update_xaxes(title="Empresas vigentes", range=[0, max(niv["vigentes"].max(), 1) * 1.18])
            c.grafico(fig, 280, "Conectar · Crecer · Liderar · clic para filtrar", dims=["nivel_2027"], clave="nivel")

    with c.tarjeta():
        _, _, r5 = c.datos(excluir=("anio_mes",))
        sm = r5.assign(sat=r5["satisfaccion_general"].fillna(r5["satisfaccion_prom"])).groupby("anio_mes") \
               .agg(satisfaccion=("sat", "mean"), respuestas=("encuesta_id", "count")).reset_index().sort_values("anio_mes")
        sm["Mes"] = sm["anio_mes"].map(c.anio_mes_txt)
        fig = px.line(sm, x="Mes", y="satisfaccion", markers=True, custom_data=["anio_mes", "respuestas"],
                      title="Satisfacción mensual", color_discrete_sequence=[c.C["naranja"]])
        fig.update_traces(line_width=3, marker_size=9,
                          hovertemplate="%{x}: <b>%{y:.2f}</b> de 5 · %{customdata[1]} respuestas<extra></extra>")
        fig.update_yaxes(range=[1, 5.2], title="Promedio 1-5")
        fig.update_xaxes(title="")
        c.grafico(fig, 240, "Promedio de las encuestas de eventos · escala 1 a 5 · clic en un mes para filtrar",
                  dims=["anio_mes"], clave="satm")

with lateral, c.panel():
    dic31 = vig[vig["fecha_expiracion"] == pd.Timestamp(corte.year, 12, 31)]
    rel = c.tabla("v_relacion_participacion_renovacion")
    alto = rel[rel["nivel_participacion_12m"] == "6 o más"]["pct_vigentes"]
    cero = rel[rel["nivel_participacion_12m"] == "0 asistencias"]["pct_vigentes"]
    cart = vig[vig["semaforo"] == "Rojo"].groupby("ejecutiva").size().sort_values(ascending=False)
    items = []
    if len(dic31):
        items.append(f"<b>{c.fmt(len(dic31))} membresías vencen el 31 de diciembre</b><br>"
                     f"<span>{c.fmt((dic31['semaforo'] == 'Rojo').sum())} de ellas ya tienen riesgo alto. "
                     f"Es la ola de renovación del año.</span>")
    if part is not None:
        items.append(f"<b>{c.fmt(100 - part, 0)} % de los vigentes no asistió a nada en 90 días</b><br>"
                     f"<span>Pagan pero no usan los beneficios: son el primer segmento a reactivar.</span>")
    if len(alto) and len(cero):
        items.append(f"<b>Participar se asocia con quedarse</b><br><span>Con 6 o más asistencias sigue vigente el "
                     f"{c.fmt(alto.iloc[0], 0)} %; sin asistencias, el {c.fmt(cero.iloc[0], 0)} %.</span>")
    if len(cart):
        items.append(f"<b>{cart.index[0]} concentra más empresas en riesgo alto</b><br>"
                     f"<span>{c.fmt(cart.iloc[0])} empresas con riesgo alto en su cartera.</span>")
    if not items:
        items.append("<b>Sin lecturas para esta selección</b><br><span>Quita algún filtro para ver más datos.</span>")
    c.pulso(items, "Pulso", "Sentimos el pulso. Lo convertimos en acción.")
    if st.button("Ver afiliados en riesgo", type="primary", key="ir_riesgo", **c.ancho(st.button)):
        st.session_state["dir_sem"] = ["Rojo"]
        c.ir("02_afiliados.py")
