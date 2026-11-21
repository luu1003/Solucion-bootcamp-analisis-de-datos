#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Control de la ingesta · Reto ACTHO

Lógica que usan los DAG de Airflow (pipelines/airflow/dags/), escrita sin
depender de Airflow para poder probarla y ejecutarla por separado:

  * Huella (SHA-256) de cada archivo fuente y detección de cambios.
  * Registro de ejecuciones y lotes en el esquema 'ingesta' (trazabilidad).
  * Validación de las tablas limpias antes de cargarlas.
  * Verificación de la base después de la carga.
  * Recálculo del semáforo y fotos históricas en el esquema 'historial'.

También funciona como línea de comandos:
    python src/ingesta_control.py ingesta       # limpia y carga solo si los archivos cambiaron (+ --forzar)
    python src/ingesta_control.py estado        # últimas ejecuciones y lotes
    python src/ingesta_control.py cambios       # ¿hay archivos nuevos?
    python src/ingesta_control.py recalcular    # semáforo y fotos con fecha de hoy
    python src/ingesta_control.py recalcular --fecha-corte 2026-11-21
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(os.environ.get("ACTHO_RAIZ") or Path(__file__).resolve().parent.parent)
DATOS = RAIZ / "Datos"
SALIDA = RAIZ / "salida"
sys.path.insert(0, str(RAIZ / "src"))

# Fuente (código del README) -> archivo dentro de Datos/
FUENTES = {
    "zoho_crm": "1. Base de datos de afiliados/Base de datos Hackaton_anonimizada.xlsx",
    "asistencia_excel": "2. Registros de participación en actividades/BASE ASISTENCIA A EVENTOS 2026 - EAFIT_anonimizada.xlsx",
    "encuesta_presencial": "3. Encuestas y NPS/Eventos Presenciales 2026_anonimizada.xlsx",
    "encuesta_virtual": "3. Encuestas y NPS/Eventos Virtuales ACRIP 2026_anonimizada.xlsx",
    "encuesta_post_evento": "3. Encuestas y NPS/ENCUESTA-POST-EVENTOS (PRESENCIAL Y VIRTUAL)_anonimizada.xlsx",
    "base_afiliados": "5. Indicadores y reportes actuales/Base de datos afiliados ACTHO_anonimizada.xlsx",
}

# Reglas de validación de la capa limpia (antes de cargar).
LLAVES = {
    "dim_empresa": "empresa_id", "dim_persona": "persona_id", "dim_evento": "evento_id",
    "dim_ejecutiva": "ejecutiva_id", "fact_membresia": "registro_id",
    "fact_asistencia": "asistencia_id", "fact_encuesta_evento": "encuesta_id",
}
RELACIONES = [  # (tabla, columna, tabla destino, columna destino, admite nulos)
    ("dim_empresa", "ejecutiva_id", "dim_ejecutiva", "ejecutiva_id", False),
    ("dim_persona", "empresa_id", "dim_empresa", "empresa_id", True),
    ("fact_membresia", "empresa_id", "dim_empresa", "empresa_id", False),
    ("fact_asistencia", "empresa_id", "dim_empresa", "empresa_id", False),
    ("fact_asistencia", "persona_id", "dim_persona", "persona_id", False),
    ("fact_asistencia", "evento_id", "dim_evento", "evento_id", False),
    ("fact_encuesta_evento", "empresa_id", "dim_empresa", "empresa_id", True),
    ("fact_encuesta_evento", "persona_id", "dim_persona", "persona_id", True),
    ("fact_encuesta_evento", "evento_id", "dim_evento", "evento_id", True),
]
RANGOS = [  # (tabla, columna, mínimo, máximo)
    ("fact_encuesta_evento", "nps_puntaje", 0, 10),
    ("fact_encuesta_evento", "satisfaccion_prom", 1, 5),
    ("fact_encuesta_evento", "satisfaccion_general", 1, 5),
]
MINIMOS = {"dim_empresa": 100, "fact_asistencia": 100, "dim_evento": 1, "fact_encuesta_evento": 1}


