# -*- coding: utf-8 -*-
"""
Constructor de gráficas del Dashboard: cada persona arma sus propias consultas sin programar.

Se elige la fuente (empresas, asistencias, encuestas o uso de beneficios), la dimensión, un desglose
opcional, la medida y el tipo de gráfico. Las gráficas respetan los filtros del tablero y, como las demás,
filtran todo el tablero con un clic. Se guardan en la sesión y se pueden descargar o cargar como archivo.
"""
from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st

import comun as c

DIM_EMPRESA = {"nivel_2027": "Nivel 2027", "tipo_membresia": "Tipo de afiliado", "sector": "Sector", "ciudad": "Ciudad",
               "tamano_empresa": "Tamaño", "ejecutiva": "Ejecutiva", "riesgo": "Nivel de riesgo",
               "rango_vencimiento": "Vencimiento", "mes_venc": "Mes de vencimiento", "estado_membresia": "Estado",
               "region": "Región", "renovacion_aprox": "Renovación", "mes_alta": "Mes de afiliación"}
DIM_ASIST = {"anio_mes": "Mes", "linea_2027": "Línea 2027", "modalidad": "Modalidad", "nivel_cargo": "Nivel de cargo",
             "condicion_empresa": "Afiliada o no", "evento": "Evento", "costo": "Con o sin costo",
             "nivel_2027": "Nivel 2027", "sector": "Sector", "ciudad": "Ciudad", "ejecutiva": "Ejecutiva"}
DIM_ENC = {"anio_mes": "Mes", "origen_encuesta": "Formulario", "modalidad": "Modalidad", "nps_categoria": "Categoría NPS",
           "tipo_cruce": "Identificación de la empresa", "linea_2027": "Línea 2027", "nivel_2027": "Nivel 2027",
           "sector": "Sector", "ciudad": "Ciudad", "ejecutiva": "Ejecutiva", "condicion_empresa": "Afiliada o no"}
DIM_USO = {"servicio": "Beneficio", "linea_servicio": "Línea del beneficio", "fuente": "Fuente del dato",
           "anio_mes": "Mes", "nivel_2027": "Nivel 2027", "sector": "Sector", "ciudad": "Ciudad", "ejecutiva": "Ejecutiva",
           "condicion_empresa": "Afiliada o no"}

MEDIDAS = {
    "Empresas vigentes": ["Empresas", "% que usa beneficios (90 días)", "% con riesgo alto", "Puntaje de riesgo promedio",
                          "Satisfacción promedio", "Asistencias en 12 meses (promedio)", "Aprovechamiento del nivel (%)"],
    "Empresas del CRM": ["Empresas", "% vigentes", "Renovaron (aprox.)", "No renovaron (aprox.)"],
    "Asistencias": ["Inscripciones", "Personas distintas", "Empresas distintas", "Eventos distintos"],
    "Encuestas": ["Respuestas", "Satisfacción promedio", "NPS", "Empresas distintas"],
    "Uso de beneficios": ["Usos", "Empresas distintas", "Beneficios distintos"],
}
DIMS = {"Empresas vigentes": DIM_EMPRESA, "Empresas del CRM": DIM_EMPRESA, "Asistencias": DIM_ASIST,
        "Encuestas": DIM_ENC, "Uso de beneficios": DIM_USO}
TIPOS = ["Barras verticales", "Barras horizontales", "Líneas", "Anillo (sin filtro por clic)"]
MESES_DIM = {"anio_mes", "mes_venc", "mes_alta"}


def _xf_de(dim: str) -> str | None:
    """Dimensión del filtro cruzado que corresponde a una columna (el nivel de riesgo se guarda como semáforo)."""
    if dim == "riesgo":
        return "semaforo"
    return dim if dim in c.XF_DIMS else None


