#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Limpieza y unificación de datos · Reto ACTHO (Tablero integral de afiliados)

Lee las exportaciones originales de la carpeta Datos/ y genera en salida/ un
conjunto de tablas limpias y relacionadas (modelo en estrella), un reporte de
calidad y un diccionario de datos.

Uso:
    python3 src/limpieza_datos.py
    python3 src/limpieza_datos.py --fecha-corte 2026-11-21

Reglas de limpieza (resumen; el detalle queda en salida/reporte_calidad.csv):
  * Texto: tildes dañadas (mojibake), espacios, mayúsculas y variantes.
  * Nulos: categorías vacías -> 'Sin dato'; fechas y números vacíos se dejan
    vacíos (no se inventan); algunos vacíos se derivan de otro campo.
  * Atípicos: fechas imposibles, calificaciones fuera de rango, porcentajes
    fuera de 0-100, valores extremos por rango intercuartílico (se marcan).
  * Identificadores: formato EMP-#### / P-##### y duplicados.
  * Registros de prueba y duplicados: se excluyen y quedan en salida/excluidos_crm.csv.

Los datos son confidenciales (NDA del reto): Datos/ y salida/ están en .gitignore.
"""
from __future__ import annotations

import argparse
import re
import unicodedata
import warnings
from pathlib import Path

try:
    import numpy as np
    import openpyxl
    import pandas as pd
except ModuleNotFoundError as e:  # mensaje claro si falta una librería
    raise SystemExit(
        f"Falta la librería '{e.name}' en este Python ({__import__('sys').executable}).\n"
        f"Instálala con:  {__import__('sys').executable} -m pip install -r requirements.txt"
    )

warnings.filterwarnings("ignore")

RAIZ = Path(__file__).resolve().parent.parent

# ──────────────────────────────────────────────────────────────────────────────
# Configuración
# ──────────────────────────────────────────────────────────────────────────────
ARCHIVOS = {
    "crm": "1. Base de datos de afiliados/Base de datos Hackaton_anonimizada.xlsx",
    "asistencia": "2. Registros de participación en actividades/BASE ASISTENCIA A EVENTOS 2026 - EAFIT_anonimizada.xlsx",
    "enc_presencial": "3. Encuestas y NPS/Eventos Presenciales 2026_anonimizada.xlsx",
    "enc_virtual": "3. Encuestas y NPS/Eventos Virtuales ACRIP 2026_anonimizada.xlsx",
    "enc_post": "3. Encuestas y NPS/ENCUESTA-POST-EVENTOS (PRESENCIAL Y VIRTUAL)_anonimizada.xlsx",
    "principal": "5. Indicadores y reportes actuales/Base de datos afiliados ACTHO_anonimizada.xlsx",
}
# Fuentes opcionales: si no están, sus tablas quedan vacías y el tablero muestra "listo para recibir".
ARCHIVOS_OPCIONALES = {
    "enc_90d": "3. Encuestas y NPS/90 días - NPS_sin respuestas (instrumento).xlsx",
    "uso_beneficios": "8. Uso de beneficios/uso_beneficios.xlsx",
}

# ── Catálogo de servicios de la oferta 2027 (documento "Servicios y equivalencias con los datos") ──
# incluido_*: 1 si el servicio viene incluido en ese nivel. fuente_dato: dónde queda registro hoy.
# opcion_90d: opción de la pregunta 3.1 de la encuesta de 90 días que lo representa.
CATALOGO_SERVICIOS = [
    # id, servicio, línea, descripción, conectar, crecer, liderar, condición, fuente_dato, opcion_90d
    ("S01", "Actho Legislativo", "Anticipar", "Webinar legal sobre cambios en la norma laboral", 1, 1, 1,
     "Espacios VIP con abogados y autoridades solo en Liderar", "Asistencia", "Actualización legal"),
    ("S02", "Actho en Marcha (boletín)", "Anticipar", "Boletín quincenal con alerta legal y novedades de IA", 0, 1, 1,
     "Solo afiliados", "Plantilla mensual", "Boletin"),
    ("S03", "Actho de Creación", "Anticipar", "Laboratorio práctico de IA aplicada al trabajo", 1, 1, 1,
     "Activa la comunidad Talento Aumentado", "Asistencia", "Formación"),
    ("S04", "GetAbstract y AI tip del mes", "Anticipar", "Resúmenes de libros de negocios y consejo mensual de IA", 1, 1, 1,
     "Para toda la empresa afiliada", "Plantilla mensual", "Contenidos"),
    ("S05", "Otros espacios de Anticipar", "Anticipar", "Webinars y foros temáticos de la línea Anticipar", 1, 1, 1,
     "", "Asistencia", ""),
    ("S06", "Actho de Valentía", "Pares", "Círculo cerrado donde la alta dirección comparte aprendizajes", 0, 0, 1,
     "C-level, por invitación", "Asistencia", ""),
    ("S07", "Actho de Autoridad", "Pares", "Conversación cercana con un líder de alto nivel", 0, 0, 1,
     "C-level y VP", "Asistencia", ""),
    ("S08", "Actho de Liderar", "Pares", "Experiencias vivenciales de liderazgo", 0, 0, 1,
     "Conectar y Crecer con costo adicional", "Asistencia", "Networking"),
    ("S09", "Comunidades", "Pares", "Siete grupos temáticos de conversación entre pares", 1, 1, 1,
     "", "CRM y asistencia", "Comunidades"),
    ("S10", "Actho de Evidencia", "Saber", "Mediciones nacionales de clima, bienestar y compensación", 0, 1, 1,
     "En construcción; co-creación en Crecer y Liderar", "Sin registro", ""),
    ("S11", "Actho de Presencia", "Proyectar", "Newsletter en LinkedIn con la columna de un líder", 0, 1, 1,
     "", "Plantilla mensual", ""),
    ("S12", "Actho Seguido (podcast)", "Proyectar", "Podcast de ACTHO", 0, 0, 1, "", "Plantilla mensual", ""),
    ("S13", "Sello ACTHO", "Acompañar", "Distintivo de empresa afiliada", 1, 1, 1, "", "Plantilla mensual", "Sello ACTHO"),
    ("S14", "Actho de Rumbo y primeros 90 días", "Acompañar", "Bienvenida, diagnóstico y conexión con consultores", 1, 1, 1,
     "Solo empresas", "Plantilla mensual", ""),
    ("S15", "Eventos grandes", "Transversal", "Foro híbrido, Semana del Talento, HR Global Day y Cumbre Laboral", 0, 1, 1,
     "1 entrada por evento en Crecer, 2 en Liderar; Conectar con tarifa de afiliado", "Asistencia", "Eventos"),
    ("S16", "Foros", "Transversal", "Foros de Gestión Humana y de Soluciones", 1, 1, 1, "", "Asistencia", ""),
    ("S17", "Centro de Experiencias en Bogotá", "Transversal", "Espacio para eventos, talleres, comités y podcast", 0, 0, 0,
     "Tarifa de afiliado en todos; descuento en Crecer y Liderar", "Plantilla mensual", ""),
    ("S99", "Otro beneficio (autodeclarado)", "Otro", "Beneficio indicado como 'Otro' en la encuesta de 90 días", 0, 0, 0,
     "", "Encuesta 90 días", "Otros (especifique)"),
]
EXPERIENCIA_SERVICIO = {"actho legislativo": "S01", "actho de liderar": "S08", "actho de autoridad": "S07",
                        "actho de valentia": "S06", "actho de creacion": "S03"}
LINEA_SERVICIO = {"evento grande": "S15", "foro": "S16", "anticipar": "S05", "pares": "S09"}

COLUMNAS_CRM = {
    "ID de registro [anonimizado]": "registro_id",
    "Propietario de Empresa [anonimizado]": "ejecutiva",
    "Nombre de Empresa [anonimizado]": "empresa_id",
    "Tipo de Empresa": "tipo_empresa",
    "Ciudad de facturación": "ciudad_facturacion",
    "País de facturación": "pais",
    "Etiqueta": "etiqueta",
    "Región": "region",
    "Tipo de Compañía": "tipo_compania",
    "Estado": "estado_registro",
    "Fecha de Afiliación": "fecha_afiliacion",
    "Independiente": "independiente",
    "Cantidad de Empleados": "rango_empleados",
    "Sector Económico": "sector",
    "Departamento": "departamento",
    "Ciudad": "ciudad",
    "Subsector Económico [anonimizado]": "subsector",
    "Tipo de Membresía": "tipo_membresia",
    "Categoría de Membresía": "categoria_membresia",
    "Tipo de Consultora": "tipo_consultora",
    "% de Mujeres en la Compañía": "pct_mujeres",
    "Fecha de Expiración Afiliación": "fecha_expiracion",
    "Estado de la Membresía": "estado_membresia",
    "HR Estratégico": "com_hr_estrategico",
    "Mas que un Salario": "com_mas_que_un_salario",
    "Talento que Elige": "com_talento_que_elige",
    "Gente que Crece": "com_gente_que_crece",
    "Talento Aumentado": "com_talento_aumentado",
    "Mujeres HR": "com_mujeres_hr",
    "Influenciador": "com_influenciador",
    "Tamaño de la Empresa": "tamano_empresa",
    "Miembro Desde el": "miembro_desde",
    "Vinculado a Comunidades": "vinculado_comunidades",
    "Cantidad Miembros": "cantidad_miembros",
}
COLS_COMUNIDADES = [c for c in COLUMNAS_CRM.values() if c.startswith("com_")]

# (tipo de membresía, categoría implícita). La clave se compara sin tildes y en minúscula.
TIPO_COMPUESTO = {
    "empresa": ("Empresa", None), "empresas": ("Empresa", None),
    "consultoras": ("Consultoras", None), "universidades": ("Universidades", None),
    "persona natural": ("Persona natural", None),
    "corporativa estandar": ("Empresa", "Estándar"),
    "corporativa premium": ("Empresa", "Premium"),
    "consultor/vendor estandar": ("Consultoras", "Estándar"),
    "consultor/vendor premium": ("Consultoras", "Premium"),
    "personal estandar": ("Persona natural", "Estándar"),
    "personal premium": ("Persona natural", "Premium"),
    "jovenes talentos / estudiantes": ("Persona natural", "Estudiante"),
}
# 'Estándar Colaborador' se unifica como Estándar (supuesto a confirmar con ACTHO).
CATEGORIAS = {
    "estandar": "Estándar", "estandar colaborador": "Estándar",
    "premium": "Premium", "elite": "Elite", "personal": "Personal",
}
# Equivalencia con la oferta 2027 (documento "Servicios y equivalencias").
NIVEL_2027 = {"Estándar": "Conectar", "Premium": "Crecer", "Elite": "Liderar"}

ESTADOS = {
    "activo": "Activo", "cancelado": "Cancelado", "expirado": "Expirado",
    "inactivo": "Inactivo", "periodo de gracia": "Periodo de gracia",
    "pronto a expirar": "Pronto a expirar",
}
VIGENTES = ["Activo", "Periodo de gracia", "Pronto a expirar"]
ORDEN_ESTADO = {"Activo": 0, "Pronto a expirar": 1, "Periodo de gracia": 2, "Expirado": 3,
                "Inactivo": 4, "Cancelado": 5, "Sin estado": 6}

MANUAL_CIUDAD = {"Bogotá D.C.": "Bogotá", "Bogota D.C.": "Bogotá", "Bogotá, D.C.": "Bogotá", "DC": "Bogotá"}
MANUAL_DEPTO = {"DC": "Bogotá D.C.", "Bogotá, D.C.": "Bogotá D.C.", "Bogotá": "Bogotá D.C.",
                "Atlantico": "Atlántico", "Bolivar": "Bolívar"}
DEPARTAMENTOS = {"antioquia", "cundinamarca", "valle del cauca", "atlantico", "bolivar",
                 "santander", "meta", "risaralda", "cauca"}
REGION_NORM = {"bogota": "Bogotá", "medellin": "Antioquia", "antioquia": "Antioquia",
               "cundinamarca": "Cundinamarca", "eje cafetero": "Eje Cafetero",
               "santander": "Santander", "otra": "Otra", "otro": "Otra"}
REGION_POR_DEPTO = {"Bogotá D.C.": "Bogotá", "Cundinamarca": "Cundinamarca", "Antioquia": "Antioquia"}
PAIS_NORM = {"colombia": "Colombia", "colomba": "Colombia", "guatemala": "Guatemala"}

RANGOS_EMPLEADOS = ["1-50", "51-200", "201-1.000", "1.001-5.000", "5.001-10.000", "10.001 o más"]
# Eventos de varios días (N° de evento -> días adicionales).
DURACION_EXTRA = {7: 3}
RX_ID_EMPRESA = re.compile(r"^EMP-\d{4}$")
RX_ID_PERSONA = re.compile(r"^P-\d{5}$")

# ──────────────────────────────────────────────────────────────────────────────
# Utilidades
# ──────────────────────────────────────────────────────────────────────────────
CALIDAD: list[dict] = []


def registrar(tabla, campo, problema, regla, filas, accion="Corregido"):
    """Anota un hallazgo de calidad. Si no afectó filas, no se registra."""
    if int(filas) > 0:
        CALIDAD.append(dict(tabla=tabla, campo=campo, problema=problema,
                            regla_aplicada=regla, filas_afectadas=int(filas), accion=accion))


def informar(tabla, campo, dato, valor):
    CALIDAD.append(dict(tabla=tabla, campo=campo, problema=dato, regla_aplicada="",
                        filas_afectadas=int(valor), accion="Informativo"))


def arreglar_mojibake(v):
    """'Bogotﾃ｡' -> 'Bogotá' (UTF-8 leído como cp932)."""
    if not isinstance(v, str) or not re.search(r"[｡-ﾟ]", v):
        return v
    try:
        return v.encode("cp932").decode("utf-8")
    except Exception:
        return v


def limpiar_texto(v):
    if not isinstance(v, str):
        return v
    return re.sub(r"\s+", " ", v.replace("\xa0", " ")).strip()


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")


def clave(s):
    return re.sub(r"\s+", " ", sin_tildes(s).strip().lower())


def n_tildes(s):
    return sum(1 for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) == "Mn")


def canonizar(serie, manual=None):
    """Unifica variantes (mayúsculas, tildes, espacios) usando la forma más completa."""
    manual = {clave(k): v for k, v in (manual or {}).items()}
    s = serie.dropna().astype(str)
    canon = {}
    for k, grupo in s.groupby(s.map(clave)):
        if k in manual:
            canon[k] = manual[k]
            continue
        cuentas = grupo.value_counts()
        mejor = max(cuentas.index, key=lambda x: (n_tildes(x), cuentas[x]))
        if mejor.isupper() and len(mejor) > 3:
            mejor = mejor.title()
        canon[k] = mejor
    return serie.map(lambda v: canon.get(clave(v), v) if isinstance(v, str) else v)


def cambios(antes, despues):
    a = antes.astype("object").where(antes.notna(), None)
    d = despues.astype("object").where(despues.notna(), None)
    return int(((a != d) & ~(a.isna() & d.isna())).sum())


def rellenar(df, tabla, columnas, valor="Sin dato"):
    for c in columnas:
        n = int(df[c].isna().sum())
        registrar(tabla, c, "Valores nulos",
                  f"Se rellena con '{valor}' para que los filtros no queden en blanco", n)
        df[c] = df[c].fillna(valor)


def atipicos_iqr(serie, k=1.5):
    x = pd.to_numeric(serie, errors="coerce")
    q1, q3 = x.quantile(0.25), x.quantile(0.75)
    iqr = q3 - q1
    return (x < q1 - k * iqr) | (x > q3 + k * iqr)


MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
         "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12}
RX_FECHA_ES = re.compile(
    r"([a-záéíóú]+)\.?\s+(\d{1,2}),\s+(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([ap])\.?\s*m", re.I)


def parsear_fecha_es(v):
    """'mar. 27, 2025 09:24:10 a. m.' -> Timestamp."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return pd.NaT
    if not isinstance(v, str):
        return pd.Timestamp(v)
    m = RX_FECHA_ES.search(v.replace("\xa0", " "))
    if not m:
        return pd.to_datetime(v, errors="coerce")
    txt = m.group(1).lower()
    mes = MESES.get(txt) or MESES.get(txt[:3])
    if mes is None:
        return pd.NaT
    hora = int(m.group(4)) % 12 + (12 if m.group(7).lower() == "p" else 0)
    return pd.Timestamp(int(m.group(3)), mes, int(m.group(2)), hora, int(m.group(5)), int(m.group(6) or 0))


