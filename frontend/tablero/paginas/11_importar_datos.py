# -*- coding: utf-8 -*-
"""11 · Importar datos: elegir el tipo de dato, descargar la plantilla de Excel (mismo formato de los archivos
originales), subirla llena, revisar lo que encontró la limpieza y enviarla al pipeline (Airflow o local)."""
import hashlib
import sys

import pandas as pd
import streamlit as st

import comun as c

sys.path.insert(0, str(c.RAIZ / "src"))
import importaciones as imp  # noqa: E402

c.encabezado("Importar datos", "Sube datos nuevos con las plantillas de Excel: pasan por la misma limpieza y llegan "
                               "al tablero", filtros=False)

SQL_ESTADO = """SELECT id, inicio, fin, estado FROM ingesta.ejecucion ORDER BY id DESC LIMIT 1"""


@st.cache_data(ttl=600, show_spinner="Armando la plantilla…")
def _plantilla(tipo: str) -> bytes:
    return imp.plantilla(tipo)


@st.cache_data(ttl=600, show_spinner=False)
def _empresas_validas() -> frozenset:
    return frozenset(c.consulta("SELECT empresa_id FROM actho.dim_empresa")["empresa_id"])


@st.cache_data(ttl=900, show_spinner="Revisando el archivo con las reglas de limpieza…", max_entries=8)
def _validar(tipo: str, huella: str, contenido: bytes, corte: str) -> dict:
    return imp.validar(tipo, contenido, corte=corte, empresas_validas=set(_empresas_validas()))


def _procesando() -> bool:
    try:
        e = c.consulta(SQL_ESTADO)
    except Exception:  # noqa: BLE001
        return False
    return bool(len(e)) and e.iloc[0]["estado"] == "en_curso" and \
        (pd.Timestamp.now() - pd.Timestamp(e.iloc[0]["inicio"])) < pd.Timedelta(minutes=30)


# ──────────────────────────────────────────────────────────────────────────────
# 1. Tipo de dato
# ──────────────────────────────────────────────────────────────────────────────
izq, der = c.columnas([1.15, 1], "pareja", gap="medium")
with izq, c.tarjeta("1. ¿Qué datos vas a subir?", "Cada tipo tiene su plantilla con el mismo formato que ACTHO ya usa"):
    nombres = {t: d["nombre"] for t, d in imp.TIPOS.items()}
    tipo = st.radio("Tipo de datos", list(nombres), format_func=nombres.get, key="imp_tipo",
                    label_visibility="collapsed")
    d = imp.TIPOS[tipo]
    modo = ("Se suma a lo que ya hay" if d["modo"] == "agregar" else "Reemplaza la base completa (queda un respaldo)")
    st.markdown(f'<div class="hallazgo"><div>{c.chip(modo, "Morado" if d["modo"] == "agregar" else "Alerta")} '
                f'{c._e(d["descripcion"])}</div></div>', unsafe_allow_html=True)

