# -*- coding: utf-8 -*-
"""01 · Panel general: metas 2027, salud de la base, vencimientos, participación y satisfacción."""
import pandas as pd
import plotly.express as px
import streamlit as st

import comun as c

c.encabezado("Dashboard", "Cómo va la asociación: afiliados, retención, participación y satisfacción")

p = c.parametros()
corte = pd.Timestamp(p["fecha_corte"])
e = c.filtrar_empresas(c.empresas())
vig = e[e["es_vigente"] == 1]
a = c.filtrar_detalle(c.asistencia(), "fecha_evento")
r = c.filtrar_detalle(c.encuestas(), "fecha_respuesta")

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
    c.meta(m1, "Tasa de renovación", renov["tasa_renovacion_aprox"], c.METAS_2027["renovacion"],
           f"Aproximada: {c.fmt(renov['renovados'])} renovados y {c.fmt(renov['no_renovados'])} no renovados en 12 meses",
           chip_=("Alerta", f"{c.fmt(c.METAS_2027['renovacion'] - renov['tasa_renovacion_aprox'], 1)} pts por debajo"))
    c.meta(m2, "NPS de eventos", nps, c.METAS_2027["nps"],
           f"{c.fmt(nps_n)} respuestas con NPS · el NPS de ACTHO (encuesta de 90 días) aún no tiene respuestas", sufijo="",
           chip_=("OK" if (nps or 0) >= c.METAS_2027["nps"] else "Alerta", "Sobre la meta" if (nps or 0) >= c.METAS_2027["nps"] else "Bajo la meta"))
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
    c.kpi(k[4], "Riesgo de no renovar", c.fmt(rojos), "Empresas en rojo en el semáforo",
          chip_=("Alerta", f"{c.fmt((vig['semaforo'] == 'Amarillo').sum())} en amarillo"))

    g1, g2 = st.columns([1.35, 1])
    with g1:
        with c.tarjeta():
            prox = vig[vig["fecha_expiracion"].notna() & (vig["fecha_expiracion"] <= corte + pd.DateOffset(months=12))].copy()
            prox["mes"] = prox["fecha_expiracion"].dt.to_period("M").dt.to_timestamp()
            prox.loc[prox["fecha_expiracion"] < corte, "mes"] = corte.to_period("M").to_timestamp()
            serie = prox.groupby(["mes", "semaforo"]).size().reset_index(name="empresas").sort_values("mes")
            serie["Mes"] = serie["mes"].map(c.mes_txt)
            fig = px.bar(serie, x="Mes", y="empresas", color="semaforo", color_discrete_map=c.SEMAFORO,
                         title="Vencimientos de los próximos 12 meses",
                         category_orders={"semaforo": ["Rojo", "Amarillo", "Verde"]})
            fig.update_xaxes(title="", categoryorder="array", categoryarray=list(dict.fromkeys(serie["Mes"])))
            fig.update_yaxes(title="Empresas")
            c.grafico(fig, 300, "Membresías vigentes por mes de expiración y semáforo")
    with g2:
        with c.tarjeta():
            sem = vig["semaforo"].value_counts().reindex(["Rojo", "Amarillo", "Verde"]).fillna(0).reset_index()
            sem.columns = ["semaforo", "empresas"]
            fig = px.pie(sem, names="semaforo", values="empresas", hole=0.62, color="semaforo",
                         color_discrete_map=c.SEMAFORO, title="Semáforo de riesgo")
            fig.update_traces(textinfo="value+percent", sort=False)
            fig.add_annotation(text=f"<b>{c.fmt(len(vig))}</b><br>vigentes", showarrow=False, font_size=14)
            c.grafico(fig, 300, "Vencimiento + participación + satisfacción")

    with c.tarjeta():
        c.cabeza("Renovaciones prioritarias", "Próximos 90 días · ordenadas por riesgo")
        top = vig[vig["dias_a_vencer"].between(-365, 90)].sort_values(["puntaje_riesgo", "dias_a_vencer"], ascending=[False, True]).head(6)
        filas = [{"emp": r.empresa_id, "det": f"{r.nivel_2027} · {r.sector}", "ej": r.ejecutiva,
                  "vence": c.fecha_txt(r.fecha_expiracion),
                  "dias": (f"hace {c.fmt(-r.dias_a_vencer)} días" if r.dias_a_vencer < 0 else f"en {c.fmt(r.dias_a_vencer)} días"),
                  "asis": c.fmt(r.inscripciones_12m), "sem": c.chip_semaforo(r.semaforo),
                  "mot": r.motivos_riesgo or ""} for r in top.itertuples()]
        c.tabla_html(filas, [("Afiliado", ("emp", "det"), "texto"), ("Ejecutiva", "ej", "texto"),
                             ("Vence", ("vence", "dias"), "texto"), ("Asist. 12 m", "asis", "num"),
                             ("Riesgo", "sem", "html"), ("Por qué", "mot", "texto")])

    g3, g4 = st.columns(2)
    with g3:
        with c.tarjeta():
            pm = a.groupby(["anio_mes", "condicion_empresa"]).size().reset_index(name="inscripciones").sort_values("anio_mes")
            pm["Mes"] = pm["anio_mes"].map(c.anio_mes_txt)
            fig = px.bar(pm, x="Mes", y="inscripciones", color="condicion_empresa",
                         color_discrete_map={"Afiliada": c.C["morado"], "No afiliada": c.C["cian"]},
                         title="Participación en experiencias")
            fig.update_xaxes(title="")
            fig.update_yaxes(title="")
            c.grafico(fig, 280, "Inscripciones por mes · afiliadas y no afiliadas")
    with g4:
        with c.tarjeta():
            niv = vig.groupby("nivel_2027").agg(vigentes=("empresa_id", "count"),
                                                participan=("participa_en_ventana", "sum")).reset_index()
            niv["% que participa"] = (100 * niv["participan"] / niv["vigentes"]).round(1)
            fig = px.bar(niv.sort_values("vigentes"), x="vigentes", y="nivel_2027", orientation="h",
                         text="vigentes", title="Afiliados por nivel 2027", hover_data=["% que participa"],
                         color_discrete_sequence=[c.C["morado"]])
            fig.update_yaxes(title="")
            fig.update_xaxes(title="")
            c.grafico(fig, 280, "Conectar · Crecer · Liderar")

    with c.tarjeta():
        sm = r.assign(sat=r["satisfaccion_general"].fillna(r["satisfaccion_prom"])).groupby("anio_mes") \
              .agg(satisfaccion=("sat", "mean"), respuestas=("encuesta_id", "count")).reset_index().sort_values("anio_mes")
        sm["Mes"] = sm["anio_mes"].map(c.anio_mes_txt)
        fig = px.line(sm, x="Mes", y="satisfaccion", markers=True, hover_data=["respuestas"],
                      title="Satisfacción mensual", color_discrete_sequence=[c.C["naranja"]])
        fig.update_traces(line_width=3, marker_size=8)
        fig.update_yaxes(range=[1, 5.2], title="")
        fig.update_xaxes(title="")
        c.grafico(fig, 240, "Promedio de las encuestas de eventos · escala 1 a 5")

