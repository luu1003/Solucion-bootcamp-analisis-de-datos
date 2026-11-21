# -*- coding: utf-8 -*-
"""
DAG · actho_ingesta_datos

Captura los datos limpios en PostgreSQL (README, secciones 7 y 9.1):

    verificar_fuentes → detectar_cambios ─(sin cambios: termina)─┐
                              │                                  │
                         iniciar_ejecucion → limpiar_datos → validar_capa_limpia
                              → cargar_postgres → verificar_base → registrar_lotes
                              → recalcular_riesgo (dispara actho_recalculo_riesgo_diario)

* Corre todos los días a las 5:30 a. m. (hora de Bogotá) y solo procesa si algún
  archivo de Datos/ cambió (huella SHA-256 frente a ingesta.lote_carga).
* Se puede lanzar a mano con los parámetros 'forzar' y 'fecha_corte'.
* Si un paso falla, la ejecución queda 'con_errores' en ingesta.ejecucion y la base
  conserva la carga anterior (la carga es una sola transacción).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pendulum
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sdk import Param, dag, get_current_context, task

RAIZ = Path(os.environ.get("ACTHO_RAIZ") or Path(__file__).resolve().parents[3])
sys.path.insert(0, str(RAIZ / "src"))
ZONA = "America/Bogota"


def _marcar_error(context):
    """Si una tarea falla, deja la ejecución como 'con_errores' con el detalle."""
    try:
        import ingesta_control as ic
        conn = ic.conectar()
        ic.cerrar_ejecucion(conn, estado="con_errores", dag_run_id=context["dag_run"].run_id,
                            detalle={"tarea": context["task_instance"].task_id,
                                     "error": str(context.get("exception"))[:2000]})
    except Exception as e:  # noqa: BLE001
        print(f"No se pudo registrar el error en ingesta.ejecucion: {e}")


@dag(
    dag_id="actho_ingesta_datos",
    description="Limpia las fuentes de ACTHO y las carga en PostgreSQL cuando cambian",
    schedule="30 5 * * *",
    start_date=pendulum.datetime(2026, 11, 1, tz=ZONA),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": pendulum.duration(minutes=2), "on_failure_callback": _marcar_error},
    params={
        "forzar": Param(False, type="boolean", description="Procesar aunque los archivos no hayan cambiado"),
        "fecha_corte": Param("", type="string", description="AAAA-MM-DD; vacío = hoy"),
    },
    tags=["actho", "ingesta"],
    doc_md=__doc__,
)
def actho_ingesta_datos():

    @task
    def verificar_fuentes() -> dict:
        import ingesta_control as ic
        huellas = ic.huellas_fuentes()
        for fuente, d in huellas.items():
            print(f"{fuente:<22} {d['hash'][:12]}…  {d['bytes']:>9,} bytes  {d['archivo']}")
        return huellas

    @task.short_circuit
    def detectar_cambios(huellas: dict) -> bool:
        import ingesta_control as ic
        ctx = get_current_context()
        conn = ic.conectar()
        ic.asegurar_esquemas(conn)
        cambiadas = ic.fuentes_cambiadas(huellas, ic.ultimas_huellas(conn))
        ctx["ti"].xcom_push(key="cambiadas", value=cambiadas)
        if cambiadas:
            print("Fuentes con cambios:", ", ".join(cambiadas))
            return True
        if ctx["params"]["forzar"]:
            print("Sin cambios, pero se fuerza el procesamiento.")
            return True
        ejec = ic.iniciar_ejecucion(conn, ctx["dag_run"].run_id, None, [])
        ic.cerrar_ejecucion(conn, ejec, "sin_cambios")
        print("Ningún archivo cambió desde la última carga: no hay nada que procesar.")
        return False

    @task
    def iniciar_ejecucion() -> dict:
        import ingesta_control as ic
        ctx = get_current_context()
        fecha = ctx["params"]["fecha_corte"] or pendulum.now(ZONA).to_date_string()
        cambiadas = ctx["ti"].xcom_pull(task_ids="detectar_cambios", key="cambiadas") or []
        ejec = ic.iniciar_ejecucion(ic.conectar(), ctx["dag_run"].run_id, fecha, cambiadas)
        return {"ejecucion_id": ejec, "fecha_corte": fecha}

    @task
    def limpiar_datos(info: dict) -> dict:
        import ingesta_control as ic
        ic.ejecutar_script("limpieza_datos.py", "--fecha-corte", info["fecha_corte"])
        return info

    @task
    def validar_capa_limpia(info: dict) -> dict:
        import ingesta_control as ic
        filas = ic.validar_salida()
        for t, n in sorted(filas.items()):
            print(f"{t:<22} {n:>6} filas")
        return {**info, "filas": filas}

    @task
    def cargar_postgres(info: dict) -> dict:
        import ingesta_control as ic
        ic.ejecutar_script("cargar_postgres.py", "--fecha-corte", info["fecha_corte"])
        return info

    @task
    def verificar_base(info: dict) -> dict:
        import ingesta_control as ic
        kpis = ic.verificar_base(ic.conectar())
        print("Indicadores principales:", {k: v for k, v in kpis.items() if v is not None})
        return {**info, "kpis": {k: (float(v) if isinstance(v, (int, float)) or hasattr(v, "is_finite") else str(v))
                                 for k, v in kpis.items() if v is not None}}

    @task
    def registrar_lotes(info: dict, huellas: dict) -> dict:
        import ingesta_control as ic
        conn = ic.conectar()
        ic.registrar_lotes(conn, info["ejecucion_id"], huellas)
        ic.cerrar_ejecucion(conn, info["ejecucion_id"], "procesado",
                            {"filas": info["filas"], "kpis": info["kpis"]})
        return {"fecha_corte": info["fecha_corte"]}

    huellas = verificar_fuentes()
    hay_cambios = detectar_cambios(huellas)
    info = iniciar_ejecucion()
    hay_cambios >> info
    cerrado = registrar_lotes(verificar_base(cargar_postgres(validar_capa_limpia(limpiar_datos(info)))), huellas)

    recalcular = TriggerDagRunOperator(
        task_id="recalcular_riesgo",
        trigger_dag_id="actho_recalculo_riesgo_diario",
        conf={"fecha_corte": "{{ ti.xcom_pull(task_ids='registrar_lotes')['fecha_corte'] }}"},
    )
    cerrado >> recalcular


actho_ingesta_datos()