def _datos(fuente: str, excluir: tuple) -> pd.DataFrame:
    e, a, r = c.datos(excluir=excluir)
    if fuente == "Empresas vigentes":
        return e[e["es_vigente"] == 1]
    if fuente == "Empresas del CRM":
        return e[e["en_crm"] == 1]
    if fuente == "Asistencias":
        return a
    if fuente == "Encuestas":
        return r.assign(satisfaccion=r["satisfaccion_general"].fillna(r["satisfaccion_prom"]))
    return c.datos_uso(excluir=excluir)


def _medir(df: pd.DataFrame, medida: str) -> float:
    if df.empty:
        return 0
    m = medida
    if m in ("Empresas", "Respuestas", "Inscripciones"):
        return len(df)
    if m == "Usos":
        return df["cantidad"].sum()
    if m == "Empresas distintas":
        return df["empresa_id"].nunique()
    if m == "Personas distintas":
        return df["persona_id"].nunique()
    if m == "Eventos distintos":
        return df["evento_id"].nunique()
    if m == "Beneficios distintos":
        return df["servicio"].nunique()
    if m == "% que usa beneficios (90 días)":
        return 100 * df["participa_en_ventana"].astype(bool).mean()
    if m == "% con riesgo alto":
        return 100 * (df["semaforo"] == "Rojo").mean()
    if m == "Puntaje de riesgo promedio":
        return df["puntaje_riesgo"].mean()
    if m == "Satisfacción promedio":
        return (df["satisfaccion"] if "satisfaccion" in df else df["satisfaccion_promedio"]).mean()
    if m == "Asistencias en 12 meses (promedio)":
        return df["inscripciones_12m"].mean()
    if m == "Aprovechamiento del nivel (%)":
        return df["pct_aprovechamiento"].mean()
    if m == "% vigentes":
        return 100 * df["es_vigente"].mean()
    if m == "Renovaron (aprox.)":
        return (df["renovacion_aprox"] == "Renovó").sum()
    if m == "No renovaron (aprox.)":
        return (df["renovacion_aprox"] == "No renovó").sum()
    if m == "NPS":
        n = df["nps_puntaje"].notna().sum()
        return 100 * ((df["nps_categoria"] == "Promotor").sum() - (df["nps_categoria"] == "Detractor").sum()) / n if n else None
    return len(df)


def calcular(g: dict) -> pd.DataFrame:
    dims = [d for d in [g["dim"], g.get("color")] if d]
    excluir = tuple(x for x in (_xf_de(d) for d in dims) if x)
    df = _datos(g["fuente"], excluir).copy()
    for d in dims:
        df[d] = df[d].fillna("Sin dato").astype(str)
    if "riesgo" in dims:
        df["semaforo"] = df["semaforo"].fillna("Sin dato")
    filas = []
    for clave, sub in df.groupby(dims, dropna=False):
        clave = clave if isinstance(clave, tuple) else (clave,)
        fila = dict(zip(dims, clave))
        fila["valor"] = _medir(sub, g["medida"])
        if "riesgo" in dims:
            fila["semaforo"] = sub["semaforo"].iloc[0]
        filas.append(fila)
    res = pd.DataFrame(filas)
    if res.empty:
        return res
    res = res.dropna(subset=["valor"])
    if g["dim"] in MESES_DIM:
        res = res.sort_values(g["dim"])
    else:
        orden = res.groupby(g["dim"])["valor"].sum().sort_values(ascending=False)
        top = int(g.get("top") or 0)
        if top:
            res = res[res[g["dim"]].isin(orden.index[:top])]
        res[g["dim"]] = pd.Categorical(res[g["dim"]], categories=list(orden.index), ordered=True)
        res = res.sort_values(g["dim"])
        res[g["dim"]] = res[g["dim"]].astype(str)
    return res


def _etiqueta(dim, v):
    return c.anio_mes_txt(v) if dim in MESES_DIM else (c.riesgo_txt(v) if dim == "riesgo" else v)


