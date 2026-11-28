# -*- coding: utf-8 -*-
"""03 · Ficha 360° del afiliado: salud, membresía, participación, satisfacción y acciones sugeridas."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import comun as c
import extracto
import ia

todas = c.empresas()
crm = todas[todas["en_crm"] == 1].sort_values(["es_vigente", "puntaje_riesgo"], ascending=[False, False])
ids = crm["empresa_id"].tolist() + sorted(todas[todas["en_crm"] == 0]["empresa_id"].tolist())
inicial = st.session_state.get("empresa_sel") or ids[0]

c.encabezado("Ficha 360° del afiliado", "Todo lo que sabemos de una empresa en una sola vista", filtros=False)
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

uso = c.uso_beneficios()
uso_e = uso[uso["empresa_id"] == emp_id]
cat = c.catalogo()
vigente = emp["es_vigente"] == 1
salud = round(100 - 100 * (emp["puntaje_riesgo"] or 0) / 9) if vigente else None

# Encabezado de la empresa
st.markdown(
    f'<div class="kpi" style="padding:1.1rem 1.3rem"><div><span style="font-size:1.5rem;font-weight:700;color:{c.C["morado"]}">{emp_id}</span> &nbsp; '
    f'{c.chip_semaforo(emp["semaforo"])} {c.chip(emp["estado_membresia"], "morado")} {c.chip(emp["nivel_2027"])}'
    f'<div class="subtitulo" style="margin-top:.4rem">{emp["tipo_membresia"]} · {emp["sector"]} · {emp["ciudad"]} · '
    f'Ejecutiva: <b>{emp["ejecutiva"]}</b> · Afiliada desde {c.fecha_txt(emp["fecha_afiliacion"])}</div></div></div>',
    unsafe_allow_html=True)

k = c.fila(5)
c.kpi(k[0], "Índice de salud", c.fmt(salud) if salud is not None else "—", "100 = sin alertas de riesgo", oscuro=True,
      chip_=("Morado", f"Riesgo {c.riesgo_txt(emp['semaforo']).lower()}" if vigente else "No vigente"))
if pd.notna(emp["dias_a_vencer"]):
    nota_vence = (f"vencida hace {c.fmt(-emp['dias_a_vencer'])} días" if emp["dias_a_vencer"] < 0
                  else f"en {c.fmt(emp['dias_a_vencer'])} días")
else:
    nota_vence = emp["rango_vencimiento"]
c.kpi(k[1], "Vence", c.fecha_txt(emp["fecha_expiracion"]), nota_vence)
c.kpi(k[2], "Beneficios usados", c.fmt(emp["servicios_12m"]),
      (f"{c.fmt(emp['servicios_incluidos_usados'])} de {c.fmt(emp['servicios_incluidos_medibles'])} incluidos en su nivel · "
       if pd.notna(emp["servicios_incluidos_medibles"]) else "") + f"{c.fmt(emp['inscripciones_12m'])} asistencias en 12 meses",
      ayuda_=c.ayuda("Aprovechamiento del nivel"))
c.kpi(k[3], "Personas que participan", c.fmt(emp["personas_distintas"]), f"{c.fmt(emp['lineas_distintas'])} líneas usadas")
prom_general = enc["satisfaccion_general"].fillna(enc["satisfaccion_prom"]).mean()
c.kpi(k[4], "Satisfacción", c.fmt(emp["satisfaccion_promedio"], 2), f"Promedio general {c.fmt(prom_general, 2)}")

izq, der = st.columns([2.2, 1], gap="medium")
with izq:
    g1, g2 = st.columns([1, 1.25])
    with g1:
        with c.tarjeta():
            comp = pd.DataFrame({"Componente": ["Vencimiento", "Participación", "Satisfacción"],
                                 "Puntos": [emp["pts_vencimiento"], emp["pts_participacion"], emp["pts_satisfaccion"]],
                                 "Máximo": [p["pts_vencida"], p["pts_sin_participacion"] + p["pts_sin_participacion_12m"],
                                            p["pts_detractor"]]})
            fig = go.Figure()
            fig.add_bar(y=comp["Componente"], x=comp["Máximo"], orientation="h", marker_color=c.C["lavanda"],
                        marker_line=dict(color=c.C["lavanda_2"], width=1),
                        name="Máximo", hoverinfo="skip")
            fig.add_bar(y=comp["Componente"], x=comp["Puntos"], orientation="h", marker_color=c.C["naranja"],
                        name="Puntos", text=comp["Puntos"], textposition="inside", textfont=dict(color=c.C["tinta"]),
                        hovertemplate="%{y}: <b>%{x}</b> puntos<extra></extra>")
            fig.update_layout(barmode="overlay", title="Componentes del riesgo", showlegend=False)
            c.grafico(fig, 200, f"{c.fmt(emp['puntaje_riesgo'])} puntos de 9 · riesgo alto desde {p['umbral_rojo']}")
    with g2:
        with c.tarjeta():
            if len(asis_e):
                linea = asis_e.groupby(["anio_mes", "linea_2027"]).size().reset_index(name="inscripciones").sort_values("anio_mes")
                linea["Mes"] = linea["anio_mes"].map(c.anio_mes_txt)
                fig = px.bar(linea, x="Mes", y="inscripciones", color="linea_2027", title="Participación en experiencias",
                             color_discrete_map=c.LINEA, labels={"linea_2027": "Línea"})
                fig.update_xaxes(title="")
                fig.update_yaxes(title="", dtick=1)
                c.grafico(fig, 200, "Inscripciones por mes y línea 2027")
            else:
                c.cabeza("Participación en experiencias", "Inscripciones por mes y línea 2027")
                st.info("Esta empresa no registra asistencias a eventos de 2026.")

    with c.tarjeta():
        nivel = emp["nivel_2027"]
        c.cabeza(f"Valor recibido · nivel {nivel}", "Beneficios incluidos en su afiliación y si los usó en los últimos 12 meses")
        col_inc = {"Conectar": "incluido_conectar", "Crecer": "incluido_crecer", "Liderar": "incluido_liderar"}.get(nivel)
        if col_inc and len(cat):
            corte_ = pd.Timestamp(p["fecha_corte"])
            u12 = uso_e[(uso_e["es_fechado"] == 0) | (pd.to_datetime(uso_e["fecha"]) > corte_ - pd.Timedelta(days=365))]
            usados = u12.groupby("servicio_id").agg(usos=("cantidad", "sum"), ultimo=("fecha", "max"),
                                                    fuente=("fuente", "first"))
            medibles = set(cat[cat["fuente_dato"].isin(["Asistencia", "CRM y asistencia"])]["servicio_id"]) | set(uso["servicio_id"])
            filas = []
            for r_ in cat[cat[col_inc] == 1].itertuples():
                if r_.servicio_id in usados.index:
                    u_ = usados.loc[r_.servicio_id]
                    estado = c.chip("Usado", "OK")
                    det = f"{c.fmt(u_['usos'])} usos · " + ("vinculación vigente" if str(u_["fuente"]).startswith("CRM")
                                                           else f"último {c.fecha_txt(u_['ultimo'])}")
                elif r_.servicio_id in medibles:
                    estado, det = c.chip("Disponible, sin usar", "Riesgo"), "Proponerlo en la próxima conversación"
                else:
                    estado, det = c.chip("Sin registro aún", "Neutro"), "ACTHO todavía no registra su uso"
                filas.append({"s": r_.servicio, "l": r_.linea_servicio, "e": estado, "d": det})
            c.tabla_html(filas, [("Beneficio", ("s", "l"), "texto"), ("Estado", "e", "html"), ("Detalle", "d", "texto")])
        else:
            st.caption("Esta afiliación no está en un nivel 2027 (persona natural o no afiliada).")

    with c.tarjeta():
        c.cabeza("Historial de participación")
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
        with c.tarjeta():
            c.cabeza("Personas de la empresa")
            if len(personas):
                pc = personas.groupby("nivel_cargo").size().reset_index(name="personas").sort_values("personas")
                fig = px.bar(pc, x="personas", y="nivel_cargo", orientation="h", text="personas",
                             color_discrete_sequence=[c.C["morado"]])
                fig.update_traces(width=0.5 if len(pc) == 1 else None, textposition="outside", cliponaxis=False,
                                  textfont=dict(color=c.C["tinta"]), hovertemplate="%{y}: <b>%{x}</b> personas<extra></extra>")
                fig.update_yaxes(title="")
                fig.update_xaxes(title="", showticklabels=False, showgrid=False, range=[0, pc["personas"].max() * 1.25])
                c.grafico(fig, max(140, 46 * len(pc) + 50))
                st.caption(f"{c.fmt((personas['autoriza_datos'] == 'Sí').sum())} de {c.fmt(len(personas))} autorizan "
                           "el uso de sus datos para comunicaciones.")
            else:
                st.caption("Sin personas registradas.")
    with p2:
        with c.tarjeta():
            c.cabeza("Encuestas de la empresa")
            if len(enc_e):
                c.tabla_df(enc_e[["fecha_respuesta", "evento", "satisfaccion_prom", "nps_puntaje", "tipo_cruce"]],
                           height=230, column_config={
                               "fecha_respuesta": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                               "evento": "Evento", "satisfaccion_prom": st.column_config.NumberColumn("Satisf.", format="%.2f"),
                               "nps_puntaje": "NPS", "tipo_cruce": "Cruce"})
            else:
                st.caption("Esta empresa no ha respondido encuestas.")

with der, c.panel():
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
    if vigente or emp["en_crm"] == 1:
        enc_ext = enc_e.copy()
        rec_e = ia.t("recomendacion")
        rec_e = rec_e[rec_e["empresa_id"] == emp_id] if len(rec_e) else None
        st.download_button("Descargar extracto de valor", extracto.html_extracto(emp, uso_e, asis_e, enc_ext, cat, p["fecha_corte"],
                                                                                 rec_e).encode("utf-8"),
                           file_name=f"extracto_valor_{emp_id}.html", mime="text/html", type="primary",
                           icon=":material/description:", key="ficha_extracto", **c.ancho(st.download_button),
                           help="Página lista para imprimir o guardar como PDF con lo que la empresa usó en el año")
    if isinstance(emp.get("inconsistencia"), str) and emp["inconsistencia"]:
        st.warning(f"Dato por revisar en el CRM: {emp['inconsistencia']}")


# ──────────────────────────────────────────────────────────────────────────────
# Apoyo de IA
# ──────────────────────────────────────────────────────────────────────────────
def _lista(txt):
    return "".join(f"<li>{c._e(x)}</li>" for x in str(txt).split(" · ") if x and x != "nan")


with der, c.tarjeta("Apoyo de IA", "Lo que sugieren los modelos para esta empresa", ayuda=ia.desc("general")):
    if not ia.hay():
        ia.sin_modelos()
    else:
        ren = ia.renovacion()
        r = ren[ren["empresa_id"] == emp_id]
        if len(r):
            r = r.iloc[0]
            color = ia.BANDA_COLOR.get(r["banda"], c.C["morado"])
            st.markdown(
                f'<div style="display:flex;align-items:baseline;gap:.6rem"><span style="font-size:2rem;font-weight:700;'
                f'color:{color}">{100 * r["p_renovar"]:.0f} %</span><span>probabilidad de renovar{ia.info("renovacion")}</span></div>'
                f'{ia.chip(r["banda"])}'
                + (f'<p style="margin:.5rem 0 .1rem;font-size:.8rem"><b>A favor</b></p><ul style="margin:0;font-size:.8rem">'
                   f'{_lista(r["a_favor"])}</ul>' if r["a_favor"] else "")
                + (f'<p style="margin:.4rem 0 .1rem;font-size:.8rem"><b>En contra</b></p><ul style="margin:0;font-size:.8rem">'
                   f'{_lista(r["en_contra"])}</ul>' if r["en_contra"] else ""),
                unsafe_allow_html=True)
            lectura = {"Probable": "suele renovar: mantén la relación y pide referidos.",
                       "Incierta": "puede ir para cualquier lado: conviene una conversación de valor antes del vencimiento.",
                       "En riesgo": "se parece más a las que no renovaron: priorízala y ataca los factores en contra."}
            st.markdown(f'<p style="font-size:.78rem;margin:.5rem 0 .2rem"><b>Cómo leerlo:</b> {r["banda"]} — '
                        f'{lectura.get(r["banda"], "")} El porcentaje sale de compararla con las 503 empresas que ya '
                        'decidieron en el último año. Si sabes algo que los datos no muestran (cambio de gerente, una queja, '
                        'recorte de presupuesto), tu criterio pesa más.</p>', unsafe_allow_html=True)
            ia.nota("renovacion")
        acc = ia.t("accion")
        a = acc[acc["empresa_id"] == emp_id] if len(acc) else acc
        if len(a):
            c.actividad(f"Siguiente paso: {a.iloc[0]['accion']}", a.iloc[0]["motivo"], acento=True)
        per = ia.perfiles()
        pe = per[per["empresa_id"] == emp_id] if len(per) else per
        if len(pe):
            res = ia.t("perfil_resumen").set_index("perfil")
            nombre = pe.iloc[0]["perfil"]
            c.actividad(f"Perfil: {nombre}", res.loc[nombre, "descripcion"] if nombre in res.index else "")
        rec = ia.t("recomendacion")
        rec = rec[rec["empresa_id"] == emp_id] if len(rec) else rec
        for x in rec.itertuples():
            c.actividad(f"{x.tipo}: {x.recomendacion}", x.motivo)
        par = ia.t("empresa_parecida")
        par = par[par["empresa_id"] == emp_id] if len(par) else par
        if len(par):
            info = ren.set_index("empresa_id")["banda"] if len(ren) else {}
            filas = [{"e": x.parecida_id, "s": f"{100 * x.similitud:.0f}",
                      "b": ia.chip(info.get(x.parecida_id, "—")) if len(ren) else ""} for x in par.itertuples()]
            st.markdown('<p style="margin:.6rem 0 .2rem;font-size:.8rem"><b>Empresas parecidas</b> (misma forma de '
                        'usar la membresía)</p>', unsafe_allow_html=True)
            c.tabla_html(filas, [("Empresa", "e", "texto"), ("Parecido", "s", "num"), ("Renovación", "b", "html")])
            def _abrir():
                v = st.session_state.get("ficha_parecida")
                if v and v != "—":
                    st.session_state["ficha_empresa"] = st.session_state["empresa_sel"] = v
                st.session_state["ficha_parecida"] = "—"

            st.selectbox("Abrir la ficha de una empresa parecida", ["—"] + par["parecida_id"].tolist(),
                         key="ficha_parecida", on_change=_abrir)
        if not vigente:
            pr = ia.propension()
            x = pr[pr["empresa_id"] == emp_id] if len(pr) else pr
            if len(x):
                c.actividad(f"Parecido con afiliadas: {x.iloc[0]['puntaje']:.0f} / 100 ({x.iloc[0]['banda']})",
                            "Qué tanto se parece su forma de participar a la de las empresas afiliadas", acento=True)
                ia.nota("propension")
