# -*- coding: utf-8 -*-
"""06 · Pulso: alertas, factores asociados a la retención y simulador de criterios del semáforo."""
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

import comun as c

c.encabezado("Pulso", "Alertas, factores de riesgo y criterios del semáforo para decidir con ACTHO")

p = c.parametros()
todas = c.filtrar_empresas(c.empresas())
vig = todas[todas["es_vigente"] == 1].copy()

tab1, tab2, tab3 = st.tabs(["Alertas", "Factores de retención", "Simulador de criterios"])

with tab1:
    hist = c.tabla("evaluacion_riesgo", "historial") if c.existe("historial.evaluacion_riesgo") else pd.DataFrame()
    fechas = sorted(hist["fecha_corte"].unique()) if len(hist) else []
    izq, der = st.columns([2.2, 1], gap="medium")
    with izq:
        if len(fechas) >= 2:
            ult, ant = fechas[-1], fechas[-2]
            h_ult = hist[hist["fecha_corte"] == ult].set_index("empresa_id")
            h_ant = hist[hist["fecha_corte"] == ant].set_index("empresa_id")["semaforo"]
            nuevos = h_ult[(h_ult["semaforo"] == "Rojo") & (h_ult.index.map(h_ant) != "Rojo")].reset_index()
            st.markdown(f"**{c.fmt(len(nuevos))} empresas pasaron a rojo** entre el {c.fecha_txt(ant)} y el {c.fecha_txt(ult)}")
            evo = hist.groupby(["fecha_corte", "semaforo"]).size().reset_index(name="empresas").sort_values("fecha_corte")
            evo["Fecha de corte"] = evo["fecha_corte"].map(c.fecha_txt)
            fig = px.line(evo, x="Fecha de corte", y="empresas", color="semaforo", markers=True,
                          color_discrete_map=c.SEMAFORO, title="Evolución del semáforo")
            fig.update_xaxes(title="")
            fig.update_yaxes(title="")
            c.grafico(fig, 260)
            tabla_alertas = nuevos[["empresa_id", "ejecutiva", "nivel_2027", "dias_a_vencer", "puntaje", "motivos"]]
        else:
            st.markdown("**Alertas rojas actuales**")
            st.caption("El historial necesita al menos dos recálculos (DAG diario de Airflow) para mostrar cambios. "
                       "Mientras tanto se listan las empresas en rojo hoy.")
            tabla_alertas = vig[vig["semaforo"] == "Rojo"].sort_values("puntaje_riesgo", ascending=False)[
                ["empresa_id", "ejecutiva", "nivel_2027", "dias_a_vencer", "puntaje_riesgo", "motivos_riesgo"]]
        tabla_alertas = tabla_alertas.rename(columns={"puntaje_riesgo": "puntaje", "motivos_riesgo": "motivos"})
        c.tabla_df(tabla_alertas, height=320, column_config={
            "empresa_id": "Empresa", "ejecutiva": "Ejecutiva", "nivel_2027": "Nivel",
            "dias_a_vencer": st.column_config.NumberColumn("Días a vencer", format="%d"),
            "puntaje": st.column_config.ProgressColumn("Riesgo", min_value=0, max_value=9, format="%d"),
            "motivos": st.column_config.TextColumn("Motivos", width="large")})
        c.descargar(tabla_alertas, "alertas_rojas.csv", "Exportar alertas")
    with der:
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
    def barra(col, df, x, titulo):
        t = df.groupby(x, observed=False).agg(empresas=("empresa_id", "count"), vigentes=("es_vigente", "sum")).reset_index()
        t["% vigente"] = (100 * t["vigentes"] / t["empresas"]).round(1)
        fig = px.bar(t, x=x, y="% vigente", text="% vigente", hover_data=["empresas"], title=titulo,
                     color_discrete_sequence=[c.C["morado"]])
        fig.update_yaxes(range=[0, 105], title="")
        fig.update_xaxes(title="")
        with col:
            with st.container(border=True):
                c.grafico(fig, 280)
    crm["Asistencias 12 meses"] = pd.cut(crm["inscripciones_12m"], [-1, 0, 2, 5, 1000], labels=["0", "1-2", "3-5", "6+"])
    crm["Personas distintas"] = pd.cut(crm["personas_distintas"], [-1, 0, 1, 3, 1000], labels=["0", "1", "2-3", "4+"])
    crm["Líneas usadas"] = pd.cut(crm["lineas_distintas"], [-1, 0, 1, 2, 10], labels=["0", "1", "2", "3+"])
    barra(g1, crm, "Asistencias 12 meses", "% vigente por asistencias")
    barra(g2, crm, "Personas distintas", "% vigente por personas que participan")
    barra(g3, crm, "Líneas usadas", "% vigente por líneas usadas")

