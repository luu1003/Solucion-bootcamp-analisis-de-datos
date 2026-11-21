# -*- coding: utf-8 -*-
"""02 · Afiliados: directorio para el equipo comercial con filtros, riesgo y vista rápida."""
import pandas as pd
import streamlit as st

import comun as c

c.encabezado("Afiliados", "Directorio de la base con su estado, participación, satisfacción y riesgo")

e = c.filtrar_empresas(c.empresas())

f1, f2, f3, f4 = st.columns([1.3, 1.3, 1.3, 1])
universo = f1.segmented_control("Universo", ["Vigentes", "Todos en CRM", "No afiliados"], default="Vigentes",
                                key="dir_universo") if hasattr(st, "segmented_control") else \
    f1.radio("Universo", ["Vigentes", "Todos en CRM", "No afiliados"], horizontal=True, key="dir_universo")
semaforos = f2.multiselect("Semáforo", ["Rojo", "Amarillo", "Verde"], placeholder="Todos", key="dir_sem")
venc = f3.multiselect("Vencimiento", ["Vencida", "0-30 días", "31-60 días", "61-90 días", "Más de 90 días", "Sin fecha"],
                      placeholder="Todos", key="dir_venc")
buscar = f4.text_input("Buscar código", placeholder="EMP-0123", key="dir_buscar")

if universo == "Vigentes":
    e = e[e["es_vigente"] == 1]
elif universo == "Todos en CRM":
    e = e[e["en_crm"] == 1]
elif universo == "No afiliados":
    e = e[(e["es_vigente"] == 0) & (e["inscripciones_total"] > 0)]
if semaforos:
    e = e[e["semaforo"].isin(semaforos)]
if venc:
    e = e[e["rango_vencimiento"].isin(venc)]
if buscar:
    e = e[e["empresa_id"].str.contains(buscar.strip(), case=False, na=False)]

k = st.columns(4)
c.kpi(k[0], "Empresas en la lista", c.fmt(len(e)))
c.kpi(k[1], "Participan (90 días)", c.fmt(100 * e["participa_en_ventana"].mean() if len(e) else None, 1, " %"))
c.kpi(k[2], "Satisfacción promedio", c.fmt(e["satisfaccion_promedio"].mean(), 2))
c.kpi(k[3], "En rojo", c.fmt((e["semaforo"] == "Rojo").sum()))
st.write("")

orden = e.sort_values(["puntaje_riesgo", "dias_a_vencer"], ascending=[False, True])
vista = orden[["empresa_id", "semaforo", "puntaje_riesgo", "nivel_2027", "tipo_membresia", "estado_membresia",
               "ejecutiva", "sector", "ciudad", "dias_a_vencer", "inscripciones_12m", "personas_distintas",
               "ultima_asistencia", "satisfaccion_promedio", "motivos_riesgo"]].copy()
vista["satisfaccion_promedio"] = vista["satisfaccion_promedio"].map(lambda v: c.fmt(v, 2))

izq, der = st.columns([3, 1.05], gap="medium")
with izq:
    sel = c.tabla_df(
        vista, height=520, on_select="rerun", selection_mode="single-row", key="dir_tabla",
        column_config={
            "empresa_id": st.column_config.TextColumn("Empresa"),
            "semaforo": st.column_config.TextColumn("Semáforo"),
            "puntaje_riesgo": st.column_config.ProgressColumn("Riesgo", min_value=0, max_value=9, format="%d"),
            "nivel_2027": "Nivel", "tipo_membresia": "Tipo", "estado_membresia": "Estado",
            "ejecutiva": "Ejecutiva", "sector": "Sector", "ciudad": "Ciudad",
            "dias_a_vencer": st.column_config.NumberColumn("Días a vencer", format="%d"),
            "inscripciones_12m": st.column_config.NumberColumn("Asist. 12m"),
            "personas_distintas": st.column_config.NumberColumn("Personas"),
            "ultima_asistencia": st.column_config.DateColumn("Última asistencia", format="DD/MM/YYYY"),
            "satisfaccion_promedio": "Satisf.",
            "motivos_riesgo": st.column_config.TextColumn("Motivos", width="large"),
        })
    c.descargar(vista, "afiliados_actho.csv", "Exportar lista (CSV)")

with der:
    filas = sel.selection.rows if sel is not None and hasattr(sel, "selection") else []
    if filas:
        fila = vista.iloc[filas[0]]
        emp = orden[orden["empresa_id"] == fila["empresa_id"]].iloc[0]
        items = [
            f"<b>{emp['empresa_id']}</b> {c.chip_semaforo(emp['semaforo'])}<br>"
            f"<span>{emp['nivel_2027']} · {emp['tipo_membresia']} · {emp['estado_membresia']}</span>",
            f"<b>Ejecutiva:</b> {emp['ejecutiva']}<br><span>Vence: {c.fecha_txt(emp['fecha_expiracion'])}"
            f"{' (' + c.fmt(emp['dias_a_vencer']) + ' días)' if pd.notna(emp['dias_a_vencer']) else ''}</span>",
            f"<b>Participación:</b> {c.fmt(emp['inscripciones_12m'])} asistencias en 12 meses<br>"
            f"<span>{c.fmt(emp['personas_distintas'])} personas · última {c.fecha_txt(emp['ultima_asistencia'])}</span>",
            f"<b>Por qué:</b> <span>{emp['motivos_riesgo'] or 'Sin alertas'}</span>",
        ]
        c.pulso(items, titulo="Vista rápida", lema="Sugerencia de Pulso según su riesgo")
        st.write("")
        if st.button("Abrir ficha 360°", type="primary", **c.ancho(st.button)):
            c.ir("03_ficha_360.py", emp["empresa_id"])
    else:
        c.pulso(["<b>Selecciona una empresa</b><br><span>Marca una fila de la tabla para ver su resumen "
                 "y abrir su ficha 360°.</span>",
                 f"<b>{c.fmt((e['semaforo'] == 'Rojo').sum())} empresas en rojo</b><br><span>Están arriba de la lista: "
                 "la tabla se ordena por riesgo y cercanía del vencimiento.</span>"],
                titulo="Vista rápida", lema="Directorio ordenado por prioridad")
