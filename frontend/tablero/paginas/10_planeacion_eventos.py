# -*- coding: utf-8 -*-
"""10 · Planeación de eventos: simula un evento antes de hacerlo (inscritos, % de afiliados, cargos y
satisfacción esperados a partir de los eventos parecidos), revisa la demanda del tema y la fecha, arma la
convocatoria con quienes autorizaron datos y guarda el plan para compararlo después con lo real."""
import json
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import comun as c
import ia

c.encabezado("Planeación de eventos", "Simula un evento antes de hacerlo y arma su convocatoria", filtros=False)

if not ia.hay() or ia.t("evento_base").empty:
    ia.sin_modelos()
    st.stop()

import simulador_eventos as sim  # noqa: E402  (vive en src/, ia.py agrega la ruta)

base = ia.t("evento_base").copy()
base["fecha"] = pd.to_datetime(base["fecha"])
residuos = ia.t("evento_backtest")["residuo_log"].to_numpy()
demanda = ia.t("tema_demanda")
interes = ia.t("interes_persona")
corte = pd.Timestamp(c.parametros()["fecha_corte"])
COSTOS = {"Gratuito": 0.0, "Con costo solo para no afiliados": 0.1, "Pago para todos (taller, sesión de trabajo)": 0.9}
TEMAS = sorted(t for t in demanda["tema"].unique()) if not demanda.empty else sorted(base["tema"].unique())


def opciones(col):
    return sorted(base[col].dropna().astype(str).unique())


# ──────────────────────────────────────────────────────────────────────────────
# 1. Diseño del evento
# ──────────────────────────────────────────────────────────────────────────────
izq, der = c.columnas([1.05, 2.3], "lateral", gap="medium")
with izq, c.tarjeta("Diseña el evento", "Cambia cualquier dato y la estimación se actualiza"):
    nombre = st.text_input("Nombre del evento", "Nuevo evento", max_chars=120)
    fecha = st.date_input("Fecha", value=max(date.today(), corte.date()) + timedelta(days=30), format="DD/MM/YYYY")
    modalidad = st.selectbox("Modalidad", opciones("modalidad"), index=opciones("modalidad").index("Presencial")
                             if "Presencial" in opciones("modalidad") else 0)
    linea = st.selectbox("Línea 2027", opciones("linea_2027"))
    exp_op = opciones("experiencia")
    experiencia = st.selectbox("Experiencia", exp_op, index=exp_op.index("Sin dato") if "Sin dato" in exp_op else 0,
                               help="La experiencia de la oferta 2027 a la que pertenece (Sin dato si es general).")
    tema = st.selectbox("Tema", TEMAS, index=TEMAS.index("Inteligencia artificial aplicada a talento humano")
                        if "Inteligencia artificial aplicada a talento humano" in TEMAS else 0)
    costo = st.radio("Costo", list(COSTOS), index=0)
    cupo = st.number_input("Cupo (0 = sin límite)", min_value=0, max_value=5000, value=0, step=10)

q = {"modalidad": modalidad, "linea_2027": linea, "tema": tema, "experiencia": experiencia,
     "pct_con_costo": COSTOS[costo], "mes": fecha.month, "dia_semana": fecha.weekday()}
r = sim.predecir(base, q, residuos=residuos)
vec = r["vecinos"]