with tab3:
    st.markdown("Ajusta los criterios y mira cómo cambiaría el semáforo **antes** de cambiarlo en la base "
                "(`actho.config_parametro`). Es la propuesta de umbrales para validar con Dirección.")
    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown("**Vencimiento**")
        pv30 = st.slider("Vence en 0-30 días o vencida", 0, 5, int(p["pts_vence_30"]))
        pv60 = st.slider("Vence en 31-60 días", 0, 5, int(p["pts_vence_60"]))
        pv90 = st.slider("Vence en 61-90 días", 0, 5, int(p["pts_vence_90"]))
    with s2:
        st.markdown("**Participación**")
        ventana = st.slider("Ventana de participación (días)", 30, 180, int(p["ventana_participacion_dias"]), step=15)
        pp = st.slider("Sin asistencias en la ventana", 0, 5, int(p["pts_sin_participacion"]))
        pp12 = st.slider("… y tampoco en 12 meses (adicional)", 0, 3, int(p["pts_sin_participacion_12m"]))
    with s3:
        st.markdown("**Satisfacción y umbrales**")
        ps = st.slider("Satisfacción baja", 0, 5, int(p["pts_satisfaccion_baja"]))
        umbral_sat = st.slider("Se considera baja por debajo de", 3.0, 5.0, float(p["umbral_satisfaccion_baja"]), step=0.1)
        rojo = st.slider("Rojo desde (puntos)", 1, 12, int(p["umbral_rojo"]))
        amarillo = st.slider("Amarillo desde (puntos)", 1, 12, int(p["umbral_amarillo"]))

    # Participación en la nueva ventana, desde el detalle de asistencia
    corte = pd.Timestamp(p["fecha_corte"])
    a = c.asistencia()
    activos_v = set(a[(a["fecha_evento"] > corte - pd.Timedelta(days=int(ventana))) & (a["fecha_evento"] <= corte)]["empresa_id"])
    d = vig["dias_a_vencer"]
    pts_v = np.select([(d < 0) | (vig["estado_membresia"] == "Periodo de gracia"), d <= 30, d <= 60, d <= 90],
                      [pv30, pv30, pv60, pv90], 0)
    sin_part = ~vig["empresa_id"].isin(activos_v)
    pts_p = np.where(sin_part, pp + np.where(vig["inscripciones_12m"] == 0, pp12, 0), 0)
    pts_s = np.where(vig["detractor_reciente"].fillna(False), int(p["pts_detractor"]),
                     np.where(vig["satisfaccion_promedio"] < umbral_sat, ps, 0))
    total = pts_v + pts_p + pts_s
    nuevo = np.where(total >= rojo, "Rojo", np.where(total >= amarillo, "Amarillo", "Verde"))
    comp = pd.DataFrame({"Semáforo": ["Rojo", "Amarillo", "Verde"],
                         "Actual": [(vig["semaforo"] == s).sum() for s in ["Rojo", "Amarillo", "Verde"]],
                         "Simulado": [(nuevo == s).sum() for s in ["Rojo", "Amarillo", "Verde"]]})
    larga = comp.melt("Semáforo", var_name="Escenario", value_name="Empresas")
    g1, g2 = st.columns([1.4, 1])
    with g1:
        with st.container(border=True):
            fig = px.bar(larga, x="Semáforo", y="Empresas", color="Escenario", barmode="group", text="Empresas",
                         color_discrete_map={"Actual": c.C["lavanda_2"], "Simulado": c.C["naranja"]},
                         title="Semáforo actual frente al simulado")
            fig.update_xaxes(title="")
            fig.update_yaxes(title="")
            c.grafico(fig, 300)
    with g2:
        cambian = (nuevo != vig["semaforo"].to_numpy()).sum()
        c.pulso([f"<b>{c.fmt(cambian)} empresas cambiarían de color</b>",
                 f"<b>{c.fmt((nuevo == 'Rojo').sum())} en rojo</b><br><span>"
                 + (f"Son unas {c.fmt((nuevo == 'Rojo').sum() / max(vig['ejecutiva'].nunique(), 1), 0)} por ejecutiva: "
                    "valida con el equipo si es una carga que se puede contactar en el mes.")
                 + "</span>",
                 "<b>Para aplicarlo</b><br><span>Actualizar los valores en <code>sql/vistas_dashboard.sql</code> "
                 "y volver a cargar (setup o Airflow).</span>"],
                titulo="Resultado", lema="Simulación sobre los vigentes filtrados")
