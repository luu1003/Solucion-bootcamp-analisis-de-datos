# -*- coding: utf-8 -*-
"""
Paquete de Power BI del Dashboard principal · ACTHO

Genera un Power BI Project (PBIP) que se abre en Power BI Desktop (Windows) con:
  * Modelo semántico en TMDL: tablas Empresas, Asistencia, Encuestas y Beneficios (relacionadas por la
    empresa) y las medidas del tablero (afiliados activos, vencimientos, uso de beneficios, renovación,
    satisfacción, NPS y riesgo), con las mismas definiciones que el tablero en Streamlit.
  * Informe en formato PBIR con dos páginas: "Dashboard" (segmentaciones, tarjetas y gráficos) y
    "Renovaciones" (lista priorizada). Tema con los colores de ACTHO.
  * Los datos en CSV (carpeta datos/) y el parámetro CarpetaDatos que apunta a ella.

Uso desde el tablero: botón "Ver en Power BI" del Dashboard.
Uso por consola (escribe la carpeta sin abrir el tablero):
    python frontend/tablero/powerbi.py --salida powerbi/
"""
from __future__ import annotations

import io
import json
import uuid
import zipfile
from pathlib import Path

import pandas as pd

NOMBRE = "ACTHO_Dashboard"
CARPETA_DEFECTO = "C:\\ACTHO_PowerBI\\datos\\"
NS = uuid.UUID("6f1c8a52-3a0e-4f53-9a51-7c1b8f2d4e10")
ESQ = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
V_REPORT, V_PAGE, V_VISUAL = "3.1.0", "2.0.0", "2.5.0"

MORADO, NARANJA, LAVANDA, CIAN, TINTA, MENTA = "#5B00D9", "#FF5A0F", "#9D75FF", "#0B8199", "#1B1235", "#EEF6F5"

TEMA = {
    "name": "ACTHO",
    "dataColors": [MORADO, NARANJA, CIAN, LAVANDA, "#2B0A6B", "#FF9A66", "#C9B2FF", "#8AE6F7"],
    "background": "#FFFFFF", "foreground": TINTA, "tableAccent": MORADO,
    "good": MORADO, "neutral": LAVANDA, "bad": NARANJA,
    "maximum": MORADO, "center": LAVANDA, "minimum": "#EFE6FF",
    "textClasses": {
        "title": {"fontFace": "Segoe UI Semibold", "fontSize": 13, "color": MORADO},
        "header": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": TINTA},
        "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": "#5E5876"},
        "callout": {"fontFace": "Segoe UI Bold", "fontSize": 28, "color": TINTA},
    },
    "visualStyles": {
        "*": {"*": {
            "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
            "border": [{"show": False}],
            "dropShadow": [{"show": False}],
        }},
        "page": {"*": {"background": [{"color": {"solid": {"color": MENTA}}, "transparency": 0}]}},
    },
}