with lateral, c.panel():
    dic31 = vig[vig["fecha_expiracion"] == pd.Timestamp(corte.year, 12, 31)]
    rel = c.tabla("v_relacion_participacion_renovacion")
    alto = rel[rel["nivel_participacion_12m"] == "6 o más"]["pct_vigentes"]
    cero = rel[rel["nivel_participacion_12m"] == "0 asistencias"]["pct_vigentes"]
    cart = vig[vig["semaforo"] == "Rojo"].groupby("ejecutiva").size().sort_values(ascending=False)
    items = []
    if len(dic31):
        items.append(f"<b>{c.fmt(len(dic31))} membresías vencen el 31 de diciembre</b><br>"
                     f"<span>{c.fmt((dic31['semaforo'] == 'Rojo').sum())} de ellas ya están en rojo. "
                     f"Es la ola de renovación del año.</span>")
    if part is not None:
        items.append(f"<b>{c.fmt(100 - part, 0)} % de los vigentes no asistió a nada en 90 días</b><br>"
                     f"<span>Pagan pero no usan los beneficios: son el primer segmento a reactivar.</span>")
    if len(alto) and len(cero):
        items.append(f"<b>Participar se asocia con quedarse</b><br><span>Con 6 o más asistencias sigue vigente el "
                     f"{c.fmt(alto.iloc[0], 0)} %; sin asistencias, el {c.fmt(cero.iloc[0], 0)} %.</span>")
    if len(cart):
        items.append(f"<b>{cart.index[0]} concentra más alertas rojas</b><br>"
                     f"<span>{c.fmt(cart.iloc[0])} empresas en rojo en su cartera.</span>")
    c.pulso(items, "Pulso", "Sentimos el pulso. Lo convertimos en acción.")
    if st.button("Ver afiliados en riesgo", type="primary", **c.ancho(st.button)):
        if c.pagina_activa("04_renovacion.py"):
            c.ir("04_renovacion.py")
        else:
            st.session_state["dir_sem"] = ["Rojo"]
            c.ir("02_afiliados.py")
