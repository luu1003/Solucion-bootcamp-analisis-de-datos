"""Importación de datos con plantillas de Excel.

Flujo: el usuario elige el tipo de dato → descarga la plantilla (mismas hojas, filas de título y encabezados
que los archivos que entregó ACTHO, sin datos) → la llena → la sube → se valida con las MISMAS funciones de
limpieza del pipeline → se guarda en Datos/9. Importaciones/<tipo>/ (o reemplaza el archivo original, con
respaldo) → se dispara el DAG actho_ingesta_datos de Airflow (o, sin Airflow, el mismo proceso en local) →
los datos llegan limpios a PostgreSQL y los modelos de IA se reentrenan.

    python src/importaciones.py plantilla asistencia salida.xlsx     # genera una plantilla
    python src/importaciones.py validar asistencia archivo.xlsx       # valida un archivo
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from copy import copy
from datetime import datetime
from pathlib import Path

RAIZ = Path(os.environ.get("ACTHO_RAIZ") or Path(__file__).resolve().parent.parent)
DATOS = RAIZ / "Datos"
CARPETA = "9. Importaciones"
RESPALDOS = "_respaldos"
DAG_INGESTA = "actho_ingesta_datos"

# modo "agregar": se suma a lo que ya hay (cada archivo importado queda guardado y se procesa junto a los originales).
# modo "reemplazar": es una exportación completa que sustituye al archivo original (se guarda un respaldo).
TIPOS = {
    "asistencia": {
        "nombre": "Asistencia a eventos",
        "descripcion": "Uno o varios eventos nuevos con sus inscritos: una hoja por evento, igual que la base de "
                       "asistencia 2026, y la hoja de homologación con la fecha, la línea y la modalidad.",
        "modo": "agregar", "original": "2. Registros de participación en actividades/"
                                       "BASE ASISTENCIA A EVENTOS 2026 - EAFIT_anonimizada.xlsx",
    },
    "enc_post": {
        "nombre": "Encuesta post-evento",
        "descripcion": "Respuestas de la encuesta de satisfacción post-evento (presencial y virtual), con las mismas "
                       "preguntas y columnas que exporta la herramienta de encuestas.",
        "modo": "agregar", "original": "3. Encuestas y NPS/ENCUESTA-POST-EVENTOS (PRESENCIAL Y VIRTUAL)_anonimizada.xlsx",
    },
    "enc_90d": {
        "nombre": "Encuesta de 90 días (NPS de ACTHO)",
        "descripcion": "Respuestas de la encuesta de relación a los 90 días de afiliación: NPS de la asociación, "
                       "intención de renovar y beneficios usados.",
        "modo": "agregar", "original": "3. Encuestas y NPS/90 días - NPS_sin respuestas (instrumento).xlsx",
    },
    "uso_beneficios": {
        "nombre": "Uso de beneficios",
        "descripcion": "Uso de los servicios que no dejan registro automático (boletín, GetAbstract, Presencia, "
                       "podcast, Sello, Centro de Experiencias, Rumbo): una fila por uso.",
        "modo": "agregar", "original": None,
    },
    "crm": {
        "nombre": "Base de afiliados (exportación de Zoho CRM)",
        "descripcion": "La exportación completa de empresas del CRM. Reemplaza a la anterior: sube siempre la base "
                       "completa, no solo los cambios.",
        "modo": "reemplazar", "original": "1. Base de datos de afiliados/Base de datos Hackaton_anonimizada.xlsx",
    },
    "principal": {
        "nombre": "Contactos principales de afiliados",
        "descripcion": "La base de contactos principales (empresa, ciudad, cargo y persona). Reemplaza a la anterior.",
        "modo": "reemplazar", "original": "5. Indicadores y reportes actuales/Base de datos afiliados ACTHO_anonimizada.xlsx",
    },
}
TIPOS_AGREGAR = [t for t, d in TIPOS.items() if d["modo"] == "agregar"]


def _clave(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("\n", " ").split())


# ──────────────────────────────────────────────────────────────────────────────
# Archivos importados (los usa la limpieza y la detección de cambios)
# ──────────────────────────────────────────────────────────────────────────────
def carpeta(tipo: str, datos: Path | None = None) -> Path:
    return Path(datos or DATOS) / CARPETA / tipo


def archivos_importados(datos: Path | None, tipo: str) -> list[Path]:
    """Archivos .xlsx importados de un tipo, en orden de llegada (el nombre empieza con la fecha y hora)."""
    c = carpeta(tipo, datos)
    if not c.exists():
        return []
    return sorted(p for p in c.glob("*.xlsx") if not p.name.startswith(("~$", ".")))


def huella_carpeta(datos: Path | None, tipo: str) -> dict:
    """Huella de todos los archivos importados de un tipo (cambia si se agrega o se quita alguno)."""
    h = hashlib.sha256()
    total = 0
    for p in archivos_importados(datos, tipo):
        h.update(p.name.encode())
        h.update(hashlib.sha256(p.read_bytes()).digest())
        total += p.stat().st_size
    return {"archivo": f"{CARPETA}/{tipo}/", "hash": h.hexdigest(), "bytes": total}


# ──────────────────────────────────────────────────────────────────────────────
# Plantillas
# ──────────────────────────────────────────────────────────────────────────────
MORADO, NARANJA = "5B00D9", "FF5B14"


def _copiar_filas(origen, destino, hasta: int, max_col: int | None = None):
    """Copia las primeras filas (títulos y encabezados) con su formato; ningún dato."""
    max_col = max_col or origen.max_column
    for r in range(1, hasta + 1):
        for col in range(1, max_col + 1):
            o = origen.cell(row=r, column=col)
            d = destino.cell(row=r, column=col, value=o.value)
            if o.has_style:
                d.font, d.fill, d.border = copy(o.font), copy(o.fill), copy(o.border)
                d.alignment, d.number_format = copy(o.alignment), o.number_format
        if origen.row_dimensions[r].height:
            destino.row_dimensions[r].height = origen.row_dimensions[r].height
    for letra, dim in origen.column_dimensions.items():
        if dim.width:
            destino.column_dimensions[letra].width = dim.width
    destino.freeze_panes = destino.cell(row=hasta + 1, column=1)


def _fila_encabezado(ws, pred, max_filas=8) -> int:
    for i, fila in enumerate(ws.iter_rows(max_row=max_filas, values_only=True), start=1):
        if any(isinstance(v, str) and pred(_clave(v)) for v in fila):
            return i
    return 1


def _resaltar_encabezado(ws, fila: int):
    from openpyxl.styles import Font, PatternFill
    for celda in ws[fila]:
        if celda.value not in (None, ""):
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = PatternFill("solid", fgColor=MORADO)


def _hoja_instrucciones(wb, titulo: str, lineas: list[str], listas: dict[str, list] | None = None):
    from openpyxl.styles import Alignment, Font
    ws = wb.create_sheet("Instrucciones", 0)
    ws["A1"] = titulo
    ws["A1"].font = Font(bold=True, size=14, color=MORADO)
    for i, linea in enumerate(lineas, start=3):
        ws.cell(row=i, column=1, value=linea).alignment = Alignment(wrap_text=True, vertical="top")
        if linea and linea[:2] in ("1.", "2.", "3.", "4.", "5.", "6.") or linea.endswith(":"):
            ws.cell(row=i, column=1).font = Font(bold=linea.endswith(":"))
    ws.column_dimensions["A"].width = 120
    if listas:
        lw = wb.create_sheet("Listas")
        for j, (nombre, valores) in enumerate(listas.items(), start=1):
            lw.cell(row=1, column=j, value=nombre).font = Font(bold=True)
            for i, v in enumerate(valores, start=2):
                lw.cell(row=i, column=j, value=v)
            lw.column_dimensions[chr(64 + j)].width = 34
        lw.sheet_state = "hidden"
    wb.active = 0
    return ws


def _lista(wb, ws, nombre_lista: str, rango: str, error: str):
    """Lista desplegable sobre un rango, tomando los valores de la hoja oculta Listas."""
    from openpyxl.worksheet.datavalidation import DataValidation
    lw = wb["Listas"]
    col = next(c for c in range(1, lw.max_column + 1) if lw.cell(row=1, column=c).value == nombre_lista)
    letra = chr(64 + col)
    n = sum(1 for r in range(2, lw.max_row + 1) if lw.cell(row=r, column=col).value not in (None, ""))
    dv = DataValidation(type="list", formula1=f"=Listas!${letra}$2:${letra}${n + 1}", allow_blank=True,
                        showErrorMessage=True, errorStyle="warning", errorTitle="Valor fuera de la lista", error=error)
    ws.add_data_validation(dv)
    dv.add(rango)


NIVELES_CARGO = ["Alta dirección (C-level / VP)", "Dirección / Gerencia", "Jefatura / Coordinación",
                 "Profesional / Analista / Consultor", "Asistente / Auxiliar", "Estudiante / Practicante",
                 "Independiente / Consultor externo", "Otro"]


def _valores_actuales(campo: str, defecto: list) -> list:
    """Valores que ya existen en la base (para las listas desplegables); si no hay base, los de referencia."""
    try:
        import psycopg
        sys.path.insert(0, str(RAIZ / "src"))
        from cargar_postgres import cadena_conexion
        sql = {"linea_2027": "SELECT DISTINCT linea_2027 FROM actho.dim_evento",
               "experiencia": "SELECT DISTINCT experiencia FROM actho.dim_evento",
               "modalidad": "SELECT DISTINCT modalidad FROM actho.dim_evento",
               "nivel_cargo": "SELECT DISTINCT nivel_cargo FROM actho.fact_asistencia"}[campo]
        with psycopg.connect(cadena_conexion(), connect_timeout=3) as conn:
            v = sorted(r[0] for r in conn.execute(sql).fetchall() if r[0] and r[0] != "Sin dato")
        return v or defecto
    except Exception:  # noqa: BLE001
        return defecto


def plantilla(tipo: str, datos: Path | None = None) -> bytes:
    """Plantilla vacía con el mismo formato del archivo original de ese tipo."""
    import openpyxl
    datos = Path(datos or DATOS)
    d = TIPOS[tipo]
    if tipo == "uso_beneficios":
        return _plantilla_uso()
    ruta = datos / d["original"]
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró el archivo original para armar la plantilla: {d['original']}")
    orig = openpyxl.load_workbook(ruta)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    comunes = [
        "Antes de empezar:",
        "• No cambies los nombres de las hojas ni de las columnas, y no borres las filas de título: el sistema las usa "
        "para reconocer cada dato.",
        "• Los datos de personas y empresas van con su código anonimizado (EMP-0001 para empresas, P-00001 para "
        "personas), igual que en los archivos originales.",
        "• Las fechas pueden ir como fecha de Excel o como DD/MM/AAAA.",
        "• Puedes dejar vacías las columnas que no apliquen; el sistema marca como «Sin dato» lo que falte.",
        "",
        "Después de subirla:",
        "1. El tablero revisa el archivo con las mismas reglas de limpieza de siempre y te muestra qué encontró.",
        "2. Si todo está bien, al confirmar se guarda y se procesa (Airflow o el proceso local).",
        "3. En unos minutos los datos aparecen en el tablero y los modelos de IA se actualizan.",
    ]
    if tipo == "asistencia":
        hom = next(ws for ws in orig.worksheets if "HOMOLOG" in ws.title.upper())
        hi = _fila_encabezado(hom, lambda v: v.startswith(("n evento", "no evento", "n° evento", "nº evento")))
        h = wb.create_sheet(hom.title)
        _copiar_filas(hom, h, hi, 7)
        _resaltar_encabezado(h, hi)
        ejemplo = next(ws for ws in orig.worksheets
                       if not ws.title.upper().startswith("GENERAL") and "HOMOLOG" not in ws.title.upper())
        he = _fila_encabezado(ejemplo, lambda v: v.startswith("id_empresa"))
        for n in (1, 2):
            ev = wb.create_sheet(f"EVENTO {n}")
            _copiar_filas(ejemplo, ev, he)
            ev["A1"] = f"Nombre del evento {n} (escríbelo aquí)"
            _resaltar_encabezado(ev, he)
            h.cell(row=hi + n, column=2, value=f"EVENTO {n}")
        listas = {"Línea 2027": _valores_actuales("linea_2027", ["Anticipar", "Pares", "Foro", "Evento grande"]),
                  "Experiencia": _valores_actuales("experiencia", ["Sin dato"]),
                  "Modalidad": _valores_actuales("modalidad", ["Presencial", "Virtual", "Híbrido"]),
                  "Nivel de cargo": _valores_actuales("nivel_cargo", NIVELES_CARGO),
                  "Costo": ["Sin costo", "Con costo"], "Sí / No": ["Si", "No"]}
        _hoja_instrucciones(wb, "Plantilla de asistencia a eventos · ACTHO", [
            "Para qué: registrar eventos nuevos y sus inscritos, con el mismo formato de la base de asistencia 2026.",
            "",
            "Cómo llenarla:",
            f"1. En la hoja «{hom.title}», una fila por evento: deja vacío el N° de evento (el sistema lo asigna), escribe "
            "en «Hoja» el nombre exacto de la hoja del evento (por ejemplo EVENTO 1), la fecha, el nombre, la línea "
            "2027, la experiencia y la modalidad (elige de las listas).",
            "2. En cada hoja de evento, escribe el nombre del evento en la primera fila y una fila por inscrito debajo de "
            "los encabezados: código de afiliado (1 = afiliado, 2 = no afiliado), código de la empresa, código de la "
            "persona, nivel de cargo, costo y si autorizó el tratamiento de datos.",
            "3. ¿Más de dos eventos? Copia una hoja de evento (clic derecho → Mover o copiar → Crear una copia), "
            "renómbrala y agrégala en la homologación.",
            "4. Si un evento ya estaba en la base (misma fecha y nombre), sus inscritos se suman a los que ya tenía y "
            "no se duplican personas.",
            "",
        ] + comunes, listas)
        for col, nombre in ((5, "Línea 2027"), (6, "Experiencia"), (7, "Modalidad")):
            letra = chr(64 + col)
            _lista(wb, h, nombre, f"{letra}{hi + 1}:{letra}{hi + 200}", "Elige un valor de la lista para que el evento "
                                                                        "se clasifique bien.")
        for n in (1, 2):
            ev = wb[f"EVENTO {n}"]
            encs = [_clave(c.value) for c in ev[he]]
            for nombre, pred in (("Nivel de cargo", lambda v: v.startswith("nivel de cargo")),
                                 ("Costo", lambda v: v.startswith("costo")),
                                 ("Sí / No", lambda v: "autoriz" in v)):
                idx = next((i for i, v in enumerate(encs) if v and pred(v)), None)
                if idx is not None:
                    letra = chr(65 + idx)
                    _lista(wb, ev, nombre, f"{letra}{he + 1}:{letra}{he + 3000}", "Elige un valor de la lista.")
    elif tipo in ("enc_post", "enc_90d"):
        resp = orig["Responses"]
        hi = _fila_encabezado(resp, lambda v: v.startswith("id de respuesta"))
        ws = wb.create_sheet("Responses")
        _copiar_filas(resp, ws, hi)
        _resaltar_encabezado(ws, hi)
        _hoja_instrucciones(wb, f"Plantilla de {d['nombre'].lower()} · ACTHO", [
            "Para qué: cargar respuestas de la encuesta con las mismas columnas que exporta la herramienta de encuestas.",
            "",
            "Cómo llenarla:",
            "1. Lo más fácil: exporta las respuestas desde la herramienta de encuestas y pega las filas debajo de los "
            "encabezados de la hoja «Responses», respetando el orden de las columnas.",
            "2. Una fila por respuesta. El «ID de respuesta» debe ser único; si una respuesta ya existía, se reemplaza "
            "por la nueva (no se duplica). Si lo dejas vacío, el sistema le asigna uno.",
            "3. En «Nombre completo» va el código de la persona (P-00001) y en «Empresa» el de la empresa (EMP-0001).",
            "4. Las calificaciones van como número (1 a 5) y el NPS de 0 a 10.",
            "",
        ] + comunes)
    else:   # crm, principal: una hoja con una fila de encabezados
        hoja = orig.worksheets[0]
        ws = wb.create_sheet(hoja.title)
        _copiar_filas(hoja, ws, 1)
        _resaltar_encabezado(ws, 1)
        extra = ("Exporta la base completa de empresas desde Zoho CRM (con todos los campos) y pégala debajo de los "
                 "encabezados, o súbela tal como sale de Zoho si conserva los mismos nombres de columna."
                 if tipo == "crm" else
                 "Una fila por contacto principal: código de la empresa, ciudad, cargo y código de la persona.")
        _hoja_instrucciones(wb, f"Plantilla de {d['nombre'].lower()} · ACTHO", [
            "Para qué: " + d["descripcion"],
            "",
            "Cómo llenarla:",
            "1. " + extra,
            "2. Este archivo REEMPLAZA al anterior: incluye todas las filas, no solo las nuevas. El archivo anterior queda "
            f"guardado como respaldo en Datos/{CARPETA}/{RESPALDOS}/.",
            "",
        ] + comunes)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _servicios() -> list[str]:
    sys.path.insert(0, str(RAIZ / "src"))
    import limpieza_datos as L
    return [s[1] for s in L.CATALOGO_SERVICIOS if s[0] != "S99"]


def _plantilla_uso() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Registros"
    ws.append(["fecha", "empresa_id", "persona_id (opcional)", "servicio", "cantidad", "fuente", "detalle (opcional)"])
    _resaltar_encabezado(ws, 1)
    for col, ancho in zip("ABCDEFG", [12, 12, 20, 36, 10, 24, 40]):
        ws.column_dimensions[col].width = ancho
    ws.freeze_panes = "A2"
    _hoja_instrucciones(wb, "Plantilla de uso de beneficios · ACTHO", [
        "Para qué: registrar el uso de los servicios que no dejan registro automático (boletín Actho en Marcha, "
        "GetAbstract y AI tip, Actho de Presencia, Actho Seguido, Sello ACTHO, Centro de Experiencias, Actho de Rumbo).",
        "",
        "Cómo llenarla:",
        "1. En la hoja Registros, una fila por uso: fecha, código de la empresa (EMP-0001), código de la persona si se "
        "conoce, servicio (elígelo de la lista), cantidad (personas, aperturas, descargas) y la fuente del dato.",
        "2. Puedes subir una plantilla por mes: cada archivo se suma a los anteriores.",
        "",
        "Ejemplo: 15/11/2026 | EMP-0019 | (vacío) | Actho en Marcha (boletín) | 1 | Plataforma de correo | Abrió el boletín",
        "",
        "Las filas con empresa, servicio o fecha no reconocidos se excluyen y aparecen en el diagnóstico de calidad.",
    ], {"Servicio": _servicios()})
    _lista(wb, ws, "Servicio", "D2:D5000", "Elige un servicio de la lista.")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# Ingreso manual: lo que se escribe en el tablero se vuelca en la misma plantilla y sigue el mismo camino
# (validación → Datos/9. Importaciones → pipeline). Solo para los tipos que se suman.
# ──────────────────────────────────────────────────────────────────────────────
# (campo, etiqueta, clase, opciones, prefijo de la columna en la plantilla)
MANUAL = {
    "asistencia": [
        ("codigo_afiliado", "Tipo de asistente", "lista", ["Afiliado", "No afiliado"], None),
        ("empresa_id", "Código de empresa", "texto", None, "id_empresa"),
        ("persona_id", "Código de persona", "texto", None, "id_persona"),
        ("nivel_cargo", "Nivel de cargo", "lista", NIVELES_CARGO, "nivel de cargo"),
        ("costo", "Costo", "lista", ["Sin costo", "Con costo"], "costo"),
        ("autoriza", "Autoriza datos", "lista", ["Si", "No"], "autoriz"),
    ],
    "uso_beneficios": [
        ("fecha", "Fecha", "fecha", None, "fecha"),
        ("empresa_id", "Código de empresa", "texto", None, "empresa_id"),
        ("persona_id", "Código de persona (opcional)", "texto", None, "persona_id"),
        ("servicio", "Servicio", "lista", "servicios", "servicio"),
        ("cantidad", "Cantidad", "numero", None, "cantidad"),
        ("fuente", "Fuente del dato", "texto", None, "fuente"),
        ("detalle", "Detalle (opcional)", "texto", None, "detalle"),
    ],
    "enc_post": [
        ("respuesta_id", "ID de respuesta (opcional)", "texto", None, "id de respuesta"),
        ("fecha", "Fecha de respuesta", "fecha", None, "respuesta completada"),
        ("persona_id", "Código de persona", "texto", None, "1. nombre completo"),
        ("empresa_id", "Código de empresa", "texto", None, "4. empresa"),
        ("cargo", "Nivel de cargo", "lista", NIVELES_CARGO, "5. cargo"),
        ("ciudad", "Ciudad", "texto", None, "6. ciudad"),
        ("afiliado", "¿Es afiliado?", "lista", ["Sí, soy afiliado", "No soy afiliado"], "7. eres afiliado"),
        ("modalidad", "Modalidad", "lista", ["Presencial", "Virtual"], "12. como participaste"),
        ("satisfaccion", "Satisfacción (1 a 5)", "numero", None, "13. en general"),
        ("nps", "NPS (0 a 10)", "numero", None, "14. de 0 a 10"),
        ("gusto", "Lo que más gustó", "texto", None, "16. que fue lo que mas"),
        ("mejorar", "Qué mejorar", "texto", None, "17. que deberiamos mejorar"),
    ],
    "enc_90d": [
        ("respuesta_id", "ID de respuesta (opcional)", "texto", None, "id de respuesta"),
        ("fecha", "Fecha de respuesta", "fecha", None, "respuesta completada"),
        ("persona_id", "Código de persona", "texto", None, "nombre completo"),
        ("empresa_id", "Código de empresa", "texto", None, "nombre de la empresa"),
        ("cargo", "Nivel de cargo", "lista", NIVELES_CARGO, "cargo"),
        ("ciudad", "Ciudad", "texto", None, "ciudad"),
        ("nps", "NPS de ACTHO (0 a 10)", "numero", None, "1.1."),
        ("razon", "Razón de la calificación", "texto", None, "1.2."),
        ("renovar", "Probabilidad de renovar (1 a 5)", "numero", None, "6.1."),
        ("acepta", "Acepta tratamiento de datos", "lista", ["Sí", "No"], "he leido y acepto"),
    ],
}
CAMPOS_EVENTO = [("nombre", "Nombre del evento"), ("fecha", "Fecha"), ("linea_2027", "Línea 2027"),
                 ("experiencia", "Experiencia"), ("modalidad", "Modalidad")]


def opciones_manual(tipo: str, campo: str) -> list:
    for c_, _, clase, ops, _ in MANUAL.get(tipo, []):
        if c_ == campo:
            return _servicios() if ops == "servicios" else (ops or [])
    if campo in ("linea_2027", "experiencia", "modalidad"):
        return _valores_actuales(campo, {"linea_2027": ["Anticipar", "Pares", "Foro", "Evento grande"],
                                         "experiencia": ["Sin dato"], "modalidad": ["Presencial", "Virtual"]}[campo])
    return []


def _vacio(v) -> bool:
    try:
        import pandas as pd
        return v is None or (not isinstance(v, str) and pd.isna(v)) or (isinstance(v, str) and not v.strip())
    except Exception:  # noqa: BLE001
        return v is None


def _valor_excel(v):
    import pandas as pd
    if _vacio(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    if hasattr(v, "item"):
        return v.item()
    return v.strip() if isinstance(v, str) else v


def llenar_plantilla(tipo: str, filas, evento: dict | None = None, datos: Path | None = None) -> bytes:
    """Escribe en la plantilla del tipo las filas ingresadas a mano (DataFrame con los campos de MANUAL[tipo])."""
    import openpyxl
    import pandas as pd
    wb = openpyxl.load_workbook(io.BytesIO(plantilla(tipo, datos)))
    filas = filas[[c_ for c_, *_ in MANUAL[tipo] if c_ in filas.columns]].copy()
    filas = filas[~filas.apply(lambda r: all(_vacio(v) for v in r), axis=1)]
    if tipo == "asistencia":
        h = next(ws for ws in wb.worksheets if "HOMOLOG" in ws.title.upper())
        hi = _fila_encabezado(h, lambda v: v.startswith(("n evento", "no evento", "n° evento", "nº evento")))
        ev = evento or {}
        fecha = pd.Timestamp(ev.get("fecha")) if not _vacio(ev.get("fecha")) else None
        for col, v in zip(range(2, 8), ["EVENTO 1", fecha.to_pydatetime() if fecha is not None else None, ev.get("nombre"),
                                        ev.get("linea_2027"), ev.get("experiencia"), ev.get("modalidad")]):
            h.cell(row=hi + 1, column=col, value=v)
        for col in range(1, 8):
            h.cell(row=hi + 2, column=col, value=None)
        del wb["EVENTO 2"]
        ws = wb["EVENTO 1"]
        ws["A1"] = ev.get("nombre")
        he = _fila_encabezado(ws, lambda v: v.startswith("id_empresa"))
        encs = [_clave(c_.value) for c_ in ws[he]]
        destino = {c_: next((i for i, e in enumerate(encs) if e and (e.startswith(pref) or (pref == "autoriz" and pref in e))),
                            None) for c_, _, _, _, pref in MANUAL[tipo] if pref}
        for j, (_, r) in enumerate(filas.iterrows(), start=he + 1):
            ws.cell(row=j, column=1, value={"Afiliado": 1, "No afiliado": 2}.get(r.get("codigo_afiliado")))
            for c_, idx in destino.items():
                if idx is not None:
                    ws.cell(row=j, column=idx + 1, value=_valor_excel(r.get(c_)))
    else:
        hoja = "Registros" if tipo == "uso_beneficios" else "Responses"
        ws = wb[hoja]
        hi = 1 if tipo == "uso_beneficios" else _fila_encabezado(ws, lambda v: v.startswith("id de respuesta"))
        encs = [_clave(c_.value) for c_ in ws[hi]]
        destino = {}
        for c_, _, _, _, pref in MANUAL[tipo]:
            destino[c_] = next((i for i, e in enumerate(encs) if e and e.startswith(pref)), None)
        marca = datetime.now().strftime("%Y%m%d%H%M%S")
        for n, (j, (_, r)) in enumerate(enumerate(filas.iterrows(), start=hi + 1), start=1):
            for c_, idx in destino.items():
                if idx is None:
                    continue
                v = _valor_excel(r.get(c_))
                if c_ == "respuesta_id" and v is None:
                    v = f"MAN-{marca}-{n}"   # la encuesta de 90 días descarta respuestas sin ID
                if c_ == "fecha" and v is not None and tipo != "uso_beneficios":
                    ws.cell(row=j, column=encs.index("respuesta iniciada") + 1, value=v)
                ws.cell(row=j, column=idx + 1, value=v)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# Validación: se corre la misma limpieza del pipeline sobre el archivo subido
# ──────────────────────────────────────────────────────────────────────────────
def _encabezados(ruta: Path, hoja: str | None, pred) -> tuple[list, int]:
    import openpyxl
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    ws = wb[hoja] if hoja else wb.worksheets[0]
    hi = _fila_encabezado(ws, pred)
    fila = next(ws.iter_rows(min_row=hi, max_row=hi, values_only=True))
    return [_clave(v) for v in fila if v not in (None, "")], hi


def _comparar_columnas(original: Path, subido: Path, hoja, pred, errores, advertencias):
    esperadas, _ = _encabezados(original, hoja, pred)
    tiene, _ = _encabezados(subido, hoja, pred)
    faltan = [c for c in esperadas if c not in tiene]
    sobran = [c for c in tiene if c not in esperadas]
    if faltan:
        (errores if len(faltan) > len(esperadas) * 0.3 else advertencias).append(
            f"Faltan {len(faltan)} columna(s) de la plantilla: " + ", ".join(faltan[:6]) + ("…" if len(faltan) > 6 else ""))
    if sobran:
        advertencias.append(f"Hay {len(sobran)} columna(s) que no están en la plantilla y se ignorarán: "
                            + ", ".join(sobran[:4]) + ("…" if len(sobran) > 4 else ""))


def validar(tipo: str, contenido: bytes, nombre: str = "archivo.xlsx", datos: Path | None = None,
            corte=None, empresas_validas: set | None = None) -> dict:
    """Corre la limpieza real sobre el archivo y devuelve lo que encontró. Nunca toca la base ni Datos/."""
    import openpyxl
    import pandas as pd
    sys.path.insert(0, str(RAIZ / "src"))
    import limpieza_datos as L
    datos = Path(datos or DATOS)
    d = TIPOS[tipo]
    corte = pd.Timestamp(corte) if corte else pd.Timestamp.today().normalize()
    errores, advertencias, resumen = [], [], []
    vista = pd.DataFrame()
    tmp = Path(tempfile.mkdtemp()) / "subido.xlsx"
    tmp.write_bytes(contenido)
    L.CALIDAD.clear()
    try:
        try:
            wb = openpyxl.load_workbook(tmp, read_only=True)
            hojas = [ws.title for ws in wb.worksheets]
        except Exception:  # noqa: BLE001
            return {"ok": False, "errores": ["El archivo no es un Excel válido (.xlsx). Guárdalo como «Libro de Excel» "
                                             "y vuelve a subirlo."], "advertencias": [], "resumen": [], "hallazgos": None,
                    "vista": vista, "filas": 0}
        original = datos / d["original"] if d["original"] else None
        if tipo == "asistencia":
            if not any("HOMOLOG" in h.upper() for h in hojas):
                errores.append("No está la hoja de homologación (lista de eventos). Usa la plantilla sin renombrar hojas.")
            else:
                ev = L.cargar_eventos(tmp, asignar_ids=True)
                if ev.empty:
                    errores.append("La hoja de homologación no tiene eventos: llena al menos una fila con la hoja, "
                                   "fecha y nombre del evento.")
                else:
                    a = L.cargar_asistencia(tmp, ev)
                    resumen += [("Eventos", len(ev)), ("Inscripciones válidas", len(a)),
                                ("Empresas distintas", a["empresa_id"].nunique()),
                                ("Personas distintas", a["persona_id"].nunique())]
                    sin_fecha = ev["fecha"].isna().sum()
                    if sin_fecha:
                        advertencias.append(f"{sin_fecha} evento(s) sin fecha válida: no se podrán ubicar en el tiempo.")
                    sin_insc = sorted(set(ev["evento_id"]) - set(a["evento_id"]))
                    if sin_insc:
                        advertencias.append("Eventos sin inscritos (revisa que el nombre en «Hoja» coincida con la hoja): "
                                            + ", ".join(ev.set_index("evento_id").loc[sin_insc, "nombre"].astype(str)))
                    if len(a) == 0:
                        errores.append("No se encontró ningún inscrito válido (cada fila necesita el código de la "
                                       "empresa, EMP-0001).")
                    vista = a.merge(ev[["evento_id", "nombre", "fecha"]], on="evento_id").head(200)[
                        ["nombre", "fecha", "empresa_id", "persona_id", "nivel_cargo", "costo", "autoriza_datos"]]
        elif tipo in ("enc_post", "enc_90d"):
            if "Responses" not in hojas:
                errores.append("No está la hoja «Responses». Usa la plantilla sin renombrar hojas.")
            else:
                _comparar_columnas(original, tmp, "Responses", lambda v: v.startswith("id de respuesta"),
                                   errores, advertencias)
                if not errores:
                    if tipo == "enc_post":
                        eventos = L.cargar_eventos(datos / TIPOS["asistencia"]["original"])
                        L.CALIDAD.clear()   # solo interesan los hallazgos del archivo subido
                        out, temas = L.cargar_encuesta_post(tmp, eventos)
                        out = out[out["respuesta_id"].replace({"nan": None, "": None}).notna()
                                  | out["fecha_respuesta"].notna()]
                        resumen += [("Respuestas", len(out)), ("Con NPS", int(out["nps_puntaje"].notna().sum())),
                                    ("Con empresa reconocida", int(out["empresa_id"].notna().sum())),
                                    ("Temas pedidos", len(temas))]
                        vista = out.head(200)[["respuesta_id", "fecha_respuesta", "empresa_id", "nivel_cargo",
                                               "satisfaccion_general", "nps_puntaje"]]
                    else:
                        out, usos = L.cargar_encuesta_90d(tmp, L.construir_catalogo())
                        resumen += [("Respuestas", len(out)), ("Con NPS", int(out["nps_actho"].notna().sum())),
                                    ("Con empresa reconocida", int(out["empresa_id"].notna().sum())),
                                    ("Usos de beneficios declarados", len(usos))]
                        vista = out.head(200)[["respuesta_id", "fecha_respuesta", "empresa_id", "nps_actho",
                                               "intencion_renovar"]]
                    if len(out) == 0:
                        errores.append("La hoja «Responses» no tiene respuestas debajo de los encabezados.")
        elif tipo == "uso_beneficios":
            if "Registros" not in hojas:
                errores.append("No está la hoja «Registros». Usa la plantilla sin renombrar hojas.")
            else:
                if empresas_validas is None:
                    crm, _ = L.cargar_crm(datos / TIPOS["crm"]["original"], corte)
                    empresas_validas = set(crm["empresa_id"].dropna())
                    L.CALIDAD.clear()
                bruto = pd.read_excel(tmp, sheet_name="Registros").dropna(how="all")
                cat = L.construir_catalogo()
                out = L.cargar_plantilla_uso(tmp, cat, empresas_validas)
                # Qué fila no sirve y por qué (número de fila de Excel = índice + 2)
                nombres = {L.clave(x) for x in cat["servicio"]} | set(cat["servicio_id"])
                b = bruto.copy()
                b.columns = [L.clave(c).replace(" (opcional)", "").strip().replace(" ", "_") for c in b.columns]
                for i, r in b.iterrows():
                    motivos = []
                    emp = L._id_silencioso(pd.Series([r.get("empresa_id")]), L.RX_ID_EMPRESA).iloc[0]
                    if pd.isna(emp):
                        motivos.append("código de empresa inválido")
                    elif emp not in empresas_validas:
                        motivos.append(f"la empresa {emp} no está en la base")
                    sv = r.get("servicio")
                    if not isinstance(sv, str) or (L.clave(sv) not in nombres and sv.strip().upper() not in nombres):
                        motivos.append(f"servicio «{sv}» no está en la lista")
                    if pd.isna(L._fecha_plantilla(r.get("fecha"))):
                        motivos.append("fecha no reconocida")
                    if motivos:
                        advertencias.append(f"Fila {i + 2}: " + "; ".join(motivos) + " (no se cargará).")
                resumen += [("Filas en la plantilla", len(bruto)), ("Usos válidos", len(out)),
                            ("Empresas", out["empresa_id"].nunique())]
                if len(bruto) and not len(out):
                    errores.append("Ninguna fila tiene empresa, servicio y fecha reconocidos.")
                elif len(bruto) == 0:
                    errores.append("La hoja «Registros» está vacía.")
                vista = out.head(200)
        elif tipo == "crm":
            _comparar_columnas(original, tmp, None, lambda v: v.startswith("id de registro"), errores, advertencias)
            if not errores:
                crm, excl = L.cargar_crm(tmp, corte)
                vig = int(crm["es_vigente"].sum()) if "es_vigente" in crm else None
                resumen += [("Registros leídos", len(crm) + len(excl)), ("Empresas", crm["empresa_id"].nunique()),
                            ("Vigentes al corte", vig), ("Registros excluidos", len(excl))]
                if crm.empty:
                    errores.append("No se encontró ninguna empresa con código válido (EMP-0001).")
                antes = pd.read_excel(original).shape[0] if original and original.exists() else None
                if antes and len(crm) + len(excl) < 0.8 * antes:
                    advertencias.append(f"Este archivo trae {len(crm) + len(excl):,} registros y el actual {antes:,}. "
                                        "Recuerda que REEMPLAZA a la base completa: ¿seguro que no es solo una parte?")
                vista = crm.head(200)[[c for c in ["empresa_id", "tipo_membresia", "nivel_2027", "estado_membresia",
                                                   "fecha_expiracion", "ciudad"] if c in crm.columns]]
        elif tipo == "principal":
            _comparar_columnas(original, tmp, None, lambda v: v.startswith("nombre de empresa"), errores, advertencias)
            if not errores:
                p = pd.read_excel(tmp)
                ids = L.validar_id(p.iloc[:, 0], L.RX_ID_EMPRESA, "dim_persona", "empresa_id")
                resumen += [("Contactos", len(p)), ("Con empresa válida", int(ids.notna().sum()))]
                antes = pd.read_excel(original).shape[0] if original and original.exists() else None
                if antes and len(p) < 0.8 * antes:
                    advertencias.append(f"Este archivo trae {len(p):,} contactos y el actual {antes:,}. Recuerda que "
                                        "REEMPLAZA a la base completa.")
                if ids.notna().sum() == 0:
                    errores.append("Ninguna fila tiene un código de empresa válido (EMP-0001).")
                vista = p.head(200)
    except SystemExit as e:
        errores.append(str(e))
    except Exception as e:  # noqa: BLE001
        errores.append(f"El archivo no tiene la estructura de la plantilla ({type(e).__name__}: {str(e)[:200]}). "
                       "Descarga la plantilla y copia los datos en ella sin cambiar hojas ni encabezados.")
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)
    hallazgos = pd.DataFrame(L.CALIDAD) if L.CALIDAD else pd.DataFrame()
    if len(hallazgos):
        hallazgos = hallazgos[pd.to_numeric(hallazgos.get("filas_afectadas", 0), errors="coerce").fillna(0) > 0]
    L.CALIDAD.clear()
    filas = next((v for k, v in resumen if k in ("Inscripciones válidas", "Respuestas", "Usos válidos", "Empresas",
                                                 "Contactos")), 0) or 0
    return {"ok": not errores, "errores": errores, "advertencias": advertencias, "resumen": resumen,
            "hallazgos": hallazgos, "vista": vista, "filas": int(filas)}


# ──────────────────────────────────────────────────────────────────────────────
# Guardar, registrar y procesar
# ──────────────────────────────────────────────────────────────────────────────
def guardar(tipo: str, contenido: bytes, nombre_original: str, usuario: str | None, datos: Path | None = None) -> Path:
    datos = Path(datos or DATOS)
    d = TIPOS[tipo]
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    quien = "".join(ch for ch in (usuario or "tablero") if ch.isalnum())[:20] or "tablero"
    if d["modo"] == "agregar":
        destino = carpeta(tipo, datos) / f"{marca}_{quien}.xlsx"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)
        return destino
    destino = datos / d["original"]
    if destino.exists():
        resp = datos / CARPETA / RESPALDOS / f"{tipo}_{marca}_{destino.name}"
        resp.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destino, resp)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".subiendo.xlsx")
    tmp.write_bytes(contenido)
    os.replace(tmp, destino)
    return destino


SQL_TABLA = """CREATE SCHEMA IF NOT EXISTS ingesta;
CREATE TABLE IF NOT EXISTS ingesta.importacion (
    importacion_id serial PRIMARY KEY, creado timestamp DEFAULT now(), usuario text, tipo text NOT NULL,
    modo text, archivo_original text, archivo_guardado text, filas integer, estado text DEFAULT 'recibido',
    procesado_por text, ejecucion_id integer, mensaje text)"""


def registrar(conn, tipo, usuario, archivo_original, archivo_guardado: Path, filas, procesado_por, mensaje=None) -> int:
    conn.execute(SQL_TABLA)
    rel = str(Path(archivo_guardado).relative_to(DATOS)) if str(archivo_guardado).startswith(str(DATOS)) \
        else str(archivo_guardado)
    return conn.execute("""INSERT INTO ingesta.importacion (usuario, tipo, modo, archivo_original, archivo_guardado,
                           filas, procesado_por, mensaje) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING importacion_id""",
                        (usuario, tipo, TIPOS[tipo]["modo"], archivo_original, rel, filas, procesado_por,
                         mensaje)).fetchone()[0]


def _airflow(url: str, conf: dict) -> str:
    """Lanza el DAG de ingesta por la API de Airflow 3 (token sin credenciales con simple_auth_manager_all_admins)."""
    import urllib.request

    def pedir(metodo, ruta, cuerpo=None, token=None):
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(url.rstrip("/") + ruta, data=datos, method=metodo,
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {token}"} if token else {})})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read() or b"{}")

    usuario, clave = os.environ.get("AIRFLOW_USUARIO"), os.environ.get("AIRFLOW_CLAVE")
    tok = (pedir("POST", "/auth/token", {"username": usuario, "password": clave}) if usuario and clave
           else pedir("GET", "/auth/token"))
    token = tok.get("access_token") or tok.get("token")
    pedir("PATCH", f"/api/v2/dags/{DAG_INGESTA}", {"is_paused": False}, token)
    run = pedir("POST", f"/api/v2/dags/{DAG_INGESTA}/dagRuns", {"logical_date": None, "conf": conf}, token)
    return run.get("dag_run_id", "")


def procesar(conf: dict | None = None, registro: Path | None = None) -> tuple[str, str]:
    """Dispara el procesamiento. Con AIRFLOW_API_URL usa Airflow; si no hay Airflow (setup.py), corre el mismo
    proceso (ingesta_control.py ingesta) en segundo plano. Devuelve (quién lo procesa, detalle)."""
    url = os.environ.get("AIRFLOW_API_URL")
    motivo = ""
    if url:
        try:
            return "Airflow", _airflow(url, conf or {})
        except Exception as e:  # noqa: BLE001
            motivo = f"Airflow no respondió ({type(e).__name__}); se procesa en local. "
    registro = registro or (DATOS / CARPETA / "procesamiento.log")
    registro.parent.mkdir(parents=True, exist_ok=True)
    with open(registro, "w", encoding="utf-8") as f:
        subprocess.Popen([sys.executable, str(RAIZ / "src" / "ingesta_control.py"), "ingesta"], cwd=RAIZ,
                         env=dict(os.environ, PYTHONIOENCODING="utf-8"), stdout=f, stderr=subprocess.STDOUT,
                         start_new_session=True)
    return "Proceso local", motivo + f"registro en {registro.relative_to(RAIZ) if registro.is_relative_to(RAIZ) else registro}"


if __name__ == "__main__":
    orden, tipo = sys.argv[1], sys.argv[2]
    if orden == "plantilla":
        Path(sys.argv[3]).write_bytes(plantilla(tipo))
        print("Plantilla guardada en", sys.argv[3])
    elif orden == "validar":
        r = validar(tipo, Path(sys.argv[3]).read_bytes())
        print(json.dumps({k: v for k, v in r.items() if k not in ("vista", "hallazgos")}, ensure_ascii=False,
                         indent=2, default=str))
        if r["hallazgos"] is not None and len(r["hallazgos"]):
            print(r["hallazgos"].to_string())