# ── Tablas del modelo: (nombre en el modelo, columna origen -> columna en Power BI, tipo) ─────────────────
# tipo: text | int | number | date
TABLAS = {
    "Empresas": [
        ("empresa_id", "Empresa", "text"), ("nivel_2027", "Nivel 2027", "text"),
        ("tipo_membresia", "Tipo de afiliado", "text"), ("sector", "Sector", "text"), ("ciudad", "Ciudad", "text"),
        ("tamano_empresa", "Tamaño", "text"), ("ejecutiva", "Ejecutiva", "text"),
        ("estado_membresia", "Estado de la membresía", "text"), ("es_activo", "Es activo", "int"),
        ("es_vigente", "Es vigente", "int"), ("fecha_afiliacion", "Fecha de afiliación", "date"),
        ("fecha_expiracion", "Fecha de expiración", "date"), ("dias_a_vencer", "Días a vencer", "int"),
        ("rango_vencimiento", "Rango de vencimiento", "text"), ("mes_venc", "Mes de vencimiento", "text"),
        ("vence_12m", "Vence en 12 meses", "int"), ("prioridad", "Prioridad renovación", "int"),
        ("riesgo", "Riesgo", "text"), ("puntaje_riesgo", "Puntaje de riesgo", "int"),
        ("usa_90", "Usa beneficios 90 días", "int"), ("usa_12", "Usa beneficios 12 meses", "int"),
        ("inscripciones_12m", "Asistencias 12 meses", "int"), ("personas_distintas", "Personas que participan", "int"),
        ("satisfaccion_promedio", "Satisfacción promedio", "number"), ("renovacion_aprox", "Renovación", "text"),
        ("motivos_riesgo", "Motivos de riesgo", "text"), ("en_crm", "En CRM", "int"),
    ],
    "Asistencia": [
        ("asistencia_id", "Inscripción", "int"), ("empresa_id", "Empresa", "text"), ("persona_id", "Persona", "text"),
        ("evento", "Evento", "text"), ("fecha_evento", "Fecha del evento", "date"), ("anio_mes", "Mes", "text"),
        ("linea_2027", "Línea 2027", "text"), ("modalidad", "Modalidad", "text"), ("nivel_cargo", "Nivel de cargo", "text"),
        ("condicion_empresa", "Condición de la empresa", "text"),
    ],
    "Encuestas": [
        ("encuesta_id", "Respuesta", "int"), ("empresa_id", "Empresa", "text"), ("fecha_respuesta", "Fecha de respuesta", "date"),
        ("anio_mes", "Mes", "text"), ("satisfaccion", "Satisfacción", "number"), ("nps_puntaje", "NPS", "int"),
        ("nps_categoria", "Categoría NPS", "text"), ("origen_encuesta", "Origen", "text"),
    ],
    "Beneficios": [
        ("uso_id", "Uso", "int"), ("empresa_id", "Empresa", "text"), ("servicio", "Beneficio", "text"),
        ("linea_servicio", "Línea del beneficio", "text"), ("fecha", "Fecha", "date"), ("anio_mes", "Mes", "text"),
        ("fuente", "Fuente", "text"), ("es_fechado", "Fechado", "int"), ("cantidad", "Cantidad", "int"),
    ],
}
ARCHIVO = {"Empresas": "empresas.csv", "Asistencia": "asistencia.csv", "Encuestas": "encuestas.csv", "Beneficios": "beneficios.csv"}

MEDIDAS = [  # (nombre, DAX, formato)
    ("Afiliados activos", "CALCULATE(COUNTROWS(Empresas), Empresas[Es activo] = 1)", "#,0"),
    ("Afiliados vigentes", "CALCULATE(COUNTROWS(Empresas), Empresas[Es vigente] = 1)", "#,0"),
    ("Vencen en 90 días", "CALCULATE(COUNTROWS(Empresas), Empresas[Es vigente] = 1, Empresas[Días a vencer] >= 0, "
                          "Empresas[Días a vencer] <= 90)", "#,0"),
    ("Vencimientos 12 meses", "CALCULATE(COUNTROWS(Empresas), Empresas[Vence en 12 meses] = 1)", "#,0"),
    ("Uso de beneficios", "DIVIDE(CALCULATE(COUNTROWS(Empresas), Empresas[Es vigente] = 1, "
                          "Empresas[Usa beneficios 90 días] = 1), [Afiliados vigentes])", "0.0%;-0.0%;0.0%"),
    ("Riesgo alto", "CALCULATE(COUNTROWS(Empresas), Empresas[Riesgo] = \"Alto\")", "#,0"),
    ("Tasa de renovación", "DIVIDE(CALCULATE(COUNTROWS(Empresas), Empresas[Renovación] = \"Renovó\"), "
                           "CALCULATE(COUNTROWS(Empresas), Empresas[Renovación] IN {\"Renovó\", \"No renovó\"}))",
     "0.0%;-0.0%;0.0%"),
    ("Satisfacción", "AVERAGE(Encuestas[Satisfacción])", "0.00"),
    ("NPS de eventos", "VAR n = COUNT(Encuestas[NPS]) VAR p = CALCULATE(COUNTROWS(Encuestas), Encuestas[Categoría NPS] = "
                       "\"Promotor\") VAR d = CALCULATE(COUNTROWS(Encuestas), Encuestas[Categoría NPS] = \"Detractor\") "
                       "RETURN IF(n > 0, 100 * DIVIDE(p - d, n))", "0"),
    ("Inscripciones", "COUNTROWS(Asistencia)", "#,0"),
    ("Usos de beneficios", "SUM(Beneficios[Cantidad])", "#,0"),
]


def _tag(*partes) -> str:
    return str(uuid.uuid5(NS, "/".join(partes)))


def _q(nombre: str) -> str:
    """Nombre TMDL: entre comillas simples si tiene espacios o caracteres especiales."""
    return nombre if nombre.replace("_", "").isalnum() and nombre.isascii() else "'" + nombre.replace("'", "''") + "'"