def validar_id(serie, regex, tabla, campo):
    """Normaliza (mayúsculas, sin espacios) y anula IDs con formato inválido."""
    s = serie.map(lambda v: re.sub(r"\s+", "", v).upper() if isinstance(v, str) else v)
    malos = s.notna() & ~s.fillna("").str.match(regex)
    registrar(tabla, campo, "ID con formato inválido", "Se anula el ID (queda vacío)", malos.sum())
    return s.where(~malos, np.nan)


def si_no(v):
    """'SI', 'SÍ ', 'Sí, autorizo...', 'NO, AUTORIZO...' -> 'Sí' / 'No' / 'Sin dato'."""
    if not isinstance(v, str) or not v.strip():
        return "Sin dato"
    t = clave(v)
    if t.startswith("si"):
        return "Sí"
    if t.startswith("no"):
        return "No"
    return "Sin dato"


# ──────────────────────────────────────────────────────────────────────────────
# CRM (afiliación)
# ──────────────────────────────────────────────────────────────────────────────
def cargar_crm(ruta, corte):
    t = "crm"
    crudo = pd.read_excel(ruta).rename(columns=COLUMNAS_CRM)
    df = crudo[[c for c in COLUMNAS_CRM.values() if c in crudo.columns]].copy()
    informar(t, "(archivo)", "Registros leídos del CRM", len(df))

    # Texto: tildes dañadas, espacios, vacíos.
    moj = 0
    for c in df.select_dtypes(include="object").columns:
        antes = df[c].copy()
        df[c] = df[c].map(arreglar_mojibake).map(limpiar_texto).replace("", np.nan)
        moj += cambios(antes, df[c])
    registrar(t, "(texto)", "Tildes dañadas, espacios sobrantes o vacíos", "Se repara la codificación y se recortan espacios", moj)

    # Registros de prueba.
    prueba = df["etiqueta"].map(lambda v: clave(v) in {"prueba", "pruebas"} if isinstance(v, str) else False)
    excluidos = df[prueba].assign(motivo="Registro de prueba (etiqueta)")
    registrar(t, "etiqueta", "Registros de prueba", "Se excluyen de las tablas limpias (quedan en excluidos_crm.csv)", prueba.sum(), "Excluido")
    df = df[~prueba].drop(columns=["etiqueta"]).copy()

    df["empresa_id"] = validar_id(df["empresa_id"], RX_ID_EMPRESA, t, "empresa_id")
    df["registro_id"] = df["registro_id"].astype(str).str.strip()
    dup_reg = df["registro_id"].duplicated()
    registrar(t, "registro_id", "ID de registro repetido", "Se conserva el primero", dup_reg.sum(), "Excluido")
    df = df[~dup_reg]

    # Ejecutiva de cuenta.
    antes = df["ejecutiva"].copy()
    df["ejecutiva"] = df["ejecutiva"].map(lambda v: np.nan if (pd.isna(v) or clave(str(v)) in {"0", ""}) else limpiar_texto(str(v)))
    df["ejecutiva"] = df["ejecutiva"].fillna("Sin asignar (cuenta ACTHO)")
    registrar(t, "ejecutiva", "Propietario vacío o '0'", "Se asigna 'Sin asignar (cuenta ACTHO)'", cambios(antes, df["ejecutiva"]))

    # Ubicación.
    antes = df["ciudad"].copy()
    df["ciudad"] = canonizar(df["ciudad"], MANUAL_CIUDAD)
    df["ciudad_facturacion"] = canonizar(df["ciudad_facturacion"], MANUAL_CIUDAD)
    en_depto = df["ciudad"].map(lambda v: isinstance(v, str) and clave(v) in DEPARTAMENTOS)
    en_depto_f = df["ciudad_facturacion"].map(lambda v: isinstance(v, str) and clave(v) in DEPARTAMENTOS)
    registrar(t, "ciudad", "Ciudad con nombre de departamento", "Se anula (no es una ciudad)", en_depto.sum() + en_depto_f.sum())
    df.loc[en_depto, "ciudad"] = np.nan
    df.loc[en_depto_f, "ciudad_facturacion"] = np.nan
    sin_ciudad = df["ciudad"].isna() & df["ciudad_facturacion"].notna()
    df.loc[sin_ciudad, "ciudad"] = df.loc[sin_ciudad, "ciudad_facturacion"]
    registrar(t, "ciudad", "Ciudad vacía con ciudad de facturación", "Se completa con la ciudad de facturación", sin_ciudad.sum())
    registrar(t, "ciudad", "Variantes de escritura (Bogota/Bogotá/BOGOTA, Medellin/Medellín…)", "Se unifican por clave sin tildes", cambios(antes, df["ciudad"]) - int(sin_ciudad.sum()) - int(en_depto.sum()))

    antes = df["departamento"].copy()
    df["departamento"] = canonizar(df["departamento"], MANUAL_DEPTO)
    registrar(t, "departamento", "Variantes (DC, Bogotá D.C., sin tildes)", "Se unifican", cambios(antes, df["departamento"]))
    antes = df["pais"].copy()
    df["pais"] = df["pais"].map(lambda v: PAIS_NORM.get(clave(v), v) if isinstance(v, str) else v)
    registrar(t, "pais", "Variantes (COLOMBIA, Colomba)", "Se unifican", cambios(antes, df["pais"]))

    reg = df["region"].map(lambda v: REGION_NORM.get(clave(v), v) if isinstance(v, str) else v)
    derivada = reg.isna() & df["departamento"].notna()
    reg = reg.where(~derivada, df["departamento"].map(lambda d: REGION_POR_DEPTO.get(d) or REGION_NORM.get(clave(d), "Otra")))
    registrar(t, "region", "Región vacía con departamento", "Se deriva del departamento", derivada.sum())
    registrar(t, "region", "Variantes de escritura", "Se unifican (Medellín -> Antioquia, Otro -> Otra)", cambios(df["region"], reg) - int(derivada.sum()))
    df["region"] = reg

    for c in ["sector", "subsector"]:
        antes = df[c].copy()
        df[c] = canonizar(df[c])
        registrar(t, c, "Variantes de escritura (Tecnologia/Tecnología…)", "Se unifican por clave sin tildes", cambios(antes, df[c]))

    # Tipo y categoría de membresía (equivalencias de la oferta 2027).
    tipos, cats, swap, cat_tipo, desconocidas = [], [], 0, 0, 0
    for tr, cr in zip(df["tipo_membresia"], df["categoria_membresia"]):
        kt = clave(tr) if isinstance(tr, str) else None
        kc = clave(cr) if isinstance(cr, str) else None
        if kt in CATEGORIAS and kc in TIPO_COMPUESTO:
            kt, kc = kc, kt
            swap += 1
        tipo, impl = TIPO_COMPUESTO.get(kt, (None, None)) if kt else (None, None)
        if tipo is None and kc in TIPO_COMPUESTO:
            tipo, impl = TIPO_COMPUESTO[kc]
            cat_tipo += 1
        cat = impl or CATEGORIAS.get(kc)
        if tipo is None and cat == "Personal":
            tipo = "Persona natural"
        if cr is not None and isinstance(cr, str) and cat is None and kc not in TIPO_COMPUESTO:
            desconocidas += 1
        tipos.append(tipo)
        cats.append(cat)
    antes_t, antes_c = df["tipo_membresia"].copy(), df["categoria_membresia"].copy()
    df["tipo_membresia"], df["categoria_membresia"] = tipos, cats
    registrar(t, "tipo_membresia/categoria_membresia", "Tipo y categoría intercambiados", "Se intercambian", swap)
    registrar(t, "categoria_membresia", "La categoría traía un tipo (Empresas, Consultoras, Persona Natural)", "Se mueve a tipo de membresía", cat_tipo)
    registrar(t, "tipo_membresia", "Nombres compuestos o variantes (Corporativa Estándar, Personal Premium…)", "Se separan en tipo y categoría", cambios(antes_t, df["tipo_membresia"]) - swap)
    registrar(t, "categoria_membresia", "Categoría con valor no reconocido (p. ej. 'Plus')", "Queda 'Sin dato' y se deja registro", desconocidas, "Revisar con ACTHO")
    df["nivel_2027"] = [
        "Oferta propia (persona natural)" if tp == "Persona natural"
        else NIVEL_2027.get(ct, "Sin clasificar")
        for tp, ct in zip(df["tipo_membresia"], df["categoria_membresia"])
    ]

    # Estado.
    df["estado_membresia"] = df["estado_membresia"].map(lambda v: ESTADOS.get(clave(v)) if isinstance(v, str) else np.nan)
    derivar = df["estado_membresia"].isna() & df["estado_registro"].map(lambda v: isinstance(v, str) and clave(v) == "activo")
    df.loc[derivar, "estado_membresia"] = "Activo"
    registrar(t, "estado_membresia", "Estado de la membresía vacío con Estado = Activo", "Se completa como 'Activo'", derivar.sum())
    sin_estado = df["estado_membresia"].isna()
    registrar(t, "estado_membresia", "Estado de la membresía vacío sin otra pista", "Queda 'Sin estado' (no se inventa)", sin_estado.sum(), "Revisar con ACTHO")
    df["estado_membresia"] = df["estado_membresia"].fillna("Sin estado")
    df["es_activo"] = (df["estado_membresia"] == "Activo").astype(int)
    df["es_vigente"] = df["estado_membresia"].isin(VIGENTES).astype(int)

    # Fechas y atípicos.
    for c in ["fecha_afiliacion", "fecha_expiracion", "miembro_desde"]:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    futura = df["fecha_afiliacion"] > corte
    exp_antes = df["fecha_expiracion"] < df["fecha_afiliacion"]
    act_vencida = (df["estado_membresia"] == "Activo") & (df["fecha_expiracion"] < corte)
    vig_sin_exp = (df["es_vigente"] == 1) & df["fecha_expiracion"].isna()
    incons = pd.Series("", index=df.index)
    for mask, txt in [(futura, "Fecha de afiliación futura"), (exp_antes, "Expiración anterior a la afiliación"),
                      (act_vencida, "Activo con expiración vencida"), (vig_sin_exp, "Vigente sin fecha de expiración")]:
        incons = incons.where(~mask, incons + np.where(incons.str.len() > 0, "; ", "") + txt)
    df["inconsistencia"] = incons.replace("", np.nan)
    registrar(t, "fecha_afiliacion", "Fecha de afiliación posterior a la fecha de corte (posible error de digitación, p. ej. 2066)", "Se anula la fecha y se marca en 'inconsistencia'", futura.sum())
    df.loc[futura, "fecha_afiliacion"] = pd.NaT
    registrar(t, "fecha_expiracion", "Expiración anterior a la afiliación", "Se marca en 'inconsistencia' (no se modifica)", exp_antes.sum(), "Marcado")
    registrar(t, "estado_membresia", "Estado Activo con fecha de expiración ya vencida", "Se marca en 'inconsistencia' (no se modifica)", act_vencida.sum(), "Marcado")
    registrar(t, "fecha_expiracion", "Membresía vigente sin fecha de expiración", "Se marca en 'inconsistencia'", vig_sin_exp.sum(), "Marcado")
    registrar(t, "fecha_afiliacion", "Fecha de afiliación vacía", "Se deja vacía (no se inventa)", df["fecha_afiliacion"].isna().sum(), "Sin cambio")
    registrar(t, "fecha_expiracion", "Fecha de expiración vacía", "Se deja vacía (cancelados suelen no tenerla)", df["fecha_expiracion"].isna().sum(), "Sin cambio")
    dias = (df["fecha_expiracion"] - corte).dt.days
    df["dias_a_vencer"] = dias.where(df["es_vigente"] == 1)
    df["rango_vencimiento"] = np.select(
        [df["es_vigente"] == 0, df["dias_a_vencer"].isna(), df["dias_a_vencer"] < 0, df["dias_a_vencer"] <= 30,
         df["dias_a_vencer"] <= 60, df["dias_a_vencer"] <= 90],
        ["No aplica", "Sin fecha", "Vencida", "0-30 días", "31-60 días", "61-90 días"], default="Más de 90 días")

    # Tamaño, empleados, % mujeres.
    def rango(v):
        if not isinstance(v, str):
            return v
        s = re.sub(r"\s*-\s*", "-", clave(v))
        if "mas de" in s:
            return "10.001 o más"
        return s if s in RANGOS_EMPLEADOS else v
    antes = df["rango_empleados"].copy()
    df["rango_empleados"] = df["rango_empleados"].map(rango)
    registrar(t, "rango_empleados", "Formatos distintos ('1 - 50' / '1-50', 'mas de 10.001')", "Se unifica el formato", cambios(antes, df["rango_empleados"]))
    pct = pd.to_numeric(df["pct_mujeres"].astype(str).str.replace("%", "", regex=False), errors="coerce")
    fuera = pct.notna() & ((pct < 0) | (pct > 100))
    registrar(t, "pct_mujeres", "Porcentaje fuera de 0-100", "Se anula", fuera.sum())
    df["pct_mujeres"] = pct.where(~fuera)
    registrar(t, "pct_mujeres", "Texto con símbolo % ('50%')", "Se convierte a número", int(df["pct_mujeres"].notna().sum()))

    # Comunidades y miembros.
    for c in COLS_COMUNIDADES:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df["n_comunidades"] = (df[COLS_COMUNIDADES] > 0).sum(axis=1)
    df["vinculado_comunidades"] = df["vinculado_comunidades"].map(
        lambda v: 1 if str(v).strip().lower() in {"true", "1", "sí", "si"} else 0)
    df["cantidad_miembros"] = pd.to_numeric(df["cantidad_miembros"], errors="coerce")
    df["cantidad_miembros_atipico"] = atipicos_iqr(df["cantidad_miembros"]).astype(int)
    registrar(t, "cantidad_miembros", "Valores extremos (rango intercuartílico)", "Se marca en 'cantidad_miembros_atipico' (no se elimina)", df["cantidad_miembros_atipico"].sum(), "Marcado")

    df["independiente"] = df["independiente"].map(si_no)
    df["es_persona_natural"] = (df["tipo_membresia"] == "Persona natural").astype(int)

    # Nulos en categorías -> 'Sin dato'.
    rellenar(df, t, ["tipo_empresa", "tipo_compania", "tamano_empresa", "rango_empleados", "sector",
                     "subsector", "ciudad", "departamento", "region", "pais", "tipo_consultora",
                     "tipo_membresia", "categoria_membresia"])
    # Campo 'Estado' de Zoho (Activo/Inactivo): se conserva para conciliar con los informes de Zoho.
    df["estado_crm"] = df["estado_registro"].map(
        lambda v: {"activo": "Activo", "inactivo": "Inactivo"}.get(clave(v), "Sin dato") if isinstance(v, str) else "Sin dato")
    df = df.drop(columns=["ciudad_facturacion", "estado_registro"])
    return df.reset_index(drop=True), excluidos


