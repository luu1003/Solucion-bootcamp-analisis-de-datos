#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Carga de los datos limpios a PostgreSQL · Reto ACTHO

Lee las tablas de salida/ (generadas por src/limpieza_datos.py), crea el
esquema 'actho' con llaves primarias y foráneas, y carga los datos.
Cada ejecución reemplaza el esquema completo, así que se puede repetir.

Conexión: se toma de la variable DATABASE_URL o de un archivo .env en la raíz
del proyecto (copia .env.ejemplo como .env y ajústalo). Ejemplo:
    DATABASE_URL=postgresql://usuario:clave@localhost:5432/actho

Uso:
    python src/cargar_postgres.py
    python src/cargar_postgres.py --esquema actho --solo-sql   (solo escribe sql/esquema.sql)

El archivo .env no se sube a GitHub (está en .gitignore).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ModuleNotFoundError as e:
    raise SystemExit(f"Falta la librería '{e.name}'. Corre:  python setup.py --solo-instalar")

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "salida"

# Orden de carga (dimensiones antes que hechos) y llaves.
TABLAS = {
    "dim_ejecutiva": {"pk": ["ejecutiva_id"]},
    "dim_fecha": {"pk": ["fecha"]},
    "dim_empresa": {"pk": ["empresa_id"], "fk": {"ejecutiva_id": "dim_ejecutiva"}},
    "dim_persona": {"pk": ["persona_id"], "fk": {"empresa_id": "dim_empresa"}},
    "dim_evento": {"pk": ["evento_id"]},
    "dim_servicio": {"pk": ["servicio_id"]},
    "fact_membresia": {"pk": ["registro_id"], "fk": {"empresa_id": "dim_empresa", "ejecutiva_id": "dim_ejecutiva"}},
    "fact_asistencia": {"pk": ["asistencia_id"],
                        "fk": {"empresa_id": "dim_empresa", "persona_id": "dim_persona", "evento_id": "dim_evento"}},
    "fact_encuesta_evento": {"pk": ["encuesta_id"], "unique": ["respuesta_id"],
                             "fk": {"empresa_id": "dim_empresa", "persona_id": "dim_persona", "evento_id": "dim_evento"}},
    "fact_encuesta_temas": {"pk": None, "fk": {"encuesta_id": "fact_encuesta_evento"}},
    "fact_uso_beneficio": {"pk": ["uso_id"], "fk": {"empresa_id": "dim_empresa", "servicio_id": "dim_servicio"}},
    "fact_encuesta_relacion": {"pk": ["respuesta_id"], "fk": {"empresa_id": "dim_empresa"}},
    "reporte_calidad": {"pk": None},
    "diccionario_datos": {"pk": None},
}
FK_DESTINO = {"dim_ejecutiva": "ejecutiva_id", "dim_empresa": "empresa_id", "dim_persona": "persona_id",
              "dim_evento": "evento_id", "fact_encuesta_evento": "encuesta_id", "dim_servicio": "servicio_id"}
COLS_FECHA = {"fecha", "fecha_fin", "fecha_afiliacion", "fecha_expiracion", "miembro_desde"}
COLS_FECHA_HORA = {"fecha_respuesta"}
INDICES = [("fact_asistencia", "empresa_id"), ("fact_asistencia", "evento_id"), ("fact_asistencia", "persona_id"),
           ("fact_encuesta_evento", "empresa_id"), ("fact_encuesta_evento", "evento_id"),
           ("fact_membresia", "empresa_id"), ("dim_empresa", "estado_membresia"), ("dim_empresa", "ejecutiva_id"),
           ("fact_uso_beneficio", "empresa_id"), ("fact_uso_beneficio", "servicio_id")]
# Tipos fijos para tablas que pueden llegar vacías (p. ej. la encuesta de 90 días antes de tener respuestas).
TIPOS_FORZADOS = {"nps_actho": "integer", "cumplimiento_expectativas": "numeric(10,2)", "calif_bienvenida": "numeric(10,2)",
                  "calif_ejecutiva": "numeric(10,2)", "intencion_renovar": "numeric(10,2)", "es_prueba": "integer",
                  "es_fechado": "integer", "cantidad": "integer", "medible": "integer",
                  "incluido_conectar": "integer", "incluido_crecer": "integer", "incluido_liderar": "integer"}


def leer_env():
    """Lee .env (CLAVE=valor) sin dependencias externas; no pisa variables ya definidas."""
    archivo = RAIZ / ".env"
    if not archivo.exists():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def cadena_conexion():
    leer_env()
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    partes = {k: os.environ.get(f"PG{k.upper()}") for k in ["host", "port", "database", "user", "password"]}
    if partes["database"] and partes["user"]:
        return " ".join(f"{'dbname' if k == 'database' else k}={v}" for k, v in partes.items() if v)
    return None


def leer_tabla(nombre):
    ruta = SALIDA / f"{nombre}.csv"
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}. Corre primero la limpieza:  python setup.py")
    df = pd.read_csv(ruta, encoding="utf-8-sig", low_memory=False)
    for c in df.columns:
        if c in COLS_FECHA:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
        elif c in COLS_FECHA_HORA:
            df[c] = pd.to_datetime(df[c], errors="coerce")
        elif TIPOS_FORZADOS.get(c) == "integer":
            df[c] = pd.to_numeric(df[c], errors="coerce").round().astype("Int64")
        elif pd.api.types.is_float_dtype(df[c]) and df[c].dropna().apply(float.is_integer).all() and \
                (c.endswith("_id") or c in {"anio", "mes", "nps_puntaje", "dias_a_vencer", "cantidad_miembros"}):
            df[c] = df[c].astype("Int64")
    return df