# ──────────────────────────────────────────────────────────────────────────────
# Conexión y esquemas de control
# ──────────────────────────────────────────────────────────────────────────────
def conectar():
    import psycopg
    from cargar_postgres import cadena_conexion
    url = cadena_conexion()
    if not url:
        raise RuntimeError("No hay conexión configurada (DATABASE_URL o archivo .env).")
    return psycopg.connect(url, connect_timeout=10, autocommit=True)


def asegurar_esquemas(conn):
    conn.execute((RAIZ / "sql" / "control.sql").read_text(encoding="utf-8"))


# ──────────────────────────────────────────────────────────────────────────────
# Fuentes y cambios
# ──────────────────────────────────────────────────────────────────────────────
def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def huellas_fuentes() -> dict:
    faltan = [r for r in FUENTES.values() if not (DATOS / r).exists()]
    if faltan:
        raise FileNotFoundError("Faltan archivos en Datos/:\n  - " + "\n  - ".join(faltan))
    return {f: {"archivo": r, "hash": sha256(DATOS / r), "bytes": (DATOS / r).stat().st_size}
            for f, r in FUENTES.items()}


def ultimas_huellas(conn) -> dict:
    filas = conn.execute("""
        SELECT DISTINCT ON (fuente) fuente, hash_sha256
        FROM ingesta.lote_carga WHERE estado = 'procesado'
        ORDER BY fuente, cargado_en DESC""").fetchall()
    return {f: h for f, h in filas}


def fuentes_cambiadas(actuales: dict, previas: dict) -> list:
    return sorted(f for f, d in actuales.items() if previas.get(f) != d["hash"])


# ──────────────────────────────────────────────────────────────────────────────
# Ejecuciones y lotes
# ──────────────────────────────────────────────────────────────────────────────
def iniciar_ejecucion(conn, dag_run_id, fecha_corte, cambiadas) -> int:
    return conn.execute("""
        INSERT INTO ingesta.ejecucion (dag_run_id, fecha_corte, fuentes_cambiadas)
        VALUES (%s, %s, %s) RETURNING id""", (dag_run_id, fecha_corte, cambiadas)).fetchone()[0]


def cerrar_ejecucion(conn, ejecucion_id=None, estado="procesado", detalle=None, dag_run_id=None):
    sql = "UPDATE ingesta.ejecucion SET fin = now(), estado = %s, detalle = coalesce(detalle, '{}'::jsonb) || %s::jsonb "
    params = [estado, json.dumps(detalle or {}, default=str)]
    if ejecucion_id is not None:
        conn.execute(sql + "WHERE id = %s", params + [ejecucion_id])
    else:
        conn.execute(sql + "WHERE dag_run_id = %s AND estado = 'en_curso'", params + [dag_run_id])


def registrar_lotes(conn, ejecucion_id, huellas):
    for fuente, d in huellas.items():
        conn.execute("""
            INSERT INTO ingesta.lote_carga (ejecucion_id, fuente, archivo, hash_sha256, bytes)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (fuente, hash_sha256) DO UPDATE
               SET ejecucion_id = EXCLUDED.ejecucion_id, estado = 'procesado', cargado_en = now()""",
                     (ejecucion_id, fuente, d["archivo"], d["hash"], d["bytes"]))