def consolidar_empresas(crm):
    """Un registro por empresa: el más relevante (vigente primero, luego el más reciente)."""
    t = "dim_empresa"
    orden = crm.assign(_p=crm["estado_membresia"].map(ORDEN_ESTADO)).sort_values(
        ["empresa_id", "_p", "fecha_expiracion", "registro_id"], ascending=[True, True, False, False])
    principal = ~orden.duplicated("empresa_id")
    orden["es_registro_principal"] = principal.astype(int)
    n_reg = orden.groupby("empresa_id")["registro_id"].transform("count")
    orden["n_registros_crm"] = n_reg
    registrar(t, "empresa_id", "Empresa con más de un registro en el CRM (membresías de distintos ciclos o personas)",
              "Se toma como principal el vigente / más reciente; los demás quedan en fact_membresia", (~principal).sum(), "Consolidado")
    dim = orden[principal].drop(columns=["_p", "es_registro_principal"]).copy()
    dim["en_crm"] = 1
    dim["origen"] = "CRM"
    membresias = orden.drop(columns=["_p"]).copy()
    return dim.reset_index(drop=True), membresias.reset_index(drop=True)


# ──────────────────────────────────────────────────────────────────────────────
# Eventos y asistencia
# ──────────────────────────────────────────────────────────────────────────────
def cargar_eventos(ruta):
    t = "dim_evento"
    bruto = pd.read_excel(ruta, sheet_name="HOMOLOGACION OFERTA 2027", header=None)
    hi = next(i for i in range(8) if str(bruto.iloc[i, 0]).strip().lower().startswith("n° evento"))
    ev = bruto.iloc[hi + 1:, :7].copy()
    ev.columns = ["evento_id", "hoja_origen", "fecha", "nombre", "linea_2027", "experiencia", "modalidad"]
    ev = ev[pd.to_numeric(ev["evento_id"], errors="coerce").notna()].copy()
    ev["evento_id"] = ev["evento_id"].astype(int)
    for c in ["hoja_origen", "nombre", "linea_2027", "experiencia", "modalidad"]:
        ev[c] = ev[c].map(limpiar_texto).replace("", np.nan)
    ev["hoja_origen"] = ev["hoja_origen"].str.upper()
    ev["fecha"] = pd.to_datetime(ev["fecha"], errors="coerce")
    registrar(t, "fecha", "Fecha del evento no interpretable", "Queda vacía", ev["fecha"].isna().sum(), "Revisar con ACTHO")
    ev["fecha_fin"] = ev["fecha"] + pd.to_timedelta(ev["evento_id"].map(DURACION_EXTRA).fillna(0), unit="D")
    rellenar(ev, t, ["experiencia", "linea_2027", "modalidad"], "Sin dato")
    ev["anio"] = ev["fecha"].dt.year
    ev["mes"] = ev["fecha"].dt.month
    return ev.reset_index(drop=True)