with der, c.tarjeta("2. Descarga la plantilla", "Llénala en Excel sin cambiar hojas ni encabezados"):
    try:
        contenido_plantilla = _plantilla(tipo)
        st.download_button(f"Descargar plantilla · {d['nombre']}", contenido_plantilla,
                           file_name=f"Plantilla_ACTHO_{tipo}.xlsx", icon=":material/download:", type="primary",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key=f"plantilla_{tipo}", **c.ancho(st.download_button))
    except FileNotFoundError as e:
        st.error(str(e))
    st.markdown(
        '<ul style="font-size:.84rem;margin:.6rem 0 0;padding-left:1.1rem;line-height:1.55">'
        '<li>Tiene las mismas hojas, filas de título y columnas que el archivo que entregó ACTHO, sin datos.</li>'
        '<li>La primera hoja, <b>Instrucciones</b>, explica cómo llenarla; donde hay listas desplegables, elige de ellas.</li>'
        '<li>Empresas y personas van con su código (EMP-0001, P-00001).</li>'
        '<li>Puedes pegar una exportación de la herramienta de origen si respeta las columnas.</li></ul>',
        unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# 3. Subir (Excel o a mano), revisar y confirmar
# ──────────────────────────────────────────────────────────────────────────────
def revisar_y_confirmar(contenido: bytes, nombre: str, origen: str):
    """Muestra lo que encontró la limpieza y, si todo está bien, guarda y manda a procesar."""
    huella = hashlib.sha256(contenido).hexdigest()
    r = _validar(tipo, huella, contenido, str(c.parametros()["fecha_corte"]))
    if r["resumen"]:
        k = c.fila(len(r["resumen"]))
        for i, (et, v) in enumerate(r["resumen"]):
            c.kpi(k[i], et, c.fmt(v) if isinstance(v, (int, float)) else (v or "—"), "")
    for e in r["errores"]:
        st.error(e, icon=":material/error:")
    for a in r["advertencias"][:12]:
        st.warning(a, icon=":material/warning:")
    if len(r["advertencias"]) > 12:
        st.caption(f"… y {len(r['advertencias']) - 12} advertencias más.")
    if r["ok"]:
        st.success("Los datos tienen la estructura correcta y la limpieza los puede leer.", icon=":material/check_circle:")
    hall = r.get("hallazgos")
    if hall is not None and len(hall):
        with st.expander(f"Qué corrigió o excluyó la limpieza ({len(hall)})"):
            c.tabla_df(hall.rename(columns={"tabla": "Tabla", "campo": "Campo", "problema": "Qué encontró",
                                            "regla_aplicada": "Qué hace", "filas_afectadas": "Filas",
                                            "accion": "Resultado"}), height=260)
    if len(r["vista"]):
        with st.expander(f"Vista previa de los datos limpios ({len(r['vista'])} primeras filas)"):
            c.tabla_df(r["vista"], height=260)
    en_curso = _procesando()
    confirma = True
    if d["modo"] == "reemplazar" and r["ok"]:
        confirma = st.checkbox("Entiendo que este archivo reemplaza la base completa (la anterior queda como respaldo).",
                               key=f"imp_conf_{huella[:8]}")
    if en_curso:
        st.info("Hay un procesamiento en curso. Espera a que termine (abajo ves el estado) para importar más datos.",
                icon=":material/hourglass_top:")
    if st.button("Importar y procesar", type="primary", icon=":material/upload:",
                 disabled=not (r["ok"] and confirma) or en_curso, key=f"imp_confirmar_{origen}"):
        sesion = st.session_state.get("sesion") or {}
        usuario = sesion.get("usuario") or sesion.get("nombre")
        try:
            destino = imp.guardar(tipo, contenido, nombre, usuario)
            quien, detalle = imp.procesar({"origen": "importacion", "tipo": tipo})
            import psycopg
            with psycopg.connect(c._url(), autocommit=True) as conn:
                imp.registrar(conn, tipo, usuario, nombre, destino, r["filas"], quien, detalle or None)
            st.session_state["imp_ver"] += 1
            st.session_state.pop("imp_manual", None)
            st.session_state["imp_mensaje"] = (quien, detalle, d["nombre"])
            c.consulta.clear()
            st.rerun()
        except Exception as ex:  # noqa: BLE001
            st.error(f"No se pudo importar: {ex}")


TIPO_COLUMNA = {"texto": lambda et, ops: st.column_config.TextColumn(et),
                "numero": lambda et, ops: st.column_config.NumberColumn(et, step=1),
                "fecha": lambda et, ops: st.column_config.DateColumn(et, format="DD/MM/YYYY"),
                "lista": lambda et, ops: st.column_config.SelectboxColumn(et, options=[""] + list(ops))}

with c.tarjeta("3. Carga los datos", "Sube la plantilla llena o escribe los datos aquí; en ambos casos se revisan con "
                                     "las mismas reglas de limpieza antes de guardarlos"):
    st.session_state.setdefault("imp_ver", 0)
    t_excel, t_mano = st.tabs([":material/upload_file: Subir un archivo de Excel", ":material/edit_note: Escribir los datos aquí"])
    with t_excel:
        archivo = st.file_uploader("Archivo de Excel (.xlsx)", type=["xlsx"],
                                   key=f"imp_archivo_{tipo}_{st.session_state['imp_ver']}",
                                   help="Hasta 200 MB. Solo se guarda cuando confirmas.")
        if archivo is not None:
            revisar_y_confirmar(archivo.getvalue(), archivo.name, "excel")
    with t_mano:
        if tipo not in imp.MANUAL:
            st.info(f"«{d['nombre']}» reemplaza la base completa, así que se sube como archivo (pestaña de al lado). "
                    "Para corregir una sola empresa, hazlo en Zoho CRM y luego sube la exportación.",
                    icon=":material/info:")
        else:
            evento = None
            if tipo == "asistencia":
                eventos = c.tabla("dim_evento").sort_values("fecha", ascending=False)
                etiquetas = ["Evento nuevo"] + [f"{pd.Timestamp(f):%d/%m/%Y} · {n}" for f, n in zip(eventos["fecha"], eventos["nombre"])]
                cual = st.selectbox("¿A qué evento pertenecen los inscritos?", etiquetas, key="imp_ev_sel",
                                    help="Elige un evento que ya existe para sumarle inscritos, o crea uno nuevo.")
                base = {} if cual == "Evento nuevo" else eventos.iloc[etiquetas.index(cual) - 1].to_dict()
                e1, e2 = c.columnas([2.2, 1], "controles")
                nombre_ev = e1.text_input("Nombre del evento", base.get("nombre", ""), key=f"imp_ev_nombre_{cual}",
                                          disabled=cual != "Evento nuevo")
                fecha_ev = e2.date_input("Fecha", pd.Timestamp(base["fecha"]).date() if base.get("fecha") is not None
                                         else pd.Timestamp.today().date(), format="DD/MM/YYYY",
                                         key=f"imp_ev_fecha_{cual}", disabled=cual != "Evento nuevo")
                e3, e4, e5 = c.columnas([1, 1, 1], "controles")
                sel = {}
                for col_, campo, et in ((e3, "linea_2027", "Línea 2027"), (e4, "experiencia", "Experiencia"),
                                        (e5, "modalidad", "Modalidad")):
                    ops = imp.opciones_manual(tipo, campo)
                    if base.get(campo) and base[campo] not in ops:
                        ops = [base[campo]] + ops
                    sel[campo] = col_.selectbox(et, ops, index=ops.index(base[campo]) if base.get(campo) in ops else 0,
                                                key=f"imp_ev_{campo}_{cual}", disabled=cual != "Evento nuevo")
                evento = {"nombre": nombre_ev, "fecha": pd.Timestamp(fecha_ev), **sel}
                st.markdown("**Inscritos** · una fila por persona")
            campos = imp.MANUAL[tipo]
            n_filas = 3
            vacia = pd.DataFrame(index=range(n_filas))
            for c_, _, clase, _, _ in campos:   # texto en blanco ("") para que las celdas no digan "None"
                vacia[c_] = (pd.Series([pd.NaT] * n_filas, dtype="datetime64[ns]") if clase == "fecha" else
                             pd.Series([None] * n_filas, dtype="Float64") if clase == "numero" else
                             pd.Series([""] * n_filas, dtype="object"))
            config = {c_: TIPO_COLUMNA[clase](et, imp.opciones_manual(tipo, c_)) for c_, et, clase, _, _ in campos}
            editado = st.data_editor(vacia, column_config=config, num_rows="dynamic", hide_index=True,
                                     key=f"imp_editor_{tipo}_{st.session_state['imp_ver']}", **c.ancho(st.data_editor))
            st.caption("Agrega filas con el «+» al final de la tabla. Empresas y personas van con su código (EMP-0001, "
                       "P-00001). Las filas vacías se ignoran.")
            if st.button("Revisar datos", icon=":material/fact_check:", key="imp_revisar_manual",
                         disabled=tipo == "asistencia" and not (evento or {}).get("nombre")):
                st.session_state["imp_manual"] = (tipo, imp.llenar_plantilla(tipo, editado, evento))
            manual = st.session_state.get("imp_manual")
            if manual and manual[0] == tipo:
                revisar_y_confirmar(manual[1], f"ingreso_manual_{tipo}.xlsx", "manual")

if st.session_state.get("imp_mensaje"):
    quien, detalle, nombre = st.session_state.pop("imp_mensaje")
    st.toast(f"{nombre}: archivo recibido y enviado a procesar", icon=":material/check_circle:")
    st.success(f"Archivo recibido. Lo está procesando **{quien}**: limpieza → validación → carga a PostgreSQL → "
               "modelos de IA. En uno o dos minutos los datos aparecen en el tablero."
               + (f" ({detalle})" if detalle and quien == "Airflow" else ""), icon=":material/rocket_launch:")

# ──────────────────────────────────────────────────────────────────────────────
# 4. Historial y estado
# ──────────────────────────────────────────────────────────────────────────────
with c.tarjeta("Importaciones y procesamiento", "Lo que se ha subido desde el tablero y en qué va"):
    b1, b2 = st.columns([1, 3], vertical_alignment="center")
    if b1.button("Actualizar estado", icon=":material/refresh:", key="imp_refrescar"):
        st.cache_data.clear()
        st.rerun()
    try:
        ej = c.consulta(SQL_ESTADO)
    except Exception:  # noqa: BLE001
        ej = pd.DataFrame()
    if len(ej):
        e = ej.iloc[0]
        txt = {"en_curso": ("Alerta", "Procesando ahora"), "procesado": ("OK", "Última carga completa"),
               "sin_cambios": ("Neutro", "Última revisión: sin cambios"),
               "con_errores": ("Riesgo", "La última carga tuvo errores")}.get(e["estado"], ("Neutro", e["estado"]))
        b2.markdown(f'{c.chip(txt[1], txt[0])} &nbsp;<span style="font-size:.82rem">ejecución {e["id"]} · inició '
                    f'{pd.Timestamp(e["inicio"]):%d/%m/%Y %H:%M}'
                    + (f' · terminó {pd.Timestamp(e["fin"]):%H:%M}' if pd.notna(e["fin"]) else "") + "</span>",
                    unsafe_allow_html=True)
    try:
        h = c.consulta("""SELECT i.creado, i.usuario, i.tipo, i.archivo_original, i.filas, i.estado, i.procesado_por
                          FROM ingesta.importacion i ORDER BY i.importacion_id DESC LIMIT 50""")
    except Exception:  # noqa: BLE001
        h = pd.DataFrame()
    if h.empty:
        st.caption("Aún no se ha importado ningún archivo desde el tablero.")
    else:
        h["tipo"] = h["tipo"].map(lambda t: imp.TIPOS.get(t, {}).get("nombre", t))
        h["estado"] = h["estado"].map({"recibido": "En cola", "procesado": "En el tablero",
                                       "con_errores": "Con errores"}).fillna(h["estado"])
        h["creado"] = pd.to_datetime(h["creado"]).dt.strftime("%d/%m/%Y %H:%M")
        c.tabla_df(h.rename(columns={"creado": "Fecha", "usuario": "Quién", "tipo": "Tipo", "archivo_original": "Archivo",
                                     "filas": "Filas válidas", "estado": "Estado", "procesado_por": "Procesado por"}),
                   height=240)
    st.caption("Los archivos quedan guardados en Datos/9. Importaciones (no se suben a GitHub). Para deshacer una "
               "importación de tipo «se suma», borra su archivo de esa carpeta: la siguiente carga lo retira.")