with der:
    k = c.fila(4)
    rango = f"Rango probable (80 %): {c.fmt(r.get('li80'))} a {c.fmt(r.get('ls80'))}"
    c.kpi(k[0], "Inscritos esperados", c.fmt(r["inscritos"]), rango, oscuro=True, chip_=("IA", "Simulación"),
          ayuda_=ia.desc("eventos"))
    c.kpi(k[1], "Afiliados entre inscritos", c.fmt(r["pct_afiliados"], 0, " %"),
          "Parte de inscritos de empresas afiliadas vigentes", chip_=("IA", "Eventos parecidos"),
          ayuda_="Promedio, ponderado por parecido, del % de inscritos afiliados en los 5 eventos más parecidos.")
    c.kpi(k[2], "Satisfacción esperada", c.fmt(r["satisfaccion"], 2) if r["satisfaccion"] else "—",
          "Promedio 1 a 5 de las encuestas de los eventos parecidos", chip_=("IA", "Eventos parecidos"),
          ayuda_="Promedio, ponderado por parecido, de la satisfacción (1 a 5) en los eventos parecidos que tuvieron encuesta.")
    c.kpi(k[3], "Empresas distintas", c.fmt(r["empresas"]), "Empresas que suelen inscribirse en eventos así",
          chip_=("IA", "Eventos parecidos"),
          ayuda_="Promedio, ponderado por parecido, de las empresas distintas inscritas en los eventos parecidos.")
    ia.nota("eventos")
    if cupo:
        if cupo < (r.get("li80") or 0):
            st.warning(f"El cupo de {c.fmt(cupo)} es menor que el rango probable: es posible que se llene rápido. "
                       "Considera lista de espera o un segundo grupo.", icon=":material/group_add:")
        elif cupo > (r.get("ls80") or np.inf) * 1.3:
            st.info(f"El cupo de {c.fmt(cupo)} está muy por encima de lo esperado: o se refuerza la convocatoria o "
                    "se reserva un espacio más pequeño.", icon=":material/event_seat:")

    with c.tarjeta("Cómo se compara con los eventos parecidos", "Los 5 eventos en los que se basa la estimación",
                   ayuda=ia.desc("eventos")):
        v = vec.sort_values("inscritos").copy()
        v["Etiqueta"] = v["nombre"].map(lambda n: c.partir(n, 46))
        fig = go.Figure()
        if r.get("li80") is not None:
            fig.add_vrect(x0=r["li80"], x1=r["ls80"], fillcolor=c.C["lavanda"], line_width=0, layer="below",
                          annotation_text="Rango probable", annotation_position="top left",
                          annotation_font=dict(color=c.C["morado"], size=11))
        fig.add_bar(x=v["inscritos"], y=v["Etiqueta"], orientation="h", marker_color=c.C["morado"],
                    text=v["inscritos"], textposition="outside", cliponaxis=False,
                    customdata=np.c_[v["modalidad"], v["tema"], v["fecha"].dt.strftime("%d/%m/%Y"), v["peso"].round(2)],
                    hovertemplate="%{y}<br>%{customdata[2]} · %{customdata[0]} · %{customdata[1]}<br>"
                                  "<b>%{x}</b> inscritos · peso %{customdata[3]}<extra></extra>", name="Inscritos")
        fig.add_vline(x=r["inscritos"], line=dict(color=c.C["naranja"], width=3, dash="dash"),
                      annotation_text=f"Estimado: {c.fmt(r['inscritos'])}", annotation_position="bottom right",
                      annotation_font=dict(color=c.C["naranja_texto"], size=12))
        fig.update_layout(showlegend=False)
        fig.update_xaxes(title="Inscritos", range=[0, max(v["inscritos"].max(), r.get("ls80") or 0) * 1.18])
        fig.update_yaxes(title="")
        c.grafico(fig, 300)

    cargos = {k_: v_ for k_, v_ in r["cargos"].items() if v_ and k_ not in ("Sin dato",)}
    g1, g2 = c.columnas(2, "pareja")
    with g1, c.tarjeta("Quiénes vendrían", "Nivel de cargo esperado (% de inscritos)"):
        d = pd.Series(cargos).sort_values()
        fig = go.Figure(go.Bar(x=d.values, y=[c.partir(i, 22) for i in d.index], orientation="h",
                               marker_color=c.C["cian_graf"], text=[f"{x:.0f} %" for x in d.values],
                               textposition="outside", cliponaxis=False,
                               hovertemplate="%{y}: <b>%{x:.0f} %</b><extra></extra>"))
        fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, d.max() * 1.3 if len(d) else 1])
        c.grafico(fig, 260)
    with g2, c.tarjeta("La fecha", f"{fecha:%d/%m/%Y} · {sim.DIAS[fecha.weekday()]}"):
        avisos = []
        if fecha.weekday() >= 5:
            avisos.append(("Alerta", "Cae en fin de semana: en 2026 ningún evento de ACTHO se hizo en sábado o domingo."))
        dia_hist = base["fecha"].dt.dayofweek.value_counts()
        if fecha.weekday() < 5 and dia_hist.get(fecha.weekday(), 0) == 0:
            avisos.append(("Neutro", f"No hay eventos previos un {sim.DIAS[fecha.weekday()]}: la estimación pesa menos el día."))
        cerca = base[(base["fecha"] - pd.Timestamp(fecha)).abs() <= pd.Timedelta(days=3)]
        for _, ev in cerca.iterrows():
            avisos.append(("Alerta", f"Muy cerca de «{c.partir(ev['nombre'], 60).replace('<br>', ' ')}» "
                                     f"({ev['fecha']:%d/%m/%Y})."))
        try:
            planes = c.consulta("SELECT nombre, fecha FROM historial.plan_evento WHERE fecha BETWEEN %s AND %s",
                                (fecha - timedelta(days=7), fecha + timedelta(days=7)))
            for _, pl in planes.iterrows():
                avisos.append(("Alerta", f"Ya hay un plan guardado para {pd.Timestamp(pl['fecha']):%d/%m}: «{pl['nombre']}»."))
        except Exception:  # noqa: BLE001
            pass
        e = ia.con_ia(c.empresas())
        vence = e[(e["es_vigente"] == 1) & (pd.to_datetime(e["fecha_expiracion"]).dt.to_period("M") == pd.Period(fecha, "M"))]
        if len(vence):
            riesgo = (vence.get("banda") == "En riesgo").sum() if "banda" in vence else 0
            avisos.append(("Morado", f"En {c.MESES[fecha.month - 1]} vencen {c.fmt(len(vence))} afiliadas"
                                     + (f" ({c.fmt(riesgo)} con baja probabilidad de renovar)" if riesgo else "")
                                     + ": invítalas, el evento puede ser parte de su renovación."))
        if not avisos:
            avisos.append(("OK", "Sin choques con eventos pasados ni planes guardados en esa semana."))
        for tono, txt in avisos:
            st.markdown(f'<div class="hallazgo"><div>{c.chip({"Alerta": "Revisar", "OK": "Bien", "Morado": "Oportunidad", "Neutro": "Nota"}[tono], tono)} {txt}</div></div>',
                        unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# 2. Demanda del tema
# ──────────────────────────────────────────────────────────────────────────────
d1, d2 = c.columnas([1.6, 1], "lateral", gap="medium")
with d1, c.tarjeta("Lo que piden frente a lo que ofrecemos",
                   "% de solicitudes en encuestas y % de eventos de 2026 por tema · el tema elegido resaltado",
                   ayuda=ia.desc("temas")):
    dd = demanda[demanda["tema"] != "General / tendencias"].sort_values("pct_demanda")
    dd["Etiqueta"] = dd["tema"].map(lambda t_: c.partir(t_, 34))
    opac = [1 if t_ == tema else 0.35 for t_ in dd["tema"]]
    fig = go.Figure()
    fig.add_bar(y=dd["Etiqueta"], x=dd["pct_demanda"], name="Piden (encuestas)", orientation="h",
                marker=dict(color=c.C["naranja"], opacity=opac), customdata=dd[["solicitudes"]].to_numpy(),
                hovertemplate="%{y}<br>Piden: <b>%{x} %</b> (%{customdata[0]} menciones)<extra></extra>")
    fig.add_bar(y=dd["Etiqueta"], x=dd["pct_oferta"], name="Ofrecemos (eventos)", orientation="h",
                marker=dict(color=c.C["morado"], opacity=opac), customdata=dd[["eventos"]].to_numpy(),
                hovertemplate="%{y}<br>Ofrecemos: <b>%{x} %</b> (%{customdata[0]} eventos)<extra></extra>")
    fig.update_layout(barmode="group", bargap=0.25)
    fig.update_xaxes(title="% del total", ticksuffix=" %")
    c.grafico(fig, 470)
    ia.nota("temas", "temas leídos de comentarios libres; revisa la ficha para su precisión")
with d2, c.panel():
    fila_t = demanda[demanda["tema"] == tema]
    items = []
    if len(fila_t):
        ft = fila_t.iloc[0]
        brecha = ft["brecha"]
        items.append(f"<b>{tema}</b><br><span>{c.fmt(ft['solicitudes'])} menciones en encuestas "
                     f"({c.fmt(ft['pct_demanda'], 1)} %) y {c.fmt(ft['eventos'])} eventos en 2026 "
                     f"({c.fmt(ft['pct_oferta'], 1)} %).</span>")
        items.append(("<b>Tema con demanda sin atender</b><br><span>Lo piden más de lo que se ofrece: buena apuesta "
                       "para atraer y retener.</span>") if brecha > 1 else
                     ("<b>Tema ya bien cubierto</b><br><span>Se ofrece tanto o más de lo que se pide: diferénciate en "
                      "formato o profundidad.</span>") if brecha < -1 else
                     "<b>Oferta y demanda equilibradas</b><br><span>El tema se ofrece en proporción a lo que piden.</span>")
    top = demanda[demanda["tema"] != "General / tendencias"].nlargest(3, "brecha")
    items.append("<b>Mayores brechas</b><br><span>" + " · ".join(top["tema"]) + "</span>")
    tex = ia.t("tema_texto")
    if not tex.empty:
        ej = tex[(tex["tema"] == tema) & (tex["origen"] != "Etiqueta de la encuesta")]["temas_solicitados"].head(3)
        if len(ej):
            items.append("<b>Lo que dicen</b><br><span>" + " · ".join(f"«{c._e(x[:90])}»" for x in ej) + "</span>")
    c.pulso(items, "Pulso del tema", "Demanda leída de las encuestas")

# ──────────────────────────────────────────────────────────────────────────────
# 3. Convocatoria
# ──────────────────────────────────────────────────────────────────────────────
with c.tarjeta("Convocatoria sugerida", "Personas con interés en el tema que autorizaron el uso de sus datos",
               ayuda="Interés = eventos del tema a los que asistió + 2 × veces que lo pidió en encuestas (tema leído con IA). "
                     "Primero quienes trabajan en afiliadas con baja probabilidad de renovar."):
    f1, f2, f3 = c.columnas([2, 1.2, 1], "controles")
    niveles = sorted(interes["nivel_cargo"].dropna().unique()) if not interes.empty else []
    publico = f1.multiselect("Público objetivo (nivel de cargo)", niveles,
                             default=[n for n in niveles if n not in ("Estudiante / Practicante", "Otro", "Sin dato")])
    solo_af = f2.radio("Empresas", ["Todas", "Solo afiliadas", "Solo no afiliadas"], horizontal=False)
    n_max = f3.number_input("Máximo de personas", 10, 2000, 200, step=10)
    conv = interes[(interes["tema"] == tema) & (interes["autoriza_datos"] == "Sí")].copy()
    if publico:
        conv = conv[conv["nivel_cargo"].isin(publico)]
    if solo_af == "Solo afiliadas":
        conv = conv[conv["es_afiliada"] == 1]
    elif solo_af == "Solo no afiliadas":
        conv = conv[conv["es_afiliada"] == 0]
    ren = ia.renovacion()
    if not ren.empty:
        conv = conv.merge(ren[["empresa_id", "banda"]], on="empresa_id", how="left")
    else:
        conv["banda"] = None
    conv["prioridad"] = conv["puntaje"] + np.where(conv["banda"] == "En riesgo", 2, 0)
    conv = conv.sort_values("prioridad", ascending=False).head(int(n_max))
    k = c.fila(4)
    c.kpi(k[0], "Personas a convocar", c.fmt(len(conv)), "Con interés en el tema y autorización de datos")
    c.kpi(k[1], "Empresas", c.fmt(conv["empresa_id"].nunique()), "Empresas distintas en la lista")
    c.kpi(k[2], "De afiliadas en riesgo", c.fmt((conv["banda"] == "En riesgo").sum()),
          "Invitarlas ayuda a la renovación", chip_=("IA", "Prob. de renovar"), ayuda_=ia.desc("renovacion"))
    c.kpi(k[3], "No afiliadas", c.fmt((conv["es_afiliada"] == 0).sum()), "Oportunidad de afiliación")
    vista = conv.rename(columns={"persona_id": "Persona", "empresa_id": "Empresa", "nivel_cargo": "Cargo",
                                 "asistencias": "Eventos del tema", "pedidos": "Lo pidió en encuestas",
                                 "es_afiliada": "Afiliada", "banda": "Renovación (IA)"})
    vista["Afiliada"] = vista["Afiliada"].map({1: "Sí", 0: "No"})
    cols = ["Persona", "Empresa", "Cargo", "Eventos del tema", "Lo pidió en encuestas", "Afiliada", "Renovación (IA)"]
    c.tabla_df(vista[cols], height=280)
    st.caption("Los datos vienen anonimizados: la lista trae identificadores de persona y empresa para cruzarlos con "
               "Zoho y sacar nombres y correos. Solo incluye a quienes autorizaron el tratamiento de datos.")
    c.descargar(vista[cols], f"convocatoria_{fecha:%Y%m%d}.csv", "Descargar convocatoria (CSV)")

# ──────────────────────────────────────────────────────────────────────────────
# 4. Guardar el plan y comparar con lo real
# ──────────────────────────────────────────────────────────────────────────────
SQL_PLAN = """CREATE SCHEMA IF NOT EXISTS historial;
CREATE TABLE IF NOT EXISTS historial.plan_evento (
    plan_id serial PRIMARY KEY, creado timestamp DEFAULT now(), creado_por text,
    nombre text NOT NULL, fecha date, modalidad text, linea_2027 text, experiencia text, tema text,
    costo text, cupo integer, estimado numeric, li80 numeric, ls80 numeric, pct_afiliados numeric,
    satisfaccion numeric, parametros jsonb, evento_id_real integer, notas text)"""


def guardar_plan():
    import psycopg
    with psycopg.connect(c._url(), autocommit=True) as conn:
        conn.execute(SQL_PLAN)
        conn.execute("""INSERT INTO historial.plan_evento (creado_por, nombre, fecha, modalidad, linea_2027, experiencia,
                        tema, costo, cupo, estimado, li80, ls80, pct_afiliados, satisfaccion, parametros)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                     ((st.session_state.get("sesion") or {}).get("usuario"), nombre, fecha, modalidad, linea, experiencia, tema, costo, cupo or None,
                      round(r["inscritos"], 1), r.get("li80"), r.get("ls80"), r["pct_afiliados"], r["satisfaccion"],
                      json.dumps(q, default=str)))
    c.consulta.clear()


with c.tarjeta("Planes guardados", "Guarda la simulación; cuando el evento ocurra se compara con lo real"):
    b1, b2 = c.columnas([1, 3], "controles")
    if b1.button("Guardar este plan", type="primary", icon=":material/save:"):
        try:
            guardar_plan()
            st.toast(f"Plan «{nombre}» guardado", icon=":material/check_circle:")
        except Exception as ex:  # noqa: BLE001
            st.error(f"No se pudo guardar el plan: {ex}")
    b2.caption("Los planes quedan en el historial de PostgreSQL (no se borran con cada carga de datos).")
    try:
        planes = c.consulta("SELECT * FROM historial.plan_evento ORDER BY fecha")
    except Exception:  # noqa: BLE001
        planes = pd.DataFrame()
    if planes.empty:
        st.caption("Aún no hay planes guardados.")
    else:
        real = c.tabla("dim_evento")[["evento_id", "fecha", "modalidad", "inscritos"]]
        real["fecha"] = pd.to_datetime(real["fecha"])
        planes["fecha"] = pd.to_datetime(planes["fecha"])
        m = planes.merge(real, on=["fecha", "modalidad"], how="left", suffixes=("", "_real"))
        m = m.drop_duplicates("plan_id")
        m["Resultado"] = np.where(m["inscritos"].isna(),
                                  np.where(m["fecha"] > corte, "Por realizar", "Sin evento registrado en esa fecha"),
                                  np.where((m["inscritos"] >= m["li80"]) & (m["inscritos"] <= m["ls80"]), "Dentro del rango",
                                           np.where(m["inscritos"] > m["ls80"], "Por encima", "Por debajo")))
        vista = pd.DataFrame({"Plan": m["nombre"], "Fecha": m["fecha"].dt.strftime("%d/%m/%Y"), "Modalidad": m["modalidad"],
                              "Tema": m["tema"], "Estimado": m["estimado"].round(0),
                              "Rango 80 %": m["li80"].round(0).astype("Int64").astype(str) + " – " + m["ls80"].round(0).astype("Int64").astype(str),
                              "Real": m["inscritos"].astype("Int64").astype(str).replace("<NA>", "—"),
                              "Resultado": m["Resultado"]})
        c.tabla_df(vista)

with st.expander("¿Qué tan bien estima? Prueba con los eventos de 2026"):
    bt = ia.t("evento_backtest").merge(base[["evento_id", "nombre", "modalidad"]], on="evento_id")
    fig = go.Figure()
    lim = max(bt["real"].max(), bt["estimado"].max()) * 1.05
    fig.add_scatter(x=[0, lim], y=[0, lim], mode="lines", line=dict(color=c.C["linea"], dash="dot"), hoverinfo="skip",
                    name="Estimado = real")
    for mod, g in bt.groupby("modalidad"):
        fig.add_scatter(x=g["real"], y=g["estimado"], mode="markers", name=mod,
                        marker=dict(size=10, color=c.MODALIDAD.get(mod, c.C["morado"])), text=g["nombre"],
                        hovertemplate="%{text}<br>Real <b>%{x}</b> · estimado <b>%{y:.0f}</b><extra></extra>")
    marcas = [10, 20, 50, 100, 200, 500]
    fig.update_xaxes(title="Inscritos reales", type="log", tickvals=marcas)
    fig.update_yaxes(title="Estimado sin ver el evento", type="log", tickvals=marcas)
    c.grafico(fig, 360, "Cada punto es un evento estimado con los demás (validación dejando uno fuera) · escala logarítmica")
    f = ia.ficha("eventos")
    st.caption(f"{f.get('linea_base', '')} {f.get('limitaciones', '')}")