def leer_hoja_evento(ws):
    """Devuelve filas normalizadas de una hoja de evento (los encabezados cambian de hoja a hoja)."""
    filas = list(ws.iter_rows(values_only=True))
    hi = next((i for i, r in enumerate(filas[:8])
               if any(isinstance(v, str) and v.strip().upper().startswith("ID_EMPRESA") for v in r)), None)
    if hi is None:
        return []
    enc = [limpiar_texto(v).lower() if isinstance(v, str) else "" for v in filas[hi]]

    def col(pred):
        return next((i for i, v in enumerate(enc) if v and pred(v)), None)

    ci = col(lambda v: v.startswith("id_empresa"))
    pi = col(lambda v: v.startswith("id_persona"))
    ki = col(lambda v: v.startswith("nivel de cargo"))
    co = col(lambda v: v.startswith("costo"))
    au = col(lambda v: "autoriz" in v or "protecci" in v or "tratamiento" in v)

    def g(r, i):
        return r[i] if i is not None and i < len(r) else None

    salida = []
    for r in filas[hi + 1:]:
        if g(r, ci) is None:
            continue
        salida.append(dict(
            empresa_id=g(r, ci), persona_id=g(r, pi), nivel_cargo=g(r, ki), costo=g(r, co),
            autoriza_datos=g(r, au), codigo_afiliado=r[0] if r else None))
    return salida


def cargar_asistencia(ruta, eventos):
    t = "fact_asistencia"
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    hoja_a_evento = dict(zip(eventos["hoja_origen"], eventos["evento_id"]))
    regs, vacias, sin_evento = [], [], []
    for ws in wb.worksheets:
        nombre = ws.title.strip().upper()
        if nombre.startswith("GENERAL") or "HOMOLOG" in nombre:
            continue
        if nombre not in hoja_a_evento:
            sin_evento.append(ws.title)
            continue
        filas = leer_hoja_evento(ws)
        if not filas:
            vacias.append(ws.title)
        for f in filas:
            f["evento_id"] = hoja_a_evento[nombre]
            regs.append(f)
    registrar(t, "(hoja)", "Hoja de evento vacía o sin encabezado: " + ", ".join(vacias), "El evento queda sin inscritos", len(vacias), "Revisar con ACTHO")
    registrar(t, "(hoja)", "Hoja sin evento en la homologación: " + ", ".join(sin_evento), "Se omite", len(sin_evento), "Revisar con ACTHO")
    a = pd.DataFrame(regs)
    informar(t, "(archivo)", "Filas leídas de las hojas de evento", len(a))

    a["empresa_id"] = validar_id(a["empresa_id"], RX_ID_EMPRESA, t, "empresa_id")
    a["persona_id"] = validar_id(a["persona_id"], RX_ID_PERSONA, t, "persona_id")
    sin_emp = a["empresa_id"].isna()
    registrar(t, "empresa_id", "Fila sin ID de empresa válido", "Se excluye (no se puede asignar a una empresa)", sin_emp.sum(), "Excluido")
    a = a[~sin_emp].copy()

    for c in ["nivel_cargo", "costo"]:
        a[c] = a[c].map(lambda v: limpiar_texto(str(v)) if v is not None and not (isinstance(v, float) and np.isnan(v)) else np.nan)
    # La primera columna de cada hoja trae códigos 1 y 2 (encabezado 'AFILIADO', 'Tipo de asistente', 'Columna 1' o vacío).
    cod = pd.to_numeric(a["codigo_afiliado"], errors="coerce")
    a["codigo_afiliado"] = cod.where(cod.isin([1, 2]))
    registrar(t, "codigo_afiliado", "Primera columna de las hojas con encabezados distintos y valores 1/2", "Se unifica como 'codigo_afiliado' (1 = afiliado, 2 = no afiliado según los datos; confirmar con ACTHO)", cod.notna().sum())
    a["afiliado_segun_hoja"] = a["codigo_afiliado"].map({1: "Afiliado", 2: "No afiliado"}).fillna("Sin dato")
    antes = a["autoriza_datos"].copy()
    a["autoriza_datos"] = a["autoriza_datos"].map(si_no)
    registrar(t, "autoriza_datos", "Variantes de escritura (SI, SÍ, Si, 'SÍ, AUTORIZO…', 'NO, AUTORIZO…')", "Se unifica en Sí / No / Sin dato", cambios(antes, a["autoriza_datos"]))
    a["costo"] = a["costo"].map(lambda v: {"sin costo": "Sin costo", "con costo": "Con costo"}.get(clave(v), np.nan) if isinstance(v, str) else np.nan)
    rellenar(a, t, ["costo", "nivel_cargo"], "Sin dato")

    # Duplicados: la misma persona inscrita dos veces en el mismo evento.
    dup = a.duplicated(["evento_id", "persona_id"], keep="first") & a["persona_id"].notna()
    registrar(t, "persona_id", "Persona repetida en el mismo evento", "Se conserva una sola inscripción", dup.sum(), "Excluido")
    a = a[~dup].copy()
    a = a.sort_values(["evento_id", "empresa_id", "persona_id"]).reset_index(drop=True)
    a.insert(0, "asistencia_id", np.arange(1, len(a) + 1))
    return a


# ──────────────────────────────────────────────────────────────────────────────
# Encuestas
# ──────────────────────────────────────────────────────────────────────────────
def leer_respuestas(ruta, hoja="Responses"):
    bruto = pd.read_excel(ruta, sheet_name=hoja, header=None)
    hi = next(i for i in range(min(6, len(bruto))) if bruto.iloc[i].astype(str).str.contains("ID de respuesta").any())
    enc = [limpiar_texto(str(x)) if pd.notna(x) else f"col_{j}" for j, x in enumerate(bruto.iloc[hi])]
    datos = bruto.iloc[hi + 1:].reset_index(drop=True)
    datos.columns = enc
    return datos


def buscar(df, *fragmentos, exacto_inicio=False):
    frag = [clave(f).replace("¿", "").replace("?", "") for f in fragmentos]
    for c in df.columns:
        k = clave(c).replace("¿", "").replace("?", "").strip()
        if (k.startswith(frag[0]) if exacto_inicio else frag[0] in k) and all(f in k for f in frag[1:]):
            return c
    return None


def calificacion(serie, tabla, campo):
    x = pd.to_numeric(serie, errors="coerce")
    fuera = x.notna() & ~x.between(1, 5)
    registrar(tabla, campo, "Calificación fuera de la escala 1-5", "Se anula", fuera.sum())
    return x.where(~fuera)


def tipo_cruce(metodo):
    k = clave(metodo) if isinstance(metodo, str) else ""
    if k.startswith("correo exacto"):
        return "Exacto"
    if k.startswith(("nombre de empresa", "dominio")):
        return "Aproximado"
    if "sin coincidencia" in k:
        return "Sin coincidencia"
    return "Sin empresa"


def inferir_evento(fecha, modalidad, eventos):
    """Asigna el evento 2026 más reciente (hasta 3 días antes de la respuesta) de la misma modalidad."""
    if pd.isna(fecha) or fecha.year != 2026:
        return np.nan, "Encuesta de 2025 o sin fecha"
    permitidas = {"Presencial", "Híbrido"} if modalidad == "Presencial" else {"Virtual", "Híbrido"}
    d = fecha.normalize()
    cand = eventos[eventos["modalidad"].isin(permitidas) & (eventos["fecha_fin"] <= d) &
                   ((d - eventos["fecha_fin"]).dt.days <= 3)]
    if cand.empty:
        return np.nan, "Sin evento en esa fecha"
    ultima = cand["fecha_fin"].max()
    cand = cand[cand["fecha_fin"] == ultima]
    if len(cand) > 1:
        return np.nan, "Ambiguo (varios eventos el mismo día)"
    return int(cand.iloc[0]["evento_id"]), "Asignado por fecha"


def cargar_encuesta_evento(ruta, modalidad, origen, eventos):
    t = "fact_encuesta_evento"
    d = leer_respuestas(ruta)
    c_id = buscar(d, "id de respuesta", exacto_inicio=True)
    c_ini, c_fin = buscar(d, "respuesta iniciada"), buscar(d, "respuesta completada")
    c_loc = buscar(d, "como calificarias la", exacto_inicio=True)
    c_conv, c_conf = buscar(d, "convocatoria"), buscar(d, "conferencistas")
    c_rel, c_tem = buscar(d, "relevante"), buscar(d, "temarios")
    c_per, c_emp = buscar(d, "nombre completo", exacto_inicio=True), buscar(d, "empresa", "id_empresa", exacto_inicio=True)
    c_ciu, c_crm, c_met = buscar(d, "ciudad", exacto_inicio=True), buscar(d, "empresa_en_crm"), buscar(d, "metodo_asignacion")
    out = pd.DataFrame({
        "respuesta_id": d[c_id].astype(str).str.strip(),
        "origen_encuesta": origen,
        "modalidad": modalidad,
        "fecha_inicio": d[c_ini].map(parsear_fecha_es),
        "fecha_respuesta": d[c_fin].map(parsear_fecha_es),
        "persona_id": validar_id(d[c_per], RX_ID_PERSONA, t, "persona_id"),
        "empresa_id": validar_id(d[c_emp], RX_ID_EMPRESA, t, "empresa_id"),
        "ciudad": canonizar(d[c_ciu].map(limpiar_texto), MANUAL_CIUDAD),
        "calif_espacio": calificacion(d[c_loc], t, "calif_espacio"),
        "calif_convocatoria": calificacion(d[c_conv], t, "calif_convocatoria"),
        "calif_expositor": calificacion(d[c_conf], t, "calif_expositor"),
        "calif_contenido": calificacion(d[c_rel], t, "calif_contenido"),
        "temas_solicitados": d[c_tem].map(limpiar_texto),
        "empresa_en_crm_origen": d[c_crm].map(limpiar_texto),
        "metodo_asignacion_empresa": d[c_met].map(limpiar_texto),
    })
    out["satisfaccion_prom"] = out[["calif_espacio", "calif_convocatoria", "calif_expositor", "calif_contenido"]].mean(axis=1, skipna=True).round(2)
    inf = [inferir_evento(f, modalidad, eventos) for f in out["fecha_respuesta"]]
    out["evento_id"] = [i[0] for i in inf]
    out["evento_inferencia"] = [i[1] for i in inf]
    return out