def tipo_sql(serie, col):
    if col in TIPOS_FORZADOS:
        return TIPOS_FORZADOS[col]
    if col in COLS_FECHA:
        return "date"
    if col in COLS_FECHA_HORA:
        return "timestamp"
    if pd.api.types.is_bool_dtype(serie):
        return "boolean"
    if pd.api.types.is_integer_dtype(serie):
        return "integer"
    if pd.api.types.is_float_dtype(serie):
        return "numeric(10,2)"
    return "text"


def generar_sql(tablas, esquema):
    sql = [f"-- Esquema generado por src/cargar_postgres.py a partir de salida/\n",
           f"DROP SCHEMA IF EXISTS {esquema} CASCADE;", f"CREATE SCHEMA {esquema};", ""]
    descripciones = tablas.get("diccionario_datos")
    for nombre, df in tablas.items():
        conf = TABLAS[nombre]
        cols = []
        for c in df.columns:
            nulo = " NOT NULL" if conf.get("pk") and c in conf["pk"] else ""
            cols.append(f'    "{c}" {tipo_sql(df[c], c)}{nulo}')
        if conf.get("pk"):
            cols.append(f"    PRIMARY KEY ({', '.join(conf['pk'])})")
        for u in conf.get("unique", []):
            cols.append(f"    UNIQUE ({u})")
        for col, destino in conf.get("fk", {}).items():
            if col in df.columns:
                cols.append(f"    FOREIGN KEY ({col}) REFERENCES {esquema}.{destino}({FK_DESTINO[destino]})")
        sql.append(f"CREATE TABLE {esquema}.{nombre} (\n" + ",\n".join(cols) + "\n);\n")
        if descripciones is not None:
            for _, r in descripciones[descripciones["tabla"] == nombre].iterrows():
                if isinstance(r["descripcion"], str) and r["descripcion"]:
                    texto = r["descripcion"].replace("'", "''")
                    sql.append(f"COMMENT ON COLUMN {esquema}.{nombre}.\"{r['campo']}\" IS '{texto}';")
            sql.append("")
    for tabla, col in INDICES:
        sql.append(f"CREATE INDEX ON {esquema}.{tabla} ({col});")
    return "\n".join(sql) + "\n"


def a_filas(df):
    obj = df.astype(object).where(df.notna(), None)
    return [tuple(None if (isinstance(v, float) and np.isnan(v)) else v for v in fila) for fila in obj.itertuples(index=False)]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Carga los datos limpios a PostgreSQL")
    ap.add_argument("--esquema", default=os.environ.get("PGSCHEMA", "actho"))
    ap.add_argument("--solo-sql", action="store_true", help="solo escribe sql/esquema.sql, sin conectarse")
    ap.add_argument("--fecha-corte", default=None, help="AAAA-MM-DD para los indicadores (por defecto, hoy)")
    args = ap.parse_args()
    esquema = args.esquema

    tablas = {n: leer_tabla(n) for n in TABLAS}
    ddl = generar_sql(tablas, esquema)
    (RAIZ / "sql").mkdir(exist_ok=True)
    (RAIZ / "sql" / "esquema.sql").write_text(ddl, encoding="utf-8")
    print("Esquema escrito en sql/esquema.sql")
    if args.solo_sql:
        return

    url = cadena_conexion()
    if not url:
        raise SystemExit("No hay datos de conexión. Copia .env.ejemplo como .env y escribe tu DATABASE_URL.")
    try:
        import psycopg
    except ModuleNotFoundError:
        raise SystemExit("Falta la librería 'psycopg'. Corre:  python setup.py --solo-instalar")

    try:
        conn = psycopg.connect(url, connect_timeout=10)
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"No se pudo conectar a PostgreSQL: {e}\n"
                         "Revisa que el servidor esté encendido y que DATABASE_URL en .env sea correcta.")
    with conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
            for nombre, df in tablas.items():
                columnas = ", ".join(f'"{c}"' for c in df.columns)
                with cur.copy(f"COPY {esquema}.{nombre} ({columnas}) FROM STDIN") as copia:
                    for fila in a_filas(df):
                        copia.write_row(fila)
            # Verificación: filas en la base = filas en los CSV.
            print(f"\nTablas cargadas en el esquema '{esquema}':")
            for nombre, df in tablas.items():
                cur.execute(f"SELECT count(*) FROM {esquema}.{nombre}")
                n = cur.fetchone()[0]
                marca = "ok" if n == len(df) else f"ESPERADAS {len(df)}"
                print(f"  {nombre:<22} {n:>6} filas  {marca}")
                if n != len(df):
                    raise SystemExit("La cantidad de filas no coincide; se revierte la carga.")
            # Vistas del tablero (indicadores, semáforo, segmentos).
            vistas = RAIZ / "sql" / "vistas_dashboard.sql"
            if vistas.exists():
                cur.execute(vistas.read_text(encoding="utf-8").replace("actho.", f"{esquema}."))
                if args.fecha_corte:
                    cur.execute(f"UPDATE {esquema}.config_parametro SET fecha = %s WHERE clave = 'fecha_corte'",
                                (args.fecha_corte,))
                cur.execute("SELECT count(*) FROM information_schema.views WHERE table_schema = %s", (esquema,))
                print(f"  vistas del tablero      {cur.fetchone()[0]:>6} creadas (sql/vistas_dashboard.sql)")
    print("\nCarga terminada.")


if __name__ == "__main__":
    main()