# ──────────────────────────────────────────────────────────────────────────────
# Datos
# ──────────────────────────────────────────────────────────────────────────────
def preparar_datos(e: pd.DataFrame, a: pd.DataFrame, r: pd.DataFrame, u: pd.DataFrame, corte) -> dict:
    corte = pd.Timestamp(corte)
    e = e.copy()
    fx = pd.to_datetime(e["fecha_expiracion"])
    e["vence_12m"] = ((e["es_vigente"] == 1) & fx.notna() & (fx <= corte + pd.DateOffset(months=12))).astype(int)
    e["prioridad"] = ((e["es_vigente"] == 1) & ((e["dias_a_vencer"] <= 90) | (e["rango_vencimiento"] == "Vencida"))).astype(int)
    e["riesgo"] = e["semaforo"].map({"Rojo": "Alto", "Amarillo": "Medio", "Verde": "Bajo"}).fillna("No aplica")
    e["usa_90"] = e["participa_en_ventana"].fillna(False).astype(bool).astype(int)
    e["usa_12"] = e["usa_beneficio_12m"].fillna(False).astype(bool).astype(int) if "usa_beneficio_12m" in e else 0
    r = r.copy()
    r["satisfaccion"] = r["satisfaccion_general"].fillna(r["satisfaccion_prom"])
    fuentes = {"Empresas": e, "Asistencia": a, "Encuestas": r, "Beneficios": u}
    salida = {}
    for tabla, cols in TABLAS.items():
        df = fuentes[tabla]
        out = pd.DataFrame({destino: df[origen] if origen in df else None for origen, destino, _ in cols})
        for _, destino, tipo in cols:
            if tipo == "date":
                out[destino] = pd.to_datetime(out[destino], errors="coerce").dt.strftime("%Y-%m-%d")
            elif tipo == "int":
                out[destino] = pd.to_numeric(out[destino], errors="coerce").round().astype("Int64")
            elif tipo == "number":
                out[destino] = pd.to_numeric(out[destino], errors="coerce").round(4)
        salida[tabla] = out
    return salida


# ──────────────────────────────────────────────────────────────────────────────
# Modelo semántico (TMDL)
# ──────────────────────────────────────────────────────────────────────────────
TIPO_TMDL = {"text": "string", "int": "int64", "number": "double", "date": "dateTime"}
TIPO_M = {"text": "type text", "int": "Int64.Type", "number": "type number", "date": "type date"}


def tmdl_tabla(tabla: str) -> str:
    cols = TABLAS[tabla]
    L = [f"table {tabla}", f"\tlineageTag: {_tag('tabla', tabla)}", ""]
    if tabla == "Empresas":
        for nombre, dax, formato in MEDIDAS:
            L += [f"\tmeasure {_q(nombre)} = {dax}", f"\t\tformatString: {formato}",
                  f"\t\tlineageTag: {_tag('medida', nombre)}", ""]
    for _, destino, tipo in cols:
        L += [f"\tcolumn {_q(destino)}", f"\t\tdataType: {TIPO_TMDL[tipo]}"]
        if tipo == "date":
            L.append("\t\tformatString: dd/MM/yyyy")
        elif tipo == "int":
            L.append("\t\tformatString: 0")
        L += [f"\t\tlineageTag: {_tag('columna', tabla, destino)}", "\t\tsummarizeBy: none",
              f"\t\tsourceColumn: {destino}", "", "\t\tannotation SummarizationSetBy = Automatic", ""]
    tipos = ", ".join('{"' + d + '", ' + TIPO_M[t] + "}" for _, d, t in cols)
    L += [f"\tpartition {tabla} = m", "\t\tmode: import", "\t\tsource =",
          "\t\t\t\tlet",
          f'\t\t\t\t    Origen = Csv.Document(File.Contents(CarpetaDatos & "{ARCHIVO[tabla]}"), '
          '[Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
          "\t\t\t\t    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),",
          f'\t\t\t\t    Tipos = Table.TransformColumnTypes(Encabezados, {{{tipos}}}, "en-US")',
          "\t\t\t\tin", "\t\t\t\t    Tipos", "", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(L)


def archivos_modelo(carpeta_datos: str) -> dict:
    sm = f"{NOMBRE}.SemanticModel"
    tablas = list(TABLAS)
    f = {
        f"{sm}/definition.pbism": json.dumps({"version": "4.0", "settings": {}}, indent=2),
        f"{sm}/.platform": json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "SemanticModel", "displayName": NOMBRE},
            "config": {"version": "2.0", "logicalId": _tag("logical", "modelo")}}, indent=2),
        f"{sm}/definition/database.tmdl": "database\n\tcompatibilityLevel: 1567\n\n",
        f"{sm}/definition/model.tmdl": "\n".join([
            "model Model", "\tculture: es-CO", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
            "\tsourceQueryCulture: es-CO", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
            "annotation PBI_QueryOrder = " + json.dumps(["CarpetaDatos"] + tablas, ensure_ascii=False), "",
            *[f"ref table {t}" for t in tablas], ""]),
        f"{sm}/definition/expressions.tmdl": "\n".join([
            f'expression CarpetaDatos = "{carpeta_datos}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
            f"\tlineageTag: {_tag('parametro', 'CarpetaDatos')}", "", "\tannotation PBI_ResultType = Text", ""]),
        f"{sm}/definition/relationships.tmdl": "\n".join(
            sum([[f"relationship {_tag('relacion', t)}", f"\tfromColumn: {t}.Empresa", "\ttoColumn: Empresas.Empresa", ""]
                 for t in ["Asistencia", "Encuestas", "Beneficios"]], [])),
    }
    for t in tablas:
        f[f"{sm}/definition/tables/{t}.tmdl"] = tmdl_tabla(t)
    return f