def dibujar(g: dict, i: int):
    res = calcular(g)
    etiquetas = {**DIMS[g["fuente"]]}
    titulo = f"{g['medida']} por {etiquetas[g['dim']].lower()}" + (f" y {etiquetas[g['color']].lower()}" if g.get("color") else "")
    sub = f"{g['fuente']} · con los filtros del tablero"
    if res.empty:
        c.cabeza(titulo, sub)
        st.info("No hay datos con los filtros actuales.")
        return res
    dim, color = g["dim"], g.get("color")
    res["Etiqueta"] = [_etiqueta(dim, v) for v in res[dim]]
    if g["tipo"] != "Barras horizontales":
        res["Etiqueta"] = [c.partir(t, 14) if isinstance(t, str) else t for t in res["Etiqueta"]]
    else:
        res["Etiqueta"] = [c.partir(t, 26) if isinstance(t, str) else t for t in res["Etiqueta"]]
    if color:
        res["Desglose"] = [_etiqueta(color, v) for v in res[color]]
    # customdata con los valores crudos (para el filtro cruzado)
    xf_dims, cd = [], []
    for d in [dim, color]:
        x = _xf_de(d) if d else None
        if x:
            xf_dims.append(x)
            cd.append("semaforo" if d == "riesgo" else d)
    mapa = c.RIESGO if color == "riesgo" else (c.CONDICION if color == "condicion_empresa" else
                                               c.NPS_COLOR if color == "nps_categoria" else
                                               c.LINEA if color in ("linea_2027", "linea_servicio") else
                                               c.MODALIDAD if color == "modalidad" else None)
    comunes = dict(custom_data=cd or None, color="Desglose" if color else None,
                   color_discrete_map=mapa if color else None,
                   color_discrete_sequence=c.SECUENCIA if color else [c.C["morado"]], title=titulo)
    comunes = {k: v for k, v in comunes.items() if v is not None}
    pct = g["medida"].startswith("%") or "(%)" in g["medida"]
    fmt_v = ".1f" if pct or "promedio" in g["medida"].lower() or g["medida"] == "NPS" else ",.0f"
    tipo = g["tipo"]
    if tipo == "Barras horizontales":
        fig = px.bar(res, x="valor", y="Etiqueta", orientation="h", **comunes)
        fig.update_yaxes(title="", categoryorder="array", categoryarray=list(dict.fromkeys(res["Etiqueta"]))[::-1])
        fig.update_xaxes(title=g["medida"])
        hov = "%{y}: <b>%{x:" + fmt_v + "}</b><extra></extra>"
    elif tipo == "Líneas":
        fig = px.line(res, x="Etiqueta", y="valor", markers=True, **comunes)
        fig.update_traces(line_width=3, marker_size=8)
        fig.update_xaxes(title="")
        fig.update_yaxes(title=g["medida"])
        hov = "%{x}: <b>%{y:" + fmt_v + "}</b><extra></extra>"
    elif tipo.startswith("Anillo"):
        agg = res.groupby("Etiqueta", sort=False)["valor"].sum().reset_index()
        fig = px.pie(agg, names="Etiqueta", values="valor", hole=.6, title=titulo,
                     color_discrete_sequence=c.SECUENCIA)
        fig.update_traces(textinfo="percent", textfont=dict(color="#FFFFFF"), sort=False,
                          marker=dict(line=dict(color="#FFFFFF", width=2)))
        c.grafico(fig, 320, sub)
        return res
    else:
        fig = px.bar(res, x="Etiqueta", y="valor", **comunes)
        fig.update_xaxes(title="", tickangle=0 if res["Etiqueta"].nunique() <= 10 else -35,
                         categoryorder="array", categoryarray=list(dict.fromkeys(res["Etiqueta"])))
        fig.update_yaxes(title=g["medida"])
        hov = "%{x}: <b>%{y:" + fmt_v + "}</b><extra></extra>"
    fig.update_traces(hovertemplate=hov)
    c.grafico(fig, 320, sub + (" · clic para filtrar" if xf_dims else ""), dims=xf_dims or None, clave=f"usr{i}")
    return res


