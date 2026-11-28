# -*- coding: utf-8 -*-
"""06 · Pulso: alertas, factores asociados a la retención y simulador de criterios del semáforo."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import comun as c
import ia

c.encabezado("Pulso", "Alertas, factores de riesgo y criterios del semáforo para decidir con ACTHO")

p = c.parametros()
todas = c.filtrar_empresas(c.empresas())
vig = todas[todas["es_vigente"] == 1].copy()

c.heroe("Sentimos el pulso. Lo convertimos en acción.", "¿A quién podemos perder y qué hacemos hoy?",
        "Alertas del semáforo, factores que se asocian con la renovación y un simulador para acordar los criterios con Dirección.")

tab1, tab2, tab3 = st.tabs(["Alertas", "Factores de retención", "Simulador de criterios"])

with tab1:
    hist = c.tabla("evaluacion_riesgo", "historial") if c.existe("historial.evaluacion_riesgo") else pd.DataFrame()
    fechas = sorted(hist["fecha_corte"].unique()) if len(hist) else []
    izq, der = st.columns([2.2, 1], gap="medium")
    with izq, c.tarjeta():
        if len(fechas) >= 2:
            ult, ant = fechas[-1], fechas[-2]
            h_ult = hist[hist["fecha_corte"] == ult].set_index("empresa_id")
            h_ant = hist[hist["fecha_corte"] == ant].set_index("empresa_id")["semaforo"]
            nuevos = h_ult[(h_ult["semaforo"] == "Rojo") & (h_ult.index.map(h_ant) != "Rojo")].reset_index()
            c.cabeza(f"{c.fmt(len(nuevos))} empresas pasaron a riesgo alto", f"Entre el {c.fecha_txt(ant)} y el {c.fecha_txt(ult)}")
            evo = hist.groupby(["fecha_corte", "semaforo"]).size().reset_index(name="empresas").sort_values("fecha_corte")
            evo["Fecha de corte"] = evo["fecha_corte"].map(c.fecha_txt)
            evo["Riesgo"] = evo["semaforo"].map(c.SEM_TXT)
            fig = px.line(evo, x="Fecha de corte", y="empresas", color="Riesgo", markers=True,
                          color_discrete_map=c.RIESGO, category_orders={"Riesgo": c.ORDEN_RIESGO},
                          title="Evolución del semáforo")
            fig.update_traces(line_width=3, marker_size=9)
            fig.update_xaxes(title="")
            fig.update_yaxes(title="")
            c.grafico(fig, 240, "Empresas vigentes por nivel de riesgo en cada recálculo diario")
            tabla_alertas = nuevos[["empresa_id", "ejecutiva", "nivel_2027", "dias_a_vencer", "puntaje", "motivos"]]
        else:
            c.cabeza("Alertas de riesgo alto", "Empresas vigentes con riesgo alto hoy")
            st.caption("El historial necesita al menos dos recálculos (DAG diario de Airflow) para mostrar cambios. "
                       "Mientras tanto se listan las empresas con riesgo alto hoy.")
            tabla_alertas = vig[vig["semaforo"] == "Rojo"].sort_values("puntaje_riesgo", ascending=False)[
                ["empresa_id", "ejecutiva", "nivel_2027", "dias_a_vencer", "puntaje_riesgo", "motivos_riesgo"]]
        tabla_alertas = tabla_alertas.rename(columns={"puntaje_riesgo": "puntaje", "motivos_riesgo": "motivos"})
        c.tabla_df(tabla_alertas, height=320, column_config={
            "empresa_id": "Empresa", "ejecutiva": "Ejecutiva", "nivel_2027": "Nivel",
            "dias_a_vencer": st.column_config.NumberColumn("Días a vencer", format="%d"),
            "puntaje": st.column_config.ProgressColumn("Puntaje", min_value=0, max_value=9, format="%d", width="small"),
            "motivos": st.column_config.TextColumn("Motivos", width="large")})
        c.descargar(tabla_alertas, "alertas_riesgo_alto.csv", "Exportar alertas")
    with der, c.panel():
        comp = pd.Series({"Vencimiento": (vig["pts_vencimiento"] > 0).sum(),
                          "Participación": (vig["pts_participacion"] > 0).sum(),
                          "Satisfacción": (vig["pts_satisfaccion"] > 0).sum()})
        c.pulso([f"<b>{c.fmt(v)} vigentes</b> con alerta de {k.lower()}" for k, v in comp.items()] +
                ["<b>Consultas en lenguaje natural</b><br><span>Pendiente: un asistente de IA que responda "
                 "preguntas sobre los datos solo podrá leer las vistas del tablero, con datos seudonimizados.</span>"],
                titulo="Pulso", lema="Qué está generando las alertas")

with tab2:
    st.caption("Asociaciones observadas en los datos, no causas: una empresa que ya decidió irse tampoco asiste.")
    crm = todas[(todas["en_crm"] == 1) & (todas["estado_membresia"] != "Sin estado")].copy()
    g1, g2, g3 = st.columns(3)
    def barra(col, df, x, titulo, sub=None):
        t = df.groupby(x, observed=False).agg(empresas=("empresa_id", "count"), vigentes=("es_vigente", "sum")).reset_index()
        t["% vigente"] = (100 * t["vigentes"] / t["empresas"]).round(1)
        fig = px.bar(t, x=x, y="% vigente", text="% vigente", custom_data=["empresas"], title=titulo,
                     color_discrete_sequence=[c.C["morado"]])
        fig.update_traces(texttemplate="%{y:.0f} %", textposition="outside", cliponaxis=False,
                          textfont=dict(color=c.C["tinta"]),
                          hovertemplate="%{x}: <b>%{y:.1f} %</b> vigente · %{customdata[0]} empresas<extra></extra>")
        fig.update_yaxes(range=[0, 118], title="")
        fig.update_xaxes(title="", type="category")
        with col:
            with c.tarjeta():
                c.grafico(fig, 260, sub)
    crm["Asistencias 12 meses"] = pd.cut(crm["inscripciones_12m"], [-1, 0, 2, 5, 1000], labels=["0", "1-2", "3-5", "6+"])
    crm["Personas distintas"] = pd.cut(crm["personas_distintas"], [-1, 0, 1, 3, 1000], labels=["0", "1", "2-3", "4+"])
    crm["Líneas usadas"] = pd.cut(crm["lineas_distintas"], [-1, 0, 1, 2, 10], labels=["0", "1", "2", "3+"])
    barra(g1, crm, "Asistencias 12 meses", "Participación", "% vigente según asistencias en 12 meses")
    barra(g2, crm, "Personas distintas", "Amplitud de la relación", "% vigente según personas que participan")
    barra(g3, crm, "Líneas usadas", "Uso de la oferta", "% vigente según líneas 2027 usadas")

    coef = ia.t("renovacion_coef")
    ren = ia.renovacion()
    if len(coef) and len(ren):
        h1, h2 = st.columns([1.2, 1], gap="medium")
        with h1, c.tarjeta("Qué pesa en la probabilidad de renovar", "✦ Modelo de IA · efecto de cada factor manteniendo los demás fijos",
                           ayuda=ia.desc("renovacion")):
            d = coef.sort_values("coeficiente")
            d["Etiqueta"] = d["etiqueta"].map(lambda t_: c.partir(t_, 30))
            fig = go.Figure(go.Bar(
                x=d["coeficiente"], y=d["Etiqueta"], orientation="h",
                marker_color=[c.C["morado"] if v > 0 else c.C["naranja"] for v in d["coeficiente"]],
                customdata=np.c_[d["razon_momios"].round(2), d["etapa"]],
                hovertemplate="%{y}<br>Efecto <b>%{x:.2f}</b> · multiplica las chances por %{customdata[0]}"
                              "<br>%{customdata[1]}<extra></extra>"))
            fig.add_vline(x=0, line=dict(color=c.C["gris"], width=1))
            fig.update_xaxes(title="← baja la probabilidad · sube la probabilidad →")
            c.grafico(fig, 420)
            ia.nota("renovacion")
        with h2, c.tarjeta("Semáforo frente al modelo", "Empresas vigentes según las dos miradas",
                           ayuda="El semáforo usa reglas fijas (vencimiento, uso reciente, satisfacción). El modelo de IA "
                                 "además pesa antigüedad, tamaño y comunidades. Cruzarlos muestra dónde no coinciden."):
            m = vig.merge(ren[["empresa_id", "banda"]], on="empresa_id")
            m["Riesgo"] = m["semaforo"].map(c.SEM_TXT)
            tab = pd.crosstab(m["Riesgo"], m["banda"]).reindex(index=c.ORDEN_RIESGO, columns=ia.ORDEN_BANDA, fill_value=0)
            fig = go.Figure(go.Heatmap(z=tab.values, x=[f"IA: {b}" for b in tab.columns], y=[f"Semáforo: {r_}" for r_ in tab.index],
                                       text=tab.values, texttemplate="%{text}", colorscale=[[0, c.C["lavanda"]], [1, c.C["morado"]]],
                                       showscale=False, hovertemplate="%{y} · %{x}: <b>%{z}</b><extra></extra>",
                                       textfont=dict(size=14)))
            fig.update_yaxes(autorange="reversed")
            c.grafico(fig, 260)
            ojo = m[(m["semaforo"] == "Verde") & (m["banda"] == "En riesgo")]
            st.markdown(f'<div class="hallazgo"><div><b>{c.fmt(len(ojo))} empresas con semáforo bajo que el modelo ve en '
                        'riesgo.</b> El semáforo mira vencimiento, uso reciente y satisfacción; el modelo además pesa '
                        'antigüedad, tamaño y comunidades. Son las que conviene revisar.</div></div>', unsafe_allow_html=True)
            if len(ojo):
                c.descargar(ojo[["empresa_id", "ejecutiva", "nivel_2027", "dias_a_vencer"]], "semaforo_vs_modelo.csv",
                            "Exportar esas empresas")

with tab3:
    st.markdown("Ajusta los criterios y mira cómo cambiaría el semáforo **antes** de cambiarlo en la base "
                "(`actho.config_parametro`). Es la propuesta de umbrales para validar con Dirección.")
    s1, s2, s3 = st.columns(3)
    with s1, c.tarjeta():
        c.cabeza("Vencimiento", "Puntos según días para vencer")
        pv30 = st.slider("Vence en 0-30 días o vencida", 0, 5, int(p["pts_vence_30"]))
        pv60 = st.slider("Vence en 31-60 días", 0, 5, int(p["pts_vence_60"]))
        pv90 = st.slider("Vence en 61-90 días", 0, 5, int(p["pts_vence_90"]))
    with s2, c.tarjeta():
        c.cabeza("Participación", "Puntos por no usar beneficios")
        ventana = st.slider("Ventana de participación (días)", 30, 180, int(p["ventana_participacion_dias"]), step=15)
        pp = st.slider("Sin uso de beneficios en la ventana", 0, 5, int(p["pts_sin_participacion"]))
        pp12 = st.slider("… y tampoco en 12 meses (adicional)", 0, 3, int(p["pts_sin_participacion_12m"]))
    with s3, c.tarjeta():
        c.cabeza("Satisfacción y umbrales", "Cuándo el riesgo es alto o medio")
        ps = st.slider("Satisfacción baja", 0, 5, int(p["pts_satisfaccion_baja"]))
        umbral_sat = st.slider("Se considera baja por debajo de", 3.0, 5.0, float(p["umbral_satisfaccion_baja"]), step=0.1)
        rojo = st.slider("Riesgo alto desde (puntos)", 1, 12, int(p["umbral_rojo"]))
        amarillo = st.slider("Riesgo medio desde (puntos)", 1, 12, int(p["umbral_amarillo"]))

    # Participación en la nueva ventana: usos fechados de beneficios (misma regla que la base)
    corte = pd.Timestamp(p["fecha_corte"])
    u = c.uso_beneficios()
    fu = pd.to_datetime(u["fecha"])
    activos_v = set(u[(u["es_fechado"] == 1) & (fu > corte - pd.Timedelta(days=int(ventana))) & (fu <= corte)]["empresa_id"])
    d = vig["dias_a_vencer"]
    pts_v = np.select([(d < 0) | (vig["estado_membresia"] == "Periodo de gracia"), d <= 30, d <= 60, d <= 90],
                      [pv30, pv30, pv60, pv90], 0)
    sin_part = ~vig["empresa_id"].isin(activos_v)
    pts_p = np.where(sin_part, pp + np.where(~vig["usa_beneficio_12m"].fillna(False).astype(bool), pp12, 0), 0)
    pts_s = np.where(vig["detractor_reciente"].fillna(False), int(p["pts_detractor"]),
                     np.where(vig["satisfaccion_promedio"] < umbral_sat, ps, 0))
    total = pts_v + pts_p + pts_s
    nuevo = np.where(total >= rojo, "Rojo", np.where(total >= amarillo, "Amarillo", "Verde"))
    comp = pd.DataFrame({"Riesgo": c.ORDEN_RIESGO,
                         "Actual": [(vig["semaforo"] == s).sum() for s in ["Rojo", "Amarillo", "Verde"]],
                         "Simulado": [(nuevo == s).sum() for s in ["Rojo", "Amarillo", "Verde"]]})
    larga = comp.melt("Riesgo", var_name="Escenario", value_name="Empresas")
    g1, g2 = st.columns([1.4, 1])
    with g1:
        with c.tarjeta():
            fig = px.bar(larga, x="Riesgo", y="Empresas", color="Escenario", barmode="group", text="Empresas",
                         color_discrete_map={"Actual": c.C["lavanda_graf"], "Simulado": c.C["morado"]},
                         title="Semáforo actual frente al simulado")
            fig.update_traces(textposition="outside", cliponaxis=False, textfont=dict(color=c.C["tinta"]))
            fig.update_yaxes(range=[0, max(larga["Empresas"].max(), 1) * 1.18])
            fig.update_xaxes(title="")
            fig.update_yaxes(title="")
            c.grafico(fig, 280, "Empresas vigentes por nivel de riesgo")
    with g2, c.panel():
        cambian = (nuevo != vig["semaforo"].to_numpy()).sum()
        c.pulso([f"<b>{c.fmt(cambian)} empresas cambiarían de nivel</b>",
                 f"<b>{c.fmt((nuevo == 'Rojo').sum())} con riesgo alto</b><br><span>"
                 + (f"Son unas {c.fmt((nuevo == 'Rojo').sum() / max(vig['ejecutiva'].nunique(), 1), 0)} por ejecutiva: "
                    "valida con el equipo si es una carga que se puede contactar en el mes.")
                 + "</span>",
                 "<b>Para aplicarlo</b><br><span>Actualizar los valores en <code>sql/vistas_dashboard.sql</code> "
                 "y volver a cargar (setup o Airflow).</span>"],
                titulo="Resultado", lema="Simulación sobre los vigentes filtrados")