# ──────────────────────────────────────────────────────────────────────────────
# Informe (PBIR)
# ──────────────────────────────────────────────────────────────────────────────
def _lit(v) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


def _col(ent, prop) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": prop}}


def _med(prop) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "Empresas"}}, "Property": prop}}


def _proy(campo, activo=None) -> dict:
    ent = campo[list(campo)[0]]["Expression"]["SourceRef"]["Entity"]
    p = {"field": campo, "queryRef": f"{ent}.{campo[list(campo)[0]]['Property']}"}
    if activo is not None:
        p["active"] = activo
    return p


def _titulo(texto) -> dict:
    return {"title": [{"properties": {"show": _lit("true"), "text": _lit("'" + texto.replace("'", "''") + "'"),
                                      "fontColor": {"solid": {"color": _lit(f"'{MORADO}'")}}}}]}


def _colores(ent, prop, mapa) -> list:
    return [{"properties": {"fill": {"solid": {"color": _lit(f"'{color}'")}}},
             "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": _col(ent, prop),
                                                               "Right": {"Literal": {"Value": f"'{valor}'"}}}}}]}}
            for valor, color in mapa.items()]


def _visual(nombre, x, y, w, h, z, tipo, consulta=None, titulo=None, objetos=None, orden=None, filtros=None):
    v = {"visualType": tipo, "drillFilterOtherVisuals": True}
    if consulta:
        v["query"] = {"queryState": {rol: {"projections": proy} for rol, proy in consulta.items()}}
        if orden:
            v["query"]["sortDefinition"] = {"sort": [{"field": orden[0], "direction": orden[1]}]}
    if objetos:
        v["objects"] = objetos
    if titulo:
        v["visualContainerObjects"] = _titulo(titulo)
    d = {"$schema": f"{ESQ}/visualContainer/{V_VISUAL}/schema.json", "name": nombre,
         "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z}, "visual": v}
    if filtros:
        d["filterConfig"] = {"filters": filtros}
    return d


def _texto(nombre, x, y, w, h, z, titulo, sub):
    corrida = lambda t, tam, color, peso=None: {"value": t, "textStyle": dict(
        {"fontFamily": "Segoe UI", "fontSize": tam, "color": color}, **({"fontWeight": peso} if peso else {}))}
    return {"$schema": f"{ESQ}/visualContainer/{V_VISUAL}/schema.json", "name": nombre,
            "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
            "visual": {"visualType": "textbox", "drillFilterOtherVisuals": True,
                       "objects": {"general": [{"properties": {"paragraphs": [
                           {"textRuns": [corrida(titulo, "22pt", TINTA, "bold")]},
                           {"textRuns": [corrida(sub, "11pt", "#5E5876")]}]}}]}}}


def _segmentaciones(prefijo, y):
    campos = [("Nivel 2027", "Nivel 2027"), ("Tipo de afiliado", "Tipo de afiliado"), ("Sector", "Sector"),
              ("Ciudad", "Ciudad"), ("Ejecutiva", "Ejecutiva")]
    out = []
    for i, (prop, tit) in enumerate(campos):
        out.append(_visual(f"{prefijo}seg{i}", 16 + i * 250, y, 240, 64, 1000 + i, "slicer",
                           {"Values": [_proy(_col("Empresas", prop), True)]}, titulo=tit,
                           objetos={"data": [{"properties": {"mode": _lit("'Dropdown'")}}]}))
    return out


RIESGO_COLOR = {"Alto": NARANJA, "Medio": LAVANDA, "Bajo": MORADO}


def pagina_dashboard() -> tuple[dict, list]:
    pid = "dashboard0000000001"
    vis = [_texto("titulo", 16, 8, 900, 64, 1, "Dashboard · ACTHO",
                  "Cómo va la asociación: afiliados, renovación, uso de beneficios, satisfacción y riesgo")]
    vis += _segmentaciones("d", 80)
    tarjetas = ["Afiliados activos", "Vencen en 90 días", "Uso de beneficios", "Tasa de renovación", "NPS de eventos", "Riesgo alto"]
    for i, m in enumerate(tarjetas):
        vis.append(_visual(f"tarjeta{i}", 16 + i * 208, 160, 196, 110, 2000 + i, "card",
                           {"Values": [_proy(_med(m))]}, titulo=m))
    vis.append(_visual("vencimientos", 16, 286, 740, 330, 3000, "columnChart",
                       {"Category": [_proy(_col("Empresas", "Mes de vencimiento"), True)],
                        "Series": [_proy(_col("Empresas", "Riesgo"))],
                        "Y": [_proy(_med("Vencimientos 12 meses"))]},
                       titulo="Vencimientos de los próximos 12 meses por nivel de riesgo",
                       objetos={"dataPoint": _colores("Empresas", "Riesgo", RIESGO_COLOR)},
                       orden=(_col("Empresas", "Mes de vencimiento"), "Ascending")))
    vis.append(_visual("semaforo", 772, 286, 492, 330, 3001, "donutChart",
                       {"Category": [_proy(_col("Empresas", "Riesgo"), True)], "Y": [_proy(_med("Afiliados vigentes"))]},
                       titulo="Semáforo de riesgo (vigentes)",
                       objetos={"dataPoint": _colores("Empresas", "Riesgo", RIESGO_COLOR)}))
    vis.append(_visual("participacion", 16, 632, 620, 320, 3002, "columnChart",
                       {"Category": [_proy(_col("Asistencia", "Mes"), True)],
                        "Series": [_proy(_col("Asistencia", "Condición de la empresa"))],
                        "Y": [_proy(_med("Inscripciones"))]},
                       titulo="Participación en experiencias por mes",
                       objetos={"dataPoint": _colores("Asistencia", "Condición de la empresa",
                                                      {"Afiliada": MORADO, "No afiliada": CIAN})},
                       orden=(_col("Asistencia", "Mes"), "Ascending")))
    vis.append(_visual("beneficios", 652, 632, 612, 320, 3003, "clusteredBarChart",
                       {"Category": [_proy(_col("Beneficios", "Beneficio"), True)], "Y": [_proy(_med("Usos de beneficios"))]},
                       titulo="Uso de beneficios por servicio", orden=(_med("Usos de beneficios"), "Descending")))
    vis.append(_visual("satisfaccion", 16, 968, 620, 280, 3004, "lineChart",
                       {"Category": [_proy(_col("Encuestas", "Mes"), True)], "Y": [_proy(_med("Satisfacción"))]},
                       titulo="Satisfacción mensual (1 a 5)", orden=(_col("Encuestas", "Mes"), "Ascending")))
    vis.append(_visual("niveles", 652, 968, 612, 280, 3005, "clusteredBarChart",
                       {"Category": [_proy(_col("Empresas", "Nivel 2027"), True)], "Y": [_proy(_med("Afiliados vigentes"))]},
                       titulo="Afiliados vigentes por nivel 2027", orden=(_med("Afiliados vigentes"), "Descending")))
    pagina = {"$schema": f"{ESQ}/page/{V_PAGE}/schema.json", "name": pid, "displayName": "Dashboard",
              "displayOption": "FitToWidth", "height": 1264, "width": 1280}
    return pagina, vis


def pagina_renovaciones() -> tuple[dict, list]:
    pid = "renovaciones000000002"
    vis = [_texto("titulo2", 16, 8, 900, 64, 1, "Renovaciones prioritarias",
                  "Vigentes que vencen en 90 días o ya vencidas, ordenadas por puntaje de riesgo")]
    vis += _segmentaciones("r", 80)
    cols = ["Empresa", "Ejecutiva", "Nivel 2027", "Fecha de expiración", "Días a vencer", "Riesgo", "Puntaje de riesgo",
            "Asistencias 12 meses", "Motivos de riesgo"]
    filtro = [{"name": "filtroPrioridad", "field": _col("Empresas", "Prioridad renovación"), "type": "Categorical",
               "filter": {"Version": 2, "From": [{"Name": "e", "Entity": "Empresas", "Type": 0}],
                          "Where": [{"Condition": {"In": {
                              "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "e"}},
                                                          "Property": "Prioridad renovación"}}],
                              "Values": [[{"Literal": {"Value": "1L"}}]]}}}]}}]
    vis.append(_visual("tabla", 16, 160, 1248, 560, 2000, "tableEx",
                       {"Values": [_proy(_col("Empresas", c)) for c in cols]}, titulo="Calendario de renovaciones",
                       orden=(_col("Empresas", "Puntaje de riesgo"), "Descending"), filtros=filtro))
    pagina = {"$schema": f"{ESQ}/page/{V_PAGE}/schema.json", "name": pid, "displayName": "Renovaciones",
              "displayOption": "FitToPage", "height": 736, "width": 1280}
    return pagina, vis