# ──────────────────────────────────────────────────────────────────────────────
# Pasos del proyecto
# ──────────────────────────────────────────────────────────────────────────────
def ejecutar_script(script, *args) -> str:
    """Corre un script de src/ con el mismo Python y devuelve su salida; falla con el detalle."""
    r = subprocess.run([sys.executable, str(RAIZ / "src" / script), *map(str, args)], cwd=RAIZ,
                       capture_output=True, text=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    salida = (r.stdout or "") + (r.stderr or "")
    print(salida)
    if r.returncode != 0:
        raise RuntimeError(f"{script} terminó con error:\n{salida[-3000:]}")
    return salida


def validar_salida() -> dict:
    """Revisa las tablas limpias antes de cargarlas. Lanza ValueError con todos los problemas."""
    import pandas as pd
    errores, resumen = [], {}
    tablas = {}
    for nombre in set(LLAVES) | {t for r in RELACIONES for t in (r[0], r[2])}:
        ruta = SALIDA / f"{nombre}.csv"
        if not ruta.exists():
            errores.append(f"No existe {ruta.name}")
            continue
        tablas[nombre] = pd.read_csv(ruta, encoding="utf-8-sig", low_memory=False)
        resumen[nombre] = len(tablas[nombre])
    for nombre, minimo in MINIMOS.items():
        if nombre in tablas and len(tablas[nombre]) < minimo:
            errores.append(f"{nombre}: {len(tablas[nombre])} filas (mínimo esperado {minimo})")
    for nombre, llave in LLAVES.items():
        if nombre in tablas:
            s = tablas[nombre][llave]
            if s.isna().any():
                errores.append(f"{nombre}.{llave}: {int(s.isna().sum())} llaves vacías")
            if s.duplicated().any():
                errores.append(f"{nombre}.{llave}: {int(s.duplicated().sum())} llaves repetidas")
    for t, c, td, cd, nulos in RELACIONES:
        if t in tablas and td in tablas:
            s = tablas[t][c]
            if not nulos and s.isna().any():
                errores.append(f"{t}.{c}: {int(s.isna().sum())} vacíos no permitidos")
            huerfanos = s.dropna()[~s.dropna().isin(tablas[td][cd])]
            if len(huerfanos):
                errores.append(f"{t}.{c}: {len(huerfanos)} valores sin correspondencia en {td} (p. ej. {huerfanos.iloc[0]})")
    for t, c, lo, hi in RANGOS:
        if t in tablas and c in tablas[t]:
            x = pd.to_numeric(tablas[t][c], errors="coerce").dropna()
            fuera = ((x < lo) | (x > hi)).sum()
            if fuera:
                errores.append(f"{t}.{c}: {int(fuera)} valores fuera de {lo}-{hi}")
    if errores:
        raise ValueError("La validación de la capa limpia falló:\n  - " + "\n  - ".join(errores))
    return resumen


def verificar_base(conn, esquema="actho") -> dict:
    """Comprueba que la base quedó coherente con los CSV y que el tablero responde."""
    import pandas as pd
    errores = []
    for nombre in LLAVES:
        esperadas = len(pd.read_csv(SALIDA / f"{nombre}.csv", encoding="utf-8-sig", usecols=[0]))
        n = conn.execute(f"SELECT count(*) FROM {esquema}.{nombre}").fetchone()[0]
        if n != esperadas:
            errores.append(f"{nombre}: {n} filas en la base, {esperadas} en el CSV")
    cur = conn.execute(f"SELECT * FROM {esquema}.v_kpi_principal")
    filas = cur.fetchall()
    if len(filas) != 1:
        errores.append("v_kpi_principal no devolvió una fila")
    if errores:
        raise ValueError("La verificación de la base falló:\n  - " + "\n  - ".join(errores))
    return {d.name: v for d, v in zip(cur.description, filas[0])}


# ──────────────────────────────────────────────────────────────────────────────
# Recálculo diario del semáforo y fotos históricas
# ──────────────────────────────────────────────────────────────────────────────
def recalcular_riesgo(conn, fecha_corte: date | str | None = None) -> dict:
    fecha_corte = str(fecha_corte or date.today())
    existe = conn.execute("SELECT to_regclass('actho.v_empresa_360') IS NOT NULL").fetchone()[0]
    if not existe:
        raise RuntimeError("No existe actho.v_empresa_360: corre primero la ingesta.")
    asegurar_esquemas(conn)
    conn.execute("UPDATE actho.config_parametro SET fecha = %s WHERE clave = 'fecha_corte'", (fecha_corte,))
    version = conn.execute("""SELECT left(md5(string_agg(clave || '=' || coalesce(valor::text, ''), ';' ORDER BY clave)), 8)
                              FROM actho.config_parametro WHERE clave <> 'fecha_corte'""").fetchone()[0]
    conn.execute("""
        INSERT INTO historial.evaluacion_riesgo
            (fecha_corte, empresa_id, ejecutiva, nivel_2027, estado_membresia, dias_a_vencer,
             pts_vencimiento, pts_participacion, pts_satisfaccion, puntaje, semaforo, motivos, version_reglas)
        SELECT fecha_corte, empresa_id, ejecutiva, nivel_2027, estado_membresia, dias_a_vencer,
               pts_vencimiento, pts_participacion, pts_satisfaccion, puntaje_riesgo, semaforo, motivos_riesgo, %s
        FROM actho.v_empresa_360 WHERE es_vigente = 1
        ON CONFLICT (fecha_corte, empresa_id) DO UPDATE SET
            ejecutiva = EXCLUDED.ejecutiva, nivel_2027 = EXCLUDED.nivel_2027,
            estado_membresia = EXCLUDED.estado_membresia, dias_a_vencer = EXCLUDED.dias_a_vencer,
            pts_vencimiento = EXCLUDED.pts_vencimiento, pts_participacion = EXCLUDED.pts_participacion,
            pts_satisfaccion = EXCLUDED.pts_satisfaccion, puntaje = EXCLUDED.puntaje,
            semaforo = EXCLUDED.semaforo, motivos = EXCLUDED.motivos,
            version_reglas = EXCLUDED.version_reglas, calculado_en = now()""", (version,))
    conn.execute("""
        INSERT INTO historial.snapshot_membresia
            (periodo, empresa_id, ejecutiva, estado_membresia, tipo_membresia, categoria_membresia,
             nivel_2027, fecha_afiliacion, fecha_expiracion, es_vigente)
        SELECT date_trunc('month', %s::date)::date, empresa_id, ejecutiva, estado_membresia, tipo_membresia,
               categoria_membresia, nivel_2027, fecha_afiliacion, fecha_expiracion, es_vigente
        FROM actho.v_empresa_360 WHERE en_crm = 1
        ON CONFLICT (periodo, empresa_id) DO UPDATE SET
            ejecutiva = EXCLUDED.ejecutiva, estado_membresia = EXCLUDED.estado_membresia,
            tipo_membresia = EXCLUDED.tipo_membresia, categoria_membresia = EXCLUDED.categoria_membresia,
            nivel_2027 = EXCLUDED.nivel_2027, fecha_afiliacion = EXCLUDED.fecha_afiliacion,
            fecha_expiracion = EXCLUDED.fecha_expiracion, es_vigente = EXCLUDED.es_vigente, tomado_en = now()""",
                 (fecha_corte,))
    conteo = dict(conn.execute("""SELECT semaforo, count(*) FROM historial.evaluacion_riesgo
                                  WHERE fecha_corte = %s GROUP BY semaforo""", (fecha_corte,)).fetchall())
    nuevos_rojos = conn.execute("""
        SELECT a.empresa_id, a.ejecutiva, a.motivos
        FROM historial.evaluacion_riesgo a
        LEFT JOIN LATERAL (SELECT semaforo FROM historial.evaluacion_riesgo b
                           WHERE b.empresa_id = a.empresa_id AND b.fecha_corte < a.fecha_corte
                           ORDER BY b.fecha_corte DESC LIMIT 1) prev ON true
        WHERE a.fecha_corte = %s AND a.semaforo = 'Rojo' AND prev.semaforo IS DISTINCT FROM 'Rojo'
          AND prev.semaforo IS NOT NULL
        ORDER BY a.ejecutiva, a.empresa_id""", (fecha_corte,)).fetchall()
    return {"fecha_corte": fecha_corte, "version_reglas": version, "semaforo": conteo,
            "nuevos_rojos": [dict(empresa_id=e, ejecutiva=k, motivos=m) for e, k, m in nuevos_rojos]}


# ──────────────────────────────────────────────────────────────────────────────
# Ingesta completa (la usan setup.py y la línea de comandos; Airflow usa los pasos sueltos)
# ──────────────────────────────────────────────────────────────────────────────
def ingesta_completa(fecha_corte=None, forzar=False, origen="setup") -> dict:
    """Limpia y carga solo si algún archivo de Datos/ cambió (o si se fuerza o falta la base).
    Siempre recalcula el semáforo con la fecha de corte."""
    from datetime import datetime
    fecha = str(fecha_corte or date.today())
    conn = conectar()
    asegurar_esquemas(conn)
    huellas = huellas_fuentes()
    cambiadas = fuentes_cambiadas(huellas, ultimas_huellas(conn))
    hay_base = conn.execute("SELECT to_regclass('actho.v_empresa_360') IS NOT NULL").fetchone()[0]
    if not cambiadas and hay_base and not forzar:
        r = recalcular_riesgo(conn, fecha)
        return {"estado": "sin_cambios", "fecha_corte": fecha, "semaforo": r["semaforo"]}
    ejec = iniciar_ejecucion(conn, f"{origen}__{datetime.now().isoformat(timespec='seconds')}", fecha, cambiadas)
    try:
        ejecutar_script("limpieza_datos.py", "--fecha-corte", fecha)
        filas = validar_salida()
        ejecutar_script("cargar_postgres.py", "--fecha-corte", fecha)
        kpis = verificar_base(conn)
        registrar_lotes(conn, ejec, huellas)
        cerrar_ejecucion(conn, ejec, "procesado", {"filas": filas, "kpis": {k: str(v) for k, v in kpis.items()}})
    except Exception as e:  # noqa: BLE001
        cerrar_ejecucion(conn, ejec, "con_errores", {"error": str(e)[:2000]})
        raise
    r = recalcular_riesgo(conn, fecha)
    return {"estado": "procesado", "fecha_corte": fecha, "fuentes_cambiadas": cambiadas, "semaforo": r["semaforo"]}


# ──────────────────────────────────────────────────────────────────────────────
def _cli():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    argumentos = sys.argv[1:]
    fecha = None
    if "--fecha-corte" in argumentos:
        i = argumentos.index("--fecha-corte")
        fecha = argumentos[i + 1] if i + 1 < len(argumentos) else None
        argumentos = argumentos[:i] + argumentos[i + 2:]
    forzar = "--forzar" in argumentos
    argumentos = [a for a in argumentos if a != "--forzar"]
    orden = argumentos[0] if argumentos else "estado"
    conn = conectar()
    asegurar_esquemas(conn)
    if orden == "ingesta":
        r = ingesta_completa(fecha, forzar)
        if r["estado"] == "sin_cambios":
            print("Datos al día: ningún archivo de Datos/ cambió desde la última carga (se omite la limpieza).")
        else:
            print("Datos procesados y cargados. Fuentes con cambios:", ", ".join(r.get("fuentes_cambiadas") or ["(forzado)"]))
        print(f"Semáforo al {r['fecha_corte']}: {r['semaforo']}")
        return
    if orden == "cambios":
        cambiadas = fuentes_cambiadas(huellas_fuentes(), ultimas_huellas(conn))
        print("Fuentes con cambios:", ", ".join(cambiadas) if cambiadas else "ninguna")
    elif orden == "recalcular":
        print(json.dumps(recalcular_riesgo(conn, fecha or (argumentos[1] if len(argumentos) > 1 else None)),
                         ensure_ascii=False, indent=2, default=str))
    else:
        for fila in conn.execute("""SELECT id, dag_run_id, inicio::timestamp(0), estado, fecha_corte, fuentes_cambiadas
                                    FROM ingesta.ejecucion ORDER BY id DESC LIMIT 10"""):
            print(*fila, sep=" | ")


if __name__ == "__main__":
    _cli()