def constructor():
    """Sección 'Crea tus gráficas' del Dashboard."""
    graficas = st.session_state.setdefault("graficas_usuario", [])
    with c.tarjeta():
        c.cabeza("Crea tus gráficas", "Elige qué contar y cómo verlo; respeta los filtros y se filtra con un clic")
        f1, f2, f3, f4, f5, f6 = st.columns([1.2, 1.2, 1.2, 1.4, 1.2, .8])
        fuente = f1.selectbox("Datos", list(MEDIDAS), key="cg_fuente")
        dims = DIMS[fuente]
        dim = f2.selectbox("Agrupar por", list(dims), format_func=dims.get, key=f"cg_dim_{fuente}")
        color = f3.selectbox("Desglosar por", [None] + [d for d in dims if d != dim],
                             format_func=lambda d: "Sin desglose" if d is None else dims[d], key=f"cg_color_{fuente}")
        medida = f4.selectbox("Medida", MEDIDAS[fuente], key=f"cg_medida_{fuente}")
        tipo = f5.selectbox("Tipo", TIPOS, key="cg_tipo")
        top = f6.selectbox("Mostrar", [10, 5, 15, 25, 0], format_func=lambda n: "Todos" if n == 0 else f"Top {n}",
                           key="cg_top", help="Cuántas categorías mostrar (no aplica a meses)")
        b1, b2, b3, _ = st.columns([1.3, 1.5, 1.8, 2.4])
        if b1.button("Agregar gráfica", type="primary", icon=":material/add_chart:", key="cg_agregar"):
            graficas.append(dict(fuente=fuente, dim=dim, color=color, medida=medida, tipo=tipo, top=top))
            st.rerun()
        if graficas:
            b2.download_button("Guardar mis gráficas", json.dumps(graficas, ensure_ascii=False, indent=2).encode("utf-8"),
                               file_name="mis_graficas_actho.json", mime="application/json", icon=":material/download:",
                               key="cg_guardar")
        with b3.popover("Cargar gráficas guardadas", icon=":material/upload:"):
            archivo = st.file_uploader("Archivo de gráficas (.json)", type=["json"], key="cg_cargar")
            if archivo is not None and st.button("Cargar", key="cg_cargar_btn"):
                try:
                    nuevas = json.loads(archivo.getvalue().decode("utf-8"))
                    validas = [g for g in nuevas if isinstance(g, dict) and g.get("fuente") in MEDIDAS
                               and g.get("dim") in DIMS[g["fuente"]] and g.get("medida") in MEDIDAS[g["fuente"]]]
                    graficas.extend(validas)
                    st.rerun()
                except (ValueError, KeyError):
                    st.error("El archivo no tiene el formato de gráficas del tablero.")
        if not graficas:
            st.caption("Ejemplos: «Empresas vigentes · Sector · % con riesgo alto», «Asistencias · Mes · desglose por "
                       "Línea 2027», «Uso de beneficios · Beneficio · desglose por Fuente del dato».")

    for fila in range(0, len(graficas), 2):
        cols = st.columns(2)
        for j, i in enumerate(range(fila, min(fila + 2, len(graficas)))):
            g = graficas[i]
            with cols[j], c.tarjeta():
                res = dibujar(g, i)
                q1, q2, _ = st.columns([1, 1.25, 1.5])
                if q1.button("Quitar", key=f"cg_quitar_{i}", icon=":material/delete:"):
                    graficas.pop(i)
                    st.rerun()
                if res is not None and len(res):
                    q2.download_button("CSV", res.drop(columns=["Etiqueta"], errors="ignore").to_csv(index=False).encode("utf-8-sig"),
                                       file_name=f"grafica_{i + 1}.csv", mime="text/csv", key=f"cg_csv_{i}",
                                       icon=":material/table:")