def archivos_informe(tema_base: dict | None = None) -> dict:
    rp = f"{NOMBRE}.Report"
    version_tema = {"visual": V_VISUAL, "page": V_PAGE, "report": V_REPORT}
    report = {"$schema": f"{ESQ}/report/{V_REPORT}/schema.json",
              "themeCollection": {"customTheme": {"name": "ACTHO.json", "reportVersionAtImport": version_tema,
                                                  "type": "RegisteredResources"}},
              "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                                    "items": [{"name": "ACTHO.json", "path": "ACTHO.json", "type": "CustomTheme"}]}],
              "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True}}
    if tema_base:
        report["themeCollection"]["baseTheme"] = {"name": tema_base["name"], "reportVersionAtImport": version_tema,
                                                  "type": "SharedResources"}
        report["resourcePackages"].insert(0, {"name": "SharedResources", "type": "SharedResources", "items": [
            {"name": tema_base["name"], "path": f"BaseThemes/{tema_base['name']}.json", "type": "BaseTheme"}]})
    f = {
        f"{rp}/definition.pbir": json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOMBRE}.SemanticModel"}}}, indent=2),
        f"{rp}/.platform": json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "Report", "displayName": NOMBRE},
            "config": {"version": "2.0", "logicalId": _tag("logical", "informe")}}, indent=2),
        f"{rp}/definition/version.json": json.dumps({
            "$schema": f"{ESQ}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2),
        f"{rp}/definition/report.json": json.dumps(report, indent=2, ensure_ascii=False),
        f"{rp}/StaticResources/RegisteredResources/ACTHO.json": json.dumps(TEMA, indent=2, ensure_ascii=False),
    }
    if tema_base:
        f[f"{rp}/StaticResources/SharedResources/BaseThemes/{tema_base['name']}.json"] = json.dumps(tema_base["contenido"])
    paginas = [pagina_dashboard(), pagina_renovaciones()]
    f[f"{rp}/definition/pages/pages.json"] = json.dumps({
        "$schema": f"{ESQ}/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p["name"] for p, _ in paginas], "activePageName": paginas[0][0]["name"]}, indent=2)
    for pagina, visuales in paginas:
        base = f"{rp}/definition/pages/{pagina['name']}"
        f[f"{base}/page.json"] = json.dumps(pagina, indent=2, ensure_ascii=False)
        for v in visuales:
            f[f"{base}/visuals/{v['name']}/visual.json"] = json.dumps(v, indent=2, ensure_ascii=False)
    return f


LEEME = """ACTHO · Dashboard en Power BI
==============================

Contenido
  ACTHO_Dashboard.pbip            Ábrelo con Power BI Desktop (Windows, versión de 2026 o posterior).
  ACTHO_Dashboard.SemanticModel   Modelo: tablas Empresas, Asistencia, Encuestas y Beneficios, y las medidas.
  ACTHO_Dashboard.Report          Informe con dos páginas: Dashboard y Renovaciones. Tema con los colores de ACTHO.
  datos/                          Los datos del tablero en CSV (corte {corte}{filtro}).
  tema_actho.json                 El tema de colores, por si quieres aplicarlo a otro informe.

Cómo abrirlo
  1. Descomprime el ZIP directamente en C:\\ para que quede la carpeta C:\\ACTHO_PowerBI\\
     (el modelo busca los datos en C:\\ACTHO_PowerBI\\datos\\).
     Si lo descomprimes en otra carpeta: Inicio > Transformar datos > Editar parámetros >
     CarpetaDatos, y escribe la ruta de la carpeta datos terminada en \\.
  2. Abre ACTHO_Dashboard.pbip con Power BI Desktop y pulsa "Actualizar" para cargar los datos.
  3. Los gráficos se filtran entre sí al hacer clic, como en el tablero; las segmentaciones de arriba
     filtran por nivel, tipo de afiliado, sector, ciudad y ejecutiva.

Notas
  * Power BI Desktop solo existe para Windows. En Mac se puede abrir en una máquina virtual con Windows.
  * Las medidas usan las mismas definiciones del tablero (ver la página "Datos y calidad").
  * "Tasa de renovación" es la aproximada hasta que haya dos fotos mensuales de las membresías.
  * Para conectarlo directo a PostgreSQL en lugar de los CSV, cambia el origen de cada tabla por
    PostgreSQL.Database("servidor", "actho") y las vistas actho.v_empresa_360, v_asistencia_detalle,
    v_encuesta_detalle y v_uso_beneficio_detalle.
"""


def construir_zip(datos: dict, corte, nota_filtro="", carpeta_datos=CARPETA_DEFECTO, tema_base=None) -> bytes:
    """datos: salida de preparar_datos(). Devuelve el ZIP con la carpeta ACTHO_PowerBI/."""
    raiz = "ACTHO_PowerBI"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{raiz}/{NOMBRE}.pbip", json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0", "artifacts": [{"report": {"path": f"{NOMBRE}.Report"}}],
            "settings": {"enableAutoRecovery": True}}, indent=2))
        for ruta, contenido in {**archivos_modelo(carpeta_datos), **archivos_informe(tema_base)}.items():
            z.writestr(f"{raiz}/{ruta}", contenido)
        for tabla, df in datos.items():
            z.writestr(f"{raiz}/datos/{ARCHIVO[tabla]}", df.to_csv(index=False, encoding="utf-8"))
        z.writestr(f"{raiz}/tema_actho.json", json.dumps(TEMA, indent=2, ensure_ascii=False))
        z.writestr(f"{raiz}/LEEME.txt", LEEME.format(corte=pd.Timestamp(corte).strftime("%d/%m/%Y"), filtro=nota_filtro))
    return buf.getvalue()


