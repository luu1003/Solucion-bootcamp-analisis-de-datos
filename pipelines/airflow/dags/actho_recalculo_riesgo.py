# -*- coding: utf-8 -*-
"""
DAG · actho_recalculo_riesgo_diario

Recalcula el semáforo de riesgo cada día (README, sección 9.2):

    actualizar_semaforo → reportar_alertas

* Corre todos los días a las 6:00 a. m. (hora de Bogotá) y también al terminar
  cada ingesta (lo dispara actho_ingesta_datos).
* Mueve la fecha de corte a hoy, así 'días para vencer' y las ventanas de
  participación avanzan aunque no lleguen archivos nuevos.
* Guarda el semáforo de cada empresa en historial.evaluacion_riesgo (con la huella
  de los parámetros usados) y la foto del mes en historial.snapshot_membresia,
  que permite medir renovaciones reales (historial.v_movimientos_mensuales).
* Reporta las empresas que pasaron a rojo desde la evaluación anterior.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pendulum
from airflow.sdk import Param, dag, get_current_context, task

RAIZ = Path(os.environ.get("ACTHO_RAIZ") or Path(__file__).resolve().parents[3])
sys.path.insert(0, str(RAIZ / "src"))
ZONA = "America/Bogota"


@dag(
    dag_id="actho_recalculo_riesgo_diario",
    description="Recalcula el semáforo de riesgo y guarda el historial",
    schedule="0 6 * * *",
    start_date=pendulum.datetime(2026, 11, 1, tz=ZONA),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": pendulum.duration(minutes=2)},
    params={"fecha_corte": Param("", type="string", description="AAAA-MM-DD; vacío = hoy")},
    tags=["actho", "retencion"],
    doc_md=__doc__,
)
def actho_recalculo_riesgo_diario():

    @task
    def actualizar_semaforo() -> dict:
        import ingesta_control as ic
        ctx = get_current_context()
        conf = (ctx["dag_run"].conf or {}) if ctx.get("dag_run") else {}
        fecha = conf.get("fecha_corte") or ctx["params"]["fecha_corte"] or pendulum.now(ZONA).to_date_string()
        resultado = ic.recalcular_riesgo(ic.conectar(), fecha)
        print(f"Fecha de corte {resultado['fecha_corte']} · reglas {resultado['version_reglas']} · "
              f"semáforo {resultado['semaforo']}")
        return resultado

    @task
    def reportar_alertas(resultado: dict) -> int:
        rojos = resultado["nuevos_rojos"]
        if not rojos:
            print("No hay empresas nuevas en rojo desde la evaluación anterior.")
            return 0
        print(f"{len(rojos)} empresas pasaron a ROJO:")
        for r in rojos:
            print(f"  {r['ejecutiva']:<28} {r['empresa_id']}  {r['motivos']}")
        # Aquí se conectará la notificación (correo o tarea en Zoho) de la sección 8 del README.
        return len(rojos)

    reportar_alertas(actualizar_semaforo())


actho_recalculo_riesgo_diario()