def cargar_encuesta_post(ruta, eventos):
    t = "fact_encuesta_evento"
    d = leer_respuestas(ruta)
    g = lambda *a, **k: buscar(d, *a, **k)
    out = pd.DataFrame({
        "respuesta_id": d[g("id de respuesta", exacto_inicio=True)].astype(str).str.strip(),
        "origen_encuesta": "post_evento_2026",
        "fecha_inicio": d[g("respuesta iniciada")].map(parsear_fecha_es),
        "fecha_respuesta": d[g("respuesta completada")].map(parsear_fecha_es),
        "persona_id": validar_id(d[g("1. nombre completo", exacto_inicio=True)], RX_ID_PERSONA, t, "persona_id"),
        "empresa_id": validar_id(d[g("4. empresa", exacto_inicio=True)], RX_ID_EMPRESA, t, "empresa_id"),
        "nivel_cargo": d[g("5. cargo", exacto_inicio=True)].map(limpiar_texto),
        "ciudad": canonizar(d[g("6. ciudad", exacto_inicio=True)].map(limpiar_texto), MANUAL_CIUDAD),
        "afiliado_declarado": d[g("7. eres afiliado", exacto_inicio=True)].map(
            lambda v: "Sí" if isinstance(v, str) and clave(v).startswith("si") else ("No" if isinstance(v, str) else "Sin dato")),
        "modalidad": d[g("12. como participaste", exacto_inicio=True)].map(limpiar_texto),
        "satisfaccion_general": calificacion(d[g("13. en general", exacto_inicio=True)], t, "satisfaccion_general"),
        "lo_que_gusto": d[g("16. que fue lo que mas", exacto_inicio=True)].map(limpiar_texto),
        "a_mejorar": d[g("17. que deberiamos mejorar", exacto_inicio=True)].map(limpiar_texto),
        "empresa_en_crm_origen": d[g("empresa_en_crm")].map(limpiar_texto),
        "metodo_asignacion_empresa": d[g("metodo_asignacion")].map(limpiar_texto),
    })
    # NPS: '10 (Promoter)' -> 10, y categoría calculada con la regla estándar.
    c_nps = g("14. de 0 a 10", exacto_inicio=True)
    nps = pd.to_numeric(d[c_nps].astype(str).str.extract(r"^\s*(\d+)")[0], errors="coerce")
    fuera = nps.notna() & ~nps.between(0, 10)
    registrar(t, "nps_puntaje", "Puntaje NPS fuera de 0-10", "Se anula", fuera.sum())
    out["nps_puntaje"] = nps.where(~fuera)
    out["nps_categoria"] = np.select([out["nps_puntaje"] >= 9, out["nps_puntaje"] >= 7, out["nps_puntaje"] >= 0],
                                     ["Promotor", "Pasivo", "Detractor"], default=None)
    # Calificaciones por aspecto (presencial y virtual comparten pregunta con columnas distintas).
    for destino, clave_aspecto in [("calif_expositor", "expositor"), ("calif_contenido", "contenido"),
                                   ("calif_recepcion", "recepcion"), ("calif_espacio", "espacio"),
                                   ("calif_manejo_tiempo", "manejo del tiempo"), ("calif_alimentacion", "alimentacion")]:
        cols = [c for c in d.columns if clave(c).startswith("15.") and f"[{clave_aspecto}" in clave(c)]
        out[destino] = calificacion(d[cols].apply(pd.to_numeric, errors="coerce").bfill(axis=1).iloc[:, 0], t, destino) if cols else np.nan
    aspectos = ["calif_expositor", "calif_contenido", "calif_recepcion", "calif_espacio", "calif_manejo_tiempo", "calif_alimentacion"]
    out["satisfaccion_prom"] = out[aspectos].mean(axis=1, skipna=True).round(2)
    # Consentimientos.
    for destino, frag in [("acepta_tratamiento_datos", "he leido y acepto"), ("acepta_novedades", "quiero recibir novedades"),
                          ("acepta_compartir_datos", "autorizo que actho comparta"), ("acepta_uso_imagen", "autorizo que actho use mi imagen")]:
        c = g(frag)
        out[destino] = d[c].map(si_no) if c else "Sin dato"
    inf = [inferir_evento(f, m, eventos) if isinstance(m, str) else (np.nan, "Sin modalidad") for f, m in zip(out["fecha_respuesta"], out["modalidad"])]
    out["evento_id"] = [i[0] for i in inf]
    out["evento_inferencia"] = [i[1] for i in inf]
    # Temas pedidos (varias opciones por respuesta -> tabla larga).
    filas = []
    for c in d.columns:
        m = re.match(r"^18\..*\[(.+)\]$", c)
        if not m:
            continue
        tema = limpiar_texto(m.group(1))
        for rid, v in zip(out["respuesta_id"], d[c]):
            if isinstance(v, str) and v.strip():
                detalle = v.split(" - ", 1)[1].strip() if tema.lower().startswith("otro") and " - " in v else np.nan
                filas.append(dict(respuesta_id=rid, tema=("Otro" if tema.lower().startswith("otro") else tema), detalle=detalle))
    return out, pd.DataFrame(filas, columns=["respuesta_id", "tema", "detalle"])


def unificar_encuestas(partes, dim_empresa):
    t = "fact_encuesta_evento"
    e = pd.concat(partes, ignore_index=True, sort=False)
    dup = e.duplicated("respuesta_id", keep="first")
    registrar(t, "respuesta_id", "ID de respuesta repetido", "Se conserva el primero", dup.sum(), "Excluido")
    e = e[~dup].copy()
    dup2 = e.duplicated(["persona_id", "fecha_respuesta", "modalidad", "origen_encuesta"], keep="first") & e["persona_id"].notna()
    registrar(t, "persona_id", "Misma persona con dos respuestas en el mismo instante", "Se conserva una", dup2.sum(), "Excluido")
    e = e[~dup2].copy()
    e["tipo_cruce"] = e["metodo_asignacion_empresa"].map(tipo_cruce)
    informar(t, "tipo_cruce", "Respuestas sin empresa identificable", (e["tipo_cruce"] == "Sin empresa").sum())
    informar(t, "tipo_cruce", "Respuestas con empresa 'aproximada' (nombre o dominio de correo)", (e["tipo_cruce"] == "Aproximado").sum())
    conocidas = set(dim_empresa["empresa_id"])
    huerfanas = e["empresa_id"].notna() & ~e["empresa_id"].isin(conocidas)
    registrar(t, "empresa_id", "Empresa de la encuesta que no está en el CRM ni en asistencia", "Se agrega a dim_empresa como 'No afiliado (sin registro en CRM)'", huerfanas.sum(), "Consolidado")
    e["anio"] = e["fecha_respuesta"].dt.year
    for c in ["fecha_respuesta", "fecha_inicio"]:
        fut = e[c] > pd.Timestamp.today() + pd.Timedelta(days=1)
        registrar(t, c, "Fecha de respuesta en el futuro", "Se anula", fut.sum())
        e.loc[fut, c] = pd.NaT
    rellenar(e, t, ["ciudad", "modalidad", "metodo_asignacion_empresa", "empresa_en_crm_origen"], "Sin dato")
    e["evento_inferencia"] = e["evento_inferencia"].fillna("Sin dato")
    e.insert(0, "encuesta_id", np.arange(1, len(e) + 1))
    return e.reset_index(drop=True)


# ──────────────────────────────────────────────────────────────────────────────
# Encuesta de relación a 90 días (NPS de ACTHO)
# ──────────────────────────────────────────────────────────────────────────────
COLS_RELACION = ["respuesta_id", "fecha_respuesta", "persona_id", "empresa_id", "empresa_reportada", "nivel_cargo",
                 "ciudad", "nps_actho", "nps_categoria", "razon_nps", "motivo_afiliacion", "cumplimiento_expectativas",
                 "beneficios_usados", "beneficio_mas_valor", "beneficio_desconocido", "que_funciono", "que_no_funciono",
                 "calif_bienvenida", "calif_ejecutiva", "intencion_renovar", "quiere_contacto",
                 "acepta_tratamiento_datos", "es_prueba"]


def _id_silencioso(serie, regex):
    """Toma el código anonimizado si la celda lo trae; si trae un nombre real, queda vacío (sin registrarlo como error)."""
    return serie.map(lambda v: re.sub(r"\s+", "", v).upper() if isinstance(v, str) else None) \
                .map(lambda v: v if isinstance(v, str) and regex.match(v) else np.nan)


def _opciones(d, prefijo):
    """Columnas de selección múltiple 'N.N. Pregunta [Opción]' -> lista de opciones marcadas por fila."""
    cols = [(c, re.search(r"\[(.+)\]\s*$", c).group(1).strip()) for c in d.columns
            if clave(c).startswith(prefijo) and re.search(r"\[(.+)\]\s*$", c)]
    return [[op for c, op in cols if isinstance(fila[c], str) and fila[c].strip()] for _, fila in d.iterrows()]


def cargar_encuesta_90d(ruta, catalogo):
    """Encuesta de relación a 90 días: NPS de la asociación, intención de renovar y beneficios usados.
    Devuelve (respuestas, usos_declarados). Si el archivo no existe o no tiene respuestas, ambas quedan vacías."""
    t = "fact_encuesta_relacion"
    vacio = pd.DataFrame(columns=COLS_RELACION)
    usos_vacio = pd.DataFrame(columns=["empresa_id", "persona_id", "servicio_id", "fecha", "cantidad", "fuente", "detalle"])
    if ruta is None or not Path(ruta).exists():
        informar(t, "(archivo)", "Encuesta de 90 días: archivo no encontrado (la tabla queda vacía)", 0)
        return vacio, usos_vacio
    d = leer_respuestas(ruta)
    d = d[d[buscar(d, "id de respuesta", exacto_inicio=True)].notna()].reset_index(drop=True)
    informar(t, "(archivo)", "Respuestas de la encuesta de 90 días", len(d))
    if d.empty:
        return vacio, usos_vacio
    g = lambda *a, **k: buscar(d, *a, **k)
    col = lambda c: d[c] if c else pd.Series([np.nan] * len(d))
    out = pd.DataFrame({
        "respuesta_id": d[g("id de respuesta", exacto_inicio=True)].astype(str).str.strip(),
        "fecha_respuesta": col(g("respuesta completada")).map(parsear_fecha_es),
        "persona_id": _id_silencioso(col(g("nombre completo", exacto_inicio=True)), RX_ID_PERSONA),
        "empresa_id": _id_silencioso(col(g("nombre de la empresa", exacto_inicio=True)), RX_ID_EMPRESA),
        "empresa_reportada": col(g("nombre de la empresa", exacto_inicio=True)).map(limpiar_texto),
        "nivel_cargo": col(g("cargo", exacto_inicio=True)).map(limpiar_texto),
        "ciudad": canonizar(col(g("ciudad", exacto_inicio=True)).map(limpiar_texto), MANUAL_CIUDAD),
        "razon_nps": col(g("1.2.", exacto_inicio=True)).map(limpiar_texto),
        "beneficio_mas_valor": col(g("3.2.", exacto_inicio=True)).map(limpiar_texto),
        "beneficio_desconocido": col(g("3.3.", exacto_inicio=True)).map(limpiar_texto),
        "que_funciono": col(g("4.1.", exacto_inicio=True)).map(limpiar_texto),
        "que_no_funciono": col(g("4.2.", exacto_inicio=True)).map(limpiar_texto),
        "quiere_contacto": col(g("6.2.", exacto_inicio=True)).map(si_no),
        "acepta_tratamiento_datos": col(g("he leido y acepto")).map(si_no),
    })
    nps = pd.to_numeric(col(g("1.1.", exacto_inicio=True)).astype(str).str.extract(r"^\s*(\d+)")[0], errors="coerce")
    fuera = nps.notna() & ~nps.between(0, 10)
    registrar(t, "nps_actho", "Puntaje NPS fuera de 0-10", "Se anula", fuera.sum())
    out["nps_actho"] = nps.where(~fuera)
    out["nps_categoria"] = np.select([out["nps_actho"] >= 9, out["nps_actho"] >= 7, out["nps_actho"] >= 0],
                                     ["Promotor", "Pasivo", "Detractor"], default=None)
    for destino, frag in [("cumplimiento_expectativas", "2.2."), ("calif_bienvenida", "5.1."),
                          ("calif_ejecutiva", "5.2."), ("intencion_renovar", "6.1.")]:
        c = g(frag, exacto_inicio=True)
        out[destino] = calificacion(col(c).astype(str).str.extract(r"^\s*(\d+)")[0], t, destino)
    motivos, beneficios = _opciones(d, "2.1."), _opciones(d, "3.1.")
    out["motivo_afiliacion"] = ["; ".join(m) if m else np.nan for m in motivos]
    out["beneficios_usados"] = ["; ".join(b) if b else np.nan for b in beneficios]
    # Respuestas de prueba (el instrumento se probó con una respuesta de ensayo).
    texto = d.apply(lambda f: " ".join(str(x) for x in f if isinstance(x, str)).lower(), axis=1)
    out["es_prueba"] = texto.str.contains(r"\bprueba\b|\btest\b|\bensayo\b", regex=True).astype(int)
    registrar(t, "es_prueba", "Respuestas de prueba en el formulario", "Se marcan y se excluyen de los indicadores", out["es_prueba"].sum(), "Marcado")
    registrar(t, "empresa_id", "Respuesta sin código de empresa reconocible", "Queda sin empresa; se guarda el nombre escrito en 'empresa_reportada'",
              (out["empresa_id"].isna() & (out["es_prueba"] == 0)).sum(), "Revisar con ACTHO")

    # Beneficios que dice haber usado -> uso de beneficios autodeclarado.
    opcion_a_servicio = {clave(op): sid for sid, _, _, _, _, _, _, _, _, op in CATALOGO_SERVICIOS if op}
    filas = []
    for (_, r), lista in zip(out.iterrows(), beneficios):
        if r["es_prueba"] or pd.isna(r["empresa_id"]):
            continue
        for op in lista:
            filas.append(dict(empresa_id=r["empresa_id"], persona_id=r["persona_id"],
                              servicio_id=opcion_a_servicio.get(clave(op), "S99"), fecha=r["fecha_respuesta"],
                              cantidad=1, fuente="Encuesta 90 días (autodeclarado)", detalle=op))
    return out[COLS_RELACION], pd.DataFrame(filas, columns=usos_vacio.columns)


