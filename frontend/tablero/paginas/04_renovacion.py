# -*- coding: utf-8 -*-
"""04 · Renovación y retención: calendario de vencimientos, cartera por ejecutiva y factores de retención."""
import pandas as pd
import plotly.express as px
import streamlit as st

import comun as c

c.encabezado("Renovación y retención", "Quién vence, quién está en riesgo y en qué cartera, a tiempo para actuar")

p = c.parametros()
corte = pd.Timestamp(p["fecha_corte"])
todas = c.filtrar_empresas(c.empresas())
vig = todas[todas["es_vigente"] == 1].copy()

ventana = st.segmented_control("Ventana de vencimiento", [30, 60, 90], default=90, key="ren_ventana",
                               format_func=lambda d: f"Próximos {d} días") if hasattr(st, "segmented_control") else \
    st.radio("Ventana de vencimiento", [30, 60, 90], index=2, horizontal=True, key="ren_ventana")
ventana = ventana or 90
prox = vig[(vig["dias_a_vencer"].between(0, ventana)) | (vig["rango_vencimiento"] == "Vencida")]

renov = c.tabla("v_tasa_renovacion").iloc[0]
k = c.fila(5)
c.kpi(k[0], f"Vencen en {ventana} días", c.fmt(vig["dias_a_vencer"].between(0, ventana).sum()),
      "Membresías vigentes por renovar", oscuro=True,
      chip_=("Morado", f"{c.fmt((vig['rango_vencimiento'] == 'Vencida').sum())} vencidas en gracia"))
c.kpi(k[1], "Prioridad alta", c.fmt((prox["semaforo"] == "Rojo").sum()), "En rojo dentro de la ventana",
      chip_=("Riesgo", "Contactar primero"))
c.kpi(k[2], "Sin participación", c.fmt((~prox["participa_en_ventana"].astype(bool)).sum()),
      "Sin asistencias en 90 días", chip_=("Alerta", "Reactivar antes de renovar"))
c.kpi(k[3], "Tasa de renovación", c.fmt(renov["tasa_renovacion_aprox"], 1, " %"), "Aproximada · últimos 12 meses",
      chip_=("Alerta", "Meta 2027: 90 %"))
c.kpi(k[4], "Retiros", c.fmt(renov["no_renovados"]), "Cancelados o expirados en 12 meses",
      chip_=("Riesgo", "Motivo no registrado"))

izq, der = st.columns([2.3, 1], gap="medium")
with izq:
    with c.tarjeta():
        c.cabeza("Calendario de renovaciones", f"{c.fmt(len(prox))} empresas por contactar · ordenadas por riesgo")
        lista = prox.sort_values(["puntaje_riesgo", "dias_a_vencer"], ascending=[False, True])[
            ["empresa_id", "semaforo", "ejecutiva", "nivel_2027", "fecha_expiracion", "dias_a_vencer",
             "inscripciones_12m", "satisfaccion_promedio", "motivos_riesgo"]].copy()
        lista["satisfaccion_promedio"] = lista["satisfaccion_promedio"].map(lambda v: c.fmt(v, 2))
        sel = c.tabla_df(lista, height=330, on_select="rerun", selection_mode="single-row", key="ren_tabla",
                         column_config={
                             "empresa_id": "Empresa", "semaforo": "Semáforo", "ejecutiva": "Ejecutiva",
                             "nivel_2027": "Nivel",
                             "fecha_expiracion": st.column_config.DateColumn("Vence", format="DD/MM/YYYY"),
                             "dias_a_vencer": st.column_config.NumberColumn("Días", format="%d"),
                             "inscripciones_12m": "Asist. 12m",
                             "satisfaccion_promedio": "Satisf.",
                             "motivos_riesgo": st.column_config.TextColumn("Motivos", width="large")})
        b1, b2 = st.columns([1, 1])
        with b1:
            c.descargar(lista, f"vencimientos_{ventana}_dias.csv", "Exportar para campaña de renovación")
        filas = sel.selection.rows if sel is not None and hasattr(sel, "selection") else []
        if filas and b2.button("Abrir ficha 360°", **c.ancho(st.button)):
            c.ir("03_ficha_360.py", lista.iloc[filas[0]]["empresa_id"])

    with c.tarjeta():
        mes = vig[vig["fecha_expiracion"].notna() & (vig["fecha_expiracion"] <= corte + pd.DateOffset(months=12))].copy()
        mes["mes"] = mes["fecha_expiracion"].clip(lower=corte).dt.to_period("M").dt.to_timestamp()
        calor = mes.pivot_table(index="ejecutiva", columns="mes", values="empresa_id", aggfunc="count", fill_value=0)
        calor.columns = [c.mes_txt(m) for m in calor.columns]
        calor.index = [i.replace(" (cuenta ACTHO)", "") for i in calor.index]
        fig = px.imshow(calor, text_auto=True, aspect="auto", title="Vencimientos por ejecutiva",
                        color_continuous_scale=[c.C["menta"], c.C["lavanda_2"], c.C["morado"]])
        fig.update_xaxes(title="", side="bottom")
        fig.update_yaxes(title="")
        fig.update_coloraxes(showscale=False)
        c.grafico(fig, 300, "Membresías vigentes por mes de expiración")
    with c.tarjeta():
        c.cabeza("Seguimiento por ejecutiva de cuenta", "Cartera vigente, participación, satisfacción y semáforo")
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
        cart["participan"] = (100 * cart["participan"]).round(1)
        c.tabla_df(cart, column_config={
            "ejecutiva": "Ejecutiva", "vigentes": "Vigentes", "vencen_90": "Vencen 90 días", "vencidas": "Vencidas",
            "participan": st.column_config.ProgressColumn("% participa", min_value=0, max_value=100, format="%.0f %%"),
            "satisfaccion": st.column_config.NumberColumn("Satisf.", format="%.2f"),
            "rojo": "Rojo", "amarillo": "Amarillo", "verde": "Verde"})

with der, c.panel("Retención", "Qué se asocia con quedarse"):
    rel = c.tabla("v_relacion_participacion_renovacion")
    with c.tarjeta():
        fig = px.bar(rel, x="nivel_participacion_12m", y="pct_vigentes", text="pct_vigentes",
                     title="Vigencia según participación", color_discrete_sequence=[c.C["morado"]])
        fig.update_yaxes(range=[0, 105], title="")
        fig.update_xaxes(title="")
        c.grafico(fig, 250, "% que sigue vigente · asistencias en 12 meses")
    hist = c.tabla("v_movimientos_mensuales", "historial") if c.existe("historial.v_movimientos_mensuales") else pd.DataFrame()
    items = [
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
        fig = px.bar(ret, x="antiguedad", y="% vigente", text="% vigente", hover_data=["empresas"],
                     title="Retención por antigüedad", color_discrete_sequence=[c.C["naranja"]])
        fig.update_yaxes(range=[0, 105], title="")
        fig.update_xaxes(title="")
        c.grafico(fig, 260, "% que sigue vigente según años de afiliación")
    for i in items:
        partes = i.split("<br>", 1)
        c.actividad(partes[0].replace("<b>", "").replace("</b>", ""), partes[1].replace("<span>", "").replace("</span>", ""), acento=True)
