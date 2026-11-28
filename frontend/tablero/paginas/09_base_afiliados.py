# -*- coding: utf-8 -*-
"""09 · Base de afiliados: cómo se mueve la base (altas, retiros, vencimientos por renovar) y cómo está compuesta
(tipo, sector, tamaño y ciudad). Responde la pregunta de afiliación del reto."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import comun as c
import ia

c.encabezado("Base de afiliados", "Cómo se mueve la base mes a mes y cómo está compuesta")

p = c.parametros()
corte = pd.Timestamp(p["fecha_corte"])
e, _, _ = c.datos()
crm = e[e["en_crm"] == 1]
vig = crm[crm["es_vigente"] == 1]
fa, fx = pd.to_datetime(crm["fecha_afiliacion"]), pd.to_datetime(crm["fecha_expiracion"])
retirada = crm["estado_membresia"].isin(["Cancelado", "Expirado", "Inactivo"])
hace12 = corte - pd.Timedelta(days=365)
altas12 = ((fa > hace12) & (fa <= corte)).sum()
retiros12 = (retirada & (fx > hace12) & (fx <= corte)).sum()
renov = c.tasa_renovacion(e)

k = c.fila(5)
c.kpi(k[0], "Afiliados vigentes", c.fmt(len(vig)), f"{c.fmt((vig['es_activo'] == 1).sum())} activos · el resto en gracia o por expirar",
      oscuro=True, chip_=("Morado", f"{c.fmt(vig['nivel_2027'].nunique())} niveles"), ayuda_=c.ayuda("Afiliados vigentes"))
c.kpi(k[1], "Altas en 12 meses", c.fmt(altas12), "Empresas con fecha de afiliación en el último año",
      chip_=("OK", f"{c.fmt(altas12 / 12, 1)} por mes"), ayuda_=c.ayuda("Altas"))
c.kpi(k[2], "Retiros en 12 meses", c.fmt(retiros12), "Canceladas, expiradas o inactivas que vencieron en el año",
      chip_=("Riesgo", "Motivo no registrado"), ayuda_=c.ayuda("Retiros"))
neto = altas12 - retiros12
c.kpi(k[3], "Crecimiento neto", ("+" if neto > 0 else "") + c.fmt(neto), "Altas menos retiros en 12 meses",
      chip_=("OK" if neto >= 0 else "Alerta", "La base crece" if neto >= 0 else "La base se reduce"))
c.kpi(k[4], "Tasa de renovación", c.fmt(renov["tasa"], 1, " %"), renov["nota"],
      chip_=("Alerta", f"Meta 2027: {c.fmt(c.METAS_2027['renovacion'], 0)} %"),
      ayuda_=c.ayuda("Tasa de renovación (medida)" if renov["tipo"] == "medida" else "Tasa de renovación (aproximada)"))

principal, lateral = st.columns([3.2, 1], gap="medium")
with principal:
    with c.tarjeta():
        e_m, _, _ = c.datos(excluir=("mes_alta",))
        crm_m = e_m[e_m["en_crm"] == 1]
        fa_m, fx_m = pd.to_datetime(crm_m["fecha_afiliacion"]), pd.to_datetime(crm_m["fecha_expiracion"])
        meses = pd.period_range(corte - pd.DateOffset(months=23), corte, freq="M")
        claves = [m.strftime("%Y-%m") for m in meses]
        altas = fa_m.dt.strftime("%Y-%m").value_counts()
        ret = fx_m[crm_m["estado_membresia"].isin(["Cancelado", "Expirado", "Inactivo"])].dt.strftime("%Y-%m").value_counts()
        mov = pd.DataFrame({"mes": claves})
        mov["altas"] = mov["mes"].map(altas).fillna(0)
        mov["retiros"] = -mov["mes"].map(ret).fillna(0)
        mov["neto"] = (mov["altas"] + mov["retiros"]).cumsum()
        mov["Mes"] = mov["mes"].map(lambda m: c.anio_mes_txt(m).replace(" ", "<br>"))
        fig = go.Figure()
        fig.add_bar(x=mov["Mes"], y=mov["altas"], name="Altas", marker_color=c.C["morado"], customdata=mov[["mes"]].to_numpy(),
                    hovertemplate="%{x}: <b>%{y}</b> altas<extra></extra>")
        # Solo las altas filtran (el mes de retiro no es una dimensión de la empresa vigente).
        fig.add_bar(x=mov["Mes"], y=mov["retiros"], name="Retiros", marker_color=c.C["naranja"],
                    hovertext=(-mov["retiros"]).astype(int).astype(str), hovertemplate="%{x}: <b>%{hovertext}</b> retiros<extra></extra>")
        fig.add_scatter(x=mov["Mes"], y=mov["neto"], name="Neto acumulado", mode="lines+markers",
                        line=dict(color=c.C["cian_graf"], width=3), marker=dict(size=6),
                        hovertemplate="%{x}: neto acumulado <b>%{y}</b><extra></extra>")
        fig.update_layout(barmode="relative", title="Movimiento de la base")
        fig.update_xaxes(title="", tickangle=0, tickmode="array", tickvals=list(mov["Mes"])[::2])
        fig.update_yaxes(title="Empresas", zeroline=True, zerolinecolor=c.C["linea"])
        c.grafico(fig, 340, "Últimos 24 meses · altas arriba, retiros abajo y neto acumulado · clic en una alta para ver esas empresas",
                  dims=["mes_alta"], clave="mov")
        st.caption("Altas: fecha de afiliación de las empresas que siguen en Zoho (las que salieron hace años pueden no "
                   "estar). Retiros: fecha de expiración de las canceladas, expiradas o inactivas. Desde la segunda foto "
                   "mensual de Airflow, las renovaciones y retiros se miden sin aproximaciones.")

    def banda(fig, d, color, nombre):
        x = list(d["mes"]) + list(d["mes"])[::-1]
        for li, ls, alfa, et in (("li95", "ls95", 0.12, "95 %"), ("li80", "ls80", 0.25, "80 %")):
            if li in d and d[li].notna().any():
                fig.add_scatter(x=x, y=list(d[ls]) + list(d[li])[::-1], fill="toself", mode="lines", line=dict(width=0),
                                fillcolor=c._desvanecer(color, alfa), name=f"Rango {et}", hoverinfo="skip")
        fig.add_scatter(x=d["mes"], y=d["pronostico"], mode="lines+markers", name=nombre,
                        line=dict(color=color, width=3, dash="dash"), marker=dict(size=5),
                        hovertemplate="%{x|%b %Y}: <b>%{y:.0f}</b><extra>" + nombre + "</extra>")

    alt = ia.pronostico("altas")
    vproy = ia.pronostico("vigentes")
    if len(alt) and len(vproy):
        g1, g2 = st.columns(2)
        with g1, c.tarjeta():
            h = alt[(alt["tipo"] == "historia") & (alt["mes"] >= corte - pd.DateOffset(months=36))]
            f = alt[alt["tipo"] == "pronostico"]
            fig = go.Figure()
            fig.add_bar(x=h["mes"], y=h["real"], name="Altas reales", marker_color=c.C["morado"],
                        hovertemplate="%{x|%b %Y}: <b>%{y:.0f}</b> altas<extra></extra>")
            banda(fig, f, c.C["naranja"], "Pronóstico")
            fig.update_layout(title="Altas por mes: real y pronóstico")
            fig.update_xaxes(title="")
            fig.update_yaxes(title="Empresas nuevas", rangemode="tozero")
            c.grafico(fig, 320, f"Últimos 36 meses y pronóstico a dic-2027 · {c.fmt(f['pronostico'].sum())} altas esperadas")
            fa_ = ia.ficha("altas")
            ia.nota("altas", "le gana a la línea base" if fa_.get("detalle", {}).get("gana_linea_base") else
                    "no le gana a todas las líneas base: úsalo como referencia")
        with g2, c.tarjeta():
            fig = go.Figure()
            fig.add_hline(y=len(vig), line=dict(color=c.C["linea"], dash="dot"),
                          annotation_text=f"Hoy: {c.fmt(len(vig))}", annotation_position="bottom left")
            banda(fig, vproy, c.C["morado"], "Vigentes proyectadas")
            fig.update_layout(title="Afiliadas vigentes proyectadas")
            fig.update_xaxes(title="")
            fig.update_yaxes(title="Vigentes")
            fin = vproy.iloc[-1]
            c.grafico(fig, 320, f"Dic-2027: {c.fmt(fin['pronostico'])} (80 %: {c.fmt(fin['li80'])} a {c.fmt(fin['ls80'])}) "
                                "· simulación con la probabilidad de renovar de cada empresa + altas esperadas")
            ia.nota("vigentes")
        st.caption("Las proyecciones son de toda la base (no responden a los filtros) y se recalculan con cada carga.")

    def composicion(col, dim, titulo, top=None):
        with col, c.tarjeta():
            e_c, _, _ = c.datos(excluir=(dim,))
            v = e_c[e_c["es_vigente"] == 1]
            d = v.groupby(dim).agg(vigentes=("empresa_id", "count"), usan=("participa_en_ventana", "mean"),
                                   alto=("semaforo", lambda s: (s == "Rojo").mean())).reset_index()
            d = d.sort_values("vigentes", ascending=False)
            resto = None
            if top and len(d) > top:
                resto = d.iloc[top:]["vigentes"].sum()
                d = d.head(top)
            d["usan"] = (100 * d["usan"]).round(0)
            d["alto"] = (100 * d["alto"]).round(0)
            d["Etiqueta"] = d[dim].map(lambda t: c.partir(t, 22))
            fig = px.bar(d.iloc[::-1], x="vigentes", y="Etiqueta", orientation="h", text="vigentes",
                         custom_data=[dim, "usan", "alto"], title=titulo, color_discrete_sequence=[c.C["morado"]])
            fig.update_traces(textposition="outside", cliponaxis=False, textfont=dict(color=c.C["tinta"]),
                              hovertemplate="%{y}: <b>%{x}</b> vigentes · %{customdata[1]} % usa beneficios · "
                                            "%{customdata[2]} % riesgo alto<extra></extra>")
            fig.update_xaxes(title="", showticklabels=False, showgrid=False, range=[0, max(d["vigentes"].max(), 1) * 1.2])
            fig.update_yaxes(title="")
            sub = "Vigentes · clic para filtrar" + (f" · {c.fmt(resto)} en otras categorías" if resto else "")
            c.grafico(fig, max(220, 30 * len(d) + 70), sub, dims=[dim], clave=f"comp_{dim}")

    f1, f2 = st.columns(2)
    composicion(f1, "tipo_membresia", "Por tipo de afiliado")
    composicion(f2, "tamano_empresa", "Por tamaño de empresa")
    f3, f4 = st.columns(2)
    composicion(f3, "sector", "Por sector (10 principales)", top=10)
    composicion(f4, "ciudad", "Por ciudad (10 principales)", top=10)

    with c.tarjeta():
        c.cabeza("Composición detallada", "Vigentes por nivel 2027 y tipo de afiliado")
        piv = vig.pivot_table(index="nivel_2027", columns="tipo_membresia", values="empresa_id", aggfunc="count",
                              fill_value=0, margins=True, margins_name="Total")
        c.tabla_df(piv.reset_index().rename(columns={"nivel_2027": "Nivel 2027"}))
        c.descargar(vig[["empresa_id", "nivel_2027", "tipo_membresia", "sector", "subsector", "tamano_empresa", "ciudad",
                         "region", "ejecutiva", "estado_membresia", "fecha_afiliacion", "fecha_expiracion"]],
                    "base_afiliados_vigentes.csv", "Exportar la base vigente (CSV)")

with lateral, c.panel():
    items = []
    if len(vig):
        top_ciudad = vig["ciudad"].value_counts()
        items.append(f"<b>{c.fmt(100 * top_ciudad.iloc[0] / len(vig), 0)} % de la base está en {top_ciudad.index[0]}</b><br>"
                     "<span>La presencia nacional de 2027 empieza con una base muy concentrada.</span>")
        top_sector = vig["sector"].value_counts()
        items.append(f"<b>{top_sector.index[0]} es el sector más grande</b><br><span>{c.fmt(top_sector.iloc[0])} empresas vigentes "
                     f"({c.fmt(100 * top_sector.iloc[0] / len(vig), 0)} %).</span>")
    mes_alta = pd.to_datetime(crm["fecha_afiliacion"]).dt.month.value_counts()
    if len(mes_alta):
        items.append(f"<b>{c.MESES[int(mes_alta.index[0]) - 1].capitalize()} es el mes con más afiliaciones</b><br>"
                     "<span>Históricamente; conviene reforzar la prospección antes de ese mes.</span>")
    items.append(f"<b>Crecimiento neto: {('+' if neto > 0 else '') + c.fmt(neto)} en 12 meses</b><br>"
                 f"<span>{c.fmt(altas12)} altas frente a {c.fmt(retiros12)} retiros.</span>")
    fv = ia.ficha("vigentes")
    if fv:
        d_ = fv["detalle"]
        items.append(f"<b>✦ Si nada cambia: {c.fmt(fv['valor'])} vigentes a dic-2027</b>{ia.info('vigentes')}<br><span>De las "
                     f"{c.fmt(d_.get('vencen_2026'))} que vencen antes de 2027 se espera que renueve el "
                     f"{c.fmt(100 * (d_.get('renov_esperada_2026') or 0), 0)} %. Subir la renovación es la palanca "
                     "más grande del crecimiento.</span>")
    c.pulso(items, "Pulso", "Lo que dice la composición de la base")