# ──────────────────────────────────────────────────────────────────────────────
# Uso de beneficios: asistencia + comunidades + encuesta 90 días + plantilla mensual
# ──────────────────────────────────────────────────────────────────────────────
NOMBRE_COMUNIDAD = {"com_hr_estrategico": "HR Estratégico", "com_mas_que_un_salario": "Más que un salario",
                    "com_talento_que_elige": "Talento que elige", "com_gente_que_crece": "Gente que crece",
                    "com_talento_aumentado": "Talento aumentado", "com_mujeres_hr": "Mujeres que transforman"}
COLS_PLANTILLA = ["fecha", "empresa_id", "persona_id", "servicio", "cantidad", "fuente", "detalle"]


def construir_catalogo():
    cat = pd.DataFrame(CATALOGO_SERVICIOS, columns=[
        "servicio_id", "servicio", "linea_servicio", "descripcion", "incluido_conectar", "incluido_crecer",
        "incluido_liderar", "condicion", "fuente_dato", "opcion_encuesta_90d"])
    cat["medible"] = (cat["fuente_dato"] != "Sin registro").astype(int)
    return cat


def servicio_de_evento(experiencia, linea):
    k = clave(experiencia) if isinstance(experiencia, str) else ""
    if k.startswith("comunidad"):
        return "S09"
    for frag, sid in EXPERIENCIA_SERVICIO.items():
        if k.startswith(frag):
            return sid
    return LINEA_SERVICIO.get(clave(linea) if isinstance(linea, str) else "", "S05")


