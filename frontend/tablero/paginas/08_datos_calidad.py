# -*- coding: utf-8 -*-
"""08 · Datos y calidad: cargas, estado de las fuentes, diagnóstico y recomendaciones de captura."""
import pandas as pd
import plotly.express as px
import streamlit as st

import comun as c
import ia


@st.cache_data(show_spinner=False)
def plantilla_uso_xlsx(servicios: tuple) -> bytes:
    """Plantilla mensual para registrar el uso de los beneficios que no dejan registro automático."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    ws = wb.active
    ws.title = "Registros"
    enc = ["fecha", "empresa_id", "persona_id (opcional)", "servicio", "cantidad", "fuente", "detalle (opcional)"]
    ws.append(enc)
    for celda in ws[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="5B00D9")
    for col, ancho in zip("ABCDEFG", [12, 12, 20, 36, 10, 24, 40]):
        ws.column_dimensions[col].width = ancho
    lista = wb.create_sheet("Servicios")
    for sv in servicios:
        lista.append([sv])
    dv = DataValidation(type="list", formula1=f"=Servicios!$A$1:$A${len(servicios)}", allow_blank=False,
                        showErrorMessage=True, errorTitle="Servicio no válido", error="Elige un servicio de la lista")
    ws.add_data_validation(dv)
    dv.add("D2:D5000")
    ins = wb.create_sheet("Instrucciones", 0)
    for linea in [
        "Plantilla mensual de uso de beneficios · ACTHO",
        "",
        "Para qué: registrar el uso de los servicios que no dejan registro automático (boletín Actho en Marcha,",
        "GetAbstract y AI tip, Actho de Presencia, Actho Seguido, Sello ACTHO, Centro de Experiencias, Actho de Rumbo).",
        "",
        "Cómo:",
        "1. En la hoja Registros, una fila por uso: fecha (AAAA-MM-DD), código de la empresa (EMP-####),",
        "   servicio (elígelo de la lista), cantidad (p. ej. personas o aperturas) y la fuente del dato.",
        "2. Guarda el archivo como Datos/8. Uso de beneficios/uso_beneficios.xlsx (acumula los meses en el mismo archivo).",
        "3. Corre python3 setup.py o espera la carga diaria de Airflow: el tablero lo incluye en «Uso de beneficios».",
        "",
        "Las filas con empresa, servicio o fecha no reconocidos se excluyen y aparecen en el diagnóstico de calidad.",
        "",
        "Ejemplo de una fila: 2026-11-15 | EMP-0019 | (vacío) | Actho en Marcha (boletín) | 1 | Plataforma de correo | Abrió el boletín",
    ]:
        ins.append([linea])
    ins["A1"].font = Font(bold=True, size=14, color="5B00D9")
    ins.column_dimensions["A"].width = 110
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

c.encabezado("Datos y calidad", "De dónde vienen los datos, qué se corrigió y qué conviene cambiar en la captura",
             filtros=False)

calidad = c.tabla("reporte_calidad")
dic = c.tabla("diccionario_datos")
enc = c.encuestas()
emp = c.empresas()

k = c.fila(4)
c.kpi(k[0], "Hallazgos de calidad", c.fmt(len(calidad)), "Registrados por la limpieza automática", oscuro=True,
      chip_=("Morado", f"{c.fmt((calidad['accion'] == 'Revisar con ACTHO').sum())} para revisar con ACTHO"))
c.kpi(k[1], "Encuestas con empresa exacta", c.fmt(100 * (enc["tipo_cruce"] == "Exacto").mean(), 1, " %"),
      "Cruce por correo exacto", chip_=("Riesgo", f"{c.fmt((enc['tipo_cruce'] == 'Sin empresa').sum())} sin empresa"))
c.kpi(k[2], "Encuestas con evento", c.fmt(100 * enc["evento_id"].notna().mean(), 1, " %"),
      "Asignado por fecha y modalidad", chip_=("Alerta", "El formulario no pide el evento"))
c.kpi(k[3], "Empresas fuera del CRM", c.fmt((emp["en_crm"] == 0).sum()), "Participan sin registro en Zoho",
      chip_=("Alerta", "Unificar identidad"))

izq, der = st.columns([2.2, 1], gap="medium")
with izq:
    with c.tarjeta():
        c.cabeza("Cargas recientes", "Ejecuciones de Airflow y archivos procesados")
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
            c.cabeza("Último archivo de cada fuente", "Huella SHA-256 del archivo procesado")
            c.tabla_df(lotes, column_config={"fuente": "Fuente", "archivo": "Archivo", "huella": "Huella SHA-256",
                                             "cargado_en": st.column_config.DatetimeColumn("Cargado", format="DD/MM/YY HH:mm")})
    with c.tarjeta():
        c.cabeza("Diagnóstico de calidad", "Qué se encontró en los datos y cómo se resolvió")
        acc = st.multiselect("Acción", sorted(calidad["accion"].unique()), placeholder="Todas", key="cal_accion")
        vista = calidad[calidad["accion"].isin(acc)] if acc else calidad
        c.tabla_df(vista[["tabla", "campo", "problema", "regla_aplicada", "filas_afectadas", "accion"]].fillna("—"), height=330,
                   column_config={"tabla": st.column_config.TextColumn("Tabla", width="small"),
                                  "campo": st.column_config.TextColumn("Campo", width="small"),
                                  "problema": st.column_config.TextColumn("Problema", width="large"),
                                  "regla_aplicada": st.column_config.TextColumn("Regla", width="medium"),
                                  "filas_afectadas": st.column_config.NumberColumn("Filas", width="small"),
                                  "accion": st.column_config.TextColumn("Acción", width="medium")})
        c.descargar(calidad, "reporte_calidad.csv", "Descargar diagnóstico")
    with c.tarjeta():
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
                     title="Completitud del CRM", color_discrete_sequence=[c.C["morado"]])
        fig.update_traces(texttemplate="%{x:.0f} %", textposition="outside", cliponaxis=False,
                          textfont=dict(color=c.C["tinta"]), hovertemplate="%{y}: <b>%{x:.1f} %</b> sin dato<extra></extra>")
        fig.update_yaxes(title="")
        fig.update_xaxes(title="", range=[0, 112], showticklabels=False, showgrid=False)
        c.grafico(fig, 340, "% de empresas del CRM sin el dato")
        st.caption("Las fechas de expiración vacías son normales en membresías canceladas.")
    with c.tarjeta():
        c.cabeza("Definiciones de los indicadores", "Propuesta para acordar con ACTHO · el ícono ? de cada tarjeta muestra la misma definición")
        d = c.definiciones()
        if len(d):
            filas = [{"i": r.indicador, "d": r.definicion, "k": r.calculo or "", "f": r.fuente or "",
                      "e": c.chip("Acordada", "OK") if r.estado == "Acordada" else c.chip("Por validar", "Alerta")}
                     for r in d.itertuples()]
            c.tabla_html(filas, [("Indicador", "i", "texto"), ("Definición", ("d", "k"), "texto"), ("Fuente", "f", "texto"),
                                 ("Estado", "e", "html")])
            c.descargar(d.drop(columns=["orden"]), "definiciones_indicadores_actho.csv", "Descargar para validar con ACTHO")
            st.caption("Cuando ACTHO acuerde una definición, se marca como 'Acordada' en sql/vistas_dashboard.sql "
                       "(tabla actho.definicion_indicador) y queda así en todo el tablero.")

    with c.tarjeta():
        c.cabeza("Conciliación con Zoho", "Por qué el informe de membresías de Zoho y el tablero muestran cifras distintas de activos")
        if c.existe("actho.v_conciliacion_activos"):
            conc = c.tabla("v_conciliacion_activos")
            c.tabla_html([{"c": r.concepto, "n": c.fmt(r.cantidad)} for r in conc.itertuples()],
                         [("Concepto", "c", "texto"), ("Cantidad", "n", "num")])
            det = c.tabla("v_conciliacion_detalle")
            partes = " · ".join(f"{r.estado_membresia}: <b>{c.fmt(r.registros_zoho_activo)}</b>" for r in det.itertuples())
            c.hallazgo(f"Los registros con «Estado = Activo» en Zoho se reparten así según su estado de membresía: {partes}.")
            malos = det[det["estado_membresia"].isin(["Expirado", "Cancelado", "Inactivo"])]["registros_zoho_activo"].sum()
            if malos:
                c.hallazgo(f"<b>{c.fmt(malos)} registros</b> figuran como activos en Zoho pero su membresía está expirada o cancelada: "
                           "conviene corregirlos en el CRM.")

    with c.tarjeta():
        c.cabeza("Cobertura del uso de beneficios", "Qué servicios de la oferta 2027 ya dejan registro y cuántos usos hay")
        cat = c.catalogo()
        uso = c.uso_beneficios()
        if len(cat):
            n_uso = uso.groupby("servicio_id").agg(usos=("cantidad", "sum"), empresas=("empresa_id", "nunique"))
            filas = []
            for r in cat.itertuples():
                tiene = r.servicio_id in n_uso.index
                filas.append({"s": r.servicio, "l": r.linea_servicio, "f": r.fuente_dato,
                              "u": c.fmt(n_uso.loc[r.servicio_id, "usos"]) if tiene else "0",
                              "e": c.fmt(n_uso.loc[r.servicio_id, "empresas"]) if tiene else "0",
                              "x": c.chip("Con datos", "OK") if tiene else (c.chip("Sin fuente", "Riesgo") if r.fuente_dato == "Sin registro"
                                                                         else c.chip("Falta cargar", "Alerta"))})
            c.tabla_html(filas, [("Servicio", ("s", "l"), "texto"), ("Fuente prevista", "f", "texto"), ("Usos", "u", "num"),
                                 ("Empresas", "e", "num"), ("Estado", "x", "html")])
            st.download_button("Descargar plantilla mensual de uso (Excel)",
                               plantilla_uso_xlsx(tuple(cat[cat["fuente_dato"].isin(["Plantilla mensual", "Asistencia", "CRM y asistencia"])]["servicio"])),
                               file_name="uso_beneficios.xlsx", icon=":material/download:", key="dl_plantilla",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               help="Llénala cada mes y guárdala en Datos/8. Uso de beneficios/uso_beneficios.xlsx")

    with c.tarjeta("Modelos de IA en palabras simples",
                   "✦ Qué pregunta responde cada modelo, cómo llega a su opinión, qué tan confiable es y cuándo dudar",
                   ayuda=ia.desc("general")):
        fichas = ia.t("modelo")
        if fichas.empty:
            ia.sin_modelos()
        else:
            ent = pd.Timestamp(fichas["entrenado"].iloc[0])
            st.caption(f"Revisados por última vez el {ent:%d/%m/%Y} a las {ent:%H:%M} con datos al "
                       f"{c.fecha_txt(fichas['fecha_corte'].iloc[0])}. Se vuelven a entrenar solos cada vez que llegan datos nuevos. "
                       "Ninguno decide por el equipo: ordenan y explican para que la decisión sea más informada.")
            filas = []
            for f in fichas.itertuples():
                ex = ia.explicacion(f.modelo)
                activo = f.estado == "Activo"
                filas.append({"n": f.nombre, "q": ex.get("pregunta", f.objetivo), "c": ex.get("confianza") or "—",
                              "e": c.chip("Activo" if activo else "En espera", "OK" if activo else "Alerta"),
                              "p": f.pestanas})
            c.tabla_html(filas, [("Modelo", ("n", "q"), "texto"), ("Qué tan confiable es", "c", "texto"),
                                 ("Dónde se ve", "p", "texto"), ("Estado", "e", "html")])
            st.markdown("**Ábrelo para ver cómo piensa cada uno**")
            for f in fichas.itertuples():
                ex = ia.explicacion(f.modelo)
                with st.expander(f"✦ {f.nombre}"):
                    if ex.get("pregunta"):
                        st.markdown(
                            f"**Qué pregunta responde.** {ex['pregunta']}\n\n"
                            f"**En qué se fija.** {ex['mira']}\n\n"
                            f"**Cómo llega a su opinión.** {ex['decide']}\n\n"
                            f"**Qué tan confiable es.** {ex['confianza'] or 'Aún sin medir.'}\n\n"
                            f"**Tenlo en cuenta para.** {ex['usar']}\n\n"
                            f"**Duda de él cuando.** {ex['dudar']}")
                    else:
                        st.markdown(f"**Para qué.** {f.objetivo}\n\n**Estado.** {f.estado}")
                    st.markdown(f'<div class="nota-ia" style="margin-top:.6rem"><b>Detalle técnico</b> · {c._e(f.metodo)} · '
                                f'Datos: {c._e(f.datos)} · {c._e(f.metrica)} = {ia._num(f.valor, 3)}. {c._e(f.linea_base)} '
                                f'· Límites: {c._e(f.limitaciones)}</div>', unsafe_allow_html=True)

    ident = ia.t("identidad")
    if len(ident):
        with c.tarjeta("Cruces por revisar", "✦ Personas y empresas que el modelo de identidad sugiere corregir",
                       ayuda=ia.desc("identidad")):
            k = c.fila(2)
            c.kpi(k[0], "Encuestas con empresa sugerida", c.fmt(ident["respuesta_id"].notna().sum()),
                  "La empresa se completó o corrigió con la asistencia de esa persona", chip_=("IA", "Identidad"),
                  ayuda_=ia.desc("identidad"))
            c.kpi(k[1], "Personas en varias empresas", c.fmt(ident["respuesta_id"].isna().sum()),
                  "Cambio de empleo o error de digitación: revisar en Zoho")
            c.tabla_df(ident.rename(columns={"respuesta_id": "Respuesta", "persona_id": "Persona",
                                             "empresa_actual": "Empresa(s) actual(es)", "empresa_sugerida": "Sugerida",
                                             "tipo_cruce": "Cruce", "motivo": "Motivo", "confianza": "Confianza"}), height=260)
            c.descargar(ident, "cruces_por_revisar.csv", "Exportar cruces por revisar")
            ia.nota("identidad")

    with st.expander("Diccionario de datos"):
        c.tabla_df(dic, height=400)

with der, c.panel():
    with c.tarjeta():
        cr = enc["tipo_cruce"].value_counts().reset_index()
        cr.columns = ["Cruce", "Respuestas"]
        fig = px.pie(cr, names="Cruce", values="Respuestas", hole=0.62, title="Identificación en encuestas",
                     color_discrete_sequence=[c.C["morado"], c.C["cian_graf"], c.C["naranja"], c.C["lavanda_graf"]])
        fig.update_traces(textinfo="percent", insidetextorientation="horizontal",
                          textfont=dict(size=13, color=["#FFFFFF", "#FFFFFF", c.C["tinta"], c.C["tinta"]]),
                          hovertemplate="%{label}: <b>%{value}</b> respuestas (%{percent})<extra></extra>",
                          marker=dict(line=dict(color="#FFFFFF", width=2)))
        c.grafico(fig, 260, "Cómo se asignó la empresa a cada respuesta")
    c.pulso([
        "<b>Pedir NIT y código de evento en cada encuesta</b><br><span>Hoy 142 respuestas no tienen empresa y "
        "el evento se infiere por la fecha.</span>",
        "<b>Registrar el uso de los beneficios digitales</b><br><span>Boletín, GetAbstract, Presencia, podcast y Sello no dejan "
        "rastro: la plantilla mensual de esta página los suma al indicador de uso.</span>",
        "<b>Activar la encuesta de 90 días</b><br><span>Es la única fuente del NPS de ACTHO y de la intención de renovar; el "
        "tablero ya está listo para recibirla.</span>",
        "<b>Guardar el motivo del retiro en Zoho</b><br><span>Con una lista cerrada, para medir por qué no renuevan.</span>",
        "<b>No sobrescribir la expiración al renovar</b><br><span>Registrar cada renovación como un movimiento; "
        "mientras tanto, la foto mensual de Airflow guarda el historial.</span>",
        "<b>Un solo formato de asistencia</b><br><span>Mismas columnas en todas las hojas y NIT sin dígito de "
        "verificación.</span>",
        "<b>Listas cerradas en el CRM</b><br><span>Ciudad, sector y categoría sin texto libre, para evitar "
        "variantes y tildes dañadas.</span>",
    ], titulo="Recomendaciones de captura", lema="Para que el tablero se mantenga al día")
