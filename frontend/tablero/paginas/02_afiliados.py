# -*- coding: utf-8 -*-
"""02 · Afiliados: directorio para el equipo comercial con filtros, riesgo y vista rápida."""
import pandas as pd
import streamlit as st

import comun as c
import ia

c.encabezado("Afiliados", "Directorio de la base con su estado, participación, satisfacción y riesgo")

e = ia.con_ia(c.filtrar_empresas(c.empresas()))
for col in ("p_renovar", "banda", "perfil", "propension", "a_favor", "en_contra"):
    if col not in e:
        e[col] = None

f1, f2, f3, f5, f4 = st.columns([1.9, 1.1, 1.1, 1.3, 0.9])
universo = f1.segmented_control("Universo", ["Vigentes", "Todos en CRM", "No afiliados"], default="Vigentes",
                                key="dir_universo") if hasattr(st, "segmented_control") else \
    f1.radio("Universo", ["Vigentes", "Todos en CRM", "No afiliados"], horizontal=True, key="dir_universo")
semaforos = f2.multiselect("Riesgo", ["Rojo", "Amarillo", "Verde"], placeholder="Todos", key="dir_sem",
                           format_func=c.riesgo_txt)
venc = f3.multiselect("Vencimiento", ["Vencida", "0-30 días", "31-60 días", "61-90 días", "Más de 90 días", "Sin fecha"],
                      placeholder="Todos", key="dir_venc")
perfiles_sel = f5.multiselect("Perfil ✦ IA", sorted(e["perfil"].dropna().unique()), placeholder="Todos", key="dir_perfil",
                              help=ia.desc("perfiles"))
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
if perfiles_sel:
    e = e[e["perfil"].isin(perfiles_sel)]
if buscar:
    e = e[e["empresa_id"].str.contains(buscar.strip(), case=False, na=False)]

k = c.fila(4)
c.kpi(k[0], "Empresas en la lista", c.fmt(len(e)), f"Universo: {universo.lower() if universo else 'vigentes'}", oscuro=True,
      chip_=("Morado", f"{c.fmt(e['ejecutiva'].nunique())} ejecutivas"))
c.kpi(k[1], "Uso de beneficios", c.fmt(100 * e["participa_en_ventana"].mean() if len(e) else None, 1, " %"),
      "Usaron algún beneficio en los últimos 90 días", chip_=("Alerta", f"{c.fmt((~e['participa_en_ventana'].astype(bool)).sum())} sin uso"),
      ayuda_=c.ayuda("Uso de beneficios"))
c.kpi(k[2], "Satisfacción promedio", c.fmt(e["satisfaccion_promedio"].mean(), 2), "Escala 1 a 5 · últimos 12 meses",
      chip_=("OK", f"{c.fmt(e['satisfaccion_promedio'].notna().sum())} con encuestas"))
c.kpi(k[3], "Riesgo alto de no renovar", c.fmt((e["semaforo"] == "Rojo").sum()), "Empresas con riesgo alto",
      chip_=("Riesgo", f"{c.fmt((e['semaforo'] == 'Amarillo').sum())} con riesgo medio"))

no_af = universo == "No afiliados"
orden = (e.sort_values("propension", ascending=False) if no_af
         else e.sort_values(["puntaje_riesgo", "dias_a_vencer"], ascending=[False, True]))
col_ia = ["propension"] if no_af else ["p_renovar", "perfil"]
vista = orden[["empresa_id", "semaforo", "puntaje_riesgo"] + col_ia + ["nivel_2027", "tipo_membresia", "estado_membresia",
               "ejecutiva", "sector", "ciudad", "dias_a_vencer", "inscripciones_12m", "personas_distintas",
               "ultima_asistencia", "pct_aprovechamiento", "satisfaccion_promedio", "motivos_riesgo"]].copy()
