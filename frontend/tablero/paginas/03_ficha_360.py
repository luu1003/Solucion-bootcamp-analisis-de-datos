# -*- coding: utf-8 -*-
"""03 · Ficha 360° del afiliado: salud, membresía, participación, satisfacción y acciones sugeridas."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import comun as c

todas = c.empresas()
crm = todas[todas["en_crm"] == 1].sort_values(["es_vigente", "puntaje_riesgo"], ascending=[False, False])
ids = crm["empresa_id"].tolist() + sorted(todas[todas["en_crm"] == 0]["empresa_id"].tolist())
inicial = st.session_state.get("empresa_sel") or ids[0]

c.encabezado("Ficha 360° del afiliado", "Todo lo que sabemos de una empresa en una sola vista")
emp_id = st.selectbox("Empresa", ids, index=ids.index(inicial) if inicial in ids else 0, key="ficha_empresa",
                      help="Por defecto aparecen primero las vigentes con mayor riesgo")
st.session_state["empresa_sel"] = emp_id
emp = todas[todas["empresa_id"] == emp_id].iloc[0]
p = c.parametros()

asis = c.asistencia()
asis_e = asis[asis["empresa_id"] == emp_id]
enc = c.encuestas()
enc_e = enc[enc["empresa_id"] == emp_id]
personas = c.consulta("SELECT persona_id, nivel_cargo, autoriza_datos, inscripciones_2026, es_contacto_principal "
                      "FROM actho.dim_persona WHERE empresa_id = %s ORDER BY inscripciones_2026 DESC", (emp_id,))

vigente = emp["es_vigente"] == 1
salud = round(100 - 100 * (emp["puntaje_riesgo"] or 0) / 9) if vigente else None

# Encabezado de la empresa
st.markdown(
    f'<div class="tarjeta"><span style="font-size:1.35rem;font-weight:700">{emp_id}</span> &nbsp; '
    f'{c.chip_semaforo(emp["semaforo"])} {c.chip(emp["estado_membresia"], "morado")} {c.chip(emp["nivel_2027"])}'
    f'<div class="subtitulo" style="margin-top:.4rem">{emp["tipo_membresia"]} · {emp["sector"]} · {emp["ciudad"]} · '
    f'Ejecutiva: <b>{emp["ejecutiva"]}</b> · Afiliada desde {c.fecha_txt(emp["fecha_afiliacion"])}</div></div>',
    unsafe_allow_html=True)
st.write("")

k = st.columns(5)
c.kpi(k[0], "Índice de salud", c.fmt(salud) if salud is not None else "—", "100 = sin alertas", oscuro=True)
if pd.notna(emp["dias_a_vencer"]):
    nota_vence = (f"vencida hace {c.fmt(-emp['dias_a_vencer'])} días" if emp["dias_a_vencer"] < 0
                  else f"en {c.fmt(emp['dias_a_vencer'])} días")
else:
    nota_vence = emp["rango_vencimiento"]
c.kpi(k[1], "Vence", c.fecha_txt(emp["fecha_expiracion"]), nota_vence)
c.kpi(k[2], "Asistencias 12 meses", c.fmt(emp["inscripciones_12m"]),
      f"{c.fmt(emp['inscripciones_ventana'])} en los últimos {p['ventana_participacion_dias']} días")
c.kpi(k[3], "Personas que participan", c.fmt(emp["personas_distintas"]), f"{c.fmt(emp['lineas_distintas'])} líneas usadas")
prom_general = enc["satisfaccion_general"].fillna(enc["satisfaccion_prom"]).mean()
c.kpi(k[4], "Satisfacción", c.fmt(emp["satisfaccion_promedio"], 2), f"Promedio general {c.fmt(prom_general, 2)}")
st.write("")

izq, der = st.columns([2.2, 1], gap="medium")
with izq:
    g1, g2 = st.columns([1, 1.25])
    with g1:
        with st.container(border=True):
            comp = pd.DataFrame({"Componente": ["Vencimiento", "Participación", "Satisfacción"],
                                 "Puntos": [emp["pts_vencimiento"], emp["pts_participacion"], emp["pts_satisfaccion"]],
                                 "Máximo": [p["pts_vencida"], p["pts_sin_participacion"] + p["pts_sin_participacion_12m"],
                                            p["pts_detractor"]]})
            fig = go.Figure()
            fig.add_bar(y=comp["Componente"], x=comp["Máximo"], orientation="h", marker_color=c.C["lavanda"],
                        name="Máximo", hoverinfo="skip")
            fig.add_bar(y=comp["Componente"], x=comp["Puntos"], orientation="h", marker_color=c.C["naranja"],
                        name="Puntos", text=comp["Puntos"], textposition="inside")
            fig.update_layout(barmode="overlay", title=f"Riesgo: {c.fmt(emp['puntaje_riesgo'])} puntos",
                              showlegend=False)
            c.grafico(fig, 230)
    with g2:
        with st.container(border=True):
            if len(asis_e):
                linea = asis_e.groupby(["anio_mes", "linea_2027"]).size().reset_index(name="inscripciones").sort_values("anio_mes")
                linea["Mes"] = linea["anio_mes"].map(c.anio_mes_txt)
                fig = px.bar(linea, x="Mes", y="inscripciones", color="linea_2027", title="Participación por mes y línea")
                fig.update_xaxes(title="")
                fig.update_yaxes(title="", dtick=1)
                c.grafico(fig, 230)
            else:
                st.markdown("**Participación por mes y línea**")
                st.info("Esta empresa no registra asistencias a eventos de 2026.")

    with st.container(border=True):
        st.markdown("**Historial de participación**")
        if len(asis_e):
            hist = asis_e.groupby(["fecha_evento", "evento", "linea_2027", "modalidad"]) \
                         .agg(personas=("persona_id", "nunique")).reset_index().sort_values("fecha_evento", ascending=False)
            c.tabla_df(hist, height=230, column_config={
                "fecha_evento": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"), "evento": "Evento",
                "linea_2027": "Línea", "modalidad": "Modalidad", "personas": "Personas"})
        else:
            st.caption("Sin asistencias registradas.")

    p1, p2 = st.columns(2)
    with p1:
        with st.container(border=True):
            st.markdown("**Personas de la empresa**")
            if len(personas):
                pc = personas.groupby("nivel_cargo").size().reset_index(name="personas").sort_values("personas")
                fig = px.bar(pc, x="personas", y="nivel_cargo", orientation="h", color_discrete_sequence=[c.C["morado"]])
                fig.update_yaxes(title="")
                fig.update_xaxes(title="", dtick=1)
                c.grafico(fig, 200)
                st.caption(f"{c.fmt((personas['autoriza_datos'] == 'Sí').sum())} de {c.fmt(len(personas))} autorizan "
                           "el uso de sus datos para comunicaciones.")
            else:
                st.caption("Sin personas registradas.")
    with p2:
        with st.container(border=True):
            st.markdown("**Encuestas de la empresa**")
            if len(enc_e):
                c.tabla_df(enc_e[["fecha_respuesta", "evento", "satisfaccion_prom", "nps_puntaje", "tipo_cruce"]],
                           height=230, column_config={
                               "fecha_respuesta": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                               "evento": "Evento", "satisfaccion_prom": st.column_config.NumberColumn("Satisf.", format="%.2f"),
                               "nps_puntaje": "NPS", "tipo_cruce": "Cruce"})
            else:
                st.caption("Esta empresa no ha respondido encuestas.")

with der:
    acciones = []
    if vigente and emp["pts_vencimiento"] > 0:
        acciones.append(f"<b>Contactar para la renovación</b><br><span>{emp['motivos_riesgo'].split(' · ')[0]}. "
                        "Llevar el resumen del valor recibido en el año.</span>")
    if vigente and not emp["participa_en_ventana"]:
        lineas_todas = {"Anticipar", "Foro", "Pares", "Evento grande"}
        usadas = set(asis_e["linea_2027"].dropna())
        temas = enc_e["temas_solicitados"].dropna()
        sugerida = sorted(lineas_todas - usadas)
        acciones.append("<b>Invitar a la próxima experiencia</b><br><span>"
                        + (f"No ha usado: {', '.join(sugerida)}. " if sugerida else "")
                        + (f"Pidió temas como «{temas.iloc[0][:60]}»." if len(temas) else
                           "Proponer la línea con más asistencia de su sector.") + "</span>")
    if vigente and emp["personas_distintas"] == 1:
        acciones.append("<b>Abrir la relación a más personas</b><br><span>Solo participa una persona: invitar a "
                        "otros niveles del área de talento humano.</span>")
    if emp["detractor_reciente"]:
        acciones.append("<b>Seguimiento personal</b><br><span>Calificó bajo recientemente: llamar antes de cualquier "
                        "envío masivo.</span>")
    if emp["tiene_promotor"]:
        acciones.append("<b>Invitar a tomar la palabra</b><br><span>Tiene promotores: testimonio, columna o "
                        "podcast Actho Seguido.</span>")
    if not vigente and emp["inscripciones_total"] > 0:
        acciones.append(f"<b>Oportunidad de afiliación</b><br><span>Participa sin membresía vigente "
                        f"({c.fmt(emp['inscripciones_total'])} asistencias). Enviar propuesta de afiliación.</span>")
    if not acciones:
        acciones.append("<b>Sin alertas</b><br><span>Mantener el contacto regular y compartir la agenda.</span>")
    c.pulso(acciones, titulo="Acciones sugeridas", lema="Reglas de Pulso a partir de su ficha")
    if isinstance(emp.get("inconsistencia"), str) and emp["inconsistencia"]:
        st.warning(f"Dato por revisar en el CRM: {emp['inconsistencia']}")
