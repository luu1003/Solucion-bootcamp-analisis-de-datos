# -*- coding: utf-8 -*-
"""08 · Datos y calidad: cargas, estado de las fuentes, diagnóstico y recomendaciones de captura."""
import pandas as pd
import plotly.express as px
import streamlit as st

import comun as c

c.encabezado("Datos y calidad", "De dónde vienen los datos, qué se corrigió y qué conviene cambiar en la captura")

calidad = c.tabla("reporte_calidad")
dic = c.tabla("diccionario_datos")
enc = c.encuestas()
emp = c.empresas()

k = st.columns(4)
c.kpi(k[0], "Hallazgos de calidad", c.fmt(len(calidad)),
      f"{c.fmt((calidad['accion'] == 'Revisar con ACTHO').sum())} para revisar con ACTHO", oscuro=True)
c.kpi(k[1], "Encuestas con empresa exacta", c.fmt(100 * (enc["tipo_cruce"] == "Exacto").mean(), 1, " %"),
      f"{c.fmt((enc['tipo_cruce'] == 'Sin empresa').sum())} sin empresa identificable")
c.kpi(k[2], "Encuestas con evento asignado", c.fmt(100 * enc["evento_id"].notna().mean(), 1, " %"),
      "El formulario no pide el evento")
c.kpi(k[3], "Empresas fuera del CRM", c.fmt((emp["en_crm"] == 0).sum()), "Participan sin registro en Zoho")
st.write("")

izq, der = st.columns([2.2, 1], gap="medium")
with izq:
    with st.container(border=True):
        st.markdown("**Cargas recientes**")
        ej = c.consulta("SELECT id, inicio, fin, estado, fecha_corte, array_to_string(fuentes_cambiadas, ', ') "
                        "AS fuentes, detalle->>'tarea' AS tarea_con_error FROM ingesta.ejecucion "
                        "ORDER BY id DESC LIMIT 8") if c.existe("ingesta.ejecucion") else pd.DataFrame()
        if ej.empty:
            st.info("Aún no hay cargas registradas por Airflow. Los datos se cargaron con `setup.py`; "
                    "al activar el DAG `actho_ingesta_datos` aquí aparecerá cada ejecución y cada archivo procesado.")
        else:
            c.tabla_df(ej, column_config={"id": "N°", "inicio": st.column_config.DatetimeColumn("Inicio", format="DD/MM/YY HH:mm"),
                                          "fin": st.column_config.DatetimeColumn("Fin", format="DD/MM/YY HH:mm"),
                                          "estado": "Estado", "fecha_corte": st.column_config.DateColumn("Corte", format="DD/MM/YYYY"),
                                          "fuentes": "Fuentes que cambiaron", "tarea_con_error": "Tarea con error"})
            lotes = c.consulta("SELECT fuente, archivo, left(hash_sha256, 12) AS huella, cargado_en "
                               "FROM ingesta.lote_carga ORDER BY cargado_en DESC")
            st.markdown("**Último archivo procesado de cada fuente**")
            c.tabla_df(lotes, column_config={"fuente": "Fuente", "archivo": "Archivo", "huella": "Huella SHA-256",
                                             "cargado_en": st.column_config.DatetimeColumn("Cargado", format="DD/MM/YY HH:mm")})
    with st.container(border=True):
        st.markdown("**Diagnóstico de calidad** (generado por la limpieza)")
        acc = st.multiselect("Acción", sorted(calidad["accion"].unique()), placeholder="Todas", key="cal_accion")
        vista = calidad[calidad["accion"].isin(acc)] if acc else calidad
        c.tabla_df(vista[["tabla", "campo", "problema", "regla_aplicada", "filas_afectadas", "accion"]], height=330,
                   column_config={"problema": st.column_config.TextColumn("Problema", width="large"),
                                  "regla_aplicada": st.column_config.TextColumn("Regla", width="medium")})
        c.descargar(calidad, "reporte_calidad.csv", "Descargar diagnóstico")
    with st.container(border=True):
        crm = c.tabla("dim_empresa")
        crm = crm[crm["en_crm"] == 1]
        campos = {"tipo_empresa": "Tipo de empresa", "tamano_empresa": "Tamaño", "rango_empleados": "Empleados",
                  "subsector": "Subsector", "sector": "Sector", "ciudad": "Ciudad", "region": "Región",
                  "categoria_membresia": "Categoría", "tipo_membresia": "Tipo de membresía",
                  "fecha_afiliacion": "Fecha de afiliación", "fecha_expiracion": "Fecha de expiración"}
        comp = pd.DataFrame({"Campo": list(campos.values()),
                             "% sin dato": [round(100 * (crm[k].isna() | (crm[k].astype(str) == "Sin dato")).mean(), 1)
                                            for k in campos]}).sort_values("% sin dato")
        fig = px.bar(comp, x="% sin dato", y="Campo", orientation="h", text="% sin dato",
                     title="Completitud del CRM: % de empresas sin el dato", color_discrete_sequence=[c.C["morado"]])
        fig.update_yaxes(title="")
        fig.update_xaxes(title="", range=[0, 100])
        c.grafico(fig, 360)
        st.caption("Las fechas de expiración vacías son normales en membresías canceladas.")
    with st.expander("Diccionario de datos"):
        c.tabla_df(dic, height=400)

with der:
    with st.container(border=True):
        cr = enc["tipo_cruce"].value_counts().reset_index()
        cr.columns = ["Cruce", "Respuestas"]
        fig = px.pie(cr, names="Cruce", values="Respuestas", hole=0.6, title="Cómo se identificó la empresa en encuestas",
                     color_discrete_sequence=[c.C["morado"], c.C["cian"], c.C["naranja"], c.C["lavanda_2"]])
        c.grafico(fig, 280)
    c.pulso([
        "<b>Pedir NIT y código de evento en cada encuesta</b><br><span>Hoy 142 respuestas no tienen empresa y "
        "el evento se infiere por la fecha.</span>",
        "<b>Guardar el motivo del retiro en Zoho</b><br><span>Con una lista cerrada, para medir por qué no renuevan.</span>",
        "<b>No sobrescribir la expiración al renovar</b><br><span>Registrar cada renovación como un movimiento; "
        "mientras tanto, la foto mensual de Airflow guarda el historial.</span>",
        "<b>Un solo formato de asistencia</b><br><span>Mismas columnas en todas las hojas y NIT sin dígito de "
        "verificación.</span>",
        "<b>Listas cerradas en el CRM</b><br><span>Ciudad, sector y categoría sin texto libre, para evitar "
        "variantes y tildes dañadas.</span>",
    ], titulo="Recomendaciones de captura", lema="Para que el tablero se mantenga al día")