vista["satisfaccion_promedio"] = vista["satisfaccion_promedio"].map(lambda v: c.fmt(v, 2))
vista["semaforo"] = vista["semaforo"].map(c.SEM_TXT).fillna("Sin evaluar")

izq, der = st.columns([3, 1.05], gap="medium")
with izq, c.tarjeta():
    c.cabeza("Directorio de afiliados", ("Ordenado por parecido con las afiliadas" if no_af else
                                         "Ordenado por riesgo y cercanía del vencimiento") + " · marca una fila para ver su resumen")
    sel = c.tabla_df(
        vista, height=520, on_select="rerun", selection_mode="single-row", key="dir_tabla",
        column_config={
            "empresa_id": st.column_config.TextColumn("Empresa"),
            "semaforo": st.column_config.TextColumn("Riesgo"),
            "puntaje_riesgo": st.column_config.ProgressColumn("Puntaje", min_value=0, max_value=9, format="%d", width="small"),
            "p_renovar": st.column_config.ProgressColumn("✦ Prob. renovar", min_value=0, max_value=1, format="percent",
                                                         help=ia.desc("renovacion")),
            "perfil": st.column_config.TextColumn("✦ Perfil", help=ia.desc("perfiles")),
            "propension": st.column_config.ProgressColumn("✦ Parecido con afiliadas", min_value=0, max_value=100,
                                                          format="%d", help=ia.desc("propension")),
            "nivel_2027": st.column_config.TextColumn("Nivel", width="small"), "tipo_membresia": "Tipo", "estado_membresia": "Estado",
            "ejecutiva": "Ejecutiva", "sector": "Sector", "ciudad": "Ciudad",
            "dias_a_vencer": st.column_config.NumberColumn("Días a vencer", format="%d"),
            "inscripciones_12m": st.column_config.NumberColumn("Asist. 12m"),
            "personas_distintas": st.column_config.NumberColumn("Personas"),
            "ultima_asistencia": st.column_config.DateColumn("Última asistencia", format="DD/MM/YYYY"),
            "satisfaccion_promedio": "Satisf.",
            "pct_aprovechamiento": st.column_config.ProgressColumn("Aprovecha nivel", min_value=0, max_value=100, format="%.0f %%",
                                                                   help="Beneficios incluidos en su nivel que usó en 12 meses"),
            "motivos_riesgo": st.column_config.TextColumn("Motivos", width="large"),
        })
    ia.nota("propension" if no_af else "renovacion")
    c.descargar(vista, "afiliados_actho.csv", "Exportar lista (CSV)")

with der, c.panel():
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
        if pd.notna(emp.get("p_renovar")):
            items.append(f"<b>✦ IA: {100 * emp['p_renovar']:.0f} % de probabilidad de renovar</b>{ia.info('renovacion')}<br>"
                         f"<span>{emp['perfil'] or ''}{' · a favor: ' + emp['a_favor'] if emp['a_favor'] else ''}</span>")
        elif pd.notna(emp.get("propension")):
            items.append(f"<b>✦ IA: parecido con afiliadas {emp['propension']:.0f}/100</b>{ia.info('propension')}<br>"
                         "<span>Candidata a propuesta de afiliación</span>")
        c.pulso(items, titulo="Vista rápida", lema="Sugerencia de Pulso según su riesgo")
        if c.pagina_activa("03_ficha_360.py") and st.button("Abrir ficha 360°", type="primary", **c.ancho(st.button)):
            c.ir("03_ficha_360.py", emp["empresa_id"])
    else:
        c.pulso(["<b>Selecciona una empresa</b><br><span>Marca una fila de la tabla para ver su resumen "
                 "y su sugerencia de acción.</span>",
                 f"<b>{c.fmt((e['semaforo'] == 'Rojo').sum())} empresas con riesgo alto</b><br><span>Están arriba de la lista: "
                 "la tabla se ordena por riesgo y cercanía del vencimiento.</span>"],
                titulo="Vista rápida", lema="Directorio ordenado por prioridad")