def tema_base_local() -> dict | None:
    """Tema base de Power BI si está en recursos/ (opcional)."""
    ruta = Path(__file__).parent / "recursos" / "powerbi_tema_base.json"
    if ruta.exists():
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
        return {"name": contenido.get("name", "CY24SU10"), "contenido": contenido}
    return None


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser(description="Escribe el proyecto de Power BI del Dashboard")
    ap.add_argument("--salida", default="powerbi")
    args = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    import psycopg
    from cargar_postgres import cadena_conexion
    with psycopg.connect(cadena_conexion()) as conn:
        leer = lambda sql: pd.DataFrame(conn.execute(sql).fetchall(), columns=[d.name for d in conn.execute(sql).description])
        e = leer("SELECT * FROM actho.v_empresa_360")
        a = leer("SELECT * FROM actho.v_asistencia_detalle")
        r = leer("SELECT * FROM actho.v_encuesta_detalle")
        u = leer("SELECT * FROM actho.v_uso_beneficio_detalle")
        corte = conn.execute("SELECT fecha_corte FROM actho.v_parametros").fetchone()[0]
    fx = pd.to_datetime(e["fecha_expiracion"])
    e["mes_venc"] = fx.where(fx >= pd.Timestamp(corte), pd.Timestamp(corte)).dt.strftime("%Y-%m").where(fx.notna())
    contenido = construir_zip(preparar_datos(e, a, r, u, corte), corte, tema_base=tema_base_local())
    destino = Path(args.salida)
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        z.extractall(destino)
    print(f"Proyecto de Power BI escrito en {destino.resolve() / 'ACTHO_PowerBI'}")