def _fecha_plantilla(v):
    """Fecha de la plantilla: celda de fecha de Excel, AAAA-MM-DD o DD/MM/AAAA."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return pd.NaT
    if not isinstance(v, str):
        return pd.Timestamp(v)
    v = v.strip()
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}", v):
        return pd.to_datetime(v[:10], errors="coerce", format="%Y-%m-%d")
    return pd.to_datetime(v, errors="coerce", dayfirst=True)


def cargar_plantilla_uso(ruta, catalogo, empresas_validas):
    """Plantilla mensual (Datos/8. Uso de beneficios/uso_beneficios.xlsx) para los servicios que no dejan
    registro automático: boletín, GetAbstract, Presencia, podcast, Sello, Centro de Experiencias, Rumbo."""
    t = "fact_uso_beneficio"
    vacio = pd.DataFrame(columns=["empresa_id", "persona_id", "servicio_id", "fecha", "cantidad", "fuente", "detalle"])
    if ruta is None or not Path(ruta).exists():
        informar(t, "(plantilla)", "Plantilla mensual de uso de beneficios: sin archivo (solo se usan asistencia, comunidades y encuesta)", 0)
        return vacio
    p = pd.read_excel(ruta, sheet_name="Registros")
    p.columns = [clave(c).replace(" (opcional)", "").strip().replace(" ", "_") for c in p.columns]
    faltan = [c for c in ["fecha", "empresa_id", "servicio"] if c not in p.columns]
    if faltan:
        raise SystemExit(f"La plantilla de uso de beneficios no tiene las columnas: {', '.join(faltan)}")
    p = p.dropna(how="all")
    informar(t, "(plantilla)", "Filas leídas de la plantilla mensual de uso de beneficios", len(p))
    por_nombre = {clave(s): i for i, s in zip(catalogo["servicio_id"], catalogo["servicio"])}
    por_id = set(catalogo["servicio_id"])
    sid = p["servicio"].map(lambda v: (v.strip().upper() if isinstance(v, str) and v.strip().upper() in por_id
                                       else por_nombre.get(clave(v))) if isinstance(v, str) else None)
    out = pd.DataFrame({
        "empresa_id": _id_silencioso(p["empresa_id"], RX_ID_EMPRESA),
        "persona_id": _id_silencioso(p["persona_id"], RX_ID_PERSONA) if "persona_id" in p else np.nan,
        "servicio_id": sid,
        "fecha": p["fecha"].map(_fecha_plantilla),
        "cantidad": pd.to_numeric(p["cantidad"], errors="coerce").fillna(1).astype(int) if "cantidad" in p else 1,
        "fuente": ("Plantilla: " + p["fuente"].fillna("sin fuente").astype(str).map(limpiar_texto)) if "fuente" in p else "Plantilla mensual",
        "detalle": p["detalle"].map(limpiar_texto) if "detalle" in p else np.nan,
    })
    malas = out["empresa_id"].isna() | ~out["empresa_id"].isin(empresas_validas) | out["servicio_id"].isna() | out["fecha"].isna()
    registrar(t, "(plantilla)", "Filas de la plantilla con empresa, servicio o fecha no reconocidos",
              "Se excluyen (revisar la plantilla)", malas.sum(), "Revisar con ACTHO")
    return out[~malas]


def construir_uso_beneficios(asistencia, eventos, dim_empresa, declarados, plantilla, corte):
    """Una fila por uso de un beneficio. 'es_fechado' = 1 si el uso tiene fecha real (cuenta para la ventana
    de 90 días); la vinculación a comunidades del CRM es un estado vigente, no una actividad fechada."""
    t = "fact_uso_beneficio"
    ev = eventos.set_index("evento_id")
    a = asistencia[["empresa_id", "persona_id", "evento_id"]].copy()
    a["servicio_id"] = [servicio_de_evento(ev.at[e, "experiencia"], ev.at[e, "linea_2027"]) for e in a["evento_id"]]
    a["fecha"] = a["evento_id"].map(ev["fecha"])
    a["cantidad"], a["fuente"] = 1, "Asistencia"
    a["detalle"] = a["evento_id"].map(ev["nombre"])
    a["es_fechado"] = 1
    filas = []
    crm = dim_empresa[dim_empresa["en_crm"] == 1]
    for c, nombre in NOMBRE_COMUNIDAD.items():
        if c not in crm:
            continue
        sub = crm[crm[c] > 0]
        for emp, n in zip(sub["empresa_id"], sub[c]):
            filas.append(dict(empresa_id=emp, persona_id=np.nan, servicio_id="S09", fecha=corte, cantidad=int(n),
                              fuente="CRM (comunidad vigente)", detalle=nombre, es_fechado=0))
    com = pd.DataFrame(filas)
    informar(t, "fuente", "Vinculaciones vigentes a comunidades tomadas del CRM", len(com))
    otros = pd.concat([declarados, plantilla], ignore_index=True).assign(es_fechado=1)
    u = pd.concat([a.drop(columns=["evento_id"]), com, otros], ignore_index=True, sort=False)
    u["fecha"] = pd.to_datetime(u["fecha"]).dt.normalize()
    u["cantidad"] = pd.to_numeric(u["cantidad"], errors="coerce").fillna(1).astype(int)
    u = u.sort_values(["empresa_id", "fecha", "servicio_id"]).reset_index(drop=True)
    u.insert(0, "uso_id", np.arange(1, len(u) + 1))
    for f, n in u.groupby("fuente").size().items():
        informar(t, "fuente", f"Usos de beneficios desde '{f}'", n)
    return u[["uso_id", "empresa_id", "persona_id", "servicio_id", "fecha", "cantidad", "fuente", "detalle", "es_fechado"]]


# ──────────────────────────────────────────────────────────────────────────────
# Personas, empresas no afiliadas, calendario y diccionario
# ──────────────────────────────────────────────────────────────────────────────
def construir_personas(asistencia, encuestas, ruta_principal):
    t = "dim_persona"
    a = asistencia[["persona_id", "empresa_id", "nivel_cargo", "autoriza_datos"]].dropna(subset=["persona_id"])
    e = encuestas[["persona_id", "empresa_id"]].dropna(subset=["persona_id"])  # incluye personas sin empresa identificada.assign(nivel_cargo="Sin dato", autoriza_datos="Sin dato")
    pr = pd.read_excel(ruta_principal)
    pr.columns = ["empresa_id", "ciudad", "nivel_cargo", "persona_id"]
    pr["empresa_id"] = validar_id(pr["empresa_id"], RX_ID_EMPRESA, t, "empresa_id")
    pr["persona_id"] = validar_id(pr["persona_id"], RX_ID_PERSONA, t, "persona_id")
    pr["nivel_cargo"] = pr["nivel_cargo"].map(limpiar_texto)
    pr = pr.dropna(subset=["persona_id", "empresa_id"])
    pr_ids = set(pr["persona_id"])
    base = pd.concat([a, e, pr.assign(autoriza_datos="Sin dato")[["persona_id", "empresa_id", "nivel_cargo", "autoriza_datos"]]], ignore_index=True)
    mult = base.dropna(subset=["empresa_id"]).groupby("persona_id")["empresa_id"].nunique()
    registrar(t, "empresa_id", "Persona asociada a más de una empresa", "Se toma la empresa más frecuente (prioridad: asistencia)", (mult > 1).sum(), "Consolidado")

    def moda(s):
        s = s.dropna()
        return s.mode().iloc[0] if not s.empty else np.nan
    sin_dato = lambda s: moda(s[s != "Sin dato"]) if (s != "Sin dato").any() else "Sin dato"
    p = base.groupby("persona_id").agg(
        empresa_id=("empresa_id", moda), nivel_cargo=("nivel_cargo", sin_dato),
        autoriza_datos=("autoriza_datos", lambda s: "No" if (s == "No").any() else ("Sí" if (s == "Sí").any() else "Sin dato")),
    ).reset_index()
    contradictorias = base.groupby("persona_id")["autoriza_datos"].apply(lambda x: {"Sí", "No"} <= set(x)).sum()
    registrar(t, "autoriza_datos", "Persona con autorizaciones contradictorias entre eventos", "Prevalece 'No' (criterio conservador para campañas)", contradictorias)
    p["es_contacto_principal"] = p["persona_id"].isin(pr_ids).astype(int)
    n_ins = asistencia.groupby("persona_id").size().rename("inscripciones_2026")
    p = p.merge(n_ins, on="persona_id", how="left")
    p["inscripciones_2026"] = p["inscripciones_2026"].fillna(0).astype(int)
    p["nivel_cargo"] = p["nivel_cargo"].fillna("Sin dato")
    return p


def completar_empresas(dim, ids_asistencia, ids_encuesta, ids_principal):
    """Agrega las empresas que participan pero no tienen registro en el CRM."""
    nuevas = []
    for ids, origen in [(ids_asistencia, "Asistencia"), (ids_encuesta, "Encuesta"), (ids_principal, "Base de afiliados")]:
        for i in sorted(set(ids) - set(dim["empresa_id"]) - {x["empresa_id"] for x in nuevas}):
            nuevas.append(dict(empresa_id=i, origen=origen))
    n = pd.DataFrame(nuevas)
    if n.empty:
        return dim
    n["en_crm"] = 0
    n["estado_membresia"] = "No afiliado (sin registro en CRM)"
    n["es_activo"] = 0
    n["es_vigente"] = 0
    n["nivel_2027"] = "No afiliado"
    n["ejecutiva"] = "Sin asignar (cuenta ACTHO)"
    n["rango_vencimiento"] = "No aplica"
    informar("dim_empresa", "en_crm", "Empresas que participan pero no están en el CRM", len(n))
    out = pd.concat([dim, n], ignore_index=True, sort=False)
    for c in ["tipo_empresa", "tipo_compania", "tamano_empresa", "rango_empleados", "sector", "subsector", "ciudad",
              "departamento", "region", "pais", "tipo_consultora", "tipo_membresia", "categoria_membresia", "independiente"]:
        out[c] = out[c].fillna("Sin dato")
    for c in ["n_comunidades", "vinculado_comunidades", "n_registros_crm", "es_persona_natural", "cantidad_miembros_atipico"] + COLS_COMUNIDADES:
        out[c] = out[c].fillna(0).astype(int)
    return out


def construir_calendario(desde="2025-01-01", hasta="2027-12-31"):
    f = pd.DataFrame({"fecha": pd.date_range(desde, hasta, freq="D")})
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    f["anio"] = f["fecha"].dt.year
    f["trimestre"] = f["fecha"].dt.quarter
    f["mes"] = f["fecha"].dt.month
    f["nombre_mes"] = f["mes"].map(lambda m: meses[m - 1])
    f["anio_mes"] = f["fecha"].dt.strftime("%Y-%m")
    f["semana_iso"] = f["fecha"].dt.isocalendar().week.astype(int)
    return f


DESCRIPCIONES = {
    "empresa_id": "Código anonimizado de la empresa (EMP-####). Llave común entre CRM, asistencia y encuestas.",
    "persona_id": "Código anonimizado de la persona (P-#####).",
    "registro_id": "ID del registro en Zoho CRM (R-####). Una empresa puede tener varios.",
    "ejecutiva_id": "Identificador de la ejecutiva de cuenta (KAM) propietaria.",
    "ejecutiva": "Ejecutiva de cuenta (KAM) propietaria de la empresa en el CRM.",
    "nombre": "Nombre.",
    "tipo_membresia": "Quién se afilia: Empresa, Consultoras, Universidades o Persona natural.",
    "categoria_membresia": "Categoría en Zoho: Estándar, Premium, Elite o Personal.",
    "nivel_2027": "Nivel de la oferta 2027 equivalente: Conectar (Estándar), Crecer (Premium), Liderar (Elite).",
    "estado_membresia": "Estado de la membresía (Activo, Periodo de gracia, Pronto a expirar, Expirado, Inactivo, Cancelado).",
    "es_activo": "1 si el estado de la membresía es 'Activo' (definición del indicador 'Afiliados activos').",
    "es_vigente": "1 si es Activo, Periodo de gracia o Pronto a expirar.",
    "fecha_afiliacion": "Fecha de afiliación (vacía si venía vacía o era imposible).",
    "fecha_expiracion": "Fecha de expiración de la afiliación.",
    "miembro_desde": "Fecha 'Miembro desde' del CRM.",
    "dias_a_vencer": "Días entre la fecha de corte y la expiración (solo membresías vigentes).",
    "rango_vencimiento": "Vencida, 0-30, 31-60, 61-90 o Más de 90 días.",
    "inconsistencia": "Alertas de coherencia detectadas en el registro (no se corrigen, se marcan).",
    "sector": "Sector económico unificado.",
    "subsector": "Subsector económico unificado.",
    "tamano_empresa": "Micro, Pequeña, Mediana o Grande.",
    "rango_empleados": "Rango de empleados normalizado.",
    "tipo_empresa": "Tipo de empresa (nacional, multinacional, pública…).",
    "tipo_compania": "Tipo de compañía en el CRM (Asociado, Cliente, Aliado, Otro).",
    "ciudad": "Ciudad unificada.",
    "departamento": "Departamento unificado.",
    "region": "Región (derivada del departamento cuando faltaba).",
    "pais": "País unificado.",
    "pct_mujeres": "Porcentaje de mujeres en la compañía (0-100).",
    "independiente": "Si es consultor independiente (Sí/No/Sin dato).",
    "tipo_consultora": "Tipo de consultora (solo membresías de consultoras).",
    "vinculado_comunidades": "1 si está vinculado a alguna comunidad.",
    "n_comunidades": "Número de comunidades temáticas a las que pertenece.",
    "cantidad_miembros": "Cantidad de miembros registrados de la empresa.",
    "cantidad_miembros_atipico": "1 si el valor es extremo según el rango intercuartílico.",
    "n_registros_crm": "Número de registros de la empresa en el CRM.",
    "en_crm": "1 si la empresa tiene registro en el CRM.",
    "origen": "De dónde viene la empresa (CRM, Asistencia, Encuesta, Base de afiliados).",
    "es_persona_natural": "1 si la membresía es de persona natural.",
    "es_registro_principal": "1 si es el registro que representa a la empresa en dim_empresa.",
    "evento_id": "N° de evento según la hoja de homologación 2026.",
    "fecha": "Fecha.", "fecha_fin": "Fecha de fin del evento (eventos de varios días).",
    "hoja_origen": "Nombre de la hoja del libro de asistencia.",
    "linea_2027": "Línea de la oferta 2027 validada por ACTHO (Anticipar, Saber, Pares, Proyectar, Foro, Evento grande).",
    "experiencia": "Experiencia o detalle dentro de la línea.",
    "modalidad": "Presencial, Virtual o Híbrido.",
    "anio": "Año.", "mes": "Mes (número).", "trimestre": "Trimestre.",
    "nombre_mes": "Nombre del mes.", "anio_mes": "Año y mes (AAAA-MM).", "semana_iso": "Semana ISO.",
    "asistencia_id": "Consecutivo de la inscripción (una fila por persona y evento).",
    "nivel_cargo": "Nivel de cargo agrupado.",
    "costo": "Con costo / Sin costo.",
    "autoriza_datos": "Autorización de tratamiento de datos (Sí/No/Sin dato). Condición para usar la persona en campañas.",
    "codigo_afiliado": "Código 1/2 de la primera columna de cada hoja (encabezado 'AFILIADO' en algunas). Los datos sugieren 1 = afiliado, 2 = no afiliado; confirmar con ACTHO.",
    "afiliado_segun_hoja": "Afiliado / No afiliado / Sin dato, interpretando el código de la hoja (hipótesis por confirmar).",
    "empresa_en_crm": "1 si la empresa tiene registro en el CRM.",
    "empresa_afiliada_vigente": "1 si la empresa tiene hoy una membresía vigente en el CRM.",
    "es_contacto_principal": "1 si es el afiliado principal de su empresa según la base de afiliados.",
    "inscripciones_2026": "Número de eventos 2026 en los que está inscrita la persona.",
    "encuesta_id": "Consecutivo de la respuesta.", "respuesta_id": "ID de respuesta del formulario.",
    "origen_encuesta": "Formulario de origen (presencial, virtual o post-evento 2026).",
    "fecha_inicio": "Inicio de la respuesta.", "fecha_respuesta": "Fecha y hora en que se completó la respuesta.",
    "calif_espacio": "Locación (presencial) o plataforma (virtual), 1-5.",
    "calif_convocatoria": "Convocatoria y publicidad, 1-5.",
    "calif_expositor": "Calidad de conferencistas / expositores, 1-5.",
    "calif_contenido": "Relevancia y utilidad del contenido, 1-5.",
    "calif_recepcion": "Recepción y acompañamiento del equipo, 1-5 (solo post-evento).",
    "calif_manejo_tiempo": "Manejo del tiempo, 1-5 (solo post-evento).",
    "calif_alimentacion": "Alimentación, 1-5 (solo post-evento presencial).",
    "satisfaccion_prom": "Promedio de las calificaciones 1-5 disponibles de la respuesta.",
    "satisfaccion_general": "Satisfacción general con el espacio, 1-5 (solo post-evento).",
    "nps_puntaje": "Probabilidad de recomendar, 0-10 (solo post-evento).",
    "nps_categoria": "Promotor (9-10), Pasivo (7-8) o Detractor (0-6).",
    "temas_solicitados": "Temas pedidos en texto libre (encuestas 2025-2026).",
    "lo_que_gusto": "Lo que más gustó (texto libre).", "a_mejorar": "Qué mejorar (texto libre).",
    "afiliado_declarado": "Si la persona dice ser afiliada.",
    "empresa_en_crm_origen": "Indicador 'EMPRESA_EN_CRM' agregado en el archivo original.",
    "metodo_asignacion_empresa": "Cómo se asignó la empresa a la respuesta (correo exacto, nombre, dominio…).",
    "tipo_cruce": "Confiabilidad del cruce con la empresa: Exacto, Aproximado, Sin coincidencia o Sin empresa.",
    "evento_inferencia": "Resultado de inferir el evento por fecha (las encuestas no traen el evento).",
    "acepta_tratamiento_datos": "Aceptó la política de tratamiento de datos.",
    "acepta_novedades": "Quiere recibir novedades y ofertas.",
    "acepta_compartir_datos": "Autoriza compartir datos con patrocinadores.",
    "acepta_uso_imagen": "Autoriza el uso de su imagen.",
    "tema": "Tema solicitado para próximos espacios.", "detalle": "Detalle cuando el tema es 'Otro'.",
    "motivo": "Motivo de exclusión.",
    "inscritos": "Personas inscritas al evento (sin duplicados).",
    "empresas_distintas": "Empresas distintas con al menos una inscripción al evento.",
    "com_hr_estrategico": "Pertenece a la comunidad 'HR Estratégico' (0 = no).",
    "com_mas_que_un_salario": "Pertenece a la comunidad 'Más que un Salario' (0 = no).",
    "com_talento_que_elige": "Pertenece a la comunidad 'Talento que Elige' (0 = no).",
    "com_gente_que_crece": "Pertenece a la comunidad 'Gente que Crece' (0 = no).",
    "com_talento_aumentado": "Pertenece a la comunidad 'Talento Aumentado' (0 = no).",
    "com_mujeres_hr": "Pertenece a la comunidad 'Mujeres HR' (0 = no).",
    "com_influenciador": "Marcado como influenciador en el CRM (0 = no).",
    "estado_crm": "Campo 'Estado' de Zoho (Activo/Inactivo). Es el que cuentan los informes de Zoho; se conserva para conciliar.",
    "servicio_id": "Código del servicio de la oferta 2027 (S01-S17; S99 = otro autodeclarado).",
    "servicio": "Nombre del servicio de la oferta 2027.",
    "linea_servicio": "Línea de la oferta 2027 del servicio (Anticipar, Saber, Pares, Proyectar, Acompañar, Transversal).",
    "descripcion": "Descripción del servicio.",
    "incluido_conectar": "1 si el servicio viene incluido en el nivel Conectar.",
    "incluido_crecer": "1 si el servicio viene incluido en el nivel Crecer.",
    "incluido_liderar": "1 si el servicio viene incluido en el nivel Liderar.",
    "condicion": "Condiciones del servicio según el nivel (documento de equivalencias).",
    "fuente_dato": "Dónde queda registro del uso hoy (Asistencia, CRM, Plantilla mensual, Encuesta 90 días o Sin registro).",
    "opcion_encuesta_90d": "Opción de la pregunta 3.1 de la encuesta de 90 días que corresponde al servicio.",
    "medible": "1 si hoy existe alguna fuente para medir el uso del servicio.",
    "uso_id": "Consecutivo del uso de un beneficio.",
    "cantidad": "Cantidad de usos (p. ej. personas vinculadas a una comunidad o aperturas del boletín).",
    "fuente": "Origen del registro de uso: Asistencia, CRM (comunidad vigente), Encuesta 90 días o Plantilla.",
    "es_fechado": "1 si el uso tiene fecha real (cuenta para la ventana de 90 días); 0 para estados vigentes como las comunidades.",
    "empresa_reportada": "Empresa escrita por quien responde (sirve para identificarla cuando no trae código).",
    "nps_actho": "Probabilidad de recomendar ACTHO a un colega, 0-10 (NPS de la asociación).",
    "razon_nps": "Razón principal de la calificación NPS.",
    "motivo_afiliacion": "Qué motivó la afiliación (opciones marcadas, separadas por ';').",
    "cumplimiento_expectativas": "En qué medida ACTHO ha cumplido lo esperado, 1-5.",
    "beneficios_usados": "Beneficios usados en los últimos 90 días (opciones marcadas, separadas por ';').",
    "beneficio_mas_valor": "Beneficio que más valor ha dado.",
    "beneficio_desconocido": "Beneficio que no sabía que tenía.",
    "que_funciono": "Lo que mejor ha funcionado.", "que_no_funciono": "Lo que no ha estado a la altura.",
    "calif_bienvenida": "Calificación del proceso de bienvenida, 1-5.",
    "calif_ejecutiva": "Calificación del acompañamiento de la ejecutiva de cuenta, 1-5.",
    "intencion_renovar": "Probabilidad de renovar la afiliación, 1-5.",
    "quiere_contacto": "Quiere que lo contacten para conversar de su experiencia.",
    "es_prueba": "1 si es una respuesta de prueba (se excluye de los indicadores).",
}


def diccionario(tablas):
    filas = []
    for nombre, df in tablas.items():
        for c in df.columns:
            s = df[c]
            ej = s.dropna()
            filas.append(dict(
                tabla=nombre, campo=c, tipo=str(s.dtype).replace("object", "texto").replace("int64", "entero")
                .replace("float64", "decimal").replace("datetime64[ns]", "fecha"),
                descripcion=DESCRIPCIONES.get(c, ""), filas=len(df),
                nulos=int(s.isna().sum()), pct_nulos=round(100 * s.isna().mean(), 1),
                valores_distintos=int(s.nunique(dropna=True)),
                ejemplo=str(ej.iloc[0])[:60] if not ej.empty else ""))
    return pd.DataFrame(filas)


# ──────────────────────────────────────────────────────────────────────────────
# Orquestación
# ──────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Limpieza de datos ACTHO")
    ap.add_argument("--datos", default=str(RAIZ / "Datos"))
    ap.add_argument("--salida", default=str(RAIZ / "salida"))
    ap.add_argument("--fecha-corte", default=None, help="AAAA-MM-DD (por defecto, hoy)")
    args = ap.parse_args()
    datos, salida = Path(args.datos), Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    corte = pd.Timestamp(args.fecha_corte) if args.fecha_corte else pd.Timestamp.today().normalize()
    print(f"Fecha de corte: {corte.date()}")
    ruta = {k: datos / v for k, v in ARCHIVOS.items()}
    ruta_opc = {k: datos / v for k, v in ARCHIVOS_OPCIONALES.items()}

    crm, excluidos = cargar_crm(ruta["crm"], corte)
    dim_empresa, membresias = consolidar_empresas(crm)
    eventos = cargar_eventos(ruta["asistencia"])
    asistencia = cargar_asistencia(ruta["asistencia"], eventos)

    enc_pres = cargar_encuesta_evento(ruta["enc_presencial"], "Presencial", "evento_presencial", eventos)
    enc_virt = cargar_encuesta_evento(ruta["enc_virtual"], "Virtual", "evento_virtual", eventos)
    enc_post, temas = cargar_encuesta_post(ruta["enc_post"], eventos)
    temas_pres = pd.concat([enc_pres[["respuesta_id", "temas_solicitados"]], enc_virt[["respuesta_id", "temas_solicitados"]]])
    encuestas = unificar_encuestas([enc_pres, enc_virt, enc_post], dim_empresa)
    catalogo = construir_catalogo()
    relacion, declarados = cargar_encuesta_90d(ruta_opc["enc_90d"], catalogo)

    principal = pd.read_excel(ruta["principal"])
    ids_principal = validar_id(principal.iloc[:, 0], RX_ID_EMPRESA, "dim_persona", "empresa_id").dropna()
    ids_encuesta = pd.concat([encuestas["empresa_id"], relacion["empresa_id"]]).dropna()
    dim_empresa = completar_empresas(dim_empresa, asistencia["empresa_id"].dropna(), ids_encuesta, ids_principal)
    plantilla = cargar_plantilla_uso(ruta_opc["uso_beneficios"], catalogo, set(dim_empresa["empresa_id"]))
    uso = construir_uso_beneficios(asistencia, eventos, dim_empresa, declarados, plantilla, corte)

    # Ejecutivas.
    ej = pd.DataFrame({"nombre": sorted(dim_empresa["ejecutiva"].dropna().unique())})
    ej.insert(0, "ejecutiva_id", np.arange(1, len(ej) + 1))
    dim_empresa = dim_empresa.merge(ej.rename(columns={"nombre": "ejecutiva"}), on="ejecutiva", how="left")
    membresias = membresias.merge(ej.rename(columns={"nombre": "ejecutiva"}), on="ejecutiva", how="left")

    # Marcas de afiliación en asistencia y encuestas.
    vig = dim_empresa.set_index("empresa_id")["es_vigente"]
    en_crm = dim_empresa.set_index("empresa_id")["en_crm"]
    asistencia["empresa_en_crm"] = asistencia["empresa_id"].map(en_crm).fillna(0).astype(int)
    asistencia["empresa_afiliada_vigente"] = asistencia["empresa_id"].map(vig).fillna(0).astype(int)
    encuestas["empresa_en_crm"] = encuestas["empresa_id"].map(en_crm).fillna(0).astype(int)
    for cod_, txt in [(1, "código 1"), (2, "código 2")]:
        sub = asistencia[asistencia["codigo_afiliado"] == cod_]
        if len(sub):
            informar("fact_asistencia", "codigo_afiliado", f"% de inscripciones con {txt} cuya empresa tiene membresía vigente hoy (evidencia: 1 = afiliado, 2 = no afiliado)", round(100 * sub["empresa_afiliada_vigente"].mean()))
    informar("fact_asistencia", "empresa_en_crm", "Inscripciones de empresas que están en el CRM", asistencia["empresa_en_crm"].sum())
    informar("fact_asistencia", "empresa_en_crm", "Inscripciones de empresas que NO están en el CRM (posibles no afiliados)", (asistencia["empresa_en_crm"] == 0).sum())
    informar("fact_encuesta_evento", "evento_id", "Respuestas con evento asignado", encuestas["evento_id"].notna().sum())
    informar("fact_encuesta_evento", "evento_id", "Respuestas sin evento (las encuestas no registran el evento)", encuestas["evento_id"].isna().sum())

    personas = construir_personas(asistencia, encuestas, ruta["principal"])
    ni = asistencia.groupby("evento_id").size()
    eventos["inscritos"] = eventos["evento_id"].map(ni).fillna(0).astype(int)
    eventos["empresas_distintas"] = eventos["evento_id"].map(asistencia.groupby("evento_id")["empresa_id"].nunique()).fillna(0).astype(int)
    calendario = construir_calendario()

    # Columnas finales y orden.
    dim_empresa = dim_empresa.drop(columns=["ejecutiva", "registro_id"], errors="ignore")
    membresias = membresias[["registro_id", "empresa_id", "ejecutiva_id", "tipo_membresia", "categoria_membresia", "nivel_2027",
                             "estado_membresia", "estado_crm", "es_activo", "es_vigente", "fecha_afiliacion", "miembro_desde",
                             "fecha_expiracion", "dias_a_vencer", "rango_vencimiento", "inconsistencia", "es_registro_principal"]]
    ej_out = ej
    temas_out = temas.merge(encuestas[["respuesta_id", "encuesta_id"]], on="respuesta_id", how="left")
    temas_out = temas_out[["encuesta_id", "respuesta_id", "tema", "detalle"]]
    informar("fact_encuesta_temas", "tema", "Temas solicitados registrados (post-evento)", len(temas_out))
    encuestas = encuestas.drop(columns=["fecha_inicio"])
    excluidos = excluidos[["registro_id", "empresa_id", "motivo"]] if not excluidos.empty else excluidos

    tablas = {
        "dim_empresa": dim_empresa, "dim_persona": personas, "dim_evento": eventos, "dim_ejecutiva": ej_out,
        "dim_fecha": calendario, "fact_membresia": membresias, "fact_asistencia": asistencia,
        "fact_encuesta_evento": encuestas, "fact_encuesta_temas": temas_out,
        "dim_servicio": catalogo, "fact_uso_beneficio": uso, "fact_encuesta_relacion": relacion,
    }
    for fecha_col_tabla in ["fecha_afiliacion", "fecha_expiracion", "miembro_desde"]:
        pass
    for nombre, df in tablas.items():
        df.to_csv(salida / f"{nombre}.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    excluidos.to_csv(salida / "excluidos_crm.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(CALIDAD).to_csv(salida / "reporte_calidad.csv", index=False, encoding="utf-8-sig")
    diccionario(tablas).to_csv(salida / "diccionario_datos.csv", index=False, encoding="utf-8-sig")

    print("\nTablas generadas en", salida)
    for nombre, df in tablas.items():
        print(f"  {nombre:<22} {len(df):>6} filas · {df.shape[1]:>2} columnas")
    print(f"  {'reporte_calidad':<22} {len(CALIDAD):>6} hallazgos")
    print("  diccionario_datos, excluidos_crm")


if __name__ == "__main__":
    main()
